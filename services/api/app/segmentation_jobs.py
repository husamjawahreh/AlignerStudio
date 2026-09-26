"""Case-store binding for process-local segmentation jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engines.geometry.scan_preparation import PreparationError
from engines.segmentation.fv03_pipeline import (
    SegmentationInputError,
    SegmentationJobConflict,
    cancel_segmentation_job,
    get_segmentation_job,
    review_segmentation,
    submit_segmentation_job,
)

from app.store import case_store


def _artifact(case: Any, arch: str) -> dict[str, Any]:
    source = next(
        (item for item in case.intake_artifacts if item.get("arch", {}).get("arch") == arch),
        None,
    )
    if source is None:
        raise PreparationError(f"No intake artifact for arch '{arch}'")
    return source


def submit_case_segmentation_job(case: Any, arch: str) -> dict[str, Any]:
    artifact = _artifact(case, arch)

    def persist() -> None:
        case_store.update(case)

    return submit_segmentation_job(
        artifact,
        case_id=case.id,
        arch=arch,
        on_persist=persist,
    )


def segmentation_job_for_case(case: Any, arch: str, job_id: str) -> dict[str, Any] | None:
    live = get_segmentation_job(job_id)
    if live is not None and live.get("case_id") == case.id and live.get("arch") == arch:
        return live
    artifact = _artifact(case, arch)
    session = artifact.get("segmentation") if isinstance(artifact.get("segmentation"), dict) else {}
    for job in session.get("jobs") or []:
        if job.get("job_id") != job_id:
            continue
        if job.get("state") not in {"completed", "failed", "cancelled"}:
            job["state"] = "failed"
            job["blocked"] = True
            job["error"] = {
                "code": "JOB_LOST",
                "message": "The segmentation job is not running in this process.",
                "availability": "NOT_AVAILABLE",
            }
            job["ended_at"] = datetime.now(UTC).isoformat()
            job["real_inference"] = False
            job["fixture"] = False
            case_store.update(case)
        return job
    return None


def cancel_case_segmentation_job(case: Any, arch: str, job_id: str) -> dict[str, Any] | None:
    live = get_segmentation_job(job_id)
    if live is not None and live.get("case_id") == case.id:
        return cancel_segmentation_job(job_id)
    return segmentation_job_for_case(case, arch, job_id)


def review_case_segmentation(case: Any, arch: str, action: str, payload: dict[str, Any]) -> Any:
    artifact = _artifact(case, arch)
    review_segmentation(artifact, action, payload)
    case_store.update(case)
    return case


__all__ = [
    "SegmentationInputError",
    "SegmentationJobConflict",
    "cancel_case_segmentation_job",
    "review_case_segmentation",
    "segmentation_job_for_case",
    "submit_case_segmentation_job",
]
