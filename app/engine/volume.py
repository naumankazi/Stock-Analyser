"""Volume analysis module — OBV, Accumulation/Distribution, VWAP, ratio."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def analyse_volume(df: pd.DataFrame) -> dict:
    """Analyse volume metrics and return a flat dict for VolumeIntelligence."""
    try:
        vol = df["volume"]
        close = df["close"]
        high = df["high"]
        low = df["low"]

        current_vol = int(vol.iloc[-1])
        avg_vol = int(vol.tail(20).mean())
        ratio = round(current_vol / avg_vol, 2) if avg_vol > 0 else 0.0

        # ── OBV trend ─────────────────────────────────────────
        obv = _compute_obv(close, vol)
        obv_sma = obv.rolling(20).mean()
        if len(obv_sma.dropna()) >= 5:
            obv_slope = float(obv_sma.dropna().iloc[-1]) - float(obv_sma.dropna().iloc[-5])
            obv_trend = "rising" if obv_slope > 0 else ("falling" if obv_slope < 0 else "flat")
        else:
            obv_trend = "flat"

        # ── Accumulation / Distribution ───────────────────────
        ad = _compute_ad(high, low, close, vol)
        ad_sma = ad.rolling(20).mean()
        if len(ad_sma.dropna()) >= 5:
            ad_slope = float(ad_sma.dropna().iloc[-1]) - float(ad_sma.dropna().iloc[-5])
            ad_label = "accumulation" if ad_slope > 0 else ("distribution" if ad_slope < 0 else "neutral")
        else:
            ad_label = "neutral"

        # ── VWAP (last 20 bars) ──────────────────────────────
        vwap_val = _compute_vwap(high, low, close, vol, window=20)

        price = float(close.iloc[-1])
        if vwap_val is not None:
            pvw = "above" if price > vwap_val else ("below" if price < vwap_val else "at")
        else:
            pvw = "at"

        # ── Volume confirmation ──────────────────────────────
        recent_price_up = float(close.iloc[-1]) > float(close.iloc[-5]) if len(close) >= 5 else True
        vol_confirms = (ratio >= 1.0 and obv_trend == "rising" and recent_price_up) or \
                       (ratio >= 1.0 and obv_trend == "falling" and not recent_price_up)

        return {
            "current_volume": current_vol,
            "avg_volume_20d": avg_vol,
            "volume_ratio": ratio,
            "obv_trend": obv_trend,
            "accumulation_distribution": ad_label,
            "vwap": round(vwap_val, 2) if vwap_val else None,
            "price_vs_vwap": pvw,
            "volume_confirmation": vol_confirms,
        }
    except Exception as e:
        logger.exception("[analyse_volume] Failed: %s", e)
        return {
            "current_volume": 0, "avg_volume_20d": 0, "volume_ratio": 0.0,
            "obv_trend": "flat", "accumulation_distribution": "neutral",
            "vwap": None, "price_vs_vwap": "at", "volume_confirmation": False,
        }


# ── Helpers ──────────────────────────────────────────────────

def _compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _compute_ad(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Accumulation/Distribution Line."""
    mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mfm = mfm.fillna(0)
    return (mfm * volume).cumsum()


def _compute_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 20) -> float | None:
    """Volume-Weighted Average Price over the last `window` bars."""
    if len(close) < window:
        return None
    typical = (high + low + close) / 3
    recent_tp = typical.tail(window)
    recent_vol = volume.tail(window)
    total_vol = recent_vol.sum()
    if total_vol == 0:
        return None
    return float((recent_tp * recent_vol).sum() / total_vol)
