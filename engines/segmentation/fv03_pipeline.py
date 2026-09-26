"""FV-03 segmentation jobs.

The worker is process-local. ToothInstanceNet stays behind a backend object.
A blocked runtime persists the blocker and does not invent a segmentation.
"""

from __future__ import annotations

import copy
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock, Thread
from time import perf_counter, sleep
from typing import Any, Protocol

import numpy as np
import trimesh

from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from domain.tooth.segmentation_proof import refuse_fixture_on_real_record
from domain.tooth.segmentation_review import (
    ENVIRONMENT_CAPABILITY_STATES,
    SEMANTIC_IDENTITY_NOT_ESTABLISHED,
    SegmentationReviewError,
    apply_review_action,
    candidate_instance,
    empty_segmentation,
    segmentation_input_reasons,
)
from engines.geometry.scan_preparation import (
    PreparationError,
    _load_mesh,
    _sha256_file,
)
from engines.segmentation.fv01_execution import (
    DISCOVERED_CHECKPOINT,
    DISCOVERED_SOURCE,
    PINNED_SOURCE_REVISION,
    run_fv01_execution,
)

PINNED_CHECKPOINT_SHA256 = ToothInstanceNetConfig.checkpoint_sha256
_LOCK = RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_CAPABILITY: dict[str, Any] | None = None


class SegmentationInputError(PreparationError):
    """The prepared artifact is not an allowed segmentation input."""


class SegmentationJobConflict(PreparationError):
    """An equivalent or different segmentation job is already active."""


