"""In-memory case repository for Phase 1 (no database yet)."""

from __future__ import annotations

from domain.case.models import Case


class InMemoryCaseStore:
    """Process-local store of cases. Not persistent across restarts."""

    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}

    def add(self, case: Case) -> Case:
        self._cases[case.id] = case
        return case

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def list(self) -> list[Case]:
        return list(self._cases.values())


case_store = InMemoryCaseStore()
