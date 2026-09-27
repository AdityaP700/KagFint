"""Forecast metrics: WMAPE, MAE, RMSE.

All functions take aligned numpy arrays of actuals and predictions and ignore
pairs where the actual or prediction is null (counted separately by callers).
WMAPE optionally accepts per-series weights (the competition's test_weights).
"""

from __future__ import annotations

import numpy as np


def wmape(y: np.ndarray, yhat: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Weighted mean absolute percentage error: sum(w*|y-yhat|) / sum(w*|y|).

    Without weights this reduces to the standard WMAPE. If the actuals sum to
    zero the metric is undefined and returns nan — callers must surface that,
    not hide it.
    """
    y, yhat = _clean(y, yhat)
    if weights is not None:
        weights = np.asarray(weights, dtype=float)
        denom = float((weights * np.abs(y)).sum())
        if denom == 0:
            return float("nan")
        return float((weights * np.abs(y - yhat)).sum() / denom)
    denom = float(np.abs(y).sum())
    if denom == 0:
        return float("nan")
    return float(np.abs(y - yhat).sum() / denom)


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = _clean(y, yhat)
    return float(np.abs(y - yhat).mean()) if len(y) else float("nan")


def rmse(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = _clean(y, yhat)
    return float(np.sqrt(np.mean((y - yhat) ** 2))) if len(y) else float("nan")


def _clean(y: np.ndarray, yhat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    if y.shape != yhat.shape:
        raise ValueError(f"shape mismatch: actuals {y.shape} vs predictions {yhat.shape}")
    mask = ~(np.isnan(y) | np.isnan(yhat))
    return y[mask], yhat[mask]
