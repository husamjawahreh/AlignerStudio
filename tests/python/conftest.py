"""Isolate durable API files during the Python test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_durable_paths(tmp_path_factory, monkeypatch):
    sessions = tmp_path_factory.mktemp("treatment_sessions")
    cases = tmp_path_factory.mktemp("cases") / "cases.json"
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(sessions))
    monkeypatch.setenv("ALIGNERSTUDIO_CASE_STORE", str(cases))
    import app.config as config
    from app.store import case_store
    from app.treatment_sessions import treatment_sessions

    config.TREATMENT_SESSION_DIR = Path(sessions)
    config.CASE_STORE_PATH = Path(cases)
    case_store.path = Path(cases)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()
