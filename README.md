# Backtest-RRS
RSI Range Shift 


"""
RSI Range Shift Backtest Strategy
=================================
Youtube URL : https://youtu.be/v5hoPMN2RP0?si=txQh-GyB_bMNMUou
This backtest program implements an intraday options trading strategy based on RSI range shifts and candlestick breakouts/breakdowns on spot index data (e.g., NIFTY).

1. Core Concept
---------------
- The strategy identifies support and resistance levels on the RSI (Relative Strength Index, default length 14) of the consolidated spot price (5-minute interval).
- It checks for swing highs and swing lows on the RSI line using scipy's peak finding.
- A swing low near the Call Level (default 60 +/- 1.5 tolerance) indicates "CALL_SUPPORT".
- A swing high near the Call Level (60 +/- 1.5) indicates "CALL_RESISTANCE".
- A swing low near the Put Level (default 40 +/- 1.5) indicates "PUT_SUPPORT".
- A swing high near the Put Level (40 +/- 1.5) indicates "PUT_RESISTANCE".

2. Entry Conditions (Spot-driven Breakout/Breakdown)
-----------------------------------------------------
On every candle, the strategy looks at the signal from the previous candle (candle at index [-2]):
- SUPPORT Signal (CALL_SUPPORT or PUT_SUPPORT) at [-2]:
  - Enter trade if the current candle Close [-1] breaks out above the High of the support candle [-2] (i.e., Close[-1] > High[-2]).
  - Direction: BUY Call / SELL Put (determined by options_side_config).
  - Stoploss: Low of the support candle [-2].
- RESISTANCE Signal (CALL_RESISTANCE or PUT_RESISTANCE) at [-2]:
  - Enter trade if the current candle Close [-1] breaks down below the Low of the resistance candle [-2] (i.e., Close[-1] < Low[-2]).
  - Direction: SELL Call / BUY Put (determined by options_side_config).
  - Stoploss: High of the resistance candle [-2].

3. Option Selection
-------------------
- Once a breakout/breakdown triggers, the strategy selects the ATM (At-The-Money) options strike based on the spot Close price.
- It loads the corresponding 1-minute options data from the OPTIONS_PATH (e.g., NIFTYyymmdd[Strike][CE/PE].csv) for that day.
- Entry price in the option contract is recorded as the Close price at the end of the entry bar.

4. Exit Conditions
------------------
Positions are exited based on the underlying spot price movement:
- For Long Call / Short Put positions:
  - Stoploss: Spot Low[-1] falls below the entry candle's stoploss (Low[-2]).
  - Technical Exit: Spot Close[-1] closes below the previous candle's low (Low[-2]).
  - Intraday Exit: Time reaches 15:15 or later.
- For Short Call / Long Put positions:
  - Stoploss: Spot High[-1] rises above the entry candle's stoploss (High[-2]).
  - Technical Exit: Spot Close[-1] closes above the previous candle's high (High[-2]).
  - Intraday Exit: Time reaches 15:15 or later.
- The option exit price is filled from the option's 1-minute close price corresponding to the exit timestamp.

5. Performance Reporting & Metrics
----------------------------------
After the backtest run completes, it calculates:
- Monthly & Yearly PNL.
- Annualized Max Drawdown.
- ROI % based on an initial capital of 25,000 RS.
- Recovery Days from Max Drawdown.
- Highest single-trade profit and loss.
- Total trade count per month.
- Saves the trade-by-trade log and summary statistics to BACKTEST_RSI_RANGE_SHIFT.csv.
"""