class SegmentationBackend(Protocol):
    name: str
    version: str
    model_id: str
    real_inference: bool

    def describe(self) -> dict[str, Any]:
        """Backend identity. This does not run inference."""

    def execute(self, prepared_path: Path, *, prepared_sha256: str) -> dict[str, Any]:
        """Return instances or a blocker. Must not invent FDI."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(job: dict[str, Any]) -> float | None:
    started = job.get("started_at")
    ended = job.get("ended_at")
    if not started or not ended:
        return None
    start = datetime.fromisoformat(str(started))
    end = datetime.fromisoformat(str(ended))
    return (end - start).total_seconds() * 1000.0


def _memory_mb() -> dict[str, float]:
    current = 0.0
    peak = 0.0
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            current = int(line.split()[1]) / 1024.0
        elif line.startswith("VmHWM:"):
            peak = int(line.split()[1]) / 1024.0
    return {"rss_mb": current, "peak_rss_mb": peak}


def reset_segmentation_jobs() -> None:
    global _CAPABILITY
    with _LOCK:
        _JOBS.clear()
        _CAPABILITY = None


def _session(artifact: dict[str, Any]) -> dict[str, Any]:
    current = artifact.get("segmentation")
    if not isinstance(current, dict):
        current = empty_segmentation()
        artifact["segmentation"] = current
    return current


def _prepared_sha(artifact: dict[str, Any]) -> str | None:
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    active = session.get("active") or {}
    value = active.get("output_sha256")
    return str(value) if value else None


def _geometry_facts(artifact: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(artifact.get("source_path") or ""))
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    active = session.get("active") or {}
    derived = Path(str(active.get("output_path") or ""))
    facts: dict[str, Any] = {
        "source_exists": source.is_file(),
        "source_hash_matches": False,
        "derived_exists": derived.is_file(),
        "derived_hash_matches": False,
        "finite": None,
        "face_vertex_consistent": None,
        "face_count": None,
        "vertex_count": None,
    }
    if source.is_file():
        facts["source_hash_matches"] = _sha256_file(source) == artifact.get("sha256")
    if derived.is_file() and not derived.name.endswith(".partial"):
        facts["derived_hash_matches"] = _sha256_file(derived) == active.get("output_sha256")
        try:
            mesh = _load_mesh(derived)
        except PreparationError:
            facts["finite"] = False
            facts["face_vertex_consistent"] = False
        else:
            vertices = np.asarray(mesh.vertices, dtype=np.float64)
            faces = np.asarray(mesh.faces)
            facts["vertex_count"] = int(len(vertices))
            facts["face_count"] = int(len(faces))
            facts["finite"] = bool(vertices.size) and bool(np.isfinite(vertices).all())
            facts["face_vertex_consistent"] = not (
                len(faces) and (int(faces.min()) < 0 or int(faces.max()) >= len(vertices))
            )
    return facts


def assess_segmentation_input(artifact: dict[str, Any]) -> dict[str, Any]:
    """Full input gate. The prepared mesh is loaded once."""
    geometry = _geometry_facts(artifact)
    reasons = segmentation_input_reasons(artifact, geometry=geometry)
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    comparison = (session.get("quality_comparison") or {}).get("prepared") or {}
    stored_faces = comparison.get("face_count")
    if (
        geometry.get("face_count") is not None
        and stored_faces is not None
        and geometry["face_count"] != stored_faces
    ):
        reasons.append("face_count_inconsistent")
    active = session.get("active") or {}
    return {
        "accepted": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "prepared_sha256": active.get("output_sha256"),
        "source_sha256": artifact.get("sha256"),
        "readiness": session.get("readiness"),
        "face_count": geometry.get("face_count"),
        "vertex_count": geometry.get("vertex_count"),
        "finite": geometry.get("finite"),
        "technical_only": True,
        "clinically_ready": False,
    }


def _availability(state: str) -> str:
    if state == "AVAILABLE":
        return "AVAILABLE"
    if state in ENVIRONMENT_CAPABILITY_STATES:
        return "ENVIRONMENT_BLOCKED"
    return "NOT_AVAILABLE"


def _map_capability(report: dict[str, Any]) -> dict[str, Any]:
    states = set(report.get("applicable_states") or [])
    applicable: list[str] = []
    if "DRIVER_UNAVAILABLE" in states or "GPU_UNAVAILABLE" in states:
        applicable.append("DRIVER_UNAVAILABLE")
    if "PYTORCH_UNAVAILABLE" in states:
        applicable.append("PYTORCH_UNAVAILABLE")
    if "POINTOPS_UNAVAILABLE" in states or "CUDA_UNAVAILABLE" in states:
        applicable.append("CUDA_EXTENSION_UNAVAILABLE")
    if "MODEL_MISSING" in states or "MODEL_LOAD_FAILED" in states:
        applicable.append("MODEL_ARTIFACT_UNAVAILABLE")
    if "MODEL_CONTRACT_UNKNOWN" in states:
        applicable.append("MODEL_CONTRACT_UNAVAILABLE")
    contract = report.get("contract") or {}
    checkpoint = report.get("checkpoint") or {}
    contract_ok = (
        bool(contract.get("tensor_contract_rederived"))
        and contract.get("state") == "TENSOR_CONTRACT_ESTABLISHED"
    )
    if report.get("ready") and contract_ok:
        primary = "AVAILABLE"
        executable = True
    else:
        executable = False
        primary = applicable[0] if applicable else "BACKEND_ERROR"
    report = {
        **report,
        "checkpoint_present": bool(checkpoint.get("present")),
        "checkpoint_hash_matches": checkpoint.get("matches_pinned_digest"),
    }
    output = contract.get("output") or {}
    point = contract.get("input") or {}
    identify = contract.get("identify_head") or {}
    return {
        "capability_state": primary,
        "applicable_states": applicable or [primary],
        "availability": _availability(primary),
        "executable": executable,
        "real_inference": False,
        "fixture_selected": False,
        "backend_name": "toothinstancenet",
        "backend_version": ToothInstanceNetConfig.model_version,
        "model_id": "instseg_full.ckpt",
        "model_sha256": PINNED_CHECKPOINT_SHA256 if report.get("checkpoint_hash_matches") else None,
        "checkpoint_present": bool(report.get("checkpoint_present")),
        "checkpoint_hash_matches": report.get("checkpoint_hash_matches"),
        "input_channels": point.get("in_channels"),
        "identify_logits": identify.get("out_channels"),
        "instance_ids_from": output.get("instance_ids_generated_by"),
        "fdi_encoded": output.get("fdi_encoded"),
        "arch_encoded": output.get("arch_encoded"),
        "left_right_encoded": output.get("left_right_encoded"),
        "model_class_mapping": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "left_right_config_verified": False,
        "preprocessing_description": (
            "Checkpoint does not store preprocessing. Upstream declarations are not "
            "treated as a measured contract, and this probe does not run them."
        ),
        "output_schema_version": "fv03-candidate-1",
        "runtime": {
            "primary_state": report.get("primary_state"),
            "device": None,
            "fv01_applicable_states": list(report.get("applicable_states") or []),
        },
        "clinical_accuracy_claim": False,
        "message": (
            "ToothInstanceNet can execute on this host."
            if executable
            else (
                "ToothInstanceNet cannot execute. "
                f"Primary blocker: {primary}. No segmentation was fabricated."
            )
        ),
    }


def detect_tin_capability(*, refresh: bool = False) -> dict[str, Any]:
    """Probe the real ToothInstanceNet runtime. Does not run inference."""
    global _CAPABILITY
    with _LOCK:
        if _CAPABILITY is not None and not refresh:
            return copy.deepcopy(_CAPABILITY)
    report = run_fv01_execution(
        hash_checkpoint=True, extract_contract=True, attempt_inference=False
    )
    mapped = _map_capability(report)
    mapped["fv01_primary_state"] = report.get("primary_state")
    mapped["checkpoint_contract_state"] = (report.get("contract") or {}).get("state")
    from engines.segmentation.fv03_1_runtime import (
        build_runtime_manifest,
        classify_self_test,
    )

    manifest = build_runtime_manifest(report, capability_state=mapped["capability_state"])
    self_test = classify_self_test(mapped)
    manifest["self_test_state"] = self_test["state"]
    manifest["runtime_capability_state"] = mapped["capability_state"]
    mapped["runtime_manifest"] = manifest
    mapped["self_test"] = self_test
    with _LOCK:
        _CAPABILITY = mapped
    return copy.deepcopy(mapped)


class ToothInstanceNetBackend:
    """TIN adapter. Domain code does not import this class's checkpoint facts."""

    name = "toothinstancenet"
    version = ToothInstanceNetConfig.model_version
    model_id = "instseg_full.ckpt"
    real_inference = True

    def describe(self) -> dict[str, Any]:
        return detect_tin_capability()

    def execute(self, prepared_path: Path, *, prepared_sha256: str) -> dict[str, Any]:
        capability = detect_tin_capability()
        if not capability["executable"]:
            return {
                "status": "blocked",
                "blocked": True,
                "instances": [],
                "capability": capability,
                "real_inference": False,
                "fixture": False,
                "device": None,
                "duration_ms": None,
            }
        started = perf_counter()
        translated = _execute_tin_engine(prepared_path, prepared_sha256=prepared_sha256)
        translated["duration_ms"] = (perf_counter() - started) * 1000.0
        translated["capability"] = capability
        return translated


