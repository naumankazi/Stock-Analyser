"""Offline regression tests: python -m unittest discover -s tests -v."""

import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.engine import query_engine as qe, screener
from app.models.schemas import ScreenerRequest


class MonthlyVolumeTests(unittest.TestCase):
    def prepare(self, volumes):
        df = pd.DataFrame({"close": 100., "open": 99., "high": 101.,
                           "low": 98., "volume": volumes})
        with patch.object(qe, "get_analysis_cache", return_value={}), \
             patch.object(qe, "resolve_ticker", return_value="TEST.NS"), \
             patch.object(qe, "fetch_historical", return_value=df), \
             patch.object(qe, "compute_rsi", return_value={"rsi": 55}), \
             patch.object(qe, "compute_moving_averages", return_value={}), \
             patch.object(qe.yf, "Ticker") as ticker:
            ticker.return_value.info = {}
            return qe.prepare_stock_data("TEST.NS", raise_errors=True)

    def test_latest_21_sessions_and_filter(self):
        data = self.prepare([10000] * 4 + list(range(1, 22)))
        self.assertEqual(data["volume_1m_avg"], 11)
        self.assertEqual(data["volume_1w_avg"], 19)
        for alias in ["Volume 1 month average", "Volume 1month average",
                      "VOLUME   1 Month Average"]:
            with self.subTest(alias=alias), self.assertNoLogs(qe.logger, level="WARNING"):
                self.assertEqual(qe.ExpressionEvaluator(data).evaluate(alias), 11)
                conditions, errors = qe.QueryParser().parse(f"Volume > 1.5 * {alias}")
                self.assertFalse(errors)
                self.assertTrue(qe.evaluate_all_conditions(data, conditions))
                data["volume"] = 10
                self.assertFalse(qe.evaluate_all_conditions(data, conditions))
                data["volume"] = 21
        self.assertIn("Volume 1 month average", qe.get_available_fields()["Volume"])

    def test_incomplete_month_is_missing_not_shorter_average(self):
        for volumes in [[100] * 20, [100] * 20 + [None]]:
            data = self.prepare(volumes)
            self.assertNotIn("volume_1m_avg", data)
            conditions, _ = qe.QueryParser().parse("Volume 1 month average > 0")
            self.assertFalse(qe.evaluate_all_conditions(data, conditions))

    def test_fetch_error_can_be_reported_without_breaking_optional_callers(self):
        with patch.object(qe, "get_analysis_cache", return_value={}), \
             patch.object(qe, "resolve_ticker", return_value="KRMAYURVED.NS"), \
             patch.object(qe, "fetch_historical", side_effect=ValueError("No data returned")):
            self.assertIsNone(qe.prepare_stock_data("KRMAYURVED.NS"))
            with self.assertRaisesRegex(ValueError, "No data returned"):
                qe.prepare_stock_data("KRMAYURVED.NS", raise_errors=True)


class FailureReportingTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @staticmethod
    def fetch(ticker, **kwargs):
        if ticker == "MATCH.NS":
            return {"volume": 200., "volume_1m_avg": 100., "close": 100.}
        if ticker == "NONMATCH.NS":
            return {"volume": 50., "volume_1m_avg": 100., "close": 100.}
        raise ValueError(f"No data returned for ticker '{ticker}'")

    def test_single_and_multi_query_api_keep_all_failures(self):
        failed = [f"FAILED{i}.NS" for i in range(25)] + ["KRMAYURVED.NS"]
        stocks = ["MATCH.NS", "NONMATCH.NS"] + failed
        query = "Volume > Volume 1 month average"
        for mode in [{"query": query}, {"queries": [query, "Volume > 100"]}]:
            with self.subTest(mode=mode), \
                 patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
                 patch("app.api.routes.prepare_stock_data", side_effect=self.fetch):
                response = self.client.post("/api/screen", json={
                    **mode, "custom_tickers": ",".join(stocks), "top_n": 1,
                })
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["matched_tickers"], ["MATCH.NS"])
                self.assertEqual(data["total_screened"], 2)
                self.assertEqual(set(data["failed_tickers"]), set(failed))
                self.assertIn("No data returned", data["failure_reasons"]["KRMAYURVED.NS"])

    def test_all_failed_api_with_ai_enabled(self):
        for mode in [{"query": "Volume > 0"}, {"queries": ["Volume > 0"]}]:
            with self.subTest(mode=mode), patch.object(qe, "prepare_stock_data", side_effect=self.fetch):
                response = self.client.post("/api/screen", json={
                    **mode, "custom_tickers": "KRMAYURVED.NS", "include_llm": True,
                })
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["matched_tickers"], [])
                self.assertEqual(data["failed_tickers"], ["KRMAYURVED.NS"])

    def test_detail_fetch_failure_is_not_silently_dropped(self):
        with patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
             patch("app.api.routes.prepare_stock_data", side_effect=RuntimeError("Provider timeout")):
            response = self.client.post("/api/screen", json={
                "query": "Volume > 0", "custom_tickers": "MATCH.NS",
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["failure_reasons"], {"MATCH.NS": "Provider timeout"})

    def test_empty_universe(self):
        self.assertEqual(qe.run_query("Volume > 0", stocks=[]).failure_reasons, {})
        self.assertEqual(qe.run_multiple_queries(["Volume > 0"], stocks=[]).ordered, [])

    def test_screener_no_fundamentals_and_non_404_error(self):
        for kwargs in [{"return_value": None}, {"side_effect": RuntimeError("Provider timeout")}]:
            with self.subTest(kwargs=kwargs), \
                 patch.object(screener, "get_analysis_cache", return_value={}), \
                 patch.object(screener, "_fetch_fundamentals", **kwargs):
                response = self.client.post("/api/screen", json={"custom_tickers": "KRMAYURVED.NS"})
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["stocks"], [])
                self.assertEqual(data["failed_tickers"], ["KRMAYURVED.NS"])
                self.assertTrue(data["failure_reasons"]["KRMAYURVED.NS"])

    def test_screener_partial_technical_failure(self):
        with patch.object(screener, "get_analysis_cache", return_value={}), \
             patch.object(screener, "_fetch_fundamentals", return_value={"price": 100.}), \
             patch.object(screener, "fetch_historical", side_effect=ValueError("No history")):
            report = screener.run_screener(ScreenerRequest(custom_tickers="PARTIAL.NS"))
            self.assertEqual(len(report.stocks), 1)
            self.assertEqual(report.failed_tickers, ["PARTIAL.NS"])
            self.assertIn("neutral defaults used", report.failure_reasons["PARTIAL.NS"])


