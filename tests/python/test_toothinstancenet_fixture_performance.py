"""N4.2: fixture reconstruction must stay O(vertices+faces), not O(vertices*faces).

These tests use a synthetic (but manifest/checksum-valid) artifact sized large enough that the
pre-fix `vertex in vertex_indices` tuple-membership scan would take many seconds, while the
current set-backed lookup completes quickly. The heavyweight real 171k-triangle artifact is
benchmarked separately in tests/performance (not part of the fast suite).
"""

import hashlib
import json
import struct
import time
from pathlib import Path

from adapters.toothinstancenet.fixture import load_validated_fixture
from domain.tooth.identification import ArchType

CONFIGURATION = {
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

# Enough triangles per instance to make the old O(V*F) tuple-membership scan clearly slow
# (multiple seconds) while staying fast (well under a second) for the current O(V+F) fix.
TRIANGLES_PER_INSTANCE = 60


def _instance_triangle(instance_id: int, index: int) -> tuple[tuple[float, float, float], ...]:
    # Each triangle gets its own 3 unique, non-degenerate vertices so no two instances share
    # geometry; offset far enough apart that instances never spatially collide.
    x = instance_id * 1000.0 + index * 3.0
    return (
        (x, 0.0, 1.0),
        (x, 0.0, 0.0),
        (x + 1.0, 1.0, 0.0),
    )


def _stl_bytes(triangle_count: int) -> bytes:
    output = bytearray(b"AlignerStudio performance artifact".ljust(80, b" "))
    output.extend(struct.pack("<I", triangle_count))
    for instance_id in range(14):
        for index in range(TRIANGLES_PER_INSTANCE):
            output.extend(struct.pack("<3f", 0.0, 0.0, 1.0))
            for vertex in _instance_triangle(instance_id, index):
                output.extend(struct.pack("<3f", *vertex))
            output.extend(struct.pack("<H", 0))
    # 3 background vertices/triangle to satisfy the -1 background-label requirement.
    background_x = 14 * 1000.0 + 1_000_000.0
    output.extend(struct.pack("<3f", 0.0, 0.0, 1.0))
    background_triangle = (
        (background_x, 0.0, 1.0),
        (background_x, 0.0, 0.0),
        (background_x + 1.0, 1.0, 0.0),
    )
    for vertex in background_triangle:
        output.extend(struct.pack("<3f", *vertex))
    output.extend(struct.pack("<H", 0))
    return bytes(output)


def _labels(arch: ArchType) -> list[int]:
    start = 31 if arch is ArchType.LOWER else 11
    labels = []
    for instance_id in range(14):
        labels += [start + instance_id // 2] * (3 * TRIANGLES_PER_INSTANCE)
    labels += [0] * 3
    return labels


def _write_artifact(root: Path) -> Path:
    root.mkdir()
    audits = []
    for arch in (ArchType.LOWER, ArchType.UPPER):
        total_triangles = 14 * TRIANGLES_PER_INSTANCE + 1
        (root / f"{arch.value}.stl").write_bytes(_stl_bytes(total_triangles))
        instance_values = [
            value for value in range(14) for _ in range(3 * TRIANGLES_PER_INSTANCE)
        ] + [-1] * 3
        label_values = _labels(arch)
        (root / f"{arch.value}.json").write_text(
            json.dumps({"instances": instance_values, "labels": label_values})
        )
        audits.append(
            {
                "arch": arch.value,
                "instances_length": len(instance_values),
                "labels_length": len(label_values),
                "unique_instances": [-1, *range(14)],
                "unique_labels": sorted(set(label_values)),
                "instance_to_label": {
                    str(index): label_values[index * 3 * TRIANGLES_PER_INSTANCE]
                    for index in range(14)
                },
                "expected_labels": sorted(set(label_values) - {0}),
                "semantic_pass": True,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps({"stage": "instances", "configuration": CONFIGURATION, "semantic_audit": audits})
    )
    (root / "README.md").write_text("performance fixture")
    lines = []
    artifact_names = (
        "README.md",
        "lower.json",
        "lower.stl",
        "manifest.json",
        "upper.json",
        "upper.stl",
    )
    for name in artifact_names:
        lines.append(f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    return root


def test_reconstruction_completes_quickly_at_scale(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    started = time.perf_counter()
    result = load_validated_fixture(root, arch=ArchType.UPPER)
    elapsed = time.perf_counter() - started
    assert len(result.segmentation.instances) == 14
    # O(V+F) should finish in well under a second at this scale; O(V*F) would take several
    # seconds. A generous 3s ceiling catches an algorithmic regression without being flaky.
    assert elapsed < 3.0, f"fixture reconstruction took {elapsed:.2f}s, expected O(V+F) scaling"


def test_reconstruction_preserves_deterministic_instance_ordering(tmp_path: Path) -> None:
    """N4.5.3: tooth_ref ordering must stay `instance:0..13` regardless of lookup structure."""
    root = _write_artifact(tmp_path / "artifact")
    result = load_validated_fixture(root, arch=ArchType.UPPER)
    tooth_refs = [tooth.tooth_ref for tooth in result.identification.teeth]
    assert tooth_refs == [f"upper:instance:{index}" for index in range(14)]
    instance_ids = [instance.instance_id for instance in result.segmentation.instances]
    assert instance_ids == list(range(14))


def test_reconstructed_geometry_matches_reference_scan_algorithm(tmp_path: Path) -> None:
    """Equivalence check: the O(1)-lookup fix must reconstruct byte-identical geometry."""
    from adapters.toothinstancenet import fixture as fx

    root = _write_artifact(tmp_path / "artifact")

    def reference_reconstruct(root: Path, arch: ArchType):
        manifest = fx._validate_manifest(root)
        payload, vertices, faces, instance_to_label = fx._validate_arch(root, arch, manifest)
        instances_array = payload["instances"]
        reconstructed = []
        for source_instance_id in range(14):
            vertex_indices = tuple(
                index
                for index, value in enumerate(instances_array)
                if value == source_instance_id
            )
            triangle_indices = tuple(
                index
                for index, face in enumerate(faces)
                if all(vertex in vertex_indices for vertex in face)
            )
            selected_vertices = tuple(
                sorted({vertex for index in triangle_indices for vertex in faces[index]})
            )
            local_lookup = {vertex: local for local, vertex in enumerate(selected_vertices)}
            local_faces = tuple(
                tuple(local_lookup[vertex] for vertex in faces[index])
                for index in triangle_indices
            )
            centroid = tuple(
                sum(vertices[index][axis] for index in vertex_indices) / len(vertex_indices)
                for axis in range(3)
            )
            reconstructed.append((triangle_indices, selected_vertices, local_faces, centroid))
        return reconstructed

    new_result = load_validated_fixture(root, arch=ArchType.UPPER)
    reference = reference_reconstruct(root, ArchType.UPPER)
    for instance, (ref_triangles, ref_vertices, ref_faces, ref_centroid) in zip(
        new_result.segmentation.instances, reference, strict=True
    ):
        assert instance.triangle_indices == ref_triangles
        assert instance.vertex_indices == ref_vertices
        assert instance.mesh_faces == ref_faces
        assert instance.centroid == ref_centroid
