"""
Triple Confirmation Intraday Options Trading Strategy
=====================================================
Youtube URL : https://www.youtube.com/watch?v=0EXVG4kPAm0
This backtest program implements an intraday options trading strategy based on a confluence of three indicators (Supertrend, MACD, and VWAP) calculated on spot index data (e.g., NIFTY 50).

1. Core Concept & Indicators
---------------------------
- The strategy resamples the 1-minute spot price data to 5-minute intervals (consolidated for the market hours 09:15 to 15:30).
- It computes three key technical indicators:
  - Supertrend (default: length = 20, multiplier = 2.0) to identify trend direction (bullish/bearish) and trailing stop loss levels.
  - MACD (default fast = 12, slow = 26, signal = 9) to detect crossovers and momentum shift.
  - Daily Intraday VWAP (Volume Weighted Average Price) to determine price location relative to the average. (If spot volume is zero/unavailable, a constant volume fallback is used to estimate a cumulative average price).

2. Confluence Entry Conditions
-----------------------------
A position is entered when the following indicators align simultaneously:
- Bullish / Call Entry (Buy CE or Sell PE, based on options_strategy_mode):
  - Supertrend is Bullish (direction == 1).
  - MACD line > MACD Signal line.
  - Spot Close >= VWAP * (1 - vwap_tolerance) (price is near or above VWAP).
  - Trigger: Either (Supertrend bullish flip on current candle AND recent MACD bullish crossover in last 4 candles) OR (MACD bullish crossover on current candle AND recent Supertrend bullish flip in last 4 candles).
- Bearish / Put Entry (Buy PE or Sell CE, based on options_strategy_mode):
  - Supertrend is Bearish (direction == -1).
  - MACD line < MACD Signal line.
  - Spot Close <= VWAP * (1 + vwap_tolerance) (price is near or below VWAP).
  - Trigger: Either (Supertrend bearish flip on current candle AND recent MACD bearish crossover in last 4 candles) OR (MACD bearish crossover on current candle AND recent Supertrend bearish flip in last 4 candles).

3. Option Selection & Execution
------------------------------
- On entry trigger, the ATM (At-The-Money) strike is determined by rounding the spot Close to the nearest strike step size (default 50 for NIFTY).
- The weekly/monthly options contract expiry is resolved.
- The corresponding 1-minute option contract data file is loaded from OPTIONS_PATH (e.g., NIFTYyymmdd[Strike][CE/PE].csv).
- The option entry price is filled from the 1-minute option Close price matching the 5-minute spot entry candle timestamp.
- To simulate the 50% partial exit, two sub-trades (Trade A - PARTIAL, and Trade B - FULL) are created for each entry.

4. Exit Conditions
------------------
Active positions are monitored bar-by-bar and exited based on the underlying spot price:
- Trailing Stop Loss:
  - For Bullish trades: Spot Close falls below the Supertrend value.
  - For Bearish trades: Spot Close rises above the Supertrend value.
- Technical Reverse:
  - For Bullish trades: Supertrend reverses to Bearish.
  - For Bearish trades: Supertrend reverses to Bullish.
- Profit Booking (MACD opposite crossover):
  - For Bullish trades: MACD bearish crossover occurs.
  - For Bearish trades: MACD bullish crossover occurs.
  - Action: The partial sub-trade (Trade A) is closed at the current option price, representing booking 50% of the position.
- Intraday Exit: Time reaches 15:15 or later. Remaining open sub-trades are squared off.
- Exit option prices are fetched from the corresponding 1-minute option Close price.

5. Performance Reporting & Metrics
----------------------------------
After the backtest completes, it calculates:
- Monthly & Yearly PNL.
- Annualized Max Drawdown.
- ROI % based on initial capital of 25,000 RS.
- Recovery Days from Max Drawdown.
- Highest single-trade profit and loss.
- Total trade count per month.
- Saves the trade-by-trade log and summary statistics to BACKTEST_TRIPLE_CONFIRMATION_OPTIONS.csv.
"""

import pandas as pd
import numpy as np
import pandas_ta as pdt
from backtesting import Backtest, Strategy
from datetime import datetime, time as dtime
import os

# --- OHLC Consolidate for 5 Min Intraday Data ---
def ohlc_consolidate(df: pd.DataFrame, timevalue: str, Isvolume: bool = True) -> pd.DataFrame:
    df = df.copy()
    if 'timestamp' in df.columns:
        df.set_index('timestamp', inplace=True)
    df.index = pd.to_datetime(df.index)

    # Filter time range
    df = df[(df.index.time >= dtime(9, 15)) & (df.index.time < dtime(15, 30))]

    # Resample
    ohlc_df = df.resample(
        timevalue, offset=(pd.Timestamp('09:15:00') - pd.Timestamp('00:00:00'))
    ).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })

    if Isvolume and 'volume' in df.columns:
        resampled_volume = df['volume'].resample(
            timevalue, offset=(pd.Timestamp('09:15:00') - pd.Timestamp('00:00:00'))
        ).sum()
        ohlc_df['volume'] = resampled_volume
    else:
        ohlc_df['volume'] = 0

    ohlc_df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
    return ohlc_df

