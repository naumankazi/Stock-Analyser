import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.engine import analyzer, swing_context
from app.models.swing import SwingAnalysis, SwingSections
from app.services import llm_enrichment, swing_analysis


def sample_bars():
    dates = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=320)
    close = 80 + np.arange(320) * .1 + np.sin(np.arange(320) / 3)
    return pd.DataFrame({"date": dates, "open": close - .2, "high": close + 1,
                         "low": close - 1, "close": close, "volume": 100000 + np.arange(320) * 100})


def sample_quote(df):
    return {"price": float(df.close.iloc[-1]), "open": float(df.open.iloc[-1]),
            "day_high": float(df.high.iloc[-1]), "day_low": float(df.low.iloc[-1]),
            "volume": 150000, "prev_close": float(df.close.iloc[-2]),
            "market_time": datetime.now(timezone.utc).timestamp(), "fetched_at": "2026-01-01T00:00:00Z",
            "fundamentals": {"returnOnEquity": .2, "debtToEquity": 40, "earningsQuarterlyGrowth": .12},
            "sector": "Unknown"}


def technical_report():
    df = sample_bars()
    with patch.object(analyzer, "resolve_ticker", return_value="TEST.NS"), \
         patch.object(analyzer, "get_analysis_cache", return_value={}), \
         patch.object(analyzer, "fetch_historical", return_value=df), \
         patch.object(analyzer, "fetch_weekly", return_value=df.iloc[::5]), \
         patch.object(analyzer, "fetch_monthly", return_value=df.iloc[::20]), \
         patch.object(analyzer, "fetch_quote", return_value=sample_quote(df)):
        return analyzer.run_analysis("TEST.NS")


def trade_context():
    return {"stock": "TEST.NS", "currency": "INR", "as_of": {"freshness_verified": True},
            "market_data": {"current_price": 100, "atr_14": 2},
            "structure_levels": [{"price": p, "kind": "support" if p < 100 else "resistance", "basis": "Observed pivot"}
                                 for p in [97, 110, 115, 120]],
            "target_candidates": [{"price": p, "basis": "Observed pivot"} for p in [110, 115, 120]],
            "stage_checks": {key: True for key in ["price_above_50_dma", "price_above_200_dma", "dma_50_above_200", "dma_50_rising", "dma_200_flat_or_rising"]}}


def ai_response():
    return {
        "decision": "ENTER NOW", "stage": "Stage 2", "stage2_score": 8, "current_setup": "Retest",
        "entry_now": True, "entry_zone_low": 99, "entry_zone_high": 101, "proposed_entry": 100,
        "confirmation_trigger": "Hold the observed retest", "technical_stop": 96, "stop_anchor": 97,
        "stop_reason": "Below the 97 swing low with 0.5 ATR buffer",
        "targets": [{"label": label, "price": price, "basis": "Observed swing high"}
                    for label, price in zip(["Target 1", "Target 2", "Extended target"], [110, 115, 120])],
        "partial_profit_plan": "Consider 40–50% at +8–10%", "trailing_method": "20 EMA below rising swing lows",
        "full_exit_trigger": "Support breakdown", "major_support": 97, "major_resistance": 110,
        "extension_risk": "NOT EXTENDED", "relative_strength": "OUTPERFORMER", "volume_quality": "Contracting retest volume",
        "setup_score": 8, "setups": [{"name": name, "status": "VALID" if name == "RETEST" else "ABSENT",
                                    "quality_score": 8, "evidence": ["Observed price structure"], "levels": {"support": 97}}
                                   for name in ["BREAKOUT", "RETEST", "FLAG", "EMA_PULLBACK"]],
        "sections": {key: ["Evidence-based explanation"] for key in SwingSections.model_fields},
        "answers": {key: "Specific price action" for key in ["entry_today", "biggest_risk", "better_setup",
                   "strength_or_chasing", "one_event_to_wait_for", "bullish_thesis_invalidation"]},
    }


