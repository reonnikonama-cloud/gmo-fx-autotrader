# analyzer/risk_analyzer.py
import numpy as np
import pandas as pd

class RiskAnalyzer:
    """リスク分析・金融工学評価ユニット"""
    def __init__(self, risk_free_rate: float = 0.001):
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(self, trade_history: list, current_balance: float, initial_capital: float) -> dict:
        pnls = [t.get("pnl", 0.0) for t in trade_history if "pnl" in t]
        if not pnls:
            return {
                "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "var_95": 0.0
            }

        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]

        win_rate = (len(wins) / len(pnls)) * 100
        profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else (sum(wins) if sum(wins) > 0 else 0.0)

        # 資産曲線とMaxDrawdown(%)の算出
        balance_curve = [initial_capital]
        for p in pnls:
            balance_curve.append(balance_curve[-1] + p)
        
        s = pd.Series(balance_curve)
        peak = s.cummax()
        dd = (s - peak) / peak
        max_dd = abs(float(dd.min())) * 100

        # シャープレシオ & Historical VaR (95%)
        returns = pd.Series(pnls) / initial_capital
        std_dev = float(returns.std()) if len(returns) > 1 else 0.0
        sharpe = (float(returns.mean()) - self.risk_free_rate) / std_dev if std_dev > 0 else 0.0
        var_95 = abs(float(np.percentile(pnls, 5))) if len(pnls) >= 5 else 0.0

        return {
            "total_trades": len(pnls),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "var_95": round(var_95, 0)
        }