class DeterministicMockBackend:
    """Contract stand-in for tests. This is not ToothInstanceNet inference."""

    name = "deterministic_mock"
    version = "fv03-mock-1"
    model_id = "mock-contract"
    real_inference = False

    def describe(self) -> dict[str, Any]:
        return {
            "capability_state": "AVAILABLE",
            "applicable_states": ["AVAILABLE"],
            "availability": "AVAILABLE",
            "executable": True,
            "real_inference": False,
            "inference_kind": "mock_contract",
            "fixture_selected": False,
            "backend_name": self.name,
            "backend_version": self.version,
            "model_id": self.model_id,
            "model_sha256": None,
            "model_class_mapping": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
            "fdi_encoded": False,
            "clinical_accuracy_claim": False,
            "message": "Deterministic mock backend. Not real model inference.",
        }

    def execute(self, prepared_path: Path, *, prepared_sha256: str) -> dict[str, Any]:
        mesh = _load_mesh(prepared_path)
        faces = np.asarray(mesh.faces)
        count = int(len(faces))
        even = [index for index in range(count) if index % 2 == 0]
        odd = [index for index in range(count) if index % 2 == 1]
        return {
            "status": "completed",
            "blocked": False,
            "real_inference": False,
            "inference_kind": "mock_contract",
            "fixture": False,
            "device": "mock",
            "duration_ms": 0.0,
            "groups": [
                {"face_indices": even, "raw_model_class": 0, "confidence": None},
                {"face_indices": odd, "raw_model_class": 1, "confidence": None},
            ],
            "capability": self.describe(),
        }


def _execute_tin_engine(prepared_path: Path, *, prepared_sha256: str) -> dict[str, Any]:
    from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter
    from domain.tooth.identification import ArchType
    from engines.segmentation.toothinstancenet import ToothInstanceNetEngine

    source_env = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "").strip()
    source = Path(source_env) if source_env else DISCOVERED_SOURCE
    checkpoint_env = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "").strip()
    checkpoint = Path(checkpoint_env) if checkpoint_env else DISCOVERED_CHECKPOINT
    if _source_revision(source) != PINNED_SOURCE_REVISION:
        raise SegmentationInputError("Pinned ToothInstanceNet source revision does not match.")
    config = ToothInstanceNetConfig(
        checkpoint_path=checkpoint,
        source_root=source,
        device="cuda",
    )
    engine = ToothInstanceNetEngine(ToothInstanceNetAdapter(config), arch=ArchType.UPPER)
    result = engine.segment(str(prepared_path))
    if result.segmentation.metadata.fixture or result.identification.fixture:
        raise SegmentationInputError("Fixture segmentation cannot be used as real inference.")
    groups = []
    for tooth in result.identification.teeth:
        instance = tooth.instance
        if instance.fixture:
            raise SegmentationInputError("Fixture instance cannot be used as real inference.")
        groups.append(
            {
                "face_indices": list(instance.triangle_indices),
                "raw_model_class": instance.semantic_label,
                "confidence": tooth.confidence.score if tooth.confidence_available else None,
                "confidence_available": bool(tooth.confidence_available),
            }
        )
    return {
        "status": "completed",
        "blocked": False,
        "real_inference": True,
        "inference_kind": "toothinstancenet",
        "fixture": False,
        "device": "cuda",
        "prepared_sha256": prepared_sha256,
        "model_sha256": config.checkpoint_sha256,
        "groups": groups,
        "fdi_authoritative": False,
        "clinical_accuracy_claim": False,
    }


def _source_revision(source: Path) -> str | None:
    if not source.is_dir():
        return None
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _public_job(job: dict[str, Any], *, duplicate: bool = False) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "case_id": job["case_id"],
        "arch": job.get("arch"),
        "prepared_input_sha": job.get("prepared_input_sha"),
        "source_sha256": job.get("source_sha256"),
        "backend": job.get("backend"),
        "model_sha256": job.get("model_sha256"),
        "state": job["state"],
        "queued_at": job.get("queued_at"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
        "duration_ms": _duration_ms(job),
        "progress": job.get("progress"),
        "progress_stage": job.get("progress_stage"),
        "output_run_id": job.get("output_run_id"),
        "error": job.get("error"),
        "blocked": bool(job.get("blocked")),
        "real_inference": bool(job.get("real_inference")),
        "duplicate": duplicate or bool(job.get("duplicate")),
        "fixture": False,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "clinical_accuracy_claim": False,
        "clinically_verified": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "self_test_state": job.get("self_test_state"),
        "quality_evaluation": "NOT_AVAILABLE",
        "validation_status": job.get("validation_status"),
        "instance_count": job.get("instance_count"),
        "evidence_bundle_sha256": job.get("evidence_bundle_sha256"),
        "review_state": job.get("review_state"),
        "requires_review": job.get("requires_review", True),
        "execution_origin": job.get("execution_origin"),
        "native_execution": bool(job.get("native_execution")),
        "split_available": False,
        "manual_segmentation_correction": "NOT_IMPLEMENTED",
    }


def _remember(job: dict[str, Any]) -> None:
    artifact = job["_artifact"]
    session = _session(artifact)
    public = _public_job(job)
    jobs = [item for item in session.get("jobs") or [] if item.get("job_id") != job["job_id"]]
    jobs.append(public)
    session["jobs"] = jobs


