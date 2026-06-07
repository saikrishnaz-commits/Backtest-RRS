# from IPython.core import autocall
import pandas as pd
import numpy as np
import pandas_ta as pdt
from backtesting import Backtest, Strategy
from datetime import datetime, time as dtime
import os
from scipy.signal import find_peaks


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

def parse_strike(rule, ltp, step=50):
    """Parse strike rule like 'ATM', 'ATM+100', 'ATM-100'. Returns strike price (int) or None if premium-based."""
    if isinstance(rule, str) and rule.upper().startswith("P"):
        # Premium-based selection — handled separately in enter_option_trade
        return None
    if isinstance(rule, str) and "ATM" in rule:
        atm = get_strike(ltp, step)
        expression = rule.replace("ATM", str(atm))
        try:
            return int(eval(expression))
        except Exception as e:
            print(f"Error parsing strike rule '{rule}': {e}")
            return atm
    return rule


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
            "criteria_timestamp":None,
            "criteria_type":None,
            "criteria_breakout_price":None, #high/low
            "symbol":None,
            "expiry_date":None,
            "strike_price":None,
            "option_type":None,
            "entry_signal": None,
            "entry_time": None,
            "entry_price": None,
            "profit_points" : None,
            "stoploss":None,
            "exit_timestamp":None,
            "exit_price":None,
            "reason_for_exit":None,
            "options_data":None,
            }

