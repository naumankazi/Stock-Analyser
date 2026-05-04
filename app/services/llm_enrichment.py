"""LLM Enrichment Layer for Stock Analysis.

This module adds AI-powered analysis on top of existing stock metrics,
providing structured insights for investment decisions.

Architecture: Screener → MultiQuery → Stock Analysis → LLM Enrichment → API Response
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date
from typing import Any, Optional

import httpx
from cachetools import TTLCache
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# LLM API Configuration - supports multiple providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai, azure, anthropic
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_VERSION = os.getenv("LLM_API_VERSION", "2023-07-01-preview")  # Azure API version
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_PARALLEL = int(os.getenv("LLM_MAX_PARALLEL", "5"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# Cache for LLM responses (1 hour TTL - analysis doesn't change rapidly)
_llm_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)


# ── Pydantic Models for Structured Output ────────────────────────────────────

class StrengthSignals(BaseModel):
    """Strength indicators from metrics."""
    trend_alignment: str = Field(description="Trend alignment assessment")
    momentum_quality: str = Field(description="Momentum quality assessment")
    volume_support: str = Field(description="Volume support assessment")
    price_structure: str = Field(description="Price structure assessment")


class EntryStrategy(BaseModel):
    """Entry strategy recommendation."""
    trigger: str = Field(description="Entry trigger condition")
    zone: str = Field(description="Entry price zone")
    position_size: str = Field(description="Position sizing recommendation")
    time_horizon: str = Field(description="Suggested holding period")


class LLMAnalysis(BaseModel):
    """Structured LLM analysis output."""
    verdict: str = Field(
        description="Trading verdict: BUY, WATCHLIST, HOLD, AVOID"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score 0.0-1.0"
    )
    stage: str = Field(
        description="Trend stage: EARLY_TREND, CONFIRMED_UPTREND, LATE_STAGE, DISTRIBUTION, DOWNTREND, ACCUMULATION"
    )
    thesis: list[str] = Field(
        description="2-4 bullet points explaining the investment thesis"
    )
    strength_signals: StrengthSignals = Field(
        description="Key strength indicators"
    )
    risk_flags: list[str] = Field(
        description="1-3 key risk factors to monitor"
    )
    entry_strategy: EntryStrategy = Field(
        description="Recommended entry approach"
    )


class EnrichedStock(BaseModel):
    """Stock with LLM enrichment."""
    stock: str
    tags: list[str]
    metrics: dict[str, Any]
    llm: Optional[LLMAnalysis] = None


# ── Tag Classification ───────────────────────────────────────────────────────

def classify_stock_tags(metrics: dict, is_duplicate: bool = False) -> list[str]:
    """Classify a stock with relevant tags based on metrics.
    
    Args:
        metrics: Stock metrics dictionary
        is_duplicate: Whether stock appears in multiple queries
        
    Returns:
        List of applicable tags
    """
    tags = []
    
    # Multi-query conviction
    if is_duplicate:
        tags.append("duplicate")
    
    # Trend tags
    primary_trend = metrics.get("primary_trend", "").lower()
    if primary_trend == "bullish":
        tags.append("uptrend")
    elif primary_trend == "bearish":
        tags.append("downtrend")
    
    # Momentum tags
    rsi = metrics.get("rsi", 50)
    if rsi and 50 < rsi < 70:
        tags.append("momentum")
    elif rsi and rsi > 70:
        tags.append("overbought")
    elif rsi and rsi < 30:
        tags.append("oversold")
    
    # Volume tags
    volume_ratio = metrics.get("volume_ratio", 1.0)
    if volume_ratio and volume_ratio > 1.5:
        tags.append("high_volume")
    
    # Breakout detection
    dist_from_high = metrics.get("distance_from_52w_high_pct")
    if dist_from_high is not None and abs(dist_from_high) < 5:
        tags.append("near_52w_high")
        if volume_ratio and volume_ratio > 1.5:
            tags.append("breakout")
    
    # Trend strength
    adx = metrics.get("adx")
    if adx and adx > 25:
        tags.append("strong_trend")
    
    # MA crossover
    ma_50 = metrics.get("ma_50")
    ma_200 = metrics.get("ma_200")
    if ma_50 and ma_200 and ma_50 > ma_200:
        tags.append("golden_cross")
    
    # Value tags
    pe_vs_sector = metrics.get("pe_vs_sector", "").lower()
    if pe_vs_sector == "undervalued":
        tags.append("value")
    
    # Quality tags
    roe = metrics.get("roe_pct")
    if roe and roe > 20:
        tags.append("high_roe")
    
    moat = metrics.get("moat", "").lower()
    if moat == "strong":
        tags.append("moat")
    
    return tags


# ── Payload Builder ──────────────────────────────────────────────────────────

def _filter_none_values(d: dict) -> dict:
    """Remove keys with None values from a dict. Returns empty dict if all None."""
    return {k: v for k, v in d.items() if v is not None}


def build_llm_payload(stock_analysis: dict, tags: list[str]) -> dict:
    """Build structured payload for LLM from stock analysis.
    
    Combines metrics from stockAnalResp with classification tags.
    Filters out sections with all-null values to avoid LLM confusion.
    
    Args:
        stock_analysis: Full stock analysis dictionary
        tags: Classification tags for the stock
        
    Returns:
        Structured payload for LLM prompt
    """
    # Build sections with filtering
    price_data = _filter_none_values({
        "current_price": stock_analysis.get("current_price"),
        "change_pct": stock_analysis.get("change_pct"),
        "open": stock_analysis.get("open"),
        "high": stock_analysis.get("high"),
        "low": stock_analysis.get("low"),
        "volume": stock_analysis.get("volume"),
        "distance_from_52w_high_pct": stock_analysis.get("distance_from_52w_high_pct"),
        "distance_from_52w_low_pct": stock_analysis.get("distance_from_52w_low_pct"),
        "high_52w": stock_analysis.get("high_52w"),
        "low_52w": stock_analysis.get("low_52w"),
    })
    
    trend = _filter_none_values({
        "primary_trend": stock_analysis.get("primary_trend") or stock_analysis.get("technical_trend"),
        "daily_trend": stock_analysis.get("daily_trend"),
        "weekly_trend": stock_analysis.get("weekly_trend"),
        "trend_alignment": stock_analysis.get("trend_alignment"),
        "trend_strength": stock_analysis.get("trend_strength"),
        "ma_50": stock_analysis.get("ma_50") or stock_analysis.get("sma_50"),
        "ma_200": stock_analysis.get("ma_200") or stock_analysis.get("sma_200"),
        "adx": stock_analysis.get("adx"),
        "supertrend_signal": stock_analysis.get("supertrend_signal"),
    })
    
    momentum = _filter_none_values({
        "rsi": stock_analysis.get("rsi"),
        "rsi_state": stock_analysis.get("rsi_state"),
        "macd_signal": stock_analysis.get("macd_signal"),
        "macd_line": stock_analysis.get("macd_line"),
        "signal_line": stock_analysis.get("signal_line"),
        "histogram": stock_analysis.get("histogram"),
    })
    
    volume = _filter_none_values({
        "volume_ratio": stock_analysis.get("volume_ratio"),
        "obv_trend": stock_analysis.get("obv_trend"),
        "accumulation_distribution": stock_analysis.get("accumulation_distribution"),
        "vwap": stock_analysis.get("vwap"),
        "price_vs_vwap": stock_analysis.get("price_vs_vwap"),
        "volume_1w_avg": stock_analysis.get("volume_1w_avg"),
    })
    
    support_resistance = _filter_none_values({
        "nearest_support": stock_analysis.get("nearest_support"),
        "nearest_resistance": stock_analysis.get("nearest_resistance"),
        "breakout_probability": stock_analysis.get("breakout_probability"),
    })
    
    volatility = _filter_none_values({
        "atr": stock_analysis.get("atr"),
        "atr_percent": stock_analysis.get("atr_percent"),
        "volatility_regime": stock_analysis.get("volatility_regime"),
        "bollinger_position": stock_analysis.get("bollinger_position"),
        "beta": stock_analysis.get("beta"),
    })
    
    fundamentals = _filter_none_values({
        "pe_ratio": stock_analysis.get("pe_ratio"),
        "pe_vs_sector": stock_analysis.get("pe_vs_sector"),
        "peg_ratio": stock_analysis.get("peg_ratio"),
        "roe_pct": stock_analysis.get("roe_pct"),
        "roce": stock_analysis.get("roce"),
        "debt_to_equity": stock_analysis.get("debt_to_equity") or stock_analysis.get("de_ratio"),
        "operating_margin": stock_analysis.get("operating_margin"),
        "profit_margin": stock_analysis.get("profit_margin"),
        "revenue_growth_5y_pct": stock_analysis.get("revenue_growth_5y_pct"),
        "profit_growth_5y_pct": stock_analysis.get("profit_growth_5y_pct"),
        "market_cap": stock_analysis.get("market_cap"),
        "free_cash_flow": stock_analysis.get("free_cash_flow"),
        "moat": stock_analysis.get("moat"),
    })
    
    trade_levels = _filter_none_values({
        "entry_zone_low": stock_analysis.get("entry_zone_low"),
        "entry_zone_high": stock_analysis.get("entry_zone_high"),
        "ideal_entry": stock_analysis.get("ideal_entry"),
        "stop_loss": stock_analysis.get("stop_loss"),
        "target_base": stock_analysis.get("target_base"),
        "target_bull": stock_analysis.get("target_bull"),
        "risk_reward_ratio": stock_analysis.get("risk_reward_ratio"),
        "position_bias": stock_analysis.get("position_bias"),
    })
    
    scores = _filter_none_values({
        "composite_score": stock_analysis.get("composite_score"),
        "trend_score": stock_analysis.get("trend_score"),
        "momentum_score": stock_analysis.get("momentum_score"),
        "volume_score": stock_analysis.get("volume_score"),
        "volatility_score": stock_analysis.get("volatility_score"),
        "risk_score": stock_analysis.get("risk_score"),
        "market_state": stock_analysis.get("market_state"),
    })
    
    # Build final payload, excluding empty sections
    payload = {
        "stock": stock_analysis.get("ticker") or stock_analysis.get("stock", "UNKNOWN"),
        "tags": tags,
    }
    
    if price_data:
        payload["price_data"] = price_data
    if trend:
        payload["trend"] = trend
    if momentum:
        payload["momentum"] = momentum
    if volume:
        payload["volume"] = volume
    if support_resistance:
        payload["support_resistance"] = support_resistance
    if volatility:
        payload["volatility"] = volatility
    if fundamentals:
        payload["fundamentals"] = fundamentals
    if trade_levels:
        payload["trade_levels"] = trade_levels
    if scores:
        payload["scores"] = scores
    
    return payload


# ── Prompt Builder ───────────────────────────────────────────────────────────

def build_prompt(payload: dict) -> str:
    """Build structured prompt for LLM analysis.
    
    Enforces JSON output with specific schema to avoid hallucination.
    
    Args:
        payload: Structured payload from build_llm_payload
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are a quantitative stock analyst. Analyze the following stock data and provide a structured assessment.

