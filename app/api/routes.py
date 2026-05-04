"""API route definitions."""
# Updated: Added screener_urls support for multiple Screener.in URLs v2

from __future__ import annotations

import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.engine.analyzer import run_analysis
from app.engine.data_fetcher import fetch_quote
from app.engine.screener import run_screener
from app.engine.query_engine import (
    run_query,
    run_multiple_queries,
    validate_query,
    get_available_fields,
    get_example_queries,
    prepare_stock_data,
    get_default_stock_universe,
)
from app.models.schemas import (
    AnalysisReport,
    AnalysisRequest,
    ScreenerReport,
    ScreenerRequest,
    QueryScreenerReport,
    QueryScreenerReportWithLLM,
    QueryResultItem,
    LLMEnrichedStock,
    LLMEnrichmentSummary,
)
from app.services.llm_enrichment import (
    enrich_stocks,
    select_stocks_for_enrichment,
    rank_by_confidence,
    sort_by_verdict,
    classify_stock_tags,
    get_cache_stats as get_llm_cache_stats,
    clear_llm_cache,
    build_llm_payload,
    call_llm,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisReport)
async def analyze(req: AnalysisRequest):
    """Run full technical analysis for a given ticker."""
    try:
        report = run_analysis(req.ticker, req.position)
        
        # Add LLM analysis if requested
        if req.include_llm:
            try:
                # Build trimmed stock data from calculated technical indicators
                stock_data = _build_llm_stock_data(report)
                
                tags = classify_stock_tags(stock_data, False)
                payload = build_llm_payload(stock_data, tags)
                
                import httpx
                async with httpx.AsyncClient() as client:
                    llm_result = await call_llm(payload, client)
                
                if llm_result:
                    report_dict = report.model_dump()
                    report_dict["llm_analysis"] = llm_result
                    return report_dict
            except Exception as e:
                logger.warning("LLM enrichment failed for %s: %s", req.ticker, e)
                # Continue without LLM analysis
        
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Analysis failed for %s: %s\n%s", req.ticker, e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


