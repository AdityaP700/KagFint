# AGENTS.md — operating rules for this repository

These rules govern any agent (or human) working in this repo.

## Data safety
- `data/raw/` is immutable: never modify, rename, or delete its contents.
- Validation failures must not silently pass downstream; report, quantify, explain.

## Environment
- Use the isolated `.venv/` environment only. Never install into the global Python.
- Install dependencies only when a milestone requires them; keep `requirements.txt` in sync.

## Secrets
- `.env` is local-only and git-ignored. Never print secrets, never commit them.
- `.env.example` documents variable names only.

## Git
- No force-push, no history rewriting, no `git reset --hard` without explicit permission.
- Stage explicitly (`git add src/ tests/ ...`); inspect `git status` and `git diff --cached` before committing.
- Checkpoint commits per meaningful milestone, conventional-style messages (e.g. `feat(forecasting): ...`).
- Never commit datasets, model weights, caches, `.venv/`, or large generated artifacts.

## Compute
- Heavy workloads (model training, feature building) must use GPU where supported
  (RTX 4050 Laptop, 6 GB) and keep CPU usage modest — limit `n_jobs`, avoid
  saturating all cores, and run heavy jobs sequentially, not in parallel.

## Code
- Small modules, type hints where useful, explicit configuration, meaningful logging.
- No fabricated data, metrics, or claims; measured language only.
- A feature is done only when implemented, run, tested, edge-cases considered,
  outputs inspected, and docs updated.

## Validation
- Forecasting uses chronological splits only (never random K-fold).
- Every advanced model is compared against Seasonal Naive and Moving Average baselines.
- Every pipeline run writes a run manifest to `data_quality_reports/`.