# --- Compute Indicators ---
def compute_indicators(df: pd.DataFrame, supertrend_length=20, supertrend_multiplier=2.0, macd_fast=12, macd_slow=26, macd_signal=9) -> pd.DataFrame:
    # Supertrend
    supertrend = pdt.supertrend(df['high'], df['low'], df['close'], length=supertrend_length, multiplier=supertrend_multiplier)
    df = pd.concat([df, supertrend], axis=1)

    # MACD
    macd = pdt.macd(df['close'], fast=macd_fast, slow=macd_slow, signal=macd_signal)
    df = pd.concat([df, macd], axis=1)

    # Daily Intraday VWAP
    df['date'] = df.index.date
    
    # Check if volume is all 0 or empty
    if 'volume' not in df.columns or (df['volume'] == 0).all():
        vol_col = pd.Series(1, index=df.index)
    else:
        vol_col = df['volume'].replace(0, 1)

    typical_price = (df['high'] + df['low'] + df['close']) / 3
    tp_vol = typical_price * vol_col
    
    # Calculate VWAP
    df_temp = pd.DataFrame({'tp_vol': tp_vol, 'vol': vol_col, 'date': df['date']})
    vwap = df_temp.groupby('date', group_keys=False).apply(lambda x: x['tp_vol'].cumsum() / x['vol'].cumsum())
    df['vwap'] = vwap
    df.drop(columns=['date'], inplace=True)
    
    # Rename columns to standardized names for strategy
    st_val_col = f'SUPERT_{supertrend_length}_{supertrend_multiplier}'
    st_dir_col = f'SUPERTd_{supertrend_length}_{supertrend_multiplier}'
    macd_col = f'MACD_{macd_fast}_{macd_slow}_{macd_signal}'
    macd_sig_col = f'MACDs_{macd_fast}_{macd_slow}_{macd_signal}'
    macd_hist_col = f'MACDh_{macd_fast}_{macd_slow}_{macd_signal}'
    
    rename_map = {
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
        st_val_col: 'SUPERT',
        st_dir_col: 'SUPERTd', # 1 for Bullish, -1 for Bearish
        macd_col: 'MACD',
        macd_sig_col: 'MACD_Signal',
        macd_hist_col: 'MACD_Hist',
        'vwap': 'VWAP'
    }
    df.rename(columns=rename_map, inplace=True)
    return df

def parse_strike(rule, ltp, step=50):
    """Parse strike rule like 'ATM', 'ATM+100', 'ATM-100'. Returns strike price (int)."""
    if isinstance(rule, str) and "ATM" in rule:
        atm = get_strike(ltp, step)
        expression = rule.replace("ATM", str(atm))
        try:
            return int(eval(expression))
        except Exception as e:
            print(f"Error parsing strike rule '{rule}': {e}")
            return atm
    return int(rule)

def get_strike(ltp, step_size):
    """Round LTP to nearest strike price"""
    remainder = ltp % step_size
    if remainder >= step_size / 2:
        return int(ltp + (step_size - remainder))
    else:
        return int(ltp - remainder)

# --- Positions records ---
def default_records():
    return {
        "criteria_timestamp": None,
        "supertrend_signal_time": None,
        "macd_signal_time": None,
        "pattern_vwap_signal_time": None,
        "criteria_type": None,
        "criteria_breakout_price": None, # Spot entry close price
        "symbol": None,
        "expiry_date": None,
        "strike_price": None,
        "option_type": None, # "CALL" or "PUT"
        "entry_signal": None, # "BUY" or "SELL"
        "entry_time": None,
        "entry_price": None, # Option entry close price
        "stoploss": None, # Spot stoploss value (ST level)
        "exit_timestamp": None,
        "exit_price": None, # Option exit close price
        "profit_points": None, # Option points gain/loss
        "reason_for_exit": None,
        "options_data": None,
        "trade_part": None, # "PARTIAL" or "FULL"
    }

