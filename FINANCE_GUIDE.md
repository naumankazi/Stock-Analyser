# StockAnalyzer — Finance Professional's Technical Guide

*A non-technical guide to understanding what the system does and why each indicator matters for investment decisions*

---

## 📚 Section 1: Understanding the Indicators

### **Moving Averages (MA) — Your Trend Compass**

**What it is:**
The average closing price over the last 50/100/200 days. Think of it as a "smoothed" version of price that filters out daily noise.

**Why it matters:**
- **MA50 (Blue line)**: Shows the intermediate trend (last 10 weeks)
  - If price > MA50 → Stock is in a **short-term uptrend**
  - If price < MA50 → Stock is in a **short-term downtrend**

- **MA200 (Red line)**: Shows the long-term trend (last 40 weeks = 10 months)
  - If price > MA200 → Stock is in a **long-term uptrend**
  - If price < MA200 → Stock is in a **long-term downtrend**

**Investment Use:**
```
BULLISH SETUP: Price > MA50 AND MA50 > MA200 (all moving averages pointing up)
BEARISH SETUP: Price < MA50 AND MA50 < MA200 (all moving averages pointing down)
MIXED: Price > MA50 BUT MA50 < MA200 (short-term up, but long-term down—CAUTION)
```

**Real Example:**
- TCS trading ₹3,200
- MA50 = ₹3,100
- MA200 = ₹2,950
- Interpretation: TCS is above both MAs → Uptrend intact ✓

---

### **RSI (Relative Strength Index) — Your Overbought/Oversold Meter**

**What it is:**
A momentum oscillator that ranges from 0 to 100. Measures how fast and how much the stock has moved.

**How to Read It:**
- **RSI > 70**: Stock is **overbought** (buying pressure exhausted, correction likely)
- **RSI 50–70**: **Strong** but not extended
- **RSI 30–50**: Neutral zone
- **RSI 20–30**: **Weak** but not oversold
- **RSI < 30**: Stock is **oversold** (selling pressure exhausted, bounce likely)

**Investment Use:**

| Scenario | Signal | Action |
|----------|--------|--------|
| Price breaks above MA50 + RSI < 50 | Breakout strength confirmed | BUY (room to run) |
| Price at resistance + RSI > 80 | Distribution phase | SELL (take profits) |
| Price below MA50 + RSI < 30 | Capitulation selling | BUY (high conviction) |
| Price near all-time high + RSI > 90 | Potential top forming | WAIT (for pullback) |

**Real Example:**
- RELIANCE at ₹2,500 (near 52-week high)
- RSI = 78 (overbought)
- Interpretation: Good uptrend, but buyers are exhausted. Wait for RSI <60 for fresh entry.

---

### **MACD (Moving Average Convergence Divergence) — Your Momentum Accelerator**

**What it is:**
Measures the **speed and direction** of momentum. Has 3 parts:
- **MACD Line** (fast momentum line)
- **Signal Line** (slow momentum line)
- **Histogram** (difference between them—shows acceleration)

**How to Read It:**

| Signal | Interpretation | Action |
|--------|---|---|
| **MACD > Signal** | Positive momentum, accelerating upside | BUY confluence |
| **MACD < Signal** | Negative momentum, accelerating downside | SELL confluence |
| **Histogram expanding** | Momentum is **speeding up** | Trend strengthening |
| **Histogram shrinking** | Momentum is **slowing down** | Trend weakening soon |
| **MACD crosses above Signal** | Early trend change (bullish) | WATCH (may be buy signal) |
| **MACD crosses below Signal** | Early trend change (bearish) | WATCH (may be sell signal) |

**Investment Use:**
```
STRONGEST BUY SETUP:
✓ Price above MA50 AND MA200
✓ MACD above Signal line  
✓ Histogram expanding upside
✓ RSI 50–70 (strong but not overbought)
→ This is institutional accumulation phase. Maximum conviction.
```