## Stock Data
```json
{json.dumps(payload, indent=2, default=str)}
```

## Analysis Requirements
Based on the metrics above, provide a structured analysis following these rules:

1. **Stage Classification** (choose one):
   - EARLY_TREND: Price just crossed above key MAs, RSI 50-60, low ADX
   - CONFIRMED_UPTREND: All MAs aligned bullish, RSI 55-70, ADX > 25
   - LATE_STAGE: Near 52W high, RSI > 65, extended from MAs
   - DISTRIBUTION: High volume on down days, RSI divergence
   - DOWNTREND: Below key MAs, RSI < 50
   - ACCUMULATION: Low RSI, high volume, near support

2. **Verdict** (choose one):
   - BUY: Strong setup, good risk/reward, confirmed trend
   - WATCHLIST: Promising but needs confirmation or better entry
   - HOLD: Existing position, no action needed
   - AVOID: Poor technicals, high risk, or unclear setup

3. **Confidence**: 0.0-1.0 based on signal clarity and alignment

4. **Thesis**: 2-4 bullet points (be specific, cite metrics)

5. **Risk Flags**: 1-3 specific risks (cite metrics or market conditions)

## Output Format (STRICT JSON)
Respond ONLY with valid JSON matching this exact schema:
```json
{{
  "verdict": "BUY|WATCHLIST|HOLD|AVOID",
  "confidence": 0.75,
  "stage": "EARLY_TREND|CONFIRMED_UPTREND|LATE_STAGE|DISTRIBUTION|DOWNTREND|ACCUMULATION",
  "thesis": [
    "Point 1 with specific metric",
    "Point 2 with specific metric"
  ],
  "strength_signals": {{
    "trend_alignment": "brief assessment",
    "momentum_quality": "brief assessment",
    "volume_support": "brief assessment",
    "price_structure": "brief assessment"
  }},
  "risk_flags": [
    "Risk 1 with context",
    "Risk 2 with context"
  ],
  "entry_strategy": {{
    "trigger": "specific entry trigger",
    "zone": "price range or condition",
    "position_size": "sizing recommendation",
    "time_horizon": "expected holding period"
  }}
}}
```

