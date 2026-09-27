# Evidence.dev dashboard (in-progress future path)

**The shipping stakeholder dashboard is `src/demandops/dashboard.py`** — a
self-contained static HTML page (no build tooling) generated from the frozen
artifacts and served at `/dashboard` by the API. That is the artifact of
record for Checkpoint 11.

This directory holds an Evidence.dev (markdown + SQL) project as the future
BI-layer path, per the industry-standard split (SQL transformations in the
warehouse's `bi` schema, a BI tool on top — `bi.risk_scores`,
`bi.recommendations`, `bi.simulation` are already loaded by
`src/demandops/bi_load.py`).

## Status

- Sources connect: `npx evidence sources` succeeds against the local
  PostgreSQL (`rohlik` + `bi` schemas).
- Static build fails inside SvelteKit prerender with the v40-era npm package
  stack on this machine. Blockers found so far were fixed one by one (peer
  deps pinned, base64-encoded options, deprecated template layout), but the
  remaining prerender failure needs a dedicated session.

## To resume

1. `npm install` in this directory (npm cache redirected to `.npm-cache/` on D:).
2. `npx evidence sources` — already working.
3. `npx evidence dev` / debug the SvelteKit prerender step.

## Files

- `sources/rohlik/connection.yaml` — source spec (name/type).
- `sources/rohlik/connection.options.yaml` — credentials, base64-encoded as
  Evidence v40 expects (git-ignored; contains real values, never commit).
- `pages/*.md` — the markdown+SQL pages (executive overview, risk, what-if).
