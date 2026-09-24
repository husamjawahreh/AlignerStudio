"""Application configuration for the API service."""

from __future__ import annotations

import os
from pathlib import Path

UPLOAD_DIR = Path(os.environ.get("ALIGNERSTUDIO_UPLOAD_DIR", "./data/uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CASE_STORE_PATH = Path(
	os.environ.get("ALIGNERSTUDIO_CASE_STORE", str(UPLOAD_DIR.parent / "cases.json"))
).resolve()
