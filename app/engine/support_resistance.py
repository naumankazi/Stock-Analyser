"""Support and resistance level detection using pivot points and price clustering."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_support_resistance(df: pd.DataFrame, n_levels: int = 3) -> dict:
    """Detect key S/R levels. Returns a dict with support_levels, resistance_levels."""
    try:
        highs = df["high"].values
        lows = df["low"].values
        close = df["close"].values
        current = float(close[-1])

        # Collect pivot highs and pivot lows (local extrema with window=5)
        pivot_prices: list[float] = []
        window = 5

        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i - window: i + window + 1]):
                pivot_prices.append(float(highs[i]))
            if lows[i] == min(lows[i - window: i + window + 1]):
                pivot_prices.append(float(lows[i]))

        if len(pivot_prices) < 4:
            all_prices = np.concatenate([highs, lows])
            pivot_prices = list(np.quantile(all_prices, [0.1, 0.25, 0.5, 0.75, 0.9]))

        pivot_arr = np.array(pivot_prices)

        support_levels: list[float] = []
        resistance_levels: list[float] = []

        sorted_pivots = np.sort(pivot_arr)
        clusters: list[list[float]] = []
        current_cluster: list[float] = [float(sorted_pivots[0])]

        for p in sorted_pivots[1:]:
            if abs(p - current_cluster[-1]) / current_cluster[-1] < 0.015:
                current_cluster.append(float(p))
            else:
                clusters.append(current_cluster)
                current_cluster = [float(p)]
        clusters.append(current_cluster)

        cluster_means = [round(np.mean(c), 2) for c in clusters if len(c) >= 1]

        for level in cluster_means:
            if level < current:
                support_levels.append(level)
            else:
                resistance_levels.append(level)

        support_levels = sorted(support_levels, reverse=True)[:n_levels]
        resistance_levels = sorted(resistance_levels)[:n_levels]

        if not support_levels:
            support_levels = [round(current * 0.95, 2), round(current * 0.90, 2)]
        if not resistance_levels:
            resistance_levels = [round(current * 1.05, 2), round(current * 1.10, 2)]

        return {
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
            "nearest_support": support_levels[0] if support_levels else None,
            "nearest_resistance": resistance_levels[0] if resistance_levels else None,
        }
    except Exception as e:
        logger.exception("[compute_support_resistance] Failed: %s", e)
        return {
            "support_levels": [], "resistance_levels": [],
            "nearest_support": None, "nearest_resistance": None,
        }
