"""Trade plan generator: entry, 3 stop-losses, 3 targets, R:R, and confidence rating.

Designed for a ~3-month positional / swing-trade strategy.
"""

from __future__ import annotations

import logging

from app.models.schemas import (
    ConfidenceRating,
    FibonacciLevels,
    IndicatorsBundle,
    MovingAverageData,
    SupportResistance,
    TimeframeTrend,
    TradePlan,
    TradePlanLevel,
    TrendDirection,
    VolumeAnalysis,
)

logger = logging.getLogger(__name__)


def generate_trade_plan(
    current_price: float,
    trends: list[TimeframeTrend],
    sr: SupportResistance,
    ma: MovingAverageData,
    indicators: IndicatorsBundle,
    volume: VolumeAnalysis,
    fib: FibonacciLevels,
) -> TradePlan:
    """Generate an actionable trade plan based on all computed indicators."""
    try:
        # Determine directional bias
        bullish_score = 0
        bearish_score = 0

        # Trend scoring
        for t in trends:
            weight = 1
            if t.timeframe == "Weekly":
                weight = 2
            elif t.timeframe == "Monthly":
                weight = 3
            if t.direction == TrendDirection.BULLISH:
                bullish_score += weight
            elif t.direction == TrendDirection.BEARISH:
                bearish_score += weight

        # RSI
        rsi_val = indicators.rsi.value
        if rsi_val < 30:
            bullish_score += 2  # Oversold
        elif rsi_val < 40:
            bullish_score += 1
        elif rsi_val > 70:
            bearish_score += 2  # Overbought
        elif rsi_val > 60:
            bearish_score += 1

        # MACD
        if indicators.macd.histogram > 0:
            bullish_score += 1
        else:
            bearish_score += 1

        # MA alignment
        if ma.ma_50 and ma.ma_200:
            if ma.ma_50 > ma.ma_200:
                bullish_score += 2
            else:
                bearish_score += 2

        # Volume
        if volume.volume_ratio > 1.2 and "bullish" in volume.interpretation.lower():
            bullish_score += 1
        elif volume.volume_ratio > 1.2 and "bearish" in volume.interpretation.lower():
            bearish_score += 1

        # Bollinger position
        bb = indicators.bollinger_bands
        if current_price < bb.lower:
            bullish_score += 1  # Oversold bounce potential
        elif current_price > bb.upper:
            bearish_score += 1  # Overextended

        is_bullish = bullish_score > bearish_score
        bias = "Long" if is_bullish else "Short"

        # Determine key levels
        nearest_support = sr.support_levels[0] if sr.support_levels else current_price * 0.95
        nearest_resistance = sr.resistance_levels[0] if sr.resistance_levels else current_price * 1.05

        # Fibonacci key level (38.2% or 61.8%)
        fib_382 = fib.levels.get("38.2%", current_price)
        fib_618 = fib.levels.get("61.8%", current_price)

        # Gather all meaningful price levels
        supports_sorted = sorted(sr.support_levels)             # ascending
        resistances_sorted = sorted(sr.resistance_levels)       # ascending

        fib_236 = fib.levels.get("23.6%", None)
        fib_382 = fib.levels.get("38.2%", None)
        fib_500 = fib.levels.get("50.0%", None)
        fib_618 = fib.levels.get("61.8%", None)
        fib_786 = fib.levels.get("78.6%", None)

        if is_bullish:
            # ── LONG setup ──────────────────────────────
            ideal_entry = round(min(current_price, nearest_support * 1.005), 2)

            # 3 Stop-losses (below supports, widening)
            sl1_price = round(nearest_support * 0.98, 2)
            sl1_desc = "Just below nearest support (tight)"

            second_support = supports_sorted[0] if len(supports_sorted) >= 2 and supports_sorted[0] < sl1_price else sl1_price * 0.97
            sl2_price = round(second_support * 0.98, 2) if second_support != sl1_price * 0.97 else round(sl1_price * 0.97, 2)
            sl2_desc = "Below secondary support (moderate)"

            sl3_price = round(ideal_entry * 0.92, 2)  # ~8% max drawdown for positional
            sl3_desc = "Max risk threshold ~8% (wide / positional)"

            # 3 Targets (above resistance, widening)
            t1_price = round(nearest_resistance, 2)
            t1_desc = "Nearest resistance"

            # T2: next resistance or fibonacci level
            above_resistances = [r for r in resistances_sorted if r > t1_price * 1.01]
            if above_resistances:
                t2_price = round(above_resistances[0], 2)
                t2_desc = "Secondary resistance"
            elif fib_618 and fib_618 > t1_price:
                t2_price = round(fib_618, 2)
                t2_desc = "Fibonacci 61.8% retracement"
            else:
                t2_price = round(t1_price * 1.05, 2)
                t2_desc = "5% above T1 (projected)"

            # T3: aggressive — fib extension or further resistance
            further_resistances = [r for r in resistances_sorted if r > t2_price * 1.01]
            if further_resistances:
                t3_price = round(further_resistances[0], 2)
                t3_desc = "Major resistance zone"
            elif fib_786 and fib_786 > t2_price:
                t3_price = round(fib_786, 2)
                t3_desc = "Fibonacci 78.6% extension"
            else:
                t3_price = round(t2_price * 1.08, 2)
                t3_desc = "8% above T2 (projected 3-month)"

        else:
            # ── SHORT setup ─────────────────────────────
            ideal_entry = round(max(current_price, nearest_resistance * 0.995), 2)

            sl1_price = round(nearest_resistance * 1.02, 2)
            sl1_desc = "Just above nearest resistance (tight)"

            second_resistance = resistances_sorted[-1] if len(resistances_sorted) >= 2 and resistances_sorted[-1] > sl1_price else sl1_price * 1.03
            sl2_price = round(second_resistance * 1.02, 2) if second_resistance != sl1_price * 1.03 else round(sl1_price * 1.03, 2)
            sl2_desc = "Above secondary resistance (moderate)"

            sl3_price = round(ideal_entry * 1.08, 2)
            sl3_desc = "Max risk threshold ~8% (wide / positional)"

            t1_price = round(nearest_support, 2)
            t1_desc = "Nearest support"

            below_supports = [s for s in supports_sorted if s < t1_price * 0.99]
            if below_supports:
                t2_price = round(below_supports[-1], 2)
                t2_desc = "Secondary support"
            elif fib_382 and fib_382 < t1_price:
                t2_price = round(fib_382, 2)
                t2_desc = "Fibonacci 38.2% retracement"
            else:
                t2_price = round(t1_price * 0.95, 2)
                t2_desc = "5% below T1 (projected)"

            further_supports = [s for s in supports_sorted if s < t2_price * 0.99]
            if further_supports:
                t3_price = round(further_supports[-1], 2)
                t3_desc = "Major support zone"
            elif fib_236 and fib_236 < t2_price:
                t3_price = round(fib_236, 2)
                t3_desc = "Fibonacci 23.6% level"
            else:
                t3_price = round(t2_price * 0.92, 2)
                t3_desc = "8% below T2 (projected 3-month)"

        # Build level objects
        stop_losses = [
            TradePlanLevel(label="SL1", price=sl1_price, description=sl1_desc),
            TradePlanLevel(label="SL2", price=sl2_price, description=sl2_desc),
            TradePlanLevel(label="SL3", price=sl3_price, description=sl3_desc),
        ]
        targets = [
            TradePlanLevel(label="T1", price=t1_price, description=t1_desc),
            TradePlanLevel(label="T2", price=t2_price, description=t2_desc),
            TradePlanLevel(label="T3", price=t3_price, description=t3_desc),
        ]

        # Risk-to-reward based on SL1 (tight) vs T2 (moderate target)
        risk = abs(ideal_entry - sl1_price)
        reward = abs(t2_price - ideal_entry)
        rr = round(reward / risk, 2) if risk > 0 else 0

        explanation_parts = [
            f"**{bias} bias** — Bullish signals: {bullish_score}, Bearish signals: {bearish_score}.",
            f"**Strategy:** 3-month positional / swing trade.",
            f"Entry near {ideal_entry:.2f}.",
            f"**Stop-losses:** SL1 {sl1_price:.2f} ({sl1_desc}), SL2 {sl2_price:.2f} ({sl2_desc}), SL3 {sl3_price:.2f} ({sl3_desc}).",
            f"**Targets:** T1 {t1_price:.2f} ({t1_desc}), T2 {t2_price:.2f} ({t2_desc}), T3 {t3_price:.2f} ({t3_desc}).",
            f"Risk:Reward (SL1→T2) = 1:{rr}.",
        ]
        if rr >= 2:
            explanation_parts.append("Favorable R:R ratio — strong setup.")
        elif rr >= 1:
            explanation_parts.append("Acceptable R:R ratio.")
        else:
            explanation_parts.append("Unfavorable R:R — consider tighter entry or wait for pullback.")

        return TradePlan(
            ideal_entry=ideal_entry,
            stop_losses=stop_losses,
            targets=targets,
            risk_reward_ratio=rr,
            position_bias=bias,
            strategy_horizon="3 months",
            explanation=" ".join(explanation_parts),
        )
    except Exception as e:
        logger.exception("[generate_trade_plan] Failed: %s", e)
        raise


