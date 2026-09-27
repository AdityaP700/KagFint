# Failure Log: what broke, why, and what it taught

The pipeline's failure paths were not designed in advance; they were learned,
then made permanent. Each entry lists the failure, the root cause, the fix,
and the lesson that outlived it. This is the "failure pipeline" section an
interviewer rarely sees, written down.

## 1. Kaggle download blocked (403)

- **Failure:** authenticated API returned 403 on the competition download.
- **Diagnosis:** the competition listing showed `userHasEntered: false`: the
  rules had not been accepted on the account.
- **Fix:** one manual click ("Join Competition") on the Kaggle site.
- **Lesson:** credential errors and authorization errors look identical at the
  HTTP layer. Read the API's own error detail (it named the rules URL) before
  blaming the token.

## 2. The 57x order-count inflation

- **Failure:** warehouse demand query reported 7.1 billion orders for
  Prague_1, and 0.016 units per order. Both absurd.
- **Root cause:** `total_orders` is a warehouse-day attribute repeated across
  every product row. Summing it across product rows multiplies it by the
  product count. My first "fix" (SELECT DISTINCT on warehouse/day) made it
  worse, because the column varies slightly *within* a warehouse-day (1-4
  distinct values), so DISTINCT duplicated rows and inflated the sales join.
- **Fix:** aggregate orders to their mean per warehouse-day, compute units and
  orders at their own grains, then join the aggregates. Verified: ~8-9.4 units
  per order, matching grocery reality.
- **Lesson:** "obviously warehouse-level" columns must have their grain
  verified before summing. The check is now documented in the SQL catalog and
  visible in the query files.

## 3. The NaN-id grid (test suite green, real data broken)

- **Failure:** the seasonal-naive forecaster produced predictions for the
  unit tests but failed on real data with 2,638 holdout rows lacking any
  prediction.
- **Root cause:** regularizing each series to a daily grid used
  `reindex()`, which fills gap days with NaN in *every* column, including
  `unique_id`. The grid silently became a pile of anonymous rows. The unit
  tests missed it because their fixture histories were already gapless: the
  test data was cleaner than reality.
- **Fix:** re-stamp the series id onto reindexed rows; add a regression test
  with a mid-series gap.
- **Lesson:** unit tests fail exactly where fixtures are cleaner than
  production. When a bug survives tests, the fix is a test built from the
  *real* shape of the data, not a smarter assertion.

## 4. LightGBM has no GPU on Windows wheels

- **Failure:** `device='gpu'` and `device='cuda'` both failed with "not
  enabled in this build."
- **Decision:** rather than a risky source compile, switch to XGBoost 3.2.0,
  whose wheel ships CUDA (verified with a 3-second fit). The project plan
  allowed "LightGBM or another justified gradient-boosting model."
- **Lesson:** library capability claims are distribution-specific. Verify the
  capability on the actual machine, record the result, and keep the fallback
  plan inside the decision document.

## 5. The evaluator that kept stopping the pipeline

- **Failure:** baseline evaluation aborted three times: 2,638 rows, then
  2,401, then 195 missing predictions.
- **Root causes, in order:** missing calendar days breaking weekday-pattern
  extraction (fixed with grid regularization); cold-start series with < 7 days
  of history (fixed with a documented mean fallback); zero-history products
  whose first-ever sale fell inside the holdout (fixed with a documented
  global-mean fill and a series-grid that includes them).
- **Lesson:** the completeness gate looked like an annoyance and was actually
  the most valuable component in the file. Each abort surfaced a real data
  condition that would otherwise have silently thinned the evaluation set.

## 6. The boundary test that was wrong twice

- **Failure:** the tier-boundary test failed, then failed again after a
  "fix": first because the expected value assumed a wrong fraction, then
  because the case landed below the MEDIUM threshold by design.
- **Resolution:** the engine's thresholds were correct and intentional
  (MEDIUM requires unmet >= 5 AND fraction >= 0.05). The final test documents
  three boundary cases: exact-MEDIUM, exact-HIGH, and just-below-MEDIUM.
- **Lesson:** when a test fails, decide explicitly whether the code or the
  expectation is the defect, and write the boundary into the test name. Twice
  failing the same test while "fixing" it is a signal you are guessing.

## 7. Neon inserts at WAN speed

- **Failure:** loading 3 x 3,739 rows to Neon took minutes with no progress.
- **Root cause:** per-row INSERT round trips to a US-East server from India.
- **Fix:** psycopg3 `executemany` (pipeline mode): seconds.
- **Lesson:** the same code that is instant on localhost is a latency bug on
  the cloud. Distance is a dimension of performance testing.

## 8. A secret file reached a commit

- **Failure:** a mid-session commit captured
  `dashboard/sources/rohlik/connection.options.yaml`, which contained the
  database password (base64-encoded, which is encoding, not encryption).
- **Fix:** the file was untracked and git-ignored; with explicit
  authorization, the entire local history was rewritten with filter-branch,
  reflogs and stash refs expired, and the tree garbage-collected. Verification
  scanned every remaining blob for three secret patterns: zero hits.
- **Lesson:** secrets automation ("never commit .env") must also cover files
  created *by tools* mid-session. Evidence writes its credentials into
  `connection.options.yaml` by design; that filename is now in .gitignore.
  Post-purge verification is a scan, not a memory exercise.

## 9. The git purge subtlety worth remembering

- **Failure:** after filter-branch + reflog expire + `gc --prune=now`, the
  secret blob was still reachable.
- **Root cause:** `refs/stash` still anchored the pre-rewrite commit chain
  (a stash had been used to clean the tree before the rewrite, and popping it
  left its ref behind).
- **Fix:** `git stash clear`, expire, gc again; rescan clean.
- **Lesson:** "the commit is gone" and "the objects are unreachable" are
  different claims. Refs hide in stash, notes, and backup refs. Verify with a
  full object scan, not `git log`.