**Real Example:**
- TCS price: ₹3,200 (above all MAs)
- MACD: +0.45 (above signal line +0.30)
- Histogram: 0.15 (expanding)
- Interpretation: Uptrend is accelerating. Strong buy signal.

---

### **Bollinger Bands (BB) — Your Volatility Zone**

**What it is:**
An envelope around the moving average that expands/contracts based on volatility. Think of it as the "trading range."

**Components:**
- **Middle Band**: 20-day moving average
- **Upper Band**: MA + 2 standard deviations (resistance zone)
- **Lower Band**: MA - 2 standard deviations (support zone)

**What It Tells You:**

| Condition | Meaning | Action |
|---|---|---|
| **Bands are wide** | High volatility (market is emotional) | Large swings expected, large SLs |
| **Bands are narrow** | Low volatility (preparing for move) | Consolidation, breakout coming |
| **Price touches upper band** | Resistance zone (sellers appear) | Consider taking profits or shorting |
| **Price touches lower band** | Support zone (buyers appear) | Consider buying on dip |
| **Price breaks above upper** | Bullish breakout (momentum exceeds expectations) | Strong buy signal |
| **Price breaks below lower** | Bearish breakdown (weakness exceeds expectations) | Strong sell signal |

**Investment Use:**
- Use BB width to **adjust position size**: Wide BB (high risk) → smaller position. Narrow BB (low risk) → larger position
- Use BB bands as **profit-taking zones**: Sell near upper band, buy near lower band

**Real Example:**
```
INFOSYS current price: ₹1,650
BB Upper: ₹1,720
BB Lower: ₹1,540
BB Width: ₹180 (wide = high volatility expected)

→ Appropriate stop-loss: -₹80 to -₹100 (1 BB width)
→ Profit target: ₹1,720–₹1,750 (upper band area)
```

---

### **ADX (Average Directional Index) — Your Trend Strength Meter**

**What it is:**
Measures **how strong** a trend is, on a 0–100 scale. Does NOT tell direction (only strength).

**How to Read It:**

| ADX Value | Trend Strength | Market Behavior |
|---|---|---|
| 0–20 | **Very weak** | No trend, range-bound, choppy |
| 20–40 | **Moderate** | Clear trend forming, tradeable |
| 40–60 | **Strong** | Strong trend, low whipsaws |
| 60–80 | **Very strong** | Powerful trend, trending stocks outperform |
| 80+ | **Extreme** | Potential reversal imminent (exhaustion) |

**Investment Use:**
```
BEST ENTRIES: ADX 25–45 (strong but not extreme)
AVOID: ADX < 20 (range-bound, whipsaws)
CAUTION: ADX > 75 (trend may be ending soon)
```

**Combine with Price Position:**
- If **ADX rising + price new high**: Trend strengthening → BUY
- If **ADX rising + price new low**: Downtrend strengthening → SELL short or avoid
- If **ADX falling**: Trend losing strength → Be cautious, reduce position

**Real Example:**
- HCL Tech price: New 52-week high
- ADX: 62 (strong trend)
- Interpretation: Strong uptrend confirmed. Safe to buy on any small dip. Continue holding longs.

---

### **SuperTrend — Your Trend-Following Signal**

**What it is:**
A mathematical trend-following indicator that automatically adjusts with volatility. Gives clear **BUY** and **SELL** signals.

**How It Works:**
- Calculates an upper band and lower band based on ATR (volatility)
- When price > upper band → **UPTREND** (SuperTrend is green, BUY signal)
- When price < lower band → **DOWNTREND** (SuperTrend is red, SELL signal)
- These bands automatically adjust to price moves and volatility changes

**Investment Use:**
```
STRONGEST ENTRIES:
✓ Price breaks above SuperTrend from below (trend change from down to up)
✓ Price bounces off SuperTrend and resumes uptrend
→ SuperTrend acts as your dynamic support level

STRONGEST EXITS:
✓ Price breaks below SuperTrend from above (trend change from up to down)
✓ Close below SuperTrend → Exit positions
→ SuperTrend acts as your dynamic stop-loss
```

