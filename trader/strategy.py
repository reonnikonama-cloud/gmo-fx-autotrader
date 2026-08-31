import pandas as pd
import numpy as np
from typing import Dict, Any, List

class BasicStrategy:
    """外為どっとコム掲載のローソク足パターン全種を自動検知する拡張戦略クラス"""

    def __init__(self, short_window: int = 5, long_window: int = 20, rsi_window: int = 14, atr_window: int = 14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window
        self.atr_window = atr_window
        self.circuit_breaker_triggered = False

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "short_window": self.short_window,
            "long_window": self.long_window,
            "rsi_window": self.rsi_window,
            "atr_window": self.atr_window
        }

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 移動平均線 (SMA)
        df['sma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_window).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_window).mean()

        return df

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, bool]:
        """
        1本足・2本足・3本足のローソク足パターンを四本値から包括的に計算
        """
        results = {
            # 1本足
            "bullish_marubozu": False, "bearish_marubozu": False,  # 大陽線 / 大陰線
            "doji": False,                                         # 十字線 (転換点)
            "hammer_pinbar": False,                                # 下ヒゲ / タクリ足 (強気反転)
            "shooting_star_pinbar": False,                         # 上ヒゲ / 首吊り線 (弱気反転)
            # 2本足
            "bullish_engulfing": False, "bearish_engulfing": False, # 包み線
            "bullish_harami": False, "bearish_harami": False,       # はらみ線
            "piercing_line": False,                                # 切り込み線 (強気)
            "dark_cloud_cover": False,                             # かぶせ線 (弱気)
            # 3本足
            "three_red_soldiers": False,                           # 赤三兵 (強力な買い)
            "three_black_crows": False,                            # 黒三兵 (強力な売り)
            "morning_star": False,                                 # 明けの明星 (底打ち反転)
            "evening_star": False                                  # 宵の明星 (天井反転)
        }

        if len(df) < 3:
            return results

        c0 = df.iloc[-1]  # 最新足
        c1 = df.iloc[-2]  # 1本前
        c2 = df.iloc[-3]  # 2本前

        def body(c): return abs(c['close'] - c['open'])
        def range_total(c): return max(c['high'] - c['low'], 0.0001)
        def is_bull(c): return c['close'] > c['open']
        def is_bear(c): return c['close'] < c['open']

        # --- 1本足パターンの判定 ---
        # 十字線 (実体が全体の値幅の10%以下)
        results["doji"] = (body(c0) / range_total(c0)) <= 0.10

        # 大陽線 / 大陰線 (実体が全体の75%以上)
        results["bullish_marubozu"] = is_bull(c0) and (body(c0) / range_total(c0) >= 0.75)
        results["bearish_marubozu"] = is_bear(c0) and (body(c0) / range_total(c0) >= 0.75)

        # ピンバー（タクリ足・ハンマー / 首吊り線・流れ星）
        lower_shadow0 = min(c0['open'], c0['close']) - c0['low']
        upper_shadow0 = c0['high'] - max(c0['open'], c0['close'])
        results["hammer_pinbar"] = (lower_shadow0 >= 2 * body(c0)) and (upper_shadow0 <= body(c0) * 0.5)
        results["shooting_star_pinbar"] = (upper_shadow0 >= 2 * body(c0)) and (lower_shadow0 <= body(c0) * 0.5)

        # --- 2本足パターンの判定 ---
        # 包み線 (エンガルフィング)
        results["bullish_engulfing"] = is_bear(c1) and is_bull(c0) and (c0['open'] <= c1['close']) and (c0['close'] >= c1['open'])
        results["bearish_engulfing"] = is_bull(c1) and is_bear(c0) and (c0['open'] >= c1['close']) and (c0['close'] <= c1['open'])

        # はらみ線 (ハラミ)
        results["bullish_harami"] = is_bear(c1) and is_bull(c0) and (c0['open'] > c1['close']) and (c0['close'] < c1['open'])
        results["bearish_harami"] = is_bull(c1) and is_bear(c0) and (c0['open'] < c1['close']) and (c0['close'] > c1['open'])

        # 切り込み線 (陰線のあと、前足実体の中値以上まで押し返す陽線)
        c1_mid = c1['open'] - (body(c1) / 2)
        results["piercing_line"] = is_bear(c1) and is_bull(c0) and (c0['open'] < c1['low']) and (c0['close'] > c1_mid) and (c0['close'] < c1['open'])

        # かぶせ線 (陽線のあと、前足実体の中値以下まで食い込む陰線)
        c1_mid_bear = c1['open'] + (body(c1) / 2)
        results["dark_cloud_cover"] = is_bull(c1) and is_bear(c0) and (c0['open'] > c1['high']) and (c0['close'] < c1_mid_bear) and (c0['close'] > c1['open'])

        # --- 3本足パターンの判定 ---
        # 赤三兵 (陽線が3本連続して下値を切り上げる)
        results["three_red_soldiers"] = is_bull(c2) and is_bull(c1) and is_bull(c0) and \
                                         (c2['close'] < c1['close'] < c0['close']) and \
                                         (c2['open'] < c1['open'] < c0['open'])

        # 黒三兵 (陰線が3本連続して上値を切り下げる)
        results["three_black_crows"] = is_bear(c2) and is_bear(c1) and is_bear(c0) and \
                                        (c2['close'] > c1['close'] > c0['close']) and \
                                        (c2['open'] > c1['open'] > c0['open'])

        # 明けの明星 (大陰線 → 小足/十字線 → 大陽線)
        results["morning_star"] = is_bear(c2) and (body(c1) < body(c2) * 0.4) and is_bull(c0) and (c0['close'] > (c2['open'] + c2['close']) / 2)

        # 宵の明星 (大陽線 → 小足/十字線 → 大陰線)
        results["evening_star"] = is_bull(c2) and (body(c1) < body(c2) * 0.4) and is_bear(c0) and (c0['close'] < (c2['open'] + c2['close']) / 2)

        return results

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": "データ不足"}

        df_ind = self._calculate_indicators(df)
        curr = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        patterns = self.detect_candlestick_patterns(df_ind)

        # テクニカル指標（SMAクロス）
        gold_cross = (prev['sma_short'] <= prev['sma_long']) and (curr['sma_short'] > curr['sma_long'])
        dead_cross = (prev['sma_short'] >= prev['sma_long']) and (curr['sma_short'] < curr['sma_long'])

        # 強気 / 弱気パターンの集計
        bullish_keys = ["bullish_marubozu", "hammer_pinbar", "bullish_engulfing", "bullish_harami", "piercing_line", "three_red_soldiers", "morning_star"]
        bearish_keys = ["bearish_marubozu", "shooting_star_pinbar", "bearish_engulfing", "bearish_harami", "dark_cloud_cover", "three_black_crows", "evening_star"]

        active_bullish = [k for k in bullish_keys if patterns.get(k)]
        active_bearish = [k for k in bearish_keys if patterns.get(k)]

        signal = "HOLD"
        reason = "NONE"

        # 1. ゴールデンクロス / デッドクロス (最優先)
        if gold_cross and curr['rsi'] < 70:
            signal = "BUY"
            reason = f"Golden Cross (RSI: {curr['rsi']:.1f})"
        elif dead_cross and curr['rsi'] > 30:
            signal = "SELL"
            reason = f"Dead Cross (RSI: {curr['rsi']:.1f})"
        # 2. 複合ローソク足パターンシグナル (RSI過熱感フィルター適用)
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