IMPORTANT: Return ONLY the JSON object, no markdown formatting, no explanations."""

    return prompt


# ── LLM Call Function ────────────────────────────────────────────────────────

async def call_llm(payload: dict, client: httpx.AsyncClient) -> Optional[dict]:
    """Call LLM API with structured payload.
    
    Args:
        payload: Stock payload from build_llm_payload
        client: Shared async HTTP client
        
    Returns:
        Parsed JSON response or None if failed
    """
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set, skipping LLM enrichment")
        return None
    
    stock = payload.get("stock", "UNKNOWN")
    
    # Check cache first
    cache_key = f"llm:{stock}:{date.today().isoformat()}"
    if cache_key in _llm_cache:
        logger.debug("LLM cache hit for %s", stock)
        return _llm_cache[cache_key]
    
    prompt = build_prompt(payload)
    
    try:
        # Build request based on provider
        if LLM_PROVIDER == "azure":
            # Azure OpenAI has different URL format and auth
            headers = {
                "api-key": LLM_API_KEY,
                "Content-Type": "application/json",
            }
            request_body = {
                "messages": [
                    {"role": "system", "content": "You are a quantitative stock analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": LLM_TEMPERATURE,
                "max_tokens": 1000,
            }
            # Azure URL: {base}/openai/deployments/{deployment}/chat/completions?api-version={version}
            base = LLM_BASE_URL.rstrip('/')
            url = f"{base}/openai/deployments/{LLM_MODEL}/chat/completions?api-version={LLM_API_VERSION}"
            
        elif LLM_PROVIDER == "openai":
            headers = {
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            }
            request_body = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a quantitative stock analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": LLM_TEMPERATURE,
                "max_tokens": 1000,
            }
            url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
            
        elif LLM_PROVIDER == "anthropic":
            headers = {
                "x-api-key": LLM_API_KEY,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            request_body = {
                "model": LLM_MODEL,
                "max_tokens": 1000,
                "temperature": LLM_TEMPERATURE,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            url = "https://api.anthropic.com/v1/messages"
        else:
            logger.error("Unsupported LLM provider: %s", LLM_PROVIDER)
            return None
        
        response = await client.post(
            url,
            headers=headers,
            json=request_body,
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract content based on provider
        if LLM_PROVIDER in ("openai", "azure"):
            content = data["choices"][0]["message"]["content"]
        elif LLM_PROVIDER == "anthropic":
            content = data["content"][0]["text"]
        else:
            content = ""
        
        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        # Validate structure
        if not isinstance(result, dict):
            logger.warning("LLM returned non-dict for %s", stock)
            return None
        
        required_keys = {"verdict", "confidence", "stage", "thesis", "risk_flags"}
        if not required_keys.issubset(result.keys()):
            logger.warning("LLM response missing required keys for %s", stock)
            return None
        
        # Cache successful result
        _llm_cache[cache_key] = result
        logger.info("LLM enrichment successful for %s", stock)
        
        return result
        
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON for %s: %s", stock, e)
        return None
    except httpx.HTTPStatusError as e:
        logger.error("LLM API error for %s: %s", stock, e.response.status_code)
        return None
    except httpx.TimeoutException:
        logger.warning("LLM timeout for %s", stock)
        return None
    except Exception as e:
        logger.error("LLM call failed for %s: %s", stock, e)
        return None


# ── Single Stock Enrichment ──────────────────────────────────────────────────

async def enrich_single_stock(
    stock_data: dict,
    is_duplicate: bool,
    client: httpx.AsyncClient
) -> dict:
    """Enrich a single stock with LLM analysis.
    
    Args:
        stock_data: Stock metrics dictionary
        is_duplicate: Whether stock appears in multiple queries
        client: Shared async HTTP client
        
    Returns:
        Enriched stock dictionary with 'llm' field (or None if failed)
    """
    # Classify tags
    tags = classify_stock_tags(stock_data, is_duplicate)
    
    # Build payload
    payload = build_llm_payload(stock_data, tags)
    
    # Call LLM
    llm_result = await call_llm(payload, client)
    
    # Build enriched response
    stock_name = stock_data.get("ticker") or stock_data.get("stock", "UNKNOWN")
    
    result = {
        "stock": stock_name,
        "tags": tags,
        "metrics": stock_data,
    }
    
    if llm_result:
        result["llm"] = llm_result
    
    return result


# ── Batch Enrichment ─────────────────────────────────────────────────────────

async def enrich_stocks(
    stocks: list[dict],
    duplicates: Optional[list[str]] = None,
    max_parallel: int = LLM_MAX_PARALLEL,
) -> list[dict]:
    """Enrich multiple stocks with LLM analysis in parallel.
    
    Args:
        stocks: List of stock analysis dictionaries
        duplicates: List of tickers that appear in multiple queries
        max_parallel: Maximum parallel LLM calls
        
    Returns:
        List of enriched stock dictionaries
    """
    if not stocks:
        return []
    
    duplicates_set = set(duplicates or [])
    
    async with httpx.AsyncClient() as client:
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_parallel)
        
        async def bounded_enrich(stock: dict) -> dict:
            async with semaphore:
                ticker = stock.get("ticker") or stock.get("stock", "")
                is_dup = ticker in duplicates_set
                return await enrich_single_stock(stock, is_dup, client)
        
        # Run all enrichments in parallel
        tasks = [bounded_enrich(stock) for stock in stocks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed results
        enriched = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Enrichment failed for stock %d: %s", i, result)
                # Return stock without LLM field on failure
                stock = stocks[i]
                enriched.append({
                    "stock": stock.get("ticker") or stock.get("stock", "UNKNOWN"),
                    "tags": classify_stock_tags(stock, stock.get("ticker", "") in duplicates_set),
                    "metrics": stock,
                })
            else:
                enriched.append(result)
        
        return enriched


# ── Stock Selection for LLM ──────────────────────────────────────────────────

def select_stocks_for_enrichment(
    multi_query_result: dict,
    stock_details: list[dict],
    max_stocks: int = 15,
) -> tuple[list[dict], list[str]]:
    """Select top stocks for LLM enrichment.
    
    Prioritizes:
    1. Stocks appearing in multiple queries (duplicates)
    2. Top stocks from ordered list
    
    Args:
        multi_query_result: Result from multi-query screening
        stock_details: Full stock details list
        max_stocks: Maximum number of stocks to enrich
        
    Returns:
        Tuple of (selected stocks, duplicate tickers)
    """
    duplicates = multi_query_result.get("duplicates", [])
    ordered = multi_query_result.get("ordered", [])
    
    # Build ticker -> stock mapping
    ticker_to_stock = {}
    for stock in stock_details:
        ticker = stock.get("ticker") or stock.get("stock", "")
        if ticker:
            ticker_to_stock[ticker] = stock
    
    selected_tickers = []
    
    # First, add all duplicates (high conviction)
    for ticker in duplicates:
        if ticker in ticker_to_stock and ticker not in selected_tickers:
            selected_tickers.append(ticker)
    
    # Then fill remaining slots from ordered list
    for ticker in ordered:
        if len(selected_tickers) >= max_stocks:
            break
        if ticker in ticker_to_stock and ticker not in selected_tickers:
            selected_tickers.append(ticker)
    
    # Get stock data for selected tickers
    selected_stocks = [ticker_to_stock[t] for t in selected_tickers if t in ticker_to_stock]
    
    return selected_stocks, duplicates


# ── Confidence-Based Ranking ─────────────────────────────────────────────────

def rank_by_confidence(enriched_stocks: list[dict]) -> list[dict]:
    """Sort enriched stocks by LLM confidence score.
    
    Stocks without LLM analysis are ranked last.
    
    Args:
        enriched_stocks: List of enriched stock dictionaries
        
    Returns:
        Sorted list (highest confidence first)
    """
    def get_confidence(stock: dict) -> float:
        llm = stock.get("llm")
        if llm:
            return llm.get("confidence", 0.0)
        return -1.0  # Stocks without LLM analysis go last
    
    return sorted(enriched_stocks, key=get_confidence, reverse=True)


# ── Stage-Based Sorting ──────────────────────────────────────────────────────

# Stage priority order (lower = better)
STAGE_PRIORITY = {
    "EARLY_TREND": 1,
    "ACCUMULATION": 2,
    "CONFIRMED_UPTREND": 3,
    "LATE_STAGE": 4,
    "DISTRIBUTION": 5,
    "DOWNTREND": 6,
}


def sort_by_stage(enriched_stocks: list[dict]) -> list[dict]:
    """Sort enriched stocks by trend stage.
    
    Early trends first (best entry opportunities).
    
    Args:
        enriched_stocks: List of enriched stock dictionaries
        
    Returns:
        Sorted list (early stages first)
    """
    def get_stage_priority(stock: dict) -> int:
        llm = stock.get("llm")
        if llm:
            stage = llm.get("stage", "")
            return STAGE_PRIORITY.get(stage, 99)
        return 100  # Stocks without LLM analysis go last
    
    return sorted(enriched_stocks, key=get_stage_priority)


def sort_by_verdict(enriched_stocks: list[dict]) -> list[dict]:
    """Sort enriched stocks by verdict (BUY first, then WATCHLIST, etc.).
    
    Args:
        enriched_stocks: List of enriched stock dictionaries
        
    Returns:
        Sorted list (BUY first)
    """
    verdict_priority = {
        "BUY": 1,
        "WATCHLIST": 2,
        "HOLD": 3,
        "AVOID": 4,
    }
    
    def get_verdict_priority(stock: dict) -> tuple[int, float]:
        llm = stock.get("llm")
        if llm:
            verdict = llm.get("verdict", "")
            confidence = llm.get("confidence", 0.0)
            return (verdict_priority.get(verdict, 99), -confidence)
        return (100, 0.0)
    
    return sorted(enriched_stocks, key=get_verdict_priority)


# ── Cache Management ─────────────────────────────────────────────────────────

def clear_llm_cache() -> int:
    """Clear the LLM response cache.
    
    Returns:
        Number of items cleared
    """
    count = len(_llm_cache)
    _llm_cache.clear()
    return count


def get_cache_stats() -> dict:
    """Get LLM cache statistics.
    
    Returns:
        Dict with cache info
    """
    return {
        "size": len(_llm_cache),
        "maxsize": _llm_cache.maxsize,
        "ttl": _llm_cache.ttl,
        "hits_today": date.today().isoformat(),
    }
