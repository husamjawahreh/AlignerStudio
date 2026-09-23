"""Strict loader for validated ToothInstanceNet per-vertex artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from adapters.toothinstancenet.contract import ToothInstanceNetDiagnostics
from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothCoordinateSystem,
    ToothIdentificationResult,
)
from domain.tooth.segmentation import (
    SegmentationMetadata,
    ToothInstance,
    ToothSegmentationResult,
)
from engines.segmentation.toothinstancenet import ToothInstanceNetInferenceResult


class ToothInstanceNetFixtureError(ValueError):
    """Raised when an explicit validated artifact is malformed."""


ARTIFACT_ID = "official_real_case_stage2_verified_v1"
ARTIFACT_ZIP_SHA256 = "b0f57d45e19ec1c981964dcad1309570fdc96ec21052ada62050fa3ccb8621b2"
EXPECTED_CONFIGURATION = {
    "m3_as_m2": True,
    "distinguish_left_right": False,
    "distinguish_upper_lower": False,
    "norm": True,
    "clean": True,
    "uniform_density_voxel_size": [0.025, 0.01],
    "stage2_iters": 0,
    "post_process_labels": False,
    "do_align": True,
}
EXPECTED_LABELS = {
    ArchType.UPPER: {0, 11, 12, 13, 14, 15, 16, 17},
    ArchType.LOWER: {0, 31, 32, 33, 34, 35, 36, 37},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_extract_zip(archive: Path) -> Path:
    archive_hash = _sha256(archive)
    if archive_hash != ARTIFACT_ZIP_SHA256:
        raise ToothInstanceNetFixtureError(
            f"Artifact ZIP SHA-256 does not match the verified artifact: {archive_hash}"
        )
    cache_root = Path(tempfile.gettempdir()) / "alignerstudio-toothinstancenet-artifacts"
    destination = cache_root / ARTIFACT_ID
    manifest = destination / "manifest.json"
    if not manifest.exists():
        cache_root.mkdir(parents=True, exist_ok=True)
        temporary = cache_root / f".{ARTIFACT_ID}.tmp"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        try:
            with zipfile.ZipFile(archive) as archive_file:
                root = temporary.resolve()
                members = archive_file.infolist()
                for member in members:
                    target = (temporary / member.filename).resolve()
                    if target != root and root not in target.parents:
                        raise ToothInstanceNetFixtureError(
                            f"Unsafe artifact ZIP member path: {member.filename}"
                        )
                archive_file.extractall(temporary)
            extracted_manifest = next(temporary.rglob("manifest.json"), None)
            if extracted_manifest is None:
                raise ToothInstanceNetFixtureError("Artifact ZIP does not contain manifest.json")
            shutil.move(str(extracted_manifest.parent), destination)
        except (OSError, zipfile.BadZipFile) as error:
            raise ToothInstanceNetFixtureError(
                f"Unable to extract artifact ZIP: {error}"
            ) from error
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return destination


def _artifact_root(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_file() and candidate.suffix.lower() == ".zip":
        return _safe_extract_zip(candidate)
    if not candidate.is_dir():
        raise ToothInstanceNetFixtureError(f"Validated artifact is unavailable: {candidate}")
    return candidate


def _verify_checksums(root: Path) -> dict[str, str]:
    checksum_file = root / "SHA256SUMS.txt"
    if not checksum_file.is_file():
        raise ToothInstanceNetFixtureError("Validated artifact is missing SHA256SUMS.txt")
    expected: dict[str, str] = {}
    for line in checksum_file.read_text().splitlines():
        digest, separator, relative = line.strip().partition("  ")
        if not separator or len(digest) != 64:
            raise ToothInstanceNetFixtureError("Malformed SHA256SUMS.txt entry")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ToothInstanceNetFixtureError(f"Unsafe checksum member path: {relative}")
        expected[relative] = digest
    for relative, digest in expected.items():
        member = root / relative
        if not member.is_file() or _sha256(member) != digest:
            raise ToothInstanceNetFixtureError(f"Artifact checksum mismatch: {relative}")
    required = {"manifest.json", "lower.json", "upper.json", "lower.stl", "upper.stl"}
    if not required.issubset(expected):
        missing = ", ".join(sorted(required - set(expected)))
        raise ToothInstanceNetFixtureError(f"Artifact checksum manifest is missing: {missing}")
    return expected


def _load_indexed_stl(
    path: Path,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ToothInstanceNetFixtureError(f"Invalid STL file: {path.name}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + triangle_count * 50:
        raise ToothInstanceNetFixtureError(f"Invalid STL topology size: {path.name}")
    vertices: list[tuple[float, float, float]] = []
    vertex_lookup: dict[tuple[float, float, float], int] = {}
    faces: list[tuple[int, int, int]] = []
    for triangle_index in range(triangle_count):
        values = struct.unpack_from("<12fH", data, 84 + triangle_index * 50)
        triangle: list[int] = []
        for offset in (3, 6, 9):
            vertex = tuple(float(value) for value in values[offset : offset + 3])
            if vertex not in vertex_lookup:
                vertex_lookup[vertex] = len(vertices)
                vertices.append(vertex)
            triangle.append(vertex_lookup[vertex])
        if len(set(triangle)) != 3:
            raise ToothInstanceNetFixtureError(f"Degenerate STL triangle at index {triangle_index}")
        faces.append(tuple(triangle))
    return vertices, faces


def _validate_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ToothInstanceNetFixtureError("Validated artifact is missing manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as error:
        raise ToothInstanceNetFixtureError("Malformed manifest.json") from error
    if manifest.get("stage") != "instances":
        raise ToothInstanceNetFixtureError("Artifact manifest stage must be instances")
    if manifest.get("configuration") != EXPECTED_CONFIGURATION:
        raise ToothInstanceNetFixtureError(
            "Artifact configuration does not match the verified contract"
        )
    audits = manifest.get("semantic_audit")
    if not isinstance(audits, list) or len(audits) != 2 or not all(
        audit.get("semantic_pass") is True for audit in audits
    ):
        raise ToothInstanceNetFixtureError("Artifact semantic audit is missing or failed")
    return manifest


def _validate_arch(
    root: Path,
    arch: ArchType,
    manifest: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[tuple[float, float, float]],
    list[tuple[int, int, int]],
    dict[int, int],
]:
    json_path = root / f"{arch.value}.json"
    stl_path = root / f"{arch.value}.stl"
    if not json_path.is_file() or not stl_path.is_file():
        raise ToothInstanceNetFixtureError(
            f"Artifact is missing {arch.value}.json or {arch.value}.stl"
        )
    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError as error:
        raise ToothInstanceNetFixtureError(f"Malformed {arch.value}.json") from error
    instances = payload.get("instances")
    labels = payload.get("labels")
    if not isinstance(instances, list) or not isinstance(labels, list):
        raise ToothInstanceNetFixtureError(
            f"{arch.value}.json must contain array instances and labels"
        )
    vertices, faces = _load_indexed_stl(stl_path)
    if len(instances) != len(labels) or len(instances) != len(vertices):
        raise ToothInstanceNetFixtureError(f"{arch.value} JSON/STL vertex cardinality mismatch")
    if set(instances) != set(range(14)) | {-1}:
        raise ToothInstanceNetFixtureError(f"{arch.value} contains unexpected instance IDs")
    expected_labels = EXPECTED_LABELS[arch]
    if not set(labels).issubset(expected_labels):
        raise ToothInstanceNetFixtureError(f"{arch.value} contains unexpected semantic labels")
    if set(labels) != expected_labels:
        raise ToothInstanceNetFixtureError(f"{arch.value} is missing an expected semantic label")
    instance_to_label: dict[int, int] = {}
    for instance_id in range(14):
        values = {
            int(label)
            for value, label in zip(instances, labels, strict=True)
            if value == instance_id
        }
        if len(values) != 1 or next(iter(values)) == 0:
            raise ToothInstanceNetFixtureError(
                f"{arch.value} instance {instance_id} does not have exactly one semantic label"
            )
        instance_to_label[instance_id] = next(iter(values))
    if any(label != 0 for value, label in zip(instances, labels, strict=True) if value == -1):
        raise ToothInstanceNetFixtureError(f"{arch.value} background vertices must have label 0")
    audit = next(
        (item for item in manifest["semantic_audit"] if item.get("arch") == arch.value),
        None,
    )
    if audit is None or audit.get("instance_to_label") != {
        str(key): value for key, value in instance_to_label.items()
    }:
        raise ToothInstanceNetFixtureError(f"{arch.value} semantic audit does not match JSON")
    return payload, vertices, faces, instance_to_label


def load_validated_fixture(
    path: str | Path,
    *,
    arch: ArchType,
    source_mesh_path: str | Path | None = None,
) -> ToothInstanceNetInferenceResult:
    """Load only an explicitly selected validated artifact; never auto-fallback."""
    root = _artifact_root(path)
    checksums = _verify_checksums(root)
    manifest = _validate_manifest(root)
    payload, vertices, faces, instance_to_label = _validate_arch(root, arch, manifest)
    instances_array = payload["instances"]
    source_stl_sha256 = checksums[f"{arch.value}.stl"]
    source_json = f"{arch.value}.json"
    artifact_note = (
        f"source_kind=validated_real_case; artifact_id={ARTIFACT_ID}; fixture=true; "
        f"experimental=true; artifact_zip_sha256={ARTIFACT_ZIP_SHA256}; arch={arch.value}; "
        f"source_stl_sha256={source_stl_sha256}; source_json={source_json}; "
        "model_stage=instances; correspondence_verified=true; "
        "semantic labels are experimental seven-class labels, not clinical FDI."
    )

    instances: list[ToothInstance] = []
    identified: list[IdentifiedTooth] = []
    semantic_by_instance: list[tuple[int, int | None]] = []
    for source_instance_id in range(14):
        vertex_indices = tuple(
            index for index, value in enumerate(instances_array) if value == source_instance_id
        )
        triangle_indices = tuple(
            index
            for index, face in enumerate(faces)
            if all(vertex in vertex_indices for vertex in face)
        )
        if not vertex_indices or not triangle_indices:
            raise ToothInstanceNetFixtureError(
                f"Unable to reconstruct valid {arch.value} instance {source_instance_id}"
            )
        selected_vertices = tuple(
            sorted({vertex for index in triangle_indices for vertex in faces[index]})
        )
        local_lookup = {vertex: local for local, vertex in enumerate(selected_vertices)}
        local_faces = tuple(
            tuple(local_lookup[vertex] for vertex in faces[index]) for index in triangle_indices
        )
        semantic_label = instance_to_label[source_instance_id]
        centroid = tuple(
            sum(vertices[index][axis] for index in vertex_indices) / len(vertex_indices)
            for axis in range(3)
        )
        instance = ToothInstance(
            instance_id=len(instances),
            triangle_indices=triangle_indices,
            vertex_indices=selected_vertices,
            mesh_vertices=tuple(vertices[index] for index in selected_vertices),
            mesh_faces=local_faces,
            centroid=centroid,
            confidence=0.0,
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes=(
                f"semantic_label={semantic_label}; source_instance_id={source_instance_id}; "
                f"{artifact_note}"
            ),
            tooth_ref=f"{arch.value}:instance:{source_instance_id}",
            semantic_label=semantic_label,
            arch=arch.value,
        )
        semantic_by_instance.append((instance.instance_id, None))
        identified.append(
            IdentifiedTooth(
                instance=instance,
                identity=None,
                landmarks=None,
                coordinate_system=ToothCoordinateSystem(
                    origin=centroid,
                    lateral_axis=(1.0, 0.0, 0.0),
                    anterior_axis=(0.0, 1.0, 0.0),
                    vertical_axis=(0.0, 0.0, 1.0),
                    semantics=(
                        "engineering-reference-axis",
                        "engineering-reference-axis",
                        "engineering-reference-axis",
                    ),
                ),
                confidence=IdentificationConfidence(
                    0.0,
                    IdentificationStatus.UNCERTAIN,
                    ("Seven-class artifact semantic label is not a clinical FDI identity.",),
                ),
                provenance=DataProvenance.EXPERIMENTAL,
                fixture=True,
                notes=f"semantic_label={semantic_label}; {artifact_note}",
                tooth_ref=instance.tooth_ref,
                semantic_label=semantic_label,
                planning_mode="semantic_only_experimental",
            )
        )
        instances.append(instance)

    segmentation = ToothSegmentationResult(
        instances=tuple(instances),
        metadata=SegmentationMetadata(
            engine_name="toothinstancenet-validated-fixture",
            model_name="toothinstancenet",
            model_version=str(payload.get("model_version", "validated-artifact")),
            input_triangle_count=len(faces),
            output_instance_count=len(instances),
            confidence_min=min((item.confidence for item in instances), default=0.0),
            confidence_mean=sum(item.confidence for item in instances) / len(instances)
            if instances
            else 0.0,
            confidence_max=max((item.confidence for item in instances), default=0.0),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes=f"{artifact_note}; fixture path is never automatic.",
        ),
        source_mesh_path=str(root / f"{arch.value}.stl"),
    )
    diagnostics = ToothInstanceNetDiagnostics(
        state="identification_incomplete",
        fdi_by_instance=tuple(semantic_by_instance),
        duplicate_fdi_numbers=(),
        missing_fdi_numbers=(),
        empty_instance_ids=(),
        notes=(artifact_note,),
    )
    return ToothInstanceNetInferenceResult(
        segmentation=segmentation,
        identification=ToothIdentificationResult(
            arch=arch,
            teeth=tuple(identified),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes=f"{artifact_note}; fixture is explicit and test-only.",
        ),
        diagnostics=diagnostics,
        status=diagnostics.state,
    )