def compute_confidence(
    trends: list[TimeframeTrend],
    indicators: IndicatorsBundle,
    ma: MovingAverageData,
    volume: VolumeAnalysis,
    trade_plan: TradePlan,
) -> ConfidenceRating:
    """Compute an overall confidence rating."""
    try:
        score = 0  # Range roughly -10 to +10

        # Trend alignment
        bullish_trends = sum(1 for t in trends if t.direction == TrendDirection.BULLISH)
        bearish_trends = sum(1 for t in trends if t.direction == TrendDirection.BEARISH)
        score += (bullish_trends - bearish_trends) * 1.5

        # RSI
        rsi = indicators.rsi.value
        if 40 <= rsi <= 60:
            pass  # Neutral
        elif rsi < 30:
            score += 2  # Oversold = potential buy
        elif rsi > 70:
            score -= 2  # Overbought = potential sell
        elif rsi < 40:
            score += 0.5
        else:
            score -= 0.5

        # MACD
        if indicators.macd.histogram > 0:
            score += 1
        else:
            score -= 1

        # Volume confirmation
        if volume.volume_ratio > 1.2:
            if "bullish" in volume.interpretation.lower():
                score += 1
            elif "bearish" in volume.interpretation.lower():
                score -= 1

        # MA alignment
        if ma.ma_50 and ma.ma_200:
            if ma.ma_50 > ma.ma_200:
                score += 1.5
            else:
                score -= 1.5

        # R:R quality
        if trade_plan.risk_reward_ratio >= 2.5:
            score += 1
        elif trade_plan.risk_reward_ratio < 1:
            score -= 1

        if score >= 5:
            return ConfidenceRating.STRONG_BUY
        elif score >= 2:
            return ConfidenceRating.BUY
        elif score <= -5:
            return ConfidenceRating.STRONG_SELL
        elif score <= -2:
            return ConfidenceRating.SELL
        else:
            return ConfidenceRating.NEUTRAL
    except Exception as e:
        logger.exception("[compute_confidence] Failed: %s", e)
        return ConfidenceRating.NEUTRAL