def merge_expires(data,symbol):
    exp_collection = {"NIFTY_EXPIRES":["2020-01-02","2020-01-09","2020-01-16","2020-01-23","2020-01-30","2020-02-06","2020-02-13","2020-02-20","2020-02-27","2020-03-05","2020-03-12","2020-03-19","2020-03-26","2020-04-01","2020-04-09","2020-04-16","2020-04-23","2020-04-30","2020-05-07","2020-05-14","2020-05-21","2020-05-28","2020-06-04","2020-06-11","2020-06-18","2020-06-25","2020-07-02","2020-07-09","2020-07-16","2020-07-23","2020-07-30","2020-08-06","2020-08-13","2020-08-20","2020-08-27","2020-09-03","2020-09-10","2020-09-17","2020-09-24","2020-10-01","2020-10-08","2020-10-15","2020-10-22","2020-10-29","2020-11-05","2020-11-12","2020-11-19","2020-11-26","2020-12-03","2020-12-10","2020-12-17","2020-12-24","2020-12-31","2021-01-07","2021-01-14","2021-01-21","2021-01-28","2021-02-04","2021-02-11","2021-02-18","2021-02-25","2021-03-04","2021-03-10","2021-03-18","2021-03-25","2021-04-01","2021-04-08","2021-04-15","2021-04-22","2021-04-29","2021-05-06","2021-05-12","2021-05-20","2021-05-27","2021-06-03","2021-06-10","2021-06-17","2021-06-24","2021-07-01","2021-07-08","2021-07-15","2021-07-22","2021-07-29","2021-08-05","2021-08-12","2021-08-18","2021-08-26","2021-09-02","2021-09-09","2021-09-16","2021-09-23","2021-09-30","2021-10-07","2021-10-14","2021-10-21","2021-10-28","2021-11-03","2021-11-11","2021-11-18","2021-11-25","2021-12-02","2021-12-09","2021-12-16","2021-12-23","2021-12-30","2022-01-06","2022-01-13","2022-01-20","2022-01-27","2022-02-03","2022-02-10","2022-02-17","2022-02-24","2022-03-03","2022-03-10","2022-03-17","2022-03-24","2022-03-31","2022-04-07","2022-04-13","2022-04-21","2022-04-28","2022-05-05","2022-05-12","2022-05-19","2022-05-26","2022-06-02","2022-06-09","2022-06-16","2022-06-23","2022-06-30","2022-07-07","2022-07-14","2022-07-21","2022-07-28","2022-08-04","2022-08-11","2022-08-18","2022-08-25","2022-09-01","2022-09-08","2022-09-15","2022-09-22","2022-09-29","2022-10-06","2022-10-13","2022-10-20","2022-10-27","2022-11-03","2022-11-10","2022-11-17","2022-11-24","2022-12-01","2022-12-08","2022-12-15","2022-12-22","2022-12-29","2023-01-05","2023-01-12","2023-01-19","2023-01-25","2023-02-02","2023-02-09","2023-02-16","2023-02-23","2023-03-02","2023-03-09","2023-03-16","2023-03-23","2023-03-29","2023-03-30","2023-04-06","2023-04-13","2023-04-20","2023-04-27","2023-05-04","2023-05-11","2023-05-18","2023-05-25","2023-06-01","2023-06-08","2023-06-15","2023-06-22","2023-06-28","2023-06-29","2023-07-06","2023-07-13","2023-07-20","2023-07-27","2023-08-03","2023-08-10","2023-08-17","2023-08-24","2023-08-31","2023-09-07","2023-09-14","2023-09-21","2023-09-28","2023-10-05","2023-10-12","2023-10-19","2023-10-26","2023-11-02","2023-11-09","2023-11-16","2023-11-23","2023-11-30","2023-12-07","2023-12-14","2023-12-21","2023-12-28","2024-01-04","2024-01-11","2024-01-18","2024-01-25","2024-02-01","2024-02-08","2024-02-15","2024-02-22","2024-02-29","2024-03-07","2024-03-14","2024-03-21","2024-03-28","2024-04-04","2024-04-10","2024-04-18","2024-04-25","2024-05-02","2024-05-09","2024-05-16","2024-05-23","2024-05-30","2024-06-06","2024-06-13","2024-06-20","2024-06-27","2024-07-04","2024-07-11","2024-07-18","2024-07-25","2024-08-01","2024-08-08","2024-08-14","2024-08-22","2024-08-29","2024-09-05","2024-09-12","2024-09-19","2024-09-26","2024-10-03","2024-10-10","2024-10-17","2024-10-24","2024-10-31","2024-11-07","2024-11-14","2024-11-21","2024-11-28","2024-12-05","2024-12-12","2024-12-19","2024-12-26","2025-01-02","2025-01-09","2025-01-16","2025-01-23","2025-01-30","2025-02-06","2025-02-13","2025-02-20","2025-02-27","2025-03-06","2025-03-13","2025-03-20","2025-03-27","2025-04-03","2025-04-09","2025-04-17","2025-04-24","2025-04-30","2025-05-08","2025-05-15","2025-05-22","2025-05-29","2025-06-05","2025-06-12","2025-06-19","2025-06-26","2025-07-03","2025-07-10","2025-07-17","2025-07-24","2025-07-31","2025-08-07","2025-08-14","2025-08-21","2025-08-28","2025-09-02","2025-09-09","2025-09-16","2025-09-23","2025-09-25","2025-09-30","2025-10-07","2025-10-14","2025-10-20","2025-10-28","2025-11-04","2025-11-11","2026-01-06","2026-01-13","2026-01-20","2026-01-27","2026-02-03","2026-02-10","2026-02-17","2026-02-24","2026-03-02","2026-03-10","2026-03-17","2026-03-24","2026-03-26","2026-03-30","2026-03-31","2026-04-07","2026-04-13","2026-04-21","2026-04-28","2026-05-05","2026-05-12","2026-05-19","2026-05-26","2026-06-02","2026-06-09","2026-06-16","2026-06-23","2026-06-25","2026-06-30","2026-07-07","2026-07-28","2026-08-25","2026-09-29","2026-12-29","2026-12-31"]}

    data = data.copy()
    data.index = pd.to_datetime(data.index)
    data['datetime'] = pd.to_datetime(data.index)

    # 1) Add a pure date column to data
    data["trade_date"] = data.index.normalize()  # strips time -> 2024-01-04 00:00:00
    # 2) Prepare expiry df with a date column
    exp_df = pd.DataFrame({
        "expiry": pd.to_datetime(exp_collection[f"{symbol}_EXPIRES"])
    }).sort_values("expiry")

    exp_df["expiry_date"] = exp_df["expiry"].dt.normalize()

    # 3) merge_asof on date, not full timestamp
    final_df = pd.merge_asof(
        data.sort_values("trade_date"),
        exp_df[["expiry_date", "expiry"]].sort_values("expiry_date"),
        left_on="trade_date",
        right_on="expiry_date",
        direction="forward"
    )

    # 4) Clean up
    final_df = final_df.drop(columns=["trade_date", "expiry_date"])
    final_df.set_index(keys="datetime",inplace=True)
    final_df["expiry"] = pd.to_datetime(final_df["expiry"]).dt.date
    final_df.dropna(subset=["expiry"],inplace=True)
    final_df.sort_values(by="datetime",inplace=True)
    return final_df
    
                    

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
    signals = []
    step_size = {"NIFTY":50,"SENSEX":100,"BANKNIFTY":100},
    OPTIONS_PATH = "options_dir"
    options_levels = {
                "CALL_level":60,
                "PUT_level":40
                }
    options_side_config = {
                "CALL_SUPPORT":"BUY",
                "CALL_RESISTANCE":"SELL",
                "PUT_SUPPORT":"SELL",
                "PUT_RESISTANCE":"BUY",
                },
    RSI_lenght = 14
    symbol = "NIFTY"
    def generate_symbol(self,option_type):
        expiry = self.data.expiry[-1].strftime("%y%m%d")

        ATM_KEY = (
            f"{self.symbol.upper()}"
            f"{expiry}"
            f"{int(float(self.current_trade['strike_price']))}"
            f"{option_type.upper()}"
        )
        return ATM_KEY
    
    def trade_finished(self):
        if self.current_trade["entry_signal"] == "BUY":
            self.current_trade["profit_points"] = (
                self.current_trade["exit_price"] -
                self.current_trade["entry_price"]
            )
        elif self.current_trade["entry_signal"] == "SELL":
            self.current_trade["profit_points"] = (
                self.current_trade["entry_price"] -
                self.current_trade["exit_price"]
            )

        RsiLevelsShift.signals.append([
            self.current_trade["criteria_timestamp"],
            self.current_trade["criteria_type"],
            self.current_trade["criteria_breakout_price"],
            self.current_trade["symbol"],
            self.current_trade["expiry_date"],
            self.current_trade["strike_price"],
            self.current_trade["option_type"],
            self.current_trade["entry_signal"],
            self.current_trade["entry_time"],
            self.current_trade["entry_price"],
            self.current_trade["profit_points"],
            self.current_trade["stoploss"],
            self.current_trade["exit_timestamp"],
            self.current_trade["exit_price"],
            self.current_trade["reason_for_exit"],
        ])
        self.current_trade = default_records()

    def init(self):
        # State tracking
       self.current_trade = default_records()
    
    def next(self):
        if len(self.data) < self.RSI_lenght:
            return

        current_time = self.data.index[-1].time()
        # 1. Intraday Exit (Square off before market close)
        trade_fill_type = (self.data.signal[-2])
        if  trade_fill_type and (not self.current_trade["entry_price"]):
            print("current_time == ",current_time)
            print(trade_fill_type)
            opttype,criteriatype = trade_fill_type.split("_")
            # print(opttype)
            if (trade_fill_type in self.options_side_config):
                transtype = self.options_side_config[trade_fill_type].upper()
                is_call = (opttype == "CALL")
                is_put = (opttype == "PUT")
                high_breakout = (self.data.Close[-1] > self.data.High[-2])
                low_breakdown = (self.data.Close[-1] < self.data.Low[-2])
                # ---------- call-sell,put-buy ----------------
                if (criteriatype.upper() == "RESISTANCE") and ((is_call and low_breakdown) or (is_put and high_breakout)) :
                    self.current_trade["criteria_timestamp"] = self.data.index[-2]
                    self.current_trade["criteria_type"] = criteriatype
                    self.current_trade["option_type"] = opttype
                    
                    self.current_trade["entry_signal"] = transtype
                    self.current_trade["symbol"] = self.symbol
                    self.current_trade["entry_time"] = self.data.index[-1]
                    self.current_trade["expiry_date"] = self.data.expiry[-1]
                    self.current_trade["strike_price"] = parse_strike(self.strike_config, self.data.Close[-1], self.step_size.get(self.symbol, 50))
                    if is_call:
                        self.current_trade["stoploss"] = self.data.High[-2]
                        self.current_trade["criteria_breakout_price"] = self.data.Low[-2]
                        ATM_KEY = self.generate_symbol("CE")
                    else:
                        self.current_trade["stoploss"] = self.data.Low[-2]
                        self.current_trade["criteria_breakout_price"] = self.data.High[-2]
                        ATM_KEY = self.generate_symbol("PE")

                    ATM_DF =  pd.read_csv(os.path.join(self.OPTIONS_PATH,ATM_KEY+".csv",),names=["Date","Time","Open","High","Low","Close","Volume","IO"],index_col=False,parse_dates=[["Date","Time"]])
                    ATM_DF.rename(columns={"Date_Time": "timestamp"}, inplace=True)
                    ATM_DF = ATM_DF[ATM_DF["timestamp"].dt.date == self.data.index[-1].date()].sort_values(by="timestamp")
                    self.current_trade["entry_price"] = ATM_DF[ATM_DF["timestamp"] <= self.data.index[-1]].iloc[-1]["Close"]    
                    self.current_trade["options_data"] = ATM_DF
                    return
                # ---------- call-buy,put-sell ----------------
                if (criteriatype.upper() == "SUPPORT") and ((is_call and high_breakout) or (is_put and low_breakdown)) :
                    self.current_trade["criteria_timestamp"] = self.data.index[-2]
                    self.current_trade["criteria_type"] = criteriatype
                    self.current_trade["option_type"] = opttype
                    
                    self.current_trade["entry_signal"] = transtype
                    self.current_trade["symbol"] = self.symbol
                    self.current_trade["entry_time"] = self.data.index[-1]
                    self.current_trade["expiry_date"] = self.data.expiry[-1]
                    self.current_trade["strike_price"] = parse_strike(self.strike_config, self.data.Close[-1], self.step_size.get(self.symbol, 50))
                    if is_call:
                        self.current_trade["stoploss"] = self.data.Low[-2]
                        self.current_trade["criteria_breakout_price"] = self.data.High[-2]
                        ATM_KEY = self.generate_symbol("CE")

                    else:
                        self.current_trade["stoploss"] = self.data.High[-2]
                        self.current_trade["criteria_breakout_price"] = self.data.Low[-2]
                        ATM_KEY = self.generate_symbol("PE")

                    ATM_DF =  pd.read_csv(os.path.join(self.OPTIONS_PATH,ATM_KEY+".csv",),names=["Date","Time","Open","High","Low","Close","Volume","IO"],index_col=False,parse_dates=[["Date","Time"]])
                    ATM_DF.rename(columns={"Date_Time": "timestamp"}, inplace=True)
                    ATM_DF = ATM_DF[ATM_DF["timestamp"].dt.date == self.data.index[-1].date()].sort_values(by="timestamp")
                    self.current_trade["entry_price"] = ATM_DF[ATM_DF["timestamp"] <= self.data.index[-1]].iloc[-1]["Close"]    
                    self.current_trade["options_data"] = ATM_DF
                    return
                    
        elif self.current_trade["entry_price"] :
            if (self.current_trade["entry_signal"] == "BUY"):
                if self.data.Low[-1] < self.current_trade["stoploss"]:
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Stoploss"
                    self.trade_finished()

                elif self.data.Close[-1] < self.data.Low[-2]:
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Closed Below Prevous Low"
                    self.trade_finished()
                
                elif self.data.index[-1].time() >= dtime(15,15):
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Exittime"
                    self.trade_finished()

                
            elif (self.current_trade["entry_signal"] == "SELL"):
                if self.data.High[-1] > self.current_trade["stoploss"]:
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Stoploss"
                    self.trade_finished()

                elif self.data.Close[-1] > self.data.High[-2]:
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Closed Above Prevous High"
                    self.trade_finished()
                
                elif self.data.index[-1].time() >= dtime(15,15):
                    ATM_DF :pd.DataFrame= self.current_trade["options_data"].sort_values(by="timestamp")
                    EXIT_ATM_df = ATM_DF[ATM_DF["timestamp"].dt.time >= self.data.index[-1].time()].iloc[0]["Close"]

                    self.current_trade["exit_timestamp"] = self.data.index[-1] 
                    self.current_trade["exit_price"] = EXIT_ATM_df
                    self.current_trade["reason_for_exit"] = "Exittime"
                    self.trade_finished()
                    

