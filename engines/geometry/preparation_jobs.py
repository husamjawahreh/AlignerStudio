"""Process-local preparation jobs.

Orientation, trim, cleanup, and the quality recheck run off the request thread.
There is no external queue. A partial mesh is never published.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

import trimesh

from domain.case.preparation import (
    ACTIVE_PREPARATION_JOB_STATES,
    TERMINAL_PREPARATION_JOB_STATES,
    PreparationJobState,
    operation_algorithm,
    preparation_cache_key,
)
from engines.geometry.scan_preparation import (
    PreparationCancelled,
    PreparationError,
    PreparationStale,
    _geometry_operations,
    _session,
    apply_operation,
    preview_operation,
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alignerstudio-preparation")
_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_cache: dict[str, dict[str, Any]] = {}
_checkpoint_hook: Callable[[str], None] | None = None

_BACKGROUND_OPERATIONS = frozenset({"orient", "trim", "cleanup"})


class PreparationJobConflict(PreparationError):
    """Another preparation job is already active for this arch."""


def set_preparation_checkpoint_hook(hook: Callable[[str], None] | None) -> None:
    """Test hook. Called at each deterministic stage before the cancel check."""
    global _checkpoint_hook
    with _lock:
        _checkpoint_hook = hook


def reset_preparation_jobs() -> None:
    """Drop in-memory jobs and cache entries. Does not delete case files."""
    global _checkpoint_hook
    with _lock:
        _checkpoint_hook = None
        for job in _jobs.values():
            job["cancel_requested"] = True
        _jobs.clear()
        _cache.clear()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _public_job(job: dict[str, Any], *, duplicate: bool = False) -> dict[str, Any]:
    started = job.get("started_at")
    ended = job.get("ended_at")
    duration_ms = None
    if started:
        end = datetime.fromisoformat(ended) if ended else datetime.now(UTC)
        duration_ms = max(
            0.0, (end - datetime.fromisoformat(started)).total_seconds() * 1000.0
        )
    completed_preview = job.get("mode") == "preview" and job.get("state") == "completed"
    preview = job.get("result") if completed_preview else None
    return {
        "job_id": job["job_id"],
        "case_id": job["case_id"],
        "arch": job.get("arch"),
        "source_artifact_hash": job["source_artifact_hash"],
        "operation": job["operation"],
        "parameters": job["parameters"],
        "mode": job["mode"],
        "state": job["state"],
        "queued_at": job.get("queued_at"),
        "started_at": started,
        "ended_at": ended,
        "duration_ms": duration_ms,
        "progress": job.get("progress"),
        "progress_stage": job.get("progress_stage"),
        "output_artifact_hash": job.get("output_artifact_hash"),
        "error": job.get("error"),
        "cache_hit": bool(job.get("cache_hit")),
        "reused": bool(job.get("reused")),
        "duplicate": duplicate or bool(job.get("duplicate")),
        "result": preview,
        "clinical_axes": False,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "occlusion_established": False,
    }


def _remember(job: dict[str, Any]) -> None:
    artifact = job["_artifact"]
    session = _session(artifact)
    stored = _public_job(job)
    if job.get("output_path"):
        stored["output_path"] = job["output_path"]
    stored["published"] = bool(job.get("published"))
    jobs = session.setdefault("jobs", [])
    for index, item in enumerate(jobs):
        if item.get("job_id") == job["job_id"]:
            jobs[index] = stored
            return
    jobs.append(stored)


def _persist(job: dict[str, Any]) -> None:
    callback = job.get("_on_persist")
    if callback is not None:
        callback()


def _provenance(job: dict[str, Any], *, published: bool) -> None:
    session = _session(job["_artifact"])
    session.setdefault("provenance_events", []).append(
        {
            "event": f"job_{job['state']}",
            "job_id": job["job_id"],
            "operation": job["operation"],
            "parameters": job["parameters"],
            "source_sha256": job["source_artifact_hash"],
            "output_sha256": job.get("output_artifact_hash"),
            "state": job["state"],
            "error": job.get("error"),
            "reused": bool(job.get("reused")),
            "cache_hit": bool(job.get("cache_hit")),
            "cache_key": job.get("cache_key"),
            "published": published,
            "replaces_source": False,
            "clinical_axes": False,
            "truth_state": job.get("truth_state"),
            "timestamp": _now(),
        }
    )


def _finish(job: dict[str, Any], state: str, error: dict[str, Any] | None = None) -> None:
    job["state"] = state
    job["ended_at"] = _now()
    job["error"] = error
    job["published"] = state == PreparationJobState.COMPLETED.value and job.get("mode") == "apply"
    if state != PreparationJobState.COMPLETED.value:
        job["output_artifact_hash"] = None
        job["published"] = False
    if state == PreparationJobState.COMPLETED.value:
        job["progress"] = 1.0
    _provenance(job, published=bool(job["published"]))
    _remember(job)
    _persist(job)


def _checkpoint(job: dict[str, Any], stage: str, progress: float) -> None:
    hook = _checkpoint_hook
    if hook is not None:
        hook(stage)
    with _lock:
        if job["state"] in TERMINAL_PREPARATION_JOB_STATES:
            raise PreparationCancelled("Preparation was cancelled before a mesh was published.")
        if job.get("cancel_requested"):
            _finish(
                job,
                PreparationJobState.CANCELLED.value,
                {
                    "code": "CANCELLED",
                    "message": "Preparation was cancelled before a mesh was published.",
                },
            )
            raise PreparationCancelled("Preparation was cancelled before a mesh was published.")
        job["state"] = PreparationJobState.RUNNING.value
        job["progress_stage"] = stage
        job["progress"] = progress
        if job.get("started_at") is None:
            job["started_at"] = _now()
        _remember(job)
        _persist(job)


def _cache_get(key: str, source_sha256: str, *, need_bytes: bool) -> dict[str, Any] | None:
    item = _cache.get(key)
    if item is None or item.get("source_sha256") != source_sha256:
        return None
    if need_bytes:
        payload = item.get("output_bytes")
        if not isinstance(payload, (bytes, bytearray)):
            return None
        if hashlib.sha256(payload).hexdigest() != item.get("output_sha256"):
            return None
    return item


def _cache_put(key: str, entry: dict[str, Any]) -> None:
    if entry.get("source_sha256") is None:
        return
    payload = entry.get("output_bytes")
    if isinstance(payload, (bytes, bytearray)):
        entry = dict(entry)
        entry["output_bytes"] = bytes(payload)
        entry["output_sha256"] = hashlib.sha256(entry["output_bytes"]).hexdigest()
    _cache[key] = entry


def _identity(
    artifact: dict[str, Any], operation: str, parameters: dict[str, Any]
) -> tuple[str, str, list[dict[str, Any]]]:
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    source_sha = str((session or {}).get("source_sha256") or artifact.get("sha256") or "")
    prefix = [
        {"operation": item.get("operation"), "parameters": item.get("replay_parameters")}
        for item in (session or {}).get("operations") or []
    ]
    algorithm = operation_algorithm(operation, parameters)
    key = preparation_cache_key(
        source_sha256=source_sha,
        operation=operation,
        parameters=parameters,
        algorithm=algorithm,
        algorithm_version=trimesh.__version__,
        replay_prefix=prefix,
    )
    return source_sha, key, prefix


def submit_preparation_job(
    artifact: dict[str, Any],
    *,
    case_id: str,
    arch: str,
    operation: str,
    parameters: dict[str, Any],
    mode: str,
    on_persist: Callable[[], None] | None = None,
    schedule: bool = True,
) -> dict[str, Any]:
    """Queue a job and return before the mesh work starts."""
    if operation not in _BACKGROUND_OPERATIONS:
        raise PreparationError("Background preparation supports orient, trim, and cleanup.")
    if mode not in {"preview", "apply"}:
        raise PreparationError("Preparation job mode must be preview or apply.")
    source_sha, cache_key, _prefix = _identity(artifact, operation, parameters)
    with _lock:
        active = [
            job
            for job in _jobs.values()
            if job["case_id"] == case_id
            and job.get("arch") == arch
            and job["state"] in ACTIVE_PREPARATION_JOB_STATES
        ]
        equivalent = next(
            (
                job
                for job in active
                if job["cache_key"] == cache_key and job["mode"] == mode
            ),
            None,
        )
        if equivalent is not None:
            return _public_job(equivalent, duplicate=True)
        if active:
            raise PreparationJobConflict("A preparation job is already active for this arch.")
        job_id = str(uuid4())
        session = _session(artifact)
        job: dict[str, Any] = {
            "job_id": job_id,
            "case_id": case_id,
            "arch": arch,
            "source_artifact_hash": source_sha,
            "operation": operation,
            "parameters": parameters,
            "mode": mode,
            "state": PreparationJobState.QUEUED.value,
            "queued_at": _now(),
            "started_at": None,
            "ended_at": None,
            "progress": 0.0,
            "progress_stage": None,
            "output_artifact_hash": None,
            "output_path": None,
            "error": None,
            "cache_key": cache_key,
            "cache_hit": False,
            "reused": False,
            "published": False,
            "expected_commit_generation": int(session.get("commit_generation") or 0),
            "algorithm": operation_algorithm(operation, parameters),
            "algorithm_version": trimesh.__version__,
            "cancel_requested": False,
            "result": None,
            "truth_state": None,
            "_artifact": artifact,
            "_on_persist": on_persist,
        }
        _jobs[job_id] = job
        _remember(job)
        _persist(job)
        public = _public_job(job)
    if schedule:
        _executor.submit(run_preparation_job, job_id)
    return public


def get_preparation_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        return _public_job(job)


def cancel_preparation_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        if job["state"] in TERMINAL_PREPARATION_JOB_STATES:
            return _public_job(job)
        job["cancel_requested"] = True
        if job["state"] == PreparationJobState.QUEUED.value:
            _finish(
                job,
                PreparationJobState.CANCELLED.value,
                {"code": "CANCELLED", "message": "Preparation was cancelled before it started."},
            )
        return _public_job(job)


def wait_preparation_job(job_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = perf_counter() + timeout_s
    while perf_counter() < deadline:
        current = get_preparation_job(job_id)
        if current is None:
            raise PreparationError("Preparation job is missing.")
        if current["state"] in TERMINAL_PREPARATION_JOB_STATES:
            return current
        sleep(0.02)
    raise PreparationError("Preparation job did not finish.")


def run_preparation_job(job_id: str) -> dict[str, Any] | None:
    """Execute one queued job. Safe to call from the worker thread or a test."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job["state"] != PreparationJobState.QUEUED.value:
            return None if job is None else _public_job(job)
        if job.get("cancel_requested"):
            _finish(
                job,
                PreparationJobState.CANCELLED.value,
                {"code": "CANCELLED", "message": "Preparation was cancelled before it started."},
            )
            return _public_job(job)
        job["state"] = PreparationJobState.RUNNING.value
        job["started_at"] = _now()
        job["progress"] = 0.05
        job["progress_stage"] = "load"
        _remember(job)
        _persist(job)
    try:
        _execute(job)
    except PreparationCancelled:
        with _lock:
            if not job.get("_finished"):
                _finish(
                    job,
                    PreparationJobState.CANCELLED.value,
                    {
                        "code": "CANCELLED",
                        "message": "Preparation was cancelled before a mesh was published.",
                    },
                )
    except PreparationStale as exc:
        _fail(job, "STALE_JOB", str(exc))
    except PreparationError as exc:
        _fail(job, "PREPARATION_REFUSED", str(exc))
    except Exception as exc:  # noqa: BLE001 - a job failure must stay on the job record
        _fail(job, "PREPARATION_FAILED", exc.__class__.__name__)
    return get_preparation_job(job_id)


