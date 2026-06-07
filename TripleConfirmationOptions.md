
**"Triple Confirmation Intraday Trading Strategy"** 

1. **Supertrend**
2. **MACD (Moving Average Convergence Divergence)**
3. **VWAP (Volume Weighted Average Price)**

The goal is to take trades only when all three indicators support the same direction.

---

# Strategy Overview

The trader wants:

* High probability trades
* Small losses
* Large winners
* Risk-Reward of roughly **1:2 or better**

Instead of relying on a single indicator (which may be only ~50% accurate), he combines three indicators to improve trade quality.

---

# Indicators Setup

## 1. Supertrend

### Settings

Default:

* Length = 10
* Factor = 3

Video recommendation:

* Length = 20
* Factor = 2

This makes Supertrend react faster to trend changes.

---

## 2. MACD

Use default settings.

MACD provides:

* Bullish crossover
* Bearish crossover
* Histogram confirmation

---

## 3. VWAP

VWAP acts as a fair-value line.

General idea:

### Above VWAP

Market is relatively strong.

### Below VWAP

Market is relatively weak.

The trader uses VWAP mainly to avoid taking bad entries.

---

# Buy Entry Rules

A BUY trade requires all three confirmations.

---

## Condition 1: Supertrend Buy Signal

Supertrend changes from:

Red → Green

A buy arrow appears.

---

## Condition 2: MACD Bullish Crossover

Blue MACD line crosses ABOVE red signal line.

This indicates bullish momentum.

---

## Condition 3: Price Near or Above VWAP

Price should be:

* Near VWAP
* Slightly above VWAP

Avoid buying when price is far below VWAP.

---

# Buy Entry Process

### Step 1

Supertrend gives BUY signal.

### Step 2

MACD bullish crossover occurs.

The crossover can happen:

* Same candle
* 1–4 candles before/after

That's acceptable.

### Step 3

Check VWAP.

If price is near VWAP:

✅ Enter Long

---

# Example Buy Flow

```
Supertrend = Buy

MACD = Bullish Cross

Price ≈ VWAP

=> Buy Trade
```

---

# Sell / Short Entry Rules

All three confirmations again.

---

## Condition 1

Supertrend turns Red.

Sell arrow appears.

---

## Condition 2

MACD Bearish Crossover

Blue line crosses BELOW red line.

---

## Condition 3

Price Near or Above VWAP

The trader prefers short entries when:

Price is above VWAP and starts weakening.

---

# Example Short Flow

```
Supertrend = Sell

MACD = Bearish Cross

Price near/above VWAP

=> Short Trade
```

---

# Stop Loss Rules

This is important.

The trader does NOT use a fixed rupee stop-loss.

He uses market structure.

---

## Long Trade

Stop-loss is:

Below Supertrend line.

Usually around:

30–50 points

---

## Short Trade

Stop-loss is:

Above Supertrend line.

---

# Position Sizing

The video recommends:

### Initial Entry

Enter with smaller quantity.

Example:

```
500 quantity
```

---

## Add More Quantity (Re-entry)

Only if:

* Trend remains valid
* Supertrend still active
* MACD still bullish
* A strong candle pattern appears

Examples:

* Doji
* Hammer
* Rejection candle

Near support area.

Then quantity can be increased.

---

# Profit Booking Rules

This is the most important part of the strategy.

---

## Rule 1

When opposite MACD crossover appears:

Book 50% quantity.

Example:

Bought 100 lots.

MACD gives opposite signal.

Sell 50 lots.

Keep remaining 50 lots.

---

## Rule 2

When Supertrend reverses:

Exit remaining 100%.

No questions.

No hope.

No waiting.

---

# Full Exit Logic

### Long Trade

Entered Long

↓

MACD turns bearish

↓

Sell 50%

↓

Supertrend turns red

↓

Exit remaining 50%

Trade complete.

---

# Risk-Reward Concept

According to the video:

Typical loss:

```
50 points
```

Typical winner:

```
100+ points
```

Risk Reward:

```
1 : 2
```

or better.

---

# Why the Strategy Works

The speaker explains:

Even if accuracy is only 50%

Example:

10 Trades

### Losses

5 trades lose

50 points each

```
5 × 50 = -250 points
```

### Winners

5 trades win

100 points each

```
5 × 100 = +500 points
```

Net:

```
+250 points
```

Profitable despite only 50% accuracy.

---

# Intraday Rule

The strategy is mainly for intraday trading.

### Timeframe

Recommended:

**5-minute chart**

(For faster entries)

---

### End of Day

Close all positions before market close.

Do not carry intraday positions overnight.

---

# Complete Trading Checklist

Before entering any trade, ask:

### Buy Trade

✅ Supertrend Buy

✅ MACD Bullish Cross

✅ Price near/above VWAP

✅ Risk acceptable

→ Enter

---

### Sell Trade

✅ Supertrend Sell

✅ MACD Bearish Cross

✅ Price near/above VWAP

✅ Risk acceptable

→ Enter

---

# Simple Example

Suppose Bank Nifty is trading.

### 10:15 AM

Supertrend turns Green.

### 10:20 AM

MACD bullish crossover.

### Price

Near VWAP.

### Action

BUY.

---

### 11:30 AM

Trade moves up 120 points.

### MACD bearish crossover

Book 50%.

---

### 12:00 PM

Supertrend turns Red.

Exit remaining 50%.

Trade finished.

---

# Summary (The Entire Strategy in One Sentence)

**Take a trade only when Supertrend, MACD, and VWAP all support the same direction; keep stop-loss near the Supertrend level, book 50% profit on the opposite MACD crossover, and exit completely when Supertrend reverses.** 

One important note: the video claims this setup can achieve around 70% accuracy, but that is the creator's opinion. You should backtest it on Bank Nifty/Nifty data before risking real money.