def _build_llm_stock_data(report) -> dict:
    """Build trimmed stock data dict from AnalysisReport for LLM enrichment.
    
    Extracts technical indicators from AnalysisReport and enriches with
    fundamentals from prepare_stock_data for comprehensive LLM analysis.
    """
    price = report.price_snapshot
    ticker = report.meta.symbol
    
    # Get fundamentals from prepare_stock_data (same source as query screening)
    fundamentals = prepare_stock_data(ticker) or {}
    
    return {
        # Identifiers
        "ticker": ticker,
        "stock": ticker,
        
        # Price metrics - from AnalysisReport
        "current_price": price.current_price,
        "close": price.current_price,
        "open": price.open,
        "high": price.day_high,
        "low": price.day_low,
        "volume": price.volume,
        "change_pct": price.change_pct,
        "distance_from_52w_high_pct": price.distance_from_52w_high_pct,
        "distance_from_52w_low_pct": price.distance_from_52w_low_pct,
        
        # 52-week data from fundamentals
        "high_52w": fundamentals.get("high_52w"),
        "low_52w": fundamentals.get("low_52w"),
        
        # Trend indicators (from TrendStructure)
        "primary_trend": report.trend_structure.primary_trend,
        "technical_trend": report.trend_structure.primary_trend,
        "daily_trend": report.trend_structure.daily_trend,
        "weekly_trend": report.trend_structure.weekly_trend,
        "trend_alignment": report.trend_structure.trend_alignment,
        "trend_strength": report.trend_structure.trend_strength,
        "ma_50": report.trend_structure.ma_50,
        "sma_50": report.trend_structure.ma_50,
        "ma_200": report.trend_structure.ma_200,
        "sma_200": report.trend_structure.ma_200,
        "adx": report.trend_structure.adx,
        "supertrend_signal": report.trend_structure.supertrend_signal,
        
        # Momentum indicators (from MomentumSignals)
        "rsi": report.momentum_signals.rsi,
        "rsi_state": report.momentum_signals.rsi_state,
        "macd_signal": report.momentum_signals.macd_signal,
        "macd_line": report.momentum_signals.macd_line,
        "signal_line": report.momentum_signals.signal_line,
        "histogram": report.momentum_signals.histogram,
        
        # Volume indicators (from VolumeIntelligence)
        "volume_ratio": report.volume_intelligence.volume_ratio,
        "obv_trend": report.volume_intelligence.obv_trend,
        "accumulation_distribution": report.volume_intelligence.accumulation_distribution,
        "vwap": report.volume_intelligence.vwap,
        "price_vs_vwap": report.volume_intelligence.price_vs_vwap,
        
        # Support/Resistance (from SupportResistanceBlock)
        "nearest_support": report.support_resistance.nearest_support,
        "nearest_resistance": report.support_resistance.nearest_resistance,
        "breakout_probability": report.support_resistance.breakout_probability,
        "support_levels": report.support_resistance.support_levels,
        "resistance_levels": report.support_resistance.resistance_levels,
        
        # Volatility (from VolatilityRisk)
        "atr": report.volatility_risk.atr,
        "atr_percent": report.volatility_risk.atr_percent,
        "volatility_regime": report.volatility_risk.volatility_regime,
        "bollinger_upper": report.volatility_risk.bollinger_upper,
        "bollinger_middle": report.volatility_risk.bollinger_middle,
        "bollinger_lower": report.volatility_risk.bollinger_lower,
        "bollinger_position": report.volatility_risk.bollinger_position,
        
        # Composite scores (from QuantScores)
        "composite_score": report.quant_scores.composite_score,
        "trend_score": report.quant_scores.trend_score,
        "momentum_score": report.quant_scores.momentum_score,
        "volume_score": report.quant_scores.volume_score,
        "volatility_score": report.quant_scores.volatility_score,
        "market_state": report.quant_scores.market_state,
        
        # Derived risk score (inverse of volatility score, normalized)
        "risk_score": max(0, 100 - report.quant_scores.volatility_score) if report.quant_scores.volatility_score else 50,
        
        # Trade levels (from TradeLevels)
        "entry_zone_low": report.trade_levels.ideal_entry * 0.98,
        "entry_zone_high": report.trade_levels.ideal_entry * 1.02,
        "ideal_entry": report.trade_levels.ideal_entry,
        "stop_loss": report.trade_levels.stop_losses[0].price if report.trade_levels.stop_losses else None,
        "target_base": report.trade_levels.targets[0].price if report.trade_levels.targets else None,
        "target_bull": report.trade_levels.targets[-1].price if len(report.trade_levels.targets) > 1 else None,
        "risk_reward_ratio": report.trade_levels.risk_reward_ratio,
        "position_bias": report.trade_levels.position_bias,
        
        # Fundamental data from prepare_stock_data (same as query screening)
        "pe_ratio": fundamentals.get("pe_ratio"),
        "peg_ratio": fundamentals.get("peg_ratio"),
        "de_ratio": fundamentals.get("de_ratio"),
        "debt_to_equity": fundamentals.get("de_ratio"),
        "roe_pct": fundamentals.get("roe"),
        "roce": fundamentals.get("roce"),
        "operating_margin": fundamentals.get("operating_margin"),
        "profit_margin": fundamentals.get("profit_margin"),
        "revenue_growth_5y_pct": fundamentals.get("revenue_growth"),
        "profit_growth_5y_pct": fundamentals.get("earnings_growth"),
        "market_cap": fundamentals.get("market_cap"),
        "beta": fundamentals.get("beta"),
        "free_cash_flow": fundamentals.get("free_cash_flow"),
        
        # Return data from fundamentals
        "return_3m": fundamentals.get("return_3m"),
        "volume_1w_avg": fundamentals.get("volume_1w_avg"),
    }


