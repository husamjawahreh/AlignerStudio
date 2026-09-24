"""Small durable case repository for the local API session."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from domain.case.models import Case, CaseStatus, MeshAsset
from app.config import CASE_STORE_PATH


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
            except (KeyError, TypeError, ValueError):
                continue
            self._cases[case.id] = case

    def _persist(self) -> None:
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
            }
            for case in self._cases.values()
        ]
        self.path.write_text(json.dumps(records, indent=2))


case_store = InMemoryCaseStore()