class SourceListAITests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @staticmethod
    def fetch(ticker, **kwargs):
        if ticker == "FAILED.NS":
            raise ValueError("No data returned")
        return {"ticker": ticker, "close": 100., "volume": 50. if ticker.startswith("FIRST") else 200.}

    @staticmethod
    async def enrich(stocks, duplicates=None):
        return [{"stock": s["ticker"], "metrics": s, "tags": [], "llm": None} for s in stocks]

    def test_ai_uses_source_order_and_requested_count_in_both_modes(self):
        # FIRST fails the filter; other stocks match both queries. Max Results is 1.
        for mode in [{"query": "Volume > 100"}, {"queries": ["Volume > 100", "Volume > 150"]}]:
            with self.subTest(mode=mode), \
                 patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
                 patch("app.api.routes.prepare_stock_data", side_effect=self.fetch), \
                 patch("app.api.routes.enrich_stocks", side_effect=self.enrich) as enrich:
                response = self.client.post("/api/screen", json={
                    **mode, "custom_tickers": "FIRST,SECOND,THIRD,FOURTH", "top_n": 1,
                    "include_llm": True, "llm_max_stocks": 2,
                })
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["matched_tickers"], ["SECOND.NS"])
                self.assertEqual([s["ticker"] for s in data["stock_details"]], ["SECOND.NS"])
                self.assertEqual([s["stock"] for s in data["llm_enriched"]], ["FIRST.NS", "SECOND.NS"])
                self.assertEqual(len(enrich.call_args.args[0]), 2)

    def test_zero_matches_still_analyzes_source_stocks_and_resolves_urls_once(self):
        for mode in [{"query": "Volume > 1000"}, {"queries": ["Volume > 1000", "Volume < 0"]}]:
            with self.subTest(mode=mode), \
                 patch("app.api.routes.get_stock_universe", return_value=(
                     ["FIRST.NS", "SECOND.NS", "THIRD.NS"], "Imported stocks")) as universe, \
                 patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
                 patch("app.api.routes.prepare_stock_data", side_effect=self.fetch), \
                 patch("app.api.routes.enrich_stocks", side_effect=self.enrich):
                response = self.client.post("/api/screen", json={
                    **mode, "screener_urls": ["https://www.screener.in/screens/71/"],
                    "include_llm": True, "llm_max_stocks": 2,
                })
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["matched_tickers"], [])
                self.assertEqual(data["stock_details"], [])
                self.assertEqual([s["stock"] for s in data["llm_enriched"]], ["FIRST.NS", "SECOND.NS"])
                universe.assert_called_once()

    def test_unavailable_and_duplicate_symbols_do_not_consume_ai_slots(self):
        def details(ticker, **kwargs):
            if ticker == "SECOND.NS":
                raise ValueError("Details timeout")
            return self.fetch(ticker, **kwargs)

        with patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
             patch("app.api.routes.prepare_stock_data", side_effect=details), \
             patch("app.api.routes.enrich_stocks", side_effect=self.enrich):
            response = self.client.post("/api/screen", json={
                "query": "Volume > 1000", "custom_tickers": "FAILED,FIRST,FIRST,SECOND,THIRD",
                "include_llm": True, "llm_max_stocks": 3,
            })
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual([s["stock"] for s in data["llm_enriched"]], ["FIRST.NS", "THIRD.NS"])
            self.assertEqual(set(data["failed_tickers"]), {"FAILED.NS", "SECOND.NS"})

    def test_ai_disabled_does_not_prepare_nonmatching_stocks_for_ai(self):
        with patch.object(qe, "prepare_stock_data", side_effect=self.fetch), \
             patch("app.api.routes.prepare_stock_data", side_effect=self.fetch) as details, \
             patch("app.api.routes.enrich_stocks") as enrich:
            response = self.client.post("/api/screen", json={
                "query": "Volume > 100", "custom_tickers": "FIRST,SECOND", "include_llm": False,
            })
            self.assertEqual(response.status_code, 200, response.text)
            details.assert_called_once_with("SECOND.NS", raise_errors=True)
            enrich.assert_not_called()


if __name__ == "__main__":
    unittest.main()