def merge_expires(data, symbol):
    exp_collection = {
        "NIFTY_EXPIRES": [
            "2020-01-02","2020-01-09","2020-01-16","2020-01-23","2020-01-30","2020-02-06","2020-02-13","2020-02-20",
            "2020-02-27","2020-03-05","2020-03-12","2020-03-19","2020-03-26","2020-04-01","2020-04-09","2020-04-16",
            "2020-04-23","2020-04-30","2020-05-07","2020-05-14","2020-05-21","2020-05-28","2020-06-04","2020-06-11",
            "2020-06-18","2020-06-25","2020-07-02","2020-07-09","2020-07-16","2020-07-23","2020-07-30","2020-08-06",
            "2020-08-13","2020-08-20","2020-08-27","2020-09-03","2020-09-10","2020-09-17","2020-09-24","2020-10-01",
            "2020-10-08","2020-10-15","2020-10-22","2020-10-29","2020-11-05","2020-11-12","2020-11-19","2020-11-26",
            "2020-12-03","2020-12-10","2020-12-17","2020-12-24","2020-12-31","2021-01-07","2021-01-14","2021-01-21",
            "2021-01-28","2021-02-04","2021-02-11","2021-02-18","2021-02-25","2021-03-04","2021-03-10","2021-03-18",
            "2021-03-25","2021-04-01","2021-04-08","2021-04-15","2021-04-22","2021-04-29","2021-05-06","2021-05-12",
            "2021-05-20","2021-05-27","2021-06-03","2021-06-10","2021-06-17","2021-06-24","2021-07-01","2021-07-08",
            "2021-07-15","2021-07-22","2021-07-29","2021-08-05","2021-08-12","2021-08-18","2021-08-26","2021-09-02",
            "2021-09-09","2021-09-16","2021-09-23","2021-09-30","2021-10-07","2021-10-14","2021-10-21","2021-10-28",
            "2021-11-03","2021-11-11","2021-11-18","2021-11-25","2021-12-02","2021-12-09","2021-12-16","2021-12-23",
            "2021-12-30","2022-01-06","2022-01-13","2022-01-20","2022-01-27","2022-02-03","2022-02-10","2022-02-17",
            "2022-02-24","2022-03-03","2022-03-10","2022-03-17","2022-03-24","2022-03-31","2022-04-07","2022-04-13",
            "2022-04-21","2022-04-28","2022-05-05","2022-05-12","2022-05-19","2022-05-26","2022-06-02","2022-06-09",
            "2022-06-16","2022-06-23","2022-06-30","2022-07-07","2022-07-14","2022-07-21","2022-07-28","2022-08-04",
            "2022-08-11","2022-08-18","2022-08-25","2022-09-01","2022-09-08","2022-09-15","2022-09-22","2022-09-29",
            "2022-10-06","2022-10-13","2022-10-20","2022-10-27","2022-11-03","2022-11-10","2022-11-17","2022-11-24",
            "2022-12-01","2022-12-08","2022-12-15","2022-12-22","2022-12-29","2023-01-05","2023-01-12","2023-01-19",
            "2023-01-25","2023-02-02","2023-02-09","2023-02-16","2023-02-23","2023-03-02","2023-03-09","2023-03-16",
            "2023-03-23","2023-03-29","2023-03-30","2023-04-06","2023-04-13","2023-04-20","2023-04-27","2023-05-04",
            "2023-05-11","2023-05-18","2023-05-25","2023-06-01","2023-06-08","2023-06-15","2023-06-22","2023-06-28",
            "2023-06-29","2023-07-06","2023-07-13","2023-07-20","2023-07-27","2023-08-03","2023-08-10","2023-08-17",
            "2023-08-24","2023-08-31","2023-09-07","2023-09-14","2023-09-21","2023-09-28","2023-10-05","2023-10-12",
            "2023-10-19","2023-10-26","2023-11-02","2023-11-09","2023-11-16","2023-11-23","2023-11-30","2023-12-07",
            "2023-12-14","2023-12-21","2023-12-28","2024-01-04","2024-01-11","2024-01-18","2024-01-25","2024-02-01",
            "2024-02-08","2024-02-15","2024-02-22","2024-02-29","2024-03-07","2024-03-14","2024-03-21","2024-03-28",
            "2024-04-04","2024-04-10","2024-04-18","2024-04-25","2024-05-02","2024-05-09","2024-05-16","2024-05-23",
            "2024-05-30","2024-06-06","2024-06-13","2024-06-20","2024-06-27","2024-07-04","2024-07-11","2024-07-18",
            "2024-07-25","2024-08-01","2024-08-08","2024-08-14","2024-08-22","2024-08-29","2024-09-05","2024-09-12",
            "2024-09-19","2024-09-26","2024-10-03","2024-10-10","2024-10-17","2024-10-24","2024-10-31","2024-11-07",
            "2024-11-14","2024-11-21","2024-11-28","2024-12-05","2024-12-12","2024-12-19","2024-12-26","2025-01-02",
            "2025-01-09","2025-01-16","2025-01-23","2025-01-30","2025-02-06","2025-02-13","2025-02-20","2025-02-27",
            "2025-03-06","2025-03-13","2025-03-20","2025-03-27","2025-04-03","2025-04-09","2025-04-17","2025-04-24",
            "2025-04-30","2025-05-08","2025-05-15","2025-05-22","2025-05-29","2025-06-05","2025-06-12","2025-06-19",
            "2025-06-26","2025-07-03","2025-07-10","2025-07-17","2025-07-24","2025-07-31","2025-08-07","2025-08-14",
            "2025-08-21","2025-08-28","2025-09-02","2025-09-09","2025-09-16","2025-09-23","2025-09-25","2025-09-30",
            "2025-10-07","2025-10-14","2025-10-20","2025-10-28","2025-11-04","2025-11-11","2026-01-06","2026-01-13",
            "2026-01-20","2026-01-27","2026-02-03","2026-02-10","2026-02-17","2026-02-24","2026-03-02","2026-03-10",
            "2026-03-17","2026-03-24","2026-03-26","2026-03-30","2026-03-31","2026-04-07","2026-04-13","2026-04-21",
            "2026-04-28","2026-05-05","2026-05-12","2026-05-19","2026-05-26","2026-06-02","2026-06-09","2026-06-16",
            "2026-06-23","2026-06-25","2026-06-30","2026-07-07","2026-07-28","2026-08-25","2026-09-29","2026-12-29",
            "2026-12-31"
        ]
    }

    data = data.copy()
    data.index = pd.to_datetime(data.index)
    data['datetime'] = pd.to_datetime(data.index)

    # 1) Add a pure date column to data
    data["trade_date"] = data.index.normalize()
    # 2) Prepare expiry df with a date column
    exp_df = pd.DataFrame({
        "expiry": pd.to_datetime(exp_collection[f"{symbol}_EXPIRES"])
    }).sort_values("expiry")

    exp_df["expiry_date"] = exp_df["expiry"].dt.normalize()

    # 3) merge_asof on date
    final_df = pd.merge_asof(
        data.sort_values("trade_date"),
        exp_df[["expiry_date", "expiry"]].sort_values("expiry_date"),
        left_on="trade_date",
        right_on="expiry_date",
        direction="forward"
    )

    # 4) Clean up
    final_df = final_df.drop(columns=["trade_date", "expiry_date"])
    final_df.set_index(keys="datetime", inplace=True)
    final_df["expiry"] = pd.to_datetime(final_df["expiry"]).dt.date
    final_df.dropna(subset=["expiry"], inplace=True)
    final_df.sort_values(by="datetime", inplace=True)
    return final_df

