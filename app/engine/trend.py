"""Multi-timeframe trend analysis — returns plain strings for LLM schema."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def analyse_trend(df: pd.DataFrame) -> str:
    """Determine trend direction from OHLCV data using MA slope + price position.

    Returns: ``'bullish'``, ``'bearish'``, or ``'neutral'``.
    """
    try:
        close = df["close"]

        if len(close) < 20:
            return "neutral"

        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean() if len(close) >= 50 else None

        current_price = float(close.iloc[-1])
        sma20_val = float(sma20.dropna().iloc[-1])

        # Slope of SMA20 over last 5 bars
        sma20_recent = sma20.dropna().tail(5)
        slope = 0
        if len(sma20_recent) >= 2:
            slope = (float(sma20_recent.iloc[-1]) - float(sma20_recent.iloc[0])) / float(sma20_recent.iloc[0]) * 100

        # Higher highs / higher lows (last 10 bars)
        highs = df["high"].tail(10)
        lows = df["low"].tail(10)
        hh = float(highs.iloc[-1]) > float(highs.iloc[0])
        hl = float(lows.iloc[-1]) > float(lows.iloc[0])

        bullish_signals = 0
        bearish_signals = 0

        if current_price > sma20_val:
            bullish_signals += 1
        else:
            bearish_signals += 1

        if slope > 0.5:
            bullish_signals += 1
        elif slope < -0.5:
            bearish_signals += 1

        if hh and hl:
            bullish_signals += 1
        elif not hh and not hl:
            bearish_signals += 1

        if sma50 is not None and len(sma50.dropna()) > 0:
            sma50_val = float(sma50.dropna().iloc[-1])
            if current_price > sma50_val:
                bullish_signals += 1
            else:
                bearish_signals += 1

        if bullish_signals >= 3:
            return "bullish"
        elif bearish_signals >= 3:
            return "bearish"
        return "neutral"
    except Exception as e:
        logger.exception("[analyse_trend] Failed: %s", e)
        return "neutral"
