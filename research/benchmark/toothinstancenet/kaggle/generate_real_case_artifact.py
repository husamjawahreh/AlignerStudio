#!/usr/bin/env python3
"""Generate the AlignerStudio fixture package from real upstream outputs only."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

UPPER_SHA256 = "60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48"
LOWER_SHA256 = "dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b"
CHECKPOINT_SHA256 = "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"
SOURCE_REVISION = "424252e3d94a1565c8c2090eb5bb456b76386b93"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    mesh = trimesh.load(path, force="mesh", process=False)
    return np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.int64)


def majority(values: np.ndarray) -> int | None:
    values = values[values > 0]
    if values.size == 0:
        return None
    unique, counts = np.unique(values, return_counts=True)
    return int(unique[np.argmax(counts)])


def generate_jaw(
    jaw: str,
    source_stl: Path,
    prediction_json: Path,
    output_dir: Path,
) -> dict:
    expected_hash = UPPER_SHA256 if jaw == "upper" else LOWER_SHA256
    actual_hash = sha256(source_stl)
    if actual_hash != expected_hash:
        raise RuntimeError(f"{jaw} STL hash mismatch: {actual_hash} != {expected_hash}")
    payload = json.loads(prediction_json.read_text())
    instances = payload.get("instances")
    labels = payload.get("labels")
    if not isinstance(instances, list) or not isinstance(labels, list):
        raise RuntimeError(f"{prediction_json} is not an upstream instance output")
    vertices, faces = load_mesh(source_stl)
    if len(instances) != len(vertices) or len(labels) != len(vertices):
        raise RuntimeError(
            f"{jaw} output cardinality does not match original vertices: "
            f"instances={len(instances)} labels={len(labels)} vertices={len(vertices)}"
        )
    instance_array = np.asarray(instances, dtype=np.int64)
    label_array = np.asarray(labels, dtype=np.int64)
    jaw_dir = output_dir / jaw
    mesh_dir = jaw_dir / "individual_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    records = []
    empty_fragments = []
    for instance_id in sorted(int(value) for value in np.unique(instance_array) if value >= 0):
        vertex_indices = np.flatnonzero(instance_array == instance_id)
        face_mask = np.all(np.isin(faces, vertex_indices), axis=1)
        face_indices = np.flatnonzero(face_mask)
        fdi = majority(label_array[vertex_indices])
        if face_indices.size == 0:
            empty_fragments.append(instance_id)
            continue
        local_vertices = np.unique(faces[face_indices].reshape(-1))
        local_lookup = {int(value): index for index, value in enumerate(local_vertices.tolist())}
        local_faces = np.asarray(
            [[local_lookup[int(value)] for value in faces[index]] for index in face_indices],
            dtype=np.int64,
        )
        mesh = trimesh.Trimesh(vertices=vertices[local_vertices], faces=local_faces, process=False)
        mesh_path = mesh_dir / f"instance_{instance_id:03d}.ply"
        mesh.export(mesh_path)
        records.append(
            {
                "instance_id": instance_id,
                "fdi_number": fdi,
                "arch": jaw,
                "vertices": vertices[local_vertices].tolist(),
                "faces": local_faces.tolist(),
                "vertex_indices": local_vertices.tolist(),
                "triangle_indices": face_indices.tolist(),
                "centroid": vertices[vertex_indices].mean(axis=0).tolist(),
                "confidence": 1.0,
                "provenance": "experimental",
                "fixture": True,
                "experimental": True,
                "mesh_path": str(mesh_path.relative_to(output_dir)),
            }
        )
    (jaw_dir / f"CASE_{jaw}.json").write_text(
        json.dumps(
            {
                "source_kind": "validated_real_case",
                "fixture": True,
                "experimental": True,
                "arch": jaw,
                "source_mesh_path": str(source_stl),
                "source_stl_sha256": actual_hash,
                "input_vertices": len(vertices),
                "input_faces": len(faces),
                "instances": records,
                "empty_instance_ids": empty_fragments,
            },
            indent=2,
        )
    )
    return {
        "arch": jaw,
        "source_stl_sha256": actual_hash,
        "input_vertices": len(vertices),
        "input_faces": len(faces),
        "detected_instances": len(np.unique(instance_array[instance_array >= 0])),
        "valid_meshes": len(records),
        "excluded_zero_face_fragments": empty_fragments,
        "prediction_json": str(prediction_json),
        "mesh_files": [record["mesh_path"] for record in records],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selected-mapping", type=Path, required=True)
    parser.add_argument("--instseg-coordinates", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.checkpoint) != CHECKPOINT_SHA256:
        raise SystemExit("checkpoint_integrity_failed")
    revision = subprocess.check_output(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"source_revision_mismatch: {revision}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.selected_mapping.is_file() or not args.instseg_coordinates.is_file():
        raise SystemExit("missing real upstream correspondence NPZ artifact")
    shutil.copy2(args.selected_mapping, args.output_dir / "selected_to_original_vertex_mapping.npz")
    shutil.copy2(args.instseg_coordinates, args.output_dir / "exact_instseg_coordinates.npz")
    jaws = []
    for jaw in ("upper", "lower"):
        prediction = args.prediction_dir / f"CASE_{jaw}.json"
        if not prediction.exists():
            prediction = args.prediction_dir / f"STEM_{jaw}.json"
        if not prediction.exists():
            raise SystemExit(f"missing upstream instance output: {jaw}")
        jaws.append(generate_jaw(jaw, args.input_dir / f"{jaw}.stl", prediction, args.output_dir))
        shutil.copy2(
            args.output_dir / jaw / f"CASE_{jaw}.json",
            args.output_dir / f"{jaw}.json",
        )
    manifest = {
        "schema_version": "toothinstancenet-validated-real-case-v1",
        "source_kind": "validated_real_case",
        "fixture": True,
        "experimental": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "preprocessing": {
            "norm": True,
            "clean": True,
            "with_color": False,
            "zscore_std": 17.3281,
            "instseg_voxel_size": 0.025,
        },
        "jaws": jaws,
    }
    (args.output_dir / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2))
    mapping = {
        "source_kind": "validated_real_case",
        "fixture": True,
        "experimental": True,
        "jaws": jaws,
    }
    (args.output_dir / "instance_fdi_mapping.json").write_text(json.dumps(mapping, indent=2))
    (args.output_dir / "final_instance_audit.json").write_text(json.dumps(manifest, indent=2))
    (args.output_dir / "mesh_manifest.json").write_text(
        json.dumps(
            {
                "source_kind": "validated_real_case",
                "fixture": True,
                "experimental": True,
                "jaws": jaws,
            },
            indent=2,
        )
    )
    (args.output_dir / "alignerstudio_toothinstancenet_integration_spec.json").write_text(
        json.dumps(
            {
                "source_kind": "validated_real_case",
                "fixture": True,
                "experimental": True,
                "fixture_directory": str(args.output_dir),
                "upper": "upper/CASE_upper.json",
                "lower": "lower/CASE_lower.json",
            },
            indent=2,
        )
    )
    (args.output_dir / "alignerstudio_toothinstancenet_implementation_contract.json").write_text(
        json.dumps(
            {
                "source_kind": "validated_real_case",
                "fixture": True,
                "experimental": True,
                "manifest": "artifact-manifest.json",
                "checkpoint_sha256": CHECKPOINT_SHA256,
                "source_revision": revision,
            },
            indent=2,
        )
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