# --- Strategy Class ---
class TripleConfirmationOptionsStrategy(Strategy):
    # Switches/Parameters (filled from main kwargs)
    strike_config = "ATM"
    step_size = {"NIFTY": 50, "SENSEX": 100, "BANKNIFTY": 100}
    OPTIONS_PATH = "options_dir"
    symbol = "NIFTY"
    vwap_tolerance = 0.002
    options_strategy_mode = "BUY"  # "BUY" or "SELL"

    signals = []

    def generate_symbol(self, option_type, strike_price):
        expiry_val = self.data.expiry[-1]
        if isinstance(expiry_val, str):
            expiry_dt = datetime.strptime(expiry_val, "%Y-%m-%d")
        elif hasattr(expiry_val, "strftime"):
            expiry_dt = expiry_val
        else:
            expiry_dt = pd.to_datetime(expiry_val)
            
        expiry_str = expiry_dt.strftime("%y%m%d")

        ATM_KEY = (
            f"{self.symbol.upper()}"
            f"{expiry_str}"
            f"{int(float(strike_price))}"
            f"{option_type.upper()}"
        )
        return ATM_KEY

    def record_finished_trade(self, trade):
        if trade["entry_signal"] == "BUY":
            trade["profit_points"] = trade["exit_price"] - trade["entry_price"]
        elif trade["entry_signal"] == "SELL":
            trade["profit_points"] = trade["entry_price"] - trade["exit_price"]

        # Save to global signals
        self.signals.append([
            trade["criteria_timestamp"],
            trade.get("supertrend_signal_time", None),
            trade.get("macd_signal_time", None),
            trade.get("pattern_vwap_signal_time", None),
            trade["criteria_type"],
            trade["criteria_breakout_price"],
            trade["symbol"],
            trade["expiry_date"],
            trade["strike_price"],
            trade["option_type"],
            trade["entry_signal"],
            trade["entry_time"],
            trade["entry_price"],
            trade["stoploss"],
            trade["exit_timestamp"],
            trade["exit_price"],
            trade["profit_points"],
            trade["reason_for_exit"],
        ])

    def init(self):
        # We track multiple sub-trades to simulate partial exit (Trade A and Trade B)
        # active_trades: list of dictionaries
        self.active_trades = []
        self.spot_dir = 0  # 1 for Long, -1 for Short
        self.last_reentry_index = 0

    def next(self):
        # Need at least 5 candles for indicator references
        if len(self.data) < 5:
            return

        current_time = self.data.index[-1].time()

        # Standard indicators
        st_dir = self.data.SUPERTd[-1]
        st_val = self.data.SUPERT[-1]
        
        mac_line = self.data.MACD[-1]
        mac_sig = self.data.MACD_Signal[-1]
        
        c = self.data.Close[-1]
        v = self.data.VWAP[-1]

        # Crossover & conditions
        macd_bullish = mac_line > mac_sig
        macd_bearish = mac_line < mac_sig
        
        price_near_above_vwap = c >= (v * (1 - self.vwap_tolerance))
        price_near_below_vwap = c <= (v * (1 + self.vwap_tolerance))

        # Flips & crossovers
        st_bullish_flip = (self.data.SUPERTd[-2] == -1) and (self.data.SUPERTd[-1] == 1)
        st_bearish_flip = (self.data.SUPERTd[-2] == 1) and (self.data.SUPERTd[-1] == -1)

        macd_bullish_cross = (self.data.MACD[-2] <= self.data.MACD_Signal[-2]) and macd_bullish
        macd_bearish_cross = (self.data.MACD[-2] >= self.data.MACD_Signal[-2]) and macd_bearish

        # Lookback (last 4 candles)
        recent_macd_bull_cross = any(
            (self.data.MACD[-i] > self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] <= self.data.MACD_Signal[-i-1])
            for i in range(1, 5) if len(self.data.MACD) > i+1
        ) or macd_bullish_cross
        
        recent_macd_bear_cross = any(
            (self.data.MACD[-i] < self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] >= self.data.MACD_Signal[-i-1])
            for i in range(1, 5) if len(self.data.MACD) > i+1
        ) or macd_bearish_cross

        st_recent_flip = any(
            (self.data.SUPERTd[-i-1] == -1) and (self.data.SUPERTd[-i] == 1)
            for i in range(1, 5) if len(self.data.SUPERTd) > i
        ) or st_bullish_flip
        
        st_recent_bear_flip = any(
            (self.data.SUPERTd[-i-1] == 1) and (self.data.SUPERTd[-i] == -1)
            for i in range(1, 5) if len(self.data.SUPERTd) > i
        ) or st_bearish_flip

        # Confluence Signals
        cond_buy = st_dir == 1 and macd_bullish and price_near_above_vwap and ((st_bullish_flip and recent_macd_bull_cross) or (macd_bullish_cross and st_recent_flip))
        cond_sell = st_dir == -1 and macd_bearish and price_near_below_vwap and ((st_bearish_flip and recent_macd_bear_cross) or (macd_bearish_cross and st_recent_bear_flip))

        # --- Compute Timestamp for Each Criteria ---
        st_signal_time = self.data.index[-1]
        for i in range(1, min(len(self.data), 10)):
            if self.data.SUPERTd[-i] != self.data.SUPERTd[-i-1]:
                st_signal_time = self.data.index[-i]
                break

        macd_signal_time = self.data.index[-1]
        for i in range(1, min(len(self.data), 10)):
            up_cross = (self.data.MACD[-i] > self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] <= self.data.MACD_Signal[-i-1])
            dn_cross = (self.data.MACD[-i] < self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] >= self.data.MACD_Signal[-i-1])
            if up_cross or dn_cross:
                macd_signal_time = self.data.index[-i]
                break

        # --- Exit Management ---
        if len(self.active_trades) > 0:
            # Check for exits on spot data
            # Determine if we hit trailing Stop Loss or Technical Reverse or square-off
            is_call = self.active_trades[0]["option_type"] == "CALL"
            is_put = self.active_trades[0]["option_type"] == "PUT"
            is_buy = self.active_trades[0]["entry_signal"] == "BUY"

            hit_sl = False
            hit_technical_reverse = False
            hit_partial_exit = False
            exit_reason = ""

            # Standard exit criteria based on spot index
            if (is_call and is_buy) or (is_put and not is_buy): # Long-style exits (CE BUY / PE SELL)
                if c < st_val:
                    hit_sl = True
                    exit_reason = "Stoploss"
                elif st_bearish_flip:
                    hit_technical_reverse = True
                    exit_reason = "Supertrend Reverse"
                elif macd_bearish_cross:
                    hit_partial_exit = True
            else: # Short-style exits (PE BUY / CE SELL)
                if c > st_val:
                    hit_sl = True
                    exit_reason = "Stoploss"
                elif st_bullish_flip:
                    hit_technical_reverse = True
                    exit_reason = "Supertrend Reverse"
                elif macd_bullish_cross:
                    hit_partial_exit = True

            # Check intraday square off time (15:15)
            hit_intraday = current_time >= dtime(15, 15)
            if hit_intraday:
                exit_reason = "Exittime"

            # Execute partial exit
            if hit_partial_exit and not hit_sl and not hit_technical_reverse and not hit_intraday:
                # Close ALL Trade A (representing PARTIAL lot) if still open
                open_partials = [t for t in self.active_trades if t["trade_part"] == "PARTIAL"]
                for trade_to_close in open_partials:
                    # Fetch option exit price
                    ATM_DF = trade_to_close["options_data"].sort_values(by="timestamp")
                    option_exit_candle = ATM_DF[ATM_DF["timestamp"] >= self.data.index[-1]]
                    exit_price = option_exit_candle.iloc[0]["Close"] if not option_exit_candle.empty else ATM_DF.iloc[-1]["Close"]
                    
                    trade_to_close["exit_timestamp"] = self.data.index[-1]
                    trade_to_close["exit_price"] = exit_price
                    trade_to_close["reason_for_exit"] = "MACD Crossover"
                    self.record_finished_trade(trade_to_close)
                    self.active_trades.remove(trade_to_close)

            # Execute full exit (SL, Technical Reverse, or Intraday)
            if hit_sl or hit_technical_reverse or hit_intraday:
                # Close ALL remaining active trades
                for trade_to_close in list(self.active_trades):
                    ATM_DF = trade_to_close["options_data"].sort_values(by="timestamp")
                    option_exit_candle = ATM_DF[ATM_DF["timestamp"] >= self.data.index[-1]]
                    exit_price = option_exit_candle.iloc[0]["Close"] if not option_exit_candle.empty else ATM_DF.iloc[-1]["Close"]
                    
                    trade_to_close["exit_timestamp"] = self.data.index[-1]
                    trade_to_close["exit_price"] = exit_price
                    trade_to_close["reason_for_exit"] = exit_reason
                    self.record_finished_trade(trade_to_close)
                    self.active_trades.remove(trade_to_close)
                self.spot_dir = 0
                return

        # --- Pyramiding / Re-entry Logic ---
        if len(self.active_trades) > 0 and len(self.active_trades) < 6:
            # Check gap between entries
            if len(self.data) > self.last_reentry_index + 1:
                o = self.data.Open[-1]
                h = self.data.High[-1]
                l = self.data.Low[-1]
                body = abs(c - o)
                tot = h - l
                if tot == 0:
                    tot = 0.01

                is_doji = body <= (tot * 0.1)
                lower_wick = min(o, c) - l
                upper_wick = h - max(o, c)

                reentry_triggered = False

                if self.spot_dir == 1:
                    if st_dir == 1 and macd_bullish:
                        is_hammer = (lower_wick >= 2 * body) and (upper_wick <= body)
                        if is_doji or is_hammer:
                            reentry_triggered = True
                elif self.spot_dir == -1:
                    if st_dir == -1 and macd_bearish:
                        is_shooting_star = (upper_wick >= 2 * body) and (lower_wick <= body)
                        if is_doji or is_shooting_star:
                            reentry_triggered = True

                if reentry_triggered:
                    option_type = self.active_trades[0]["option_type"]
                    entry_action = self.active_trades[0]["entry_signal"]
                    criteria_type = self.active_trades[0]["criteria_type"]

                    strike = parse_strike(self.strike_config, c, self.step_size.get(self.symbol, 50))
                    opt_symbol = self.generate_symbol("CE" if option_type == "CALL" else "PE", strike)
                    
                    csv_filename = os.path.join(self.OPTIONS_PATH, opt_symbol + ".csv")
                    if os.path.exists(csv_filename):
                        try:
                            ATM_DF = pd.read_csv(
                                csv_filename,
                                header=None,
                                names=["Date", "Time", "Open", "High", "Low", "Close", "Volume", "IO"]
                            )
                            ATM_DF["Datetime"] = pd.to_datetime(
                                ATM_DF["Date"].astype(str) + " " + ATM_DF["Time"].astype(str),
                                format="%Y%m%d %H:%M"
                            )
                            ATM_DF.rename(columns={"Datetime": "timestamp"}, inplace=True)
                            ATM_DF = ATM_DF[ATM_DF["timestamp"].dt.date == self.data.index[-1].date()].sort_values(by="timestamp")
                            
                            if not ATM_DF.empty:
                                entry_candles = ATM_DF[ATM_DF["timestamp"] <= self.data.index[-1]]
                                opt_entry_price = entry_candles.iloc[-1]["Close"] if not entry_candles.empty else ATM_DF.iloc[0]["Close"]
                                
                                trade_A = default_records()
                                trade_A.update({
                                    "criteria_timestamp": self.data.index[-1],
                                    "supertrend_signal_time": st_signal_time,
                                    "macd_signal_time": macd_signal_time,
                                    "pattern_vwap_signal_time": self.data.index[-1],
                                    "criteria_type": criteria_type,
                                    "criteria_breakout_price": c,
                                    "symbol": self.symbol,
                                    "expiry_date": self.data.expiry[-1],
                                    "strike_price": strike,
                                    "option_type": option_type,
                                    "entry_signal": entry_action,
                                    "entry_time": self.data.index[-1],
                                    "entry_price": opt_entry_price,
                                    "stoploss": st_val,
                                    "options_data": ATM_DF,
                                    "trade_part": "PARTIAL"
                                })
                                
                                trade_B = trade_A.copy()
                                trade_B["trade_part"] = "FULL"
                                
                                self.active_trades.append(trade_A)
                                self.active_trades.append(trade_B)
                                self.last_reentry_index = len(self.data)
                                print(f"Executed Option Re-entry: {opt_symbol} at {self.data.index[-1]}")
                        except Exception as e:
                            print(f"Error executing re-entry: {e}")

        # --- Entry Logic ---
        if len(self.active_trades) == 0:
            # Do not enter after 15:15
            if current_time >= dtime(15, 15):
                return

            triggered = False
            option_type = ""
            entry_action = ""
            criteria_type = ""
            criteria_breakout_price = c

            if cond_buy:
                triggered = True
                criteria_type = "LONG"
                if self.options_strategy_mode == "BUY":
                    option_type = "CALL"  # CE BUY
                    entry_action = "BUY"
                else:
                    option_type = "PUT"   # PE SELL
                    entry_action = "SELL"
            elif cond_sell:
                triggered = True
                criteria_type = "SHORT"
                if self.options_strategy_mode == "BUY":
                    option_type = "PUT"   # PE BUY
                    entry_action = "BUY"
                else:
                    option_type = "CALL"  # CE SELL
                    entry_action = "SELL"

            if triggered:
                strike = parse_strike(self.strike_config, c, self.step_size.get(self.symbol, 50))
                opt_symbol = self.generate_symbol("CE" if option_type == "CALL" else "PE", strike)
                
                # Check option CSV exists
                csv_filename = os.path.join(self.OPTIONS_PATH, opt_symbol + ".csv")
                if not os.path.exists(csv_filename):
                    print(f"Option data file not found: {csv_filename} - skipping entry.")
                    return

                # Load option 1-minute data
                try:
                    ATM_DF = pd.read_csv(
                        csv_filename,
                        header=None,
                        names=["Date", "Time", "Open", "High", "Low", "Close", "Volume", "IO"]
                    )
                    ATM_DF["Datetime"] = pd.to_datetime(
                        ATM_DF["Date"].astype(str) + " " + ATM_DF["Time"].astype(str),
                        format="%Y%m%d %H:%M"
                    )
                    ATM_DF.rename(columns={"Datetime": "timestamp"}, inplace=True)
                    # Filter for trade day
                    ATM_DF = ATM_DF[ATM_DF["timestamp"].dt.date == self.data.index[-1].date()].sort_values(by="timestamp")
                    
                    if ATM_DF.empty:
                        print(f"No options data rows found for date {self.data.index[-1].date()} in {csv_filename} - skipping entry.")
                        return

                    # Entry price is the close of the 5-min entry candle (i.e. <= timestamp)
                    entry_candles = ATM_DF[ATM_DF["timestamp"] <= self.data.index[-1]]
                    opt_entry_price = entry_candles.iloc[-1]["Close"] if not entry_candles.empty else ATM_DF.iloc[0]["Close"]

                except Exception as e:
                    print(f"Error parsing option file {csv_filename}: {e} - skipping entry.")
                    return

                # Create Trade A (PARTIAL lot) and Trade B (FULL lot)
                trade_A = default_records()
                trade_A.update({
                    "criteria_timestamp": self.data.index[-1],
                    "supertrend_signal_time": st_signal_time,
                    "macd_signal_time": macd_signal_time,
                    "pattern_vwap_signal_time": self.data.index[-1],
                    "criteria_type": criteria_type,
                    "criteria_breakout_price": criteria_breakout_price,
                    "symbol": self.symbol,
                    "expiry_date": self.data.expiry[-1],
                    "strike_price": strike,
                    "option_type": option_type,
                    "entry_signal": entry_action,
                    "entry_time": self.data.index[-1],
                    "entry_price": opt_entry_price,
                    "stoploss": st_val,
                    "options_data": ATM_DF,
                    "trade_part": "PARTIAL"
                })

                trade_B = trade_A.copy()
                trade_B["trade_part"] = "FULL"

                self.active_trades.append(trade_A)
                self.active_trades.append(trade_B)
                self.spot_dir = 1 if cond_buy else -1
                self.last_reentry_index = len(self.data)


