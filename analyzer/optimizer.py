# analyzer/optimizer.py
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

class StrategyOptimizer:
    """
    仮想売買データおよびヒストリカルデータを活用し、
    過学習（カーブフィッティング）を防止しながら戦略パラメータを自動チューニングする最適化エンジン
    """

    def __init__(self, initial_capital: float = 50000.0, min_trades: int = 5, train_ratio: float = 0.7):
        self.initial_capital = initial_capital
        self.min_trades = min_trades          # 最低取引回数フィルター（サンプル不足による偶然の好成績を排除）
        self.train_ratio = train_ratio        # イン・サンプル(学習)とアウト・オブ・サンプル(検証)の分割比率
        
        # パラメータの探索空間
        self.param_grid = {
            "short_window": [3, 5, 8],
            "long_window": [15, 20, 25],
            "rsi_window": [10, 14, 18],
            "atr_window": [10, 14, 20]
        }

    def simulate_strategy(self, df: pd.DataFrame, short_w: int, long_w: int, rsi_w: int) -> Tuple[float, int]:
        """
        指定されたパラメータセットで簡易バックテストを行い、損益と取引回数を算出
        Returns:
            Tuple[float, int]: (獲得損益, 総取引回数)
        """
        if len(df) < long_w + 5:
            return 0.0, 0

        df = df.copy()
        df["sma_short"] = df["close"].rolling(window=short_w).mean()
        df["sma_long"] = df["close"].rolling(window=long_w).mean()

        # RSI計算
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_w).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_w).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        balance = self.initial_capital
        position = None  # None, "BUY", "SELL"
        entry_price = 0.0
        trade_count = 0

        for i in range(long_w, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]

            curr_rsi = row["rsi"] if not np.isnan(row["rsi"]) else 50.0

            # ゴールデンクロス & RSI過熱感チェック
            buy_signal = (prev_row["sma_short"] <= prev_row["sma_long"]) and (row["sma_short"] > row["sma_long"]) and (curr_rsi < 70)
            # デッドクロス & RSI売られすぎチェック
            sell_signal = (prev_row["sma_short"] >= prev_row["sma_long"]) and (row["sma_short"] < row["sma_long"]) and (curr_rsi > 30)

            # エグジット・シグナル
            if position == "BUY" and sell_signal:
                pnl = (row["close"] - entry_price) * 1000  # 1000通貨単位での試算
                balance += pnl
                position = None
                trade_count += 1
            elif position == "SELL" and buy_signal:
                pnl = (entry_price - row["close"]) * 1000
                balance += pnl
                position = None
                trade_count += 1

            # エントリー・シグナル
            if position is None:
                if buy_signal:
                    position = "BUY"
                    entry_price = row["close"]
                elif sell_signal:
                    position = "SELL"
                    entry_price = row["close"]

        return balance - self.initial_capital, trade_count

    def optimize_parameters(self, historical_candles: Dict[str, pd.DataFrame], current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Out-of-Sample（アウト・オブ・サンプル）検証および最低取引回数フィルターを適用し、
        過学習を防止した最適なパラメータセットを導出する
        """
        best_score = -float("inf")
        best_params = current_params.copy()

        for short_w in self.param_grid["short_window"]:
            for long_w in self.param_grid["long_window"]:
                if short_w >= long_w:
                    continue  # 短期期間が長期期間以上の場合はスキップ

                for rsi_w in self.param_grid["rsi_window"]:
                    total_oos_pnl = 0.0
                    total_trades = 0
                    valid_symbol_count = 0

                    for symbol, df in historical_candles.items():
                        if df.empty or len(df) < long_w + 10:
                            continue

                        # データを In-Sample (学習用) と Out-of-Sample (検証用) に分割
                        split_idx = int(len(df) * self.train_ratio)
                        df_in_sample = df.iloc[:split_idx]
                        df_out_sample = df.iloc[split_idx:]

                        # フィルター1: In-Sample で利益が出ているか＆最低取引回数を満たしているか
                        is_pnl, is_trades = self.simulate_strategy(df_in_sample, short_w, long_w, rsi_w)
                        if is_pnl <= 0 or is_trades < self.min_trades:
                            continue  # 条件を満たさないパラメータは即棄却

                        # フィルター2: 未知の Out-of-Sample データで検証
                        oos_pnl, oos_trades = self.simulate_strategy(df_out_sample, short_w, long_w, rsi_w)
                        total_oos_pnl += oos_pnl
                        total_trades += oos_trades
                        valid_symbol_count += 1

                    if valid_symbol_count == 0:
                        continue

                    # 平均 Out-of-Sample 損益を評価スコアとする
                    avg_oos_score = total_oos_pnl / valid_symbol_count

                    # 最高スコアを更新した場合にセット
                    if avg_oos_score > best_score:
                        best_score = avg_oos_score
                        best_params = {
                            "short_window": short_w,
                            "long_window": long_w,
                            "rsi_window": rsi_w,
                            "atr_window": current_params.get("atr_window", 14)
                        }

        if best_score == -float("inf"):
            print("【自己成長エンジン】過学習フィルターを通過する条件を満たす新パラメータが見つかりませんでした。既存設定を維持します。")
            return current_params

        print(f"【自己成長エンジン】過学習フィルター通過 (検証用データ平均評価スコア: {best_score:,.1f}円相当)")
        return best_params
