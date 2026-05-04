"""Dynamic stock universe fetcher — NSE India + Screener.in integration.

Supports:
1. NSE Official Indices — Nifty 50, Nifty 500, Sector Indices
2. Screener.in Public Screens — Parse stock lists from screen URLs
3. All NSE Stocks — Complete list via NSE Bhavcopy

Uses caching to avoid repeated API calls.

Authentication:
- For Screener.in screens/queries that require login, set environment variables:
  - SCREENER_USERNAME: Your Screener.in email
  - SCREENER_PASSWORD: Your Screener.in password
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

import pandas as pd

from app.cache.memory_cache import get_data_cache

logger = logging.getLogger(__name__)

# Try to import httpx, fallback to requests if not available
try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    import requests
    HTTP_CLIENT = "requests"


# ══════════════════════════════════════════════════════════════
# SCREENER.IN AUTHENTICATION
# ══════════════════════════════════════════════════════════════

# Cached authenticated session
_screener_session = None
_screener_session_expiry = None
SCREENER_SESSION_TTL = 3600  # 1 hour


def _get_screener_credentials() -> tuple[str | None, str | None]:
    """Get Screener.in credentials from environment variables."""
    username = os.environ.get("SCREENER_USERNAME")
    password = os.environ.get("SCREENER_PASSWORD")
    return username, password


def _get_screener_session():
    """Get authenticated Screener.in session (cached).
    
    Returns authenticated session or None if login fails/no credentials.
    """
    global _screener_session, _screener_session_expiry
    
    # Check if we have a valid cached session
    if _screener_session and _screener_session_expiry:
        if datetime.now() < _screener_session_expiry:
            return _screener_session
    
    username, password = _get_screener_credentials()
    if not username or not password:
        logger.debug("No Screener.in credentials configured")
        return None
    
    logger.info("Authenticating with Screener.in...")
    
    try:
        if HTTP_CLIENT == "httpx":
            session = httpx.Client(timeout=30, follow_redirects=True)
            
            # First get the login page to get CSRF token
            login_page = session.get("https://www.screener.in/login/", headers=SCREENER_HEADERS)
            
            # Extract CSRF token from the page
            csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_page.text)
            if not csrf_match:
                logger.warning("Could not find CSRF token on Screener.in login page")
                return None
            csrf_token = csrf_match.group(1)
            
            # Submit login form
            login_data = {
                "csrfmiddlewaretoken": csrf_token,
                "username": username,
                "password": password,
            }
            
            login_headers = {
                **SCREENER_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.screener.in/login/",
                "Origin": "https://www.screener.in",
            }
            
            response = session.post(
                "https://www.screener.in/login/",
                data=login_data,
                headers=login_headers,
            )
            
            # Check if login succeeded (redirects to home or stays on login)
            if "login" in str(response.url).lower() and response.status_code == 200:
                # Still on login page = login failed
                if "Invalid" in response.text or "error" in response.text.lower():
                    logger.warning("Screener.in login failed - invalid credentials")
                    return None
            
            logger.info("Screener.in authentication successful")
            _screener_session = session
            _screener_session_expiry = datetime.now() + timedelta(seconds=SCREENER_SESSION_TTL)
            return session
            
        else:
            # requests library
            session = requests.Session()
            
            # First get the login page to get CSRF token
            login_page = session.get("https://www.screener.in/login/", headers=SCREENER_HEADERS, timeout=30)
            
            # Extract CSRF token
            csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_page.text)
            if not csrf_match:
                logger.warning("Could not find CSRF token on Screener.in login page")
                return None
            csrf_token = csrf_match.group(1)
            
            # Submit login form
            login_data = {
                "csrfmiddlewaretoken": csrf_token,
                "username": username,
                "password": password,
            }
            
            login_headers = {
                **SCREENER_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.screener.in/login/",
                "Origin": "https://www.screener.in",
            }
            
            response = session.post(
                "https://www.screener.in/login/",
                data=login_data,
                headers=login_headers,
                timeout=30,
            )
            
            if "login" in response.url.lower() and response.status_code == 200:
                if "Invalid" in response.text or "error" in response.text.lower():
                    logger.warning("Screener.in login failed - invalid credentials")
                    return None
            
            logger.info("Screener.in authentication successful")
            _screener_session = session
            _screener_session_expiry = datetime.now() + timedelta(seconds=SCREENER_SESSION_TTL)
            return session
            
    except Exception as e:
        logger.warning("Screener.in authentication failed: %s", e)
        return None


class Universe(str, Enum):
    """Predefined stock universes."""
    NIFTY_50 = "nifty50"
    NIFTY_100 = "nifty100"
    NIFTY_200 = "nifty200"
    NIFTY_500 = "nifty500"
    NIFTY_MIDCAP_100 = "nifty_midcap_100"
    NIFTY_SMALLCAP_100 = "nifty_smallcap_100"
    NIFTY_IT = "nifty_it"
    NIFTY_BANK = "nifty_bank"
    NIFTY_PHARMA = "nifty_pharma"
    NIFTY_AUTO = "nifty_auto"
    NIFTY_FMCG = "nifty_fmcg"
    NIFTY_METAL = "nifty_metal"
    NIFTY_ENERGY = "nifty_energy"
    NIFTY_INFRA = "nifty_infra"
    NIFTY_REALTY = "nifty_realty"
    ALL_NSE = "all_nse"
    NSE100_DEFAULT = "nse100"  # NSE 100 stocks (default universe)


# NSE Index API endpoints
NSE_INDEX_URLS = {
    Universe.NIFTY_50: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050",
    Universe.NIFTY_100: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20100",
    Universe.NIFTY_200: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20200",
    Universe.NIFTY_500: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500",
    Universe.NIFTY_MIDCAP_100: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20MIDCAP%20100",
    Universe.NIFTY_SMALLCAP_100: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20SMLCAP%20100",
    Universe.NIFTY_IT: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20IT",
    Universe.NIFTY_BANK: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20BANK",
    Universe.NIFTY_PHARMA: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20PHARMA",
    Universe.NIFTY_AUTO: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20AUTO",
    Universe.NIFTY_FMCG: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20FMCG",
    Universe.NIFTY_METAL: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20METAL",
    Universe.NIFTY_ENERGY: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20ENERGY",
    Universe.NIFTY_INFRA: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20INFRA",
    Universe.NIFTY_REALTY: "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20REALTY",
}

# Fallback hardcoded lists (updated periodically) - used when NSE API is blocked
NIFTY_50_FALLBACK = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS",
]

NIFTY_BANK_FALLBACK = [
    "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
    "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", 
    "PNB.NS", "BANKBARODA.NS", "AUBANK.NS",
]

NIFTY_IT_FALLBACK = [
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
    "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "LTTS.NS",
]

# Common headers for NSE API (they block requests without proper headers)
# Note: NSE has aggressive anti-bot protection - these headers mimic a real browser
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Cache TTL for stock lists (1 hour)
UNIVERSE_CACHE_TTL = 3600

NSE_BASE_URL = "https://www.nseindia.com/"

# Retry settings for NSE
NSE_MAX_RETRIES = 3
NSE_RETRY_DELAY = 2  # seconds


def _make_request(
    url: str, 
    headers: dict = None, 
    timeout: int = 30,
    use_nse_cookies: bool = False
) -> Optional[dict | str]:
    """Make HTTP request using available client.
    
    Args:
        url: Target URL
        headers: Custom headers to merge
        timeout: Request timeout in seconds
        use_nse_cookies: Whether to first fetch NSE cookies (for NSE APIs only)
    """
    import time
    headers = headers or {}
    
    for attempt in range(NSE_MAX_RETRIES if use_nse_cookies else 1):
        try:
            if HTTP_CLIENT == "httpx":
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    if use_nse_cookies:
                        # Get cookies from NSE main page first - this is critical
                        # NSE requires valid session cookies
                        try:
                            home_response = client.get(NSE_BASE_URL, headers=NSE_HEADERS)
                            if home_response.status_code == 403:
                                logger.warning("NSE home page returned 403 (attempt %d/%d)", attempt + 1, NSE_MAX_RETRIES)
                                if attempt < NSE_MAX_RETRIES - 1:
                                    time.sleep(NSE_RETRY_DELAY * (attempt + 1))
                                    continue
                                return None
                        except Exception as e:
                            logger.warning("Failed to get NSE cookies: %s", e)
                            if attempt < NSE_MAX_RETRIES - 1:
                                time.sleep(NSE_RETRY_DELAY)
                                continue
                            return None
                        
                        # Small delay between requests to avoid rate limiting
                        time.sleep(0.5)
                        response = client.get(url, headers={**NSE_HEADERS, **headers})
                    else:
                        response = client.get(url, headers=headers)
                    
                    response.raise_for_status()
                    
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        return response.json()
                    return response.text
            else:
                session = requests.Session()
                if use_nse_cookies:
                    # Get cookies from NSE main page first
                    try:
                        home_response = session.get(NSE_BASE_URL, headers=NSE_HEADERS, timeout=timeout)
                        if home_response.status_code == 403:
                            logger.warning("NSE home page returned 403 (attempt %d/%d)", attempt + 1, NSE_MAX_RETRIES)
                            if attempt < NSE_MAX_RETRIES - 1:
                                time.sleep(NSE_RETRY_DELAY * (attempt + 1))
                                continue
                            return None
                    except Exception as e:
                        logger.warning("Failed to get NSE cookies: %s", e)
                        if attempt < NSE_MAX_RETRIES - 1:
                            time.sleep(NSE_RETRY_DELAY)
                            continue
                        return None
                    
                    time.sleep(0.5)
                    response = session.get(url, headers={**NSE_HEADERS, **headers}, timeout=timeout)
                else:
                    response = session.get(url, headers=headers, timeout=timeout)
                
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    return response.json()
                return response.text
                
        except Exception as e:
            logger.warning("HTTP request failed for %s (attempt %d): %s", url, attempt + 1, e)
            if attempt < NSE_MAX_RETRIES - 1 and use_nse_cookies:
                time.sleep(NSE_RETRY_DELAY * (attempt + 1))
                continue
            return None
    
    return None


# ══════════════════════════════════════════════════════════════
# NSE INDIA INTEGRATION
# ══════════════════════════════════════════════════════════════

def fetch_nse_index_constituents(index: Universe) -> list[str]:
    """Fetch stock list for an NSE index.
    
    Returns list of ticker symbols with .NS suffix.
    """
    cache = get_data_cache()
    cache_key = f"universe|nse|{index.value}"
    
    if cache_key in cache:
        logger.info("Cache hit for NSE index: %s", index.value)
        return cache[cache_key]
    
    url = NSE_INDEX_URLS.get(index)
    if not url:
        logger.warning("No URL configured for index: %s", index.value)
        return _get_fallback_list(index)
    
    logger.info("Fetching NSE index constituents: %s", index.value)
    
    data = _make_request(url, use_nse_cookies=True)
    if not data or not isinstance(data, dict):
        logger.warning("Failed to fetch NSE index data for %s, using fallback list", index.value)
        fallback = _get_fallback_list(index)
        if fallback:
            cache[cache_key] = fallback
        return fallback
    
    tickers = []
    try:
        stocks = data.get("data", [])
        for stock in stocks:
            symbol = stock.get("symbol")
            if symbol and symbol != "NIFTY 50" and not symbol.startswith("NIFTY"):
                tickers.append(f"{symbol}.NS")
        
        logger.info("Fetched %d stocks from %s", len(tickers), index.value)
        cache[cache_key] = tickers
        return tickers
        
    except Exception as e:
        logger.exception("Error parsing NSE index data: %s", e)
        fallback = _get_fallback_list(index)
        if fallback:
            cache[cache_key] = fallback
        return fallback


def _get_fallback_list(index: Universe) -> list[str]:
    """Get hardcoded fallback list for an index when NSE API fails."""
    fallback_map = {
        Universe.NIFTY_50: NIFTY_50_FALLBACK,
        Universe.NIFTY_BANK: NIFTY_BANK_FALLBACK,
        Universe.NIFTY_IT: NIFTY_IT_FALLBACK,
    }
    
    fallback = fallback_map.get(index, [])
    if fallback:
        logger.info("Using fallback list for %s (%d stocks)", index.value, len(fallback))
    return fallback


def fetch_all_nse_stocks() -> list[str]:
    """Fetch all actively traded NSE stocks.
    
    Uses NSE's equity stock list endpoint.
    """
    cache = get_data_cache()
    cache_key = "universe|nse|all"
    
    if cache_key in cache:
        logger.info("Cache hit for all NSE stocks")
        return cache[cache_key]
    
    logger.info("Fetching all NSE stocks...")
    
    # Try multiple approaches
    tickers = []
    
    # Approach 1: Use NSE stock listing API
    url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
    data = _make_request(url, use_nse_cookies=True)
    
    if data and isinstance(data, dict):
        try:
            stocks = data.get("data", [])
            for stock in stocks:
                symbol = stock.get("symbol")
                if symbol:
                    tickers.append(f"{symbol}.NS")
        except Exception as e:
            logger.warning("Error parsing F&O stocks: %s", e)
    
    # Approach 2: Combine major indices for broader coverage
    # Always do this to ensure comprehensive coverage (F&O only has ~200 stocks)
    if len(tickers) < 500:
        logger.info("Expanding coverage by combining major indices...")
        major_indices = [
            Universe.NIFTY_500,
            Universe.NIFTY_MIDCAP_100,
            Universe.NIFTY_SMALLCAP_100,
        ]
        
        all_tickers = set(tickers)  # Keep any F&O stocks we got
        for idx in major_indices:
            idx_tickers = fetch_nse_index_constituents(idx)
            all_tickers.update(idx_tickers)
        
        tickers = list(all_tickers)
    
    # Approach 3: If NSE is completely blocked, use Nifty 50 fallback
    if not tickers:
        logger.warning("NSE API completely blocked, using Nifty 50 fallback")
        tickers = NIFTY_50_FALLBACK.copy()
    
    logger.info("Total NSE stocks fetched: %d", len(tickers))
    
    if tickers:
        cache[cache_key] = tickers
    
    return tickers


# ══════════════════════════════════════════════════════════════
# SCREENER.IN INTEGRATION
# ══════════════════════════════════════════════════════════════

# Screener.in headers
# Note: Don't request brotli (br) compression unless brotli package is installed
SCREENER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.screener.in/",
}


def _make_screener_request(url: str) -> Optional[str]:
    """Make authenticated request to Screener.in.
    
    Uses authenticated session if credentials are configured,
    otherwise falls back to unauthenticated request.
    """
    # Try authenticated session first
    session = _get_screener_session()
    
    try:
        if session:
            if HTTP_CLIENT == "httpx":
                response = session.get(url, headers=SCREENER_HEADERS)
                response.raise_for_status()
                return response.text
            else:
                response = session.get(url, headers=SCREENER_HEADERS, timeout=30)
                response.raise_for_status()
                return response.text
        else:
            # Fall back to unauthenticated request
            return _make_request(url, headers=SCREENER_HEADERS, use_nse_cookies=False)
    except Exception as e:
        logger.warning("Screener.in request failed for %s: %s", url, e)
        return None


def _get_next_page_url(html: str, current_url: str) -> Optional[str]:
    """Extract next page URL from Screener.in pagination."""
    import urllib.parse
    
    # Get base URL (remove existing query params)
    parsed = urllib.parse.urlparse(current_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    
    # Method 1: Look for href="?page=N" with "Next" text
    next_match = re.search(r'href=["\'](\?page=\d+)["\'][^>]*>\s*Next', html, re.IGNORECASE)
    if next_match:
        return base_url + next_match.group(1)
    
    # Method 2: Extract current page from "page X of Y" and build next URL
    page_info = re.search(r'page\s*(\d+)\s*of\s*(\d+)', html, re.IGNORECASE)
    if page_info:
        current_page = int(page_info.group(1))
        total_pages = int(page_info.group(2))
        
        if current_page < total_pages:
            next_page = current_page + 1
            return f"{base_url}?page={next_page}"
    
    # Method 3: Find all page links and get next sequential one
    current_page_match = re.search(r'[?&]page=(\d+)', current_url)
    current_page = int(current_page_match.group(1)) if current_page_match else 1
    
    # Check if next page link exists in HTML
    next_page = current_page + 1
    if f'page={next_page}' in html:
        return f"{base_url}?page={next_page}"
    
    return None
    
    return None



def fetch_screener_in_stocks(screen_url: str, max_pages: int = 20) -> list[str]:
    """Fetch stock list from a public Screener.in screen URL.
    
    Supports URLs like:
    - https://www.screener.in/screens/71/
    - https://www.screener.in/screen/raw/?sort=&source=&query=...
    
    Handles pagination automatically - fetches all pages up to max_pages.
    
    For screens requiring login, set SCREENER_USERNAME and SCREENER_PASSWORD
    environment variables.
    
    Returns list of ticker symbols with .NS suffix.
    """
    cache = get_data_cache()
    cache_key = f"universe|screener|{hash(screen_url)}"
    
    if cache_key in cache:
        logger.info("Cache hit for Screener.in URL")
        return cache[cache_key]
    
    logger.info("Fetching stocks from Screener.in: %s", screen_url[:80])
    
    all_tickers = set()
    current_url = screen_url
    page_num = 1
    
    while current_url and page_num <= max_pages:
        logger.info("Fetching Screener.in page %d: %s", page_num, current_url)
        
        html = _make_screener_request(current_url)
        if not html or not isinstance(html, str):
            logger.warning("Failed to fetch Screener.in page %d (no response or non-text)", page_num)
            break
        
        # Log pagination info if found
        page_info = re.search(r'(\d+)\s*results?\s*found.*?page\s*(\d+)\s*of\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
        if page_info:
            logger.info("Screener.in reports: %s results, page %s of %s", 
                       page_info.group(1), page_info.group(2), page_info.group(3))
        
        # Check if we got a login/error page instead of stock data
        if "login" in html.lower() and "company" not in html.lower():
            username, _ = _get_screener_credentials()
            if username:
                logger.warning("Screener.in login may have failed - check credentials")
            else:
                logger.warning("Screener.in requires login. Set SCREENER_USERNAME and SCREENER_PASSWORD env vars")
            break
        
        page_tickers = _parse_screener_html(html)
        
        if not page_tickers:
            logger.debug("No more stocks found on page %d", page_num)
            break
        
        prev_count = len(all_tickers)
        all_tickers.update(page_tickers)
        new_count = len(all_tickers) - prev_count
        
        logger.info("Page %d: found %d stocks (%d new, %d total)", page_num, len(page_tickers), new_count, len(all_tickers))
        
        # DON'T stop on "0 new" - sidebar/nav elements repeat on every page
        # Instead, rely on pagination info or next page detection
        
        # Get next page URL
        next_url = _get_next_page_url(html, current_url)
        if next_url:
            logger.info("Next page URL: %s", next_url)
        else:
            logger.info("No next page found, stopping pagination")
        if next_url == current_url:
            logger.warning("Next URL same as current, stopping to avoid loop")
            break  # Avoid infinite loop
        current_url = next_url
        page_num += 1
        
        # Small delay between pages to be respectful
        if current_url:
            import time
            time.sleep(0.3)
    
    tickers = sorted(all_tickers)
    
    if tickers:
        cache[cache_key] = tickers
        logger.info("Total: parsed %d stocks from Screener.in (%d pages)", len(tickers), page_num)
    
    return tickers


def _parse_screener_html(html: str) -> list[str]:
    """Parse Screener.in HTML to extract stock symbols from the results table."""
    import html as html_module
    import urllib.parse
    
    tickers = []
    
    # FIRST: Decode HTML entities in the entire HTML before parsing
    # This converts &amp; -> &, &lt; -> <, etc.
    # So /company/GVT&amp;D/ becomes /company/GVT&D/
    html_decoded = html_module.unescape(html)
    
    # Try to extract just the results table/container to avoid sidebar duplicates
    # Screener.in uses class="data-table" or id="data-table" for results
    # But we'll search the full HTML since table extraction can miss results
    
    # Indian stock symbols: MUST start with letter, can contain A-Z, 0-9, &, -, _
    # Examples: M&M, BAJAJ-AUTO, L&T, GVT&D, TCS
    # This filters out BSE codes like 517286, 544291 which are pure numeric
    SYMBOL_PATTERN = r'/company/([A-Z][A-Z0-9&\-_]*)/'
    
    # Find all company links
    matches = re.findall(SYMBOL_PATTERN, html_decoded, re.IGNORECASE)
    
    # Known invalid symbols/HTML artifacts to exclude
    INVALID_SYMBOLS = {
        'CONSOLIDATED', 'STANDALONE', 'COMPANY', 'SCREEN', 'LOGIN', 'SVG', 'PNG', 'JPG', 'CSS', 'IMG', 'DIV', 'NAV',
        'TABLE', 'TBODY', 'THEAD', 'HTML', 'HEAD', 'BODY', 'SPAN',
        'HREF', 'DATA', 'TYPE', 'CLASS', 'STYLE', 'SCRIPT', 'LINK',
        'FORM', 'INPUT', 'BUTTON', 'LABEL', 'SELECT', 'OPTION',
    }
    
    # Combine all matches
    all_symbols = set()
    for match in matches:
        symbol = match.strip().upper()
        
        # URL-decode %26 -> &, %2D -> -
        symbol = urllib.parse.unquote(symbol)
        
        # Filter out invalid patterns
        if (2 <= len(symbol) <= 20 and
            symbol not in INVALID_SYMBOLS and
            not symbol.startswith('HTTP')):
            all_symbols.add(symbol)
    
    # Convert to .NS format
    tickers = [f"{s}.NS" for s in sorted(all_symbols)]
    
    logger.debug("Parsed %d unique symbols from page", len(tickers))
    
    return tickers


def fetch_screener_query_results(query: str) -> list[str]:
    """Run a Screener.in query and fetch results.
    
    This uses Screener.in's query syntax (not our custom syntax).
    Requires authentication - set SCREENER_USERNAME and SCREENER_PASSWORD
    environment variables.
    
    Example queries:
    - "Market Capitalization > 10000"
    - "Current ratio > 2 AND Debt to equity < 0.5"
    """
    cache = get_data_cache()
    cache_key = f"universe|screener_query|{hash(query)}"
    
    if cache_key in cache:
        logger.info("Cache hit for Screener.in query")
        return cache[cache_key]
    
    # URL encode the query
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    
    url = f"https://www.screener.in/screen/raw/?sort=&source=&query={encoded_query}"
    
    logger.info("Fetching Screener.in query results: %s", query[:50])
    
    html = _make_screener_request(url)
    if not html or not isinstance(html, str):
        logger.warning("Failed to fetch Screener.in query results")
        return []
    
    # Check if we got a login page
    if "login" in html.lower() and "company" not in html.lower():
        username, _ = _get_screener_credentials()
        if username:
            logger.warning("Screener.in login may have failed - check credentials")
        else:
            logger.warning("Screener.in query requires login. Set SCREENER_USERNAME and SCREENER_PASSWORD env vars")
        return []
    
    tickers = _parse_screener_html(html)
    
    if tickers:
        cache[cache_key] = tickers
        logger.info("Parsed %d stocks from Screener.in query", len(tickers))
    
    return tickers


# ══════════════════════════════════════════════════════════════
# UNIFIED UNIVERSE FETCHER
# ══════════════════════════════════════════════════════════════

def get_stock_universe(
    universe: str | Universe | None = None,
    screener_url: str | None = None,
    screener_urls: list[str] | None = None,
    screener_query: str | None = None,
    custom_tickers: str | None = None,
) -> tuple[list[str], str]:
    """Get stock universe based on parameters.
    
    Priority:
    1. custom_tickers (if provided)
    2. screener_urls (multiple URLs, if provided)
    3. screener_url (single URL, if provided)
    4. screener_query (if provided)
    5. universe (NSE index or predefined list)
    6. Default: nse100 (100 stocks from STOCK_UNIVERSE)
    
    Returns:
        Tuple of (list of tickers, source description)
    """
    # 1. Custom tickers
    if custom_tickers:
        tickers = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]
        tickers = [t if "." in t else f"{t}.NS" for t in tickers]
        return tickers, f"Custom ({len(tickers)} tickers)"
    
    # 2. Multiple Screener.in URLs
    if screener_urls and len(screener_urls) > 0:
        all_tickers = []
        successful_urls = 0
        failed_urls = []
        for url in screener_urls:
            url = url.strip()
            if not url:
                continue
            logger.info("Fetching from Screener.in URL: %s", url)
            tickers = fetch_screener_in_stocks(url)
            if tickers:
                all_tickers.extend(tickers)
                successful_urls += 1
                logger.info("✓ Success: %d stocks from %s", len(tickers), url)
            else:
                failed_urls.append(url)
                logger.warning("✗ Failed to fetch stocks from: %s", url)
        if failed_urls:
            logger.warning("Failed URLs: %s", failed_urls)
        if all_tickers:
            # Deduplicate while preserving order
            seen = set()
            unique_tickers = []
            for t in all_tickers:
                if t not in seen:
                    seen.add(t)
                    unique_tickers.append(t)
            return unique_tickers, f"Screener.in URLs ({len(unique_tickers)} stocks from {successful_urls} screens)"
        logger.warning("Failed to fetch from any Screener.in URL, falling back to default")
    
    # 3. Single Screener.in URL
    if screener_url:
        tickers = fetch_screener_in_stocks(screener_url)
        if tickers:
            return tickers, f"Screener.in URL ({len(tickers)} stocks)"
        logger.warning("Failed to fetch from Screener.in URL, falling back to default")
    
    # 3. Screener.in query
    if screener_query:
        tickers = fetch_screener_query_results(screener_query)
        if tickers:
            return tickers, f"Screener.in Query ({len(tickers)} stocks)"
        logger.warning("Failed to fetch from Screener.in query, falling back to default")
    
    # 4. Predefined universe
    if universe:
        # Convert string to enum if needed
        if isinstance(universe, str):
            try:
                universe = Universe(universe.lower())
            except ValueError:
                logger.warning("Unknown universe: %s, using default", universe)
                universe = Universe.NSE100_DEFAULT
        
        if universe == Universe.NSE100_DEFAULT:
            # Use NSE 100 stocks (default universe)
            from app.engine.screener import STOCK_UNIVERSE
            tickers = []
            for sector_stocks in STOCK_UNIVERSE.values():
                for stock in sector_stocks:
                    tickers.append(stock["ticker"])
            return tickers, "NSE 100 (default)"
        
        elif universe == Universe.ALL_NSE:
            tickers = fetch_all_nse_stocks()
            if tickers:
                return tickers, f"All NSE ({len(tickers)} stocks)"
        
        else:
            # NSE Index
            tickers = fetch_nse_index_constituents(universe)
            if tickers:
                return tickers, f"{universe.value.upper()} ({len(tickers)} stocks)"
    
    # 5. Default: nse100
    from app.engine.screener import STOCK_UNIVERSE
    tickers = []
    for sector_stocks in STOCK_UNIVERSE.values():
        for stock in sector_stocks:
            tickers.append(stock["ticker"])
    return tickers, "NSE 100 (default)"


def get_available_universes() -> dict[str, str]:
    """Return available universe options with descriptions."""
    return {
        "nse100": "118 top Indian stocks by market cap (default, always available)",
        "nifty50": "Nifty 50 index constituents (requires NSE access)",
        "nifty100": "Nifty 100 index constituents (requires NSE access)",
        "nifty200": "Nifty 200 index constituents (requires NSE access)",
        "nifty500": "Nifty 500 index constituents (~500 stocks, requires NSE access)",
        "nifty_midcap_100": "Nifty Midcap 100 index (requires NSE access)",
        "nifty_smallcap_100": "Nifty Smallcap 100 index (requires NSE access)",
        "nifty_it": "Nifty IT sector index (requires NSE access)",
        "nifty_bank": "Nifty Bank sector index (requires NSE access)",
        "nifty_pharma": "Nifty Pharma sector index (requires NSE access)",
        "nifty_auto": "Nifty Auto sector index (requires NSE access)",
        "nifty_fmcg": "Nifty FMCG sector index (requires NSE access)",
        "nifty_metal": "Nifty Metal sector index (requires NSE access)",
        "nifty_energy": "Nifty Energy sector index (requires NSE access)",
        "nifty_infra": "Nifty Infrastructure sector index (requires NSE access)",
        "nifty_realty": "Nifty Realty sector index (requires NSE access)",
        "all_nse": "All actively traded NSE stocks (~600+, requires NSE access)",
    }