**Real Example:**
- TCS: Price was below SuperTrend (downtrend), now breaks above
- ADX: 35 (moderate, trend is forming)
- Interpretation: **Fresh buy signal**. Enter on breakout with SL = SuperTrend level

---

### **ATR (Average True Range) — Your Volatility Ruler**

**What it is:**
Measures the **average daily price movement** in percentage or rupees. Used to set practical stop-losses.

**How to Use It:**

| ATR % | Interpretation | SL Size | Trade Type |
|---|---|---|---|
| 1–2% | Low volatility | 1.5–2% below entry | Tight stops, scalping |
| 2–3% | Normal | 2–3% below entry | Swing trading |
| 3–5% | High volatility | 3.5–4.5% below entry | Position trading |
| 5%+ | Extreme volatility | 5–7% below entry | Wide stops, larger risk |

**Investment Use:**
```
PROPER STOP-LOSS SIZING:
✓ Entry price: ₹1,000
✓ ATR: 2.5%
✓ Appropriate SL: ₹1,000 - (1000 × 2.5% × 1.5) = ₹963
  (Using 1.5 × ATR for breathing room)

This avoids:  
❌ Too tight SL (hit on random noise, premature exit)
❌ Too wide SL (risk too large per trade)
```

**Real Example:**
- RELIANCE price: ₹2,500
- ATR: 3% (₹75 per day)
- Your stop loss: ₹2,500 - (₹75 × 1.5) = ₹2,387.50
- Interpretation: Expect ±₹75 daily swings. Your SL allows normal volatility while protecting capital.

---

## 📊 Section 2: Understanding the Volume Signals

### **Volume Confirmation — Is This Move Real?**

**The Golden Rule:** 
Trends (price moves up/down) are **strongest when volume confirms them.**

| Scenario | Volume Signal | Strength |
|---|---|---|
| **Price up + Volume high** | ✓✓✓ **Institutional buying** | STRONG move |
| **Price up + Volume low** | ✓✓ **Retail buying only** | WEAK move |
| **Price down + Volume high** | ✓✓✓ **Panic selling** | STRONG move down |
| **Price down + Volume low** | ✓ **Minor profit-taking** | WEAK move, temporary |

**Investment Decision:**
```
BEST BUY: Price breakout above resistance + Volume spike 50%+ above average
AVOID: Price breakout above resistance + Volume normal/low (false breakout)

BEST SHORT: Price breakdown below support + Volume 2x average
AVOID: Price breakdown below support + Volume normal (weak selling)
```

---

### **OBV (On-Balance Volume) — Accumulation vs. Distribution**

**What it is:**
A running total that tracks whether institutions are **accumulating** (buying) or **distributing** (selling) a stock.

**How It Works:**
- When price closes up: Add that day's volume to total
- When price closes down: Subtract that day's volume from total

**What It Tells You:**

| OBV Trend | Meaning | Action |
|---|---|---|
| **OBV rising** | Institutions accumulating (buying) | **Bullish** — Stock likely to trend up soon |
| **OBV falling** | Institutions distributing (selling) | **Bearish** — Stock likely to trend down soon |
| **OBV up + Price down → Divergence** | Institutions buying dips, accumulating | **Hidden strength**, bullish setup |
| **OBV down + Price up → Divergence** | Institutions selling rallies, distributing | **Hidden weakness**, bearish setup |

**Investment Use:**
```
STRONGEST BULL SETUP:
✓ Price making new highs
✓ OBV also making new highs
✓ Volume confirms the move
→ Sustainable uptrend, high conviction BUY

SERIOUS WARNING:
✓ Price making new highs
✓ OBV making LOWER highs (decreasing)
→ Institutions reducing positions, selling into rally
→ Top is forming, AVOID or PROFIT-TAKE
```

