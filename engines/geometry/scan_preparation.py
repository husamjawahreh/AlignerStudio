"""Derived scan preparation. The source file is never rewritten.

Every committed mesh is rebuilt from the source plus the operation list, then
rechecked. A watertight or capped surface is not produced here.
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

from domain.case.preparation import (
    empty_preparation,
    future_segmentation_input,
    preparation_readiness,
    structural_preparation_gate,
)
from engines.geometry.intake_inspection import _quality

_DEGENERATE_AREA = 1e-12
_FORBIDDEN_CLEANUP = {
    "fill_holes",
    "watertight",
    "watertight_conversion",
    "close_mesh",
    "reconstruct",
    "cap",
}


class PreparationError(ValueError):
    """The operation was refused before any derived file was written."""


class PreparationCancelled(PreparationError):
    """The job stopped before a prepared artifact was published."""


class PreparationStale(PreparationError):
    """The source or a newer commit changed before this job could publish."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _as_vec3(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise PreparationError(f"{name} must be three numbers.")
    vector = np.asarray(value, dtype=np.float64)
    if not np.isfinite(vector).all():
        raise PreparationError(f"{name} must be finite.")
    return vector


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, process=False, force="mesh")
    if not isinstance(loaded, trimesh.Trimesh):
        raise PreparationError("Preparation requires one triangle mesh.")
    return loaded


def _rotation_matrix(rotation_deg: np.ndarray) -> np.ndarray:
    rx, ry, rz = np.radians(rotation_deg)
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    rot_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    rot_y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    rot_z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rot_z @ rot_y @ rot_x
    return matrix


def _user_matrix(parameters: dict[str, Any]) -> np.ndarray:
    rotation = _as_vec3(parameters.get("rotation_deg", [0, 0, 0]), "rotation_deg")
    translation = _as_vec3(parameters.get("translation", [0, 0, 0]), "translation")
    linear = _rotation_matrix(rotation)
    placed = np.eye(4, dtype=np.float64)
    placed[:3, 3] = translation
    return placed @ linear


def _pca_matrix(vertices: np.ndarray) -> np.ndarray:
    if len(vertices) < 3 or not np.isfinite(vertices).all():
        raise PreparationError("Geometric orientation needs at least three finite vertices.")
    centroid = vertices.mean(axis=0)
    centered = vertices - centroid
    try:
        values, vectors = np.linalg.eigh(centered.T @ centered)
    except np.linalg.LinAlgError as exc:
        raise PreparationError("Geometric axes did not converge.") from exc
    order = np.argsort(values)[::-1]
    axes = vectors[:, order]
    if np.linalg.det(axes) < 0:
        axes = axes.copy()
        axes[:, 2] *= -1
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = axes.T
    matrix[:3, 3] = -axes.T @ centroid
    return matrix


def _matrix_payload(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix.tolist()]


