"""Central configuration: paths and environment.

All paths are resolved from the repository root (the parent of src/), so no
machine-specific absolute paths are hard-coded. Secrets come from .env via
python-dotenv and are never printed or committed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "data_quality_reports"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
MODELS_DIR = PROJECT_ROOT / "models"

for _dir in (RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR, EXTERNAL_DATA_DIR, REPORTS_DIR, MODELS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def database_url() -> str | None:
    """Return DATABASE_URL from the environment, or None when unset.

    Callers must treat None as an explicit, reported condition — never
    substitute a fabricated default connection string.
    """
    return os.getenv("DATABASE_URL") or None