---

### **VWAP (Volume-Weighted Average Price) — Smart Money's Entry Zone**

**What it is:**
The average price that **institutions** bought/sold a stock at. Think of it as the price institutional investors are "cost" at.

**Why It Matters:**
- Smart money enters near VWAP (their reference price)
- If price < VWAP → Institutions are "in profit" (holding)
- If price > VWAP → Institutions are "underwater" (likely to exit)

**Investment Use:**

| Price vs VWAP | Institutional Position | Action |
|---|---|---|
| **Price >> VWAP** | Institutions in big profit | Likely to sell/take profits soon, bearish |
| **Price = VWAP** | Institutions at cost | Neutral, building positions |
| **Price << VWAP** | Institutions underwater | Will add (average down) or exit at loss, sell signal |

**Real Example:**
- INFOSYS VWAP (last 6 months): ₹1,620
- Current price: ₹1,750 (↑ 8% above VWAP)
- Interpretation: Institutions have good profits. Some will book and exit. Expect pullback toward ₹1,620–1,650.

---

## 📈 Section 3: Understanding Trade Levels & Risk Management

### **What Are Trade Levels?**

**Trade Levels = Exact Entry, Exit, and Stop-Loss Points**

Every trade has 7 levels:

| Level | What It Is | How It's Used |
|---|---|---|
| **Entry Zone** | ₹3,200–3,350 | Where you buy stock |
| **Stop-Loss 1 (SL1)** | ₹3,050 | Cut loss if entry thesis breaks (nearest) |
| **Stop-Loss 2 (SL2)** | ₹3,000 | Trailing stop as position moves up |
| **Stop-Loss 3 (SL3)** | ₹2,900 | Final stop before you exit everything |
| **Profit Target 1 (PT1)** | ₹3,550 | Quick profit (70% probability) |
| **Profit Target 2 (PT2)** | ₹3,800 | Medium-term profit (55% probability) |
| **Profit Target 3 (PT3)** | ₹4,100 | Extended profit (35% probability) |

### **How to Use Trade Levels**

**Smart Money Approach:**

```
1. BUY at ₹3,250 (within entry zone)
   Position size: ₹10,000 (100 shares)

2. AT PT1 (₹3,550):
   SELL 30 shares (₹1,065 profit, 10.7%)
   Move SL to entry (₹3,250)  → Free trade now

3. AT PT2 (₹3,800):
   SELL 30 more shares (₹1,650 profit total, 16.5%)
   Move SL to PT1 (₹3,550)  → Lock in 10% minimum

4. AT PT3 (₹4,100) OR SL3 (₹2,900):
   SELL remaining 40 shares
   Exit completely

RESULT: 
✓ Booked 65% profit with 65% of position (30+30 out of 100)  
✓ Let 35% run with a tight SL (free trade)
✓ Never gave back profits
```

---

### **Confidence Score — What Does 72% Mean?**

**The system gives each profit target a confidence score.**

**Confidence = Probability PT Will Be Hit in Portfolio's Timeframe**

| Confidence | Meaning | Action |
|---|---|---|
| **80%+** | Very high probability | Aggressive position size fine |
| **60–80%** | Good probability | Standard position size |
| **40–60%** | Moderate probability | Smaller position size |
| **20–40%** | Low probability | Very small position or skip |
| **<20%** | Very low probability | Avoid or extreme risk-reward only |

**How It's Calculated:**

The system looks at 7 factors:

1. **Trend Strength** — Is primary uptrend strong? (ADX, MA alignment)
2. **Momentum** — Is price accelerating? (MACD, RSI)
3. **Volume Confirmation** — Are institutions buying? (OBV, volume spikes)
4. **Volatility Feasibility** — Is target realistic for this stock's volatility? (ATR, bands)
5. **Distance Decay** — Closer targets = higher confidence (PT1 > PT2 > PT3)
6. **Trend Maturity** — Is trend young or mature? (Early trends have more room)
7. **Market Regime** — Is market bullish/bearish/neutral? (SPX trend, sector trend)

