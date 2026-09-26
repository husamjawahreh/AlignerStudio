"""Record which geometry libraries are importable for intake. Does not install any."""

from __future__ import annotations

import importlib
from time import perf_counter
from typing import Any

import numpy as np
import trimesh


def _version(module: Any) -> str | None:
    return getattr(module, "__version__", None)


def evaluate_intake_libraries() -> dict[str, Any]:
    """Time only a small in-memory cleanup. No new dependency is added."""
    box = trimesh.creation.box()
    noisy = box.copy()
    noisy.vertices = np.vstack((noisy.vertices, noisy.vertices[:1]))
    started = perf_counter()
    cleaned = noisy.copy()
    cleaned.merge_vertices()
    trimesh_ms = (perf_counter() - started) * 1000
    libraries: dict[str, Any] = {
        "trimesh": {
            "importable": True,
            "version": _version(trimesh),
            "used_for": "parse, quality, explicit derived cleanup",
            "sample_merge_vertices_ms": trimesh_ms,
        }
    }
    for name in ("manifold3d", "meshlib"):
        try:
            module = importlib.import_module(name)
        except ImportError:
            libraries[name] = {
                "importable": False,
                "version": None,
                "used_for": None,
                "reason": "Not importable in this environment. Not installed for FV-02.",
            }
            continue
        libraries[name] = {
            "importable": True,
            "version": _version(module),
            "used_for": None,
            "reason": (
                "Present, but intake does not need it. "
                "Watertight conversion is not applied to clinical scans."
            ),
        }
    libraries["decision"] = (
        "trimesh performs intake parsing and the optional derived cleanup. "
        "manifold3d and meshlib are not added to that path. Open3D is not integrated."
    )
    return libraries
