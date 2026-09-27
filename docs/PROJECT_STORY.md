# DemandOps — The Story So Far

*(A plain-language tour of this project: why it exists, how it fits together,
what is already built, and what is still on the road ahead. Last updated:
Checkpoint 09, 2026-09-28. This file is refreshed as milestones land.)*

---

## 1. The story: a grocery chain that hates empty shelves

Imagine you run Rohlik — a quick-grocery delivery company in Central Europe.
Customers order groceries in an app, and within a few hours a courier drops
them at the door. You have warehouses in Prague (three of them), Brno,
Budapest, Frankfurt, and Munich.

Every day you face three embarrassingly simple-sounding questions:

1. **How much of each product will people order tomorrow?** (forecasting)
2. **Which products are about to run out on the shelf?** (stockout risk)
3. **What should we actually *do* about it — and by when?** (recommendations)

Answering these well is the difference between happy customers and "sorry,
we're out of bananas." This project, **DemandOps**, is a working miniature of
the data platform a company would build to answer them — built with real data
from a real Kaggle competition run by Rohlik itself: about **4 million rows**
of daily sales across **5,390 products × warehouses** over almost four years
(Aug 2020 → Jun 2024).

It is deliberately built like production software, not like a throwaway
Kaggle notebook: every step is validated, logged, tested, and checkpointed in
git, so any claim this project makes can be traced to evidence in the repo.

---

## 2. The intended architecture: an assembly line

Think of the system as an assembly line where each station does one job and
hands its output — never garbage — to the next:

```
 real data (CSV)          →  [1] VALIDATION GATE  →  [2] PostgreSQL  →
 [3] SQL analytics        →  [4] FORECASTING      →  [5] STOCKOUT RISK →
 [6] RECOMMENDATIONS      →  [7] API              →  [8] DASHBOARD  →
 [9] WHAT-IF SIMULATOR
```

- **[1] The validation gate.** Before anything touches the data, the data has
  to prove it's trustworthy: right columns, right types, no duplicated
  records, no impossible numbers (negative sales?), no mystery gaps in the
  calendar. Problems are *reported loudly and quantified*, never quietly
  swept under the rug. A written report + run manifest is produced every run.
- **[2] PostgreSQL.** The vetted data lands in a real database with proper
  keys and relationships — the single source of truth everything else reads.