def _orient(
    mesh: trimesh.Trimesh, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    method = str(parameters.get("method") or "user_transform")
    if method == "vertex_pca":
        matrix = _pca_matrix(np.asarray(mesh.vertices, dtype=np.float64))
        truth = "COMPUTED_GEOMETRIC_ORIENTATION"
        algorithm = "vertex_pca_alignment"
        limitation = "PCA is a geometric frame. It is not a clinical occlusal or tooth axis."
    elif method == "user_transform":
        matrix = _user_matrix(parameters)
        truth = "USER_PROVIDED"
        algorithm = "user_rigid_transform"
        limitation = "A user rotation or translation is not a clinical axis."
    else:
        raise PreparationError("Orientation method must be user_transform or vertex_pca.")
    mesh.apply_transform(matrix)
    oriented = mesh
    meta = {
        "algorithm": algorithm,
        "truth_state": truth,
        "clinical_axes": False,
        "parameters": {
            "method": method,
            "rotation_deg": [float(value) for value in parameters.get("rotation_deg", [0, 0, 0])],
            "translation": [float(value) for value in parameters.get("translation", [0, 0, 0])],
            "matrix": _matrix_payload(matrix),
        },
        "coordinates": {
            "source_frame": "SOURCE_COORDINATES",
            "applied_frame": truth,
            "clinical_orientation": False,
            "model_orientation": False,
        },
        "limitations": limitation,
    }
    if method == "user_transform":
        rotation = _as_vec3(parameters.get("rotation_deg", [0, 0, 0]), "rotation_deg")
        translation = _as_vec3(parameters.get("translation", [0, 0, 0]), "translation")
        meta["parameters"]["rotation_deg"] = [float(value) for value in rotation]
        meta["parameters"]["translation"] = [float(value) for value in translation]
    return oriented, meta


def _keep_mask(mesh: trimesh.Trimesh, parameters: dict[str, Any]) -> np.ndarray:
    region = parameters.get("region")
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    if region == "axis_aligned_box":
        minimum = _as_vec3(parameters.get("minimum"), "minimum")
        maximum = _as_vec3(parameters.get("maximum"), "maximum")
        if np.any(maximum < minimum):
            raise PreparationError("Trim maximum is below the minimum.")
        return np.all((centroids >= minimum) & (centroids <= maximum), axis=1)
    if region == "plane":
        normal = _as_vec3(parameters.get("normal"), "normal")
        length = float(np.linalg.norm(normal))
        if length == 0.0:
            raise PreparationError("Trim plane normal must be non-zero.")
        offset = parameters.get("offset", 0.0)
        if isinstance(offset, bool) or not isinstance(offset, (int, float)):
            raise PreparationError("Trim plane offset must be a number.")
        if not np.isfinite(offset):
            raise PreparationError("Trim plane offset must be finite.")
        return centroids @ (normal / length) >= float(offset)
    raise PreparationError("Trim region must be axis_aligned_box or plane.")


def _trimmed(
    mesh: trimesh.Trimesh, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    if len(mesh.faces) == 0:
        raise PreparationError("Trim needs a mesh with faces.")
    keep = _keep_mask(mesh, parameters)
    if not bool(np.any(keep)):
        raise PreparationError("The region keeps no faces. Nothing was written.")
    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()
    trimmed = mesh
    meta = {
        "algorithm": "centroid_region_crop",
        "truth_state": "USER_PROVIDED",
        "clinical_axes": False,
        "parameters": _json_parameters(parameters),
        "limitations": (
            "Faces are kept or dropped by centroid. No cap is added. "
            "The region is the one supplied with the operation, not an automatic cut."
        ),
    }
    return trimmed, meta


def _json_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in parameters.items():
        if isinstance(value, (list, tuple)):
            cleaned[key] = [
                float(item) if isinstance(item, (int, float)) else item for item in value
            ]
        elif isinstance(value, (str, bool, int, float)) or value is None:
            cleaned[key] = value
        else:
            raise PreparationError(f"Parameter {key} is not a supported value.")
    return cleaned


def _component_groups(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    if len(mesh.faces) == 0:
        return []
    labels = trimesh.graph.connected_component_labels(
        mesh.face_adjacency, node_count=len(mesh.faces)
    )
    groups = [np.flatnonzero(labels == label) for label in np.unique(labels)]
    groups.sort(key=lambda indices: (-len(indices), int(indices.min()) if len(indices) else 0))
    return groups


def describe_components(mesh: trimesh.Trimesh) -> list[dict[str, Any]]:
    """List disconnected components. Nothing is deleted."""
    groups = _component_groups(mesh)
    described: list[dict[str, Any]] = []
    for index, faces in enumerate(groups):
        vertices = np.unique(np.asarray(mesh.faces)[faces].reshape(-1))
        coordinates = np.asarray(mesh.vertices)[vertices]
        bounds = coordinates.min(axis=0), coordinates.max(axis=0)
        described.append(
            {
                "id": index,
                "face_count": int(len(faces)),
                "vertex_count": int(len(vertices)),
                "area": float(np.asarray(mesh.area_faces)[faces].sum()),
                "bounds": {
                    "min": [float(value) for value in bounds[0]],
                    "max": [float(value) for value in bounds[1]],
                },
                "clinically_irrelevant": False,
            }
        )
    return described


def _invalid_component_ids(mesh: trimesh.Trimesh, groups: list[np.ndarray]) -> list[int]:
    areas = np.asarray(mesh.area_faces, dtype=np.float64)
    invalid: list[int] = []
    for index, faces in enumerate(groups):
        used = np.asarray(mesh.faces)[faces].reshape(-1)
        coordinates = np.asarray(mesh.vertices, dtype=np.float64)[used]
        degenerate = bool(np.all(~np.isfinite(areas[faces]) | (areas[faces] <= _DEGENERATE_AREA)))
        if degenerate or not np.isfinite(coordinates).all():
            invalid.append(index)
    return invalid


def _drop_faces(mesh: trimesh.Trimesh, keep: np.ndarray) -> trimesh.Trimesh:
    if not bool(np.any(keep)):
        raise PreparationError("The operation keeps no faces. Nothing was written.")
    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()
    return mesh


def _cleanup(
    mesh: trimesh.Trimesh, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    forbidden = _FORBIDDEN_CLEANUP.intersection(parameters)
    if forbidden:
        raise PreparationError(
            "Hole filling and watertight reconstruction are not preparation cleanup."
        )
    flags = {
        "merge_duplicate_vertices": bool(parameters.get("merge_duplicate_vertices", False)),
        "remove_degenerate_faces": bool(parameters.get("remove_degenerate_faces", False)),
        "remove_duplicate_faces": bool(parameters.get("remove_duplicate_faces", False)),
        "remove_invalid_components": bool(parameters.get("remove_invalid_components", False)),
    }
    if not any(flags.values()):
        raise PreparationError("Cleanup needs at least one safe operation.")
    cleaned = mesh
    if flags["merge_duplicate_vertices"]:
        cleaned.merge_vertices()
    if flags["remove_duplicate_faces"] and len(cleaned.faces):
        ordered = np.sort(np.asarray(cleaned.faces), axis=1)
        _, unique_index = np.unique(ordered, axis=0, return_index=True)
        keep = np.zeros(len(cleaned.faces), dtype=bool)
        keep[unique_index] = True
        cleaned = _drop_faces(cleaned, keep)
    if flags["remove_degenerate_faces"] and len(cleaned.faces):
        cleaned.update_faces(cleaned.nondegenerate_faces())
        cleaned.remove_unreferenced_vertices()
    if flags["remove_invalid_components"] and len(cleaned.faces):
        groups = _component_groups(cleaned)
        invalid = set(_invalid_component_ids(cleaned, groups))
        if invalid:
            keep = np.ones(len(cleaned.faces), dtype=bool)
            for index, faces in enumerate(groups):
                if index in invalid:
                    keep[faces] = False
            cleaned = _drop_faces(cleaned, keep)
    meta = {
        "algorithm": "trimesh_safe_cleanup",
        "truth_state": "DERIVED",
        "clinical_axes": False,
        "parameters": {**flags, "watertight_conversion": False, "hole_fill": False},
        "limitations": (
            "Cleanup merges duplicate vertices, drops degenerate or duplicate faces, "
            "and can drop components that are degenerate or non-finite. "
            "It does not fill holes, close a crown, or reconstruct anatomy."
        ),
    }
    return cleaned, meta


def _connectivity(artifact: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """STL has no shared vertex indices, so component ids use a welded copy."""
    updated = dict(parameters)
    if "connectivity" not in updated:
        kind = str(artifact.get("format") or "")
        updated["connectivity"] = "welded_vertices" if kind.startswith("stl") else "stored_indices"
    return updated


def _component_basis(mesh: trimesh.Trimesh, parameters: dict[str, Any]) -> trimesh.Trimesh:
    if parameters.get("connectivity") == "welded_vertices":
        mesh.merge_vertices()
    return mesh


def _remove_components(
    mesh: trimesh.Trimesh, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    action = str(parameters.get("action") or "")
    if action == "list":
        raise PreparationError("Listing components does not change the mesh. Use preview.")
    if action != "remove":
        raise PreparationError("Component action must be remove.")
    raw_ids = parameters.get("component_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise PreparationError("component_ids must list at least one component.")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in raw_ids):
        raise PreparationError("component_ids must be integers.")
    basis = _component_basis(mesh, parameters)
    groups = _component_groups(basis)
    unknown = [item for item in raw_ids if item < 0 or item >= len(groups)]
    if unknown:
        raise PreparationError(f"Unknown component ids: {unknown}.")
    keep = np.ones(len(basis.faces), dtype=bool)
    for index in raw_ids:
        keep[groups[index]] = False
    updated = _drop_faces(basis, keep)
    marked = bool(parameters.get("user_marked_irrelevant", False))
    meta = {
        "algorithm": "remove_selected_components",
        "truth_state": "USER_PROVIDED",
        "clinical_axes": False,
        "parameters": {
            "action": "remove",
            "component_ids": [int(item) for item in raw_ids],
            "user_marked_irrelevant": marked,
            "clinical_judgement": False,
            "connectivity": parameters.get("connectivity") or "stored_indices",
        },
        "limitations": (
            "Removed components are the ids the user selected. "
            "STL ids are computed after welding a copy because STL does not share vertex indices. "
            "They are not labeled clinically irrelevant unless the user set that flag, "
            "and the flag is not a clinical finding."
        ),
    }
    return updated, meta


def _apply_operation(
    mesh: trimesh.Trimesh, operation: str, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    if operation == "orient":
        return _orient(mesh, parameters)
    if operation == "trim":
        return _trimmed(mesh, parameters)
    if operation == "cleanup":
        return _cleanup(mesh, parameters)
    if operation == "components":
        return _remove_components(mesh, parameters)
    raise PreparationError("Operation must be orient, trim, cleanup, or components.")


def _export_stl(mesh: trimesh.Trimesh) -> bytes:
    payload = mesh.export(file_type="stl")
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return bytes(payload)


def replay_mesh(source: Path, operations: list[dict[str, Any]]) -> trimesh.Trimesh:
    """Rebuild the prepared mesh from the source and the geometry operations."""
    mesh = _load_mesh(source)
    for item in operations:
        mesh, _meta = _apply_operation(mesh, str(item["operation"]), dict(item["parameters"]))
    return mesh


def _quality_summary(mesh: trimesh.Trimesh, *, kind: str) -> dict[str, Any]:
    quality = _quality(mesh, [], [], kind=kind)
    bounds = None if len(mesh.vertices) == 0 else mesh.bounds
    return {
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "boundary_edges": quality["checks"].get("boundary_edges", 0),
        "non_manifold_edges": quality["checks"].get("non_manifold_edges", 0),
        "degenerate_faces": quality["checks"].get("degenerate_faces", 0),
        "duplicate_face_groups": quality["checks"].get("duplicate_face_groups", 0),
        "duplicate_vertex_groups": quality["checks"].get("duplicate_vertex_groups", 0),
        "component_count": quality["checks"].get("component_count", 0),
        "watertight": quality["checks"].get("watertight", False),
        "bounding_box": None
        if bounds is None
        else {
            "min": [float(value) for value in bounds[0]],
            "max": [float(value) for value in bounds[1]],
        },
        "warnings": quality["warnings"],
        "blockers": quality["blockers"],
        "self_intersection": "not_run",
    }


def _source_kind(artifact: dict[str, Any]) -> str:
    kind = str(artifact.get("format") or "")
    return kind if kind.startswith("stl") else kind


def _session(artifact: dict[str, Any]) -> dict[str, Any]:
    current = artifact.get("preparation")
    if not isinstance(current, dict):
        current = empty_preparation(artifact)
        artifact["preparation"] = current
    return current


def _geometry_operations(session: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"operation": item["operation"], "parameters": item["replay_parameters"]}
        for item in session.get("operations", [])
    ]


def _require_source(artifact: dict[str, Any]) -> tuple[Path, str]:
    if artifact.get("readiness") == "BLOCKED_INVALID_INPUT":
        raise PreparationError("Invalid source is not repaired in place or replaced.")
    source = Path(str(artifact.get("source_path") or ""))
    if not source.is_file():
        raise PreparationError("Source file is missing.")
    recorded = artifact.get("sha256")
    current = _sha256_file(source)
    if recorded and current != recorded:
        raise PreparationError("Source bytes no longer match the stored hash.")
    return source, current


def _summary_from_intake(artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse the immutable source inspection. Avoids a second load and STL weld."""
    quality = artifact.get("quality")
    if not isinstance(quality, dict) or not isinstance(quality.get("checks"), dict):
        return None
    if artifact.get("vertex_count") is None or artifact.get("face_count") is None:
        return None
    checks = quality["checks"]
    bounds = artifact.get("bounding_box")
    return {
        "vertex_count": int(artifact.get("vertex_count") or 0),
        "face_count": int(artifact.get("face_count") or 0),
        "boundary_edges": checks.get("boundary_edges", 0),
        "non_manifold_edges": checks.get("non_manifold_edges", 0),
        "degenerate_faces": checks.get("degenerate_faces", 0),
        "duplicate_face_groups": checks.get("duplicate_face_groups", 0),
        "duplicate_vertex_groups": checks.get("duplicate_vertex_groups", 0),
        "component_count": checks.get("component_count", 0),
        "watertight": checks.get("watertight", False),
        "bounding_box": bounds,
        "warnings": list(quality.get("warnings") or []),
        "blockers": list(quality.get("blockers") or []),
        "self_intersection": "not_run",
        "reused_intake_inspection": True,
    }


def _source_summary(
    artifact: dict[str, Any],
    source: Path,
    mesh: trimesh.Trimesh,
    *,
    kind: str,
    mesh_is_source: bool,
) -> dict[str, Any]:
    stored = _summary_from_intake(artifact)
    if stored is not None:
        return stored
    if mesh_is_source:
        return _quality_summary(mesh, kind=kind or "stl")
    return _quality_summary(_load_mesh(source), kind=kind or "stl")


def _check_cancel(cancel_check: Any) -> None:
    if cancel_check is not None and cancel_check():
        raise PreparationCancelled("Preparation was cancelled before a mesh was published.")


def preview_operation(
    artifact: dict[str, Any],
    operation: str,
    parameters: dict[str, Any],
    *,
    cancel_check: Any = None,
    progress: Any = None,
) -> dict[str, Any]:
    """Describe one operation. No file is written and the artifact is not changed."""
    source, source_sha = _require_source(artifact)
    started = perf_counter()
    _check_cancel(cancel_check)
    if progress is not None:
        progress("load", 0.2)
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else None
    prior = _geometry_operations(session) if session else []
    mesh = replay_mesh(source, prior)
    if _sha256_file(source) != source_sha:
        raise PreparationError("Source bytes changed during preview.")
    kind = _source_kind(artifact)
    mesh_is_source = not prior
    source_summary = _summary_from_intake(artifact)
    if source_summary is None and mesh_is_source:
        source_summary = _quality_summary(mesh, kind=kind or "stl")
    if operation == "components" and parameters.get("action") == "list":
        parameters = _connectivity(artifact, parameters)
        components = describe_components(_component_basis(mesh, parameters))
        return {
            "preview": True,
            "persisted": False,
            "operation": "components",
            "components": components,
            "source_sha256": source_sha,
            "face_count": int(len(mesh.faces)),
            "vertex_count": int(len(mesh.vertices)),
            "timings_ms": {"preview_ms": (perf_counter() - started) * 1000},
            "fdi_assigned": False,
            "occlusion_established": False,
            "clinical_axes": False,
        }
    _check_cancel(cancel_check)
    if progress is not None:
        progress("operate", 0.5)
    parameters = _connectivity(artifact, parameters) if operation == "components" else parameters
    prepared, meta = _apply_operation(mesh, operation, parameters)
    if len(prepared.faces) == 0 or len(prepared.vertices) == 0:
        raise PreparationError("The operation keeps no faces. Nothing was written.")
    if _sha256_file(source) != source_sha:
        raise PreparationError("Source bytes changed during preview.")
    _check_cancel(cancel_check)
    if progress is not None:
        progress("recheck", 0.8)
    if source_summary is None:
        source_summary = _quality_summary(_load_mesh(source), kind=kind or "stl")
    comparison = {
        "source": source_summary,
        "prepared": _quality_summary(prepared, kind="stl_binary"),
    }
    return {
        "preview": True,
        "persisted": False,
        "operation": operation,
        "truth_state": meta["truth_state"],
        "clinical_axes": False,
        "parameters": meta["parameters"],
        "limitations": meta["limitations"],
        "quality_comparison": comparison,
        "source_sha256": source_sha,
        "output_sha256": _sha256_bytes(_export_stl(prepared)),
        "components": describe_components(prepared) if operation == "components" else [],
        "timings_ms": {"preview_ms": (perf_counter() - started) * 1000},
        "fdi_assigned": False,
        "occlusion_established": False,
        "clinically_segmented": False,
    }


def _stamp(
    artifact: dict[str, Any],
    session: dict[str, Any],
    *,
    event: str,
    operation: str | None,
    meta: dict[str, Any] | None,
    output_sha: str | None,
    output_path: str | None,
    comparison: dict[str, Any] | None,
    elapsed_ms: float,
    job_id: str | None = None,
    reused: bool = False,
    cache_key: str | None = None,
) -> None:
    source_sha = artifact.get("sha256")
    accepted = bool(session.get("accepted"))
    blockers = [] if comparison is None else list(comparison["prepared"]["blockers"])
    warnings = [] if comparison is None else list(comparison["prepared"]["warnings"])
    if comparison is None and session.get("quality_comparison"):
        blockers = list(session["quality_comparison"]["prepared"]["blockers"])
        warnings = list(session["quality_comparison"]["prepared"]["warnings"])
    readiness = preparation_readiness(
        operation_count=len(session.get("operations", [])),
        blockers=blockers,
        warnings=warnings,
        accepted=accepted,
    )
    active = session.get("active") or {}
    prepared_sha = output_sha if output_sha is not None else active.get("output_sha256")
    uses_prepared = accepted and bool(session.get("operations")) and readiness != "BLOCKED"
    session["readiness"] = readiness
    session["source_sha256"] = source_sha
    session["source_artifact_id"] = artifact.get("artifact_id")
    session["clinically_segmented"] = False
    session["fdi_assigned"] = False
    session["occlusion_established"] = False
    session["bite_registration_established"] = False
    session["clinical_axes"] = False
    session["future_segmentation_input"] = future_segmentation_input(
        source_sha256=source_sha,
        prepared_sha256=prepared_sha if session.get("operations") else None,
        uses_prepared_mesh=uses_prepared,
        technical_gate_passed=bool(session.get("technical_gate_passed")),
    )
    if comparison is not None:
        session["quality_comparison"] = comparison
    version = int(session.get("version") or 0) + 1
    session["version"] = version
    record = {
        "version": version,
        "event": event,
        "operation": operation,
        "source_artifact_id": artifact.get("artifact_id"),
        "source_sha256": source_sha,
        "output_sha256": output_sha,
        "output_path": output_path,
        "algorithm": None if meta is None else meta.get("algorithm"),
        "library": "trimesh",
        "library_version": trimesh.__version__,
        "parameters": None if meta is None else meta.get("parameters"),
        "truth_state": "DERIVED" if meta is None else meta.get("truth_state"),
        "clinical_axes": False,
        "timestamp": datetime.now(UTC).isoformat(),
        "readiness": readiness,
        "replaces_source": False,
        "observed_anatomy": False,
        "role": "PREPARED_ARTIFACT" if output_sha else "PREPARATION_EVENT",
        "geometry_class": "DERIVED_GEOMETRY" if output_sha else None,
        "limitations": None if meta is None else meta.get("limitations"),
        "timings_ms": {"operation_ms": elapsed_ms},
        "job_id": job_id,
        "reused": reused,
        "cache_hit": reused,
        "cache_key": cache_key,
        "published": bool(output_sha),
    }
    session.setdefault("versions", []).append(record)
    output_artifact_id = str(uuid.uuid4()) if output_sha and output_path else None
    if output_sha and output_path:
        session["active"] = {
            "role": "PREPARED_ARTIFACT",
            "geometry_class": "DERIVED_GEOMETRY",
            "artifact_id": output_artifact_id,
            "source_artifact_id": artifact.get("artifact_id"),
            "source_sha256": source_sha,
            "output_sha256": output_sha,
            "output_path": output_path,
            "truth_state": "DERIVED",
            "observed_anatomy": False,
            "replaces_source": False,
            "clinical_axes": False,
            "fdi_assigned": False,
            "occlusion_established": False,
            "job_id": job_id,
            "reused": reused,
        }
    elif not session.get("operations"):
        session["active"] = None
    _append_lineage(
        artifact,
        session,
        event=event,
        operation=operation,
        meta=meta,
        output_sha=output_sha,
        output_path=output_path,
        output_artifact_id=output_artifact_id,
        job_id=job_id,
        reused=reused,
        cache_key=cache_key,
    )
    if event in {"apply", "undo", "reset"}:
        session["commit_generation"] = int(session.get("commit_generation") or 0) + 1


def _operation_snapshot(session: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "operation": item.get("operation"),
            "algorithm": item.get("algorithm"),
            "algorithm_version": item.get("library_version"),
            "parameters": item.get("replay_parameters"),
            "truth_state": item.get("truth_state"),
            "clinical_axes": False,
        }
        for item in session.get("operations") or []
    ]


def _defer_previous_lineage(session: dict[str, Any]) -> None:
    for item in session.get("lineage") or []:
        if item.get("lifecycle") == "active":
            item["lifecycle"] = "superseded"
            item["cleanup"] = "cleanup_deferred"
            item["cleanup_reason"] = "referenced_by_preparation_history"


def _append_lineage(
    artifact: dict[str, Any],
    session: dict[str, Any],
    *,
    event: str,
    operation: str | None,
    meta: dict[str, Any] | None,
    output_sha: str | None,
    output_path: str | None,
    output_artifact_id: str | None,
    job_id: str | None,
    reused: bool,
    cache_key: str | None,
) -> None:
    if event in {"accept", "undo_accept"}:
        return
    _defer_previous_lineage(session)
    session.setdefault("lineage", []).append(
        {
            "lineage_id": str(uuid.uuid4()),
            "role": "DERIVED_PREPARED_ARTIFACT" if output_sha else "PREPARATION_EVENT",
            "event": event,
            "operation": operation,
            "parent_sha256": artifact.get("sha256"),
            "source_artifact_id": artifact.get("artifact_id"),
            "source_sha256": artifact.get("sha256"),
            "output_artifact_id": output_artifact_id,
            "output_sha256": output_sha,
            "output_path": output_path,
            "operations": _operation_snapshot(session),
            "algorithm": None if meta is None else meta.get("algorithm"),
            "algorithm_version": trimesh.__version__,
            "parameters": None if meta is None else meta.get("parameters"),
            "truth_state": None if meta is None else meta.get("truth_state"),
            "clinical_axes": False,
            "job_id": job_id,
            "reused": reused,
            "cache_key": cache_key,
            "lifecycle": "active" if output_sha else "source_restored",
            "cleanup": None,
            "replaces_source": False,
            "observed_anatomy": False,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


def _publish_bytes(
    session: dict[str, Any],
    payload: bytes,
    source: Path,
    source_sha: str,
    *,
    expected_generation: int | None,
    cancel_check: Any,
) -> tuple[str, str]:
    """Write a complete payload, then publish it. A partial file is never the active mesh."""
    version = int(session.get("version") or 0) + 1
    destination = source.with_name(f"{source.stem}-prepared-v{version}.stl")
    partial = Path(str(destination) + ".partial")
    partial.write_bytes(payload)
    try:
        if _sha256_file(source) != source_sha:
            raise PreparationError("Source bytes changed while writing a prepared mesh.")
        output_sha = _sha256_bytes(payload)
        if _sha256_file(partial) != output_sha:
            raise PreparationError("Prepared bytes do not match the computed hash.")
        generation = int(session.get("commit_generation") or 0)
        if expected_generation is not None and generation != expected_generation:
            raise PreparationStale(
                "A newer preparation was committed. This result was not published."
            )
        _check_cancel(cancel_check)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    if _sha256_file(destination) != output_sha:
        destination.unlink(missing_ok=True)
        raise PreparationError("Prepared bytes do not match the computed hash.")
    return output_sha, str(destination)


def _write_prepared(
    artifact: dict[str, Any],
    session: dict[str, Any],
    mesh: trimesh.Trimesh,
    source: Path,
    source_sha: str,
    *,
    expected_generation: int | None = None,
    cancel_check: Any = None,
) -> tuple[str, str]:
    del artifact
    return _publish_bytes(
        session,
        _export_stl(mesh),
        source,
        source_sha,
        expected_generation=expected_generation,
        cancel_check=cancel_check,
    )


def _replay_parameters(operation: str, meta: dict[str, Any]) -> dict[str, Any]:
    replay_parameters = dict(meta["parameters"])
    if operation == "orient" and replay_parameters.get("method") == "user_transform":
        return {
            "method": "user_transform",
            "rotation_deg": replay_parameters["rotation_deg"],
            "translation": replay_parameters["translation"],
        }
    if operation == "orient":
        return {"method": "vertex_pca"}
    if operation == "trim":
        return {
            key: replay_parameters[key]
            for key in ("region", "minimum", "maximum", "normal", "offset")
            if key in replay_parameters
        }
    if operation == "cleanup":
        return {
            key: replay_parameters[key]
            for key in (
                "merge_duplicate_vertices",
                "remove_degenerate_faces",
                "remove_duplicate_faces",
                "remove_invalid_components",
            )
        }
    if operation == "components":
        return {
            "action": "remove",
            "component_ids": replay_parameters["component_ids"],
            "user_marked_irrelevant": replay_parameters["user_marked_irrelevant"],
            "connectivity": replay_parameters.get("connectivity") or "stored_indices",
        }
    return replay_parameters


def apply_operation(
    artifact: dict[str, Any],
    operation: str,
    parameters: dict[str, Any],
    *,
    job_id: str | None = None,
    expected_generation: int | None = None,
    cancel_check: Any = None,
    progress: Any = None,
    reused: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one operation, write a new derived file, and recheck quality."""
    source, source_sha = _require_source(artifact)
    started = perf_counter()
    _check_cancel(cancel_check)
    session = _session(artifact)
    generation = int(session.get("commit_generation") or 0)
    if expected_generation is not None and generation != expected_generation:
        raise PreparationStale("A newer preparation was committed. This result was not published.")
    if reused is not None:
        if reused.get("source_sha256") != source_sha:
            raise PreparationError("Cache entry is for a different source.")
        if progress is not None:
            progress("commit", 0.92)
        output_sha, output_path = _publish_bytes(
            session,
            bytes(reused["output_bytes"]),
            source,
            source_sha,
            expected_generation=expected_generation,
            cancel_check=cancel_check,
        )
        if output_sha != reused.get("output_sha256"):
            Path(output_path).unlink(missing_ok=True)
            raise PreparationError("Cached bytes do not match the stored output hash.")
        meta = dict(reused["meta"])
        comparison = reused["quality_comparison"]
        prepared = None
    else:
        if progress is not None:
            progress("load", 0.2)
        prior = _geometry_operations(session)
        mesh = replay_mesh(source, prior)
        kind = _source_kind(artifact)
        source_summary = _summary_from_intake(artifact)
        if source_summary is None and not prior:
            source_summary = _quality_summary(mesh, kind=kind or "stl")
        _check_cancel(cancel_check)
        if progress is not None:
            progress("operate", 0.5)
        if operation == "components":
            parameters = _connectivity(artifact, parameters)
        prepared, meta = _apply_operation(mesh, operation, parameters)
        if len(prepared.faces) == 0 or len(prepared.vertices) == 0:
            raise PreparationError("The operation keeps no faces. Nothing was written.")
        _check_cancel(cancel_check)
        if progress is not None:
            progress("recheck", 0.8)
        if source_summary is None:
            source_summary = _quality_summary(_load_mesh(source), kind=kind or "stl")
        comparison = {
            "source": source_summary,
            "prepared": _quality_summary(prepared, kind="stl_binary"),
        }
        if progress is not None:
            progress("commit", 0.92)
        output_sha, output_path = _write_prepared(
            artifact,
            session,
            prepared,
            source,
            source_sha,
            expected_generation=expected_generation,
            cancel_check=cancel_check,
        )
    replay_parameters = _replay_parameters(operation, meta)
    session["accepted"] = False
    session["technical_gate_passed"] = False
    session.setdefault("operations", []).append(
        {
            "operation": operation,
            "replay_parameters": replay_parameters,
            "truth_state": meta["truth_state"],
            "clinical_axes": False,
            "algorithm": meta["algorithm"],
            "library": "trimesh",
            "library_version": trimesh.__version__,
            "reused": reused is not None,
        }
    )
    if operation == "components" and prepared is not None:
        session["components"] = describe_components(prepared)
    _stamp(
        artifact,
        session,
        event="apply",
        operation=operation,
        meta=meta,
        output_sha=output_sha,
        output_path=output_path,
        comparison=comparison,
        elapsed_ms=(perf_counter() - started) * 1000,
        job_id=job_id,
        reused=reused is not None,
        cache_key=None if reused is None else reused.get("cache_key"),
    )
    retire_unreferenced_outputs(artifact)
    artifact["source_bytes_modified"] = False
    artifact["fdi_assigned"] = False
    artifact["occlusion_established"] = False
    return session


def undo_preparation(artifact: dict[str, Any]) -> dict[str, Any]:
    source, source_sha = _require_source(artifact)
    session = _session(artifact)
    started = perf_counter()
    if session.get("accepted"):
        session["accepted"] = False
        session["technical_gate_passed"] = False
        _stamp(
            artifact,
            session,
            event="undo_accept",
            operation=None,
            meta={
                "algorithm": "undo_accept",
                "truth_state": "USER_PROVIDED",
                "parameters": {},
                "limitations": "Acceptance was withdrawn. The derived mesh was not deleted.",
            },
            output_sha=(session.get("active") or {}).get("output_sha256"),
            output_path=(session.get("active") or {}).get("output_path"),
            comparison=session.get("quality_comparison"),
            elapsed_ms=(perf_counter() - started) * 1000,
        )
        return session
    operations = list(session.get("operations") or [])
    if not operations:
        raise PreparationError("There is no preparation step to undo.")
    operations.pop()
    session["operations"] = operations
    session["accepted"] = False
    session["technical_gate_passed"] = False
    if not operations:
        if _sha256_file(source) != source_sha:
            raise PreparationError("Source bytes changed during undo.")
        session["components"] = []
        session["quality_comparison"] = None
        session["active"] = None
        _stamp(
            artifact,
            session,
            event="undo",
            operation=None,
            meta={
                "algorithm": "undo",
                "truth_state": "USER_PROVIDED",
                "parameters": {},
                "limitations": "Undo returned to the source. The source file was not rewritten.",
            },
            output_sha=None,
            output_path=None,
            comparison=None,
            elapsed_ms=(perf_counter() - started) * 1000,
        )
        session["quality_comparison"] = None
        session["readiness"] = "NOT_PREPARED"
        retire_unreferenced_outputs(artifact)
        return session
    prepared = replay_mesh(source, _geometry_operations(session))
    kind = _source_kind(artifact)
    comparison = {
        "source": _quality_summary(_load_mesh(source), kind=kind or "stl"),
        "prepared": _quality_summary(prepared, kind="stl_binary"),
    }
    output_sha, output_path = _write_prepared(artifact, session, prepared, source, source_sha)
    _stamp(
        artifact,
        session,
        event="undo",
        operation=operations[-1]["operation"],
        meta={
            "algorithm": "replay_remaining_operations",
            "truth_state": "DERIVED",
            "parameters": {"remaining": len(operations)},
            "limitations": "Undo rebuilt the mesh from the source and the remaining operations.",
        },
        output_sha=output_sha,
        output_path=output_path,
        comparison=comparison,
        elapsed_ms=(perf_counter() - started) * 1000,
    )
    retire_unreferenced_outputs(artifact)
    return session


def reset_preparation(artifact: dict[str, Any]) -> dict[str, Any]:
    source, source_sha = _require_source(artifact)
    session = _session(artifact)
    started = perf_counter()
    session["operations"] = []
    session["accepted"] = False
    session["technical_gate_passed"] = False
    session["components"] = []
    session["active"] = None
    session["quality_comparison"] = None
    if _sha256_file(source) != source_sha:
        raise PreparationError("Source bytes changed during reset.")
    _stamp(
        artifact,
        session,
        event="reset",
        operation=None,
        meta={
            "algorithm": "reset",
            "truth_state": "USER_PROVIDED",
            "parameters": {},
            "limitations": "Reset stops using prepared meshes. It does not modify the source.",
        },
        output_sha=None,
        output_path=None,
        comparison=None,
        elapsed_ms=(perf_counter() - started) * 1000,
    )
    session["readiness"] = "NOT_PREPARED"
    retire_unreferenced_outputs(artifact)
    return session


def accept_preparation(artifact: dict[str, Any]) -> dict[str, Any]:
    """Mark the current mesh as technically suitable. This is not a clinical accept."""
    _source, source_sha = _require_source(artifact)
    session = _session(artifact)
    started = perf_counter()
    kind = _source_kind(artifact)
    source_path = Path(str(artifact["source_path"]))
    if session.get("operations"):
        comparison = session.get("quality_comparison")
        if not comparison:
            prepared = replay_mesh(source_path, _geometry_operations(session))
            comparison = {
                "source": _source_summary(
                    artifact,
                    source_path,
                    prepared,
                    kind=kind,
                    mesh_is_source=False,
                ),
                "prepared": _quality_summary(prepared, kind="stl_binary"),
            }
        blockers = comparison["prepared"]["blockers"]
    else:
        summary = _summary_from_intake(artifact) or _quality_summary(
            _load_mesh(source_path), kind=kind or "stl"
        )
        comparison = {"source": summary, "prepared": summary}
        blockers = summary["blockers"]
    if blockers:
        raise PreparationError("A blocked mesh cannot be marked ready for segmentation.")
    if _sha256_file(source_path) != source_sha:
        raise PreparationError("Source bytes changed during accept.")
    session["quality_comparison"] = comparison
    gate = evaluate_prepared_input(artifact)
    if not gate["passed"]:
        raise PreparationError(
            "Prepared input is not technically acceptable: " + ", ".join(gate["reasons"])
        )
    session["accepted"] = True
    session["technical_gate_passed"] = True
    session["technical_gate"] = gate
    _stamp(
        artifact,
        session,
        event="accept",
        operation=None,
        meta={
            "algorithm": "accept_for_segmentation",
            "truth_state": "USER_PROVIDED",
            "parameters": {"accepted": True},
            "limitations": (
                "Ready means the mesh can be offered to a later processing step. "
                "It does not mean the scan is clinically oriented, segmented, or numbered, "
                "and it does not establish occlusion."
            ),
        },
        output_sha=(session.get("active") or {}).get("output_sha256"),
        output_path=(session.get("active") or {}).get("output_path"),
        comparison=comparison,
        elapsed_ms=(perf_counter() - started) * 1000,
    )
    return session


def measure_preparation(path: str | Path, work_dir: str | Path) -> dict[str, Any]:
    """Time on-demand preparation on a copy. The original file is only read."""
    original = Path(path)
    original_sha = _sha256_file(original)
    original_size = original.stat().st_size
    folder = Path(work_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source-copy.stl"
    source.write_bytes(original.read_bytes())
    artifact = {
        "artifact_id": "measure",
        "sha256": _sha256_file(source),
        "source_path": str(source),
        "format": "stl_binary",
        "readiness": "READY",
    }
    mesh = _load_mesh(source)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    span = bounds[1] - bounds[0]
    minimum = bounds[0] + span * 0.02
    maximum = bounds[1] - span * 0.02
    started = perf_counter()
    orient = preview_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]},
    )
    orient_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    trim = preview_operation(
        artifact,
        "trim",
        {"region": "axis_aligned_box", "minimum": minimum.tolist(), "maximum": maximum.tolist()},
    )
    trim_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    cleanup = preview_operation(
        artifact,
        "cleanup",
        {
            "merge_duplicate_vertices": True,
            "remove_degenerate_faces": True,
            "remove_duplicate_faces": True,
            "remove_invalid_components": False,
        },
    )
    cleanup_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]},
    )
    persist_ms = (perf_counter() - started) * 1000
    if _sha256_file(source) != artifact["sha256"]:
        raise PreparationError("Measurement changed the source copy.")
    if _sha256_file(original) != original_sha:
        raise PreparationError("Measurement changed the original file.")
    return {
        "file_size": original_size,
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "source_sha256": artifact["sha256"],
        "source_unchanged": True,
        "orientation_ms": orient["timings_ms"]["preview_ms"],
        "orientation_wall_ms": orient_ms,
        "trim_ms": trim["timings_ms"]["preview_ms"],
        "trim_wall_ms": trim_ms,
        "cleanup_ms": cleanup["timings_ms"]["preview_ms"],
        "cleanup_wall_ms": cleanup_ms,
        "quality_recheck_included": True,
        "persist_orient_ms": persist_ms,
        "self_intersection": "not_run",
        "prepared_readiness": artifact["preparation"]["readiness"],
        "clinical_axes": False,
        "fdi_assigned": False,
    }


def _referenced_output_paths(session: dict[str, Any]) -> set[str]:
    referenced: set[str] = set()

    def add(path: Any) -> None:
        if path:
            referenced.add(str(path))

    add((session.get("active") or {}).get("output_path"))
    for collection in ("lineage", "versions", "jobs", "provenance_events"):
        for item in session.get(collection) or []:
            if isinstance(item, dict):
                add(item.get("output_path"))
    return referenced


def retire_unreferenced_outputs(artifact: dict[str, Any]) -> dict[str, Any]:
    """Delete unpublished partials only. Referenced history is marked, not removed.

    Filesystem timestamps are not consulted.
    """
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    if not isinstance(session, dict):
        return {"removed": [], "cleanup_deferred": [], "used_filesystem_timestamps": False}
    referenced = _referenced_output_paths(session)
    active_path = (session.get("active") or {}).get("output_path")
    source = Path(str(artifact.get("source_path") or ""))
    removed: list[dict[str, str]] = []
    deferred: list[dict[str, str]] = []
    if source.is_file():
        for partial in source.parent.glob(f"{source.stem}-prepared-v*.stl.partial"):
            partial.unlink(missing_ok=True)
            removed.append({"output_path": str(partial), "reason": "unpublished_partial"})
        for prepared in source.parent.glob(f"{source.stem}-prepared-v*.stl"):
            path = str(prepared)
            if path in referenced:
                if path != active_path:
                    deferred.append(
                        {
                            "output_path": path,
                            "reason": "referenced_by_preparation_history",
                        }
                    )
            else:
                prepared.unlink(missing_ok=True)
                removed.append({"output_path": path, "reason": "unreferenced"})
    deferred_paths = {item["output_path"] for item in deferred}
    for item in session.get("lineage") or []:
        path = item.get("output_path")
        if path in deferred_paths and item.get("lifecycle") != "active":
            item["cleanup"] = "cleanup_deferred"
            item["cleanup_reason"] = "referenced_by_preparation_history"
    report = {
        "removed": removed,
        "cleanup_deferred": deferred,
        "used_filesystem_timestamps": False,
    }
    session["artifact_cleanup"] = report
    return report


def evaluate_prepared_input(artifact: dict[str, Any]) -> dict[str, Any]:
    """Technical acceptance gate. READY_FOR_SEGMENTATION is not clinical readiness."""
    source = Path(str(artifact.get("source_path") or ""))
    reasons: list[str] = []
    if not source.is_file():
        reasons.append("source_missing")
    elif _sha256_file(source) != artifact.get("sha256"):
        reasons.append("source_hash_mismatch")
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    if not isinstance(session, dict):
        session = {}
    reasons.extend(structural_preparation_gate(session, artifact.get("sha256")))
    operations = list(session.get("operations") or [])
    active = session.get("active") or {}
    mesh_path = source
    if operations:
        output = active.get("output_path")
        mesh_path = Path(str(output or ""))
        if not mesh_path.is_file():
            reasons.append("derived_missing")
        elif _sha256_file(mesh_path) != active.get("output_sha256"):
            reasons.append("derived_hash_mismatch")
    if mesh_path.is_file():
        try:
            mesh = _load_mesh(mesh_path)
        except PreparationError:
            reasons.append("geometry_unreadable")
        else:
            vertices = np.asarray(mesh.vertices, dtype=np.float64)
            faces = np.asarray(mesh.faces)
            if vertices.size and not np.isfinite(vertices).all():
                reasons.append("geometry_not_finite")
            if len(faces) and (int(faces.min()) < 0 or int(faces.max()) >= len(vertices)):
                reasons.append("face_vertex_inconsistent")
            if operations:
                prepared = (session.get("quality_comparison") or {}).get("prepared") or {}
                if prepared.get("face_count") != int(len(faces)):
                    reasons.append("face_count_inconsistent")
            elif len(vertices) == 0 or len(faces) == 0:
                reasons.append("face_count_inconsistent")
    unique = list(dict.fromkeys(reasons))
    return {
        "passed": not unique,
        "reasons": unique,
        "readiness": session.get("readiness"),
        "technical_only": True,
        "clinically_ready": False,
        "clinically_segmented": False,
        "fdi_assigned": False,
        "occlusion_established": False,
        "clinical_axes": False,
    }