# ------------------------------------------------------------------------------------------------
def recovery_days(cum_pnl):
    peak = cum_pnl.cummax()
    drawdown = cum_pnl - peak

    print("drawdown == ",drawdown)
    print("cum_pnl == ",cum_pnl)
    max_dd_idx = drawdown.idxmin()
    print("max_dd_idx === ",max_dd_idx)
    peak_before_dd = peak[:max_dd_idx].iloc[-1]

  
    dd_start_idx = peak[:max_dd_idx][peak[:max_dd_idx] == peak_before_dd].index[-1]

 
    recovery_point = cum_pnl[max_dd_idx:]
    recovered = recovery_point[recovery_point >= peak_before_dd]

    if recovered.empty:
        return None  

    recovery_idx = recovered.index[0]
    recovery_duration = (recovery_idx - dd_start_idx).days

    return recovery_duration




def main(backtest_from_to,csv_file,only_expiry,symbol,OPTIONS_PATH,formated_symbols,step_size,timeframe,RSI_lenght,RSI_Source,strike_config,options_levels,options_side_config):
    cash_rs = 25000
    
    if not os.path.exists(csv_file):
        print(f"Data file not found: {csv_file}")
        return

    # Load 1-min data
    print("Loading data...")
    # df = pd.read_csv(csv_file)
    df =  pd.read_csv(csv_file,names=["Date","Time","open","high","low","close","volume","io"],index_col=False,parse_dates=[["Date","Time"]])
    df.rename(columns={"Date_Time": "timestamp"}, inplace=True)
    df = df[(df["timestamp"] >= backtest_from_to["start_date"]) & (df["timestamp"] <= backtest_from_to["end_date"])]
    # Consolidate to 5-min
    print("Consolidating to 5-min timeframe...")
    consolidated_df = ohlc_consolidate(df, timeframe, Isvolume=True)
    
    # Compute indicators
    print("Computing RSI indicators...")
    rsi_series = pdt.rsi(consolidated_df[RSI_Source.lower()],length = RSI_lenght).rename(f'rsi')
    consolidated_df = pd.concat([consolidated_df, rsi_series], axis=1)
    consolidated_df = identify_rsi_levels(consolidated_df,options_levels)
    consolidated_df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"},inplace=True)
    # print("levelsssss == ",consolidated_df)
    consolidated_df = merge_expires(consolidated_df,symbol)
    if only_expiry:
        consolidated_df = consolidated_df[
            consolidated_df.index.date == pd.to_datetime(consolidated_df["expiry"]).dt.date
        ]
    consolidated_df.to_csv("levels.csv",index=True)
    # exit(0)
    # Initializing Backtest
    print("Starting Backtest...")
    RsiLevelsShift.strike_config = strike_config
    RsiLevelsShift.options_levels = options_levels
    RsiLevelsShift.options_side_config = options_side_config
    RsiLevelsShift.RSI_lenght = RSI_lenght
    RsiLevelsShift.symbol = symbol
    RsiLevelsShift.OPTIONS_PATH = OPTIONS_PATH
    RsiLevelsShift.step_size = step_size
    
    
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
    # print(stats)
    trades_df= pd.DataFrame(RsiLevelsShift.signals, columns=[
        [
            "criteria_timestamp",
            "criteria_type",
            "criteria_breakout_price",
            "symbol",
            "expiry_date",
            "strike_price",
            "option_type",
            "entry_signal",
            "ENTRY_TIME",
            "entry_price",
            "PNL",
            "stoploss",
            "EXIT_TIME",
            "exit_price",
            "reason_for_exit",
            ]
        ]) 

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
        drawdown = (cum_pnl - peak)
        max_dd = drawdown.min()
        drawdown_data.append((year, max_dd))
    
    monthly_trades = trades_df.groupby('month').size()
    cum_pnl = trades_df['PNL'].cumsum()
    cum_pnl.index = trades_df['EXIT_TIME']

    recovery_days_from_dd = recovery_days(cum_pnl)

    # trades_df.to_csv("trades.csv", index=False)
    highest_profit = trades_df['PNL'].max()
    highest_loss = trades_df['PNL'].min()
    
    
    roi_data = (yearly_pnl / cash_rs) * 100
    summary_rows = []
    
    for period, pnl in monthly_pnl.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': pnl, 'option_type': f'Monthly PnL ({period})'})

    for year, pnl in yearly_pnl.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME':None, 'PNL': pnl, 'option_type': f'Total Year PnL ({year})'})

    for year, dd in drawdown_data:
        summary_rows.append({'ENTRY_TIME':None, 'EXIT_TIME': None, 'PNL': dd, 'option_type': f'Max Drawdown ({year})'})


    for year, roi in roi_data.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': roi, 'option_type': f'ROI % ({year})'})


    for period, count in monthly_trades.items():
        summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': count, 'option_type': f'Trades in ({period})'})
    
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': recovery_days_from_dd, 'option_type': 'Recovery Days from MaxDD'})
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': highest_profit, 'option_type': 'Highest Single Trade Profit'})
    summary_rows.append({'ENTRY_TIME': None, 'EXIT_TIME': None, 'PNL': highest_loss, 'option_type': 'Highest Single Trade Loss'})

    summary_df = pd.DataFrame(summary_rows)
    final_df = pd.concat([trades_df, summary_df], ignore_index=True)
    final_df.drop(columns=["year","month"],inplace=True)
    final_df.to_csv("Backtest_df.csv",index=False)

    # # Save trades to CSV
    # if hasattr(stats, '_trades') and not stats._trades.empty:
    #     stats._trades.to_csv("triple_conf_trades.csv", index=False)
    #     print("\nTrades saved to triple_conf_trades.csv")
    # else:
    #     print("\nNo trades executed.")

if __name__ == "__main__":
    
    kwags = dict(
    backtest_from_to = {"start_date":datetime(2025,1,1),"end_date":datetime(2025,9,30)},
    symbol = "NIFTY",
    formated_symbols={"NIFTY":"NIFTY 50","SENSEX":"SENSEX","BANKNIFTY":"NIFTY BANK"},
    timeframe = "5min", 
    RSI_lenght = 14,
    RSI_Source = "Close",
    strike_config = "ATM",  # "ATM", "ATM+100", "ATM-100" 
    step_size = {"NIFTY":50,"SENSEX":100,"BANKNIFTY":100},
    only_expiry = False,
    OPTIONS_PATH = "",
    csv_file = "",
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
