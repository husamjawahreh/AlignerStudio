"""Small durable case repository for the local API session."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from domain.case.models import Case, CaseStatus, MeshAsset
from app.config import CASE_STORE_PATH

logger = logging.getLogger(__name__)


class InMemoryCaseStore:
    """Process-local cache persisted to a local JSON file across reloads."""

    def __init__(self, path: Path = CASE_STORE_PATH) -> None:
        self.path = path
        self._cases: dict[str, Case] = {}
        self._load()

    def add(self, case: Case) -> Case:
        self._cases[case.id] = case
        self._persist()
        return case

    def update(self, case: Case) -> Case:
        if case.id not in self._cases:
            raise KeyError(f"Case {case.id} is not present in the repository")
        self._persist()
        return case

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def list(self) -> list[Case]:
        return list(self._cases.values())

    def clear(self) -> None:
        self._cases.clear()
        self.path.unlink(missing_ok=True)

    def get_processing(self, case_id: str) -> dict | None:
        case = self._cases.get(case_id)
        return getattr(case, "processing_status", None) if case else None

    def set_processing(self, case_id: str, status: dict) -> dict:
        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(f"Case {case_id} is not present in the repository")
        setattr(case, "processing_status", status)
        self._persist()
        return status

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            records = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for record in records if isinstance(records, list) else ():
            try:
                case = Case(
                    id=record["id"],
                    patient_reference=record.get("patient_reference", ""),
                    status=CaseStatus(record.get("status", CaseStatus.CREATED.value)),
                    meshes=[
                        MeshAsset(
                            arch=mesh["arch"],
                            file_path=mesh["file_path"],
                            original_filename=mesh["original_filename"],
                            uploaded_at=datetime.fromisoformat(mesh["uploaded_at"]),
                        )
                        for mesh in record.get("meshes", [])
                    ],
                    created_at=datetime.fromisoformat(record["created_at"]),
                )
                setattr(case, "processing_status", record.get("processing_status"))
                setattr(case, "segmentation_results", record.get("segmentation_results"))
                setattr(case, "dental_intelligence", record.get("dental_intelligence"))
            except (KeyError, TypeError, ValueError):
                continue
            self._cases[case.id] = case

        recovered = False
        now = datetime.now().astimezone()
        for case in self._cases.values():
            status = getattr(case, "processing_status", None)
            if status and status.get("stage_status") == "PROCESSING":
                # Restart recovery: previous job identity is dead; retry must create a new job_id.
                # INTERRUPTED (not COMPLETED/CANCELLED) — honest durable terminal state.
                status.update(
                    {
                        "stage_status": "INTERRUPTED",
                        "error_state": True,
                        "error_code": "PROCESS_RESTARTED",
                        "user_message": "Case analysis was interrupted. Start analysis again.",
                        "technical_diagnostic": "Processing worker was interrupted during API restart.",
                        "updated_at": now.isoformat(),
                        "heartbeat_at": now.isoformat(),
                        "completed_at": now.isoformat(),
                        "result": None,
                    }
                )
                if "created_at" not in status and status.get("started_at"):
                    status["created_at"] = status["started_at"]
                # Do not leave in-flight segmentation marked as current clinical truth.
                seg = getattr(case, "segmentation_results", None)
                if isinstance(seg, dict) and seg.get("status") == "processing":
                    seg["status"] = "interrupted"
                    seg["error"] = "Segmentation interrupted by process restart"
                    setattr(case, "segmentation_results", seg)
                recovered = True
                logger.warning(
                    "PROCESSING_RECOVERED case_id=%s job_id=%s stage_status=INTERRUPTED",
                    case.id,
                    status.get("job_id"),
                )
        if recovered:
            self._persist()

    def _persist(self) -> None:
        """Atomically persist the case store (tmp + replace). Never leave half-written JSON."""
        from app.failure_injection import maybe_fail

        maybe_fail("before_case_store_persist")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "id": case.id,
                "patient_reference": case.patient_reference,
                "status": case.status.value,
                "created_at": case.created_at.isoformat(),
                "meshes": [
                    {
                        "arch": mesh.arch,
                        "file_path": mesh.file_path,
                        "original_filename": mesh.original_filename,
                        "uploaded_at": mesh.uploaded_at.isoformat(),
                    }
                    for mesh in case.meshes
                ],
                "processing_status": getattr(case, "processing_status", None),
                "segmentation_results": getattr(case, "segmentation_results", None),
                "dental_intelligence": getattr(case, "dental_intelligence", None),
            }
            for case in self._cases.values()
        ]
        payload = json.dumps(records, indent=2)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload)
        temporary.replace(self.path)


case_store = InMemoryCaseStore()
