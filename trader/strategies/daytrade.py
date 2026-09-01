from typing import Dict, Any
import pandas as pd
import numpy as np

from trader.config.pair_config import DAYTRADE_PAIR_CONFIG
from trader.utils.candlestick import detect_candlestick_patterns

class DaytradeStrategy:
    """デイトレード専用戦略（15分〜1時間足軸・固定RR 1:1.7）"""

    def __init__(self, symbol: str = "USD_JPY", short_window: int = 10, long_window: int = 30, rsi_window: int = 14):
        self.symbol = symbol
        config = DAYTRADE_PAIR_CONFIG.get(symbol, DAYTRADE_PAIR_CONFIG["USD_JPY"])
        self.tp_pips = config["tp_pips"]
        self.sl_pips = config["sl_pips"]
        self.daily_target_pips = config.get("daily_target_pips", 30.0)
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['sma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_window).mean()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": "データ不足", "strategy_type": "DAYTRADE"}

        df_ind = self._calculate_indicators(df)
        curr, prev = df_ind.iloc[-1], df_ind.iloc[-2]
        patterns = detect_candlestick_patterns(df_ind)

        gold_cross = (prev['sma_short'] <= prev['sma_long']) and (curr['sma_short'] > curr['sma_long'])
        dead_cross = (prev['sma_short'] >= prev['sma_long']) and (curr['sma_short'] < curr['sma_long'])

        bullish_keys = ["bullish_engulfing", "bullish_harami", "piercing_line", "morning_star"]
        bearish_keys = ["bearish_engulfing", "bearish_harami", "dark_cloud_cover", "evening_star"]

        active_bullish = [k for k in bullish_keys if patterns.get(k)]
        active_bearish = [k for k in bearish_keys if patterns.get(k)]

        signal = "HOLD"
        reason = "NONE"

        if (gold_cross or active_bullish) and curr['rsi'] < 65:
            signal = "BUY"
            reason = f"Daytrade BUY (Pattern: {active_bullish if active_bullish else 'SMA Cross'}, RSI: {curr['rsi']:.1f})"
        elif (dead_cross or active_bearish) and curr['rsi'] > 35:
            signal = "SELL"
            reason = f"Daytrade SELL (Pattern: {active_bearish if active_bearish else 'SMA Cross'}, RSI: {curr['rsi']:.1f})"

        pip_unit = 0.01 if "JPY" in self.symbol else 0.0001
        close_price = curr['close']

        if signal == "BUY":
            tp_price = round(close_price + (self.tp_pips * pip_unit), 3)
            sl_price = round(close_price - (self.sl_pips * pip_unit), 3)
        elif signal == "SELL":
            tp_price = round(close_price - (self.tp_pips * pip_unit), 3)
            sl_price = round(close_price + (self.sl_pips * pip_unit), 3)
        else:
            tp_price, sl_price = None, None

        return {
            "signal": signal,
            "reason": reason,
            "close_price": close_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "patterns": patterns,
            "strategy_type": "DAYTRADE"
        }