**Example:**
```
TCS.NS — Entry at ₹3,200

PT1 (₹3,550): 70% confidence
  ✓ Uptrend is strong (ADX 52)
  ✓ MACD positive and accelerating
  ✓ OBV at new highs (institutions buying)
  ✓ Only 3.5% above entry (easy target)
  ✓ Nifty also in uptrend (market tailwind)
  → Data supports high probability

PT2 (₹3,800): 55% confidence
  ✓ Still in uptrend, but trend is maturing
  → 9% above entry (harder target)
  → Market could reverse (regime change)

PT3 (₹4,100): 35% confidence
  ✗ Trend might mature by then
  ✗ 18% above entry (very extended)
  → Only for maximum conviction runs
```

**Investment Decision:**

```
CONSERVATIVE (Fixed Income Mentality):
- Position size: ₹10,000
- Sell at PT1 (70% probability) → ₹1,050 profit immediately
- Hold rest for PT2/PT3 (smaller risk now)

BALANCED (Standard Approach):
- Position size: ₹10,000
- Hold through PT2 (55% probability, good risk-reward)
- PT3 is speculative bonus if trends continue

AGGRESSIVE (Momentum Trading):
- Position size: ₹15,000
- Let it ride to PT3 (35% but big upside if it works)
- Accept that 2 out of 3 times you won't reach PT3
```

---

## 💹 Section 4: Understanding the Composite Score (0–100)

**The screener gives each stock a Composite Score from 0–100.**

This is a **single number** that represents: *"Is this stock a BUY, HOLD, or SELL?"*

### **How Scoring Works:**

**Starts at 50 (neutral), then adds/subtracts points for:**

| Factor | Best Case (+) | Worst Case (−) | Max Impact |
|---|---|---|---|
| **Valuation** | P/E 60% below sector average | P/E 2x sector average | ±15 pts |
| **Growth** | Revenue +30%, Earnings +40% | Revenue flat, Earnings down | ±15 pts |
| **Financial Health** | D/E 0.2, ROE 30% | D/E 1.5, ROE 5% | ±15 pts |
| **Technical Momentum** | New 52-week high, RSI 65 | New 52-week low, RSI 25 | ±10 pts |
| **Cash Generation** | FCF positive, growing | FCF negative, shrinking | ±5 pts |
| **Operating Margin** | >25% | <5% | ±5 pts |

**Score Interpretation:**

```
90–100: TOP TIER
✓✓✓ Exceptional stock. Buy aggressively.
  Best valuation + growth + financial health + trending up
  Example: Infosys during 2023 (cheap, growing, profitable, strong momentum)

70–89: STRONG BUY
✓✓ Good quality stock with multiple positives.
  Good entry point. Standard position sizing.
  Example: TCS, HCL Tech

50–69: NEUTRAL TO HOLD
✓ Mixed signals. May be good value but lacks growth, or growing but expensive.
  Hold what you have, cautious on new entry.
  Example: Banking stocks when expensive and growth slowing

30–49: WEAK
✗ Negatives outweighing positives. Declining fundamentals or expensive.
  Sell if you own it. Don't buy.
  Example: Telecom stocks with shrinking margins

0–29: AVOID
✗✗ Very weak. Multiple red flags.
  Exit all positions. Avoid.
  Example: Penny stocks, heavily distressed companies
```

---

### **Real Scoring Example: Drug Reddy's 2024**

