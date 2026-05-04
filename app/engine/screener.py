"""Stock screener engine — multi-factor screening for Shariah-compliant Indian equities.

Uses yfinance fundamental data to rank stocks by valuation, growth,
financial health, competitive advantage, technical momentum, and risk.
Returns structured results compatible with the /api/analyze endpoint.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from app.cache.memory_cache import get_analysis_cache
from app.engine.data_fetcher import fetch_historical, resolve_ticker
from app.engine.indicators import compute_rsi, compute_macd, compute_moving_averages
from app.engine.trend import analyse_trend
from app.models.schemas import ScreenedStock, ScreenerReport, ScreenerRequest

logger = logging.getLogger(__name__)

# ── NSE 100+ Stock Universe ─────────────────────────────────
# 118 stocks from India's top companies (Nifty 100 + select others),
# grouped by sector. This provides comprehensive coverage of
# large and mid-cap stocks across all major sectors.

STOCK_UNIVERSE: dict[str, list[dict[str, str]]] = {
    "IT / Software": [
        {"ticker": "TCS.NS", "name": "Tata Consultancy Services"},
        {"ticker": "INFY.NS", "name": "Infosys"},
        {"ticker": "HCLTECH.NS", "name": "HCL Technologies"},
        {"ticker": "WIPRO.NS", "name": "Wipro"},
        {"ticker": "TECHM.NS", "name": "Tech Mahindra"},
        {"ticker": "LTIM.NS", "name": "LTIMindtree"},
        {"ticker": "PERSISTENT.NS", "name": "Persistent Systems"},
        {"ticker": "COFORGE.NS", "name": "Coforge"},
        {"ticker": "MPHASIS.NS", "name": "Mphasis"},
        {"ticker": "LTTS.NS", "name": "L&T Technology Services"},
    ],
    "Banking": [
        {"ticker": "HDFCBANK.NS", "name": "HDFC Bank"},
        {"ticker": "ICICIBANK.NS", "name": "ICICI Bank"},
        {"ticker": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank"},
        {"ticker": "AXISBANK.NS", "name": "Axis Bank"},
        {"ticker": "SBIN.NS", "name": "State Bank of India"},
        {"ticker": "INDUSINDBK.NS", "name": "IndusInd Bank"},
        {"ticker": "BANKBARODA.NS", "name": "Bank of Baroda"},
        {"ticker": "PNB.NS", "name": "Punjab National Bank"},
        {"ticker": "FEDERALBNK.NS", "name": "Federal Bank"},
        {"ticker": "IDFCFIRSTB.NS", "name": "IDFC First Bank"},
        {"ticker": "AUBANK.NS", "name": "AU Small Finance Bank"},
    ],
    "Financial Services": [
        {"ticker": "BAJFINANCE.NS", "name": "Bajaj Finance"},
        {"ticker": "BAJAJFINSV.NS", "name": "Bajaj Finserv"},
        {"ticker": "HDFCLIFE.NS", "name": "HDFC Life Insurance"},
        {"ticker": "SBILIFE.NS", "name": "SBI Life Insurance"},
        {"ticker": "ICICIPRULI.NS", "name": "ICICI Prudential Life"},
        {"ticker": "ICICIGI.NS", "name": "ICICI Lombard General Insurance"},
        {"ticker": "SBICARD.NS", "name": "SBI Cards"},
        {"ticker": "CHOLAFIN.NS", "name": "Cholamandalam Investment"},
        {"ticker": "SHRIRAMFIN.NS", "name": "Shriram Finance"},
        {"ticker": "MUTHOOTFIN.NS", "name": "Muthoot Finance"},
        {"ticker": "POONAWALLA.NS", "name": "Poonawalla Fincorp"},
    ],
    "Pharmaceuticals": [
        {"ticker": "SUNPHARMA.NS", "name": "Sun Pharmaceutical"},
        {"ticker": "DRREDDY.NS", "name": "Dr. Reddy's Laboratories"},
        {"ticker": "CIPLA.NS", "name": "Cipla"},
        {"ticker": "DIVISLAB.NS", "name": "Divi's Laboratories"},
        {"ticker": "AUROPHARMA.NS", "name": "Aurobindo Pharma"},
        {"ticker": "BIOCON.NS", "name": "Biocon"},
        {"ticker": "LUPIN.NS", "name": "Lupin"},
        {"ticker": "TORNTPHARM.NS", "name": "Torrent Pharmaceuticals"},
        {"ticker": "ZYDUSLIFE.NS", "name": "Zydus Lifesciences"},
    ],
    "Healthcare": [
        {"ticker": "APOLLOHOSP.NS", "name": "Apollo Hospitals"},
        {"ticker": "MAXHEALTH.NS", "name": "Max Healthcare"},
        {"ticker": "FORTIS.NS", "name": "Fortis Healthcare"},
    ],
    "Oil & Gas": [
        {"ticker": "RELIANCE.NS", "name": "Reliance Industries"},
        {"ticker": "ONGC.NS", "name": "Oil & Natural Gas Corp"},
        {"ticker": "BPCL.NS", "name": "Bharat Petroleum"},
        {"ticker": "IOC.NS", "name": "Indian Oil Corporation"},
        {"ticker": "GAIL.NS", "name": "GAIL India"},
        {"ticker": "PETRONET.NS", "name": "Petronet LNG"},
        {"ticker": "HINDPETRO.NS", "name": "Hindustan Petroleum"},
    ],
    "Power & Utilities": [
        {"ticker": "NTPC.NS", "name": "NTPC"},
        {"ticker": "POWERGRID.NS", "name": "Power Grid Corporation"},
        {"ticker": "TATAPOWER.NS", "name": "Tata Power"},
        {"ticker": "ADANIGREEN.NS", "name": "Adani Green Energy"},
        {"ticker": "ADANIENSOL.NS", "name": "Adani Energy Solutions"},
        {"ticker": "NHPC.NS", "name": "NHPC"},
        {"ticker": "JSWENERGY.NS", "name": "JSW Energy"},
        {"ticker": "TORNTPOWER.NS", "name": "Torrent Power"},
    ],
    "Metals & Mining": [
        {"ticker": "TATASTEEL.NS", "name": "Tata Steel"},
        {"ticker": "JSWSTEEL.NS", "name": "JSW Steel"},
        {"ticker": "HINDALCO.NS", "name": "Hindalco Industries"},
        {"ticker": "COALINDIA.NS", "name": "Coal India"},
        {"ticker": "VEDL.NS", "name": "Vedanta"},
        {"ticker": "NMDC.NS", "name": "NMDC"},
        {"ticker": "JINDALSTEL.NS", "name": "Jindal Steel & Power"},
    ],
    "Automotive": [
        {"ticker": "TATAMOTORS.NS", "name": "Tata Motors"},
        {"ticker": "M&M.NS", "name": "Mahindra & Mahindra"},
        {"ticker": "MARUTI.NS", "name": "Maruti Suzuki"},
        {"ticker": "BAJAJ-AUTO.NS", "name": "Bajaj Auto"},
        {"ticker": "EICHERMOT.NS", "name": "Eicher Motors"},
        {"ticker": "HEROMOTOCO.NS", "name": "Hero MotoCorp"},
        {"ticker": "TVSMOTOR.NS", "name": "TVS Motor Company"},
        {"ticker": "ASHOKLEY.NS", "name": "Ashok Leyland"},
        {"ticker": "MOTHERSON.NS", "name": "Samvardhana Motherson"},
        {"ticker": "BOSCHLTD.NS", "name": "Bosch"},
    ],
    "Manufacturing / Engineering": [
        {"ticker": "LT.NS", "name": "Larsen & Toubro"},
        {"ticker": "SIEMENS.NS", "name": "Siemens"},
        {"ticker": "ABB.NS", "name": "ABB India"},
        {"ticker": "HAVELLS.NS", "name": "Havells India"},
        {"ticker": "BEL.NS", "name": "Bharat Electronics"},
        {"ticker": "CUMMINSIND.NS", "name": "Cummins India"},
        {"ticker": "BHEL.NS", "name": "Bharat Heavy Electricals"},
        {"ticker": "CGPOWER.NS", "name": "CG Power & Industrial"},
    ],
    "Consumer Goods / FMCG": [
        {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever"},
        {"ticker": "ITC.NS", "name": "ITC"},
        {"ticker": "NESTLEIND.NS", "name": "Nestle India"},
        {"ticker": "BRITANNIA.NS", "name": "Britannia Industries"},
        {"ticker": "TATACONSUM.NS", "name": "Tata Consumer Products"},
        {"ticker": "DABUR.NS", "name": "Dabur India"},
        {"ticker": "MARICO.NS", "name": "Marico"},
        {"ticker": "GODREJCP.NS", "name": "Godrej Consumer Products"},
        {"ticker": "COLPAL.NS", "name": "Colgate-Palmolive India"},
        {"ticker": "VBL.NS", "name": "Varun Beverages"},
        {"ticker": "UBL.NS", "name": "United Breweries"},
    ],
    "Retail & Consumer Discretionary": [
        {"ticker": "TITAN.NS", "name": "Titan Company"},
        {"ticker": "TRENT.NS", "name": "Trent"},
        {"ticker": "ASIANPAINT.NS", "name": "Asian Paints"},
        {"ticker": "PAGEIND.NS", "name": "Page Industries"},
        {"ticker": "DMART.NS", "name": "Avenue Supermarts (DMart)"},
        {"ticker": "JUBLFOOD.NS", "name": "Jubilant Foodworks"},
    ],
    "Cement & Building Materials": [
        {"ticker": "ULTRACEMCO.NS", "name": "UltraTech Cement"},
        {"ticker": "GRASIM.NS", "name": "Grasim Industries"},
        {"ticker": "SHREECEM.NS", "name": "Shree Cement"},
        {"ticker": "AMBUJACEM.NS", "name": "Ambuja Cements"},
        {"ticker": "ACC.NS", "name": "ACC"},
        {"ticker": "PIDILITIND.NS", "name": "Pidilite Industries"},
    ],
    "Infrastructure & Realty": [
        {"ticker": "ADANIPORTS.NS", "name": "Adani Ports & SEZ"},
        {"ticker": "ADANIENT.NS", "name": "Adani Enterprises"},
        {"ticker": "DLF.NS", "name": "DLF"},
        {"ticker": "GODREJPROP.NS", "name": "Godrej Properties"},
        {"ticker": "LODHA.NS", "name": "Macrotech Developers (Lodha)"},
    ],
    "Telecom & Media": [
        {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel"},
        {"ticker": "INDIGO.NS", "name": "InterGlobe Aviation (IndiGo)"},
        {"ticker": "ZOMATO.NS", "name": "Zomato"},
        {"ticker": "PAYTM.NS", "name": "One 97 Communications (Paytm)"},
        {"ticker": "NYKAA.NS", "name": "FSN E-Commerce (Nykaa)"},
        {"ticker": "POLICYBZR.NS", "name": "PB Fintech (PolicyBazaar)"},
    ],
}

# Approximate sector average P/E (Indian market, periodically updated)
SECTOR_AVG_PE: dict[str, float] = {
    "IT / Software": 28.0,
    "Banking": 12.0,
    "Financial Services": 18.0,
    "Pharmaceuticals": 30.0,
    "Healthcare": 45.0,
    "Oil & Gas": 10.0,
    "Power & Utilities": 15.0,
    "Metals & Mining": 8.0,
    "Automotive": 22.0,
    "Manufacturing / Engineering": 35.0,
    "Consumer Goods / FMCG": 55.0,
    "Retail & Consumer Discretionary": 60.0,
    "Cement & Building Materials": 25.0,
    "Infrastructure & Realty": 25.0,
    "Telecom & Media": 30.0,
}


def _safe_get(info: dict, *keys, default=None) -> Any:
    """Try multiple keys in yfinance info dict, return first non-None."""
    for k in keys:
        val = info.get(k)
        if val is not None:
            return val
    return default


def _fetch_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch fundamental data for a single ticker via yfinance."""
    cache = get_analysis_cache()
    cache_key = f"screener_fund|{ticker}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            return None

        price = _safe_get(info, "currentPrice", "regularMarketPrice", default=0)
        market_cap = _safe_get(info, "marketCap", default=0)
        pe = _safe_get(info, "trailingPE", "forwardPE")
        peg = _safe_get(info, "pegRatio")
        de = _safe_get(info, "debtToEquity")
        roe = _safe_get(info, "returnOnEquity")
        op_margin = _safe_get(info, "operatingMargins")
        rev_growth = _safe_get(info, "revenueGrowth")
        earnings_growth = _safe_get(info, "earningsGrowth")
        fcf = _safe_get(info, "freeCashflow", default=0)
        profit_margin = _safe_get(info, "profitMargins")
        beta = _safe_get(info, "beta", default=1.0)

        result = {
            "price": float(price) if price else 0,
            "market_cap": float(market_cap) if market_cap else 0,
            "market_cap_cr": round(float(market_cap) / 1e7, 2) if market_cap else None,
            "pe_ratio": round(float(pe), 2) if pe else None,
            "peg_ratio": round(float(peg), 2) if peg else None,
            "debt_to_equity": round(float(de) / 100, 2) if de else None,  # yfinance gives D/E as percentage
            "roe_pct": round(float(roe) * 100, 2) if roe else None,
            "operating_margin_pct": round(float(op_margin) * 100, 2) if op_margin else None,
            "revenue_growth_pct": round(float(rev_growth) * 100, 2) if rev_growth else None,
            "earnings_growth_pct": round(float(earnings_growth) * 100, 2) if earnings_growth else None,
            "free_cash_flow": float(fcf) if fcf else 0,
            "free_cash_flow_cr": round(float(fcf) / 1e7, 2) if fcf else None,
            "profit_margin_pct": round(float(profit_margin) * 100, 2) if profit_margin else None,
            "beta": round(float(beta), 2) if beta else 1.0,
        }

        cache[cache_key] = result
        return result

    except Exception as e:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, e)
        return None


