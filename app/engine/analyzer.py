"""Main analysis orchestrator — coordinates all engine modules.

Assembles the LLM-optimized decision-layer AnalysisReport.
No narrative explanations. No trade opinions. Structured signals only.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from app.cache.memory_cache import get_analysis_cache
from app.engine.data_fetcher import fetch_historical, fetch_monthly, fetch_quote, fetch_weekly, resolve_ticker
from app.engine.fibonacci import compute_fibonacci
from app.engine.indicators import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_macd,
    compute_moving_averages,
    compute_rsi,
    compute_supertrend,
    detect_higher_highs_lows,
)
from app.engine.patterns import detect_patterns
from app.engine.support_resistance import compute_support_resistance
from app.engine.trend import analyse_trend
from app.engine.volume import analyse_volume
from app.models.schemas import (
    AnalysisReport,
    DerivedSignals,
    Meta,
    MomentumSignals,
    PriceSnapshot,
    QuantScores,
    SupportResistanceBlock,
    TradeLevelEntry,
    TradeLevels,
    TrendStructure,
    VolatilityRisk,
    VolumeIntelligence,
)

logger = logging.getLogger(__name__)


def run_analysis(ticker: str, position: str | None = None) -> AnalysisReport:
    """Run full technical analysis pipeline for a ticker."""
    ticker = ticker.upper().strip()
    ticker = resolve_ticker(ticker)

    # Check cache
    cache = get_analysis_cache()
    cache_key = f"analysis|{ticker}"
    if cache_key in cache:
        logger.info("Analysis cache hit for %s", ticker)
        return cache[cache_key]

    logger.info("Running full analysis for %s", ticker)

    try:
        # ── 1. Fetch data ────────────────────────────────────────
        daily_df = fetch_historical(ticker, period="2y", interval="1d")
        weekly_df = fetch_weekly(ticker)
        monthly_df = fetch_monthly(ticker)
        quote = fetch_quote(ticker)
    except Exception as e:
        logger.exception("[run_analysis] Data fetch failed for %s: %s", ticker, e)
        raise

    try:
        current_price = quote.get("price") or float(daily_df["close"].iloc[-1])
        currency, currency_symbol = _detect_currency(ticker)

        # ── 2. Engine computations (all return plain dicts / values) ──
        daily_trend = analyse_trend(daily_df)
        weekly_trend = analyse_trend(weekly_df)
        monthly_trend = analyse_trend(monthly_df)

        sr = compute_support_resistance(daily_df)
        ma = compute_moving_averages(daily_df, current_price)
        rsi = compute_rsi(daily_df)
        macd = compute_macd(daily_df)
        bb = compute_bollinger_bands(daily_df)
        vol = analyse_volume(daily_df)
        patterns = detect_patterns(daily_df)
        fib = compute_fibonacci(daily_df)
        adx = compute_adx(daily_df)
        supertrend_sig = compute_supertrend(daily_df)
        atr = compute_atr(daily_df)
        hh_hl = detect_higher_highs_lows(daily_df)
    except Exception as e:
        logger.exception("[run_analysis] Engine computation failed for %s: %s", ticker, e)
        raise

    try:
        # --- 52-week high/low distances ---
        high_52w = float(daily_df["high"].max())
        low_52w = float(daily_df["low"].min())
        dist_52w_high = round(((current_price - high_52w) / high_52w) * 100, 2) if high_52w else 0
        dist_52w_low = round(((current_price - low_52w) / low_52w) * 100, 2) if low_52w else 0

        # --- Meta ---
        meta = Meta(
            symbol=ticker,
            company_name=quote.get("name", ticker),
            analysis_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            timeframe="swing",
            data_window_days=len(daily_df),
            currency=currency,
            currency_symbol=currency_symbol,
        )

        # --- Price Snapshot ---
        price_snapshot = PriceSnapshot(
            current_price=current_price,
            change=quote.get("change", 0),
            change_pct=quote.get("change_pct", 0),
            open=quote.get("open", 0),
            day_high=quote.get("day_high", 0),
            day_low=quote.get("day_low", 0),
            prev_close=quote.get("prev_close", 0),
            volume=quote.get("volume", 0),
            market_cap=quote.get("market_cap"),
            distance_from_52w_high_pct=dist_52w_high,
            distance_from_52w_low_pct=dist_52w_low,
        )

        # --- Trend Structure ---
        # Primary trend (weighted: monthly=3, weekly=2, daily=1)
        ts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for t, w in zip([daily_trend, weekly_trend, monthly_trend], [1, 2, 3]):
            ts[t] += w
        primary = max(ts, key=ts.get)

        # Alignment label
        dirs = [daily_trend, weekly_trend, monthly_trend]
        if all(d == "bullish" for d in dirs):
            alignment = "bullish_all_timeframes"
        elif all(d == "bearish" for d in dirs):
            alignment = "bearish_all_timeframes"
        elif dirs[0] == dirs[1]:
            alignment = f"{dirs[0]}_daily_weekly"
        elif dirs[1] == dirs[2]:
            alignment = f"{dirs[1]}_weekly_monthly"
        else:
            alignment = "mixed"

        trend_structure = TrendStructure(
            primary_trend=primary,
            daily_trend=daily_trend,
            weekly_trend=weekly_trend,
            monthly_trend=monthly_trend,
            trend_alignment=alignment,
            sma_positioning=ma.get("sma_positioning", "N/A"),
            ma_50=ma.get("ma_50"),
            ma_100=ma.get("ma_100"),
            ma_200=ma.get("ma_200"),
            crossover_signals=ma.get("crossover_signals", []),
            adx=adx["adx"],
            trend_strength=adx["trend_strength"],
            higher_highs_lows=hh_hl,
            supertrend_signal=supertrend_sig,
        )

        # --- Momentum Signals ---
        momentum_signals = MomentumSignals(
            rsi=rsi["rsi"],
            rsi_state=rsi["rsi_state"],
            macd_line=macd["macd_line"],
            signal_line=macd["macd_signal_line"],
            histogram=macd["macd_histogram"],
            macd_signal=macd["macd_state"],
            momentum_acceleration=macd["momentum_acceleration"],
        )

        # --- Volume Intelligence ---
        vol_confirms = vol.get("volume_confirmation", False)
        volume_intelligence = VolumeIntelligence(
            current_volume=vol["current_volume"],
            avg_volume=vol["avg_volume_20d"],
            volume_ratio=vol["volume_ratio"],
            obv_trend=vol["obv_trend"],
            accumulation_distribution=vol["accumulation_distribution"],
            vwap=vol["vwap"],
            price_vs_vwap=vol["price_vs_vwap"],
            volume_confirmation=vol_confirms,
        )

        # --- Volatility & Risk ---
        if current_price > bb["bollinger_upper"]:
            bb_pos = "above_upper"
        elif current_price > bb["bollinger_middle"]:
            bb_pos = "upper_band"
        elif current_price > bb["bollinger_lower"]:
            bb_pos = "lower_band"
        else:
            bb_pos = "below_lower"

        atr_pct = atr["atr_percent"]
        if atr_pct < 1:
            vol_regime = "low"
        elif atr_pct < 2:
            vol_regime = "moderate"
        elif atr_pct < 4:
            vol_regime = "high"
        else:
            vol_regime = "extreme"

        volatility_risk = VolatilityRisk(
            atr=atr["atr"],
            atr_percent=atr_pct,
            bollinger_upper=bb["bollinger_upper"],
            bollinger_middle=bb["bollinger_middle"],
            bollinger_lower=bb["bollinger_lower"],
            bollinger_bandwidth=bb["bollinger_bandwidth"],
            bollinger_position=bb_pos,
            volatility_regime=vol_regime,
        )

        # --- Support & Resistance (enriched with Fibonacci + patterns) ---
        nearest_sup = sr.get("nearest_support")
        nearest_res = sr.get("nearest_resistance")

        price_to_res_pct = ((nearest_res - current_price) / current_price) * 100 if nearest_res and current_price else 10
        if price_to_res_pct < 2 and primary == "bullish" and vol_confirms:
            bp = "high"
        elif price_to_res_pct < 5 and primary == "bullish":
            bp = "moderate"
        else:
            bp = "low"

        support_resistance = SupportResistanceBlock(
            support_levels=sr["support_levels"],
            resistance_levels=sr["resistance_levels"],
            nearest_support=nearest_sup,
            nearest_resistance=nearest_res,
            breakout_probability=bp,
            fibonacci_levels=fib["levels"],
            fibonacci_trend=fib["trend_used"],
            patterns_detected=patterns,
        )

        # --- Derived Signals ---
        trend_confirm = primary in ("bullish", "bearish") and alignment in (
            "bullish_all_timeframes",
            "bearish_all_timeframes",
            f"{primary}_daily_weekly",
            f"{primary}_weekly_monthly",
        )
        rsi_state = rsi["rsi_state"]
        macd_state = macd["macd_state"]
        mom_confirm = (
            (primary == "bullish" and rsi_state in ("bullish_neutral", "oversold") and macd_state.startswith("bullish"))
            or (primary == "bearish" and rsi_state in ("bearish_neutral", "overbought") and macd_state.startswith("bearish"))
        )

        adx_val = adx["adx"]
        if vol_regime in ("low", "moderate"):
            risk_env = "favorable"
        elif vol_regime == "extreme":
            risk_env = "unfavorable"
        else:
            risk_env = "neutral"

        if adx_val < 20:
            trend_mat = "early_trend"
        elif adx_val < 30:
            trend_mat = "mid_trend"
        elif adx_val < 45:
            trend_mat = "late_trend"
        else:
            trend_mat = "mature_trend"

        derived_signals = DerivedSignals(
            trend_confirmation=trend_confirm,
            momentum_confirmation=mom_confirm,
            volume_confirmation=vol_confirms,
            risk_environment=risk_env,
            trend_maturity=trend_mat,
        )

        # --- Quant Scores (-3 to +3 each) ---
        t_score = 0
        for t in [daily_trend, weekly_trend, monthly_trend]:
            if t == "bullish":
                t_score += 1
            elif t == "bearish":
                t_score -= 1
        t_score = max(-3, min(3, t_score))

        m_score = 0
        if rsi["rsi"] > 50:
            m_score += 1
        elif rsi["rsi"] < 50:
            m_score -= 1
        if macd["macd_histogram"] > 0:
            m_score += 1
        else:
            m_score -= 1
        if macd["momentum_acceleration"] == "increasing":
            m_score += 1
        elif macd["momentum_acceleration"] == "decreasing":
            m_score -= 1
        m_score = max(-3, min(3, m_score))

        v_score = 0
        if vol["obv_trend"] == "rising":
            v_score += 1
        elif vol["obv_trend"] == "falling":
            v_score -= 1
        if vol["accumulation_distribution"] == "accumulation":
            v_score += 1
        elif vol["accumulation_distribution"] == "distribution":
            v_score -= 1
        if vol_confirms:
            v_score += 1
        v_score = max(-3, min(3, v_score))

        vol_score = 0
        if vol_regime == "extreme":
            vol_score = -3
        elif vol_regime == "high":
            vol_score = -1
        elif vol_regime == "low":
            vol_score = 1
        if bb["bollinger_bandwidth"] < 5:
            vol_score += 1
        vol_score = max(-3, min(3, vol_score))

        composite = t_score + m_score + v_score + vol_score

        if composite >= 6:
            market_state = "strong_bullish"
        elif composite >= 3:
            market_state = "bullish"
        elif composite >= 1:
            market_state = "mildly_bullish"
        elif composite >= -1:
            market_state = "neutral"
        elif composite >= -3:
            market_state = "mildly_bearish"
        elif composite >= -6:
            market_state = "bearish"
        else:
            market_state = "strong_bearish"

        quant_scores = QuantScores(
            trend_score=t_score,
            momentum_score=m_score,
            volume_score=v_score,
            volatility_score=vol_score,
            composite_score=composite,
            market_state=market_state,
        )

        # ── 4. Trade Levels (3–6 month swing targets & stop-losses) ──
        trade_levels = _compute_trade_levels(
            current_price=current_price,
            primary_trend=primary,
            sr=sr,
            fib=fib,
            atr_val=atr["atr"],
            atr_pct=atr["atr_percent"],
            market_state=market_state,
            trend_score=t_score,
            momentum_score=m_score,
            volume_score=v_score,
            momentum_confirmation=mom_confirm,
            volume_confirmation=vol_confirms,
            trend_maturity=trend_mat,
        )

        # ── 5. Chart data ────────────────────────────────────────
        chart_data = _build_chart_data(daily_df)

        # ── 6. Assemble report ───────────────────────────────────
        report = AnalysisReport(
            meta=meta,
            price_snapshot=price_snapshot,
            trend_structure=trend_structure,
            momentum_signals=momentum_signals,
            volume_intelligence=volume_intelligence,
            volatility_risk=volatility_risk,
            support_resistance=support_resistance,
            derived_signals=derived_signals,
            quant_scores=quant_scores,
            trade_levels=trade_levels,
            chart_data=chart_data,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        cache[cache_key] = report
        return report
    except Exception as e:
        logger.exception("[run_analysis] Report assembly failed for %s: %s", ticker, e)
        raise


# ── Trade Levels computation ─────────────────────────────

def _compute_trade_levels(
    current_price: float,
    primary_trend: str,
    sr: dict,
    fib: dict,
    atr_val: float,
    market_state: str,
    atr_pct: float = 3.0,
    trend_score: int = 0,
    momentum_score: int = 0,
    volume_score: int = 2,
    momentum_confirmation: bool = False,
    volume_confirmation: bool = False,
    trend_maturity: str = "mid_trend",
) -> TradeLevels:
    """Compute 3 targets and 3 stop-losses for a 3–6 month swing strategy.

    Uses a blend of:
    - Support / resistance levels
    - Fibonacci retracement / extension levels
    - ATR-based trailing distances

    Also computes institutional-grade probabilistic target confidence.
    """
    is_bullish = primary_trend == "bullish" or market_state in ("strong_bullish", "bullish", "mildly_bullish")

    fib_levels = fib.get("levels", {})
    fib_vals = sorted(fib_levels.values())  # ascending

    support_levels = sorted(sr.get("support_levels", []), reverse=True)   # nearest first
    resistance_levels = sorted(sr.get("resistance_levels", []))           # nearest first

    if is_bullish:
        # --- LONG bias ---
        position_bias = "Long"
        ideal_entry = round(current_price - 0.5 * atr_val, 2)

        # Targets: resistance levels + Fibonacci levels above current price
        candidates_up = sorted(set(
            [r for r in resistance_levels if r > current_price * 1.005]
            + [f for f in fib_vals if f > current_price * 1.005]
        ))
        # Ensure at least 3 targets using ATR multiples as fallback
        while len(candidates_up) < 3:
            last = candidates_up[-1] if candidates_up else current_price
            candidates_up.append(round(last + 2 * atr_val, 2))

        t1 = round(candidates_up[0], 2)
        t2 = round(candidates_up[min(1, len(candidates_up) - 1)], 2)
        t3 = round(candidates_up[min(2, len(candidates_up) - 1)], 2)

        targets = [
            TradeLevelEntry(label="T1", price=t1, basis="Nearest resistance / Fib level"),
            TradeLevelEntry(label="T2", price=t2, basis="Next resistance / Fib extension"),
            TradeLevelEntry(label="T3", price=t3, basis="Stretch target / major resistance"),
        ]

        # Stop-losses: support levels below current price
        candidates_dn = sorted(set(
            [s for s in support_levels if s < current_price * 0.995]
            + [f for f in fib_vals if f < current_price * 0.995]
        ), reverse=True)  # nearest first
        while len(candidates_dn) < 3:
            last = candidates_dn[-1] if candidates_dn else current_price
            candidates_dn.append(round(last - 2 * atr_val, 2))

        sl1 = round(candidates_dn[0], 2)
        sl2 = round(candidates_dn[min(1, len(candidates_dn) - 1)], 2)
        sl3 = round(candidates_dn[min(2, len(candidates_dn) - 1)], 2)

        stop_losses = [
            TradeLevelEntry(label="SL1", price=sl1, basis="Nearest support / Fib level"),
            TradeLevelEntry(label="SL2", price=sl2, basis="Next support zone"),
            TradeLevelEntry(label="SL3", price=sl3, basis="Max drawdown level"),
        ]

    else:
        # --- SHORT bias ---
        position_bias = "Short"
        ideal_entry = round(current_price + 0.5 * atr_val, 2)

        # Targets: support levels below current price
        candidates_dn = sorted(set(
            [s for s in support_levels if s < current_price * 0.995]
            + [f for f in fib_vals if f < current_price * 0.995]
        ), reverse=True)
        while len(candidates_dn) < 3:
            last = candidates_dn[-1] if candidates_dn else current_price
            candidates_dn.append(round(last - 2 * atr_val, 2))

        t1 = round(candidates_dn[0], 2)
        t2 = round(candidates_dn[min(1, len(candidates_dn) - 1)], 2)
        t3 = round(candidates_dn[min(2, len(candidates_dn) - 1)], 2)

        targets = [
            TradeLevelEntry(label="T1", price=t1, basis="Nearest support / Fib level"),
            TradeLevelEntry(label="T2", price=t2, basis="Next support zone"),
            TradeLevelEntry(label="T3", price=t3, basis="Stretch target / major support"),
        ]

        # Stop-losses: resistance above current price
        candidates_up = sorted(set(
            [r for r in resistance_levels if r > current_price * 1.005]
            + [f for f in fib_vals if f > current_price * 1.005]
        ))
        while len(candidates_up) < 3:
            last = candidates_up[-1] if candidates_up else current_price
            candidates_up.append(round(last + 2 * atr_val, 2))

        sl1 = round(candidates_up[0], 2)
        sl2 = round(candidates_up[min(1, len(candidates_up) - 1)], 2)
        sl3 = round(candidates_up[min(2, len(candidates_up) - 1)], 2)

        stop_losses = [
            TradeLevelEntry(label="SL1", price=sl1, basis="Nearest resistance / Fib level"),
            TradeLevelEntry(label="SL2", price=sl2, basis="Next resistance zone"),
            TradeLevelEntry(label="SL3", price=sl3, basis="Max adverse move level"),
        ]

    # Risk:Reward = (T2 − entry) / (entry − SL1) for long; inverted for short
    if is_bullish:
        risk = abs(ideal_entry - sl1)
        reward = abs(t2 - ideal_entry)
    else:
        risk = abs(sl1 - ideal_entry)
        reward = abs(ideal_entry - t2)

    rr = round(reward / risk, 2) if risk > 0 else 0.0

    # ── Probabilistic target confidence (institutional model) ──

    # Step 1 — Trend factor
    trend_factor = trend_score / 3.0 if trend_score != 0 else 0.33

    # Step 2 — Momentum factor
    momentum_factor = ((momentum_score + 1) / 3.0) * (1.1 if momentum_confirmation else 0.9)

    # Step 3 — Volume factor
    v_sc = volume_score if volume_score != 0 else 2
    volume_factor = (v_sc / 3.0) * (1.05 if volume_confirmation else 0.85)

    # Step 6 — Trend maturity multiplier
    maturity_map = {"early_trend": 1.15, "mid_trend": 1.00, "late_trend": 0.80, "mature_trend": 0.70}
    maturity_factor = maturity_map.get(trend_maturity, 1.00)

    # Step 7 — Market regime multiplier
    regime_map = {
        "strong_bullish": 1.15, "bullish": 1.10, "mildly_bullish": 1.05,
        "neutral": 1.00,
        "mildly_bearish": 0.90, "bearish": 0.85, "strong_bearish": 0.75,
    }
    regime_factor = regime_map.get(market_state, 1.00)

    safe_atr_pct = max(atr_pct / 100.0, 0.001)  # convert percentage to decimal

    for t in targets:
        # Step 4 — distance from entry
        distance_pct = abs(t.price - ideal_entry) / ideal_entry if ideal_entry else 0.0
        # Step 5 — volatility feasibility
        vol_feasibility = math.exp(-distance_pct / (2.0 * safe_atr_pct))
        # Final confidence
        raw = (
            100.0
            * abs(trend_factor)
            * abs(momentum_factor)
            * abs(volume_factor)
            * vol_feasibility
            * maturity_factor
            * regime_factor
        )
        t.confidence_percent = int(max(5, min(95, round(raw))))
        t.expected_move_multiple_atr = round(abs(t.price - ideal_entry) / atr_val, 2) if atr_val else 0.0

    return TradeLevels(
        strategy_horizon="3-6 months",
        position_bias=position_bias,
        ideal_entry=ideal_entry,
        targets=targets,
        stop_losses=stop_losses,
        risk_reward_ratio=rr,
    )


# ── Currency detection ────────────────────────────────────

_CURRENCY_MAP: dict[str, tuple[str, str]] = {
    ".NS": ("INR", "\u20b9"),
    ".BO": ("INR", "\u20b9"),
    ".L":  ("GBP", "\u00a3"),
    ".T":  ("JPY", "\u00a5"),
    ".HK": ("HKD", "HK$"),
    ".SS": ("CNY", "\u00a5"),
    ".SZ": ("CNY", "\u00a5"),
    ".TO": ("CAD", "C$"),
    ".AX": ("AUD", "A$"),
    ".DE": ("EUR", "\u20ac"),
    ".PA": ("EUR", "\u20ac"),
    ".AS": ("EUR", "\u20ac"),
}


def _detect_currency(ticker: str) -> tuple[str, str]:
    """Return (currency_code, currency_symbol) based on ticker suffix."""
    upper = ticker.upper()
    for suffix, (code, symbol) in _CURRENCY_MAP.items():
        if upper.endswith(suffix.upper()):
            return code, symbol
    return "USD", "$"


def _build_chart_data(df) -> list[dict]:
    """Convert DataFrame to lightweight chart-compatible OHLCV dicts."""
    try:
        records = []
        for _, row in df.iterrows():
            records.append({
                "time": row["date"].strftime("%Y-%m-%d"),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            })
        return records
    except Exception as e:
        logger.exception("[_build_chart_data] Failed: %s", e)
        return []
