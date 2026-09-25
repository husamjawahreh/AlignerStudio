"""Segmentation benchmark contract. Fixture output cannot be a completed real run."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from domain.tooth.identification import ArchType
from engines.segmentation.runtime_readiness import (
    ReadinessState,
    diagnose_toothinstancenet_readiness,
)

SOURCE_VERSION = "3dteethland-424252e3d94a1565c8c2090eb5bb456b76386b93"

OFFICIAL_CASE_ID = "official_real_case_stage2_verified_v1"
OFFICIAL_LOWER_SHA256 = "5cb38bd65cb2a9f04c89c580774e2d6c4ed28582fb46cc160fdc1249020feec3"
OFFICIAL_UPPER_SHA256 = "96e23a65e6a0eaa5550704be628dd3d27c6c5813213f6ea6b48b386d5178bd1e"


class BenchmarkRunState(StrEnum):
    NOT_RUN = "not_run"
    BLOCKED_BY_ENVIRONMENT = "blocked_by_environment"
    FAILED = "failed"
    COMPLETED = "completed"


class BenchmarkContractError(ValueError):
    """Raised when a result pretends to be measured evidence."""


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark_id: str
    case_id: str
    arch: str
    candidate: str
    candidate_version: str
    input_hash: str
    source_mesh_hash: str
    hardware: str
    runtime: str
    model_hash: str | None
    instance_count: int | None
    identity_count: int | None
    confidence_available: bool
    runtime_ms: float | None
    memory_mb: float | None
    failure_state: BenchmarkRunState
    limitations: tuple[str, ...]
    provenance: str
    fixture_substituted: bool = False

    def payload(self) -> dict:
        body = asdict(self)
        body["failure_state"] = self.failure_state.value
        body["limitations"] = list(self.limitations)
        return body


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_benchmark_result(result: BenchmarkResult) -> None:
    """COMPLETED is the only state allowed to carry inference measurements."""
    if result.fixture_substituted or result.provenance == "fixture":
        if result.failure_state is BenchmarkRunState.COMPLETED:
            raise BenchmarkContractError(
                "A fixture result must never populate a COMPLETED real-model benchmark."
            )
    if result.failure_state is BenchmarkRunState.COMPLETED:
        if result.instance_count is None or result.runtime_ms is None:
            raise BenchmarkContractError("COMPLETED requires instance_count and runtime_ms.")
        if result.provenance != "real_model_inference":
            raise BenchmarkContractError("COMPLETED provenance must be real_model_inference.")
        return
    if result.instance_count is not None or result.runtime_ms is not None:
        raise BenchmarkContractError(
            "Only COMPLETED may contain actual inference measurements."
        )
    if result.identity_count is not None or result.memory_mb is not None:
        raise BenchmarkContractError(
            "Only COMPLETED may contain identity or memory measurements."
        )


def _blocked_or_not_run(
    *,
    benchmark_id: str,
    case_id: str,
    arch: str,
    candidate: str,
    candidate_version: str,
    source_mesh_hash: str,
    failure_state: BenchmarkRunState,
    limitations: tuple[str, ...],
    provenance: str,
    model_hash: str | None = None,
) -> BenchmarkResult:
    result = BenchmarkResult(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arch=arch,
        candidate=candidate,
        candidate_version=candidate_version,
        input_hash=source_mesh_hash,
        source_mesh_hash=source_mesh_hash,
        hardware="unmeasured",
        runtime="not_executed",
        model_hash=model_hash,
        instance_count=None,
        identity_count=None,
        confidence_available=False,
        runtime_ms=None,
        memory_mb=None,
        failure_state=failure_state,
        limitations=limitations,
        provenance=provenance,
        fixture_substituted=False,
    )
    validate_benchmark_result(result)
    return result


def run_toothinstancenet_benchmark(
    mesh_path: Path,
    *,
    arch: ArchType,
    case_id: str,
    benchmark_id: str = "wave2_segmentation_v1",
) -> BenchmarkResult:
    """Record a real ToothInstanceNet attempt. Does not load fixture geometry."""
    source_hash = _sha256(mesh_path)
    readiness = diagnose_toothinstancenet_readiness()
    if readiness.state is not ReadinessState.READY:
        detail = "; ".join(item.detail for item in readiness.findings) or readiness.state.value
        blocked = readiness.state in {
            ReadinessState.BLOCKED_BY_ENVIRONMENT,
            ReadinessState.DEPENDENCY_MISSING,
        }
        return _blocked_or_not_run(
            benchmark_id=benchmark_id,
            case_id=case_id,
            arch=arch.value,
            candidate="toothinstancenet",
            candidate_version=SOURCE_VERSION,
            source_mesh_hash=source_hash,
            failure_state=(
                BenchmarkRunState.BLOCKED_BY_ENVIRONMENT
                if blocked
                else BenchmarkRunState.NOT_RUN
            ),
            limitations=(
                f"Readiness {readiness.state.value}. {detail}",
                "No fixture substitution.",
            ),
            provenance="real_model_not_executed",
            model_hash=None,
        )
    return _blocked_or_not_run(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arch=arch.value,
        candidate="toothinstancenet",
        candidate_version=SOURCE_VERSION,
        source_mesh_hash=source_hash,
        failure_state=BenchmarkRunState.NOT_RUN,
        limitations=(
            "Readiness is READY, but this command does not launch inference. "
            "A COMPLETED row requires a separate measured run.",
        ),
        provenance="real_model_not_executed",
    )


def run_contract_only_candidate(
    mesh_path: Path,
    *,
    arch: ArchType,
    case_id: str,
    candidate: str,
    candidate_version: str,
    limitation: str,
    benchmark_id: str = "wave2_segmentation_v1",
) -> BenchmarkResult:
    """Register a challenger that is not installed. Does not invent instances."""
    source_hash = _sha256(mesh_path)
    return _blocked_or_not_run(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arch=arch.value,
        candidate=candidate,
        candidate_version=candidate_version,
        source_mesh_hash=source_hash,
        failure_state=BenchmarkRunState.NOT_RUN,
        limitations=(limitation, "Not clinical segmentation evidence."),
        provenance="contract_only",
    )


def inventory_benchmark_cases(repo_root: Path) -> dict:
    """List known meshes. Does not modify files or invent cases."""
    official = repo_root / ".research" / "tmp" / OFFICIAL_CASE_ID
    cases: list[dict] = []
    if official.is_dir():
        arches = {}
        for arch, expected in (("lower", OFFICIAL_LOWER_SHA256), ("upper", OFFICIAL_UPPER_SHA256)):
            path = official / f"{arch}.stl"
            actual = _sha256(path) if path.is_file() else None
            arches[arch] = {
                "path": str(path),
                "present": path.is_file(),
                "sha256": actual,
                "matches_official_checksum": actual == expected,
            }
        cases.append(
            {
                "case_id": OFFICIAL_CASE_ID,
                "clinical_evidence": True,
                "modified": False,
                "arches": arches,
            }
        )
    alternate = repo_root / "data" / "benchmark" / "real-case"
    if alternate.is_dir():
        arches = {}
        for arch in ("lower", "upper"):
            path = alternate / f"{arch}.stl"
            arches[arch] = {
                "path": str(path),
                "present": path.is_file(),
                "sha256": _sha256(path) if path.is_file() else None,
            }
        cases.append(
            {
                "case_id": "data_benchmark_real_case",
                "clinical_evidence": False,
                "note": "Separate copy. Not a new clinical case. Compare hashes before use.",
                "arches": arches,
            }
        )
    synthetic = repo_root / "tests" / "fixtures" / "synthetic_segmentation_arch.obj"
    return {
        "cases": cases,
        "engineering_only": [
            {
                "path": str(synthetic),
                "present": synthetic.is_file(),
                "clinical_evidence": False,
                "note": "Synthetic geometry is for adapter tests only.",
            }
        ],
    }
