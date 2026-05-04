"""Technical indicator calculations using pandas/numpy.

All functions operate on a DataFrame with columns:
    date, open, high, low, close, volume

Returns plain dicts / values for the new LLM-optimised schema.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Moving Averages ──────────────────────────────────────────

def compute_moving_averages(df: pd.DataFrame, current_price: float) -> dict:
    """Compute 20/50/100/200 SMAs, crossover signals, and SMA positioning string."""
    try:
        close = df["close"]
        ma20 = close.rolling(window=20).mean()
        ma50 = close.rolling(window=50).mean()
        ma100 = close.rolling(window=100).mean()
        ma200 = close.rolling(window=200).mean()

        latest_ma20 = _last_valid(ma20)
        latest_ma50 = _last_valid(ma50)
        latest_ma100 = _last_valid(ma100)
        latest_ma200 = _last_valid(ma200)

        # SMA positioning string  e.g. "20>50>100>200"
        ma_pairs = [
            (20, latest_ma20),
            (50, latest_ma50),
            (100, latest_ma100),
            (200, latest_ma200),
        ]
        valid = [(label, val) for label, val in ma_pairs if val is not None]
        valid_sorted = sorted(valid, key=lambda x: x[1], reverse=True)
        sma_positioning = ">".join(str(label) for label, _ in valid_sorted) if valid_sorted else "N/A"

        # Crossover signals
        crossovers: list[str] = []
        if latest_ma50 and latest_ma200:
            if len(ma50.dropna()) >= 2 and len(ma200.dropna()) >= 2:
                prev_ma50 = float(ma50.dropna().iloc[-2])
                prev_ma200 = float(ma200.dropna().iloc[-2])
                if prev_ma50 < prev_ma200 and latest_ma50 > latest_ma200:
                    crossovers.append("Golden Cross (50>200)")
                elif prev_ma50 > prev_ma200 and latest_ma50 < latest_ma200:
                    crossovers.append("Death Cross (50<200)")
            if latest_ma50 > latest_ma100:
                crossovers.append("50 MA > 100 MA")
            if latest_ma50 > latest_ma200:
                crossovers.append("50 MA > 200 MA")

        return {
            "ma_20": _round(latest_ma20),
            "ma_50": _round(latest_ma50),
            "ma_100": _round(latest_ma100),
            "ma_200": _round(latest_ma200),
            "sma_positioning": sma_positioning,
            "crossover_signals": crossovers,
        }
    except Exception as e:
        logger.exception("[compute_moving_averages] Failed for price=%.2f: %s", current_price, e)
        return {"ma_20": None, "ma_50": None, "ma_100": None, "ma_200": None, "sma_positioning": "N/A", "crossover_signals": []}


# ── RSI (Wilder's smoothing) ────────────────────────────────

def compute_rsi(df: pd.DataFrame, period: int = 14) -> dict:
    """Relative Strength Index — returns value and categorical state."""
    try:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        value = round(float(rsi.iloc[-1]), 2)

        if value >= 70:
            state = "overbought"
        elif value >= 60:
            state = "bullish_neutral"
        elif value <= 30:
            state = "oversold"
        elif value <= 40:
            state = "bearish_neutral"
        else:
            state = "neutral"

        return {"rsi": value, "rsi_state": state}

    except Exception as e:
        logger.exception("[compute_rsi] Failed: %s", e)
        return {"rsi": 50.0, "rsi_state": "neutral"}


# ── MACD ─────────────────────────────────────────────────────

def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD line, signal line, histogram + categorical state."""
    try:
        close = df["close"]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        m = round(float(macd_line.iloc[-1]), 4)
        s = round(float(signal_line.iloc[-1]), 4)
        h = round(float(histogram.iloc[-1]), 4)

        # Determine state
        if m > s and h > 0:
            state = "bullish"
        elif m < s and h < 0:
            state = "bearish"
        elif m > s and h < 0:
            state = "bullish_weakening"
        else:
            state = "bearish_weakening"

        # Detect fresh crossover (overrides)
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            prev_m = float(macd_line.iloc[-2])
            prev_s = float(signal_line.iloc[-2])
            if prev_m <= prev_s and m > s:
                state = "bullish_crossover"
            elif prev_m >= prev_s and m < s:
                state = "bearish_crossover"

        # Momentum acceleration: compare last 3 histogram values
        accel = "flat"
        if len(histogram.dropna()) >= 3:
            h_vals = histogram.dropna().tail(3).values
            if h_vals[-1] > h_vals[-2] > h_vals[-3]:
                accel = "increasing"
            elif h_vals[-1] < h_vals[-2] < h_vals[-3]:
                accel = "decreasing"

        return {
            "macd_line": m,
            "macd_signal_line": s,
            "macd_histogram": h,
            "macd_state": state,
            "momentum_acceleration": accel,
        }

    except Exception as e:
        logger.exception("[compute_macd] Failed: %s", e)
        return {"macd_line": 0, "macd_signal_line": 0, "macd_histogram": 0, "macd_state": "neutral", "momentum_acceleration": "flat"}


