"""Run manifest generation.

Every pipeline run writes a JSON manifest to data_quality_reports/ recording
what ran, on what inputs, with what validation outcome — so results are
traceable to a code state and a data state.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from demandops import config

PIPELINE_VERSION = "0.1.0"


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.PROJECT_ROOT,
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def file_sha256(path: Path, buf_size: int = 1 << 20) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    kind: str,
    inputs: dict[str, int],
    outputs: dict[str, str],
    validation_summary: dict,
    extra: dict | None = None,
) -> Path:
    """Write run_manifest_<timestamp>.json and return its path.

    kind: pipeline stage name (e.g. "ingestion_validation").
    inputs: table name -> row count.
    outputs: artifact name -> relative path string.
    validation_summary: {"PASS": n, "WARN": n, "FAIL": n, "overall": "..."}.
    """
    ts = datetime.now(timezone.utc)
    manifest = {
        "run_id": str(uuid.uuid4()),
        "timestamp": ts.isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "git_commit": git_commit(),
        "kind": kind,
        "inputs": inputs,
        "outputs": outputs,
        "validation": validation_summary,
    }
    if extra:
        manifest.update(extra)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / f"run_manifest_{ts.strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out
