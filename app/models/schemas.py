"""Pydantic schemas for request/response models — LLM-optimized decision-layer format.

No narrative explanations. No opinions. Structured signals only.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=30, description="Stock ticker symbol")
    position: Optional[str] = Field(None, description="Current position: long, short, or none")
    include_llm: bool = Field(
        default=False,
        description="Whether to include LLM analysis for this stock"
    )


# ── LLM-Optimized Decision-Layer Response Sections ──────────

class Meta(BaseModel):
    symbol: str
    company_name: str
    analysis_date: str
    timeframe: str = "swing"
    data_window_days: int
    currency: str = "USD"
    currency_symbol: str = "$"


class PriceSnapshot(BaseModel):
    current_price: float
    change: float
    change_pct: float
    open: float
    day_high: float
    day_low: float
    prev_close: float
    volume: int
    market_cap: Optional[float] = None
    distance_from_52w_high_pct: float
    distance_from_52w_low_pct: float


class TrendStructure(BaseModel):
    primary_trend: str
    daily_trend: str
    weekly_trend: str
    monthly_trend: str
    trend_alignment: str
    sma_positioning: str
    ma_50: Optional[float] = None
    ma_100: Optional[float] = None
    ma_200: Optional[float] = None
    crossover_signals: list[str] = []
    adx: float
    trend_strength: str
    higher_highs_lows: bool
    supertrend_signal: str


class MomentumSignals(BaseModel):
    rsi: float
    rsi_state: str
    macd_line: float
    signal_line: float
    histogram: float
    macd_signal: str
    momentum_acceleration: str


class VolumeIntelligence(BaseModel):
    current_volume: int
    avg_volume: int
    volume_ratio: float
    obv_trend: str
    accumulation_distribution: str
    vwap: float
    price_vs_vwap: str
    volume_confirmation: bool


class VolatilityRisk(BaseModel):
    atr: float
    atr_percent: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    bollinger_bandwidth: float
    bollinger_position: str
    volatility_regime: str


class SupportResistanceBlock(BaseModel):
    support_levels: list[float]
    resistance_levels: list[float]
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    breakout_probability: str
    fibonacci_levels: dict[str, float]
    fibonacci_trend: str
    patterns_detected: list[str] = []


class DerivedSignals(BaseModel):
    trend_confirmation: bool
    momentum_confirmation: bool
    volume_confirmation: bool
    risk_environment: str
    trend_maturity: str


class QuantScores(BaseModel):
    trend_score: int
    momentum_score: int
    volume_score: int
    volatility_score: int
    composite_score: int
    market_state: str


class TradeLevelEntry(BaseModel):
    label: str
    price: float
    basis: str
    confidence_percent: Optional[int] = None
    expected_move_multiple_atr: Optional[float] = None


class TradeLevels(BaseModel):
    strategy_horizon: str = "3-6 months"
    position_bias: str
    ideal_entry: float
    targets: list[TradeLevelEntry]
    stop_losses: list[TradeLevelEntry]
    risk_reward_ratio: float


# ── Main Response ────────────────────────────────────────────

class AnalysisReport(BaseModel):
    meta: Meta
    price_snapshot: PriceSnapshot
    trend_structure: TrendStructure
    momentum_signals: MomentumSignals
    volume_intelligence: VolumeIntelligence
    volatility_risk: VolatilityRisk
    support_resistance: SupportResistanceBlock
    derived_signals: DerivedSignals
    quant_scores: QuantScores
    trade_levels: TradeLevels
    chart_data: list[dict]
    generated_at: str
    llm_analysis: Optional["LLMAnalysis"] = Field(
        None,
        description="LLM-generated analysis (only present if include_llm=true)"
    )


# ── Stock Screener Models ────────────────────────────────────

class ScreenerRequest(BaseModel):
    capital: float = Field(100000, description="Investment capital in INR")
    max_risk_pct: float = Field(7.0, description="Maximum downside risk per stock (%)")
    horizon_months: int = Field(12, description="Investment horizon in months")
    top_n: int = Field(10, ge=1, le=100, description="Number of top stocks to return (increased for larger universes)")
    custom_tickers: Optional[str] = Field(None, description="Comma-separated ticker symbols (e.g., 'TCS.NS,INFY.NS,HCLTECH.NS'). If provided, overrides default universe.")
    
    # Dynamic Universe Selection
    universe: Optional[str] = Field(
        None,
        description="Stock universe to screen. Options: shariah_38 (default), nifty50, nifty100, nifty200, nifty500, nifty_midcap_100, nifty_smallcap_100, nifty_it, nifty_bank, nifty_pharma, nifty_auto, nifty_fmcg, nifty_metal, nifty_energy, nifty_infra, nifty_realty, all_nse"
    )
    screener_url: Optional[str] = Field(
        None,
        description="Screener.in public screen URL to fetch stocks from. E.g., 'https://www.screener.in/screens/71/'"
    )
    screener_urls: Optional[list[str]] = Field(
        None,
        description="Multiple Screener.in screen URLs. Stocks from all URLs are combined and deduplicated. E.g., ['https://www.screener.in/screens/71/', 'https://www.screener.in/screens/3625029/']"
    )
    screener_query: Optional[str] = Field(
        None,
        description="Screener.in native query to fetch stocks. E.g., 'Market Capitalization > 10000'. Note: Uses Screener.in syntax, not our query syntax."
    )
    
    # Query-based screening (Screener.in-style)
    query: Optional[str] = Field(
        None,
        description="Single query string for filtering stocks. E.g., 'RSI > 50 AND RSI < 70 AND Market Capitalization > 500'"
    )
    queries: Optional[list[str]] = Field(
        None,
        description="Multiple query strings for multi-query screening. Results are deduplicated and ordered (stocks appearing in multiple queries first)."
    )
    include_or: bool = Field(
        False,
        description="Whether to support OR conditions in queries. Default is AND-only."
    )
    
    # LLM Enrichment
    include_llm: bool = Field(
        False,
        description="Whether to include LLM analysis for top stocks. Adds structured AI insights including verdict, confidence, trend stage, and entry strategy."
    )
    llm_max_stocks: int = Field(
        15,
        ge=1,
        le=30,
        description="Maximum number of stocks to enrich with LLM analysis. Prioritizes duplicates (multi-query matches) first."
    )


class ScreenedStock(BaseModel):
    ticker: str
    company_name: str
    sector: str
    current_price: float
    market_cap_cr: Optional[float] = Field(None, description="Market cap in crores INR")
    pe_ratio: Optional[float] = None
    sector_avg_pe: Optional[float] = None
    pe_vs_sector: Optional[str] = None
    peg_ratio: Optional[float] = None
    revenue_growth_5y_pct: Optional[float] = None
    profit_growth_5y_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    free_cash_flow_cr: Optional[float] = None
    moat: str = "moderate"
    shariah_compliant: bool = True
    shariah_note: str = ""
    technical_trend: str = "neutral"
    risk_score: int = Field(5, ge=1, le=10)
    composite_score: float = Field(0, description="Multi-factor composite score")
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    target_bull: Optional[float] = None
    target_base: Optional[float] = None
    target_bear: Optional[float] = None
    allocation_pct: Optional[float] = None
    allocation_amount: Optional[float] = None
    fundamental_summary: str = ""
    growth_outlook: str = ""
    risk_factors: list[str] = []


class ScreenerReport(BaseModel):
    market_overview: str
    screening_criteria: dict
    stocks: list[ScreenedStock]
    trade_plan_summary: list[dict]
    portfolio_allocation: dict
    top_picks: list[dict]
    tickers_for_analysis: list[str] = Field(
        description="Ticker symbols ready to pass to /api/analyze"
    )
    failed_tickers: list[str] = Field(default=[], description="Tickers that failed HTTP 404 or other errors")
    generated_at: str


# ── Query-Based Screening Models ─────────────────────────────

class QueryResultItem(BaseModel):
    """Result of a single query."""
    query: str
    matched_tickers: list[str]
    total_screened: int
    errors: list[str] = []
    skipped_tickers: list[dict] = Field(
        default=[],
        description="Tickers that were skipped with reasons (missing fields, condition failures)"
    )


class QueryScreenerReport(BaseModel):
    """Response for query-based stock screening."""
    mode: str = Field(
        description="Screening mode: 'single_query' or 'multi_query'"
    )
    
    # Single query result
    query: Optional[str] = Field(None, description="The query string (for single query mode)")
    matched_tickers: list[str] = Field(
        default=[],
        description="Tickers that matched the query conditions"
    )
    total_screened: int = Field(
        0,
        description="Total number of stocks that were screened"
    )
    
    # Multi-query results
    duplicates: list[str] = Field(
        default=[],
        description="Tickers appearing in 2+ queries"
    )
    deduplicated: list[str] = Field(
        default=[],
        description="All unique matched tickers"
    )
    ordered: list[str] = Field(
        default=[],
        description="Ordered results: duplicates first, then remaining tickers"
    )
    query_breakdown: dict[str, list[str]] = Field(
        default={},
        description="Mapping of each query to its matched tickers"
    )
    query_results: list[QueryResultItem] = Field(
        default=[],
        description="Detailed results for each query"
    )
    
    # Stock details (optional, populated if requested)
    stock_details: list[dict] = Field(
        default=[],
        description="Detailed data for each matched stock (price, RSI, etc.)"
    )
    
    # Debug info
    skipped_tickers: list[dict] = Field(
        default=[],
        description="Sample of tickers that failed with reasons (for debugging)"
    )
    
    # Metadata
    available_fields: Optional[dict[str, list[str]]] = Field(
        None,
        description="Available fields grouped by category (included in validation errors)"
    )
    example_queries: Optional[list[str]] = Field(
        None,
        description="Example query strings (included in validation errors)"
    )
    errors: list[str] = Field(
        default=[],
        description="Any errors or warnings during query execution"
    )
    generated_at: str


# ── LLM Enrichment Models ────────────────────────────────────

class LLMStrengthSignals(BaseModel):
    """Strength indicators from LLM analysis."""
    trend_alignment: str = Field(description="Trend alignment assessment")
    momentum_quality: str = Field(description="Momentum quality assessment")
    volume_support: str = Field(description="Volume support assessment")
    price_structure: str = Field(description="Price structure assessment")


class LLMEntryStrategy(BaseModel):
    """Entry strategy from LLM analysis."""
    trigger: str = Field(description="Entry trigger condition")
    zone: str = Field(description="Entry price zone")
    position_size: str = Field(description="Position sizing recommendation")
    time_horizon: str = Field(description="Suggested holding period")


class LLMAnalysis(BaseModel):
    """Structured LLM analysis output for a stock."""
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
    strength_signals: LLMStrengthSignals = Field(
        description="Key strength indicators"
    )
    risk_flags: list[str] = Field(
        description="1-3 key risk factors to monitor"
    )
    entry_strategy: LLMEntryStrategy = Field(
        description="Recommended entry approach"
    )


class LLMEnrichedStock(BaseModel):
    """Stock with LLM enrichment."""
    stock: str = Field(description="Stock ticker symbol")
    tags: list[str] = Field(
        default=[],
        description="Classification tags (e.g., duplicate, momentum, breakout)"
    )
    metrics: dict = Field(
        default={},
        description="Full stock metrics from analysis"
    )
    llm: Optional[LLMAnalysis] = Field(
        None,
        description="LLM-generated analysis (None if enrichment failed or skipped)"
    )


class LLMEnrichmentSummary(BaseModel):
    """Summary of LLM enrichment results."""
    total_enriched: int = Field(description="Total stocks enriched")
    successful: int = Field(description="Successful LLM calls")
    failed: int = Field(description="Failed LLM calls")
    cached: int = Field(description="Results served from cache")
    verdicts: dict[str, int] = Field(
        default={},
        description="Count of each verdict type"
    )
    stages: dict[str, int] = Field(
        default={},
        description="Count of each stage type"
    )


class QueryScreenerReportWithLLM(QueryScreenerReport):
    """Query screener report with LLM enrichment."""
    llm_enriched: list[LLMEnrichedStock] = Field(
        default=[],
        description="Stocks enriched with LLM analysis"
    )
    llm_summary: Optional[LLMEnrichmentSummary] = Field(
        None,
        description="Summary of LLM enrichment results"
    )