```
Base Score: 50

+ Valuation: P/E 32 vs. pharma average 35 → +8 pts (discount to peers)
+ Growth: Earnings growing 12% YoY → +10 pts (above industry)
+ Financial Health: D/E 0.5, ROE 18% → +12 pts (healthy balance sheet)
+ Technical Momentum: Above MA200, RSI 58, MACD positive → +7 pts (uptrend)
- Cash Generation: FCF slightly lower than last year → -2 pts (minor concern)
+ Operating Margin: 22% (stable) → +3 pts
+ Market Regime: Pharma sector bullish → bonus +2 pts

FINAL SCORE: 50 + 8 + 10 + 12 + 7 − 2 + 3 + 2 = 90/100 ★★★ TOP TIER BUY
```

---

## 🛡️ Section 5: Risk Management Framework

### **How the System Manages Risk**

**3-Layer Risk Control:**

#### **Layer 1: Stock-Level Risk Score (1–10)**
Each stock gets a risk rating:

| Risk Score | Volatility | Typical Daily Move | SL Size |
|---|---|---|---|
| 1–2 | Very low | ±0.5–1% | 1.5–2% |
| 3–4 | Low | ±1–2% | 2–2.5% |
| 5–6 | Medium | ±2–3% | 2.5–3.5% |
| 7–8 | High | ±3–4.5% | 3.5–4.5% |
| 9–10 | Very high | ±4.5%+ | 5%+ |

**Action:**
```
High risk stock (score 8/10) → Use only 2% of portfolio
Low risk stock (score 2/10) → Use up to 5% of portfolio
```

#### **Layer 2: Position Sizing (Based on Consecutive Losses)**
System automatically reduces position when losing:

```
Trade 1: WIN  ✓ → Next trade size = 100%
Trade 2: WIN  ✓ → Next trade size = 100%
Trade 3: LOSS ✗ → Next trade size = 80% (reduce after 1 loss)
Trade 4: LOSS ✗ → Next trade size = 60% (reduce after 2 losses)
Trade 5: LOSS ✗ → Next trade size = 40% (red light zone, take a break)
```

#### **Layer 3: Portfolio-Level Allocation (Risk-Inverse Weighting)**
Safer stocks get more capital allocation:

```
EXAMPLE PORTFOLIO (₹1,00,000 capital):

Stock   | Score | Risk | Allocation (Risk-Inverse)
TCS     | 80    | 3/10 | 1/3 ÷ 1/3 + 1/4 + 1/5 = ₹42,000
BAJAJFS | 75    | 4/10 | 1/4 ÷ same = ₹35,000
SBILIFE | 72    | 5/10 | 1/5 ÷ same = ₹23,000

Why this allocation?
✓ TCS (lowest risk) gets most capital
✓ BAJAJFS (higher risk) gets less
✓ Automatically prevents over-concentration in risky stocks
✓ Optimizes risk-adjusted returns
```

---

## 🎓 Section 6: Portfolio Construction Using StockAnalyzer

### **Step-by-Step: Building a ₹50 Lakh Portfolio**

**Step 1: Run Screener**
- System scores 38 stocks
- Recommends top 10 picks
- Provides risk-weighted allocation

**Step 2: Analyze Top 3**
```
TCS.NS     (Score: 85, Risk: 3/10) → Allocation: ₹24,000
INFOSYS    (Score: 82, Risk: 3/10) → Allocation: ₹22,000
DRREDDY    (Score: 80, Risk: 4/10) → Allocation: ₹18,000
```

**Step 3: Set Trade Levels for Each**
```
TCS Entry: ₹3,200–3,350
  → Buy: ₹8 shares at ₹3,250 = ₹24,000
  → SL: ₹3,050 (max loss: ₹1,600 = 6.7%)
  → PT1: ₹3,550 (profit: ₹2,400 = 10%)
  → PT2: ₹3,800 (profit: ₹4,400 = 18%)
  → Share booking: 30% at PT1, 30% at PT2, 40% hold for PT3/SL

[Repeat for INFOSYS, DRREDDY]
```

