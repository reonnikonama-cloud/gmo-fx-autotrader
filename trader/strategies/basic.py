import pandas as pd
import numpy as np
from typing import Dict, Any
from trader.utils.candlestick import detect_candlestick_patterns

class BasicStrategy:
    """基本SMA/RSI/ATR戦略（共通ローソク足判定モジュール参照）"""

    def __init__(self, short_window: int = 5, long_window: int = 20, rsi_window: int = 14, atr_window: int = 14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window
        self.atr_window = atr_window

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['sma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_window).mean()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_window).mean()

        return df

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": "データ不足"}

        df_ind = self._calculate_indicators(df)
        curr, prev = df_ind.iloc[-1], df_ind.iloc[-2]

        patterns = detect_candlestick_patterns(df_ind)

        gold_cross = (prev['sma_short'] <= prev['sma_long']) and (curr['sma_short'] > curr['sma_long'])
        dead_cross = (prev['sma_short'] >= prev['sma_long']) and (curr['sma_short'] < curr['sma_long'])

        bullish_keys = ["bullish_marubozu", "hammer_pinbar", "bullish_engulfing", "bullish_harami", "piercing_line", "three_red_soldiers", "morning_star"]
        bearish_keys = ["bearish_marubozu", "shooting_star_pinbar", "bearish_engulfing", "bearish_harami", "dark_cloud_cover", "three_black_crows", "evening_star"]

        active_bullish = [k for k in bullish_keys if patterns.get(k)]
        active_bearish = [k for k in bearish_keys if patterns.get(k)]

        signal = "HOLD"
        reason = "NONE"

        if gold_cross and curr['rsi'] < 70:
            signal = "BUY"
            reason = f"Golden Cross (RSI: {curr['rsi']:.1f})"
        elif dead_cross and curr['rsi'] > 30:
            signal = "SELL"
            reason = f"Dead Cross (RSI: {curr['rsi']:.1f})"
        elif active_bullish and curr['rsi'] < 65:
            signal = "BUY"
            reason = f"Bullish Pattern [{', '.join(active_bullish)}] (RSI: {curr['rsi']:.1f})"
        elif active_bearish and curr['rsi'] > 35:
            signal = "SELL"
            reason = f"Bearish Pattern [{', '.join(active_bearish)}] (RSI: {curr['rsi']:.1f})"

        atr = curr['atr'] if not np.isnan(curr['atr']) else 0.10
        close_price = curr['close']

        sl_price = round(close_price - (atr * 2.0), 3) if signal == "BUY" else round(close_price + (atr * 2.0), 3)
        tp_price = round(close_price + (atr * 3.0), 3) if signal == "BUY" else round(close_price - (atr * 3.0), 3)

        return {
            "signal": signal,
            "reason": reason,
            "atr": atr,
            "sl_price": sl_price if signal != "HOLD" else None,
            "tp_price": tp_price if signal != "HOLD" else None,
            "patterns": patterns
        }

    def calculate_position_size(self, balance: float, current_price: float, risk_ratio: float, atr: float) -> float:
        risk_amount = balance * risk_ratio
        stop_loss_pip_val = max(atr * 2.0, 0.10)
        
        loss_per_1000_units = stop_loss_pip_val * 1000
        units = (risk_amount / loss_per_1000_units) * 1000
        units = max(1000, int(units // 1000) * 1000)
        return float(units)
