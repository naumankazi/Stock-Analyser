"""Query-based stock screening engine — Screener.in-style filtering.

Supports queries like:
    Market Capitalization > 500 
    AND Current price > 1.05 * DMA 200 
    AND RSI > 50 
    AND RSI < 70

Uses a safe expression parser (no eval) and integrates with existing 
data fetching, indicator calculation, and caching infrastructure.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from app.cache.memory_cache import get_analysis_cache, get_data_cache
from app.engine.data_fetcher import fetch_historical, resolve_ticker
from app.engine.indicators import compute_rsi, compute_moving_averages
from app.engine.screener import STOCK_UNIVERSE

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# FIELD MAPPING — Screener.in style → internal fields
# ══════════════════════════════════════════════════════════════

FIELD_MAP: dict[str, str] = {
    # Price fields
    "current price": "close",
    "close": "close",
    "price": "close",
    "open": "open",
    "high": "high",
    "high price": "high",
    "low": "low",
    "low price": "low",
    
    # Moving averages (multiple variants for user convenience)
    "dma 50": "sma_50",
    "dma 200": "sma_200",
    "dma50": "sma_50",
    "dma200": "sma_200",
    "sma 50": "sma_50",
    "sma 200": "sma_200",
    "sma50": "sma_50",
    "sma200": "sma_200",
    "50 dma": "sma_50",
    "200 dma": "sma_200",
    "50 day moving average": "sma_50",
    "200 day moving average": "sma_200",
    "50 day ma": "sma_50",
    "200 day ma": "sma_200",
    "50dma": "sma_50",
    "200dma": "sma_200",
    "ma 50": "sma_50",
    "ma 200": "sma_200",
    "ma50": "sma_50",
    "ma200": "sma_200",
    "ema 50": "sma_50",  # Treat EMA as SMA for now
    "ema 200": "sma_200",
    "ema50": "sma_50",
    "ema200": "sma_200",
    "50 ema": "sma_50",
    "200 ema": "sma_200",
    "moving average 50": "sma_50",
    "moving average 200": "sma_200",
    
    # Momentum indicators
    "rsi": "rsi",
    "rsi 14": "rsi",
    
    # Volume
    "volume": "volume",
    "volume 1week average": "volume_1w_avg",
    "volume 1 week average": "volume_1w_avg",
    "avg volume": "volume_1w_avg",
    "average volume": "volume_1w_avg",
    
    # Returns
    "return over 3months": "return_3m",
    "return over 3 months": "return_3m",
    "3 month return": "return_3m",
    "3m return": "return_3m",
    "return 3m": "return_3m",
    
    # Fundamental fields
    "market capitalization": "market_cap",
    "market cap": "market_cap",
    "marketcap": "market_cap",
    "mcap": "market_cap",
    
    "debt to equity": "de_ratio",
    "debt to equity ratio": "de_ratio",
    "d/e": "de_ratio",
    "de ratio": "de_ratio",
    "de": "de_ratio",
    
    "return on capital employed": "roce",
    "roce": "roce",
    
    "return on equity": "roe",
    "roe": "roe",
    
    "price to earning": "pe_ratio",
    "price to earnings": "pe_ratio",
    "pe ratio": "pe_ratio",
    "pe": "pe_ratio",
    "p/e": "pe_ratio",
    
    "peg ratio": "peg_ratio",
    "peg": "peg_ratio",
    
    "operating margin": "operating_margin",
    "op margin": "operating_margin",
    
    "profit margin": "profit_margin",
    "net margin": "profit_margin",
    
    "revenue growth": "revenue_growth",
    "rev growth": "revenue_growth",
    
    "earnings growth": "earnings_growth",
    "profit growth": "earnings_growth",
    "yoy quarterly profit growth": "earnings_growth",
    "yoy profit growth": "earnings_growth",
    
    "free cash flow": "free_cash_flow",
    "fcf": "free_cash_flow",
    
    # 52-week metrics (multiple variants for user convenience)
    "52 week high": "high_52w",
    "52w high": "high_52w",
    "52 week low": "low_52w",
    "52w low": "low_52w",
    "high price 52 week": "high_52w",
    "high 52 week": "high_52w",
    "high 52w": "high_52w",
    "low price 52 week": "low_52w",
    "low 52 week": "low_52w",
    "low 52w": "low_52w",
    "52wk high": "high_52w",
    "52wk low": "low_52w",
    "yearly high": "high_52w",
    "yearly low": "low_52w",
    "year high": "high_52w",
    "year low": "low_52w",
    "1 year high": "high_52w",
    "1 year low": "low_52w",
    "1year high": "high_52w",
    "1year low": "low_52w",
    
    # Beta
    "beta": "beta",
}


class Operator(Enum):
    """Comparison operators."""
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "="
    NEQ = "!="


OPERATOR_MAP: dict[str, Operator] = {
    ">": Operator.GT,
    "<": Operator.LT,
    ">=": Operator.GTE,
    "<=": Operator.LTE,
    "=": Operator.EQ,
    "==": Operator.EQ,
    "!=": Operator.NEQ,
    "<>": Operator.NEQ,
}

OPERATOR_FUNCS: dict[Operator, Callable[[float, float], bool]] = {
    Operator.GT: lambda a, b: a > b,
    Operator.LT: lambda a, b: a < b,
    Operator.GTE: lambda a, b: a >= b,
    Operator.LTE: lambda a, b: a <= b,
    Operator.EQ: lambda a, b: abs(a - b) < 1e-9,
    Operator.NEQ: lambda a, b: abs(a - b) >= 1e-9,
}


@dataclass
class ParsedCondition:
    """A parsed condition from a query string."""
    left_expr: str  # e.g., "Current price" or "1.05 * DMA 200"
    operator: Operator
    right_expr: str  # e.g., "500" or "1.05 * DMA 200"
    raw: str  # Original condition string
    
    
@dataclass
class QueryResult:
    """Result of running a query."""
    query: str
    matched_tickers: list[str]
    total_screened: int
    errors: list[str]
    skipped_tickers: Optional[list[dict]] = None  # Tickers skipped due to missing data


@dataclass
class MultiQueryResult:
    """Result of running multiple queries."""
    duplicates: list[str]  # Tickers appearing in 2+ queries
    deduplicated: list[str]  # All unique tickers
    ordered: list[str]  # Duplicates first, then rest
    query_results: list[QueryResult]
    query_breakdown: dict[str, list[str]]  # query → matched tickers


# ══════════════════════════════════════════════════════════════
# SAFE EXPRESSION EVALUATOR (No eval!)
# ══════════════════════════════════════════════════════════════

class ExpressionEvaluator:
    """Safe arithmetic expression evaluator with field substitution.
    
    Supports:
    - Numbers: 500, 1.05, -10
    - Fields: DMA 200, Current price, RSI
    - Operators: +, -, *, /
    - Parentheses: (High price - Current price) / High price
    """
    
    def __init__(self, stock_data: dict[str, float]):
        self.data = stock_data
        self._tokens: list[str] = []
        self._pos: int = 0
        
    def evaluate(self, expr: str) -> Optional[float]:
        """Evaluate an expression and return the result."""
        try:
            # Normalize and tokenize
            normalized = self._normalize_expression(expr)
            logger.debug("Normalized expression: '%s' → '%s'", expr, normalized)
            
            self._tokens = self._tokenize(normalized)
            logger.debug("Tokens: %s", self._tokens)
            
            self._pos = 0
            
            if not self._tokens:
                return None
                
            result = self._parse_expression()
            
            if self._pos < len(self._tokens):
                unconsumed = self._tokens[self._pos:]
                # Only warn if there are meaningful unconsumed tokens
                if any(t not in ('', ' ') for t in unconsumed):
                    logger.warning(
                        "Unconsumed tokens in expression '%s': %s. "
                        "This may indicate an unrecognized field name. "
                        "Check spelling or add the field to FIELD_MAP.",
                        expr, unconsumed
                    )
                
            return result
        except Exception as e:
            logger.debug("Expression evaluation failed for '%s': %s", expr, e)
            return None
    
    def _normalize_expression(self, expr: str) -> str:
        """Normalize field names to internal keys.
        
        Replaces field names with markers like @@key@@ for unambiguous parsing.
        Uses @@ markers to avoid conflicts with field names that contain other field names
        (e.g., "high" in "high_52w").
        """
        expr = expr.strip()
        
        # Normalize multiple spaces to single space for consistent matching
        expr = re.sub(r'\s+', ' ', expr)
        
        # Sort field names by length (longest first) to avoid partial matches
        sorted_fields = sorted(FIELD_MAP.keys(), key=len, reverse=True)
        
        result = expr
        for field_name in sorted_fields:
            # Create pattern that handles variable whitespace between words
            # e.g., "dma 200" matches "DMA 200", "DMA  200", "dma200" won't match
            words = field_name.split()
            if len(words) > 1:
                # Multi-word field: allow flexible whitespace
                pattern_str = r'\s+'.join(re.escape(w) for w in words)
            else:
                # Single word field: use word boundaries to avoid matching inside @@markers@@
                # Include @ in the boundary check to prevent double-substitution
                pattern_str = r'(?<![a-zA-Z_@])' + re.escape(field_name) + r'(?![a-zA-Z_@])'
            
            pattern = re.compile(pattern_str, re.IGNORECASE)
            internal_key = FIELD_MAP[field_name]
            # Use @@key@@ format - @ symbol won't appear in field names
            result = pattern.sub(f"@@{internal_key}@@", result)
            
        return result
    
    def _tokenize(self, expr: str) -> list[str]:
        """Tokenize expression into numbers, operators, and field references.
        
        Uses regex for cleaner, more reliable tokenization.
        """
        tokens = []
        expr = expr.strip()
        
        # Regex pattern to match all token types:
        # - Field references: @@field_key@@
        # - Numbers (including decimals and negative): -?[0-9]+\.?[0-9]*
        # - Operators: +, -, *, /, (, )
        token_pattern = re.compile(
            r'@@([^@]+)@@'  # Field: capture content inside @@ @@
            r'|(-?[0-9]+\.?[0-9]*)'  # Number
            r'|([+\-*/()])'  # Operator
        )
        
        for match in token_pattern.finditer(expr):
            field_key, number, operator = match.groups()
            if field_key:
                tokens.append(f"FIELD:{field_key}")
            elif number:
                tokens.append(number)
            elif operator:
                tokens.append(operator)
        
        return tokens
    
    def _parse_expression(self) -> Optional[float]:
        """Parse additive expression (lowest precedence)."""
        return self._parse_additive()
    
    def _parse_additive(self) -> Optional[float]:
        """Parse + and - operations."""
        left = self._parse_multiplicative()
        if left is None:
            return None
            
        while self._pos < len(self._tokens) and self._tokens[self._pos] in ('+', '-'):
            op = self._tokens[self._pos]
            self._pos += 1
            right = self._parse_multiplicative()
            if right is None:
                return None
            if op == '+':
                left = left + right
            else:
                left = left - right
                
        return left
    
    def _parse_multiplicative(self) -> Optional[float]:
        """Parse * and / operations."""
        left = self._parse_unary()
        if left is None:
            return None
            
        while self._pos < len(self._tokens) and self._tokens[self._pos] in ('*', '/'):
            op = self._tokens[self._pos]
            self._pos += 1
            right = self._parse_unary()
            if right is None:
                return None
            if op == '*':
                left = left * right
            else:
                if abs(right) < 1e-10:
                    return None  # Division by zero
                left = left / right
                
        return left
    
    def _parse_unary(self) -> Optional[float]:
        """Parse unary minus."""
        if self._pos < len(self._tokens) and self._tokens[self._pos] == '-':
            self._pos += 1
            val = self._parse_primary()
            if val is None:
                return None
            return -val
        return self._parse_primary()
    
    def _parse_primary(self) -> Optional[float]:
        """Parse numbers, fields, and parenthesized expressions."""
        if self._pos >= len(self._tokens):
            return None
            
        token = self._tokens[self._pos]
        
        # Parentheses
        if token == '(':
            self._pos += 1
            result = self._parse_expression()
            if self._pos < len(self._tokens) and self._tokens[self._pos] == ')':
                self._pos += 1
            return result
            
        # Field reference
        if token.startswith("FIELD:"):
            field_key = token[6:]
            self._pos += 1
            value = self.data.get(field_key)
            if value is None:
                logger.debug("Field '%s' not found in stock data", field_key)
            return value
            
        # Number
        try:
            value = float(token)
            self._pos += 1
            return value
        except ValueError:
            logger.debug("Cannot parse token as number: %s", token)
            return None


# ══════════════════════════════════════════════════════════════
# QUERY PARSER
# ══════════════════════════════════════════════════════════════

class QueryParser:
    """Parse Screener.in-style query strings into structured conditions."""
    
    # Regex to split on AND (case-insensitive)
    AND_PATTERN = re.compile(r'\s+AND\s+', re.IGNORECASE)
    
    # Regex to split on OR (case-insensitive) - for future use
    OR_PATTERN = re.compile(r'\s+OR\s+', re.IGNORECASE)
    
    # Regex to find comparison operators (order matters: >= before >)
    OPERATOR_PATTERN = re.compile(r'(>=|<=|!=|<>|>|<|==|=)')
    
    def parse(self, query: str) -> tuple[list[ParsedCondition], list[str]]:
        """Parse a query string into conditions.
        
        Returns:
            Tuple of (conditions, errors)
        """
        conditions = []
        errors = []
        
        query = query.strip()
        if not query:
            errors.append("Empty query")
            return conditions, errors
            
        # Split by AND (MVP: AND-only support)
        parts = self.AND_PATTERN.split(query)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Find operator
            match = self.OPERATOR_PATTERN.search(part)
            if not match:
                errors.append(f"No comparison operator found in: '{part}'")
                continue
                
            op_str = match.group(1)
            op = OPERATOR_MAP.get(op_str)
            if not op:
                errors.append(f"Unknown operator '{op_str}' in: '{part}'")
                continue
                
            # Split into left and right expressions
            left = part[:match.start()].strip()
            right = part[match.end():].strip()
            
            if not left:
                errors.append(f"Missing left-hand expression in: '{part}'")
                continue
            if not right:
                errors.append(f"Missing right-hand expression in: '{part}'")
                continue
                
            conditions.append(ParsedCondition(
                left_expr=left,
                operator=op,
                right_expr=right,
                raw=part
            ))
            
        return conditions, errors
    
    def parse_with_or(self, query: str) -> tuple[list[list[ParsedCondition]], list[str]]:
        """Parse a query with OR support (returns list of AND-condition groups).
        
        Query like: (A > 10 AND B < 20) OR (C > 30)
        Returns: [[A>10, B<20], [C>30]]
        
        For MVP, OR groups are separated at top level only.
        """
        conditions_groups = []
        errors = []
        
        query = query.strip()
        if not query:
            errors.append("Empty query")
            return conditions_groups, errors
            
        # Split by OR first
        or_parts = self.OR_PATTERN.split(query)
        
        for or_part in or_parts:
            or_part = or_part.strip()
            # Remove surrounding parentheses if present
            if or_part.startswith('(') and or_part.endswith(')'):
                or_part = or_part[1:-1].strip()
                
            if not or_part:
                continue
                
            conditions, part_errors = self.parse(or_part)
            if conditions:
                conditions_groups.append(conditions)
            errors.extend(part_errors)
            
        return conditions_groups, errors


# ══════════════════════════════════════════════════════════════
# DATA PREPARATION
# ══════════════════════════════════════════════════════════════

def _safe_get_info(info: dict, *keys, default=None) -> Any:
    """Try multiple keys in yfinance info dict, return first non-None."""
    for k in keys:
        val = info.get(k)
        if val is not None:
            return val
    return default


def prepare_stock_data(ticker: str) -> dict[str, float] | None:
    """Prepare all data fields for a single stock.
    
    Combines:
    - Current price data (OHLCV)
    - Computed indicators (RSI, SMA 50/200)
    - Derived fields (return_3m, volume_1w_avg)
    - Fundamental data (P/E, D/E, ROE, etc.)
    """
    cache = get_analysis_cache()
    cache_key = f"query_data|{ticker}"
    
    if cache_key in cache:
        logger.debug("Cache hit for query data: %s", ticker)
        return cache[cache_key]
    
    try:
        # Resolve ticker
        resolved = resolve_ticker(ticker)
        
        # Fetch OHLCV data (2 years for indicator computation)
        df = fetch_historical(resolved, period="2y", interval="1d")
        if df.empty:
            logger.warning("No OHLCV data for %s", ticker)
            return None
            
        # Latest row for current values
        latest = df.iloc[-1]
        
        data: dict[str, float] = {}
        
        # ── Price fields ──
        data["close"] = float(latest.get("close", 0))
        data["open"] = float(latest.get("open", 0))
        data["high"] = float(latest.get("high", 0))
        data["low"] = float(latest.get("low", 0))
        data["volume"] = float(latest.get("volume", 0))
        
        # ── Computed indicators ──
        
        # RSI
        rsi_result = compute_rsi(df)
        data["rsi"] = float(rsi_result.get("rsi", 50))
        
        # Moving averages
        ma_result = compute_moving_averages(df, data["close"])
        if ma_result.get("ma_50") is not None:
            data["sma_50"] = float(ma_result["ma_50"])
        if ma_result.get("ma_200") is not None:
            data["sma_200"] = float(ma_result["ma_200"])
            
        # ── Derived fields ──
        
        # Return over 3 months (63 trading days)
        if len(df) >= 63:
            close_series = df["close"]
            price_63d_ago = float(close_series.iloc[-63])
            if price_63d_ago > 0:
                data["return_3m"] = ((data["close"] - price_63d_ago) / price_63d_ago) * 100
                
        # Volume 1-week average (5 trading days)
        if len(df) >= 5:
            volume_series = df["volume"]
            data["volume_1w_avg"] = float(volume_series.tail(5).mean())
            
        # 52-week high/low
        data["high_52w"] = float(df["high"].max())
        data["low_52w"] = float(df["low"].min())
        
        # ── Fundamental data ──
        try:
            tk = yf.Ticker(resolved)
            info = tk.info
            
            # Market cap (in crores for Indian markets, else as-is)
            mcap = _safe_get_info(info, "marketCap")
            if mcap:
                data["market_cap"] = float(mcap) / 1e7  # Convert to crores
                
            # P/E Ratio
            pe = _safe_get_info(info, "trailingPE", "forwardPE")
            if pe and pe > 0:
                data["pe_ratio"] = float(pe)
                
            # PEG Ratio
            peg = _safe_get_info(info, "pegRatio")
            if peg and peg > 0:
                data["peg_ratio"] = float(peg)
                
            # Debt to Equity
            de = _safe_get_info(info, "debtToEquity")
            if de is not None:
                data["de_ratio"] = float(de) / 100  # yfinance gives as percentage
                
            # ROE
            roe = _safe_get_info(info, "returnOnEquity")
            if roe is not None:
                data["roe"] = float(roe) * 100  # Convert to percentage
                
            # ROCE (not always available, use ROE as fallback)
            roce = _safe_get_info(info, "returnOnCapitalEmployed")
            if roce is not None:
                data["roce"] = float(roce) * 100
            elif "roe" in data:
                data["roce"] = data["roe"]  # Approximate with ROE
                
            # Operating Margin
            op_margin = _safe_get_info(info, "operatingMargins")
            if op_margin is not None:
                data["operating_margin"] = float(op_margin) * 100
                
            # Profit Margin
            profit_margin = _safe_get_info(info, "profitMargins")
            if profit_margin is not None:
                data["profit_margin"] = float(profit_margin) * 100
                
            # Revenue Growth
            rev_growth = _safe_get_info(info, "revenueGrowth")
            if rev_growth is not None:
                data["revenue_growth"] = float(rev_growth) * 100
                
            # Earnings Growth
            earn_growth = _safe_get_info(info, "earningsGrowth")
            if earn_growth is not None:
                data["earnings_growth"] = float(earn_growth) * 100
                
            # Free Cash Flow (in crores)
            fcf = _safe_get_info(info, "freeCashflow")
            if fcf is not None:
                data["free_cash_flow"] = float(fcf) / 1e7
                
            # Beta
            beta = _safe_get_info(info, "beta")
            if beta is not None:
                data["beta"] = float(beta)
                
        except Exception as e:
            logger.debug("Failed to fetch fundamentals for %s: %s", ticker, e)
            
        # Cache the result
        cache[cache_key] = data
        return data
        
    except Exception as e:
        logger.warning("Failed to prepare data for %s: %s", ticker, e)
        return None


# ══════════════════════════════════════════════════════════════
# CONDITION EVALUATION
# ══════════════════════════════════════════════════════════════

def evaluate_condition(stock_data: dict[str, float], condition: ParsedCondition) -> bool:
    """Evaluate a single condition against stock data.
    
    Args:
        stock_data: Dictionary of field -> value for the stock
        condition: Parsed condition to evaluate
        
    Returns:
        True if condition is satisfied, False otherwise
    """
    try:
        evaluator = ExpressionEvaluator(stock_data)
        
        # Evaluate left side
        left_value = evaluator.evaluate(condition.left_expr)
        if left_value is None:
            logger.debug("Left expression evaluated to None: %s", condition.left_expr)
            return False
            
        # Evaluate right side
        right_value = evaluator.evaluate(condition.right_expr)
        if right_value is None:
            logger.debug("Right expression evaluated to None: %s", condition.right_expr)
            return False
            
        # Apply operator
        op_func = OPERATOR_FUNCS[condition.operator]
        result = op_func(left_value, right_value)
        
        logger.debug(
            "Condition: %s %s %s → %s %s %s = %s",
            condition.left_expr, condition.operator.value, condition.right_expr,
            left_value, condition.operator.value, right_value, result
        )
        
        return result
        
    except Exception as e:
        logger.debug("Condition evaluation failed for '%s': %s", condition.raw, e)
        return False


def evaluate_all_conditions(
    stock_data: dict[str, float],
    conditions: list[ParsedCondition]
) -> bool:
    """Evaluate all conditions (AND logic) against stock data.
    
    Returns True only if ALL conditions are satisfied.
    """
    for condition in conditions:
        if not evaluate_condition(stock_data, condition):
            return False
    return True


def evaluate_all_conditions_with_details(
    stock_data: dict[str, float],
    conditions: list[ParsedCondition]
) -> tuple[bool, list[str]]:
    """Evaluate all conditions and return details about failures.
    
    Returns:
        Tuple of (all_passed, list of failure reasons)
    """
    failures = []
    evaluator = ExpressionEvaluator(stock_data)
    
    for condition in conditions:
        left_value = evaluator.evaluate(condition.left_expr)
        right_value = evaluator.evaluate(condition.right_expr)
        
        if left_value is None:
            failures.append(f"Missing field in '{condition.left_expr}'")
            continue
        if right_value is None:
            failures.append(f"Missing field in '{condition.right_expr}'")
            continue
            
        op_func = OPERATOR_FUNCS[condition.operator]
        if not op_func(left_value, right_value):
            failures.append(
                f"Failed: {condition.left_expr}={left_value:.2f} {condition.operator.value} {condition.right_expr}={right_value:.2f}"
            )
    
    return len(failures) == 0, failures


def evaluate_any_condition_group(
    stock_data: dict[str, float],
    condition_groups: list[list[ParsedCondition]]
) -> bool:
    """Evaluate condition groups with OR logic between groups.
    
    Returns True if ANY group's conditions are all satisfied.
    """
    for group in condition_groups:
        if evaluate_all_conditions(stock_data, group):
            return True
    return False


# ══════════════════════════════════════════════════════════════
# QUERY EXECUTION
# ══════════════════════════════════════════════════════════════

def get_default_stock_universe() -> list[str]:
    """Get all tickers from the default Shariah-compliant universe."""
    tickers = []
    for sector_stocks in STOCK_UNIVERSE.values():
        for stock in sector_stocks:
            tickers.append(stock["ticker"])
    return tickers


def run_query(
    query: str,
    stocks: list[str] | None = None,
    include_or: bool = False,
    universe: str | None = None,
    screener_url: str | None = None,
    screener_urls: list[str] | None = None,
    screener_query: str | None = None,
) -> QueryResult:
    """Execute a screening query against a stock universe.
    
    Args:
        query: Query string (e.g., "RSI > 50 AND RSI < 70")
        stocks: List of tickers to screen (if provided, overrides universe)
        include_or: Whether to parse OR conditions
        universe: Predefined universe (nifty50, nifty500, all_nse, etc.)
        screener_url: Screener.in public screen URL to fetch stocks from
        screener_urls: Multiple Screener.in public screen URLs (combined and deduplicated)
        screener_query: Screener.in query to fetch stocks from
        
    Returns:
        QueryResult with matched tickers and metadata
    """
    # Determine stock universe
    universe_source = "default"
    if stocks is None:
        from app.engine.stock_universe import get_stock_universe
        stocks, universe_source = get_stock_universe(
            universe=universe,
            screener_url=screener_url,
            screener_urls=screener_urls,
            screener_query=screener_query,
        )
    
    logger.info("Screening %d stocks from: %s", len(stocks), universe_source)
        
    parser = QueryParser()
    errors = []
    
    # Parse query
    if include_or:
        condition_groups, parse_errors = parser.parse_with_or(query)
        errors.extend(parse_errors)
        
        if not condition_groups:
            return QueryResult(
                query=query,
                matched_tickers=[],
                total_screened=len(stocks),
                errors=errors if errors else ["No valid conditions parsed"]
            )
    else:
        conditions, parse_errors = parser.parse(query)
        errors.extend(parse_errors)
        
        if not conditions:
            return QueryResult(
                query=query,
                matched_tickers=[],
                total_screened=len(stocks),
                errors=errors if errors else ["No valid conditions parsed"]
            )
        condition_groups = [conditions]  # Single AND group
    
    # ── Parallel data fetching ──
    # Pre-fetch all stock data in parallel for better performance
    logger.info("Pre-fetching data for %d stocks in parallel...", len(stocks))
    stock_data_map: dict[str, dict[str, float] | None] = {}
    
    # Use ThreadPoolExecutor for parallel fetching (I/O bound)
    max_workers = min(20, len(stocks))  # Cap at 20 parallel requests
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_ticker = {
            executor.submit(prepare_stock_data, ticker): ticker 
            for ticker in stocks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                stock_data_map[ticker] = future.result()
            except Exception as e:
                logger.warning("Error fetching data for %s: %s", ticker, e)
                stock_data_map[ticker] = None
    
    logger.info("Data fetched for %d stocks", len(stock_data_map))
    
    # Screen stocks using pre-fetched data
    matched = []
    skipped = []
    screened_count = 0
    
    for ticker in stocks:
        stock_data = stock_data_map.get(ticker)
        if stock_data is None:
            logger.debug("Skipping %s — no data", ticker)
            skipped.append({"ticker": ticker, "reason": "No data available"})
            continue
            
        screened_count += 1
        
        # Evaluate conditions with details
        all_passed, failures = evaluate_all_conditions_with_details(
            stock_data, condition_groups[0]  # For AND-only queries
        )
        
        if all_passed:
            matched.append(ticker)
            logger.info("Query match: %s", ticker)
        elif failures:
            # Only log first few failures for debugging
            skipped.append({
                "ticker": ticker,
                "reasons": failures[:3]  # Limit to 3 reasons
            })
    
    return QueryResult(
        query=query,
        matched_tickers=matched,
        total_screened=screened_count,
        errors=errors,
        skipped_tickers=skipped[:20]  # Limit to 20 for response size
    )


def run_multiple_queries(
    queries: list[str],
    stocks: list[str] | None = None,
    include_or: bool = False,
    universe: str | None = None,
    screener_url: str | None = None,
    screener_urls: list[str] | None = None,
    screener_query: str | None = None,
) -> MultiQueryResult:
    """Execute multiple screening queries and combine results.
    
    - Identifies duplicates (stocks appearing in 2+ queries)
    - Returns ordered results (duplicates first)
    
    Args:
        queries: List of query strings
        stocks: List of tickers to screen (if provided, overrides universe)
        include_or: Whether to parse OR conditions
        universe: Predefined universe (nifty50, nifty500, all_nse, etc.)
        screener_url: Screener.in public screen URL to fetch stocks from
        screener_urls: Multiple Screener.in public screen URLs (combined and deduplicated)
        screener_query: Screener.in query to fetch stocks from
        
    Returns:
        MultiQueryResult with deduplicated, ordered results
    """
    # Determine stock universe
    if stocks is None:
        from app.engine.stock_universe import get_stock_universe
        stocks, universe_source = get_stock_universe(
            universe=universe,
            screener_url=screener_url,
            screener_urls=screener_urls,
            screener_query=screener_query,
        )
        logger.info("Screening %d stocks from: %s", len(stocks), universe_source)
    
    # ── Parallel data fetching ──
    # Pre-fetch all stock data in parallel for better performance
    logger.info("Pre-fetching data for %d stocks in parallel...", len(stocks))
    stock_data_cache: dict[str, dict[str, float] | None] = {}
    
    max_workers = min(20, len(stocks))  # Cap at 20 parallel requests
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(prepare_stock_data, ticker): ticker 
            for ticker in stocks
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                stock_data_cache[ticker] = future.result()
            except Exception as e:
                logger.warning("Error fetching data for %s: %s", ticker, e)
                stock_data_cache[ticker] = None
    
    logger.info("Data fetched for %d stocks", len(stock_data_cache))
    
    # Run each query
    query_results: list[QueryResult] = []
    query_breakdown: dict[str, list[str]] = {}
    
    parser = QueryParser()
    
    for query in queries:
        # Parse query
        if include_or:
            condition_groups, parse_errors = parser.parse_with_or(query)
        else:
            conditions, parse_errors = parser.parse(query)
            condition_groups = [conditions] if conditions else []
        
        if not condition_groups:
            query_results.append(QueryResult(
                query=query,
                matched_tickers=[],
                total_screened=len(stocks),
                errors=parse_errors if parse_errors else ["No valid conditions"]
            ))
            query_breakdown[query] = []
            continue
        
        # Screen stocks using cached data
        matched = []
        screened_count = 0
        
        for ticker in stocks:
            stock_data = stock_data_cache.get(ticker)
            if stock_data is None:
                continue
                
            screened_count += 1
            
            if evaluate_any_condition_group(stock_data, condition_groups):
                matched.append(ticker)
        
        query_results.append(QueryResult(
            query=query,
            matched_tickers=matched,
            total_screened=screened_count,
            errors=parse_errors
        ))
        query_breakdown[query] = matched
    
    # Combine results
    ticker_counts: dict[str, int] = {}
    for result in query_results:
        for ticker in result.matched_tickers:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
    
    # Identify duplicates (appear in 2+ queries)
    duplicates = [t for t, count in ticker_counts.items() if count >= 2]
    
    # All unique tickers
    deduplicated = list(ticker_counts.keys())
    
    # Ordered: duplicates first, sorted by count descending, then rest
    duplicates_sorted = sorted(duplicates, key=lambda t: ticker_counts[t], reverse=True)
    non_duplicates = [t for t in deduplicated if t not in duplicates]
    ordered = duplicates_sorted + non_duplicates
    
    return MultiQueryResult(
        duplicates=duplicates_sorted,
        deduplicated=deduplicated,
        ordered=ordered,
        query_results=query_results,
        query_breakdown=query_breakdown
    )


# ══════════════════════════════════════════════════════════════
# QUERY VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_query(query: str) -> tuple[bool, list[str]]:
    """Validate a query string without executing it.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    parser = QueryParser()
    conditions, errors = parser.parse(query)
    
    if errors:
        return False, errors
        
    if not conditions:
        return False, ["No conditions found in query"]
    
    # Validate field references
    for condition in conditions:
        # Check if we can parse the expressions
        for expr in [condition.left_expr, condition.right_expr]:
            normalized = expr.lower()
            has_field = False
            
            # Check if any known field is referenced
            for field_name in FIELD_MAP.keys():
                if field_name in normalized:
                    has_field = True
                    break
                    
            # If no field and it's not a pure number, it's suspicious
            if not has_field:
                try:
                    float(expr.strip())
                except ValueError:
                    # Not a number, not a known field — might be invalid
                    # But could be a computed expression, so just warn
                    pass
    
    return True, []