class SwingEvidenceTests(unittest.TestCase):
    def test_market_metrics_window_and_missing_fundamentals(self):
        report = technical_report()
        df = sample_bars()
        # An old high must not become this year's 52-week high.
        report.chart_data[0]["high"] = 99999
        with patch.object(swing_context, "fetch_quote", return_value=sample_quote(df)), \
             patch.object(swing_context, "fetch_historical", return_value=df), \
             patch.object(swing_context, "_events", return_value={"upcoming": [], "news": [], "coverage_notes": []}):
            context = swing_context.build_swing_context(report)
        market = context["market_data"]
        self.assertLess(market["high_52w"], 99999)
        self.assertAlmostEqual(market["ema_20"], df.close.ewm(span=20, adjust=False).mean().iloc[-1], places=2)
        self.assertAlmostEqual(market["return_3m_pct"], (df.close.iloc[-1] / df.close.iloc[-64] - 1) * 100, places=2)
        self.assertEqual(market["avg_volume_20d"], float(df.volume.iloc[-21:-1].mean()))
        self.assertIsNone(context["fundamentals"]["roce_pct"])
        self.assertEqual(context["fundamentals"]["roe_pct"], 20)
        self.assertEqual(context["fundamentals"]["debt_to_equity"], .4)
        self.assertTrue(context["structure_levels"])
        json.dumps(context, allow_nan=False)

    def test_benchmarks_align_dates_and_require_full_return_window(self):
        df = sample_bars().tail(70)
        benchmark = df.iloc[:-2].copy()
        benchmark["close"] = 100
        result = swing_context.compare_benchmark(df, benchmark, "Nifty 50", "^NSEI")
        self.assertEqual(result["as_of"], str(benchmark.date.iloc[-1].date()))
        self.assertEqual(result["benchmark_3m_pct"], 0)
        self.assertAlmostEqual(result["stock_1m_pct"], (df.close.iloc[-3] / df.close.iloc[-24] - 1) * 100, places=2)
        short = swing_context.compare_benchmark(df.tail(10), benchmark, "Nifty 50", "^NSEI")
        self.assertIsNone(short["stock_1m_pct"])

    def test_stale_quotes_and_benchmark_failures_are_explicit(self):
        report = technical_report()
        quote = sample_quote(sample_bars())
        quote["market_time"] = 1
        with patch.object(swing_context, "fetch_quote", return_value=quote), \
             patch.object(swing_context, "fetch_historical", side_effect=ValueError("No benchmark")), \
             patch.object(swing_context, "_events", return_value={"upcoming": [], "news": [], "coverage_notes": []}):
            context = swing_context.build_swing_context(report)
        self.assertFalse(context["as_of"]["freshness_verified"])
        self.assertTrue(any("Nifty 50" in gap for gap in context["data_gaps"]))


class SwingRiskTests(unittest.TestCase):
    def test_risk_reward_and_personal_sizing_are_recomputed(self):
        raw = ai_response()
        raw["risk_per_share"] = 1
        raw["targets"][0]["reward_risk"] = 99
        result = swing_analysis.finalize_swing_analysis(raw, trade_context(), 100000, .75)
        self.assertEqual(result.decision, "ENTER NOW")
        self.assertEqual(result.risk_per_share, 4)
        self.assertEqual(result.stop_distance_pct, 4)
        self.assertEqual(result.targets[0].reward_risk, 2.5)
        self.assertEqual(result.position_sizing[0]["quantity"], 187)
        self.assertEqual(result.position_sizing[0]["loss_at_stop"], 748)
        self.assertFalse(result.position_sizing[0]["illustrative"])

    def test_wide_stop_is_never_tightened(self):
        raw, context = ai_response(), trade_context()
        context["structure_levels"].append({"price": 93, "kind": "support"})
        raw.update(stop_anchor=93, technical_stop=92)
        result = swing_analysis.finalize_swing_analysis(raw, context)
        self.assertEqual(result.technical_stop, 92)
        self.assertFalse(result.entry_now)
        self.assertEqual(result.stop_distance_pct, 8)
        self.assertEqual([r["risk_pct"] for r in result.position_sizing], [.5, .75, 1])

    def test_fabricated_stop_and_targets_are_withheld(self):
        raw = ai_response()
        raw.update(stop_anchor=98.123, technical_stop=97)
        raw["targets"][0]["price"] = 108
        result = swing_analysis.finalize_swing_analysis(raw, trade_context())
        self.assertIsNone(result.technical_stop)
        self.assertIsNone(result.targets[0].price)
        self.assertFalse(result.entry_now)
        self.assertEqual(result.position_sizing, [])

    def test_stale_data_weak_stage_and_extended_entry_are_blocked(self):
        for change in ["stale", "weak", "extended", "no_setup"]:
            with self.subTest(change=change):
                raw, context = ai_response(), trade_context()
                if change == "stale":
                    context["as_of"]["freshness_verified"] = False
                elif change == "weak":
                    context["stage_checks"]["dma_50_rising"] = False
                elif change == "extended":
                    raw["extension_risk"] = "SEVERELY EXTENDED / DO NOT CHASE"
                else:
                    for setup in raw["setups"]:
                        setup["status"] = "ABSENT"
                self.assertFalse(swing_analysis.finalize_swing_analysis(raw, context).entry_now)

    def test_entry_now_uses_current_price_and_capital_caps_quantity(self):
        raw = ai_response()
        raw["proposed_entry"] = 99
        result = swing_analysis.finalize_swing_analysis(raw, trade_context(), 1000, 50)
        self.assertEqual(result.proposed_entry, 100)
        self.assertEqual(result.position_sizing[0]["quantity"], 10)


