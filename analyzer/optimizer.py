# analyzer/optimizer.py
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class StrategyOptimizer:
    """
    仮想売買データおよびヒストリカルデータを活用し、
    戦略パラメータを自動チューニング（自己成長）させる最適化エンジン
    """

    def __init__(self, initial_capital: float = 50000.0):
        self.initial_capital = initial_capital
        # パラメータの探索空間（探索範囲）
        self.param_grid = {
            "short_window": [3, 5, 8],
            "long_window": [15, 20, 25],
            "rsi_window": [10, 14, 18],
            "atr_window": [10, 14, 20]
        }

    def simulate_strategy(self, df: pd.DataFrame, short_w: int, long_w: int, rsi_w: int) -> float:
        """指定されたパラメータセットで簡易バックテストを行い、最終パフォーマンス（利回り）を算出"""
        if len(df) < long_w + 10:
            return 0.0

        df = df.copy()
        df["sma_short"] = df["close"].rolling(window=short_w).mean()
        df["sma_long"] = df["close"].rolling(window=long_w).mean()

        # 簡易RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_w).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_w).mean()
        rs = gain / (loss + 1e-8)
        df["rsi"] = 100 - (100 / (1 + rs))

        balance = self.initial_capital
        position = None  # None, "BUY", "SELL"
        entry_price = 0.0

        for i in range(long_w, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]

            # ゴールデンクロス & RSI過熱感チェック
            buy_signal = (prev_row["sma_short"] <= prev_row["sma_long"]) and (row["sma_short"] > row["sma_long"]) and (row["rsi"] < 70)
            # デッドクロス & RSI売られすぎチェック
            sell_signal = (prev_row["sma_short"] >= prev_row["sma_long"]) and (row["sma_short"] < row["sma_long"]) and (row["rsi"] > 30)

            # エグジット・シグナル
            if position == "BUY" and sell_signal:
                pnl = (row["close"] - entry_price) * 1000  # 1000通貨換算
                balance += pnl
                position = None
            elif position == "SELL" and buy_signal:
                pnl = (entry_price - row["close"]) * 1000
                balance += pnl
                position = None

            # エントリー・シグナル
            if position is None:
                if buy_signal:
                    position = "BUY"
                    entry_price = row["close"]
                elif sell_signal:
                    position = "SELL"
                    entry_price = row["close"]

        return balance - self.initial_capital

    def optimize_parameters(self, historical_candles: Dict[str, pd.DataFrame], current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        過去の全通貨ペアのローソク足データを交差検証し、最適なパラメータを導出する
        """
        best_score = -float("inf")
        best_params = current_params.copy()

        # パラメータ空間をグリッド探索
        for short_w in self.param_grid["short_window"]:
            for long_w in self.param_grid["long_window"]:
                if short_w >= long_w:
                    continue  # 短期が長期以上の場合はスキップ
                for rsi_w in self.param_grid["rsi_window"]:
                    total_pnl = 0.0
                    valid_symbol_count = 0

                    for symbol, df in historical_candles.items():
                        if df.empty:
                            continue
                        pnl = self.simulate_strategy(df, short_w, long_w, rsi_w)
                        total_pnl += pnl
                        valid_symbol_count += 1

                    if valid_symbol_count == 0:
                        continue

                    avg_score = total_pnl / valid_symbol_count

                    if avg_score > best_score:
                        best_score = avg_score
                        best_params = {
                            "short_window": short_w,
                            "long_window": long_w,
                            "rsi_window": rsi_w,
                            "atr_window": current_params.get("atr_window", 14)
                        }

        print(f"【自己成長エンジン】最適化完了 (評価スコア: {best_score:,.1f}円相当の改訂)")
        return best_params
