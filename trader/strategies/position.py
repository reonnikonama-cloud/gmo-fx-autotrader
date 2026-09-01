from typing import Dict, Any
import pandas as pd
import numpy as np

from trader.config.pair_config import POSITION_PAIR_CONFIG
from trader.utils.candlestick import detect_candlestick_patterns

class PositionStrategy:
    """ポジショントレード専用戦略（日足〜週足軸・可変リスクリワード 1:3〜1:5）"""

    def __init__(self, symbol: str = "USD_JPY", short_window: int = 20, long_window: int = 200, rsi_window: int = 14, atr_window: int = 14):
        self.symbol = symbol
        config = POSITION_PAIR_CONFIG.get(symbol, POSITION_PAIR_CONFIG["USD_JPY"])
        
        self.base_sl_pips = config.get("base_sl_pips", 150.0)
        self.min_rr = config.get("min_rr", 3.0)
        self.max_rr = config.get("max_rr", 5.0)
        
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

        df['sma_slope'] = (df['sma_short'].diff(5) / df['sma_short'].shift(5)).abs() * 100
        return df

    def _calculate_dynamic_rr(self, curr_row: pd.Series) -> float:
        slope = curr_row.get('sma_slope', 0.0)
        
        if pd.isna(slope) or slope <= 0.3:
            rr_ratio = self.min_rr
        elif slope >= 1.2:
            rr_ratio = self.max_rr
        else:
            rr_ratio = self.min_rr + ((slope - 0.3) / (1.2 - 0.3)) * (self.max_rr - self.min_rr)
            
        return round(rr_ratio, 2)

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": f"データ不足", "strategy_type": "POSITION"}

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

        if (gold_cross or active_bullish) and curr['rsi'] < 55:
            signal = "BUY"
            reason = f"Position BUY (Pattern: {active_bullish if active_bullish else '200SMA Cross'}, RSI: {curr['rsi']:.1f})"
        elif (dead_cross or active_bearish) and curr['rsi'] > 45:
            signal = "SELL"
            reason = f"Position SELL (Pattern: {active_bearish if active_bearish else '200SMA Cross'}, RSI: {curr['rsi']:.1f})"

        pip_unit = 0.01 if "JPY" in self.symbol else 0.0001
        close_price = curr['close']

        if signal != "HOLD":
            current_atr = curr['atr']
            if not np.isnan(current_atr) and current_atr > 0:
                sl_pips = round((current_atr * 2.0) / pip_unit, 1)
            else:
                sl_pips = self.base_sl_pips

            rr_ratio = self._calculate_dynamic_rr(curr)
            tp_pips = round(sl_pips * rr_ratio, 1)

            if signal == "BUY":
                tp_price = round(close_price + (tp_pips * pip_unit), 3)
                sl_price = round(close_price - (sl_pips * pip_unit), 3)
            else:
                tp_price = round(close_price - (tp_pips * pip_unit), 3)
                sl_price = round(close_price + (sl_pips * pip_unit), 3)

            reason += f" | Dynamic RR: 1:{rr_ratio:.2f}"
        else:
            tp_price, sl_price, rr_ratio = None, None, None

        return {
            "signal": signal,
            "reason": reason,
            "close_price": close_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "rr_ratio": rr_ratio,
            "patterns": patterns,
            "strategy_type": "POSITION"
        }
