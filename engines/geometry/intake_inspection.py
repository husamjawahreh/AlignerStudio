"""Deterministic scan intake inspection.

Reads STL, PLY, and OBJ. Does not modify the source file and does not invent
units, FDI, arch, or clinical axes.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import trimesh

from domain.case.intake import (
    OrientationKind,
    readiness_from_findings,
    resolve_arch,
    segmentation_input_binding,
)

_DEGENERATE_AREA = 1e-12
_DUPLICATE_DECIMALS = 6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _format_kind(path: Path, header: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".ply":
        lowered = header.lstrip().lower()
        if lowered.startswith(b"ply") and b"format ascii" in lowered:
            return "ply_ascii"
        return "ply"
    if suffix == ".obj":
        return "obj"
    if suffix != ".stl":
        return suffix.lstrip(".") or "unknown"
    if len(header) >= 84:
        count = int.from_bytes(header[80:84], "little")
        if path.stat().st_size == 84 + 50 * count:
            return "stl_binary"
    text = header.lstrip().lower()
    if text.startswith(b"solid"):
        return "stl_ascii"
    return "stl_binary"


def _stored_stl_normals(path: Path, kind: str) -> bool | None:
    if kind == "stl_ascii":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            if line.strip().lower().startswith("facet normal"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        values = [float(parts[2]), float(parts[3]), float(parts[4])]
                    except ValueError:
                        continue
                    if any(value != 0.0 for value in values):
                        return True
        return False
    if kind != "stl_binary":
        return None
    data = path.read_bytes()
    if len(data) < 84:
        return False
    count = int.from_bytes(data[80:84], "little")
    offset = 84
    for _ in range(min(count, 64)):
        if offset + 12 > len(data):
            break
        normal = np.frombuffer(data[offset : offset + 12], dtype="<f4")
        if np.any(normal != 0):
            return True
        offset += 50
    return False


def _finite_blocker(vertices: np.ndarray) -> str | None:
    if vertices.size == 0:
        return None
    if not np.isfinite(vertices).all():
        return "coordinates_not_finite"
    return None


def _edge_counts(faces: np.ndarray) -> tuple[int, int]:
    if len(faces) == 0:
        return 0, 0
    edges = np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return int(np.sum(counts == 1)), int(np.sum(counts > 2))


def _component_count(mesh: trimesh.Trimesh) -> int:
    if len(mesh.faces) == 0:
        return 0
    labels = trimesh.graph.connected_component_labels(
        mesh.face_adjacency, node_count=len(mesh.faces)
    )
    return int(len(np.unique(labels))) if len(labels) else 0


def _geometric_orientation(vertices: np.ndarray) -> dict[str, Any]:
    if len(vertices) < 3 or not np.isfinite(vertices).all():
        return {
            "kind": OrientationKind.COMPUTED_GEOMETRIC_ORIENTATION.value,
            "available": False,
            "clinical_axes": False,
            "reason": "Fewer than three finite vertices.",
        }
    centered = vertices - vertices.mean(axis=0)
    try:
        _values, vectors = np.linalg.eigh(centered.T @ centered)
    except np.linalg.LinAlgError:
        return {
            "kind": OrientationKind.COMPUTED_GEOMETRIC_ORIENTATION.value,
            "available": False,
            "clinical_axes": False,
            "reason": "Geometric axes did not converge.",
        }
    order = np.argsort(_values)[::-1]
    axes = vectors[:, order]
    return {
        "kind": OrientationKind.COMPUTED_GEOMETRIC_ORIENTATION.value,
        "available": True,
        "clinical_axes": False,
        "method": "vertex_pca",
        "axes": [[float(value) for value in row] for row in axes.T.tolist()],
        "centroid": [float(value) for value in vertices.mean(axis=0)],
        "limitation": "PCA is a geometric frame. It is not a clinical occlusal or tooth axis.",
    }


def _colors_available(mesh: trimesh.Trimesh) -> bool:
    visual = getattr(mesh, "visual", None)
    return bool(getattr(visual, "defined", False))


def _load(path: Path) -> tuple[trimesh.Trimesh | None, list[dict[str, Any]], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    objects: list[dict[str, Any]] = []
    try:
        loaded = trimesh.load(path, process=False, force=None)
    except Exception as exc:  # noqa: BLE001 - unreadable input is a blocker, not a crash
        return None, objects, [f"unreadable:{exc.__class__.__name__}"], warnings
    if isinstance(loaded, trimesh.Scene):
        meshes = [geom for geom in loaded.geometry.values() if isinstance(geom, trimesh.Trimesh)]
        dropped = len(loaded.geometry) - len(meshes)
        if dropped:
            blockers.append("non_mesh_objects_present")
        if not meshes:
            blockers.append("empty_mesh")
            return None, objects, blockers, warnings
        for name, geom in loaded.geometry.items():
            if isinstance(geom, trimesh.Trimesh):
                objects.append(
                    {
                        "name": str(name),
                        "vertex_count": int(len(geom.vertices)),
                        "face_count": int(len(geom.faces)),
                    }
                )
        if len(meshes) > 1:
            warnings.append("multiple_objects_preserved")
            mesh = trimesh.util.concatenate(meshes)
        else:
            mesh = meshes[0]
        return mesh, objects, blockers, warnings
    if not isinstance(loaded, trimesh.Trimesh):
        return None, objects, ["not_a_triangle_mesh"], warnings
    return loaded, objects, blockers, warnings


def inspect_source_file(
    path: str | Path,
    *,
    case_id: str | None = None,
    explicit_arch: str | None = None,
    original_filename: str | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    """Inspect one source file. The file bytes are not written."""
    started = perf_counter()
    source = Path(path)
    filename = original_filename or source.name
    if not source.is_file():
        return _blocked(
            case_id=case_id,
            artifact_id=artifact_id,
            filename=filename,
            blockers=["file_missing"],
            source_sha256=None,
            file_size=None,
        )
    hash_started = perf_counter()
    source_sha = _sha256(source)
    hash_ms = (perf_counter() - hash_started) * 1000
    header = source.read_bytes()[:256]
    kind = _format_kind(source, header)
    file_size = source.stat().st_size
    parse_started = perf_counter()
    mesh, objects, blockers, warnings = _load(source)
    parse_ms = (perf_counter() - parse_started) * 1000
    if _sha256(source) != source_sha:
        blockers.append("source_bytes_changed_during_read")
    inspect_started = perf_counter()
    quality = _quality(mesh, blockers, warnings, kind=kind)
    inspect_ms = (perf_counter() - inspect_started) * 1000
    blockers = quality["blockers"]
    warnings = quality["warnings"]
    vertices = np.zeros((0, 3)) if mesh is None else np.asarray(mesh.vertices, dtype=np.float64)
    bounds = None if mesh is None or len(vertices) == 0 else mesh.bounds
    area = None
    volume = None
    if mesh is not None and len(mesh.faces):
        area = float(mesh.area)
        if quality["checks"].get("watertight"):
            topology, _welded = _topology_view(mesh, kind)
            volume = float(topology.volume)
    normals_stored = _stored_stl_normals(source, kind)
    record = {
        "case_id": case_id,
        "artifact_id": artifact_id or str(uuid.uuid4()),
        "role": "SOURCE_FILE",
        "original_filename": filename,
        "format": kind,
        "sha256": source_sha,
        "file_size": file_size,
        "imported_at": datetime.now(UTC).isoformat(),
        "source_path": str(source),
        "source_path_is_local_storage": True,
        "source_bytes_modified": False,
        "vertex_count": 0 if mesh is None else int(len(mesh.vertices)),
        "face_count": 0 if mesh is None else int(len(mesh.faces)),
        "bounding_box": None
        if bounds is None
        else {
            "min": [float(value) for value in bounds[0]],
            "max": [float(value) for value in bounds[1]],
        },
        "surface_area": area,
        "volume": volume,
        "volume_reason": None
        if volume is not None
        else "Volume is omitted unless the mesh is watertight.",
        "normals": {
            "stored_face_normals": normals_stored,
            "available": normals_stored is True,
        },
        "colors_available": False if mesh is None else _colors_available(mesh),
        "units": None,
        "units_encoded": False,
        "units_reason": "STL, PLY, and OBJ bytes inspected here do not carry a guaranteed unit.",
        "coordinates": {
            "stored_frame": OrientationKind.SOURCE_COORDINATES.value,
            "normalized_view": {
                "kind": OrientationKind.NORMALIZED_VIEW_COORDINATES.value,
                "applied_to_source": False,
                "translation_to_centroid": None
                if len(vertices) == 0
                else [float(value) for value in (-vertices.mean(axis=0))],
            },
            "clinical_orientation": {
                "kind": OrientationKind.CLINICAL_ORIENTATION.value,
                "available": False,
            },
            "model_orientation": {
                "kind": OrientationKind.MODEL_ORIENTATION.value,
                "available": False,
            },
            "geometric_orientation": _geometric_orientation(vertices),
        },
        "arch": resolve_arch(explicit=explicit_arch),
        "objects": objects,
        "quality": quality,
        "warnings": warnings,
        "blockers": blockers,
        "readiness": readiness_from_findings(blockers=blockers, warnings=warnings),
        "truth_state": "COMPUTED",
        "provenance": "real",
        "fdi_assigned": False,
        "occlusion_established": False,
        "fixture": False,
        "relationships": [
            {"from": "SOURCE_FILE", "to": "IMPORTED_MESH", "sha256": source_sha},
        ],
        "segmentation_input": segmentation_input_binding(source_sha),
        "derived_artifacts": [],
        "timings_ms": {
            "hash_ms": hash_ms,
            "parse_ms": parse_ms,
            "inspection_ms": inspect_ms,
            "total_ms": (perf_counter() - started) * 1000,
            "repair_ms": None,
        },
    }
    return record


def _topology_view(mesh: trimesh.Trimesh, kind: str) -> tuple[trimesh.Trimesh, bool]:
    """STL has no shared vertex indices. Weld a copy for topology only."""
    if not kind.startswith("stl"):
        return mesh, False
    welded = mesh.copy()
    welded.merge_vertices()
    return welded, True


def _quality(
    mesh: trimesh.Trimesh | None,
    blockers: list[str],
    warnings: list[str],
    *,
    kind: str = "",
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "empty_mesh": mesh is None or (len(mesh.vertices) == 0 and len(mesh.faces) == 0),
        "zero_vertices": mesh is not None and len(mesh.vertices) == 0,
        "zero_faces": mesh is not None and len(mesh.faces) == 0,
        "non_finite_coordinates": False,
        "duplicate_vertex_groups": 0,
        "degenerate_faces": 0,
        "duplicate_face_groups": 0,
        "boundary_edges": 0,
        "non_manifold_edges": 0,
        "component_count": 0,
        "watertight": False,
        "self_intersection": "not_run",
        "suspicious_scale": False,
        "topology_welded_for_inspection": False,
    }
    if mesh is None:
        unreadable = any(item.startswith("unreadable") for item in blockers)
        if "file_missing" not in blockers and not unreadable:
            blockers.append("unreadable")
        return {"checks": checks, "blockers": blockers, "warnings": warnings}
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    finite = _finite_blocker(vertices)
    if finite:
        checks["non_finite_coordinates"] = True
        blockers.append(finite)
    if len(mesh.vertices) == 0:
        blockers.append("zero_vertices")
    if len(mesh.faces) == 0:
        blockers.append("zero_faces")
    topology, welded = _topology_view(mesh, kind)
    checks["topology_welded_for_inspection"] = welded
    if len(vertices) and not welded:
        rounded = np.round(vertices, decimals=_DUPLICATE_DECIMALS)
        _, counts = np.unique(rounded, axis=0, return_counts=True)
        duplicate_groups = int(np.sum(counts > 1))
        checks["duplicate_vertex_groups"] = duplicate_groups
        if duplicate_groups:
            warnings.append("duplicate_vertices")
    if len(mesh.faces):
        areas = np.asarray(mesh.area_faces, dtype=np.float64)
        degenerate = int(np.sum(~np.isfinite(areas) | (areas <= _DEGENERATE_AREA)))
        checks["degenerate_faces"] = degenerate
        if degenerate:
            warnings.append("degenerate_faces")
        ordered = np.sort(np.asarray(mesh.faces), axis=1)
        _, face_counts = np.unique(ordered, axis=0, return_counts=True)
        duplicate_faces = int(np.sum(face_counts > 1))
        checks["duplicate_face_groups"] = duplicate_faces
        if duplicate_faces:
            warnings.append("duplicate_faces")
        boundary, nonmanifold = _edge_counts(np.asarray(topology.faces))
        checks["boundary_edges"] = boundary
        checks["non_manifold_edges"] = nonmanifold
        if boundary:
            warnings.append("boundary_edges")
        if nonmanifold:
            warnings.append("non_manifold_edges")
        checks["component_count"] = _component_count(topology)
        if checks["component_count"] > 1:
            warnings.append("disconnected_components")
        checks["watertight"] = bool(topology.is_watertight)
        if not checks["watertight"]:
            warnings.append("open_surface")
        extent = mesh.extents
        max_extent = float(np.max(extent)) if len(extent) else 0.0
        checks["max_extent"] = max_extent
        if max_extent > 500 or (max_extent > 0 and max_extent < 0.01):
            checks["suspicious_scale"] = True
            warnings.append("suspicious_scale")
        density = float(len(mesh.faces) / mesh.area) if mesh.area > 0 else None
        checks["face_density_per_area"] = density
        checks["self_intersection"] = "not_run"
    return {
        "checks": checks,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _blocked(
    *,
    case_id: str | None,
    artifact_id: str | None,
    filename: str,
    blockers: list[str],
    source_sha256: str | None,
    file_size: int | None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "artifact_id": artifact_id or str(uuid.uuid4()),
        "role": "SOURCE_FILE",
        "original_filename": filename,
        "format": "unknown",
        "sha256": source_sha256,
        "file_size": file_size,
        "imported_at": datetime.now(UTC).isoformat(),
        "source_bytes_modified": False,
        "vertex_count": 0,
        "face_count": 0,
        "units": None,
        "units_encoded": False,
        "arch": resolve_arch(explicit=None),
        "warnings": [],
        "blockers": blockers,
        "readiness": readiness_from_findings(blockers=blockers, warnings=[]),
        "truth_state": "COMPUTED",
        "provenance": "real",
        "fdi_assigned": False,
        "occlusion_established": False,
        "fixture": False,
        "derived_artifacts": [],
        "quality": {"checks": {}, "blockers": blockers, "warnings": []},
    }


def derive_cleaned_mesh(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Write a derived mesh. The source file is hashed before and after and left unchanged."""
    source_path = Path(source)
    dest_path = Path(destination)
    before = _sha256(source_path)
    started = perf_counter()
    mesh = trimesh.load(source_path, process=False, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("Derived cleanup requires one triangle mesh.")
    cleaned = mesh.copy()
    cleaned.merge_vertices()
    cleaned.update_faces(cleaned.nondegenerate_faces())
    cleaned.remove_unreferenced_vertices()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.export(dest_path)
    repair_ms = (perf_counter() - started) * 1000
    after = _sha256(source_path)
    if after != before:
        raise RuntimeError("Source bytes changed while writing a derived mesh.")
    output_sha = _sha256(dest_path)
    return {
        "role": "OPTIONAL_DERIVED_CLEAN_MESH",
        "source_sha256": before,
        "output_sha256": output_sha,
        "output_path": str(dest_path),
        "algorithm": "trimesh_merge_vertices_drop_degenerate",
        "library": "trimesh",
        "library_version": trimesh.__version__,
        "parameters": {
            "merge_vertices": True,
            "drop_degenerate_faces": True,
            "watertight_conversion": False,
        },
        "truth_state": "DERIVED",
        "provenance": "generated",
        "limitations": (
            "This is a computational cleanup of duplicate vertices and degenerate faces. "
            "It is not a clinical tooth and it is not a watertight crown."
        ),
        "replaces_source": False,
        "timings_ms": {"repair_ms": repair_ms},
    }