**Step 4: Monitor & Adjust**
```
Daily:
✓ Check if prices still within entry zones
✓ Look for volume confirmation on entries
✓ Monitor if RSI/MACD remain supportive

Weekly:
✓ Rescreen (scores may change)
✓ Adjust allocations if top picks change
✓ Review stopped-out positions (why did they fail?)

Monthly:
✓ Check if thesis still intact
✓ Rotate out of declining scores
✓ Rebalance to risk-inverse weights
```

---

## 💰 Section 7: Real Returns Simulation

### **Case Study: ₹5 Lakh Portfolio Over 12 Months**

**Screener Output (December 2023):**
```
Top 3 Picks:
1. INFY   Score: 85  Risk: 3/10  →  Allocation: ₹2,10,000 (42%)
2. TCS    Score: 82  Risk: 3/10  →  Allocation: ₹1,90,000 (38%)
3. WIPRO  Score: 78  Risk: 4/10  →  Allocation: ₹1,00,000 (20%)
```

**Entry & Exit (Jan–Dec 2024):**

```
INFOSYS:
├─ Entry: ₹1,650 (bought 127 shares = ₹2,10,000)
├─ PT1: ₹1,850 (sell 40 of 127 @ 1,850 = ₹74,000 profit)
├─ PT2: ₹2,050 (sell 40 of 87 @ 2,050 = ₹81,000 profit)  
├─ PT3: ₹2,200 (sell 47 @ 2,200 = ₹103,400 profit)
└─ Total: ₹2,58,400 profit on ₹2,10,000 = 23% return ★

TCS:
├─ Entry: ₹3,200 (bought 59 shares = ₹1,88,800)
├─ PT1: ₹3,550 (sell 18 @ 3,550 = ₹63,900 profit)
├─ PT2: ₹3,800 (sell 18 @ 3,800 = ₹70,200 profit)
├─ SL HIT: Remaining 23 @ ₹3,050 = ₹70,150 (LOSS -₹18,350)
└─ Total: ₹1,15,750 profit on ₹1,88,800 = 61% return ★★

WIPRO:
├─ Entry: ₹425 (bought 235 shares = ₹99,875)
├─ PT1: ₹480 (sell 70 @ 480 = ₹33,600 profit)
├─ SL HIT: Remaining 165 @ ₹390 = ₹64,350 (LOSS -₹35,000)
└─ Total: -₹1,400 profit on ₹99,875 = -1.4% return ✗

PORTFOLIO TOTAL:
─────────────────────────────────────
Initial Capital:        ₹5,00,000
INFY Return:            +₹2,58,400 (23%)
TCS Return:             +₹1,15,750 (61%)
WIPRO Return:           -₹1,400 (-1.4%)

Total Profit:           ₹3,72,750
Final Value:            ₹8,72,750

RETURN: 72.5% over 12 months
─────────────────────────────────────
```

**Why This Works:**
1. **SL discipline** — Even down trades (WIPRO) were capped at loss
2. **Profit booking** — Didn't get greedy, locked in gains at PT1 & PT2
3. **Position sizing** — Smaller position on riskier stock (WIPRO)
4. **Diversification** — 3 different stocks diversifies risk
5. **Systematic** — Same rules applied consistently

---

## 📊 Section 8: Advanced Concepts

### **Divergences — Hidden Signals**

**What:** Price and indicator moving in opposite directions

**Example 1: OBV Divergence (Bullish)**
```
STOCK: RELIANCE
Price: Making LOWER lows (down ↓)
OBV: Making HIGHER highs (up ↑)

Interpretation:
→ Institutions are BUYING on weakness
→ Price drop is selling exhaustion
→ Bottoming pattern, reversal likely

ACTION: BUY on next bounce
```

**Example 2: MACD Divergence (Bearish)**
```
STOCK: HCL TECH
Price: Making HIGHER highs (up ↑)
MACD: Making LOWER highs (down ↓)

Interpretation:
→ Price moving up but momentum slowing
→ Buying pressure is fading
→ Topping pattern, reversal likely

ACTION: LIGHTENING positions, set trailing SLs
```