# ── Bollinger Bands ──────────────────────────────────────────

def compute_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> dict:
    """Standard Bollinger Bands — returns levels + position classification."""
    try:
        close = df["close"]
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()

        upper = sma + std_dev * std
        lower = sma - std_dev * std

        u = round(float(upper.iloc[-1]), 2)
        m = round(float(sma.iloc[-1]), 2)
        l_ = round(float(lower.iloc[-1]), 2)
        bw = round((u - l_) / m * 100, 2) if m else 0.0

        price = float(close.iloc[-1])

        if price > u:
            position = "above_upper"
        elif price > m:
            position = "upper_half"
        elif price > l_:
            position = "lower_half"
        else:
            position = "below_lower"

        if bw < 6:
            regime = "low"
        elif bw > 15:
            regime = "high"
        else:
            regime = "moderate"

        return {
            "bollinger_upper": u,
            "bollinger_middle": m,
            "bollinger_lower": l_,
            "bollinger_bandwidth": bw,
            "bollinger_position": position,
            "volatility_regime": regime,
        }

    except Exception as e:
        logger.exception("[compute_bollinger_bands] Failed: %s", e)
        return {"bollinger_upper": 0, "bollinger_middle": 0, "bollinger_lower": 0, "bollinger_bandwidth": 0, "bollinger_position": "upper_half", "volatility_regime": "moderate"}


# ── ADX (Average Directional Index) ─────────────────────────

def compute_adx(df: pd.DataFrame, period: int = 14) -> dict:
    """ADX + trend strength classification."""
    try:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = _true_range(high, low, close)

        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)

        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        adx = dx.ewm(alpha=1 / period, min_periods=period).mean()

        adx_val = round(float(adx.dropna().iloc[-1]), 1) if not adx.dropna().empty else 0.0

        if adx_val >= 40:
            strength = "strong"
        elif adx_val >= 25:
            strength = "moderate"
        else:
            strength = "weak"

        return {"adx": adx_val, "trend_strength": strength}

    except Exception as e:
        logger.exception("[compute_adx] Failed: %s", e)
        return {"adx": 0.0, "trend_strength": "weak"}


# ── SuperTrend ───────────────────────────────────────────────

def compute_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> str:
    """SuperTrend indicator — returns 'buy' or 'sell'."""
    try:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        tr = _true_range(df["high"], df["low"], df["close"]).values
        atr = pd.Series(tr).ewm(span=period, adjust=False).mean().values

        hl2 = (high + low) / 2
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        supertrend = np.zeros(len(close))
        direction = np.ones(len(close))  # 1 = up (buy), -1 = down (sell)

        for i in range(1, len(close)):
            if close[i - 1] > upper_band[i - 1]:
                direction[i] = 1
            elif close[i - 1] < lower_band[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

            if direction[i] == 1:
                lower_band[i] = max(lower_band[i], lower_band[i - 1]) if direction[i - 1] == 1 else lower_band[i]
                supertrend[i] = lower_band[i]
            else:
                upper_band[i] = min(upper_band[i], upper_band[i - 1]) if direction[i - 1] == -1 else upper_band[i]
                supertrend[i] = upper_band[i]

        return "buy" if direction[-1] == 1 else "sell"

    except Exception as e:
        logger.exception("[compute_supertrend] Failed: %s", e)
        return "buy"


# ── ATR (Average True Range) ────────────────────────────────

def compute_atr(df: pd.DataFrame, period: int = 14) -> dict:
    """ATR absolute and as percentage of price."""
    try:
        tr = _true_range(df["high"], df["low"], df["close"])
        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        atr_val = round(float(atr.iloc[-1]), 2) if not atr.dropna().empty else 0.0
        price = float(df["close"].iloc[-1])
        atr_pct = round((atr_val / price) * 100, 2) if price else 0.0
        return {"atr": atr_val, "atr_percent": atr_pct}
    except Exception as e:
        logger.exception("[compute_atr] Failed: %s", e)
        return {"atr": 0.0, "atr_percent": 0.0}


# ── Higher Highs / Higher Lows ───────────────────────────────

def detect_higher_highs_lows(df: pd.DataFrame, lookback: int = 10) -> bool:
    """Return True if the last `lookback` bars show higher highs AND higher lows."""
    try:
        highs = df["high"].tail(lookback)
        lows = df["low"].tail(lookback)
        return bool(float(highs.iloc[-1]) > float(highs.iloc[0]) and float(lows.iloc[-1]) > float(lows.iloc[0]))
    except Exception as e:
        logger.exception("[detect_higher_highs_lows] Failed: %s", e)
        return False


# ── Helpers ──────────────────────────────────────────────────

def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _last_valid(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _round(val: float | None, decimals: int = 2) -> float | None:
    return round(val, decimals) if val is not None else None
