"""Observed market evidence for the user's swing-entry framework.

Levels come from confirmed pivots and observed ranges, never percentage stops.
Missing provider fields remain null. Benchmarks are aligned on trading dates.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import math

import pandas as pd
import yfinance as yf

from app.engine.data_fetcher import fetch_historical, fetch_quote


def number(value, digits=4):
    try:
        value = float(value)
        return round(value, digits) if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def pct(value, base):
    return number((value / base - 1) * 100) if value is not None and base else None


def session_return(series, sessions):
    return pct(number(series.iloc[-1]), number(series.iloc[-sessions - 1])) if len(series) > sessions else None


def _dated_closes(df):
    dates = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).dt.normalize()
    return pd.Series(df["close"].values, index=dates).sort_index().loc[lambda s: ~s.index.duplicated(keep="last")]


def compare_benchmark(stock_df, benchmark_df, name, ticker):
    aligned = pd.concat([_dated_closes(stock_df).rename("stock"),
                         _dated_closes(benchmark_df).rename("benchmark")], axis=1).dropna()
    result = {"name": name, "ticker": ticker, "as_of": str(aligned.index[-1].date()) if len(aligned) else None}
    for label, days in [("1m", 21), ("3m", 63)]:
        stock_return = session_return(aligned["stock"], days)
        benchmark_return = session_return(aligned["benchmark"], days)
        result.update({f"stock_{label}_pct": stock_return, f"benchmark_{label}_pct": benchmark_return,
                       f"excess_{label}_pp": number(stock_return - benchmark_return) if stock_return is not None and benchmark_return is not None else None})
    return result


def _events(ticker):
    tk = yf.Ticker(ticker)
    events, news, gaps = [], [], []
    try:
        calendar = tk.get_calendar() or {}
        for label in ["Earnings Date", "Ex-Dividend Date", "Dividend Date"]:
            values = calendar.get(label)
            if values is None:
                continue
            for value in values if isinstance(values, (list, tuple)) else [values]:
                stamp = pd.Timestamp(value)
                if stamp.date() >= datetime.now(timezone.utc).date():
                    events.append({"event": label, "date": stamp.date().isoformat(), "source": "Yahoo Finance calendar"})
        if not events:
            gaps.append("No upcoming dates returned by the provider; this does not establish that no events are scheduled.")
    except Exception:
        gaps.append("Earnings/dividend calendar unavailable.")
    try:
        for item in tk.get_news(count=8):
            content = item.get("content", item)
            url = (content.get("canonicalUrl") or {}).get("url") or item.get("link")
            title = content.get("title")
            if title and url and url.startswith(("https://", "http://")):
                news.append({"title": title, "url": url, "published_at": content.get("pubDate"),
                             "source": (content.get("provider") or {}).get("displayName", "Yahoo Finance")})
        if not news:
            gaps.append("Recent corporate news unavailable.")
    except Exception:
        gaps.append("Recent corporate news unavailable.")
    gaps.append("Board meetings, bonuses, future splits and complete corporate-action coverage are not verified by this feed.")
    return {"upcoming": events, "news": news, "coverage_notes": gaps}


def build_swing_context(report):
    df = pd.DataFrame(report.chart_data).rename(columns={"time": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError("No dated daily bars for swing analysis")
    ticker = report.meta.symbol
    quote = fetch_quote(ticker)
    close = df["close"]
    current = number(quote.get("price")) or number(report.price_snapshot.current_price)
    latest = df.iloc[-1]
    prior = df.iloc[:-1]
    year = df[df["date"] > latest["date"] - pd.Timedelta(days=365)]
    metrics = {
        "current_price": current, "latest_session_open": number(quote.get("open")) or number(latest["open"]),
        "latest_session_high": number(quote.get("day_high")) or number(latest["high"]),
        "latest_session_low": number(quote.get("day_low")) or number(latest["low"]),
        "latest_session_close": number(latest["close"]), "high_52w": number(year["high"].max()),
        "low_52w": number(year["low"].min()), "current_volume": number(quote.get("volume")) or number(latest["volume"]),
        "ema_10": number(close.ewm(span=10, adjust=False, min_periods=10).mean().iloc[-1]),
        "ema_20": number(close.ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1]),
        "dma_50": number(close.rolling(50).mean().iloc[-1]),
        "dma_200": number(close.rolling(200).mean().iloc[-1]),
        "rsi_14": number(report.momentum_signals.rsi) if len(df) >= 15 else None,
        "atr_14": number(report.volatility_risk.atr) if len(df) >= 15 else None,
        "avg_volume_20d": number(prior["volume"].tail(20).mean()) if len(prior) >= 20 else None,
        "return_1m_pct": session_return(close, 21), "return_3m_pct": session_return(close, 63),
    }
    for key in ["ema_10", "ema_20", "dma_50", "high_52w"]:
        metrics[f"distance_from_{key}_pct"] = pct(current, metrics[key])
    metrics["volume_vs_20d"] = number(metrics["current_volume"] / metrics["avg_volume_20d"]) if metrics["avg_volume_20d"] else None
    for days in [50, 200]:
        rolling = close.rolling(days).mean()
        metrics[f"dma_{days}_change_20d_pct"] = pct(number(rolling.iloc[-1]), number(rolling.iloc[-21])) if len(df) >= days + 20 else None
    for days in [10, 20]:
        ema = close.ewm(span=days, adjust=False, min_periods=days).mean()
        metrics[f"ema_{days}_change_5d_pct"] = pct(number(ema.iloc[-1]), number(ema.iloc[-6])) if len(df) >= days + 5 else None

    # Confirmed pivots use three bars on either side; the final three bars are unconfirmed.
    pivots = []
    for i in range(max(3, len(df) - 252), len(df) - 3):
        window = df.iloc[i - 3:i + 4]
        for column, kind, extreme in [("high", "resistance", window["high"].max()), ("low", "support", window["low"].min())]:
            if df.iloc[i][column] == extreme:
                pivots.append({"price": number(extreme), "kind": kind, "date": df.iloc[i]["date"].date().isoformat(),
                               "basis": f"Confirmed 3-bar swing {column}"})
    base = prior.tail(20)
    levels = pivots[-40:]
    if len(base) == 20:
        levels += [{"price": number(base["high"].max()), "kind": "pivot", "basis": "Prior 20-session range high"},
                   {"price": number(base["low"].min()), "kind": "support", "basis": "Prior 20-session range low"}]
    for key in ["ema_10", "ema_20"]:
        if metrics[key]:
            levels.append({"price": metrics[key], "kind": "dynamic", "basis": key.replace("_", " ").upper()})
    lows = [p for p in pivots if p["kind"] == "support"]
    highs = [p for p in pivots if p["kind"] == "resistance"]
    cmp = lambda a, b: a > b if a is not None and b is not None else None
    checks = {
        "price_above_50_dma": cmp(current, metrics["dma_50"]),
        "price_above_200_dma": cmp(current, metrics["dma_200"]),
        "dma_50_above_200": cmp(metrics["dma_50"], metrics["dma_200"]),
        "dma_50_rising": cmp(metrics["dma_50_change_20d_pct"], 0),
        "dma_200_flat_or_rising": cmp(metrics["dma_200_change_20d_pct"], -0.1),
        "higher_highs": cmp(highs[-1]["price"], highs[-2]["price"]) if len(highs) >= 2 else None,
        "higher_lows": cmp(lows[-1]["price"], lows[-2]["price"]) if len(lows) >= 2 else None,
        "within_15pct_of_52w_high": cmp(metrics["distance_from_high_52w_pct"], -15),
    }
    returns = close.pct_change() * 100
    recent = df.tail(20)
    up = recent[recent["close"] > recent["open"]]
    down = recent[recent["close"] < recent["open"]]
    volume = {
        "volume_vs_20d": metrics["volume_vs_20d"],
        "up_day_avg_volume": number(up["volume"].mean()), "down_day_avg_volume": number(down["volume"].mean()),
        "recent_5day_avg_vs_prior_15day": number(recent.tail(5)["volume"].mean() / recent.iloc[:-5]["volume"].mean()) if len(recent) == 20 and recent.iloc[:-5]["volume"].mean() else None,
        "obv_trend": report.volume_intelligence.obv_trend,
        "accumulation_distribution": report.volume_intelligence.accumulation_distribution,
        "high_volume_bearish_reversal": bool(latest["close"] < latest["open"] and (metrics["volume_vs_20d"] or 0) >= 1.5),
        "note": "20-day average excludes the latest session. Intraday volume is partial and is not time-of-day adjusted.",
    }
    extension = {
        "largest_daily_gain_last_10_pct": number(returns.tail(10).max()),
        "days_up_over_5pct_last_10": int((returns.tail(10) > 5).sum()),
        "large_green_candles_last_5": int(((df["close"] / df["open"] - 1).tail(5) > .03).sum()),
        "five_session_return_pct": session_return(close, 5),
        "volume_climax_candidate": (metrics["volume_vs_20d"] or 0) >= 3,
    }
    fundamental_info = quote.get("fundamentals", {})
    scale = lambda key, multiplier=1: number(number(fundamental_info[key]) * multiplier) if number(fundamental_info.get(key)) is not None else None
    fundamentals = {
        "market_cap": scale("marketCap"), "market_cap_cr": scale("marketCap", 1e-7) if report.meta.currency == "INR" else None,
        "sales_growth_pct": scale("revenueGrowth", 100), "quarterly_profit_growth_pct": scale("earningsQuarterlyGrowth", 100),
        "roce_pct": scale("returnOnCapitalEmployed", 100), "roe_pct": scale("returnOnEquity", 100),
        "debt_to_equity": scale("debtToEquity", .01), "pe": scale("trailingPE"), "forward_pe": scale("forwardPE"),
        "promoter_holding_pct": None, "promoter_pledging_pct": None, "sector_pe": None, "historical_pe": None,
        "sector": quote.get("sector"),
        "coverage_note": "Provider-reported metrics. ROCE is not substituted with ROE; insider ownership is not promoter holding. Promoter/pledge and sector/historical P/E are unavailable.",
    }
    gaps = []
    comparisons = []
    # Only use a sector index when the provider's sector has a clear mapping.
    sector_map = {"Technology": ("Nifty IT", "^CNXIT"), "Financial Services": ("Nifty Financial Services", "^CNXFIN")}
    benchmarks = [("Nifty 50", "^NSEI")]
    if ticker.endswith((".NS", ".BO")) and quote.get("sector") in sector_map:
        benchmarks.append(sector_map[quote["sector"]])
    else:
        gaps.append("Relevant sector-index comparison unavailable; no proxy was substituted.")
    with ThreadPoolExecutor(max_workers=3) as executor:
        event_future = executor.submit(_events, ticker)
        futures = [(name, symbol, executor.submit(fetch_historical, symbol, period="1y", interval="1d")) for name, symbol in benchmarks]
        for name, symbol, future in futures:
            try:
                comparisons.append(compare_benchmark(df, future.result(), name, symbol))
            except Exception:
                gaps.append(f"{name} comparison unavailable.")
        events = event_future.result()
    now = datetime.now(timezone.utc)
    bar_age = (now.date() - latest["date"].date()).days
    quote_time = pd.to_datetime(quote.get("market_time"), unit="s", utc=True) if quote.get("market_time") else None
    freshness_verified = quote_time is not None and 0 <= (pd.Timestamp(now) - quote_time).total_seconds() <= 1800 and 0 <= bar_age <= 1
    if not freshness_verified:
        gaps.append("Current market freshness is unverified or stale. Do not treat this as an executable entry-now quote.")
    if len(df) < 220:
        gaps.append("Less than 220 sessions: long moving-average slope / Stage-2 evidence may be incomplete.")
    if report.meta.currency != "INR":
        gaps.append("Nifty comparison uses local-currency price returns without FX adjustment.")
    target_candidates = [dict(level) for level in levels if level["kind"] in ("resistance", "pivot")]
    if len(base) == 20:
        width = number(base["high"].max() - base["low"].min())
        if width and width > 0:
            target_candidates.append({"price": number(base["high"].max() + width), "kind": "projection",
                                      "basis": "One observed 20-session range height above its high; conditional measured-move projection, not confirmed resistance"})
    return {
        "stock": ticker, "currency": report.meta.currency,
        "as_of": {"latest_session": latest["date"].date().isoformat(), "quote_time": quote_time.isoformat() if quote_time is not None else None,
                  "retrieved_at": quote.get("fetched_at"), "indicators_generated_at": report.generated_at,
                  "source": "Yahoo Finance / configured historical fallback",
                  "freshness_verified": freshness_verified, "note": "Latest available session, not necessarily today's completed close. Prices may be delayed; data cache up to 5 minutes and analysis cache up to 10 minutes."},
        "market_data": metrics, "stage_checks": checks, "extension_signals": extension,
        "structure_levels": levels, "target_candidates": target_candidates,
        "recent_swing_low": lows[-1] if lows else None,
        "recent_swing_high": highs[-1] if highs else None,
        "base_range": {"high": number(base["high"].max()), "low": number(base["low"].min()), "sessions": len(base)},
        "volume_analysis": volume, "relative_strength": comparisons, "fundamentals": fundamentals,
        "events": events, "data_gaps": gaps,
        "recent_bars": [{**row, "date": str(row["date"].date())} for row in df.tail(90).to_dict("records")],
    }
