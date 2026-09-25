"""Wave 2 benchmark contract. Fixture output is not completed inference."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from domain.tooth.identification import ArchType
from engines.segmentation.benchmark import (
    OFFICIAL_LOWER_SHA256,
    OFFICIAL_UPPER_SHA256,
    BenchmarkContractError,
    BenchmarkResult,
    BenchmarkRunState,
    inventory_benchmark_cases,
    run_contract_only_candidate,
    run_toothinstancenet_benchmark,
    validate_benchmark_result,
)
from engines.segmentation.runtime_readiness import (
    ReadinessState,
    diagnose_toothinstancenet_readiness,
)

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"


def test_readiness_does_not_change_backend(monkeypatch) -> None:
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)
    before = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND")
    report = diagnose_toothinstancenet_readiness()
    assert os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND") == before
    assert report.backend_changed is False
    assert report.configured_backend == "onnx"
    assert report.state is not ReadinessState.READY
    assert report.state in {
        ReadinessState.BLOCKED_BY_ENVIRONMENT,
        ReadinessState.DEPENDENCY_MISSING,
        ReadinessState.MODEL_MISSING,
        ReadinessState.MISCONFIGURED,
    }


def test_fixture_cannot_be_completed_evidence() -> None:
    forged = BenchmarkResult(
        benchmark_id="wave2",
        case_id="official",
        arch="lower",
        candidate="toothinstancenet",
        candidate_version="fixture",
        input_hash="a" * 64,
        source_mesh_hash="b" * 64,
        hardware="cpu",
        runtime="fixture",
        model_hash=None,
        instance_count=14,
        identity_count=0,
        confidence_available=False,
        runtime_ms=1.0,
        memory_mb=1.0,
        failure_state=BenchmarkRunState.COMPLETED,
        limitations=(),
        provenance="fixture",
        fixture_substituted=True,
    )
    with pytest.raises(BenchmarkContractError, match="fixture"):
        validate_benchmark_result(forged)


def test_blocked_run_has_no_measurements(tmp_path) -> None:
    mesh = tmp_path / "lower.stl"
    mesh.write_bytes(b"solid x\nendsolid x\n")
    result = run_toothinstancenet_benchmark(
        mesh, arch=ArchType.LOWER, case_id="wave2-blocked"
    )
    assert result.failure_state is not BenchmarkRunState.COMPLETED
    assert result.instance_count is None
    assert result.runtime_ms is None
    assert result.memory_mb is None
    assert result.fixture_substituted is False
    assert result.provenance != "fixture"
    validate_benchmark_result(result)


def test_challengers_are_not_run(tmp_path) -> None:
    mesh = tmp_path / "upper.stl"
    mesh.write_bytes(b"solid u\nendsolid u\n")
    result = run_contract_only_candidate(
        mesh,
        arch=ArchType.UPPER,
        case_id="wave2",
        candidate="3dteethsam",
        candidate_version="not-installed",
        limitation="3DTeethSAM is not installed. Contract only.",
    )
    assert result.failure_state is BenchmarkRunState.NOT_RUN
    assert result.instance_count is None
    validate_benchmark_result(result)


@pytest.mark.skipif(not (OFFICIAL / "lower.stl").is_file(), reason="official case missing")
def test_official_real_case_benchmark_is_not_completed() -> None:
    inventory = inventory_benchmark_cases(ROOT)
    official = next(item for item in inventory["cases"] if item["case_id"].endswith("verified_v1"))
    assert official["clinical_evidence"] is True
    assert official["arches"]["lower"]["sha256"] == OFFICIAL_LOWER_SHA256
    assert official["arches"]["upper"]["sha256"] == OFFICIAL_UPPER_SHA256
    assert official["arches"]["lower"]["matches_official_checksum"] is True
    result = run_toothinstancenet_benchmark(
        OFFICIAL / "lower.stl",
        arch=ArchType.LOWER,
        case_id=official["case_id"],
    )
    assert result.source_mesh_hash == OFFICIAL_LOWER_SHA256
    assert result.failure_state is BenchmarkRunState.BLOCKED_BY_ENVIRONMENT
    assert result.instance_count is None
    assert "fixture" not in result.provenance
    assert all(item["clinical_evidence"] is False for item in inventory["engineering_only"])
