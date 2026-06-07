Source: 

# Momentum Option Selling Strategy

## Strategy Objective

This is a **directional option selling strategy** for **Nifty** (and optionally Sensex).

The idea is simple:

* First identify the market direction.
* Then wait for price to break an important level.
* Sell ATM (At-The-Money) options in the direction of momentum.
* Exit when momentum disappears.

---

# Indicators Required

Use a **5-minute Nifty chart**.

### Indicator 1: Pivot Points (Standard)

Only keep:

* R1 (Resistance)
* S1 (Support)

Remove:

* Pivot Point (Center)
* R2, R3
* S2, S3

### Indicator 2: SuperTrend

Settings:

* ATR Period = 7
* Multiplier = 3

---

# Understanding the Logic

## Step 1: Identify Direction

SuperTrend tells us the trend direction.

### Bullish Trend

* Price above SuperTrend
* SuperTrend is Green

Market is bullish.

### Bearish Trend

* Price below SuperTrend
* SuperTrend is Red

Market is bearish.

---

## Step 2: Identify Breakout Level

Use Pivot Levels.

### R1

Resistance level.

### S1

Support level.

The trade is only taken when price moves outside these levels.

This helps avoid many sideways market conditions.

---

# Entry Rules

## Bullish Setup (Sell Put)

Conditions:

✅ Price closes above R1

AND

✅ Price is above SuperTrend

When both conditions are true:

### Entry

Sell ATM Put

Example:

Nifty = 23,500

Sell:

* 23,500 PE (Current Expiry)

---

## Bearish Setup (Sell Call)

Conditions:

✅ Price closes below S1

AND

✅ Price is below SuperTrend

When both conditions are true:

### Entry

Sell ATM Call

Example:

Nifty = 23,200

Sell:

* 23,200 CE (Current Expiry)

---

# Visual Summary

## Put Selling

```
Price > R1
AND
Price > SuperTrend

→ Sell ATM Put
```

---

## Call Selling

```
Price < S1
AND
Price < SuperTrend

→ Sell ATM Call
```

---

# Exit Rules

There are only two exits.

## Exit Rule 1: SuperTrend Flip

### For Put Sell

If SuperTrend turns bearish:

Exit immediately.

---

### For Call Sell

If SuperTrend turns bullish:

Exit immediately.

---

## Exit Rule 2: Time Exit

Regardless of profit or loss:

Exit all positions at:

### 3:20 PM

No overnight positions.

---

# Risk Management Rules

These are extremely important.

## Rule 1: Maximum 3 Trades Per Day

After 3 entries:

Stop trading.

Even if another signal appears.

---

## Rule 2: No New Entry After 3:00 PM

After 3 PM:

Do not enter fresh trades.

Only manage existing trades.

---

## Rule 3: Trade Only When Conditions Match

Never trade because you "feel" the market will move.

Both must agree:

* SuperTrend direction
* Pivot breakout

If not:

No trade.

---

# Why This Strategy Works

The creator's logic is:

### Sideways Markets

Most option sellers lose money in volatile sideways markets.

Using R1 and S1 helps filter many of these situations.

Example:

```
Price stays between R1 and S1

→ No Trade
```

This avoids unnecessary trades.

---

### Trending Markets

When price breaks R1 or S1 and SuperTrend agrees:

The market usually has momentum.

Option selling benefits because:

* Time decay (Theta)
* Trend continuation

work together.

---

# Reward Structure

The strategy does NOT use a fixed target.

Profit comes from:

### 1. Theta Decay

ATM options lose value quickly.

### 2. Trend Continuation

As market moves in your direction, option premium collapses faster.

---

# Risk Structure

The risk is controlled by:

### SuperTrend Exit

If trend changes:

Exit quickly.

This prevents large losses.

---

# Example Trade (Bullish)

### Market Opens

Nifty = 23,450

R1 = 23,500

SuperTrend = Green

---

### At 11:15 AM

5-minute candle closes:

23,520

Now:

* Above R1 ✅
* Above SuperTrend ✅

Entry:

Sell 23,500 PE

---

### Market Continues Up

Option premium falls.

Profit increases.

---

### At 1:30 PM

SuperTrend flips Red.

Exit trade.

Take profit.

---

# Example Trade (Bearish)

### Market Opens

Nifty = 23,400

S1 = 23,300

SuperTrend = Red

---

### At 10:40 AM

Price closes at:

23,280

Conditions:

* Below S1 ✅
* Below SuperTrend ✅

Entry:

Sell 23,300 CE

---

### Market Falls Further

Call premium collapses.

Profit grows.

---

### Exit

Either:

* SuperTrend turns Green
* Or 3:20 PM arrives

---

# Complete Strategy Checklist

Every day:

### Before Market Opens

1. Open Nifty 5-minute chart.
2. Add Standard Pivot Points.
3. Keep only R1 and S1.
4. Add SuperTrend (7,3).

---

### Entry

#### Sell ATM Put

```
Price > R1
AND
Price > SuperTrend
```

#### Sell ATM Call

```
Price < S1
AND
Price < SuperTrend
```

---

### Exit

```
SuperTrend Flip
OR
3:20 PM
```

---

### Risk Rules

```
Max 3 trades/day
No entries after 3 PM
Current expiry only
ATM option only
No overnight holding
```

# Important Observation

Although the backtest shown in the video looks attractive, remember:

* Backtests are not guarantees.
* Slippage can increase losses.
* Fast reversals can hurt option sellers.
* Real execution may differ from historical results.
* Always forward-test with 1 lot before increasing size.

This strategy is essentially a **momentum-confirmed ATM option selling system** that combines:

**Pivot Breakout + SuperTrend Confirmation + Time-Based Exit + Strict Trade Limits.**