def _fail(job: dict[str, Any], code: str, message: str) -> None:
    with _lock:
        if job["state"] in TERMINAL_PREPARATION_JOB_STATES:
            return
        _finish(job, PreparationJobState.FAILED.value, {"code": code, "message": message})


def _execute(job: dict[str, Any]) -> None:
    artifact = job["_artifact"]
    _checkpoint(job, "load", 0.15)
    source_sha = str(artifact.get("sha256") or "")
    if source_sha != job["source_artifact_hash"]:
        raise PreparationStale("The source hash no longer matches this job.")
    session = _session(artifact)
    if int(session.get("commit_generation") or 0) != int(job["expected_commit_generation"]):
        raise PreparationStale("A newer preparation was committed. This result was not published.")
    cached = _cache_get(
        job["cache_key"],
        job["source_artifact_hash"],
        need_bytes=job["mode"] == "apply",
    )
    if cached is None and job["mode"] == "preview":
        cached = _cache_get(job["cache_key"], job["source_artifact_hash"], need_bytes=False)
        if cached is not None and cached.get("preview") is None:
            cached = None
    if cached is not None:
        _checkpoint(job, "cache_lookup", 0.55)
        job["cache_hit"] = True
        job["reused"] = True
        job["truth_state"] = (cached.get("meta") or {}).get("truth_state")
        if job["mode"] == "preview":
            job["result"] = dict(cached["preview"])
            job["result"]["reused"] = True
            job["result"]["cache_hit"] = True
            job["output_artifact_hash"] = cached.get("output_sha256")
            with _lock:
                _finish(job, PreparationJobState.COMPLETED.value, None)
            return
        _checkpoint(job, "commit", 0.92)
        apply_operation(
            artifact,
            job["operation"],
            job["parameters"],
            job_id=job["job_id"],
            expected_generation=job["expected_commit_generation"],
            cancel_check=lambda: bool(job.get("cancel_requested")),
            reused={
                "source_sha256": cached["source_sha256"],
                "output_bytes": cached["output_bytes"],
                "output_sha256": cached["output_sha256"],
                "quality_comparison": cached["quality_comparison"],
                "meta": cached["meta"],
                "cache_key": job["cache_key"],
            },
        )
        _complete_apply(job, artifact)
        return
    if job["mode"] == "preview":
        result = preview_operation(
            artifact,
            job["operation"],
            job["parameters"],
            cancel_check=lambda: bool(job.get("cancel_requested")),
            progress=lambda stage, value: _checkpoint(job, stage, value),
        )
        result = dict(result)
        result["reused"] = False
        result["cache_hit"] = False
        job["result"] = result
        job["truth_state"] = result.get("truth_state")
        job["output_artifact_hash"] = result.get("output_sha256")
        _cache_put(
            job["cache_key"],
            {
                "source_sha256": job["source_artifact_hash"],
                "preview": {key: value for key, value in result.items() if key != "timings_ms"},
                "output_sha256": result.get("output_sha256"),
                "meta": {"truth_state": result.get("truth_state"), "clinical_axes": False},
            },
        )
        with _lock:
            _finish(job, PreparationJobState.COMPLETED.value, None)
        return
    apply_operation(
        artifact,
        job["operation"],
        job["parameters"],
        job_id=job["job_id"],
        expected_generation=job["expected_commit_generation"],
        cancel_check=lambda: bool(job.get("cancel_requested")),
        progress=lambda stage, value: _checkpoint(job, stage, value),
    )
    _store_apply_cache(job, artifact)
    _complete_apply(job, artifact)


