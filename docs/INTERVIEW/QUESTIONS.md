# Interview Question Bank: the cross-questions you should ask me

Written for the Applied AI / senior data analytics interview lens. Each
question is one a senior interviewer would actually ask, followed by the
answer this repository can *demonstrate*, not just claim.

## Data and trust

**Q. "Your validation layer passed with WARN. Why did you proceed at all?"**
Because WARN and FAIL have different meanings by design. FAIL means the data
cannot be used (schema drift, business-key duplicates, impossible targets) and
the pipeline exits nonzero. WARN means a quantified anomaly exists but does not
make the data unusable: 52 null targets out of 4M, 61 missing calendar days,
32 corrupt discount rows. Proceeding on WARN while carrying the evidence
forward is exactly what a production team does; blocking on every anomaly is
how pipelines get ignored.

**Q. "You found discounts of minus 2094%. Why not just delete those rows?"**
Deleting is the silent-repair anti-pattern. Three reasons: (1) the deletion
itself becomes undocumented business logic; (2) 32 rows in 4M cannot move a
model, but the *precedent* of silent deletion can corrupt culture; (3) the
anomaly might recur at serving time, where a deletion rule would crash a
request. Instead the rows are flagged in the validation report with counts and
values, the threshold is explicit (WARN below 0.1% of rows, FAIL above), and
feature engineering handles them visibly.

**Q. "How do you know your missing calendar days are real gaps and not a
timezone or parsing bug?"** You don't, until you check. The gap detection runs
per warehouse on parsed dates, and the counts (Frankfurt_1: 53, Munich_1: 8)
were cross-checked against the raw files. The bug class I *did* hit later was
the opposite one: my forecasting code assumed a gapless daily grid, and the
pattern extraction broke. The fix (regularizing each series to a gapless grid
with forward-fill) is regression-tested.

## Forecasting and leakage

**Q. "Why is your split temporal? Everyone says that, prove it matters."**
Because the deployment question is always "predict the future from the past,"
so the only honest rehearsal is "predict the later past from the earlier past."
Random K-fold would let a model learn next week's promotions from next week's
rows and overstate accuracy. Additionally, my feature contract makes leakage
impossible *by arithmetic*: every lag and rolling window is shifted by at
least 28 days, so no holdout feature can read a holdout value. And there is a
test that plants a spike inside the holdout and asserts it cannot appear in
any feature.

**Q. "What did you exclude as leakage, and why?"** `total_orders` at date d
(although the competition supplies it, a real planner would not know a
warehouse's daily order total in advance: conservative choice) and
`availability` at date d (it is the *outcome* of a stockout; including it is
the classic target-adjacent leak). Price and discounts stay in, because the
retailer sets them in advance and the competition confirms they are known.

**Q. "Your model beats the baseline by 6 WMAPE points. Convince me that is
real."** Three lines of evidence: (1) identical split, identical evaluator,
identical completeness gate for all three models; (2) early stopping used an
inner validation window that never touches the holdout, so the holdout was
scored exactly once; (3) the run is seeded and reproduces to the fourth
decimal, and all numbers live in committed JSON artifacts, not in this README.

**Q. "Why WMAPE and not RMSE or MAPE?"** The demand distribution is heavily
right-tailed (p99 is enormous relative to p50), so RMSE lets a few huge
series dominate the story. MAPE explodes on near-zero actuals, of which there
are many in grocery. WMAPE (absolute error over absolute actuals) is scale
free across series and matches the competition metric; I also report the
competition-weighted variant using the official per-series weights, plus MAE
and RMSE for completeness. A single aggregate metric is exactly how teams
fool themselves.

**Q. "Zero-history products: your fallback is a global mean. Is that not
garbage?"** It is a labeled, quantified patch, not a solution: 10 series in
the holdout (195 rows) get the global mean, and the number is reported in the
results file. The honest fix is a category-level cold-start model, and it is
on the roadmap. Claiming the fallback does not exist, or hiding its rows,
would be the failure mode.

## Engineering

**Q. "Why is the risk engine deterministic? Why does that matter?"** Because a
recommendation that changes between runs destroys trust and cannot be audited.
Same risk table -> byte-identical recommendations, enforced by tests. When the
business asks "why did we order 10,405 units last Tuesday," the answer must
still exist.

**Q. "Why does the API serve frozen artifacts instead of querying the
database or training on request?"** Serving pre-computed results makes the
request path fast, cheap, and impossible to poison by a bad query. It also
means the API and the dashboard can never disagree, because they read the same
artifacts. Training in a request handler is an anti-pattern: unbounded
latency, unbounded cost, and it couples model quality to API uptime.

**Q. "Your simulator recomputes risk under scenarios. What stops it from
drifting from the risk engine?"** Two things: the scenario quantity formula is
literally imported from the recommendation engine (tested for equality), and
the identity scenario must reproduce the risk table exactly at runtime or the
run aborts. Drift between two implementations of the same business rule is a
classic production failure, so I made it a crash instead.

**Q. "LightGBM is the usual choice. Why XGBoost?"** Verified empirically:
LightGBM 4.7.0's Windows wheel lacks GPU support entirely (both device modes
fail), while XGBoost 3.2.0's wheel includes CUDA. The plan allowed "LightGBM
or another justified gradient-boosting model," the justification is in the
code and changelog, and the decision took 5 minutes to reach because I tested
before committing.

**Q. "Where is your data model weakest?"** The 61 missing calendar days and
the 52 null targets are inherited, not imputed: Frankfurt_1 and Munich_1
forecasts inherit their gaps through the regularization step, and their WMAPE
is indeed the worst (31.7% and 31.6% versus Prague_1's 23.0%). That is the
honesty loop working: the data problem shows up in the metric breakdown.

## Deployment and product

**Q. "Why did you not deploy a Streamlit app?"** Because the stakeholder
artifact should not depend on a fragile free-tier server that dies when idle.
The decision dashboard is a static file that always renders; the interactive
layer is Swagger; the terminal report is for engineers. A dead demo link is
worse than no link, and "batch vs. static vs. live" is the better answer than
"I deployed it."

**Q. "What happens when next month's data arrives?"** Re-run the pipeline
modules in order; each writes a new manifest with the git SHA and validation
summary; the API and dashboard read the refreshed artifacts on their next
deploy. The CI suite (pytest) runs on every push. No manual steps, no
notebooks to re-run cell by cell.

**Q. "What would break first in production?"** Cold-start products, honestly.
The global-mean fallback covers them but wastes the category signal. The next
breakage is data drift in the discount columns (the corrupt-value generator
already fired once), which is why the numeric-sanity check escalates by share
rather than by fixed count.