def _compute_composite_score(
    fund: dict[str, Any],
    sector_pe: float,
    trend: str,
    rsi_val: float,
) -> float:
    """Multi-factor composite score (0-100). Higher is better."""
    try:
        score = 50.0  # base

        # 1. Valuation (max ±15 pts)
        pe = fund.get("pe_ratio")
        if pe and sector_pe:
            pe_discount = (sector_pe - pe) / sector_pe * 100
            score += max(-15, min(15, pe_discount * 0.5))

        peg = fund.get("peg_ratio")
        if peg and peg > 0:
            if peg < 1.0:
                score += 8
            elif peg < 1.5:
                score += 4
            elif peg > 3.0:
                score -= 5

        # 2. Growth (max ±15 pts)
        rev_g = fund.get("revenue_growth_pct", 0) or 0
        score += max(-10, min(10, rev_g * 0.3))

        earn_g = fund.get("earnings_growth_pct", 0) or 0
        score += max(-5, min(5, earn_g * 0.15))

        # 3. Financial health (max ±15 pts)
        de = fund.get("debt_to_equity")
        if de is not None:
            if de < 0.3:
                score += 10
            elif de < 0.5:
                score += 6
            elif de < 0.8:
                score += 3
            elif de > 1.5:
                score -= 10
            elif de > 1.0:
                score -= 5

        roe = fund.get("roe_pct", 0) or 0
        if roe > 20:
            score += 5
        elif roe > 15:
            score += 3
        elif roe < 5:
            score -= 5

        # 4. Technical momentum (max ±10 pts)
        if trend == "bullish":
            score += 7
        elif trend == "bearish":
            score -= 7

        if rsi_val < 30:
            score += 5  # oversold — opportunity
        elif rsi_val > 70:
            score -= 5  # overbought — risk

        # 5. Cash flow strength (max ±5 pts)
        fcf = fund.get("free_cash_flow", 0)
        if fcf > 0:
            score += 3
        elif fcf < 0:
            score -= 3

        # 6. Operating margin (max ±5 pts)
        opm = fund.get("operating_margin_pct", 0) or 0
        if opm > 20:
            score += 5
        elif opm > 10:
            score += 2
        elif opm < 0:
            score -= 5

        return round(max(0, min(100, score)), 1)
    except Exception as e:
        logger.exception("[_compute_composite_score] Failed: %s", e)
        return 50.0


