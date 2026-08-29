# trader/strategy.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

class BasicStrategy:
    """
    テクニカル指標 (SMA + RSI + ATR) 及び動的リスク管理戦略
    """
    def __init__(self, short_window: int = 5, long_window: int = 20, rsi_window: int = 14, atr_window: int = 14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window
        self.atr_window = atr_window

        # サーキットブレーカー管理パラメータ
        self.max_daily_drawdown_ratio = 0.05  # 日次最大許容損失率 5%
        self.initial_daily_balance = None
        self.circuit_breaker_triggered = False
        self.last_reset_date = None

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """
        ATR (Average True Range) の計算
        """
        if len(df) < self.atr_window + 1:
            return 0.10  # デフォルト値 (10ピップス相当)

        high = df['high']
        low = df['low']
        close_prev = df['close'].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_window).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) and atr > 0 else 0.10

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """
        シグナル生成 + ATR動的SL/TPの算出
        """
        if self.circuit_breaker_triggered:
            return {"signal": "HOLD", "reason": "Circuit Breaker Active (Daily Max Loss Reached)", "sl_price": None, "tp_price": None, "atr": 0.0}

        if len(df) < self.long_window:
            return {"signal": "HOLD", "reason": "Insufficient Data", "sl_price": None, "tp_price": None, "atr": 0.0}

        df['sma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_window).mean()

        # RSI計算
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        curr_close = df['close'].iloc[-1]
        curr_short = df['sma_short'].iloc[-1]
        curr_long = df['sma_long'].iloc[-1]
        prev_short = df['sma_short'].iloc[-2]
        prev_long = df['sma_long'].iloc[-2]
        curr_rsi = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0

        atr = self.calculate_atr(df)

        signal = "HOLD"
        reason = f"SMA_S:{curr_short:.2f}, SMA_L:{curr_long:.2f}, RSI:{curr_rsi:.1f}"

        # ゴールデンクロス & RSI過熱感チェック
        if prev_short <= prev_long and curr_short > curr_long and curr_rsi < 70:
            signal = "BUY"
            reason = f"Golden Cross Detected (RSI: {curr_rsi:.1f})"
        # デッドクロス & RSI売られすぎチェック
        elif prev_short >= prev_long and curr_short < curr_long and curr_rsi > 30:
            signal = "SELL"
            reason = f"Dead Cross Detected (RSI: {curr_rsi:.1f})"

        # ATRに基づく可変ストップロス(1.5x ATR) / テイクプロフィット(3.0x ATR)
        sl_price, tp_price = None, None
        if signal == "BUY":
            sl_price = round(curr_close - (atr * 1.5), 3)
            tp_price = round(curr_close + (atr * 3.0), 3)
        elif signal == "SELL":
            sl_price = round(curr_close + (atr * 1.5), 3)
            tp_price = round(curr_close - (atr * 3.0), 3)

        return {
            "signal": signal,
            "reason": reason,
            "atr": atr,
            "sl_price": sl_price,
            "tp_price": tp_price
        }

    def calculate_position_size(self, balance: float, entry_price: float, risk_ratio: float, atr: float = 0.10) -> int:
        """
        定率リスクモデル（Fixed Fractional Risk）に基づく建玉数量計算
        リスク許容額 = 口座残高 * risk_ratio
        損切り幅 = ATR * 1.5
        """
        if balance <= 0 or entry_price <= 0:
            return 0

        risk_amount = balance * risk_ratio
        sl_distance = max(atr * 1.5, 0.05)  # 最小5ピップスは確保

        # 1通貨あたりの損失額(円) = sl_distance
        raw_units = risk_amount / sl_distance
        
        # GMOコイン FXの最小取引単位: 100通貨単位で丸め
        units = int(raw_units // 100) * 100
        return max(units, 100)  # 最低100通貨

    def check_circuit_breaker(self, current_balance: float) -> bool:
        """
        日次サーキットブレーカーチェック
        """
        today_str = datetime.now(JST).strftime("%Y-%m-%d")
        if self.last_reset_date != today_str:
            self.initial_daily_balance = current_balance
            self.circuit_breaker_triggered = False
            self.last_reset_date = today_str

        if self.initial_daily_balance and self.initial_daily_balance > 0:
            drawdown = (self.initial_daily_balance - current_balance) / self.initial_daily_balance
            if drawdown >= self.max_daily_drawdown_ratio:
                self.circuit_breaker_triggered = True

        return self.circuit_breaker_triggered
