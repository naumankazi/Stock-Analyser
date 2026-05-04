"""In-memory TTL cache for stock data to respect rate limits."""

from __future__ import annotations

from cachetools import TTLCache

# Cache market data for 5 minutes (300s) – keeps requests reasonable
_data_cache: TTLCache = TTLCache(maxsize=256, ttl=300)

# Cache full analysis results for 10 minutes
_analysis_cache: TTLCache = TTLCache(maxsize=128, ttl=600)


def get_data_cache() -> TTLCache:
    return _data_cache


def get_analysis_cache() -> TTLCache:
    return _analysis_cache
