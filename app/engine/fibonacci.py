"""Fibonacci retracement levels."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

FIB_RATIOS = {
    "0.0%": 0.0,
    "23.6%": 0.236,
    "38.2%": 0.382,
    "50.0%": 0.500,
    "61.8%": 0.618,
    "78.6%": 0.786,
    "100.0%": 1.0,
}


def compute_fibonacci(df: pd.DataFrame) -> dict:
    """Compute Fibonacci retracement from the recent swing high/low.

    Returns dict with ``levels`` (label→price) and ``trend_used``.
    """
    try:
        close = df["close"]
        lookback = min(len(df), 60)
        recent = df.tail(lookback)

        swing_high = float(recent["high"].max())
        swing_low = float(recent["low"].min())
        current = float(close.iloc[-1])
        diff = swing_high - swing_low

        high_idx = recent["high"].idxmax()
        low_idx = recent["low"].idxmin()

        if high_idx > low_idx:
            trend_used = "uptrend"
            levels = {label: round(swing_high - diff * ratio, 2) for label, ratio in FIB_RATIOS.items()}
        else:
            trend_used = "downtrend"
            levels = {label: round(swing_low + diff * ratio, 2) for label, ratio in FIB_RATIOS.items()}

        return {
            "levels": levels,
            "trend_used": trend_used,
        }
    except Exception as e:
        logger.exception("[compute_fibonacci] Failed: %s", e)
        return {"levels": {}, "trend_used": "unknown"}