# ------------------------------------------------------------------------------------------------
def recovery_days(cum_pnl):
    peak = cum_pnl.cummax()
    drawdown = cum_pnl - peak

    if drawdown.min() >= 0:
        return 0

    max_dd_idx = drawdown.idxmin()
    peak_before_dd = peak[:max_dd_idx].iloc[-1]
    
    dd_start_idx = peak[:max_dd_idx][peak[:max_dd_idx] == peak_before_dd].index[-1]

    recovery_point = cum_pnl[max_dd_idx:]
    recovered = recovery_point[recovery_point >= peak_before_dd]

    if recovered.empty:
        return (cum_pnl.index[-1] - dd_start_idx).days

    recovery_idx = recovered.index[0]
    recovery_duration = (recovery_idx - dd_start_idx).days

    return recovery_duration


def main(backtest_from_to, csv_file, only_expiry, symbol, OPTIONS_PATH, formated_symbols, step_size, timeframe, strike_config, options_strategy_mode, supertrend_length, supertrend_multiplier, macd_fast, macd_slow, macd_signal, vwap_tolerance):
    cash_rs = 25000
    
    if not os.path.exists(csv_file):
        print(f"Data file not found: {csv_file}")
        return

    # Load 1-min spot data
    print("Loading spot data...")
    df = pd.read_csv(
        csv_file,
        header=None,
        names=["Date", "Time", "open", "high", "low", "close", "volume", "io"]
    )

    df["Datetime"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        format="%Y%m%d %H:%M"
    )
    df.rename(columns={"Datetime": "timestamp"}, inplace=True)
    df = df[(df["timestamp"] >= backtest_from_to["start_date"]) & (df["timestamp"] <= backtest_from_to["end_date"])]

    # Consolidate to 5-min
    print("Consolidating to 5-min timeframe...")
    consolidated_df = ohlc_consolidate(df, timeframe, Isvolume=True)
    
    # Compute indicators
    print("Computing indicators...")
    consolidated_df = compute_indicators(
        consolidated_df, 
        supertrend_length=supertrend_length, 
        supertrend_multiplier=supertrend_multiplier,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal
    )
    
    # Merge expires
    consolidated_df = merge_expires(consolidated_df, symbol)
    if only_expiry:
        consolidated_df = consolidated_df[
            consolidated_df.index.date == pd.to_datetime(consolidated_df["expiry"]).dt.date
        ]

    # Save indicators for levels verification if needed
    consolidated_df.to_csv("levels.csv", index=True)

    # Initializing Backtest Strategy settings
    print("Starting Backtest...")
    TripleConfirmationOptionsStrategy.strike_config = strike_config
    TripleConfirmationOptionsStrategy.symbol = symbol
    TripleConfirmationOptionsStrategy.OPTIONS_PATH = OPTIONS_PATH
    TripleConfirmationOptionsStrategy.step_size = step_size
    TripleConfirmationOptionsStrategy.vwap_tolerance = vwap_tolerance
    TripleConfirmationOptionsStrategy.options_strategy_mode = options_strategy_mode
    TripleConfirmationOptionsStrategy.signals = [] # Reset static variable

    bt = Backtest(
        consolidated_df,
        TripleConfirmationOptionsStrategy,
        cash=100_000_000,     # Large cash to avoid framework limitations
        commission=0.0002, 
        trade_on_close=False
    )
    
    stats = bt.run()
    
    print("\n--- Spot Backtest Statistics ---")
    print(stats)
    
    # Process options trade log
    signals_list = TripleConfirmationOptionsStrategy.signals
    if len(signals_list) == 0:
        print("\nNo trades executed during this period.")
        return

    trades_df = pd.DataFrame(
        signals_list,
        columns=[
            "criteria_timestamp",
            "supertrend_signal_time",
            "macd_signal_time",
            "pattern_vwap_signal_time",
            "criteria_type",
            "criteria_breakout_price",
            "symbol",
            "expiry_date",
            "strike_price",
            "option_type",
            "entry_signal",
            "ENTRY_TIME",
            "entry_price",
            "stoploss",
            "EXIT_TIME",
            "exit_price",
            "PNL",
            "reason_for_exit",
        ]
    )

    trades_df['ENTRY_TIME'] = pd.to_datetime(trades_df['ENTRY_TIME'])
    trades_df['EXIT_TIME'] = pd.to_datetime(trades_df['EXIT_TIME'])
    trades_df['month'] = trades_df['EXIT_TIME'].dt.to_period('M')
    trades_df['year'] = trades_df['EXIT_TIME'].dt.year
    
    monthly_pnl = trades_df.groupby('month')['PNL'].sum()
    yearly_pnl = trades_df.groupby('year')['PNL'].sum()
    
    drawdown_data = []
    for year, group in trades_df.groupby('year'):
        cum_pnl = group['PNL'].cumsum()
        peak = cum_pnl.cummax()
        drawdown = cum_pnl - peak
        max_dd = drawdown.min()
        drawdown_data.append((year, max_dd))
    
    monthly_trades = trades_df.groupby('month').size()
    cum_pnl = trades_df['PNL'].cumsum()
    cum_pnl.index = trades_df['EXIT_TIME']

    recovery_days_from_dd = recovery_days(cum_pnl)
    highest_profit = trades_df['PNL'].max()
    highest_loss = trades_df['PNL'].min()
    
    roi_data = (yearly_pnl / cash_rs) * 100
    summary_rows = []
    
    for period, pnl in monthly_pnl.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': pnl, 'option_type': f'Monthly PnL ({period})'})

    for year, pnl in yearly_pnl.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': pnl, 'option_type': f'Total Year PnL ({year})'})

    for year, dd in drawdown_data:
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': dd, 'option_type': f'Max Drawdown ({year})'})

    for year, roi in roi_data.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': roi, 'option_type': f'ROI % ({year})'})

    for period, count in monthly_trades.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': count, 'option_type': f'Trades in ({period})'})
    
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': recovery_days_from_dd, 'option_type': 'Recovery Days from MaxDD'})
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': highest_profit, 'option_type': 'Highest Single Trade Profit'})
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': highest_loss, 'option_type': 'Highest Single Trade Loss'})

    summary_df = pd.DataFrame(summary_rows)
    final_df = pd.concat([trades_df, summary_df], ignore_index=True)
    final_df.drop(columns=["year", "month"], inplace=True)
    
    output_filename = "BACKTEST_TRIPLE_CONFIRMATION_OPTIONS.csv"
    final_df.to_csv(output_filename, index=False)
    print(f"\nOptions trades and summaries saved to {output_filename}")


