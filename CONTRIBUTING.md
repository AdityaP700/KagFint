# Contributing to DemandOps

Collaborators are welcome. This is a portfolio-grade project, which means the
bar for changes is the same as the bar for the original build: every claim is
traceable, every failure mode is tested, and every number in the docs can be
reproduced from the repo.

## Where help is wanted most

1. **Evidence.dev BI layer**: the markdown+SQL pages and Postgres source are
   connected; the SvelteKit prerender build fails on the v40-era npm stack.
   If you have SvelteKit/Windows build experience, see `dashboard/README.md`
   for the exact state.
2. **Cold-start forecasting**: replace the documented global-mean fallback
   with a category-level or popularity-prior model (see
   `docs/VALIDATION_REPORT.md`, section 7).
3. **Backtest expansion**: rolling-origin evaluation windows beyond the single
   28-day holdout.
4. **Dashboard engineering**: turn the static page into a lightweight
   interactive view fed by `/simulation`.

## Ground rules

- **Data safety**: `data/raw/` is immutable. Never commit datasets, model
  weights, `.env`, or anything matching the ignore rules.
- **No secrets, ever**: credentials live in `.env` (local) and GitHub
  Secrets/Render dashboards. If a tool you use writes a credential-bearing
  file, git-ignore it in the same change. Check `git diff --cached` for
  secrets before every commit.
- **Tests travel with features**: new pipeline behavior needs new tests that
  cover its failure modes, not just its happy path. `pytest tests/ -q` must
  stay green.
- **Validation discipline**: if your change touches data handling, extend the
  validation gate or the tests that prove the gate works.
- **Honest docs**: claims in README/docs must name their artifact
  (`experiments/*.json`, `data_quality_reports/*.json`). Measured language
  only: "WMAPE improved 6.4 points on the holdout," never "highly accurate."

## Mechanics

1. Fork / branch from `main`.
2. Small, focused commits (conventional style: `feat(forecasting): ...`).
3. `PYTHONPATH=src pytest tests/ -q` locally before opening a PR.
4. PRs: describe the *why*; link the doc section or issue it serves.
5. For anything destructive (schema changes, data deletion, dependency
   swaps), open an issue first.

Questions on architecture start at `AGENTS.md` and
`docs/INTERVIEW/PIPELINE_WALKTHROUGH.md`.
