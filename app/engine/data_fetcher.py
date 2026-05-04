"""Fetch stock data from Yahoo Finance with caching.

Supports global tickers including Indian stocks:
    - NSE: append .NS  (e.g. RELIANCE.NS, TCS.NS, INFY.NS)
    - BSE: append .BO  (e.g. RELIANCE.BO, TCS.BO)
    - US stocks work as-is (e.g. AAPL, TSLA)
    - Other exchanges: .L (London), .TO (Toronto), .HK (Hong Kong), etc.

If a bare ticker fails, the system auto-tries .NS and .BO suffixes.
For Indian stocks, NSEpy is used as fallback when yfinance is rate-limited.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

# NSEpy for fallback (Indian stocks)
try:
    from nsepy import get_history as nse_get_history
    NSEPY_AVAILABLE = True
except ImportError:
    NSEPY_AVAILABLE = False
    nse_get_history = None

from app.cache.memory_cache import get_data_cache

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 2.0  # seconds
MAX_DELAY = 30.0  # seconds

T = TypeVar("T")


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate limit error."""
    if isinstance(e, YFRateLimitError):
        return True
    error_str = str(e).lower()
    return "401" in error_str or "unauthorized" in error_str or "rate" in error_str


def retry_on_rate_limit(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that retries a function on YFRateLimitError with exponential backoff."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exception: Optional[Exception] = None
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not _is_rate_limit_error(e):
                    raise  # Not a rate limit error, propagate immediately
                
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    logger.warning(
                        "Rate limited on %s (attempt %d/%d). Retrying in %.1fs...",
                        func.__name__, attempt + 1, MAX_RETRIES + 1, delay
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Rate limit exceeded after %d attempts for %s: %s",
                        MAX_RETRIES + 1, func.__name__, e
                    )
        
        # All retries exhausted
        if last_exception is not None:
            raise last_exception
        raise RuntimeError(f"Unexpected state in retry_on_rate_limit for {func.__name__}")
    
    return wrapper

# Exchange suffixes to try if a bare ticker returns no data
_FALLBACK_SUFFIXES = [".NS", ".BO"]


def resolve_ticker(ticker: str) -> str:
    """Resolve a ticker symbol, trying exchange suffixes if needed.

    If the ticker already contains a dot (e.g. TCS.NS), use as-is.
    Otherwise try the bare ticker first, then .NS, then .BO.
    Returns the first ticker that yields data.
    """
    ticker = ticker.upper().strip()

    cache = get_data_cache()
    resolve_key = f"resolve|{ticker}"
    if resolve_key in cache:
        return cache[resolve_key]

    # If ticker already has an exchange suffix, use as-is
    if "." in ticker:
        cache[resolve_key] = ticker
        return ticker

    # Try bare ticker first
    candidates = [ticker] + [f"{ticker}{suffix}" for suffix in _FALLBACK_SUFFIXES]

    for candidate in candidates:
        try:
            result = _try_resolve_ticker(candidate)
            if result:
                logger.info("Resolved ticker '%s' → '%s'", ticker, candidate)
                cache[resolve_key] = candidate
                return candidate
        except Exception:
            continue

    # Nothing worked — return original and let downstream handle the error
    cache[resolve_key] = ticker
    return ticker


@retry_on_rate_limit
def _try_resolve_ticker(candidate: str) -> bool:
    """Try to fetch data for a ticker candidate. Returns True if data exists."""
    tk = yf.Ticker(candidate)
    df = tk.history(period="5d")
    return not df.empty


@retry_on_rate_limit
def _fetch_history_with_retry(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch history with retry on rate limit."""
    tk = yf.Ticker(ticker)
    return tk.history(period=period, interval=interval)


def _is_indian_ticker(ticker: str) -> bool:
    """Check if ticker is an Indian stock (NSE/BSE)."""
    return ticker.upper().endswith((".NS", ".BO"))


def _extract_symbol_from_indian_ticker(ticker: str) -> str:
    """Extract base symbol from Indian ticker (e.g., TCS.NS -> TCS)."""
    return ticker.upper().rsplit(".", 1)[0]


def _period_to_dates(period: str) -> tuple[date, date]:
    """Convert yfinance period string to start/end dates."""
    end_date = date.today()
    period_map = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 7300,
    }
    days = period_map.get(period.lower(), 730)
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def _fetch_via_nsepy(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch Indian stock data via NSEpy as fallback.
    
    NSEpy only supports daily data. For weekly/monthly, we resample.
    
    Note: NSEpy has compatibility issues with Python 3.13+ due to
    FrameLocalsProxy changes. This function handles those errors gracefully.
    """
    if not NSEPY_AVAILABLE or nse_get_history is None:
        raise ImportError("nsepy not installed. Run: pip install nsepy")
    
    if not _is_indian_ticker(ticker):
        raise ValueError(f"NSEpy only supports Indian stocks (.NS/.BO), got: {ticker}")
    
    symbol = _extract_symbol_from_indian_ticker(ticker)
    start_date, end_date = _period_to_dates(period)
    
    logger.info("Fetching %s via NSEpy (fallback) from %s to %s", symbol, start_date, end_date)
    
    try:
        df = nse_get_history(symbol=symbol, start=start_date, end=end_date)
        
        if df.empty:
            raise ValueError(f"No data from NSEpy for symbol '{symbol}'")
        
        # Normalize columns to match yfinance format
        df = df.reset_index()
        column_map = {
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Turnover": "turnover",
        }
        df = df.rename(columns=column_map)
        
        # Filter to only needed columns
        needed = ["date", "open", "high", "low", "close", "volume"]
        df = df[[c for c in needed if c in df.columns]]
        
        # Resample for weekly/monthly if needed
        if interval in ("1wk", "1mo"):
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            resample_rule = "W" if interval == "1wk" else "ME"
            df = df.resample(resample_rule).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna().reset_index()
        
        logger.info("NSEpy returned %d rows for %s", len(df), symbol)
        return df
        
    except TypeError as e:
        # Python 3.13+ incompatibility with nsepy (FrameLocalsProxy issue)
        if "FrameLocalsProxy" in str(e):
            raise RuntimeError(
                f"NSEpy is incompatible with Python 3.13+. "
                f"Please use yfinance or downgrade to Python 3.12. Error: {e}"
            ) from e
        raise
    except Exception as e:
        logger.error("NSEpy fetch failed for %s: %s", symbol, e)
        raise


def _is_not_found_error(e: Exception) -> bool:
    """Check if an exception indicates stock not found/delisted."""
    error_str = str(e).lower()
    return any(x in error_str for x in [
        "404", "not found", "delisted", "no data found",
        "symbol may be delisted", "no price data", "no data returned"
    ])


def _fetch_historical_with_fallback(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch historical data with multiple fallbacks for Indian stocks.
    
    Fallback chain:
    1. Try original ticker via yfinance
    2. If .NS fails, try .BO (or vice versa)
    3. Try NSEpy as last resort (Indian stocks only)
    """
    yf_error = None
    
    # Try original ticker
    try:
        df = _fetch_history_with_retry(ticker, period, interval)
        if not df.empty:
            return df
        yf_error = ValueError(f"No data returned for ticker '{ticker}'")
    except Exception as e:
        yf_error = e
    
    # For Indian stocks, try alternate exchange (NSE <-> BSE)
    if _is_indian_ticker(ticker) and (_is_not_found_error(yf_error) or yf_error):
        symbol = _extract_symbol_from_indian_ticker(ticker)
        alt_ticker = f"{symbol}.BO" if ticker.endswith(".NS") else f"{symbol}.NS"
        
        logger.info("Trying alternate exchange: %s -> %s", ticker, alt_ticker)
        try:
            df = _fetch_history_with_retry(alt_ticker, period, interval)
            if not df.empty:
                logger.info("Found data on alternate exchange: %s", alt_ticker)
                return df
        except Exception as alt_error:
            logger.debug("Alternate exchange %s also failed: %s", alt_ticker, alt_error)
    
    # Try NSEpy fallback for Indian stocks
    if _is_indian_ticker(ticker) and NSEPY_AVAILABLE:
        should_try_nsepy = (
            _is_rate_limit_error(yf_error) or 
            _is_not_found_error(yf_error) or
            (yf_error and "empty" in str(yf_error).lower())
        )
        
        if should_try_nsepy:
            logger.warning(
                "yfinance failed for %s (%s), trying NSEpy fallback...", 
                ticker, type(yf_error).__name__
            )
            try:
                return _fetch_via_nsepy(ticker, period, interval)
            except RuntimeError as nsepy_error:
                # Python 3.13+ incompatibility - log and continue with original error
                if "FrameLocalsProxy" in str(nsepy_error) or "Python 3.13" in str(nsepy_error):
                    logger.warning(
                        "NSEpy fallback skipped for %s: incompatible with Python 3.13+. "
                        "Consider using yfinance directly or adding .NS/.BO suffix.",
                        ticker
                    )
                else:
                    logger.warning("NSEpy fallback failed for %s: %s", ticker, nsepy_error)
            except Exception as nsepy_error:
                logger.warning("NSEpy fallback also failed for %s: %s", ticker, nsepy_error)
                # Raise the original yfinance error
    
    if yf_error:
        raise yf_error
    raise ValueError(f"No data returned for ticker '{ticker}'")


def fetch_historical(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Return OHLCV DataFrame, cached by (ticker, period, interval)."""
    cache = get_data_cache()
    key = f"{ticker}|{period}|{interval}"
    if key in cache:
        logger.info("Cache hit: %s", key)
        return cache[key]

    try:
        logger.info("Fetching %s period=%s interval=%s", ticker, period, interval)
        df = _fetch_historical_with_fallback(ticker, period, interval)

        if df.empty:
            raise ValueError(
                f"No data returned for ticker '{ticker}'. "
                f"For Indian stocks, try adding .NS (NSE) or .BO (BSE) — e.g. RELIANCE.NS"
            )

        # Normalize column names
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        
        # Handle index - NSEpy returns 'date' column, yfinance uses DatetimeIndex
        if "date" not in df.columns and df.index.name:
            df.index.name = "date"
            df = df.reset_index()
        
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        cache[key] = df
        return df
    except ValueError:
        raise
    except Exception as e:
        logger.exception("[fetch_historical] Failed for ticker=%s period=%s interval=%s: %s", ticker, period, interval, e)
        raise ValueError(f"Failed to fetch historical data for '{ticker}': {e}") from e


def fetch_quote(ticker: str) -> dict[str, Any]:
    """Return a real-time-ish quote snapshot."""
    cache = get_data_cache()
    key = f"quote|{ticker}"
    if key in cache:
        return cache[key]

    try:
        info = _fetch_info_with_retry(ticker)

        quote = {
            "ticker": ticker.upper(),
            "name": info.get("shortName") or info.get("longName") or ticker.upper(),
            "price": info.get("currentPrice") or info.get("regularMarketPrice") or 0,
            "change": info.get("regularMarketChange", 0) or 0,
            "change_pct": info.get("regularMarketChangePercent", 0) or 0,
            "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh") or 0,
            "day_low": info.get("dayLow") or info.get("regularMarketDayLow") or 0,
            "open": info.get("open") or info.get("regularMarketOpen") or 0,
            "prev_close": info.get("previousClose") or info.get("regularMarketPreviousClose") or 0,
            "volume": info.get("volume") or info.get("regularMarketVolume") or 0,
            "market_cap": info.get("marketCap"),
        }

        # Compute change from prev_close if API didn't supply it
        if quote["change"] == 0 and quote["prev_close"] and quote["price"]:
            quote["change"] = round(quote["price"] - quote["prev_close"], 2)
            if quote["prev_close"] != 0:
                quote["change_pct"] = round(
                    (quote["change"] / quote["prev_close"]) * 100, 2
                )

        cache[key] = quote
        return quote

    except Exception as e:
        logger.exception("[fetch_quote] Failed for ticker=%s: %s", ticker, e)
        raise


@retry_on_rate_limit
def _fetch_info_with_retry(ticker: str) -> dict[str, Any]:
    """Fetch ticker info with retry on rate limit."""
    tk = yf.Ticker(ticker)
    return tk.info or {}


def fetch_weekly(ticker: str) -> pd.DataFrame:
    """Weekly OHLCV for multi-timeframe analysis."""
    try:
        return fetch_historical(ticker, period="2y", interval="1wk")
    except Exception as e:
        logger.exception("[fetch_weekly] Failed for ticker=%s: %s", ticker, e)
        raise


def fetch_monthly(ticker: str) -> pd.DataFrame:
    """Monthly OHLCV for multi-timeframe analysis."""
    try:
        return fetch_historical(ticker, period="5y", interval="1mo")
    except Exception as e:
        logger.exception("[fetch_monthly] Failed for ticker=%s: %s", ticker, e)
        raise
