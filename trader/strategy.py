import pandas as pd
import numpy as np
from typing import Dict, Any

class TechnicalAnalysis:
    @staticmethod
    def calculate_sma(df: pd.DataFrame, column: str = "close", window: int = 20) -> pd.Series:
        return df[column].rolling(window=window).mean()

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, column: str = "close", window: int = 14) -> pd.Series:
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

class BasicStrategy:
    def __init__(self, short_window: int = 5, long_window: int = 20, rsi_window: int = 14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.long_window + 1:
            return {"signal": "HOLD", "reason": "データ数不足"}

        df["sma_short"] = TechnicalAnalysis.calculate_sma(df, "close", self.short_window)
        df["sma_long"] = TechnicalAnalysis.calculate_sma(df, "close", self.long_window)
        df["rsi"] = TechnicalAnalysis.calculate_rsi(df, "close", self.rsi_window)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        signal = "HOLD"
        reason = "シグナルなし"

        if (prev["sma_short"] <= prev["sma_long"]) and (curr["sma_short"] > curr["sma_long"]):
            if curr["rsi"] < 70:
                signal = "BUY"
                reason = f"SMAゴールデンクロス達成 (RSI: {curr['rsi']:.1f})"
            else:
                reason = f"GC達成もRSI高値警戒 (RSI: {curr['rsi']:.1f})"
        elif (prev["sma_short"] >= prev["sma_long"]) and (curr["sma_short"] < curr["sma_long"]):
            if curr["rsi"] > 30:
                signal = "SELL"
                reason = f"SMAデッドクロス達成 (RSI: {curr['rsi']:.1f})"
            else:
                reason = f"DC達成もRSI安値警戒 (RSI: {curr['rsi']:.1f})"

        return {
            "signal": signal,
            "reason": reason,
            "price": curr["close"],
            "sma_short": round(curr["sma_short"], 3),
            "sma_long": round(curr["sma_long"], 3),
            "rsi": round(curr["rsi"], 2)
        }

    @staticmethod
    def calculate_position_size(balance: float, price: float, risk_ratio: float = 0.02, min_size: int = 100) -> float:
        max_margin = balance * risk_ratio
        max_amount = (max_margin / (price * 0.05))
        amount = int(max_amount // min_size) * min_size
        return float(max(amount, min_size))