class SwingIntegrationTests(unittest.TestCase):
    def test_swing_service_requests_full_prompt_schema_and_longer_timeout(self):
        with patch.object(swing_analysis, "call_llm", return_value=ai_response()) as call:
            result = asyncio.run(swing_analysis.analyze_swing(trade_context(), None, 100000, .5))
        self.assertEqual(result.risk_per_share, 4)
        self.assertIn("SECTION 14", call.call_args.kwargs["prompt_override"])
        self.assertEqual(call.call_args.kwargs["response_model"], SwingAnalysis)
        self.assertGreaterEqual(call.call_args.kwargs["timeout_seconds"], 90)

    def test_full_user_prompt_is_included(self):
        prompt = swing_analysis.build_swing_prompt(trade_context(), 100000, .5)
        self.assertIn("SECTION 14", prompt)
        self.assertIn("SECTION 13", prompt)
        self.assertIn("Do NOT choose an arbitrary percentage stop", prompt)
        self.assertIn('"trading_capital": 100000', prompt)
        self.assertIn("JSON SCHEMA", prompt)

    def test_single_analysis_api_new_schema_and_cache_isolation(self):
        base = technical_report()
        context = trade_context()
        context["market_data"]["distance_from_high_52w_pct"] = -2
        assessed = swing_analysis.finalize_swing_analysis(ai_response(), context, 100000, .5)
        app = FastAPI()
        app.include_router(router)
        with patch("app.api.routes.run_analysis", return_value=base), \
             patch("app.api.routes.build_swing_context", return_value=context), \
             patch("app.api.routes.analyze_swing", return_value=assessed) as ai:
            response = TestClient(app).post("/api/analyze", json={"ticker": "TEST.NS", "include_llm": True,
                                                                   "trading_capital": 100000, "risk_pct": .5})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["swing_analysis"]["targets"][0]["reward_risk"], 2.5)
        self.assertEqual(response.json()["swing_analysis_status"], "complete")
        self.assertEqual(len(response.json()["swing_analysis"]["sections"]), 14)
        self.assertEqual(base.swing_data, {})
        self.assertIsNone(base.swing_analysis)
        ai.assert_awaited_once()

    def test_missing_ai_keeps_market_evidence_with_visible_status(self):
        base, context = technical_report(), trade_context()
        context["market_data"]["distance_from_high_52w_pct"] = -2
        app = FastAPI()
        app.include_router(router)
        with patch("app.api.routes.run_analysis", return_value=base), \
             patch("app.api.routes.build_swing_context", return_value=context), \
             patch("app.api.routes.analyze_swing", return_value=None):
            response = TestClient(app).post("/api/analyze", json={"ticker": "TEST.NS", "include_llm": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["swing_data"])
        self.assertEqual(response.json()["swing_analysis_status"], "unavailable")

    def test_prompt_snapshot_cache_and_response_validation(self):
        calls = []
        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ai_response())}}]})
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                for prompt in ["snapshot A", "snapshot A", "snapshot B"]:
                    result = await llm_enrichment.call_llm({"stock": "TEST.NS"}, client,
                        prompt_override=prompt, response_model=SwingAnalysis, max_tokens=6500)
                    self.assertIsNotNone(result)
        with patch.object(llm_enrichment, "LLM_API_KEY", "test"), \
             patch.object(llm_enrichment, "LLM_PROVIDER", "openai"), \
             patch.object(llm_enrichment, "_llm_cache", {}):
            asyncio.run(exercise())
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["max_tokens"], 6500)


if __name__ == "__main__":
    unittest.main()
