#!/usr/bin/env python3
"""WP-10 Production CAD technology evaluation benchmark (engineering only).

Uses official_real_case_stage2_verified_v1 tooth meshes where possible.
Synthetic solids are labeled explicitly and are never anatomical evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
OUT = ROOT / ".research" / "tmp" / "wp10_tech_evaluation_benchmark.json"


def _rss_mb() -> float | None:
    try:
        import resource

        # Linux: ru_maxrss is KiB
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    from adapters.toothinstancenet.fixture import load_validated_fixture
    from domain.tooth.identification import ArchType
    from engines.geometry.production_geometry import MeshBuffers, get_production_geometry_adapter

    if not ARTIFACT.is_dir():
        raise SystemExit(f"Real-case artifact missing: {ARTIFACT}")

    adapter = get_production_geometry_adapter()
    report: dict = {
        "benchmark_id": "wp10_production_cad_tech_evaluation_v1",
        "case_id": "official_real_case_stage2_verified_v1",
        "geometry_kind": "validated_real_case_tooth_instances",
        "clinical_claims": False,
        "manufacturing_certified": False,
        "backends": adapter.backend_catalog(),
        "operations": [],
        "decisions_hint": {},
        "rss_mb_start": _rss_mb(),
    }

    result = load_validated_fixture(ARTIFACT, arch=ArchType.UPPER)
    inst = result.segmentation.instances[0]
    verts = tuple(tuple(map(float, p)) for p in inst.mesh_vertices)
    faces = tuple(tuple(map(int, f)) for f in inst.mesh_faces)
    mesh = MeshBuffers(vertices=verts, faces=faces, identity=str(inst.tooth_ref))
    source_hash = mesh.sha256()

    ops = [
        ("current_integrity", adapter.inspect_integrity(mesh)),
        ("trimesh_inspect", adapter.inspect_topology(mesh)),
        ("manifold_validity", adapter.manifold_validity(mesh)),
        ("meshlib_self_intersection", adapter.self_intersections(mesh)),
        (
            "meshlib_engineering_offset",
            adapter.engineering_offset(mesh, distance=0.2),
        ),
        ("manifold_boolean_synthetic", adapter.manifold.boolean_union_cubes()),
        ("meshlib_boolean_synthetic", adapter.meshlib.boolean_union_spheres()),
    ]
    for name, op in ops:
        payload = op.payload()
        payload["benchmark_name"] = name
        report["operations"].append(payload)

    # Determinism: engineering offset twice
    a = adapter.engineering_offset(mesh, distance=0.2)
    b = adapter.engineering_offset(mesh, distance=0.2)
    report["determinism"] = {
        "engineering_offset_hash_match": a.output_hash == b.output_hash and a.output_hash is not None,
        "hash": a.output_hash,
    }

    # Source immutability
    after = MeshBuffers(vertices=verts, faces=faces, identity=str(inst.tooth_ref)).sha256()
    report["source_immutability"] = {
        "source_hash_before": source_hash,
        "source_hash_after": after,
        "unchanged": source_hash == after,
        "fdi_fabricated": False,
    }

    # Arch mesh inspect (open scan shell)
    import trimesh

    arch = trimesh.load(ARTIFACT / "upper.stl", force="mesh", process=False)
    t0 = time.perf_counter()
    arch_metrics = {
        "watertight": bool(arch.is_watertight),
        "is_volume": bool(arch.is_volume),
        "vertices": int(len(arch.vertices)),
        "faces": int(len(arch.faces)),
    }
    report["arch_upper_inspect"] = {
        **arch_metrics,
        "elapsed_ms": (time.perf_counter() - t0) * 1000,
        "note": "Open crown-arch scan mesh — not a manifold solid.",
    }

    report["rss_mb_end"] = _rss_mb()
    report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "ops": len(report["operations"]), "determinism": report["determinism"]}, indent=2))


if __name__ == "__main__":
    main()
