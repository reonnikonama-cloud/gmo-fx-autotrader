from typing import Dict, Any
import pandas as pd
import numpy as np

from trader.config.pair_config import SCALPING_PAIR_CONFIG
from trader.utils.candlestick import detect_candlestick_patterns

class StandardOpportunityStrategy:
    """スキャルピング専用戦略（1分足〜5分足軸・固定TP/SL）"""

    def __init__(self, symbol: str = "USD_JPY", short_window: int = 3, long_window: int = 10, rsi_window: int = 9):
        self.symbol = symbol
        config = SCALPING_PAIR_CONFIG.get(symbol, SCALPING_PAIR_CONFIG["USD_JPY"])
        self.tp_pips = config["tp_pips"]
        self.sl_pips = config["sl_pips"]
        self.daily_target_pips = config.get("daily_target_pips", 30.0)
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ema_short'] = df['close'].ewm(span=self.short_window, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.long_window, adjust=False).mean()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": "データ不足", "strategy_type": "SCALPING"}

        df_ind = self._calculate_indicators(df)
        curr, prev = df_ind.iloc[-1], df_ind.iloc[-2]
        patterns = detect_candlestick_patterns(df_ind)

        gold_cross = (prev['ema_short'] <= prev['ema_long']) and (curr['ema_short'] > curr['ema_long'])
        dead_cross = (prev['ema_short'] >= prev['ema_long']) and (curr['ema_short'] < curr['ema_long'])

        signal = "HOLD"
        reason = "NONE"

        if (gold_cross or patterns.get("bullish_marubozu") or patterns.get("hammer_pinbar")) and curr['rsi'] < 60:
            signal = "BUY"
            reason = f"Scalp BUY (RSI: {curr['rsi']:.1f})"
        elif (dead_cross or patterns.get("bearish_marubozu") or patterns.get("shooting_star_pinbar")) and curr['rsi'] > 40:
            signal = "SELL"
            reason = f"Scalp SELL (RSI: {curr['rsi']:.1f})"

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
            "strategy_type": "SCALPING"
        }