def _store_apply_cache(job: dict[str, Any], artifact: dict[str, Any]) -> None:
    session = _session(artifact)
    active = session.get("active") or {}
    path = active.get("output_path")
    if not path:
        return
    payload = Path(path).read_bytes()
    operation = session["operations"][-1]
    version = session["versions"][-1]
    preview = {
        "preview": True,
        "persisted": False,
        "operation": job["operation"],
        "truth_state": operation.get("truth_state"),
        "clinical_axes": False,
        "parameters": version.get("parameters"),
        "limitations": version.get("limitations"),
        "quality_comparison": session.get("quality_comparison"),
        "source_sha256": job["source_artifact_hash"],
        "output_sha256": active.get("output_sha256"),
        "reused": False,
        "cache_hit": False,
        "fdi_assigned": False,
        "occlusion_established": False,
        "clinically_segmented": False,
    }
    _cache_put(
        job["cache_key"],
        {
            "source_sha256": job["source_artifact_hash"],
            "output_bytes": payload,
            "output_sha256": active.get("output_sha256"),
            "quality_comparison": session.get("quality_comparison"),
            "preview": preview,
            "meta": {
                "algorithm": operation.get("algorithm"),
                "truth_state": operation.get("truth_state"),
                "clinical_axes": False,
                "parameters": version.get("parameters"),
                "limitations": version.get("limitations"),
            },
        },
    )


