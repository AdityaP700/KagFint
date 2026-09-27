# Changelog

## 2026-09-27

### Checkpoint 01 — Initial project structure
- Initialized repository layout: `src/demandops/`, `sql/`, `tests/`, `docs/`,
  `experiments/`, `data_quality_reports/`, `data/{raw,interim,processed,external}/`.
- Added central configuration module (`src/demandops/config.py`) with
  repo-root-relative paths and `.env` loading.
- Added `.gitignore` (protects raw data, secrets, venv, caches, large artifacts),
  `.env.example`, `requirements.txt`, `README.md`, `AGENTS.md`.
- Environment noted: Python 3.11.9, NVIDIA RTX 4050 Laptop (6 GB) available for
  GPU-accelerated training; PostgreSQL 17/18 installed locally (not on PATH).