def get_available_fields() -> dict[str, list[str]]:
    """Return all available fields grouped by category."""
    return {
        "Price": [
            "Current price", "Close", "Open", "High", "Low",
            "52 week high", "52 week low"
        ],
        "Moving Averages": [
            "DMA 50", "DMA 200", "SMA 50", "SMA 200"
        ],
        "Momentum": ["RSI"],
        "Volume": ["Volume", "Volume 1week average"],
        "Returns": ["Return over 3months"],
        "Valuation": ["Price to earning", "PEG ratio", "Market Capitalization"],
        "Financial Health": [
            "Debt to equity", "Return on equity", "Return on capital employed",
            "Operating margin", "Profit margin"
        ],
        "Growth": ["Revenue growth", "Earnings growth", "YOY Quarterly profit growth"],
        "Other": ["Free cash flow", "Beta"]
    }


def get_example_queries() -> list[str]:
    """Return example queries for documentation."""
    return [
        "RSI > 50 AND RSI < 70",
        "Market Capitalization > 500 AND Current price > 1.05 * DMA 200",
        "Price to earning < 30 AND Debt to equity < 0.5",
        "Current price > DMA 50 AND DMA 50 > DMA 200",
        "Return over 3months > 10 AND Operating margin > 15",
        "(High price - Current price) / High price < 0.1 AND RSI < 60",
    ]