def _complete_apply(job: dict[str, Any], artifact: dict[str, Any]) -> None:
    session = _session(artifact)
    active = session.get("active") or {}
    job["output_artifact_hash"] = active.get("output_sha256")
    job["output_path"] = active.get("output_path")
    job["truth_state"] = (session.get("operations") or [{}])[-1].get("truth_state")
    job["published"] = True
    with _lock:
        if job["state"] in TERMINAL_PREPARATION_JOB_STATES:
            return
        _finish(job, PreparationJobState.COMPLETED.value, None)


def preparation_cache_size() -> int:
    return len(_cache)


def replay_prefix_for(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else None
    return _geometry_operations(session) if session else []


def _memory_mb() -> dict[str, float]:
    """Current and peak RSS from the kernel. Not filesystem timestamps."""
    current = 0.0
    peak = 0.0
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            current = int(line.split()[1]) / 1024.0
        elif line.startswith("VmHWM:"):
            peak = int(line.split()[1]) / 1024.0
    return {"rss_mb": current, "peak_rss_mb": peak}


def measure_preparation_reliability(path: str | Path, work_dir: str | Path) -> dict[str, Any]:
    """Time the production job path on a copy. The original file is only read."""
    from engines.geometry.intake_inspection import inspect_source_file
    from engines.geometry.scan_preparation import _load_mesh, _quality_summary, _sha256_file

    original = Path(path)
    original_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    original_size = original.stat().st_size
    folder = Path(work_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source-copy.stl"
    source.write_bytes(original.read_bytes())
    artifact = inspect_source_file(
        source, case_id="fv02-2-measure", explicit_arch="upper", original_filename="upper.stl"
    )
    mesh = _load_mesh(source)
    bounds = mesh.bounds
    span = bounds[1] - bounds[0]
    minimum = (bounds[0] + span * 0.02).tolist()
    maximum = (bounds[1] - span * 0.02).tolist()
    orient_parameters = {
        "method": "user_transform",
        "rotation_deg": [0, 0, 90],
        "translation": [0, 0, 0],
    }
    trim_parameters = {"region": "axis_aligned_box", "minimum": minimum, "maximum": maximum}
    cleanup_parameters = {
        "merge_duplicate_vertices": True,
        "remove_degenerate_faces": True,
        "remove_duplicate_faces": True,
        "remove_invalid_components": False,
    }
    memory_before = _memory_mb()

    def timed(action: Callable[[], Any]) -> tuple[Any, float, float]:
        started = perf_counter()
        value = action()
        elapsed = (perf_counter() - started) * 1000.0
        return value, elapsed, _memory_mb()["rss_mb"]

    orient, orient_ms, orient_rss = timed(
        lambda: preview_operation(artifact, "orient", orient_parameters)
    )
    trim, trim_ms, trim_rss = timed(lambda: preview_operation(artifact, "trim", trim_parameters))
    cleanup, cleanup_ms, cleanup_rss = timed(
        lambda: preview_operation(artifact, "cleanup", cleanup_parameters)
    )
    recheck, recheck_ms, recheck_rss = timed(
        lambda: _quality_summary(_load_mesh(source), kind="stl_binary")
    )
    commit_job, commit_ms, commit_rss = timed(
        lambda: _run_inline_apply(artifact, "orient", orient_parameters, case_id="fv02-2-measure")
    )
    cached_artifact = inspect_source_file(
        source, case_id="fv02-2-cache", explicit_arch="upper", original_filename="upper.stl"
    )
    cache_job, cache_ms, cache_rss = timed(
        lambda: _run_inline_apply(
            cached_artifact, "orient", orient_parameters, case_id="fv02-2-cache"
        )
    )
    if _sha256_file(source) != artifact["sha256"]:
        raise PreparationError("Measurement changed the source copy.")
    if hashlib.sha256(original.read_bytes()).hexdigest() != original_sha:
        raise PreparationError("Measurement changed the original file.")
    memory_after = _memory_mb()
    return {
        "file_size": original_size,
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "source_sha256": artifact["sha256"],
        "source_unchanged": True,
        "orientation_preview_ms": orient_ms,
        "trim_preview_ms": trim_ms,
        "cleanup_preview_ms": cleanup_ms,
        "commit_ms": commit_ms,
        "quality_recheck_ms": recheck_ms,
        "cache_hit_ms": cache_ms,
        "cache_hit": bool(cache_job.get("cache_hit")),
        "commit_state": commit_job.get("state"),
        "quality_recheck_included_in_operations": True,
        "self_intersection": "not_run",
        "prepared_readiness": artifact["preparation"]["readiness"],
        "cache_readiness": cached_artifact["preparation"]["readiness"],
        "clinical_axes": False,
        "fdi_assigned": False,
        "clinically_ready": False,
        "rss_before_mb": memory_before["rss_mb"],
        "rss_after_mb": memory_after["rss_mb"],
        "peak_rss_mb": memory_after["peak_rss_mb"],
        "step_rss_mb": {
            "orientation_preview": orient_rss,
            "trim_preview": trim_rss,
            "cleanup_preview": cleanup_rss,
            "quality_recheck": recheck_rss,
            "commit": commit_rss,
            "cache_hit": cache_rss,
        },
        "preview_output_hashes": {
            "orient": orient.get("output_sha256"),
            "trim": trim.get("output_sha256"),
            "cleanup": cleanup.get("output_sha256"),
        },
        "recheck_face_count": recheck.get("face_count"),
        "copies_avoided": [
            "Source quality reuses intake inspection instead of a second load and weld.",
            "Orientation, trim, and cleanup mutate the working mesh instead of cloning it.",
        ],
        "copies_retained": [
            "The prepared STL topology recheck still welds one copy. STL has no shared vertices.",
            "Publishing still allocates the STL byte buffer.",
        ],
        "library": f"trimesh {trimesh.__version__}",
        "manifold3d_used": False,
        "meshlib_used": False,
    }


def _run_inline_apply(
    artifact: dict[str, Any], operation: str, parameters: dict[str, Any], *, case_id: str
) -> dict[str, Any]:
    queued = submit_preparation_job(
        artifact,
        case_id=case_id,
        arch="upper",
        operation=operation,
        parameters=parameters,
        mode="apply",
        schedule=False,
    )
    finished = run_preparation_job(queued["job_id"])
    if finished is None:
        raise PreparationError("Inline preparation job did not run.")
    return finished