def submit_segmentation_job(
    artifact: dict[str, Any],
    *,
    case_id: str,
    arch: str,
    backend: SegmentationBackend | None = None,
    on_persist: Any = None,
    schedule: bool = True,
) -> dict[str, Any]:
    gate = assess_segmentation_input(artifact)
    if not gate["accepted"]:
        raise SegmentationInputError(
            "Segmentation input was refused: " + ", ".join(gate["reasons"])
        )
    chosen = backend if backend is not None else ToothInstanceNetBackend()
    prepared_sha = str(gate["prepared_sha256"])
    with _LOCK:
        active = [
            job
            for job in _JOBS.values()
            if job["case_id"] == case_id
            and job.get("arch") == arch
            and job["state"] in {"queued", "running"}
        ]
        equivalent = next(
            (
                job
                for job in active
                if (
                    job.get("prepared_input_sha") == prepared_sha
                    and job.get("backend") == chosen.name
                )
            ),
            None,
        )
        if equivalent is not None:
            return _public_job(equivalent, duplicate=True)
        if active:
            raise SegmentationJobConflict("A segmentation job is already active for this arch.")
        session = _session(artifact)
        job_id = str(uuid.uuid4())
        job: dict[str, Any] = {
            "job_id": job_id,
            "case_id": case_id,
            "arch": arch,
            "prepared_input_sha": prepared_sha,
            "source_sha256": gate["source_sha256"],
            "backend": chosen.name,
            "model_sha256": None,
            "state": "queued",
            "queued_at": _now(),
            "started_at": None,
            "ended_at": None,
            "progress": 0.0,
            "progress_stage": None,
            "output_run_id": None,
            "error": None,
            "blocked": False,
            "real_inference": False,
            "expected_generation": int(session.get("generation") or 0),
            "expected_preparation_generation": int(
                (artifact.get("preparation") or {}).get("commit_generation") or 0
            ),
            "cancel_requested": False,
            "_artifact": artifact,
            "_backend": chosen,
            "_on_persist": on_persist,
        }
        _JOBS[job_id] = job
        _remember(job)
        public = _public_job(job)
    if on_persist is not None:
        on_persist()
    if schedule:
        Thread(
            target=run_segmentation_job,
            args=(job_id,),
            name="alignerstudio-segmentation",
            daemon=True,
        ).start()
    return public


def get_segmentation_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        return _public_job(job)


def cancel_segmentation_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        if job["state"] in {"completed", "failed", "cancelled"}:
            return _public_job(job)
        job["cancel_requested"] = True
        if job["state"] == "queued":
            _finish(
                job,
                "cancelled",
                {"code": "CANCELLED", "message": "Segmentation was cancelled before it started."},
            )
        return _public_job(job)