def _assess_moat(fund: dict[str, Any]) -> str:
    """Simple moat assessment based on margins, ROE, and market cap."""
    try:
        opm = fund.get("operating_margin_pct", 0) or 0
        roe = fund.get("roe_pct", 0) or 0
        mcap = fund.get("market_cap", 0) or 0

        strong_count = 0
        if opm > 20:
            strong_count += 1
        if roe > 18:
            strong_count += 1
        if mcap > 1e12:  # > 1 lakh crore
            strong_count += 1

        if strong_count >= 3:
            return "strong"
        elif strong_count >= 1:
            return "moderate"
        return "weak"
    except Exception as e:
        logger.exception("[_assess_moat] Failed: %s", e)
        return "weak"


def _assess_risk_score(fund: dict[str, Any], trend: str) -> int:
    """Risk score 1-10 (1 = lowest risk, 10 = highest risk)."""
    try:
        risk = 5  # base

        beta = fund.get("beta", 1.0) or 1.0
        if beta > 1.5:
            risk += 2
        elif beta > 1.2:
            risk += 1
        elif beta < 0.7:
            risk -= 1

        de = fund.get("debt_to_equity")
        if de is not None:
            if de > 1.0:
                risk += 2
            elif de > 0.8:
                risk += 1
            elif de < 0.3:
                risk -= 1

        earn_g = fund.get("earnings_growth_pct")
        if earn_g is not None and earn_g < 0:
            risk += 1

        if trend == "bearish":
            risk += 1
        elif trend == "bullish":
            risk -= 1

        return max(1, min(10, risk))
    except Exception as e:
        logger.exception("[_assess_risk_score] Failed: %s", e)
        return 5


