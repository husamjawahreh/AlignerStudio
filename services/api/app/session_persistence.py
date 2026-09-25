"""Durable treatment-session checkpointing for API restart / browser re-fetch.

Persists full TreatmentSession objects with gzip+pickle. Contents are domain
dataclasses only (proposal, staging meshes, validation, adjuncts, intelligence).
No fabricated geometry. Job identity for processing remains in CaseStore.
"""

from __future__ import annotations

import gzip
import logging
import pickle
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)
_lock = Lock()
_FORMAT_VERSION = 1


def _session_root(root: Path | None = None) -> Path:
    if root is not None:
        return root
    from app.config import TREATMENT_SESSION_DIR

    return TREATMENT_SESSION_DIR


def session_path(case_id: str, root: Path | None = None) -> Path:
    base = _session_root(root)
    safe = "".join(character for character in case_id if character.isalnum() or character in "-_")
    if not safe:
        raise ValueError("case_id must contain a durable path segment")
    return base / f"{safe}.session.gz"


def save_session(case_id: str, session: object, root: Path | None = None) -> Path:
    """Atomically write a treatment session checkpoint."""
    path = session_path(case_id, root)
    payload = {
        "format_version": _FORMAT_VERSION,
        "case_id": case_id,
        "session": session,
    }
    encoded = gzip.compress(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL), compresslevel=6)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with _lock:
        temporary.write_bytes(encoded)
        temporary.replace(path)
    logger.info(
        "TREATMENT_SESSION_PERSISTED case_id=%s bytes=%d path=%s",
        case_id,
        path.stat().st_size,
        path,
    )
    return path


def load_session(case_id: str, root: Path | None = None) -> object | None:
    """Load a checkpoint if present and format-compatible."""
    path = session_path(case_id, root)
    if not path.is_file():
        return None
    try:
        payload = pickle.loads(gzip.decompress(path.read_bytes()))
    except (OSError, pickle.UnpicklingError, EOFError, gzip.BadGzipFile) as error:
        logger.warning(
            "TREATMENT_SESSION_LOAD_FAILED case_id=%s error=%s",
            case_id,
            error,
        )
        return None
    if not isinstance(payload, dict) or payload.get("format_version") != _FORMAT_VERSION:
        logger.warning("TREATMENT_SESSION_LOAD_REJECTED case_id=%s reason=format", case_id)
        return None
    if payload.get("case_id") != case_id:
        logger.warning("TREATMENT_SESSION_LOAD_REJECTED case_id=%s reason=case_mismatch", case_id)
        return None
    session = payload.get("session")
    if session is None:
        return None
    logger.info("TREATMENT_SESSION_RECOVERED case_id=%s path=%s", case_id, path)
    return session


def delete_session(case_id: str, root: Path | None = None) -> None:
    path = session_path(case_id, root)
    with _lock:
        path.unlink(missing_ok=True)
