"""Case-store binding for process-local preparation jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from domain.case.preparation import TERMINAL_PREPARATION_JOB_STATES
from engines.geometry.preparation_jobs import (
    cancel_preparation_job,
    get_preparation_job,
    submit_preparation_job,
)
from engines.geometry.scan_preparation import PreparationError

from app.store import case_store


def _artifact(case: Any, arch: str) -> dict[str, Any]:
    source = next(
        (item for item in case.intake_artifacts if item.get("arch", {}).get("arch") == arch),
        None,
    )
    if source is None:
        raise PreparationError(f"No intake artifact for arch '{arch}'")
    return source


def _public_stored(job: dict[str, Any]) -> dict[str, Any]:
    hidden = {"output_path"}
    return {key: value for key, value in job.items() if key not in hidden}


def submit_case_preparation_job(
    case: Any,
    arch: str,
    operation: str,
    parameters: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    artifact = _artifact(case, arch)

    def persist() -> None:
        case_store.update(case)

    return submit_preparation_job(
        artifact,
        case_id=case.id,
        arch=arch,
        operation=operation,
        parameters=parameters,
        mode=mode,
        on_persist=persist,
    )


def preparation_job_for_case(case: Any, arch: str, job_id: str) -> dict[str, Any] | None:
    live = get_preparation_job(job_id)
    if live is not None and live.get("case_id") == case.id and live.get("arch") == arch:
        return live
    artifact = _artifact(case, arch)
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    for job in session.get("jobs") or []:
        if job.get("job_id") != job_id:
            continue
        if job.get("state") not in TERMINAL_PREPARATION_JOB_STATES:
            job["state"] = "failed"
            job["error"] = {
                "code": "JOB_LOST",
                "message": "The preparation job is not running in this process.",
            }
            job["ended_at"] = datetime.now(UTC).isoformat()
            job["published"] = False
            session.setdefault("provenance_events", []).append(
                {
                    "event": "job_failed",
                    "job_id": job_id,
                    "state": "failed",
                    "error": job["error"],
                    "published": False,
                    "replaces_source": False,
                    "timestamp": job["ended_at"],
                }
            )
            case_store.update(case)
        return _public_stored(job)
    return None


def cancel_case_preparation_job(case: Any, arch: str, job_id: str) -> dict[str, Any] | None:
    live = get_preparation_job(job_id)
    if live is not None and live.get("case_id") == case.id:
        cancelled = cancel_preparation_job(job_id)
        return cancelled
    stored = preparation_job_for_case(case, arch, job_id)
    if stored is None:
        return None
    if stored.get("state") in TERMINAL_PREPARATION_JOB_STATES:
        return stored
    return stored