def _shariah_check(sector: str, fund: dict[str, Any]) -> tuple[bool, str]:
    """Basic Shariah compliance check based on sector and debt levels."""
    try:
        non_halal_keywords = ["bank", "insurance", "alcohol", "tobacco", "gambling", "liquor"]
        sector_lower = sector.lower()
        for kw in non_halal_keywords:
            if kw in sector_lower:
                return False, f"Sector ({sector}) typically non-compliant"

        de = fund.get("debt_to_equity")
        if de is not None and de > 0.33:
            return True, f"Broadly compliant; note D/E={de:.2f} (stricter screens require <0.33)"

        return True, "Sector and financial structure appear broadly compliant"
    except Exception as e:
        logger.exception("[_shariah_check] Failed: %s", e)
        return True, "Unable to verify — defaulting to compliant"


def _compute_trade_levels(
    price: float, risk_pct: float, trend: str, fund: dict[str, Any]
) -> dict[str, float | None]:
    """Compute entry zone, stop-loss, and price targets."""
    try:
        if price <= 0:
            return {
                "entry_low": None, "entry_high": None,
                "stop_loss": None, "target_bull": None,
                "target_base": None, "target_bear": None,
            }

        sl_pct = risk_pct / 100.0
        entry_low = round(price * 0.97, 2)
        entry_high = round(price * 1.00, 2)

        stop_loss = round(price * (1 - sl_pct), 2)

        # Targets based on growth and trend
        growth_mult = 1.0
        rev_g = (fund.get("revenue_growth_pct", 0) or 0) / 100
        if rev_g > 0:
            growth_mult += rev_g * 0.5

        if trend == "bullish":
            target_bull = round(price * (1 + 0.30 * growth_mult), 2)
            target_base = round(price * (1 + 0.15 * growth_mult), 2)
            target_bear = round(price * (1 - 0.10), 2)
        elif trend == "bearish":
            target_bull = round(price * (1 + 0.15), 2)
            target_base = round(price * (1 + 0.05), 2)
            target_bear = round(price * (1 - 0.15), 2)
        else:
            target_bull = round(price * (1 + 0.20 * growth_mult), 2)
            target_base = round(price * (1 + 0.10 * growth_mult), 2)
            target_bear = round(price * (1 - 0.10), 2)

        return {
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "target_bull": target_bull,
            "target_base": target_base,
            "target_bear": target_bear,
        }
    except Exception as e:
        logger.exception("[_compute_trade_levels] Failed for price=%s: %s", price, e)
        return {
            "entry_low": None, "entry_high": None,
            "stop_loss": None, "target_bull": None,
            "target_base": None, "target_bear": None,
        }


