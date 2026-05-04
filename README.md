# StockAnalyzer — Technical Analysis & Multi-Factor Stock Screener

A full-stack Python web application with **three integrated UI modes**:

1. **Technical Analysis** — Institutional-grade analysis on any stock ticker worldwide (US, Indian NSE/BSE, London, Hong Kong, etc.) with interactive candlestick charts
2. **Query Filter** — Screener.in-style filtering with custom queries like `RSI > 50 AND Current price > 1.05 * DMA 200` across dynamic stock universes (Nifty 50/100/200/500, F&O, sector indices)
3. **Stock Screener** — Multi-factor screening with composite scoring, trade plans, and portfolio allocation

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Three UI Modes](#three-ui-modes)
- [Beginner's Guide: Understanding the Concepts](#beginners-guide-understanding-the-concepts)
- [Tech Stack](#tech-stack)
- [Project Architecture](#project-architecture)
- [How Each File Works (Beginner Walkthrough)](#how-each-file-works-beginner-walkthrough)
- [Technical Indicators Implemented](#technical-indicators-implemented-from-scratch)
- [Stock Screener Feature](#stock-screener-feature)
- [Query-Based Screening](#query-based-screening)
- [Dynamic Stock Universes](#dynamic-stock-universes)
- [API Endpoints](#api-endpoints)
- [Target Confidence Model](#target-confidence-model)
- [Key Design Decisions](#key-design-decisions)
- [Getting Started](#getting-started)
- [Supported Markets](#supported-markets)
- [Troubleshooting](#troubleshooting)
- [Frontend Features](#frontend-features)

---

## What This Project Does

### Feature 1: Technical Analysis

Enter a stock ticker (e.g. `AAPL`, `RELIANCE.NS`, `TCS.BO`) and the system:

1. **Fetches 2 years of daily OHLCV data** from Yahoo Finance via `yfinance`
2. **Computes 15+ technical indicators** from scratch using `pandas` and `numpy` — no TA libraries
3. **Generates a structured analysis report** with 10 sections covering trend, momentum, volume, volatility, support/resistance, Fibonacci, chart patterns, quant scores, derived signals, and trade levels
4. **Renders an interactive candlestick chart** using TradingView's Lightweight Charts with overlaid moving averages, Bollinger Bands, support/resistance lines, and trade level markers
5. **Computes probabilistic target confidence** using a 7-factor institutional model (trend, momentum, volume, volatility feasibility, distance decay, trend maturity, market regime)
6. **Returns everything as a single JSON API response** — optimized for both human display and LLM consumption

### Feature 2: Query Filter (NEW)

Click the "Query Filter" tab and:

1. **Write Screener.in-style queries** — natural language conditions like `RSI > 50 AND Current price > 1.05 * DMA 200`
2. **Select stock universe** — Nifty 50/100/200/500, All NSE/F&O (~500 stocks), Shariah-38, or custom tickers
3. **Run filter** — parallel data fetching for 500+ stocks completes in ~30 seconds
4. **View matched stocks** — clickable ticker badges, detailed table with RSI, DMA50/200, 52W High/Low, Market Cap, P/E
5. **Transfer to Screener** — click "Use in Screener →" to run full multi-factor analysis on filtered results

### Feature 3: Stock Screener

Click the "Stock Screener" tab and the system:

1. **Screens any stock universe** — default Shariah-38, or custom tickers (including those from Query Filter)
2. **Fetches live fundamental data** (P/E, PEG, D/E ratio, ROE, operating margin, revenue/earnings growth, free cash flow) for each stock via `yfinance`
3. **Computes a composite score (0–100)** using 6 factors: valuation, growth, financial health, technical momentum, cash flow strength, and operating margin
4. **Assesses competitive moat** (strong / moderate / weak), **risk score** (1–10), and **Shariah compliance**
5. **Generates trade levels** (entry zone, stop-loss, bull/base/bear targets) for each stock
6. **Creates a risk-weighted portfolio allocation** across the top-ranked stocks
7. **Returns top 3 conviction picks** with detailed reasoning
8. **Integrates with Technical Analysis** — click "Analyze" on any screened stock to run full technical analysis

---

## Three UI Modes

The application provides three distinct modes accessible via navigation tabs:

| Mode | Color | Purpose | Key Features |
|------|-------|---------|--------------|
| **Technical Analysis** | Blue | Deep-dive single stock analysis | 10-section report, candlestick chart, trade levels with confidence |
| **Query Filter** | Green | Filter stocks by custom conditions | Screener.in-style queries, multiple universes, transfer to screener |
| **Stock Screener** | Purple | Multi-factor ranking & portfolio allocation | Composite scoring, moat assessment, risk-weighted allocation |

### Integrated Workflow

The most powerful workflow combines Query Filter → Screener → Analysis:

```
1. Query Filter: "Market Cap > 500 AND RSI > 50 AND RSI < 70 AND Current price > 1.05 * DMA 200"
   → Returns 57 matched stocks from All NSE

2. Click "Use in Screener →"
   → Transfers 57 tickers to Screener mode

3. Screener analyzes fundamentals + technicals
   → Returns top 30 ranked with composite scores, trade plans, portfolio allocation

4. Click "Analyze" on top pick
   → Full technical analysis with chart, targets, confidence
```

---

## Beginner's Guide: Understanding the Concepts

If you're new to programming or stock analysis, here's what each major term means:

### Stock Market Basics

| Term | What It Means |
|------|---------------|
| **Ticker** | A short code for a stock, e.g. `AAPL` = Apple, `TCS.NS` = TCS on NSE |
| **OHLCV** | Open, High, Low, Close, Volume — the 5 data points recorded for each trading day |
| **NSE / BSE** | National Stock Exchange / Bombay Stock Exchange — India's two main exchanges |
| **Bull / Bear** | Bull = prices going up; Bear = prices going down |
| **P/E Ratio** | Price-to-Earnings — how much investors pay per ₹1 of earnings. Lower = cheaper stock |
| **Market Cap** | Total value of a company = share price × number of shares |

### Technical Analysis Basics

| Term | What It Means |
|------|---------------|
| **Moving Average (MA)** | The average price over the last N days. Smooth out noise to show the trend |
| **RSI** | Relative Strength Index (0–100). Above 70 = overbought (may fall), below 30 = oversold (may rise) |
| **MACD** | Moving Average Convergence Divergence — shows momentum direction and acceleration |
| **Support** | A price level where the stock tends to stop falling (buyers step in) |
| **Resistance** | A price level where the stock tends to stop rising (sellers step in) |
| **Bollinger Bands** | A volatility band around a moving average — when bands are wide, volatility is high |
| **ATR** | Average True Range — measures how much a stock moves per day on average |
| **Fibonacci Levels** | Key percentage retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) used to predict support/resistance |

### Fundamental Analysis Basics (Used by Screener)

| Term | What It Means |
|------|---------------|
| **ROE** | Return on Equity — how much profit a company makes with shareholders' money. Higher = better |
| **D/E Ratio** | Debt-to-Equity — how much debt vs. equity a company has. Lower = less risky |
| **Operating Margin** | Percentage of revenue left after operating costs. Higher = more efficient |
| **PEG Ratio** | P/E divided by growth rate. Below 1 = stock is cheap relative to its growth |
| **Free Cash Flow** | Cash left after all expenses — the actual money a company generates |
| **Moat** | Competitive advantage — like a castle's moat, it protects the company from competitors |
| **Shariah-Compliant** | Investments that follow Islamic finance principles — no alcohol, gambling, excessive debt, interest-based banking |

### How the Scoring Works (Plain English)

The screener gives each stock a **composite score from 0 to 100**:

- Starts at 50 (neutral)
- Gets **bonus points** for: cheap valuation, high growth, low debt, high ROE, bullish trend, positive cash flow, good margins
- Loses **points** for: expensive valuation, high debt, poor growth, bearish trend, negative cash flow
- The top-scoring stocks become your recommended picks

---

## Tech Stack

| Layer       | Technology                                   | What It Does (for beginners)                    |
|-------------|----------------------------------------------|-------------------------------------------------|
| Backend     | **FastAPI** (async Python web framework)     | Handles HTTP requests, serves the API           |
| Data Source | **yfinance** (Yahoo Finance API wrapper)     | Fetches stock prices and fundamental data       |
| NSE Data    | **httpx** (HTTP client for NSE India API)    | Fetches index constituents, F&O stocks          |
| Computation | **pandas** + **numpy** (no external TA libs) | Number crunching for indicators and analysis    |
| Parallelism | **ThreadPoolExecutor** (concurrent.futures)  | Parallel data fetching for 500+ stocks          |
| Validation  | **Pydantic** v2 (schema models)              | Ensures data has the right shape and types      |
| Caching     | **cachetools** (in-memory TTL cache)         | Remembers recent results to avoid re-fetching   |
| Frontend    | **Alpine.js** + **Tailwind CSS** (SPA)       | Interactive UI without heavy frameworks         |
| Charting    | **TradingView Lightweight Charts** v4        | Renders the candlestick chart in the browser    |
| Server      | **Uvicorn** (ASGI server)                    | Runs the Python web app                         |

### What These Dependencies Are (requirements.txt)

```
fastapi==0.115.6       → The web framework (like Flask but faster and async)
uvicorn[standard]==0.34.0 → The server that runs FastAPI
yfinance>=1.2.0        → Downloads stock data from Yahoo Finance for free
pandas==2.2.3          → Data manipulation library (think: Excel in Python)
numpy==2.2.1           → Math library for fast number crunching
pydantic==2.10.4       → Data validation — makes sure API inputs/outputs are correct
cachetools==5.5.1      → Caching library — avoids re-downloading the same data
python-dotenv==1.0.1   → Loads environment variables from .env files
httpx==0.28.1          → HTTP client for NSE India API (index constituents)
```

---

## Project Architecture

```
stock-analyzer/
├── requirements.txt                # Python dependencies (what libraries to install)
├── app/
│   ├── __init__.py                 # Makes 'app' a Python package (can be empty)
│   ├── main.py                     # FastAPI app startup: CORS, static files, routing
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # API endpoint definitions (/analyze, /screen, etc.)
│   ├── engine/                     # All the computation logic lives here
│   │   ├── __init__.py
│   │   ├── analyzer.py             # Main orchestrator — runs the full analysis pipeline
│   │   ├── data_fetcher.py         # yfinance wrapper with auto-resolve (.NS/.BO)
│   │   ├── indicators.py           # RSI, MACD, BB, ADX, SuperTrend, ATR (all manual)
│   │   ├── fibonacci.py            # Fibonacci retracement levels
│   │   ├── support_resistance.py   # Pivot-based S/R detection
│   │   ├── patterns.py             # Chart pattern recognition
│   │   ├── trend.py                # Multi-timeframe trend analysis
│   │   ├── volume.py               # OBV, VWAP, A/D, volume confirmation
│   │   ├── trade_plan.py           # Trade level computation with confidence
│   │   ├── screener.py             # ★ Stock screener engine (multi-factor scoring)
│   │   ├── query_engine.py         # ★ Query parser and evaluator (Screener.in-style)
│   │   └── stock_universe.py       # ★ Dynamic universe fetcher (NSE indices, F&O)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic v2 request/response models
│   ├── cache/
│   │   ├── __init__.py
│   │   └── memory_cache.py         # TTL-based in-memory cache (cachetools)
│   └── static/                     # Frontend files served to the browser
│       ├── index.html              # Single-page app (Alpine.js + Tailwind)
│       ├── css/styles.css          # Custom dark/light theme styles
│       └── js/app.js               # Chart rendering, screener UI, all frontend logic
```

### How the Technical Analysis Pipeline Works

```
User enters ticker (e.g. "RELIANCE.NS")
       │
       ▼
  routes.py  →  POST /api/analyze
       │
       ▼
  analyzer.py (orchestrator — calls all engine modules)
       │
       ├── data_fetcher.py  →  yfinance (2yr daily + weekly + monthly OHLCV)
       ├── indicators.py    →  RSI, MACD, BB, ADX, SuperTrend, ATR
       ├── trend.py         →  multi-timeframe trend classification
       ├── volume.py        →  OBV, VWAP, A/D analysis
       ├── fibonacci.py     →  retracement levels
       ├── support_resistance.py → pivot S/R levels
       ├── patterns.py      →  chart pattern detection
       ├── trade_plan.py    →  entry, targets, stop-losses, confidence
       │
       ▼
  Assembles AnalysisReport (Pydantic model)
  + computes quant scores, derived signals, trade levels with confidence
       │
       ▼
  Returns JSON → Frontend renders dashboard + candlestick chart
```

### How the Stock Screener Pipeline Works

```
User clicks "Run Screener" (optionally adjusts capital, risk%, top N)
or receives tickers from Query Filter via "Use in Screener →"
       │
       ▼
  routes.py  →  POST /api/screen
       │
       ├── If query provided → query_engine.py (Screener.in-style filtering)
       │   ├── stock_universe.py → Fetch dynamic universe (NSE indices)
       │   ├── Parallel data fetch → ThreadPoolExecutor (20 workers)
       │   ├── Parse and evaluate conditions
       │   └── Return matched tickers
       │
       └── If no query → screener.py (multi-factor scoring)
           │
           For each stock (parallel):
           ├── _fetch_fundamentals()    →  yfinance (P/E, ROE, D/E, margins, FCF)
           ├── fetch_historical()       →  1yr daily data for trend/RSI
           ├── analyse_trend()          →  bullish / neutral / bearish
           ├── compute_rsi()            →  RSI value
           ├── _compute_composite_score() → multi-factor score (0–100)
           ├── _assess_moat()           →  strong / moderate / weak
           ├── _assess_risk_score()     →  1–10 risk score
           ├── _shariah_check()         →  compliant or not + reason
           ├── _compute_trade_levels()  →  entry zone, SL, targets
           │
           ▼
  Sorts all stocks by composite score (highest first)
  Takes top N stocks
       │
       ├── Computes risk-weighted portfolio allocation (risk-inverse weighting)
       ├── Builds trade plan summary (entry/SL/target for each stock)
       ├── Identifies top 3 conviction picks with reasons
       │
       ▼
  Returns ScreenerReport JSON → Frontend renders screener dashboard
```

### How the Query Filter Pipeline Works (NEW)

```
User enters query in Query Filter tab
  e.g. "Market Capitalization > 500 AND RSI > 50 AND RSI < 70"
       │
       ▼
  app.js → runQuery() → POST /api/screen with query parameter
       │
       ▼
  routes.py → _run_query_screening()
       │
       ├── stock_universe.py → Fetch universe (e.g., all_nse = ~500 stocks)
       │   ├── NSE India API → Nifty 500 constituents
       │   ├── NSE India API → F&O stocks
       │   ├── NSE India API → Midcap/Smallcap 100
       │   └── Deduplicate and merge
       │
       ├── query_engine.py → Pre-fetch data in parallel
       │   ├── ThreadPoolExecutor (20 workers)
       │   ├── data_fetcher.py → yfinance (2yr OHLCV + info)
       │   └── Cache results for subsequent requests
       │
       ├── query_engine.py → Evaluate conditions
       │   ├── Tokenize query (@@field@@ markers)
       │   ├── Parse conditions (field, operator, expression)
       │   ├── Compute indicators (RSI, SMA) for each stock
       │   ├── Evaluate arithmetic expressions safely
       │   └── Filter stocks passing ALL conditions
       │
       └── Build stock_details for matched tickers (parallel)
           │
           ▼
  Returns QueryScreenerReport → Frontend renders results
       │
       ├── Click ticker → Switch to Analysis mode, run analysis
       └── Click "Use in Screener →" → Transfer to Screener mode
```

---

## How Each File Works (Beginner Walkthrough)

### `app/main.py` — Application Entry Point

This is where the app starts. It:
- Creates the FastAPI application instance
- Adds **CORS middleware** (allows the browser to call the API)
- Mounts the `static/` folder so HTML/CSS/JS files are served to browsers
- Registers all API routes from `routes.py`
- Adds `no-cache` headers so browsers always get the latest code during development

### `app/api/routes.py` — API Endpoints

Defines 5 URL endpoints:
- `POST /api/analyze` — Takes a ticker, runs full technical analysis, returns JSON
- `POST /api/screen` — Runs the stock screener, returns ranked stocks with scores
- `GET /api/quote/{ticker}` — Quick price quote for a single stock
- `GET /api/health` — Returns `{"status": "ok"}` — used to check if the server is running
- `GET /` — Serves the HTML dashboard

### `app/engine/analyzer.py` — Analysis Orchestrator

The "brain" of technical analysis. It:
1. Calls `data_fetcher.py` to download OHLCV data
2. Calls each indicator module (RSI, MACD, etc.)
3. Calls trend, volume, fibonacci, S/R, and pattern modules
4. Assembles everything into a single `AnalysisReport` object
5. Computes quant scores (trend/momentum/volume/volatility on a -3 to +3 scale)
6. Computes derived signals (confirmations and divergences)
7. Computes trade levels with probabilistic confidence

### `app/engine/data_fetcher.py` — Data Fetcher

Downloads stock data from Yahoo Finance using `yfinance`. Key feature: **auto-resolve** — if you type `RELIANCE`, it automatically tries `RELIANCE.NS` and `RELIANCE.BO` to find the correct Indian listing.

### `app/engine/indicators.py` — Technical Indicators

Computes all indicators from raw OHLCV data using only `pandas` and `numpy`:
- Moving averages (SMA 50, 100, 200)
- RSI (14-period)
- MACD + Signal + Histogram
- Bollinger Bands (20, 2)
- ADX (14-period)
- SuperTrend
- ATR (14-period)

### `app/engine/screener.py` — Stock Screener Engine

The complete screening system:
- Contains a hardcoded **universe of 38 Shariah-compliant Indian stocks** in 8 sectors
- For each stock: fetches fundamentals, computes trend, calculates a composite score
- Scores stocks on: valuation (P/E vs sector), growth, financial health, technical momentum, cash flow, margins
- Ranks them and returns the top N with trade levels and portfolio allocation

### `app/engine/query_engine.py` — Query Parser & Evaluator (NEW)

The Screener.in-style query engine:
- **Tokenizes** queries using `@@key@@` field markers
- **Parses** conditions into structured `ParsedCondition` objects
- **Evaluates** arithmetic expressions safely (no `eval`)
- **Maps** 60+ field aliases to internal field names (e.g., "DMA 50" → "sma_50")
- **Computes** technical indicators (RSI, SMA) on-the-fly for each stock
- **Supports** parallel evaluation across 500+ stocks via ThreadPoolExecutor

### `app/engine/stock_universe.py` — Dynamic Universe Fetcher (NEW)

Fetches stock lists from external sources:
- **NSE India API** — Nifty 50/100/200/500, sector indices (IT, Bank, Pharma, etc.)
- **F&O Stocks** — All derivatives-eligible stocks from NSE
- **Screener.in** — Public screen URLs and native queries (requires login)
- **Caching** — 5-minute TTL to avoid repeated API calls
- **Session Management** — Authenticated Screener.in sessions with 1-hour expiry

### `app/engine/trade_plan.py` — Trade Level Calculator

Computes actionable trade levels: entry point, 3 price targets (T1, T2, T3), 3 stop-losses (SL1, SL2, SL3), risk-reward ratio, and confidence percentage for each target.

### `app/models/schemas.py` — Data Models

Defines the exact structure of every request and response using Pydantic:
- `AnalysisRequest` / `AnalysisReport` — for /api/analyze
- `ScreenerRequest` / `ScreenedStock` / `ScreenerReport` — for /api/screen
- Sub-models: `Meta`, `PriceSnapshot`, `TrendStructure`, `MomentumSignals`, etc.

### `app/cache/memory_cache.py` — Caching

Uses `cachetools.TTLCache` to store results in memory:
- **Data cache** (5-minute TTL) — avoids re-downloading stock data from Yahoo
- **Analysis cache** (10-minute TTL) — avoids re-computing the same analysis

### `app/static/index.html` — Frontend UI

A single HTML file that is the entire frontend. Uses:
- **Alpine.js** for reactivity (like a lightweight React/Vue)
- **Tailwind CSS** for styling (utility-first CSS classes)
- **TradingView Lightweight Charts** for candlestick charts
- Two modes: Technical Analysis tab and Stock Screener tab

### `app/static/js/app.js` — Frontend Logic

Contains all the JavaScript logic:
- `analyze()` — calls `/api/analyze` and renders the report + chart
- `runScreener()` — calls `/api/screen` and renders the screener results
- `switchMode()` — toggles between Analysis and Screener tabs
- Chart rendering with overlaid MAs, Bollinger Bands, S/R lines, trade level markers

### `app/static/css/styles.css` — Styles

Custom CSS for dark/light theme support, card layouts, loading animations, and responsive design.

---

## Technical Indicators Implemented (From Scratch)

All indicators are computed manually using pandas/numpy — no `ta-lib` or `pandas-ta`:

| Indicator                     | What It Measures                               |
|-------------------------------|------------------------------------------------|
| SMA (50, 100, 200)           | Moving averages for trend direction            |
| RSI (14-period)              | Relative Strength Index — overbought/oversold  |
| MACD + Signal + Histogram    | Momentum direction and acceleration            |
| Bollinger Bands (20,2)       | Volatility envelope around SMA                 |
| ADX (14-period)              | Trend strength (0–100 scale)                   |
| SuperTrend                   | Trend-following buy/sell signal                |
| ATR (14-period)              | Average True Range — volatility measure        |
| OBV                          | On-Balance Volume — accumulation/distribution  |
| VWAP                         | Volume-Weighted Average Price                  |
| Accumulation/Distribution    | Money flow based on close position in range    |
| Fibonacci Retracement        | Key retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) |
| Support & Resistance         | Pivot-based horizontal levels                  |
| Higher Highs / Higher Lows   | Structural trend detection                     |
| Chart Patterns               | Double top/bottom, head & shoulders, etc.      |

---

## Stock Screener Feature

### Overview

The screener evaluates stocks across multiple factors and produces a ranked list of top picks with trade plans and portfolio allocation. It can screen:

1. **Custom Tickers** — Any comma-separated list (e.g., from Query Filter)
2. **Dynamic Universes** — Nifty 50/100/200/500, F&O stocks, sector indices
3. **Default Universe** — 38 Shariah-compliant Indian equities (8 sectors)

### Default Stock Universe (38 Shariah-Compliant Stocks)

| Sector | Stocks |
|--------|--------|
| **IT / Software** (8) | TCS, Infosys, HCL Tech, Wipro, Tech Mahindra, LTIMindtree, Persistent Systems, Coforge |
| **Pharmaceuticals** (6) | Sun Pharma, Dr. Reddy's, Cipla, Divi's Lab, Aurobindo Pharma, Biocon |
| **Healthcare** (2) | Apollo Hospitals, Max Healthcare |
| **Manufacturing / Engineering** (6) | L&T, Siemens, ABB India, Havells, Bharat Electronics, Cummins India |
| **Consumer Goods** (6) | Hindustan Unilever, Nestle India, Dabur, Marico, Britannia, Tata Consumer |
| **Infrastructure / Logistics** (3) | Adani Ports, Container Corp, Delhivery |
| **Renewable Energy** (3) | Tata Power, Adani Green, NHPC |
| **Automotive** (4) | Eicher Motors, Mahindra & Mahindra, Maruti Suzuki, Bajaj Auto |

### Screening Criteria

| Criterion | Preferred Value |
|-----------|----------------|
| Market Cap | Mid-cap and large-cap |
| Revenue Growth | Positive trend |
| Debt-to-Equity | < 0.8 |
| Return on Equity | > 15% |
| Operating Margin | Stable and positive |
| Valuation (P/E) | Reasonable vs. sector average |
| Shariah Compliance | Halal-friendly sectors; D/E < 33% preferred |

### Composite Score Breakdown (0–100)

| Factor | Max Impact | How It's Scored |
|--------|-----------|-----------------|
| **Valuation** | ±15 pts | P/E discount vs sector average, PEG ratio bonus |
| **Growth** | ±15 pts | Revenue growth (±10), earnings growth (±5) |
| **Financial Health** | ±15 pts | Debt-to-equity (±10), ROE (±5) |
| **Technical Momentum** | ±10 pts | Trend direction (±7), RSI oversold/overbought (±5) |
| **Cash Flow** | ±5 pts | Positive or negative free cash flow |
| **Operating Margin** | ±5 pts | Margin above 20% vs below 0% |

Base score starts at 50. Final score clamped to 0–100.

### Portfolio Allocation Method

Uses **risk-inverse weighting**: stocks with lower risk scores get a higher allocation.

```
weight_i = (1 / risk_score_i) / Σ(1 / risk_score_j)
allocation_i = capital × weight_i
```

### Screener Request Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `capital` | 100,000 | Investment capital in INR |
| `max_risk_pct` | 7.0 | Maximum downside risk per stock (%) |
| `horizon_months` | 12 | Investment horizon in months |
| `top_n` | 10 | Number of top stocks to return (1–30) |

### Screener Response Structure

```json
{
  "market_overview":       "Summary of market being screened",
  "screening_criteria":    { "market_cap": "...", "revenue_growth": "...", ... },
  "stocks":                [ { "ticker": "...", "composite_score": 72.5, ... } ],
  "trade_plan_summary":    [ { "ticker": "...", "entry_zone": "...", "stop_loss": "...", ... } ],
  "portfolio_allocation":  { "total_capital": 100000, "stocks": [...], ... },
  "top_picks":             [ { "rank": 1, "ticker": "...", "conviction_reasons": [...] } ],
  "tickers_for_analysis":  ["DRREDDY.NS", "TCS.NS", ...],
  "generated_at":          "2026-03-05T12:00:00+00:00"
}
```

The `tickers_for_analysis` array can be passed directly to `/api/analyze` for deeper technical analysis on any screened stock.

---

## Query-Based Screening

### Overview

A **Screener.in-style query engine** available via both:
- **UI**: Query Filter tab with form input, universe selector, and results display
- **API**: `POST /api/screen` with query parameter

Supports arithmetic expressions, multiple conditions with AND logic, and multi-query execution with duplicate detection.

### How It Works

1. **Parse** — Query string is parsed into structured conditions
2. **Fetch** — Stock data (OHLCV + fundamentals) is fetched for each ticker
3. **Compute** — Technical indicators (RSI, SMA, etc.) are calculated
4. **Evaluate** — Each condition is evaluated against the stock data
5. **Filter** — Only stocks passing ALL conditions are returned

### Supported Fields

| Category | Fields | Availability |
|----------|--------|-------------|
| **Price** | Current price, Close, Open, High, Low, 52 week high/low | ✅ Always |
| **Moving Averages** | DMA 50, DMA 200, SMA 50, SMA 200 | ✅ Always (computed) |
| **Momentum** | RSI | ✅ Always (computed) |
| **Volume** | Volume, Volume 1week average | ✅ Always |
| **Returns** | Return over 3months | ✅ Always (computed) |
| **Valuation** | Price to earning, PEG ratio, Market Capitalization | ⚠️ Usually available |
| **Financial Health** | Debt to equity, ROE, ROCE, Operating margin | ⚠️ Often available |
| **Growth** | Revenue growth, Earnings growth | ⚠️ Sometimes missing |
| **Other** | Free cash flow, Beta | ⚠️ Sometimes missing |

### Supported Operators

| Operator | Meaning |
|----------|--------|
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater than or equal |
| `<=` | Less than or equal |
| `=` | Equal |
| `!=` | Not equal |

### Expression Support

You can use arithmetic in conditions:

```
# Multiply by constant
Current price > 1.05 * DMA 200

# Percentage calculations
100 * ((High price - Current price) / High price) < 5

# Subtraction
Current price / Low price - 1 > 1
```

**Note:** Use spaces around operators. Write `- 1` not `-1` to avoid parsing issues.

### Example Queries

**Momentum Breakout:**
```
RSI > 50 AND RSI < 70 AND Current price > 1.05 * DMA 200
```

**Value + Quality:**
```
Price to earning < 25 AND Debt to equity < 0.5 AND ROE > 15
```

**Near 52-Week High:**
```
100 * ((High price - Current price) / High price) < 5 AND
100 * ((High price - Current price) / High price) > 0 AND
Volume > 100000
```

**Price Doubled from Low:**
```
100 * (Current price / Low price - 1) > 100 AND Current price > 100
```

### Using Query Filter UI (NEW)

1. **Navigate**: Click "Query Filter" tab (green) in the navigation bar
2. **Enter Query**: Type your filter conditions in the textarea
   - Use example buttons to auto-populate common queries
   - Expand "Available Fields & Operators" for reference
3. **Select Universe**: Choose from dropdown:
   - All NSE / F&O (~500 stocks) — best for broad screening
   - Nifty 500/200/100/50 — specific index constituents
   - Shariah-38 — default compliant universe
4. **Set Max Results**: Limit how many stocks to return (default: 100)
5. **Run Filter**: Click the green button and wait (~30 seconds for 500 stocks)
6. **Review Results**:
   - Summary card shows match count
   - Ticker badges — click any to run technical analysis
   - Table shows Price, RSI, DMA distances, 52W levels, fundamentals
7. **Transfer to Screener**: Click "Use in Screener →" to:
   - Auto-populate matched tickers in Screener mode
   - Run full multi-factor analysis with composite scoring
   - Generate portfolio allocation for filtered subset

### Single Query API

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RSI > 50 AND RSI < 70 AND Market Capitalization > 500",
    "top_n": 10
  }'
```

**Response:**
```json
{
  "mode": "single_query",
  "query": "RSI > 50 AND RSI < 70 AND Market Capitalization > 500",
  "matched_tickers": ["TCS.NS", "INFY.NS", "HCLTECH.NS"],
  "total_screened": 38,
  "stock_details": [
    {"ticker": "TCS.NS", "close": 4150.50, "rsi": 55.2, "market_cap": 15234.5}
  ],
  "skipped_tickers": [
    {"ticker": "WIPRO.NS", "reasons": ["Failed: RSI=72.5 > 70"]}
  ],
  "generated_at": "2026-04-26T10:30:00+00:00"
}
```

### Multi-Query API

Run multiple queries and find stocks appearing in multiple results (higher conviction):

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      "RSI > 50 AND RSI < 70",
      "Current price > 1.05 * DMA 200",
      "Price to earning < 30 AND Debt to equity < 0.5"
    ],
    "top_n": 10
  }'
```

**Response:**
```json
{
  "mode": "multi_query",
  "duplicates": ["TCS.NS", "INFY.NS"],
  "deduplicated": ["TCS.NS", "INFY.NS", "DRREDDY.NS", "SUNPHARMA.NS"],
  "ordered": ["TCS.NS", "INFY.NS", "DRREDDY.NS", "SUNPHARMA.NS"],
  "query_breakdown": {
    "RSI > 50 AND RSI < 70": ["TCS.NS", "INFY.NS", "DRREDDY.NS"],
    "Current price > 1.05 * DMA 200": ["TCS.NS", "SUNPHARMA.NS"],
    "Price to earning < 30 AND Debt to equity < 0.5": ["INFY.NS"]
  },
  "generated_at": "2026-04-26T10:30:00+00:00"
}
```

### Dynamic Stock Universe

By default, the screener uses a 38-stock Shariah-compliant universe. You can dynamically fetch stocks from:

1. **NSE India Indices** — Nifty 50, Nifty 500, Sector Indices, etc.
2. **F&O Stocks** — All NSE derivatives-eligible stocks (~200)
3. **Screener.in Screens** — Public screen URLs or native queries
4. **Custom Tickers** — Your own comma-separated list

#### Available Universes (UI + API)

| Universe | Description | Approx. Stocks |
|----------|-------------|----------------|
| `shariah_38` | Default Shariah-compliant universe | 38 |
| `all_nse` | Combined NSE + F&O + major indices | ~500 |
| `nifty50` | Nifty 50 index constituents | 50 |
| `nifty100` | Nifty 100 index constituents | 100 |
| `nifty200` | Nifty 200 index constituents | 200 |
| `nifty500` | Nifty 500 index constituents | 500 |
| `nifty_midcap_100` | Nifty Midcap 100 index | 100 |
| `nifty_smallcap_100` | Nifty Smallcap 100 index | 100 |
| `nifty_it` | Nifty IT sector index | 10 |
| `nifty_bank` | Nifty Bank index | 12 |
| `nifty_pharma` | Nifty Pharma index | 20 |
| `nifty_auto` | Nifty Auto index | 15 |
| `nifty_fmcg` | Nifty FMCG index | 15 |
| `nifty_metal` | Nifty Metal index | 15 |
| `nifty_energy` | Nifty Energy index | 10 |
| `nifty_infra` | Nifty Infrastructure index | 30 |
| `nifty_realty` | Nifty Realty index | 10 |

#### Using Universes in UI

1. **Query Filter tab** → Select universe from dropdown → Run Filter
2. **Stock Screener tab** → Results from Query Filter auto-populate custom tickers

#### Using Universes in API
| `nifty_energy` | Nifty Energy index | 10 |
| `nifty_infra` | Nifty Infrastructure index | 30 |
| `nifty_realty` | Nifty Realty index | 10 |
| `all_nse` | Combined major NSE indices | ~1000+ |

#### Screen with NSE Index

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "universe": "nifty500",
    "query": "RSI > 50 AND Current price > 1.05 * DMA 200",
    "top_n": 20
  }'
```

#### Screen with Screener.in URL

Use a public Screener.in screen URL to fetch stocks:

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "screener_url": "https://www.screener.in/screens/71/",
    "query": "RSI > 50",
    "top_n": 10
  }'
```

#### Screen with Screener.in Query

Run a Screener.in native query to fetch stocks, then apply your filter:

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "screener_query": "Market Capitalization > 10000",
    "query": "RSI > 50 AND RSI < 70",
    "top_n": 15
  }'
```

#### Priority Order

When multiple universe parameters are provided:
1. `custom_tickers` (highest priority)
2. `screener_url`
3. `screener_query`
4. `universe`
5. Default 38-stock Shariah universe (fallback)

#### Screener.in Authentication

Screener.in screens and queries **require login** to access. Set these environment variables before starting the server:

**Windows (PowerShell):**
```powershell
$env:SCREENER_USERNAME = "your-email@example.com"
$env:SCREENER_PASSWORD = "your-password"
uvicorn app.main:app --reload
```

**Windows (CMD):**
```cmd
set SCREENER_USERNAME=your-email@example.com
set SCREENER_PASSWORD=your-password
uvicorn app.main:app --reload
```

**Linux/Mac:**
```bash
export SCREENER_USERNAME="your-email@example.com"
export SCREENER_PASSWORD="your-password"
uvicorn app.main:app --reload
```

**Using .env file (recommended):**

Create a `.env` file in the project root:
```
SCREENER_USERNAME=your-email@example.com
SCREENER_PASSWORD=your-password
```

Then load it before starting:
```powershell
# PowerShell
Get-Content .env | ForEach-Object { if ($_ -match "^(.+?)=(.*)$") { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
uvicorn app.main:app --reload
```

Without credentials, Screener.in URLs and queries will fail with "requires login" warning, and the system will fall back to the default universe.

#### Get Available Universes

```bash
curl http://localhost:8000/api/screen/universes
```

### Field Name Reference

| Screener.in Style | Also Accepts |
|-------------------|-------------|
| Current price | Close, Price |
| DMA 50 | SMA 50, 50 DMA |
| DMA 200 | SMA 200, 200 DMA |
| Market Capitalization | Market cap, Mcap |
| Price to earning | PE ratio, PE, P/E |
| Debt to equity | D/E, DE ratio |
| Return on equity | ROE |
| Return on capital employed | ROCE |
| Return over 3months | 3 month return, 3m return |
| Volume 1week average | Avg volume, Average volume |
| YOY Quarterly profit growth | Earnings growth |
| High price | High |
| Low price | Low |

### Debugging Failed Queries

When no stocks match, check the `skipped_tickers` field in the response:

```json
"skipped_tickers": [
  {"ticker": "TCS.NS", "reasons": ["Missing field in 'ROCE'"]},
  {"ticker": "INFY.NS", "reasons": ["Failed: RSI=75.2 > 70"]}
]
```

Common issues:
- **Missing field** — The stock doesn't have that data (e.g., ROCE, PEG ratio)
- **Failed condition** — The stock has the data but doesn't meet the criteria

### Query Validation Endpoint

```bash
curl -X POST "http://localhost:8000/api/screen/validate?query=RSI%20%3E%2050"
```

### Help Endpoint

```bash
curl http://localhost:8000/api/screen/help
```

Returns all available fields, operators, and example queries.

---

## API Endpoints

| Method | Path               | Description                               |
|--------|--------------------|-------------------------------------------|
| GET    | `/`                | Main dashboard UI (SPA)                   |
| POST   | `/api/analyze`     | Full technical analysis (JSON)            |
| POST   | `/api/screen`      | Stock screener (multi-factor or query-based) |
| GET    | `/api/screen/help` | Query-based screening documentation       |
| GET    | `/api/screen/universes` | List available stock universes       |
| POST   | `/api/screen/validate` | Validate a query without executing    |
| GET    | `/api/quote/{sym}` | Quick price quote                         |
| GET    | `/api/health`      | Health check                              |

### Example: Technical Analysis

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

### Example: Stock Screener

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{"capital": 100000, "max_risk_pct": 7.0, "top_n": 10}'
```

Or with defaults (no body needed):

```bash
curl -X POST http://localhost:8000/api/screen
```

### Analysis Response Structure (10 Sections)

```
{
  "meta"                 → symbol, date, currency, data window
  "price_snapshot"       → current price, change%, open/high/low, 52w distances
  "trend_structure"      → primary/daily/weekly/monthly trend, MAs, ADX, crossovers
  "momentum_signals"     → RSI, MACD, momentum acceleration
  "volume_intelligence"  → volume ratio, OBV, A/D, VWAP
  "volatility_risk"      → ATR, Bollinger Bands, bandwidth, regime
  "support_resistance"   → S/R levels, Fibonacci, patterns
  "derived_signals"      → confirmations (trend/momentum/volume), risk environment
  "quant_scores"         → trend/momentum/volume/volatility scores (-3 to +3), composite
  "trade_levels"         → entry, 3 targets (T1-T3), 3 stop-losses (SL1-SL3), R:R ratio,
                           confidence_percent per target, ATR multiples
  "chart_data"           → 2 years of OHLCV for frontend chart rendering
}
```

---

## Target Confidence Model

Each trade target (T1, T2, T3) includes a **probabilistic confidence score** computed using:

```
confidence = trend_factor × momentum_factor × volume_factor
             × volatility_feasibility × maturity_multiplier × regime_multiplier
```

| Factor                  | Source Field                | Calculation                              |
|-------------------------|-----------------------------|-----------------------------------------|
| Trend Factor            | `quant_scores.trend_score`  | `score / 3`                             |
| Momentum Factor         | `momentum_score` + confirmation | `((score+1)/3) × 1.1 or 0.9`       |
| Volume Factor           | `volume_score` + confirmation   | `(score/3) × 1.05 or 0.85`         |
| Volatility Feasibility  | `atr_percent` + distance    | `exp(-distance / (2 × atr_pct))`        |
| Maturity Multiplier     | `trend_maturity`            | early=1.15, mid=1.0, late=0.8           |
| Regime Multiplier       | `market_state`              | bullish=1.1, neutral=1.0, bearish=0.85  |

Result is clamped between 5% and 95%.

---

## Key Design Decisions

| Decision | Reasoning |
|----------|-----------|
| No external TA library | All indicators computed from scratch to demonstrate understanding of the math |
| Pydantic v2 schemas | Type-safe validation, auto-generated OpenAPI docs |
| In-memory cache | Avoids hitting Yahoo Finance on repeated requests; TTL-based auto-expiry |
| Auto-resolve tickers | Bare ticker `RELIANCE` auto-tries `.NS` and `.BO` suffixes for Indian stocks |
| No-cache headers | Ensures browsers always serve fresh HTML/JS after code changes |
| LLM-optimized JSON | Flat structured signals (no prose) — can be fed directly to GPT/Claude for advice |
| Shariah-compliant universe | Pre-curated 38-stock watchlist from halal-friendly sectors only |
| Risk-inverse allocation | Lower-risk stocks get higher capital allocation automatically |
| Screener → Analyze integration | Screener's `tickers_for_analysis` plugs directly into `/api/analyze` |
| Query Filter → Screener flow | Filtered stocks can be transferred to full multi-factor screening |
| Parallel data fetching | ThreadPoolExecutor (20 workers) enables screening 500+ stocks in ~30 seconds |
| Dynamic universe fetching | NSE API integration fetches live index constituents (no hardcoded lists) |
| Safe expression evaluation | Query parser uses tokenization, not `eval()` — no security risks |
| Three-mode UI | Separates concerns: quick filter, deep analysis, portfolio allocation |

---

## Getting Started

### Prerequisites

- **Python 3.11+** (tested on 3.13) — [Download Python](https://www.python.org/downloads/)
- **pip** (comes with Python) — The package installer
- **A terminal** — Command Prompt, PowerShell (Windows), or Terminal (Mac/Linux)
- **A web browser** — Chrome, Firefox, Edge, etc.
- **Internet connection** — Required to fetch live stock data from Yahoo Finance

### Step-by-Step Installation

```bash
# 1. Clone the repository (or download and extract the ZIP)
git clone <repo-url>
cd stock-analyzer

# 2. (Recommended) Create a virtual environment
#    This keeps this project's packages separate from other Python projects
python -m venv venv

# 3. Activate the virtual environment
#    On Windows (Command Prompt):
venv\Scripts\activate
#    On Windows (PowerShell):
venv\Scripts\Activate.ps1
#    On Mac/Linux:
source venv/bin/activate

# 4. Install all required packages
pip install -r requirements.txt
```

### Running the Application

```bash
# Start the server
uvicorn app.main:app --host localhost --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://localhost:8000
INFO:     Started server process
```

Now open **http://localhost:8000** in your web browser.

### Using the Application

**Technical Analysis mode (default):**
1. Type a stock ticker in the search box (e.g. `TCS.NS`, `AAPL`, `RELIANCE`)
2. Click "Analyze" or press Enter
3. Wait for the report to load (fetches live data from Yahoo Finance)
4. Explore the candlestick chart, trend analysis, momentum signals, trade levels, etc.

**Query Filter mode (NEW):**
1. Click the "Query Filter" tab (green) at the top
2. Enter a filter query (e.g., `RSI > 50 AND RSI < 70 AND Market Cap > 500`)
3. Select a stock universe (All NSE, Nifty 500, etc.)
4. Click "Run Filter" and wait (~30 seconds for large universes)
5. Review matched stocks in the results table
6. Click any ticker badge to analyze it, OR
7. Click "Use in Screener →" to transfer results to the Screener

**Stock Screener mode:**
1. Click the "Stock Screener" tab (purple) at the top
2. (Optional) Enter custom tickers or use results from Query Filter
3. Adjust capital, risk %, and number of stocks
4. Click "Run Screener"
5. Wait for results (screens all stocks — may take 20–30 seconds on first run)
6. Review top picks, portfolio allocation, and trade plans
7. Click "Analyze" on any stock to switch to full technical analysis

**Recommended Workflow:**
```
Query Filter → Use in Screener → Analyze top picks
```

### Running in Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Interactive API Docs

FastAPI automatically generates interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

You can test all API endpoints directly from these pages — no external tools needed.

---

## Supported Markets

| Market     | Suffix  | Example          |
|------------|---------|------------------|
| US (NYSE/NASDAQ) | none | `AAPL`, `TSLA`  |
| India (NSE)      | `.NS` | `RELIANCE.NS`   |
| India (BSE)      | `.BO` | `TCS.BO`        |
| London           | `.L`  | `HSBA.L`        |
| Hong Kong        | `.HK` | `0005.HK`       |
| Tokyo            | `.T`  | `7203.T`        |

Indian tickers auto-resolve: entering `RELIANCE` will automatically try `RELIANCE.NS` and `RELIANCE.BO`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements.txt` — you haven't installed dependencies |
| `pip` not recognized | Make sure Python is installed and added to PATH. Try `python -m pip` instead |
| Port 8000 already in use | Use a different port: `uvicorn app.main:app --port 8001` |
| "No data found" for a ticker | Check the ticker symbol on [Yahoo Finance](https://finance.yahoo.com). Indian stocks need `.NS` or `.BO` suffix |
| Screener takes a long time | First run fetches data for 38 stocks — subsequent runs use cache (10 min TTL) |
| Query Filter takes 30+ seconds | Normal for 500 stocks — parallel fetching from Yahoo Finance has rate limits |
| "Rate limited" errors | Yahoo Finance rate limiting — wait 30 seconds and retry, or reduce universe size |
| "Missing field" in query results | That stock doesn't have the data (e.g., ROCE, PEG for some companies) |
| Virtual environment not activating | On Windows PowerShell, you may need: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Chart not rendering | Make sure you're using a modern browser (Chrome, Firefox, Edge). Clear browser cache if stuck |
| Query validation error | Check field name spelling, use spaces around operators (`RSI > 50` not `RSI>50`) |
| "Use in Screener" button not working | Make sure Query Filter has matched tickers (check results summary) |

---

## Frontend Features

The dashboard supports **three integrated modes** with seamless transitions:

### Technical Analysis Mode (Blue)
- Dark/light theme toggle
- Interactive candlestick chart with MA overlays, Bollinger Bands, S/R lines, and trade level markers
- Trend structure card with multi-timeframe alignment
- Momentum gauges (RSI + MACD)
- Volume intelligence with VWAP
- Fibonacci retracement bars
- Quant score heatmap
- Trade levels panel with confidence bars and ATR multiples
- Quick ticker shortcuts (US: AAPL, TSLA, MSFT | India: RELIANCE.NS, TCS.NS, INFY.NS)

### Query Filter Mode (Green) — NEW
- **Query Input**: Textarea for Screener.in-style queries
- **Example Queries**: Click-to-use templates for Growth Momentum, Near 52-Week High, Quality + Momentum, Oversold Large Caps
- **Stock Universe Dropdown**:
  - All NSE / F&O (~500 stocks)
  - Nifty 500, Nifty 200, Nifty 100, Nifty 50
  - Shariah-38 (default compliant universe)
- **Available Fields Reference**: Expandable documentation of all supported fields
- **Progress Indicator**: Step-by-step progress during parallel data fetching
- **Results Display**:
  - Summary card with match count
  - **"Use in Screener →"** button to transfer matched tickers
  - Clickable ticker badges for quick technical analysis
  - Detailed table: Price, RSI, vs DMA50/200, 52W High/Low, Market Cap, P/E
- **Error Display**: Query validation errors with helpful suggestions

### Stock Screener Mode (Purple)
- **Custom Tickers Input**: Enter comma-separated tickers (auto-populated from Query Filter)
- Configurable capital (₹), max risk %, and top N stocks
- Failed tickers display with expandable details
- Market overview summary
- Top 3 conviction picks with reasoning
- Screening summary table (score, P/E, trend, risk, moat)
- Trade plan table (entry, SL, targets for each stock)
- Portfolio allocation breakdown (risk-weighted)
- Expandable detailed analysis per stock
- "Analyze" button on each stock — switches to full technical analysis

### UI/UX Features
- **Responsive Design**: Works on desktop and tablet
- **Dark/Light Theme**: Toggle in header, persists across sessions
- **Smooth Transitions**: Alpine.js-powered animations between modes
- **Progress Feedback**: Loading spinners and step indicators for long operations
- **Cache-Aware**: 5-minute data cache, 10-minute analysis cache
- **Real-Time Updates**: Last updated timestamps in header

---

## Performance Features

### Parallel Data Fetching

The application uses `ThreadPoolExecutor` for parallel data fetching:

- **Query Filter**: Fetches 500+ stocks in parallel (20 workers max)
- **Stock Screener**: Parallel fundamental + technical data fetch
- **Stock Details**: Parallel price data preparation for matched tickers

Typical performance:
- Nifty 500 query filter: ~25-30 seconds (parallel)
- Shariah-38 screener: ~15-20 seconds (parallel)
- Single stock analysis: ~2-3 seconds

### Caching Strategy

| Cache | TTL | Purpose |
|-------|-----|---------|
| Data Cache | 5 min | Avoids re-downloading OHLCV from Yahoo Finance |
| Analysis Cache | 10 min | Avoids re-computing full analysis |
| Session Cache | Per-request | Shares data across parallel threads |

---