- **[3] SQL analytics.** A folder of plain SQL questions ("which warehouse
  sells the most?", "do promotions really help?") that business people could
  audit line by line.
- **[4] Forecasting.** Statistical + machine-learning models that predict
  daily demand per product per warehouse. Rule #1: simple baselines first,
  and any fancy model must *beat* them on a fair, time-ordered test — no
  peeking into the future.
- **[5] Stockout risk.** Combines forecasts with shelf-availability signals
  to flag "this will run out" situations.
- **[6] Recommendations.** Turns risk into plain instructions ("replenish
  ~N units of product X") with the assumptions printed on the label.
- **[7] API / [8] Dashboard.** The served-up answers: endpoints and screens
  so a human can actually use the machine's thinking.
- **[9] What-if simulator.** A playground: "what if we discount 20% next
  week?" — without ever rewriting history.

**The expected goal:** a portfolio-grade system where every number on the
dashboard can survive the question *"how do you know?"* — because the
validation reports, experiment logs, and honest comparisons are all in the
repository.

---

## 3. What is already built ✅

| Milestone | What it means in plain words |
|---|---|
| **Project skeleton** | Clean folder layout, safety rules (AGENTS.md), git-ignored secrets, one documented checkpoint per milestone. |
| **Real data acquired** | The actual Rohlik dataset downloaded and left untouched (read-only raw zone). 4.0M sales rows, 7 warehouses, ~4 years. |
| **Validation gate** | Every table is checked on every run. First run's findings are quantified in `docs/DATASET.md`: 52 rows with missing sales, 61 missing calendar days, 32 rows with corrupt discount values, 42 catalog-only products. Nothing was silently deleted. |
| **Database loaded** | All tables copied into PostgreSQL with row counts verified against the source files; keys and indexes in place. |
| **18 SQL analyses** | Real business questions already answered: Friday/Saturday demand peaks (~+22% vs Monday), promotions lift sales ~36%, ~8–9 units per order, which SKUs are most erratic, where stockout exposure concentrates, an estimated "lost sales" upper bound per warehouse. |
| **Baseline forecasts** | The two honest yardsticks are now measured on a strictly time-ordered test (train on the past, score on the final 28 days): "repeat last week's pattern" scores WMAPE 33.7%, "predict the recent 28-day average" scores 31.6%. |
| **Machine-learning forecasts (GPU)** | A gradient-boosted model (XGBoost on the laptop's NVIDIA GPU — chosen over LightGBM because LightGBM's Windows build has no GPU support, verified) trained on leak-safe features: only information that would genuinely be known in advance. It scores **WMAPE 25.2%** — a ~20% relative improvement over the best baseline. Every feature passed a "would we know this at prediction time?" test; demand-observed quantities like shelf availability were deliberately excluded as leakage. |
| **Testing** | 37 automated tests passing — including nasty-input tests proving the validator *fails loudly* on bad data, a leakage test proving a demand spike inside the test window cannot leak into features, and forecasting tests covering gap-filled histories and cold-start products. |

| **Stockout risk engine** | Each product-warehouse is scored for the next 28 days: forecast demand (from the ML model) against its observed shelf availability. Because the data has no inventory counts or supplier lead times, the engine says exactly what it knows — history is OBSERVED, forecasts DERIVED, and the assumption "next month's availability looks like last month's" is labeled ASSUMED, never passed off as fact. Result on real data: 1,051 high-risk, 729 medium, 1,959 low — the high-risk list is dominated by high-volume products running at 50–64% availability. |
| **Recommendation engine** | The risk list becomes plain instructions, versioned like production software: every row carries a rule ID, an engine version, a rationale containing its own actual numbers, and its labeled assumptions. 1,051 products get "replenish now" (with a labeled 10% safety margin, packed in fives), 729 go into the next ordering cycle, 1,822 need only monitoring — and 137 with missing availability telemetry get a "fix the data feed" instruction instead of a blind stock order. |
| **Testing** | 74 automated tests passing — validator fails-loudly tests, the leakage-spike test, forecasting gap/cold-start regressions, risk-engine boundary cases, and a 30-test recommendation battery covering input-contract failures, quantity invariants across magnitudes, degradation paths, and determinism. |

| **What-if simulator** | A scenario playground over the frozen forecasts: "what if demand surges 20% for the holidays and we also fix a tenth of the availability shortfall?" On real data that combination cuts projected unmet demand nearly in half (646k → 325k units) — fixing availability dominates even during a surge. Guarantees: the baseline columns are copied and verified untouched, history is never modified, and the do-nothing scenario must reproduce the risk engine's numbers exactly or the run aborts. The promotion lever reuses the project's own measured ~36% uplift, honestly labeled an ASSUMED elasticity, not a causal promise. |
| **Testing** | 87 automated tests passing — validator fails-loudly tests, the leakage-spike test, forecasting gap/cold-start regressions, risk-engine boundary cases, the 30-test recommendation battery, and 13 simulator tests covering lever math, separation guarantees, and refusal of invalid scenarios. |

## 5. What is being worked on now 🔨

- **FastAPI service (Checkpoint 10):** serving the frozen artifacts
  (`/health`, `/forecast`, `/risk`, `/recommendations`, `/simulation`) —
  request handlers never train models.

## 6. What is deliberately still ahead ⏳

- **FastAPI service** — `/health`, `/forecast`, `/risk`, `/recommendations`,
  `/simulation` endpoints serving pre-computed results (no training inside
  request handlers).
- **Streamlit dashboard** — executive overview → trends → forecast quality →
  risk → recommendations → what-if → data-quality status.
- **Final validation report** — one document with every experiment, metric,
  and known limitation, reproducible from the repo.

## 7. The operating principles, in one breath

Raw data is sacred and read-only; bad data fails loudly with evidence; simple
baselines are the judges of fancy models; time never be shuffled in
forecasting; every run leaves a manifest; secrets stay local; the laptop
stays cool (heavy training goes to the GPU, sequential not parallel); and no
claim is made louder than the evidence in this repository.
