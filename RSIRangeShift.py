# from IPython.core import autocall
import pandas as pd
import numpy as np
import pandas_ta as pdt
from backtesting import Backtest, Strategy
from datetime import datetime, time
import os
from scipy.signal import find_peaks


# --- OHLC Consolidate for 5 Min Intraday Data ---
def ohlc_consolidate(df: pd.DataFrame, timevalue: str, Isvolume: bool = True) -> pd.DataFrame:
    df = df.copy()
    if 'timestamp' in df.columns:
        df.set_index('timestamp', inplace=True)
    df.index = pd.to_datetime(df.index)

    # Filter time range
    df = df[(df.index.time >= time(9, 15)) & (df.index.time < time(15, 30))]

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
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # Supertrend: Length = 20, Factor = 2 (as recommended)
    supertrend = pdt.supertrend(df['high'], df['low'], df['close'], length=20, multiplier=2.0)
    df = pd.concat([df, supertrend], axis=1)

    # MACD: Default (12, 26, 9)
    macd = pdt.macd(df['close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # Daily Intraday VWAP
    df['date'] = df.index.date
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_vol'] = df['typical_price'] * df['volume']
    
    # Calculate VWAP
    vwap = df.groupby('date').apply(lambda x: x['tp_vol'].cumsum() / x['volume'].cumsum())
    # Resetting the index from the groupby operation so it maps correctly back
    df['vwap'] = vwap.reset_index(level=0, drop=True)

    df.drop(columns=['date', 'typical_price', 'tp_vol'], inplace=True)
    
    # Rename columns to standardized names for strategy
    rename_map = {
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
        'SUPERT_20_2.0': 'SUPERT',
        'SUPERTd_20_2.0': 'SUPERTd', # 1 for Bullish, -1 for Bearish
        'MACD_12_26_9': 'MACD',
        'MACDs_12_26_9': 'MACD_Signal',
        'MACDh_12_26_9': 'MACD_Hist',
        'vwap': 'VWAP'
    }
    df.rename(columns=rename_map, inplace=True)
    return df


def identify_rsi_levels(df,options_levels, prominence=10, distance=5, tolerance=1.5):
    df = df.copy()

    rsi = df["rsi"]

    call_level = options_levels["CALL_level"]  # 60
    put_level = options_levels["PUT_level"]    # 40

    # Swing highs
    peaks, _ = find_peaks(
        rsi.values,
        prominence=prominence,
        distance=distance
    )

    # Swing lows
    troughs, _ = find_peaks(
        -rsi.values,
        prominence=prominence,
        distance=distance
    )

    df["swing_high"] = False
    df["swing_low"] = False

    df.loc[df.index[peaks], "swing_high"] = True
    df.loc[df.index[troughs], "swing_low"] = True

    call_zone = rsi.between(
        call_level - tolerance,
        call_level + tolerance
    )

    put_zone = rsi.between(
        put_level - tolerance,
        put_level + tolerance
    )

    conditions = [
        df["swing_low"] & call_zone,   # 60 support
        df["swing_high"] & call_zone,  # 60 resistance
        df["swing_low"] & put_zone,    # 40 support
        df["swing_high"] & put_zone,   # 40 resistance
    ]

    choices = [
        "CALL_SUPPORT",
        "CALL_RESISTANCE",
        "PUT_SUPPORT",
        "PUT_RESISTANCE",
    ]

    df["signal"] = np.select(
        conditions,
        choices,
        default=""
    )

    return df.drop(columns =["swing_high","swing_low"])

# --- Strategy Class ---
class RsiLevelsShift(Strategy):
    strike_config = "ATM"
    options_levels = {
            "CALL":{"support":60,"resistance":40},
            "PUT":{"support":40,"resistance":60}
            }
    options_side_config = {
                "CALL_SUPPORT":"BUY",
                "CALL_RESISTANCE":"SELL",
                "PUT_SUPPORT":"SELL",
                "PUT_RESISTANCE":"BUY",
                },

    def init(self):
        # State tracking
       self.data
        
    def next(self):
        if len(self.data) < 5:
            return

        current_time = self.data.index[-1].time()
        
        # 1. Intraday Exit (Square off before market close)
        if current_time >= time(15, 15):
            if self.position.size != 0:
                self.position.close()
            self.trade_active = False
            self.trade_dir = 0
            return

        # Current values
        st_dir = self.data.SUPERTd[-1]
        st_val = self.data.SUPERT[-1]
        
        mac_line = self.data.MACD[-1]
        mac_sig = self.data.MACD_Signal[-1]
        
        c = self.data.Close[-1]
        o = self.data.Open[-1]
        h = self.data.High[-1]
        l = self.data.Low[-1]
        v = self.data.VWAP[-1]

        # Check conditions
        macd_bullish = mac_line > mac_sig
        macd_bearish = mac_line < mac_sig
        
        # VWAP condition (Near or above/below)
        # Using 0.2% tolerance for "near" VWAP
        price_near_above_vwap = c >= (v * 0.998)
        price_near_below_vwap = c <= (v * 1.002)

        # Reversal signals
        st_bullish_flip = (self.data.SUPERTd[-2] == -1) and (self.data.SUPERTd[-1] == 1)
        st_bearish_flip = (self.data.SUPERTd[-2] == 1) and (self.data.SUPERTd[-1] == -1)

        macd_bullish_cross = (self.data.MACD[-2] <= self.data.MACD_Signal[-2]) and macd_bullish
        macd_bearish_cross = (self.data.MACD[-2] >= self.data.MACD_Signal[-2]) and macd_bearish

        # Lookback for MACD cross (last 4 candles)
        recent_macd_bull_cross = any(
            (self.data.MACD[-i] > self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] <= self.data.MACD_Signal[-i-1])
            for i in range(1, 5) if len(self.data.MACD) > i+1
        ) or macd_bullish_cross
        
        recent_macd_bear_cross = any(
            (self.data.MACD[-i] < self.data.MACD_Signal[-i]) and (self.data.MACD[-i-1] >= self.data.MACD_Signal[-i-1])
            for i in range(1, 5) if len(self.data.MACD) > i+1
        ) or macd_bearish_cross

        # --- Active Trade Management (Exits & Stop Loss) ---
        if self.position.size != 0:
            # Trailing Stop Loss
            if self.position.is_long:
                # Stop loss at Supertrend line
                if c < st_val:
                    self.position.close()
                    self.trade_active = False
                    self.trade_dir = 0
            elif self.position.is_short:
                if c > st_val:
                    self.position.close()
                    self.trade_active = False
                    self.trade_dir = 0

            # Profit Booking Rule 1: Opposite MACD Crossover -> Book 50%
            if not self.partial_exit_done:
                if self.position.is_long and macd_bearish_cross:
                    self.sell(size=abs(self.position.size) // 2)
                    self.partial_exit_done = True
                elif self.position.is_short and macd_bullish_cross:
                    self.buy(size=abs(self.position.size) // 2)
                    self.partial_exit_done = True

            # Rule 2: Supertrend Reverses -> Exit 100%
            if self.position.is_long and st_bearish_flip:
                self.position.close()
                self.trade_active = False
                self.trade_dir = 0
            elif self.position.is_short and st_bullish_flip:
                self.position.close()
                self.trade_active = False
                self.trade_dir = 0

            # --- Pyramiding / Re-entry Logic ---
            # Wait at least a few candles between re-entries to avoid spam
            if len(self.data) > self.last_reentry_index + 1:
                body = abs(c - o)
                tot = h - l
                # Avoid div by zero
                if tot == 0: tot = 0.01

                # Re-entry Long
                if self.position.is_long and abs(self.position.size) < self.max_qty:
                    if st_dir == 1 and macd_bullish:
                        # Check candlestick pattern
                        is_doji = body <= (tot * 0.1)
                        lower_wick = min(o, c) - l
                        upper_wick = h - max(o, c)
                        is_hammer = (lower_wick >= 2 * body) and (upper_wick <= body)

                        if is_doji or is_hammer:
                            self.buy(size=self.qty_per_entry)
                            self.last_reentry_index = len(self.data)

                # Re-entry Short
                elif self.position.is_short and abs(self.position.size) < self.max_qty:
                    if st_dir == -1 and macd_bearish:
                        # Check candlestick pattern
                        is_doji = body <= (tot * 0.1)
                        lower_wick = min(o, c) - l
                        upper_wick = h - max(o, c)
                        is_shooting_star = (upper_wick >= 2 * body) and (lower_wick <= body)

                        if is_doji or is_shooting_star:
                            self.sell(size=self.qty_per_entry)
                            self.last_reentry_index = len(self.data)

        # --- Entry Logic ---
        if self.position.size == 0:
            st_recent_flip = any(
                (self.data.SUPERTd[-i-1] == -1) and (self.data.SUPERTd[-i] == 1)
                for i in range(1, 5) if len(self.data.SUPERTd) > i
            ) or st_bullish_flip
            
            st_recent_bear_flip = any(
                (self.data.SUPERTd[-i-1] == 1) and (self.data.SUPERTd[-i] == -1)
                for i in range(1, 5) if len(self.data.SUPERTd) > i
            ) or st_bearish_flip

            cond_buy = st_dir == 1 and macd_bullish and price_near_above_vwap and ((st_bullish_flip and recent_macd_bull_cross) or (macd_bullish_cross and st_recent_flip))
            if cond_buy:
                self.buy(size=self.qty_per_entry)
                self.trade_active = True
                self.trade_dir = 1
                self.partial_exit_done = False
                self.last_reentry_index = len(self.data)

            # Sell Entry
            cond_sell = st_dir == -1 and macd_bearish and price_near_below_vwap and ((st_bearish_flip and recent_macd_bear_cross) or (macd_bearish_cross and st_recent_bear_flip))
            if cond_sell:
                self.sell(size=self.qty_per_entry)
                self.trade_active = True
                self.trade_dir = -1
                self.partial_exit_done = False
                self.last_reentry_index = len(self.data)




def main(backtest_from_to,symbol,formated_symbols,step_size,timeframe,RSI_lenght,RSI_Source,strike_config,options_levels,options_side_config):
    
    
    csv_file = "trading_data_nifty.csv"
    if not os.path.exists(csv_file):
        print(f"Data file not found: {csv_file}")
        return

    # Load 1-min data
    print("Loading data...")
    df = pd.read_csv(csv_file)
    
    # Consolidate to 5-min
    print("Consolidating to 5-min timeframe...")
    consolidated_df = ohlc_consolidate(df, timeframe, Isvolume=True)
    
    # Compute indicators
    print("Computing RSI indicators...")
    rsi_series = pdt.rsi(consolidated_df[RSI_Source.lower()], timeperiod=RSI_lenght).rename(f'rsi')
    consolidated_df = pd.concat([consolidated_df, rsi_series], axis=1)
    consolidated_df = identify_rsi_levels(consolidated_df,options_levels)
    # levels.to_csv("levels.csv",index=True)
    # print("levelsssss == ",levels)
    # exit(0)
    # Initializing Backtest
    print("Starting Backtest...")
    RsiLevelsShift.strike_config = strike_config
    RsiLevelsShift.options_levels = options_levels
    RsiLevelsShift.options_side_config = options_side_config
    
    
    bt = Backtest(
        consolidated_df,
        RsiLevelsShift,
        cash=100_000_000,     # Start with large cash to support multiple Nifty entries
        commission=0.0002, # Approx cost including slippage/brokerage
        trade_on_close=False
    )
    stats = bt.run()
    
    # Print basic stats
    print("\n--- Backtest Statistics ---")
    print(stats)
    
    # Save trades to CSV
    if hasattr(stats, '_trades') and not stats._trades.empty:
        stats._trades.to_csv("triple_conf_trades.csv", index=False)
        print("\nTrades saved to triple_conf_trades.csv")
    else:
        print("\nNo trades executed.")

if __name__ == "__main__":
    
    kwags = dict(
    backtest_from_to = {"start_date":datetime(2025,1,1),"end_date":datetime(2025,9,30)},
    symbol = "NIFTY",
    formated_symbols={"NIFTY":"NIFTY 50","SENSEX":"SENSEX","BANKNIFTY":"NIFTY BANK"},
    step_size = {"NIFTY":50,"SENSEX":100,"BANKNIFTY":100},
    timeframe = "15min", 
    RSI_lenght = 3,
    RSI_Source = "Close",
    strike_config = "ATM",
    options_levels = {
                "CALL_level":60,
                "PUT_level":40
                },
    options_side_config = {
                "CALL_SUPPORT":"BUY",
                "CALL_RESISTANCE":"SELL",
                "PUT_SUPPORT":"SELL",
                "PUT_RESISTANCE":"BUY"
                },
    
    )
    main(**kwags)
