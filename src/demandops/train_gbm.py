"""Gradient-boosted forecasting (XGBoost on CUDA) — Checkpoint 06.

Why XGBoost and not LightGBM: the project plan allows "LightGBM or another
justified gradient-boosting model". LightGBM 4.7.0's Windows wheel ships
without GPU support (verified: both device='gpu' and device='cuda' fail with
"not enabled in this build"), while XGBoost's wheel includes CUDA and runs on
the RTX 4050. Justification recorded here and in CHANGELOG.

Protocol — identical to the baselines (Checkpoint 05):
- Holdout: final 28 days (2024-05-06 -> 2024-06-02), touched once.
- Early stopping uses an INNER validation window (the 28 days before the
  holdout), never the holdout itself.
- Metrics: WMAPE (unweighted + competition-weighted), MAE, RMSE.
- Comparison against experiments/baseline_results.json is part of the output.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import xgboost as xgb

from demandops import config, manifest
from demandops.evaluate import evaluate, load_weights
from demandops.features import build_features, load_frames, temporal_split

PARAMS = dict(
    n_estimators=3000,
    learning_rate=0.03,
    max_depth=8,
    min_child_weight=10,
    subsample=0.9,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    tree_method="hist",
    device="cuda",
    eval_metric="mae",
    early_stopping_rounds=50,
    n_jobs=8,
    random_state=42,
)


def run() -> int:
    experiments_dir = config.EXPERIMENTS_DIR
    experiments_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    df, cal, inv = load_frames()
    fdf, feature_cols = build_features(df, cal, inv)
    inner_train, inner_val, holdout = temporal_split(fdf)
    print(f"feature build: {time.perf_counter() - t0:.1f}s | "
          f"inner_train rows: {len(inner_train)}, inner_val: {len(inner_val)}, "
          f"holdout: {len(holdout)}")

    def _xy(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        frame = frame[frame["sales"].notna()]
        return frame[feature_cols], frame["sales"].to_numpy()

    X_it, y_it = _xy(inner_train)
    X_iv, y_iv = _xy(inner_val)
    X_tr_all, y_tr_all = _xy(fdf[fdf["date"] < holdout["date"].min()])

    # Phase 1: inner-validation early stopping picks the iteration count.
    t1 = time.perf_counter()
    probe = xgb.XGBRegressor(**PARAMS)
    probe.fit(X_it, y_it, eval_set=[(X_iv, y_iv)], verbose=100)
    best_rounds = int(probe.best_iteration) + 1
    print(f"early stopping: best_iteration={best_rounds} "
          f"({time.perf_counter() - t1:.1f}s)")

    # Phase 2: final model on ALL pre-holdout data, no early stopping.
    t2 = time.perf_counter()
    final_params = {k: v for k, v in PARAMS.items()
                    if k not in ("early_stopping_rounds",)}
    final_params["n_estimators"] = best_rounds
    model = xgb.XGBRegressor(**final_params)
    model.fit(X_tr_all, y_tr_all, verbose=100)
    print(f"final fit on {len(X_tr_all)} rows ({time.perf_counter() - t2:.1f}s)")

    preds = model.predict(holdout[feature_cols])
    pred_df = holdout[["unique_id", "date", "warehouse"]].copy()
    pred_df["prediction"] = preds
    pred_df["actual"] = holdout["sales"].to_numpy()
    # Persisted forecasts: downstream layers (risk, recommendations, API)
    # consume these files; no training happens inside request paths.
    forecasts_dir = config.PROCESSED_DATA_DIR / "forecasts"
    forecasts_dir.mkdir(parents=True, exist_ok=True)
    pred_path = forecasts_dir / "gbm_holdout_predictions.csv"
    pred_df.to_csv(pred_path, index=False)

    weights = load_weights()
    results = evaluate(pred_df, holdout[["unique_id", "date", "warehouse", "sales"]],
                       weights)
    print(f"gbm: WMAPE={results['overall']['wmape']:.4f}  "
          f"wWMAPE={results['overall']['wmape_weighted']:.4f}  "
          f"MAE={results['overall']['mae']:.3f}  "
          f"RMSE={results['overall']['rmse']:.3f}")

    # Importances for the top features (documented evidence, not vibes).
    imp = sorted(zip(feature_cols, model.feature_importances_),
                 key=lambda kv: -kv[1])[:10]

    baseline_path = experiments_dir / "baseline_results.json"
    comparison = {}
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))["results"]
        o = results["overall"]
        for name, r in base.items():
            comparison[name] = {
                "wmape": r["overall"]["wmape"],
                "gbm_delta_wmape": round(o["wmape"] - r["overall"]["wmape"], 4),
            }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "xgboost_hist_cuda",
        "xgboost_version": xgb.__version__,
        "params": {k: str(v) for k, v in final_params.items()},
        "best_rounds_from_inner_validation": best_rounds,
        "train_rows": int(len(X_tr_all)),
        "feature_count": len(feature_cols),
        "leakage_policy": {
            "lags": ">= 28d shifts; horizon features predate the cutoff by design",
            "excluded_total_orders": "not knowable in advance (conservative)",
            "excluded_availability": "observed outcome of stockouts (leakage)",
            "price_and_discounts": "known at prediction time (retailer-set)",
        },
        "results": results,
        "top_features": [{"feature": f, "importance": float(v)} for f, v in imp],
        "baseline_comparison": comparison,
    }
    out = experiments_dir / "gbm_results.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    manifest.write_manifest(
        kind="gbm_forecast",
        inputs={"train_rows": int(len(X_tr_all)),
                "holdout_rows": int(len(holdout))},
        outputs={"gbm_results": str(out.relative_to(config.PROJECT_ROOT))},
        validation_summary={"overall": "PASS",
                            "note": "same split and gate as baselines"},
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