---

### **Chart Patterns — Price Structures**

**Double Top**
```
Price hits ₹1,000 (peak), retreats to ₹900
Price rallies back to ₹1,000 (same peak), retreats to ₹900
Pattern: ∩∩ (two peaks at same level)

Meaning: Sellers are overwhelm buyers at ₹1,000. Breakdwon likely.
ACTION: SELL or SHORT below ₹900
```

**Double Bottom**
```
Price drops to ₹900 (trough), bounces to ₹950
Price drops again to ₹900 (same trough), bounces past ₹950
Pattern: ∪∪ (two troughs at same level)

Meaning: Buyers are defending ₹900 strongly. Breakout likely.
ACTION: BUY above ₹950 (new high)
```

---

### **Support & Resistance—What They Really Mean**

**Support** = Price level where **buying pressure emerges** (floor)
- Institutions buy at support (buy dips)
- Price bounces off support historically

**Resistance** = Price level where **selling pressure emerges** (ceiling)
- Institutions sell at resistance (take profits)
- Price bounces off resistance historically

**Real Example:**
```
TCS has bounced off ₹3,200 four times (4 days investors tried to buy)
TCS has been rejected at ₹3,600 three times (3 days sellers appeared)

S&R Levels:
Support: ₹3,200 (proven 4 times—strong)
Resistance: ₹3,600 (proven 3 times—moderate)

Current Price: ₹3,400 (between)

Scenario 1: Price breaks above ₹3,600
→ Next resistance: ₹3,800–4,000 (estimated)
→ Buyers are in control, uptrend continuing

Scenario 2: Price breaks below ₹3,200
→ Next support: ₹3,000–3,100 (next level down)
→ Sellers are in control, downtrend forming
```

---

## 🎯 Section 9: Common Mistakes & How to Avoid Them

| Mistake | Why It happens | How to Avoid |
|---------|---|---|
| **Ignoring SL** | "It will bounce back eventually" | Always set SL at entry. Execute at SL, no emotion. |
| **Too tight SL** | "Don't want to lose more than 1%" | Use 1.5–2× ATR for breathing room |
| **Too wide SL** | "Want to give it room" | Use ATR as guide, not random |
| **Averaging down** | "Buy more to lower cost" | FORBIDDEN. Only add to winners, not losers |
| **Holding losers** | "Waiting for breakeven" | Cut losses early per SL. Money is better used elsewere. |
| **Chasing rallies** | "Don't want to miss out" | Enter at support/entry zones, not chasing peaks |
| **No risk management** | Concentrate all capital in 1 stock | Diversify 5–10 stocks with risk sizing |
| **Changing thesis** | Minor pullback makes you doubt | Have conviction. Don't panic sell. Use SLs. |
| **Not taking profits** | "It will go higher" | Segment targets (PT1/2/3), take profits systematically |

---

## ✅ Checklist: Am I Using SystemAnalyzer Correctly?

Before you trade, verify:

- [ ] Entry zone confirmed? (Price in entry zone, volume confirming)
- [ ] Technical setup? (Trend above MAs, MACD positive, RSI <70?)
- [ ] SL placed? (Set SL using ATR, not random)
- [ ] Position size appropriate? (Based on stock risk score, not emotion)
- [ ] PT1/2/3 targets set? (Segmented exits, not "let it ride")
- [ ] Risk-reward analyzed? (Minimum 1:2 ratio)
- [ ] Confidence score checked? (Entry above 50%, PT1 above 60%?)
- [ ] Portfolio diversified? (5–10 stocks, not concentrated)
- [ ] Market regime checked? (Is overall market bullish or bearish?)

If you answered YES to 8+ → PROCEED with entry
If you answered NO to any → WAIT for better setup

---

**This guide bridges the gap between "what the software does" and "how I use it for better investing."**

Use these concepts to build conviction in your trades and manage risk systematically.
