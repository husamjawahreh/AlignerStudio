#!/usr/bin/env python3
"""Run the author-published MeshSegNet checkpoint for internal research only.

This script is deliberately outside production packages. It requires an external
research checkout and checkpoint configured through environment variables; it
never participates in the AlignerStudio API or segmentation engine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import distance_matrix


def _require_environment() -> tuple[Path, Path]:
    checkout = os.environ.get("MESHGSEGNET_RESEARCH_CHECKOUT")
    checkpoint = os.environ.get("MESHGSEGNET_RESEARCH_CHECKPOINT")
    if not checkout or not checkpoint:
        raise RuntimeError(
            "Set MESHGSEGNET_RESEARCH_CHECKOUT and MESHGSEGNET_RESEARCH_CHECKPOINT. "
            "Use only the author-published internal-research artifact."
        )
    checkout_path, checkpoint_path = Path(checkout), Path(checkpoint)
    if not (checkout_path / "meshsegnet.py").is_file() or not checkpoint_path.is_file():
        raise RuntimeError("Research checkout or checkpoint is unavailable.")
    return checkout_path, checkpoint_path


def _prepare(mesh_path: Path) -> tuple[Any, Any, np.ndarray, np.ndarray, np.ndarray]:
    import vedo

    mesh = vedo.load(mesh_path)
    if mesh.ncells == 0:
        raise ValueError("Input mesh has no cells")
    original = mesh.clone()
    if mesh.ncells > 10_000:
        mesh = mesh.clone().decimate(fraction=10_000 / mesh.ncells)
    points_value = mesh.points
    points = points_value() if callable(points_value) else np.asarray(points_value)
    center = mesh.center_of_mass()
    points[:, :3] -= center[:3]
    faces = _mesh_faces(mesh)
    cells = points[faces].reshape(mesh.ncells, 9).astype(np.float32)
    mesh.compute_normals()
    normals = np.asarray(mesh.celldata["Normals"], dtype=np.float32)
    centers = mesh.cell_centers()
    centers_value = centers.points if hasattr(centers, "points") else centers
    barycenters = np.asarray(centers_value, dtype=np.float32)
    barycenters -= center[:3]
    maxima, minima = points.max(axis=0), points.min(axis=0)
    means, stds = points.mean(axis=0), points.std(axis=0)
    normal_means, normal_stds = normals.mean(axis=0), normals.std(axis=0)
    if np.any(stds == 0) or np.any(normal_stds == 0) or np.any(maxima == minima):
        raise ValueError("Input mesh cannot be normalized with the published preprocessing")
    for axis in range(3):
        cells[:, axis] = (cells[:, axis] - means[axis]) / stds[axis]
        cells[:, axis + 3] = (cells[:, axis + 3] - means[axis]) / stds[axis]
        cells[:, axis + 6] = (cells[:, axis + 6] - means[axis]) / stds[axis]
        barycenters[:, axis] = (barycenters[:, axis] - minima[axis]) / (maxima[axis] - minima[axis])
        normals[:, axis] = (normals[:, axis] - normal_means[axis]) / normal_stds[axis]
    features = np.column_stack((cells, barycenters, normals)).astype(np.float32)
    distances = distance_matrix(features[:, 9:12], features[:, 9:12])
    short = (distances < 0.1).astype(np.float32)
    long = (distances < 0.2).astype(np.float32)
    short /= short.sum(axis=1, keepdims=True)
    long /= long.sum(axis=1, keepdims=True)
    return original, mesh, features, short, long


def _mesh_faces(mesh: Any) -> np.ndarray:
    faces_value = mesh.faces if hasattr(mesh, "faces") else mesh.cells
    return np.asarray(faces_value() if callable(faces_value) else faces_value)


def _tooth_regions(labels: np.ndarray, faces: list[list[int]]) -> list[dict[str, int]]:
    """Count connected non-gingiva face groups without assigning clinical identity."""
    regions: list[dict[str, int]] = []
    for label in sorted(set(labels.tolist()) - {0}):
        candidates = {index for index, value in enumerate(labels.tolist()) if value == label}
        by_vertex: dict[int, set[int]] = {}
        for index in candidates:
            for vertex in faces[index]:
                by_vertex.setdefault(vertex, set()).add(index)
        while candidates:
            start = min(candidates)
            stack = [start]
            component: list[int] = []
            candidates.remove(start)
            while stack:
                current = stack.pop()
                component.append(current)
                neighbours = {
                    neighbour
                    for vertex in faces[current]
                    for neighbour in by_vertex[vertex]
                    if neighbour in candidates
                }
                candidates.difference_update(neighbours)
                stack.extend(sorted(neighbours, reverse=True))
            regions.append({"label": int(label), "face_count": len(component)})
    return regions


def _export_label_meshes(mesh: Any, labels: np.ndarray, output: Path) -> list[str]:
    points_value = mesh.points
    points = points_value() if callable(points_value) else np.asarray(points_value)
    faces = _mesh_faces(mesh)
    exports: list[str] = []
    for label in sorted(set(labels.tolist())):
        selected = faces[labels == label]
        if len(selected) == 0:
            continue
        path = output / f"label-{label:02d}.obj"
        with path.open("w") as handle:
            for vertex in points:
                handle.write(f"v {vertex[0]:.9g} {vertex[1]:.9g} {vertex[2]:.9g}\n")
            for face in selected:
                handle.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")
        exports.append(str(path))
    return exports


def _export_colorized_visualization(mesh: Any, labels: np.ndarray, output: Path) -> Path:
    import matplotlib.pyplot as pyplot

    points_value = mesh.points
    points = points_value() if callable(points_value) else np.asarray(points_value)
    centers = points[_mesh_faces(mesh)].mean(axis=1)
    figure = pyplot.figure(figsize=(8, 6), dpi=160)
    axis = figure.add_subplot(projection="3d")
    scatter = axis.scatter(
        centers[:, 0],
        centers[:, 1],
        centers[:, 2],
        c=labels,
        cmap="tab20",
        s=1,
        linewidths=0,
    )
    axis.set_title("MeshSegNet research labels (face centroids)")
    axis.set_axis_off()
    figure.colorbar(scatter, ax=axis, label="Published class index")
    path = output / "meshsegnet_labels.png"
    figure.savefig(path, bbox_inches="tight")
    pyplot.close(figure)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="PHI-free STL, OBJ, or PLY input")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    checkout, checkpoint = _require_environment()
    sys.path.insert(0, str(checkout))
    import torch
    import vedo
    from meshsegnet import MeshSegNet

    started = time.perf_counter()
    original_mesh, mesh, features, short, long = _prepare(arguments.input)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MeshSegNet(num_classes=15, num_channels=15).to(device, dtype=torch.float)
    loaded = torch.load(checkpoint, map_location="cpu")
    model.load_state_dict(loaded["model_state_dict"])
    model.eval()
    feature_tensor = torch.from_numpy(features.T[None, ...]).to(device)
    short_tensor = torch.from_numpy(short[None, ...]).to(device)
    long_tensor = torch.from_numpy(long[None, ...]).to(device)
    with torch.no_grad():
        probabilities = model(feature_tensor, short_tensor, long_tensor).cpu().numpy()[0]
    labels = probabilities.argmax(axis=1).astype(np.int32)
    regions = _tooth_regions(labels, _mesh_faces(mesh).tolist())
    arguments.output.mkdir(parents=True, exist_ok=True)
    vedo.write(original_mesh, arguments.output / f"{arguments.input.stem}_original.vtp")
    result_mesh = mesh.clone()
    result_mesh.celldata["Label"] = labels
    vedo.write(result_mesh, arguments.output / f"{arguments.input.stem}_meshsegnet.vtp")
    summary = {
        "research_only": True,
        "input": str(arguments.input),
        "checkpoint": str(checkpoint),
        "device": str(device),
        "input_cell_count": int(original_mesh.ncells),
        "working_cell_count": int(mesh.ncells),
        "projected_back_to_original_mesh": original_mesh.ncells == mesh.ncells,
        "label_histogram": {
            str(label): int((labels == label).sum()) for label in sorted(set(labels))
        },
        "detected_tooth_regions": regions,
        "detected_tooth_region_count": len(regions),
        "runtime_seconds": time.perf_counter() - started,
        "output": str(arguments.output / f"{arguments.input.stem}_meshsegnet.vtp"),
        "original_mesh_output": str(arguments.output / f"{arguments.input.stem}_original.vtp"),
        "per_label_outputs": _export_label_meshes(mesh, labels, arguments.output),
        "colorized_visualization": str(
            _export_colorized_visualization(mesh, labels, arguments.output)
        ),
        "limitations": [
            "Author-published research checkpoint only; not clinically validated.",
            "Class labels are not a documented FDI contract.",
            "Downsampling changes mesh correspondence for inputs over 10,000 cells.",
        ],
    }
    (arguments.output / f"{arguments.input.stem}_meshsegnet.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
