"""Chart pattern detection engine.

Uses statistical/geometric heuristics on OHLC data to detect common patterns.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_patterns(df: pd.DataFrame) -> list[str]:
    """Scan for common chart patterns in the last 60-120 bars.

    Returns a flat list of pattern name strings (e.g. ["Double Top (forming)", "Consolidation"]).
    """
    try:
        found: list[str] = []

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        _detect_head_shoulders(high, low, close, found)
        _detect_cup_and_handle(close, volume, found)
        _detect_breakout_consolidation(close, high, low, volume, found)
        _detect_double_patterns(high, low, close, found)

        if not found:
            found.append("No clear pattern")

        return found
    except Exception as e:
        logger.exception("[detect_patterns] Failed: %s", e)
        return ["No clear pattern"]


def _detect_head_shoulders(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    found: list[str],
) -> None:
    try:
        if len(high) < 60:
            return

        segment = high[-60:]
        third = len(segment) // 3
        left = segment[:third]
        middle = segment[third: 2 * third]
        right = segment[2 * third:]

        left_peak = float(np.max(left))
        head_peak = float(np.max(middle))
        right_peak = float(np.max(right))

        if head_peak > left_peak and head_peak > right_peak:
            shoulder_diff = abs(left_peak - right_peak) / max(left_peak, right_peak) * 100
            head_prominence = (head_peak - max(left_peak, right_peak)) / max(left_peak, right_peak) * 100
            if shoulder_diff < 5 and head_prominence > 2:
                found.append("Head & Shoulders (potential)")

        seg_low = low[-60:]
        left_trough = float(np.min(seg_low[:third]))
        head_trough = float(np.min(seg_low[third:2 * third]))
        right_trough = float(np.min(seg_low[2 * third:]))

        if head_trough < left_trough and head_trough < right_trough:
            shoulder_diff = abs(left_trough - right_trough) / min(left_trough, right_trough) * 100
            head_depth = (min(left_trough, right_trough) - head_trough) / min(left_trough, right_trough) * 100
            if shoulder_diff < 5 and head_depth > 2:
                found.append("Inverse Head & Shoulders (potential)")
    except Exception as e:
        logger.exception("[_detect_head_shoulders] Failed: %s", e)


def _detect_cup_and_handle(
    close: np.ndarray, volume: np.ndarray,
    found: list[str],
) -> None:
    try:
        if len(close) < 40:
            return

        segment = close[-40:]
        first_half = segment[:20]
        second_half = segment[20:]

        start = float(segment[0])
        middle_low = float(np.min(first_half[5:]))
        end = float(second_half[-1])

        dip_pct = (start - middle_low) / start * 100
        recovery_pct = abs(end - start) / start * 100

        if dip_pct > 5 and recovery_pct < 5:
            handle = segment[-5:]
            handle_dip = (float(np.max(handle)) - float(np.min(handle))) / float(np.max(handle)) * 100
            if handle_dip < dip_pct * 0.5 and handle_dip > 1:
                found.append("Cup & Handle (potential)")
    except Exception as e:
        logger.exception("[_detect_cup_and_handle] Failed: %s", e)


def _detect_breakout_consolidation(
    close: np.ndarray, high: np.ndarray, low: np.ndarray, volume: np.ndarray,
    found: list[str],
) -> None:
    try:
        if len(close) < 20:
            return

        recent_high = float(np.max(high[-20:]))
        recent_low = float(np.min(low[-20:]))
        range_pct = (recent_high - recent_low) / recent_low * 100

        current = float(close[-1])
        prev_high = float(np.max(high[-40:-20])) if len(high) >= 40 else recent_high

        if range_pct < 8:
            if current > recent_high * 0.98:
                found.append("Breakout from consolidation")
            elif current < recent_low * 1.02:
                found.append("Breakdown risk from consolidation")
            else:
                found.append("Consolidation / Range-bound")
        elif current > prev_high and len(high) >= 40:
            vol_recent = float(np.mean(volume[-5:]))
            vol_avg = float(np.mean(volume[-20:]))
            if vol_recent > vol_avg * 1.2:
                found.append("Breakout with volume confirmation")
    except Exception as e:
        logger.exception("[_detect_breakout_consolidation] Failed: %s", e)


def _detect_double_patterns(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    found: list[str],
) -> None:
    try:
        if len(high) < 30:
            return

        seg_h = high[-30:]
        first_half = seg_h[:15]
        second_half = seg_h[15:]

        peak1 = float(np.max(first_half))
        peak2 = float(np.max(second_half))
        valley = float(np.min(seg_h[10:20]))

        peak_diff = abs(peak1 - peak2) / max(peak1, peak2) * 100
        valley_depth = (max(peak1, peak2) - valley) / max(peak1, peak2) * 100

        if peak_diff < 3 and valley_depth > 3:
            current = float(close[-1])
            if current < valley * 1.02:
                found.append("Double Top (confirmed)")
            else:
                found.append("Double Top (forming)")

        seg_l = low[-30:]
        trough1 = float(np.min(seg_l[:15]))
        trough2 = float(np.min(seg_l[15:]))
        peak_between = float(np.max(seg_l[10:20]))

        trough_diff = abs(trough1 - trough2) / min(trough1, trough2) * 100
        peak_height = (peak_between - min(trough1, trough2)) / min(trough1, trough2) * 100

        if trough_diff < 3 and peak_height > 3:
            current = float(close[-1])
            if current > peak_between * 0.98:
                found.append("Double Bottom (confirmed)")
            else:
                found.append("Double Bottom (forming)")
    except Exception as e:
        logger.exception("[_detect_double_patterns] Failed: %s", e)