def wait_segmentation_job(job_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = perf_counter() + timeout_s
    while perf_counter() < deadline:
        current = get_segmentation_job(job_id)
        if current is None:
            raise SegmentationInputError("Segmentation job is missing.")
        if current["state"] in {"completed", "failed", "cancelled"}:
            return current
        sleep(0.02)
    raise SegmentationInputError("Segmentation job did not finish.")


def run_segmentation_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None or job["state"] != "queued":
            return None if job is None else _public_job(job)
        if job.get("cancel_requested"):
            _finish(
                job,
                "cancelled",
                {"code": "CANCELLED", "message": "Segmentation was cancelled before it started."},
            )
            return _public_job(job)
        job["state"] = "running"
        job["started_at"] = _now()
        job["progress"] = 0.1
        job["progress_stage"] = "input_gate"
        _remember(job)
    try:
        _execute(job)
    except SegmentationInputError as exc:
        code = "STALE_SEGMENTATION" if "stale" in str(exc).lower() else "INPUT_UNSUPPORTED"
        _fail(job, code, str(exc))
    except Exception as exc:  # noqa: BLE001 - a job failure stays on the job record
        _fail(job, "BACKEND_ERROR", exc.__class__.__name__)
    return get_segmentation_job(job_id)


def _fail(job: dict[str, Any], code: str, message: str) -> None:
    with _LOCK:
        if job["state"] in {"completed", "failed", "cancelled"}:
            return
        _finish(job, "failed", {"code": code, "message": message})


def _finish(job: dict[str, Any], state: str, error: dict[str, Any] | None) -> None:
    job["state"] = state
    job["ended_at"] = _now()
    job["error"] = error
    if state == "completed":
        job["progress"] = 1.0
        job["progress_stage"] = "completed"
    _remember(job)
    persist = job.get("_on_persist")
    if persist is not None:
        persist()


def _cancelled(job: dict[str, Any]) -> bool:
    with _LOCK:
        return bool(job.get("cancel_requested")) or job["state"] in {"cancelled", "failed"}


def _execute(job: dict[str, Any]) -> None:
    artifact = job["_artifact"]
    gate = assess_segmentation_input(artifact)
    if not gate["accepted"]:
        raise SegmentationInputError(
            "Segmentation input was refused: " + ", ".join(gate["reasons"])
        )
    if gate["prepared_sha256"] != job["prepared_input_sha"]:
        raise SegmentationInputError("stale prepared artifact; this result was not published.")
    session = _session(artifact)
    preparation = artifact.get("preparation") or {}
    if int(session.get("generation") or 0) != int(job["expected_generation"]):
        raise SegmentationInputError("stale segmentation job; a newer run was not overwritten.")
    expected_preparation = int(job["expected_preparation_generation"])
    if int(preparation.get("commit_generation") or 0) != expected_preparation:
        raise SegmentationInputError("stale prepared artifact; this result was not published.")
    if _cancelled(job):
        _fail(job, "CANCELLED", "Segmentation was cancelled before a result was published.")
        return
    with _LOCK:
        job["progress"] = 0.45
        job["progress_stage"] = "capability"
        _remember(job)
    backend: SegmentationBackend = job["_backend"]
    produced = backend.execute(
        Path(str((preparation.get("active") or {}).get("output_path"))),
        prepared_sha256=str(job["prepared_input_sha"]),
    )
    if produced.get("fixture") is True:
        refuse_fixture_on_real_record(
            processing_mode="real_case",
            payload={"fixture": True, "processing_mode": "real_case"},
        )
    if _cancelled(job):
        _fail(job, "CANCELLED", "Segmentation was cancelled before a result was published.")
        return
    if gate["prepared_sha256"] != job["prepared_input_sha"]:
        raise SegmentationInputError("stale prepared artifact; this result was not published.")
    if int(_session(artifact).get("generation") or 0) != int(job["expected_generation"]):
        raise SegmentationInputError("stale segmentation job; a newer run was not overwritten.")
    _commit_run(job, produced, gate)


def _commit_run(job: dict[str, Any], produced: dict[str, Any], gate: dict[str, Any]) -> None:
    artifact = job["_artifact"]
    session = _session(artifact)
    capability = produced.get("capability") or {}
    blocked = bool(produced.get("blocked")) or produced.get("status") == "blocked"
    run_id = str(uuid.uuid4())
    backend_name = capability.get("backend_name") or job["backend"]
    backend_version = capability.get("backend_version") or ""
    model_id = capability.get("model_id") or ""
    model_sha = capability.get("model_sha256") or produced.get("model_sha256")
    real_inference = bool(produced.get("real_inference"))
    instances = []
    if not blocked:
        for index, group in enumerate(produced.get("groups") or []):
            confidence = group.get("confidence")
            available = bool(group.get("confidence_available")) and confidence is not None
            instances.append(
                candidate_instance(
                    instance_id=f"inst-{index}",
                    run_id=run_id,
                    prepared_sha256=str(job["prepared_input_sha"]),
                    face_indices=list(group.get("face_indices") or []),
                    backend_name=backend_name,
                    backend_version=str(backend_version),
                    model_id=str(model_id),
                    model_sha256=model_sha,
                    raw_model_class=group.get("raw_model_class"),
                    confidence=group.get("confidence") if available else None,
                    confidence_available=available,
                    real_inference=real_inference,
                )
            )
    mesh_stats = {
        "vertex_count": gate.get("vertex_count"),
        "face_count": gate.get("face_count"),
        "finite": gate.get("finite"),
    }
    run = {
        "run_id": run_id,
        "job_id": job["job_id"],
        "status": "blocked" if blocked else "completed",
        "blocked": blocked,
        "input": {
            "source_sha256": job["source_sha256"],
            "prepared_sha256": job["prepared_input_sha"],
            "readiness": gate.get("readiness"),
        },
        "source_sha256": job["source_sha256"],
        "prepared_sha256": job["prepared_input_sha"],
        "backend": {
            "name": backend_name,
            "version": backend_version,
            "model_id": model_id,
            "model_sha256": model_sha,
        },
        "input_mesh": mesh_stats,
        "preprocessing_description": capability.get("preprocessing_description"),
        "output_schema_version": "fv03-candidate-1",
        "runtime": capability.get("runtime") or {"device": produced.get("device")},
        "device": produced.get("device"),
        "duration_ms": produced.get("duration_ms"),
        "real_inference": real_inference,
        "inference_kind": produced.get("inference_kind") or (
            "not_run" if blocked else "toothinstancenet"
        ),
        "execution_origin": (
            "SIMULATED"
            if produced.get("inference_kind") == "mock_contract"
            else ("LOCAL_NATIVE" if real_inference and not blocked else "UNKNOWN")
        ),
        "native_execution": bool(real_inference and not blocked and produced.get("inference_kind") != "mock_contract"),
        "fixture": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "clinical_accuracy_claim": False,
        "clinical_validation": False,
        "clinical_axes": False,
        "occlusion_established": False,
        "instances": instances,
        "model_instances": copy.deepcopy(instances),
        "replaces_prepared_mesh": False,
        "hole_filling": False,
        "created_at": _now(),
        "capability_state": capability.get("capability_state"),
        "availability": capability.get("availability"),
        "blocker": None
        if not blocked
        else {
            "code": capability.get("capability_state") or "BACKEND_ERROR",
            "message": capability.get("message") or "Segmentation backend is not executable.",
            "availability": capability.get("availability"),
        },
        "limitations": [
            "Segmentation success is not clinical validity.",
            "Semantic identity is NOT_ESTABLISHED.",
            "Seven model classes are not FDI, arch identity, or left/right identity.",
        ],
    }
    from engines.segmentation.fv03_1_runtime import quality_evaluation
    from engines.segmentation.fv03_2_evidence import (
        build_fv03_2_evidence_bundle,
        build_segmentation_run_contract,
        preprocessing_configuration,
        preprocessing_reproducibility_evidence_reference,
        validate_segmentation_geometry_gate,
    )

    geometry_gate = validate_segmentation_geometry_gate(
        run=run,
        face_count=gate.get("face_count"),
        finite=gate.get("finite"),
    )
    self_test = capability.get("self_test") or {}
    job["self_test_state"] = self_test.get("state")
    quality = quality_evaluation(ground_truth_present=False)
    run["quality_evaluation"] = quality
    run["split_available"] = False
    run["clinically_verified"] = False
    runtime_manifest = capability.get("runtime_manifest") or {}
    rng_seed = produced.get("rng_seed")
    if rng_seed is None and isinstance(capability.get("rng_seed"), int):
        rng_seed = capability.get("rng_seed")
    preprocessing = preprocessing_configuration(
        rng_seed=rng_seed if isinstance(rng_seed, int) else None,
        executed=bool(real_inference and not blocked),
    )
    groups = list(produced.get("groups") or [])
    output_reference = None
    instance_generation = None
    if real_inference and not blocked:
        import hashlib
        import json

        output_reference = hashlib.sha256(
            json.dumps(groups, sort_keys=True, default=str).encode()
        ).hexdigest()
        instance_generation = {
            "algorithm": "learned_region_cluster",
            "version": str(backend_version),
            "real_model": True,
            "parameters": produced.get("clustering_parameters"),
        }
    peak_rss = produced.get("peak_rss_bytes")
    peak_gpu = produced.get("peak_gpu_memory_bytes")
    run_contract = build_segmentation_run_contract(
        run_id=run_id,
        case_id=str(job.get("case_id") or ""),
        prepared_input_artifact_id=job.get("prepared_input_sha"),
        prepared_input_sha256=job.get("prepared_input_sha"),
        prepared_mesh_statistics=mesh_stats,
        model_identifier=str(model_id) if model_id else None,
        checkpoint_sha256=model_sha,
        model_version=str(backend_version) if backend_version else None,
        backend_name=str(backend_name),
        backend_version=str(backend_version),
        python_version=runtime_manifest.get("python_version"),
        pytorch_version=runtime_manifest.get("pytorch_version"),
        cuda_version=runtime_manifest.get("cuda_version"),
        pointops_identity=(
            runtime_manifest.get("pointops_version")
            if runtime_manifest.get("pointops_available")
            else None
        ),
        execution_device=produced.get("device"),
        preprocessing=preprocessing,
        inference_duration_ms=produced.get("duration_ms"),
        peak_rss_bytes=peak_rss if isinstance(peak_rss, int) else None,
        peak_gpu_memory_bytes=peak_gpu if isinstance(peak_gpu, int) else None,
        raw_model_output_reference=output_reference,
        instance_clustering_parameters=instance_generation,
        instances=instances,
        deterministic_validation=geometry_gate,
        evidence_bundle_sha256=None,
        immutable_run_status="blocked" if blocked else "completed",
        real_inference=real_inference,
        created_at=run.get("created_at"),
        execution_origin=str(run.get("execution_origin") or "UNKNOWN"),
    )
    run["evidence"] = build_fv03_2_evidence_bundle(
        run_id=run_id,
        case_id=str(job.get("case_id") or ""),
        prepared_input_sha256=job.get("prepared_input_sha"),
        input_mesh=mesh_stats,
        model_sha256=model_sha,
        backend_name=str(backend_name),
        backend_version=str(backend_version),
        runtime_manifest=runtime_manifest or None,
        device=produced.get("device"),
        preprocessing=preprocessing,
        inference_duration_ms=produced.get("duration_ms"),
        peak_rss_bytes=peak_rss if isinstance(peak_rss, int) else None,
        peak_gpu_memory_bytes=peak_gpu if isinstance(peak_gpu, int) else None,
        raw_model_output_reference=output_reference,
        instance_generation=instance_generation,
        instances=instances,
        technical_validation=run.get("technical_validation") or {},
        real_inference=real_inference,
        blocked=blocked,
        blocker=run.get("blocker"),
        inference_kind=str(run.get("inference_kind") or ""),
        run_contract=run_contract,
    )
    evidence_sha = run["evidence"].get("evidence_sha256")
    run_contract["evidence_bundle_sha256"] = evidence_sha
    run["run_contract"] = run_contract
    run["preprocessing"] = preprocessing
    run["preprocessing_reproducibility_evidence"] = (
        preprocessing_reproducibility_evidence_reference()
    )
    run["validation_status"] = geometry_gate.get("status")
    run["evidence_bundle_sha256"] = evidence_sha
    job["validation_status"] = geometry_gate.get("status")
    job["instance_count"] = 0 if blocked else len(instances)
    job["evidence_bundle_sha256"] = evidence_sha
    job["review_state"] = "MODEL_PREDICTION" if not blocked and instances else "REQUIRES_REVIEW"
    job["requires_review"] = True
    job["execution_origin"] = run.get("execution_origin")
    job["native_execution"] = bool(run.get("native_execution"))
    with _LOCK:
        if int(session.get("generation") or 0) != int(job["expected_generation"]):
            raise SegmentationInputError("stale segmentation job; a newer run was not overwritten.")
        if _cancelled(job):
            _finish(
                job,
                "cancelled",
                {
                    "code": "CANCELLED",
                    "message": "Segmentation was cancelled before a result was published.",
                },
            )
            return
        session["generation"] = int(session.get("generation") or 0) + 1
        session.setdefault("runs", []).append(
            {key: value for key, value in run.items() if key != "model_instances"}
        )
        session["active_run_id"] = run_id
        session["semantic_identity"] = SEMANTIC_IDENTITY_NOT_ESTABLISHED
        session["fdi_assigned"] = False
        session["clinically_segmented"] = False
        session["clinical_accuracy_claim"] = False
        session["clinical_validation"] = False
        session["availability"] = run.get("availability")
        session["capability_state"] = run.get("capability_state")
        session["self_test_state"] = job.get("self_test_state")
        session["quality_evaluation"] = "NOT_AVAILABLE"
        session["split_available"] = False
        session["runtime_manifest"] = capability.get("runtime_manifest")
        session["active_run"] = {
            "run_id": run_id,
            "status": run["status"],
            "reviewable": run["reviewable"],
            "real_inference": real_inference,
            "prepared_sha256": job["prepared_input_sha"],
            "source_sha256": job["source_sha256"],
            "blocker": run.get("blocker"),
            "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
            "inference_kind": run["inference_kind"],
            "execution_origin": run.get("execution_origin"),
            "native_execution": bool(run.get("native_execution")),
            "validation_status": run.get("validation_status"),
            "instance_count": 0 if blocked else len(instances),
            "evidence_bundle_sha256": evidence_sha,
            "requires_review": True,
            "clinically_verified": False,
            "quality_evaluation": "NOT_AVAILABLE",
        }
        if run["reviewable"]:
            session["review"] = {
                "run_id": run_id,
                "instances": copy.deepcopy(instances),
                "model_instances": copy.deepcopy(instances),
                "undo": [],
                "redo": [],
                "events": [
                    {
                        "action": "model_prediction_preserved",
                        "detail": {"run_id": run_id},
                        "mutates_model_prediction": False,
                    }
                ],
                "selected_instance_id": None,
                "id_counter": 0,
            }
        else:
            session["review"] = {
                "run_id": run_id,
                "instances": [],
                "model_instances": [],
                "undo": [],
                "redo": [],
                "events": [],
                "reviewable": False,
                "reason": "No segmentation candidate was produced.",
            }
        job["output_run_id"] = run_id
        job["real_inference"] = real_inference
        job["model_sha256"] = model_sha
        job["blocked"] = blocked
        if blocked:
            _finish(job, "failed", run["blocker"])
        else:
            _finish(job, "completed", None)


def import_external_segmentation_evidence(
    artifact: dict[str, Any],
    payload: dict[str, Any],
    *,
    case_id: str,
) -> dict[str, Any]:
    """Seal a transferred external CUDA evidence bundle onto an accepted prepared artifact.

    Does not execute ToothInstanceNet. Does not relabel the run as local native execution.
    """
    from engines.segmentation.fv03_2_evidence import (
        evaluate_external_inference_seal,
        external_evidence_intact,
    )

    gate = assess_segmentation_input(artifact)
    vertices = None
    faces = None
    derived = Path(_prepared_path_from_artifact(artifact))
    if derived.is_file():
        try:
            mesh = _load_mesh(derived)
        except PreparationError:
            mesh = None
        if mesh is not None:
            vertices = np.asarray(mesh.vertices, dtype=np.float64)
            faces = np.asarray(mesh.faces, dtype=np.int64)
    decision = evaluate_external_inference_seal(
        payload,
        case_id=case_id,
        prepared_artifact_present=bool(gate.get("accepted")),
        prepared_sha256=str(gate.get("prepared_sha256") or "") or None,
        prepared_vertices=vertices,
        prepared_faces=faces,
        source_sha256=str(gate.get("source_sha256") or "") or None,
    )
    decision["prepared_gate_accepted"] = bool(gate.get("accepted"))
    if not decision["sealed"]:
        decision["persisted"] = False
        decision["review_state"] = None
        return decision
    _persist_external_sealed_run(artifact, decision, payload)
    decision["persisted"] = True
    decision["review_state"] = "MODEL_PREDICTION"
    decision["evidence_intact"] = external_evidence_intact(
        artifact["segmentation"]["runs"][-1]["evidence"]
    )
    return decision


def _prepared_path_from_artifact(artifact: dict[str, Any]) -> str:
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    active = session.get("active") if isinstance(session.get("active"), dict) else {}
    return str(active.get("output_path") or "")


def _persist_external_sealed_run(
    artifact: dict[str, Any],
    decision: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    session = _session(artifact)
    run_id = str(payload.get("run_id"))
    prepared = str(decision.get("prepared_input_sha256") or "")
    runtime = decision.get("runtime") or {}
    instances = []
    for spec in decision.get("instance_specs") or []:
        available = bool(spec.get("confidence_available"))
        instances.append(
            candidate_instance(
                instance_id=str(spec.get("instance_id")),
                run_id=run_id,
                prepared_sha256=prepared,
                face_indices=list(spec.get("face_indices") or []),
                backend_name="toothinstancenet",
                backend_version=str(decision.get("model_version") or ""),
                model_id=str(decision.get("model_identifier") or "instseg_full.ckpt"),
                model_sha256=decision.get("checkpoint_sha256"),
                raw_model_class=spec.get("raw_model_class"),
                confidence=spec.get("confidence") if available else None,
                confidence_available=available,
                real_inference=True,
            )
        )
    evidence = decision.get("evidence") or {}
    run = {
        "run_id": run_id,
        "status": "completed",
        "blocked": False,
        "sealed": True,
        "input": {
            "source_sha256": decision.get("source_sha256"),
            "prepared_sha256": prepared,
        },
        "source_sha256": decision.get("source_sha256"),
        "prepared_sha256": prepared,
        "backend": {
            "name": "toothinstancenet",
            "version": decision.get("model_version"),
            "model_id": decision.get("model_identifier"),
            "model_sha256": decision.get("checkpoint_sha256"),
        },
        "execution_origin": "EXTERNAL_CUDA",
        "native_execution": False,
        "local_native": False,
        "real_inference": True,
        "inference_executed_by_this_process": False,
        "inference_kind": "external_cuda",
        "fixture": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "clinical_accuracy_claim": False,
        "clinically_verified": False,
        "instances": instances,
        "raw_model_output": copy.deepcopy(decision.get("raw_model_output")),
        "evidence": evidence,
        "evidence_bundle_sha256": decision.get("evidence_sha256"),
        "validation_status": "PASSED",
        "technical_validation": decision.get("validation"),
        "preprocessing": decision.get("preprocessing"),
        "reproducibility_status": decision.get("reproducibility_status"),
        "runtime": runtime,
        "reviewable": True,
        "quality_evaluation": "NOT_AVAILABLE",
        "split_available": False,
    }
    with _LOCK:
        session["generation"] = int(session.get("generation") or 0) + 1
        session.setdefault("runs", []).append(run)
        session["active_run_id"] = run_id
        session["semantic_identity"] = SEMANTIC_IDENTITY_NOT_ESTABLISHED
        session["fdi_assigned"] = False
        session["clinically_segmented"] = False
        session["clinical_accuracy_claim"] = False
        session["clinical_validation"] = False
        session["quality_evaluation"] = "NOT_AVAILABLE"
        session["split_available"] = False
        session["execution_origin"] = "EXTERNAL_CUDA"
        session["active_run"] = {
            "run_id": run_id,
            "status": "completed",
            "reviewable": True,
            "real_inference": True,
            "native_execution": False,
            "execution_origin": "EXTERNAL_CUDA",
            "prepared_sha256": prepared,
            "source_sha256": decision.get("source_sha256"),
            "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
            "inference_kind": "external_cuda",
            "validation_status": "PASSED",
            "instance_count": len(instances),
            "evidence_bundle_sha256": decision.get("evidence_sha256"),
            "requires_review": True,
            "clinically_verified": False,
            "quality_evaluation": "NOT_AVAILABLE",
        }
        session["review"] = {
            "run_id": run_id,
            "instances": copy.deepcopy(instances),
            "model_instances": copy.deepcopy(instances),
            "undo": [],
            "redo": [],
            "events": [
                {
                    "action": "external_cuda_model_prediction_sealed",
                    "detail": {"run_id": run_id, "execution_origin": "EXTERNAL_CUDA"},
                    "mutates_model_prediction": False,
                }
            ],
            "selected_instance_id": None,
            "id_counter": 0,
        }


def review_segmentation(
    artifact: dict[str, Any], action: str, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        return apply_review_action(artifact, action, payload)
    except SegmentationReviewError:
        raise


def measure_segmentation_capability(path: str | Path, work_dir: str | Path) -> dict[str, Any]:
    """Time the gate and the capability probe. Inference runs only if the probe is executable."""
    from engines.geometry.intake_inspection import inspect_source_file
    from engines.geometry.preparation_jobs import _run_inline_apply
    from engines.geometry.scan_preparation import accept_preparation

    original = Path(path)
    folder = Path(work_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source-copy.stl"
    source.write_bytes(original.read_bytes())
    artifact = inspect_source_file(
        source, case_id="fv03-measure", explicit_arch="upper", original_filename="upper.stl"
    )
    _run_inline_apply(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]},
        case_id="fv03-measure",
    )
    accept_preparation(artifact)
    before = _memory_mb()
    load_started = perf_counter()
    prepared_path = (artifact.get("preparation") or {}).get("active", {}).get("output_path")
    mesh = _load_mesh(Path(str(prepared_path)))
    load_ms = (perf_counter() - load_started) * 1000.0
    gate_started = perf_counter()
    gate = assess_segmentation_input(artifact)
    gate_ms = (perf_counter() - gate_started) * 1000.0
    cap_started = perf_counter()
    capability = detect_tin_capability(refresh=True)
    capability_ms = (perf_counter() - cap_started) * 1000.0
    inference_ms = None
    inference_attempted = False
    real_inference = False
    if capability["executable"]:
        inference_attempted = True
        infer_started = perf_counter()
        produced = ToothInstanceNetBackend().execute(
            Path(str((artifact.get("preparation") or {}).get("active", {}).get("output_path"))),
            prepared_sha256=str(gate["prepared_sha256"]),
        )
        inference_ms = (perf_counter() - infer_started) * 1000.0
        real_inference = bool(produced.get("real_inference")) and not produced.get("blocked")
    after = _memory_mb()
    return {
        "file_size": original.stat().st_size,
        "source_sha256": artifact.get("sha256"),
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "prepared_sha256": gate.get("prepared_sha256"),
        "input_gate_accepted": gate["accepted"],
        "input_gate_reasons": gate["reasons"],
        "readiness": gate.get("readiness"),
        "input_gate_ms": gate_ms,
        "prepared_load_ms": load_ms,
        "capability_detection_ms": capability_ms,
        "capability_state": capability["capability_state"],
        "availability": capability["availability"],
        "applicable_states": capability["applicable_states"],
        "executable": capability["executable"],
        "inference_attempted": inference_attempted,
        "inference_ms": inference_ms,
        "real_inference": real_inference,
        "fixture_selected": False,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "clinical_accuracy_claim": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "model_sha256": capability.get("model_sha256"),
        "input_channels": capability.get("input_channels"),
        "identify_logits": capability.get("identify_logits"),
        "fdi_encoded": capability.get("fdi_encoded"),
        "rss_before_mb": before["rss_mb"],
        "rss_after_mb": after["rss_mb"],
        "peak_rss_mb": after["peak_rss_mb"],
        "library": f"trimesh {trimesh.__version__}",
        "message": capability.get("message"),
    }