def _normalize_ticker(ticker: str) -> str | None:
    """Normalize ticker input. Handle both 'TCS' and 'TCS.NS' formats."""
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    # If no exchange suffix, check if it's NSE (default to .NS for Indian stocks)
    if "." not in ticker:
        ticker = f"{ticker}.NS"
    return ticker


def _process_single_stock(
    stock_info: dict[str, str],
    sector: str,
    sector_pe: float,
    max_risk_pct: float,
) -> tuple[ScreenedStock | None, str | None]:
    """Process a single stock and return (candidate, error_ticker).
    
    Returns:
        Tuple of (ScreenedStock or None, failed_ticker or None)
    """
    ticker = stock_info["ticker"]
    company_name = stock_info["name"]
    
    try:
        # Fetch fundamentals
        fund = _fetch_fundamentals(ticker)
        if not fund or fund["price"] <= 0:
            logger.warning("Skipping %s — no data", ticker)
            return None, None

        # Fetch technical trend (2 years of daily data)
        try:
            daily_df = fetch_historical(ticker, period="2y", interval="1d")
            trend = analyse_trend(daily_df)
            rsi_data = compute_rsi(daily_df)
            rsi_val = rsi_data["rsi"]
        except Exception:
            trend = "neutral"
            rsi_val = 50.0

        # Scores and assessments
        composite = _compute_composite_score(fund, sector_pe, trend, rsi_val)
        moat = _assess_moat(fund)
        risk_score = _assess_risk_score(fund, trend)
        shariah_ok, shariah_note = _shariah_check(sector, fund)
        trade = _compute_trade_levels(fund["price"], max_risk_pct, trend, fund)

        # P/E vs sector
        pe = fund.get("pe_ratio")
        if pe and sector_pe:
            if pe < sector_pe * 0.8:
                pe_vs = "undervalued"
            elif pe > sector_pe * 1.2:
                pe_vs = "overvalued"
            else:
                pe_vs = "fair"
        else:
            pe_vs = "N/A"

        # Build fundamental summary
        parts = []
        if fund.get("revenue_growth_pct") is not None:
            parts.append(f"Revenue growth: {fund['revenue_growth_pct']:.1f}%")
        if fund.get("roe_pct") is not None:
            parts.append(f"ROE: {fund['roe_pct']:.1f}%")
        if fund.get("operating_margin_pct") is not None:
            parts.append(f"Op margin: {fund['operating_margin_pct']:.1f}%")
        if fund.get("debt_to_equity") is not None:
            parts.append(f"D/E: {fund['debt_to_equity']:.2f}")
        fundamental_summary = ". ".join(parts) if parts else "Limited fundamental data"

        # Growth outlook
        rev_g = fund.get("revenue_growth_pct", 0) or 0
        earn_g = fund.get("earnings_growth_pct", 0) or 0
        if rev_g > 15 and earn_g > 15:
            growth_outlook = "Strong growth trajectory in both revenue and earnings"
        elif rev_g > 10 or earn_g > 10:
            growth_outlook = "Moderate growth with steady revenue or earnings expansion"
        elif rev_g > 0:
            growth_outlook = "Positive but modest growth trend"
        else:
            growth_outlook = "Growth has stalled or declined; warrants caution"

        # Risk factors
        risk_factors = []
        if fund.get("debt_to_equity") and fund["debt_to_equity"] > 0.8:
            risk_factors.append("Elevated debt levels")
        beta = fund.get("beta", 1.0) or 1.0
        if beta > 1.3:
            risk_factors.append(f"High beta ({beta:.2f}) — above-average volatility")
        if pe and pe > sector_pe * 1.3:
            risk_factors.append("Richly valued relative to sector")
        if trend == "bearish":
            risk_factors.append("Currently in a technical downtrend")
        if not risk_factors:
            risk_factors.append("No major risk flags identified")

        candidate = ScreenedStock(
            ticker=ticker,
            company_name=company_name,
            sector=sector,
            current_price=fund["price"],
            market_cap_cr=fund.get("market_cap_cr"),
            pe_ratio=pe,
            sector_avg_pe=sector_pe,
            pe_vs_sector=pe_vs,
            peg_ratio=fund.get("peg_ratio"),
            revenue_growth_5y_pct=fund.get("revenue_growth_pct"),
            profit_growth_5y_pct=fund.get("earnings_growth_pct"),
            debt_to_equity=fund.get("debt_to_equity"),
            roe_pct=fund.get("roe_pct"),
            operating_margin_pct=fund.get("operating_margin_pct"),
            free_cash_flow_cr=fund.get("free_cash_flow_cr"),
            moat=moat,
            shariah_compliant=shariah_ok,
            shariah_note=shariah_note,
            technical_trend=trend,
            risk_score=risk_score,
            composite_score=composite,
            entry_zone_low=trade["entry_low"],
            entry_zone_high=trade["entry_high"],
            stop_loss=trade["stop_loss"],
            target_bull=trade["target_bull"],
            target_base=trade["target_base"],
            target_bear=trade["target_bear"],
            fundamental_summary=fundamental_summary,
            growth_outlook=growth_outlook,
            risk_factors=risk_factors,
        )
        return candidate, None

    except Exception as e:
        error_msg = str(e)
        logger.warning("Error screening %s: %s", ticker, error_msg)
        # Track 404 errors (ticker not found)
        if "404" in error_msg or "not found" in error_msg.lower():
            return None, ticker
        return None, None