@router.get("/quote/{ticker}")
async def quote(ticker: str):
    """Get a quick price quote (raw dict)."""
    try:
        data = fetch_quote(ticker.upper().strip())
        return data
    except Exception as e:
        logger.error("Quote failed for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    return {"status": "ok", "service": "stock-analyzer"}


@router.post("/screen", response_model=Union[ScreenerReport, QueryScreenerReport, QueryScreenerReportWithLLM])
async def screen(req: ScreenerRequest = ScreenerRequest()):
    """Run stock screening — supports both multi-factor and query-based modes.
    
    ## Multi-Factor Screening (default)
    When no query is provided, runs the traditional multi-factor screening for 
    Shariah-compliant Indian equities with composite scoring.
    
    Parameters:
    - capital: Investment capital in INR (default: 100000)
    - max_risk_pct: Maximum downside risk per stock (%) (default: 7.0)
    - horizon_months: Investment horizon in months (default: 12)
    - top_n: Number of top stocks to return (default: 10, max: 30)
    - custom_tickers: Comma-separated ticker symbols to screen instead of default universe
    
    ## Query-Based Screening (Screener.in-style)
    When `query` or `queries` is provided, runs query-based filtering.
    
    Parameters:
    - query: Single query string for filtering stocks
      Example: "RSI > 50 AND RSI < 70 AND Market Capitalization > 500"
    - queries: List of query strings for multi-query screening
      Results are deduplicated and ordered (stocks in multiple queries first)
    - include_or: Whether to support OR conditions (default: false, AND-only)
    
    ### Supported Fields
    - **Price**: Current price, Close, Open, High, Low, 52 week high/low
    - **Moving Averages**: DMA 50, DMA 200, SMA 50, SMA 200
    - **Momentum**: RSI
    - **Volume**: Volume, Volume 1week average
    - **Returns**: Return over 3months
    - **Valuation**: Price to earning, PEG ratio, Market Capitalization (in crores)
    - **Financial Health**: Debt to equity, Return on equity, ROCE, Operating margin
    - **Growth**: Revenue growth, Earnings growth
    
    ### Operators
    >, <, >=, <=, =, !=
    
    ### Expression Support
    - Arithmetic: `1.05 * DMA 200`, `(High - Close) / High`
    - Constants: `500`, `1.05`, `-10`
    
    ### Example Queries
    - "RSI > 50 AND RSI < 70"
    - "Market Capitalization > 500 AND Current price > 1.05 * DMA 200"
    - "Price to earning < 30 AND Debt to equity < 0.5"
    """
    try:
        # Debug: Log incoming request
        logger.info(f"screen_stocks called: screener_url={req.screener_url}, screener_urls={req.screener_urls}, query={req.query}, include_llm={req.include_llm}, custom_tickers={req.custom_tickers}")
        
        # Check if query-based screening is requested
        if req.query or req.queries:
            return await _run_query_screening(req)
        
        # If custom_tickers provided, route through query screening with pass-through query
        if req.custom_tickers:
            logger.info("Custom tickers provided - using query screening path with pass-through query")
            req.query = "Volume >= 0"
            return await _run_query_screening(req)
        
        # If screener_url or screener_query provided without a query, use query-based screening
        # with a pass-through query that matches all stocks
        if req.screener_url or req.screener_urls or req.screener_query or (req.universe and req.universe != "nifty50"):
            logger.info("Using screener_url/screener_urls/screener_query/universe without query - applying pass-through query")
            # Create a pass-through query that matches all stocks
            req.query = "Volume >= 0"
            return await _run_query_screening(req)
        
        # If LLM enrichment requested, route through query screening with pass-through query
        if req.include_llm:
            logger.info("LLM enrichment requested - using query screening path with pass-through query")
            req.query = "Volume >= 0"
            if not req.universe:
                req.universe = "nse100"  # Default universe (100 stocks from STOCK_UNIVERSE)
            return await _run_query_screening(req)
        
        # Fall back to traditional multi-factor screening
        report = run_screener(req)
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Screening failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Screening failed: {str(e)}")


async def _run_query_screening(req: ScreenerRequest) -> Union[QueryScreenerReport, QueryScreenerReportWithLLM]:
    """Handle query-based screening logic with optional LLM enrichment."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Determine stock universe (custom_tickers overrides everything else)
    stocks = None
    universe_params = {}
    
    if req.custom_tickers:
        # Parse custom tickers - highest priority
        tickers = [t.strip().upper() for t in req.custom_tickers.split(",") if t.strip()]
        # Add .NS suffix if not present
        stocks = [t if "." in t else f"{t}.NS" for t in tickers]
    else:
        # Use dynamic universe params
        universe_params = {
            "universe": req.universe,
            "screener_url": req.screener_url,
            "screener_urls": req.screener_urls,
            "screener_query": req.screener_query,
        }
    
    # Validate queries first
    all_errors = []
    
    if req.queries:
        # Multi-query mode
        for query in req.queries:
            is_valid, errors = validate_query(query)
            if not is_valid:
                all_errors.extend([f"Query '{query[:50]}...': {e}" for e in errors])
    elif req.query:
        # Single query mode
        is_valid, errors = validate_query(req.query)
        if not is_valid:
            all_errors.extend(errors)
    
    # If validation errors, return helpful response
    if all_errors:
        return QueryScreenerReport(
            mode="validation_error",
            matched_tickers=[],
            total_screened=0,
            errors=all_errors,
            available_fields=get_available_fields(),
            example_queries=get_example_queries(),
            generated_at=now
        )
    
    if req.queries:
        # Multi-query mode
        result = run_multiple_queries(
            queries=req.queries,
            stocks=stocks,
            include_or=req.include_or,
            **universe_params
        )
        
        # Build stock details for matched tickers (top N) - parallel fetch
        top_tickers = result.ordered[:req.top_n]
        stock_details = []
        
        max_workers = min(20, len(top_tickers))
        if top_tickers:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {
                    executor.submit(prepare_stock_data, ticker): ticker
                    for ticker in top_tickers
                }
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        data = future.result()
                        if data:
                            stock_details.append({
                                "ticker": ticker,
                                **{k: round(v, 2) if isinstance(v, float) else v for k, v in data.items()}
                            })
                    except Exception:
                        pass
        
        # Build base response
        base_response = {
            "mode": "multi_query",
            "matched_tickers": result.ordered[:req.top_n],
            "total_screened": result.query_results[0].total_screened if result.query_results else 0,
            "duplicates": result.duplicates,
            "deduplicated": result.deduplicated,
            "ordered": result.ordered,
            "query_breakdown": result.query_breakdown,
            "query_results": [
                QueryResultItem(
                    query=qr.query,
                    matched_tickers=qr.matched_tickers,
                    total_screened=qr.total_screened,
                    errors=qr.errors
                )
                for qr in result.query_results
            ],
            "stock_details": stock_details,
            "errors": [e for qr in result.query_results for e in qr.errors],
            "generated_at": now
        }
        
        # LLM Enrichment (if requested)
        if req.include_llm and stock_details:
            try:
                # Select stocks for enrichment (prioritize duplicates)
                multi_query_data = {
                    "duplicates": result.duplicates,
                    "ordered": result.ordered,
                }
                selected_stocks, duplicates = select_stocks_for_enrichment(
                    multi_query_data,
                    stock_details,
                    max_stocks=req.llm_max_stocks
                )
                
                # Run LLM enrichment
                enriched_stocks = await enrich_stocks(
                    selected_stocks,
                    duplicates=duplicates,
                )
                
                # Sort by verdict (BUY first, then WATCHLIST, etc.)
                enriched_sorted = sort_by_verdict(enriched_stocks)
                
                # Build enrichment summary
                verdicts = {}
                stages = {}
                successful = 0
                failed = 0
                
                for stock in enriched_stocks:
                    if stock.get("llm"):
                        successful += 1
                        verdict = stock["llm"].get("verdict", "UNKNOWN")
                        verdicts[verdict] = verdicts.get(verdict, 0) + 1
                        stage = stock["llm"].get("stage", "UNKNOWN")
                        stages[stage] = stages.get(stage, 0) + 1
                    else:
                        failed += 1
                
                summary = LLMEnrichmentSummary(
                    total_enriched=len(enriched_stocks),
                    successful=successful,
                    failed=failed,
                    cached=0,  # Could track this from the cache module
                    verdicts=verdicts,
                    stages=stages,
                )
                
                # Convert to Pydantic models
                llm_enriched = [
                    LLMEnrichedStock(
                        stock=s.get("stock", ""),
                        tags=s.get("tags", []),
                        metrics=s.get("metrics", {}),
                        llm=s.get("llm"),
                    )
                    for s in enriched_sorted
                ]
                
                return QueryScreenerReportWithLLM(
                    **base_response,
                    llm_enriched=llm_enriched,
                    llm_summary=summary,
                )
                
            except Exception as e:
                logger.error("LLM enrichment failed: %s\n%s", e, traceback.format_exc())
                # Fall back to non-LLM response
                base_response["errors"].append(f"LLM enrichment failed: {str(e)}")
                return QueryScreenerReport(**base_response)
        
        return QueryScreenerReport(**base_response)
    
    else:
        # Single query mode
        result = run_query(
            query=req.query or "",
            stocks=stocks,
            include_or=req.include_or,
            **universe_params
        )
        
        # Build stock details for matched tickers (top N) - parallel fetch
        top_tickers = result.matched_tickers[:req.top_n]
        stock_details = []
        
        max_workers = min(20, len(top_tickers))
        if top_tickers:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {
                    executor.submit(prepare_stock_data, ticker): ticker
                    for ticker in top_tickers
                }
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        data = future.result()
                        if data:
                            stock_details.append({
                                "ticker": ticker,
                                **{k: round(v, 2) if isinstance(v, float) else v for k, v in data.items()}
                            })
                    except Exception:
                        pass
        
        # Build base response
        base_response = {
            "mode": "single_query",
            "query": result.query,
            "matched_tickers": result.matched_tickers[:req.top_n],
            "total_screened": result.total_screened,
            "stock_details": stock_details,
            "skipped_tickers": result.skipped_tickers or [],
            "errors": result.errors,
            "generated_at": now
        }
        
        # LLM Enrichment (if requested)
        if req.include_llm and stock_details:
            try:
                # For single query, no duplicates
                selected_stocks, duplicates = select_stocks_for_enrichment(
                    {"duplicates": [], "ordered": result.matched_tickers},
                    stock_details,
                    max_stocks=req.llm_max_stocks
                )
                
                # Run LLM enrichment
                enriched_stocks = await enrich_stocks(
                    selected_stocks,
                    duplicates=duplicates,
                )
                
                # Sort by verdict
                enriched_sorted = sort_by_verdict(enriched_stocks)
                
                # Build enrichment summary
                verdicts = {}
                stages = {}
                successful = 0
                failed = 0
                
                for stock in enriched_stocks:
                    if stock.get("llm"):
                        successful += 1
                        verdict = stock["llm"].get("verdict", "UNKNOWN")
                        verdicts[verdict] = verdicts.get(verdict, 0) + 1
                        stage = stock["llm"].get("stage", "UNKNOWN")
                        stages[stage] = stages.get(stage, 0) + 1
                    else:
                        failed += 1
                
                summary = LLMEnrichmentSummary(
                    total_enriched=len(enriched_stocks),
                    successful=successful,
                    failed=failed,
                    cached=0,
                    verdicts=verdicts,
                    stages=stages,
                )
                
                # Convert to Pydantic models
                llm_enriched = [
                    LLMEnrichedStock(
                        stock=s.get("stock", ""),
                        tags=s.get("tags", []),
                        metrics=s.get("metrics", {}),
                        llm=s.get("llm"),
                    )
                    for s in enriched_sorted
                ]
                
                return QueryScreenerReportWithLLM(
                    **base_response,
                    llm_enriched=llm_enriched,
                    llm_summary=summary,
                )
                
            except Exception as e:
                logger.error("LLM enrichment failed: %s\n%s", e, traceback.format_exc())
                base_response["errors"].append(f"LLM enrichment failed: {str(e)}")
                return QueryScreenerReport(**base_response)
        
        return QueryScreenerReport(**base_response)


@router.get("/screen/help")
async def screen_help():
    """Get documentation for query-based screening.
    
    Returns available fields, supported operators, and example queries.
    """
    return {
        "description": "Query-based stock screening (Screener.in-style filtering)",
        "available_fields": get_available_fields(),
        "supported_operators": [">", "<", ">=", "<=", "=", "!="],
        "expression_support": {
            "arithmetic": ["1.05 * DMA 200", "Close - Open", "(High - Close) / High"],
            "constants": ["500", "1.05", "-10", "0.33"]
        },
        "example_queries": get_example_queries(),
        "multi_query_behavior": {
            "duplicates": "Stocks appearing in 2+ queries are identified",
            "ordering": "Results are ordered with duplicates first (higher conviction)",
            "deduplication": "Each stock appears only once in the final list"
        },
        "universe": {
            "default": "38 Shariah-compliant Indian stocks across 8 sectors",
            "custom": "Provide custom_tickers parameter (comma-separated) to screen any stocks",
            "dynamic": {
                "description": "Fetch stocks dynamically from NSE India or Screener.in",
                "parameters": {
                    "universe": "Predefined index/universe (nifty50, nifty500, nifty_it, etc.)",
                    "screener_url": "Screener.in public screen URL (e.g., https://www.screener.in/screens/71/)",
                    "screener_query": "Screener.in native query syntax"
                },
                "priority": "custom_tickers > screener_url > screener_query > universe > default"
            }
        },
        "api_usage": {
            "single_query": {
                "method": "POST",
                "endpoint": "/api/screen",
                "body": {
                    "query": "RSI > 50 AND RSI < 70 AND Market Capitalization > 500"
                }
            },
            "multi_query": {
                "method": "POST",
                "endpoint": "/api/screen",
                "body": {
                    "queries": [
                        "RSI > 50 AND RSI < 70",
                        "Current price > 1.05 * DMA 200",
                        "Price to earning < 25"
                    ]
                }
            },
            "with_dynamic_universe": {
                "method": "POST",
                "endpoint": "/api/screen",
                "body": {
                    "universe": "nifty500",
                    "query": "RSI > 50 AND Current price > 1.05 * DMA 200"
                }
            },
            "with_screener_url": {
                "method": "POST",
                "endpoint": "/api/screen",
                "body": {
                    "screener_url": "https://www.screener.in/screens/71/",
                    "query": "RSI > 50"
                }
            }
        }
    }


@router.get("/screen/universes")
async def get_universes():
    """Get available stock universes for screening.
    
    Returns list of predefined universes with descriptions.
    """
    from app.engine.stock_universe import get_available_universes
    return {
        "universes": get_available_universes(),
        "usage": {
            "parameter": "universe",
            "example": "POST /api/screen with body: {\"universe\": \"nifty50\", \"query\": \"RSI > 50\"}"
        },
        "alternative_sources": {
            "screener_url": "Provide a Screener.in public screen URL to fetch stocks from that screen",
            "screener_query": "Run a Screener.in native query to get matching stocks",
            "custom_tickers": "Comma-separated list of ticker symbols (highest priority)"
        }
    }


@router.post("/screen/validate")
async def validate_screen_query(query: str):
    """Validate a query string without executing it.
    
    Returns validation status, any errors, and suggestions.
    """
    is_valid, errors = validate_query(query)
    
    return {
        "query": query,
        "is_valid": is_valid,
        "errors": errors if errors else [],
        "suggestions": [] if is_valid else [
            "Use AND to combine conditions (e.g., 'RSI > 50 AND PE < 30')",
            "Supported operators: >, <, >=, <=, =, !=",
            "Field names are case-insensitive",
            "Use 'DMA 200' or 'SMA 200' for 200-day moving average"
        ],
        "available_fields": get_available_fields() if not is_valid else None
    }


# -----------------------------------------------------------------------------
# LLM Cache Management Endpoints
# -----------------------------------------------------------------------------

@router.get("/llm/cache")
async def llm_cache_stats():
    """Get LLM cache statistics.
    
    Returns current cache size, max size, TTL, and hit rate info.
    """
    stats = get_llm_cache_stats()
    return {
        "cache": stats,
        "description": "LLM response cache with 1-hour TTL",
        "tips": [
            "Cache keys include date, so stale analysis is auto-invalidated daily",
            "Use DELETE /api/llm/cache to clear cache if needed"
        ]
    }


@router.delete("/llm/cache")
async def clear_llm_cache_endpoint():
    """Clear the LLM response cache.
    
    Useful when you want fresh LLM analysis for all stocks.
    """
    cleared = clear_llm_cache()
    return {
        "cleared": cleared,
        "message": f"Cleared {cleared} cached LLM responses"
    }