if __name__ == "__main__":
    kwags = dict(
        # --- Data & Backtest Paths ---
        backtest_from_to = {"start_date": datetime(2024, 6, 1), "end_date": datetime(2024, 12, 31)},
        symbol = "NIFTY",
        formated_symbols = {"NIFTY": "NIFTY 50", "SENSEX": "SENSEX", "BANKNIFTY": "NIFTY BANK"},
        timeframe = "5min", 
        only_expiry = False,
        OPTIONS_PATH = r"C:\Users\Saikr\Downloads\rohith_02\Rohith Set (1 min)\Jan 2020 to Dec 2024 - NIFTY Spot & Options\NIFTY Options",
        csv_file = r"C:\Users\Saikr\Downloads\rohith_02\Rohith Set (1 min)\Jan 2020 to Dec 2024 - NIFTY Spot & Options\NIFTY Spot\NIFTY.csv",
        
        # --- Options Trading Settings ---
        strike_config = "ATM",  # "ATM", "ATM+100", "ATM-100" etc.
        step_size = {"NIFTY": 50, "SENSEX": 100, "BANKNIFTY": 100},
        options_strategy_mode = "BUY",  # "BUY" to BUY Call/Put, "SELL" to SELL/Write Call/Put
        
        # --- Indicator Settings ---
        supertrend_length = 20,
        supertrend_multiplier = 2.0,
        macd_fast = 12,
        macd_slow = 26,
        macd_signal = 9,
        vwap_tolerance = 0.002,  # 0.2% tolerance for price being "near" VWAP
    )
    
    main(**kwags)