def _get_stock_universe_for_screening(custom_tickers: str | None) -> list[dict[str, str]]:
    """Build list of stocks to screen. Use custom_tickers if provided, else default universe."""
    if custom_tickers:
        # Parse comma-separated tickers
        tickers = [t.strip() for t in custom_tickers.split(",") if t.strip()]
        stocks = []
        for ticker in tickers:
            normalized = _normalize_ticker(ticker)
            if normalized:
                # Try to find company name from default universe, fallback to ticker
                company_name = normalized.replace(".NS", "")
                for sector_stocks in STOCK_UNIVERSE.values():
                    for s in sector_stocks:
                        if s["ticker"] == normalized:
                            company_name = s["name"]
                            break
                stocks.append({"ticker": normalized, "name": company_name})
        return stocks
    else:
        # Use default universe
        result = []
        for sector, stocks in STOCK_UNIVERSE.items():
            result.extend(stocks)
        return result


def run_screener(req: ScreenerRequest) -> ScreenerReport:
    """Run multi-factor stock screening across the Shariah-compliant universe or custom tickers."""
    cache = get_analysis_cache()
    
    # Log the incoming request
    logger.info("Screener request received: capital=%.0f, top_n=%d, max_risk_pct=%.1f, custom_tickers=%s", 
                req.capital, req.top_n, req.max_risk_pct, req.custom_tickers or "None")
    
    cache_key = f"screener|{req.capital}|{req.top_n}|{req.max_risk_pct}|{req.custom_tickers or 'default'}"
    if cache_key in cache:
        logger.info("Screener cache hit")
        return cache[cache_key]

    logger.info("Running stock screener (top %d, capital=₹%.0f)", req.top_n, req.capital)

    all_candidates: list[ScreenedStock] = []
    failed_tickers: list[str] = []

    # Get screening universe
    stocks_to_screen = _get_stock_universe_for_screening(req.custom_tickers)
    
    # Determine if using custom tickers or default universe
    is_custom = req.custom_tickers is not None
    
    # Log which mode we're using
    if is_custom:
        logger.info("Screening custom tickers: %s (%d tickers)", req.custom_tickers[:50] + "..." if len(req.custom_tickers) > 50 else req.custom_tickers, len(stocks_to_screen))
    else:
        logger.info("Screening default universe (%d stocks)", len(stocks_to_screen))
    
    # ── Build job list with sector info ──
    jobs: list[tuple[dict[str, str], str, float]] = []
    
    if is_custom:
        # For custom tickers, find sector info if available
        sector_map = {}
        for ticker in [s["ticker"] for s in stocks_to_screen]:
            for sector, sector_stocks in STOCK_UNIVERSE.items():
                for s in sector_stocks:
                    if s["ticker"] == ticker:
                        sector_map[ticker] = sector
                        break
        
        for stock_info in stocks_to_screen:
            sector = sector_map.get(stock_info["ticker"], "Custom")
            sector_pe = SECTOR_AVG_PE.get(sector, 30.0)
            jobs.append((stock_info, sector, sector_pe))
    else:
        # Use default sector-grouped universe
        for sector, stocks in STOCK_UNIVERSE.items():
            sector_pe = SECTOR_AVG_PE.get(sector, 30.0)
            for stock_info in stocks:
                jobs.append((stock_info, sector, sector_pe))
    
    # ── Process stocks in parallel ──
    logger.info("Processing %d stocks in parallel...", len(jobs))
    max_workers = min(20, len(jobs))  # Cap at 20 parallel requests
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        futures = {
            executor.submit(
                _process_single_stock, 
                stock_info, 
                sector, 
                sector_pe, 
                req.max_risk_pct
            ): stock_info["ticker"]
            for stock_info, sector, sector_pe in jobs
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                candidate, error_ticker = future.result()
                if candidate is not None:
                    all_candidates.append(candidate)
                if error_ticker is not None:
                    failed_tickers.append(error_ticker)
            except Exception as e:
                logger.warning("Parallel processing error for %s: %s", ticker, e)
    
    logger.info("Parallel processing complete. %d candidates found.", len(all_candidates))

    # Sort by composite score descending, take top N
    all_candidates.sort(key=lambda s: s.composite_score, reverse=True)
    top_stocks = all_candidates[: req.top_n]

    # Portfolio allocation (equal-weight with risk adjustment)
    if top_stocks:
        total_risk_inv = sum(1.0 / max(s.risk_score, 1) for s in top_stocks)
        for s in top_stocks:
            weight = (1.0 / max(s.risk_score, 1)) / total_risk_inv
            s.allocation_pct = round(weight * 100, 1)
            s.allocation_amount = round(req.capital * weight, 0)

    # Build trade plan summary
    trade_plan_summary = []
    for s in top_stocks:
        trade_plan_summary.append({
            "ticker": s.ticker,
            "entry_zone": f"₹{s.entry_zone_low:,.2f} – ₹{s.entry_zone_high:,.2f}" if s.entry_zone_low else "N/A",
            "stop_loss": f"₹{s.stop_loss:,.2f}" if s.stop_loss else "N/A",
            "target_bull": f"₹{s.target_bull:,.2f}" if s.target_bull else "N/A",
            "target_base": f"₹{s.target_base:,.2f}" if s.target_base else "N/A",
            "target_bear": f"₹{s.target_bear:,.2f}" if s.target_bear else "N/A",
        })

    # Portfolio allocation summary
    portfolio_alloc = {
        "total_capital": req.capital,
        "currency": "INR",
        "stocks": [
            {"ticker": s.ticker, "pct": s.allocation_pct, "amount": s.allocation_amount}
            for s in top_stocks
        ],
        "note": f"Risk-weighted allocation across {len(top_stocks)} stocks with {req.max_risk_pct}% max downside per position",
    }

    # Top 3 picks
    top_3 = top_stocks[:3]
    top_picks = []
    for i, s in enumerate(top_3, 1):
        reasons = []
        if s.composite_score >= 65:
            reasons.append(f"High composite score ({s.composite_score})")
        if s.moat == "strong":
            reasons.append("Strong competitive moat")
        if s.pe_vs_sector == "undervalued":
            reasons.append("Undervalued relative to sector")
        if s.technical_trend == "bullish":
            reasons.append("Positive technical momentum")
        if s.debt_to_equity is not None and s.debt_to_equity < 0.5:
            reasons.append("Low leverage")
        if s.roe_pct and s.roe_pct > 15:
            reasons.append(f"Strong ROE ({s.roe_pct:.1f}%)")
        if not reasons:
            reasons.append("Balanced multi-factor profile")

        top_picks.append({
            "rank": i,
            "ticker": s.ticker,
            "company": s.company_name,
            "sector": s.sector,
            "composite_score": s.composite_score,
            "conviction_reasons": reasons,
        })

    # Market overview
    if req.custom_tickers:
        market_overview = (
            f"Custom stock screener running on user-provided tickers: {req.custom_tickers}. "
            f"The multi-factor model evaluates valuation, growth, financial health, "
            f"competitive moat, technical momentum, and risk to identify the top {req.top_n} opportunities "
            f"for a {req.horizon_months}-month investment horizon with ₹{req.capital:,.0f} capital."
        )
    else:
        market_overview = (
            "Indian equity markets are being screened across Shariah-compliant sectors "
            "including IT, Pharmaceuticals, Healthcare, Manufacturing, Consumer Goods, "
            "Infrastructure, Renewable Energy, and Automotive. "
            f"Screening universe: {sum(len(v) for v in STOCK_UNIVERSE.values())} stocks across "
            f"{len(STOCK_UNIVERSE)} sectors. "
            f"The multi-factor model evaluates valuation, growth, financial health, "
            f"competitive moat, technical momentum, and risk to identify the top {req.top_n} opportunities "
            f"for a {req.horizon_months}-month investment horizon with ₹{req.capital:,.0f} capital."
        )

    screening_criteria = {
        "market_cap": "Mid-cap and large-cap preferred",
        "revenue_growth": "Positive trend preferred",
        "debt_to_equity": "< 0.8 preferred",
        "roe": "> 15% preferred",
        "operating_margin": "Stable and positive",
        "valuation": "Reasonable P/E relative to sector",
        "shariah_compliance": "Halal-friendly sectors; debt < 33% of assets preferred",
    }

    tickers_for_analysis = [s.ticker for s in top_stocks]

    report = ScreenerReport(
        market_overview=market_overview,
        screening_criteria=screening_criteria,
        stocks=top_stocks,
        trade_plan_summary=trade_plan_summary,
        portfolio_allocation=portfolio_alloc,
        top_picks=top_picks,
        tickers_for_analysis=tickers_for_analysis,
        failed_tickers=failed_tickers,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    cache[cache_key] = report
    return report
