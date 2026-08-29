# reporter/report_generator.py
import csv

class PerformanceReporter:
    """報告部門ユニット（レポート生成 & 確定申告用取引明細出力）"""

    def generate_full_report(self, risk_metrics: dict, tax_metrics: dict, balance: float, initial_capital: float) -> str:
        total_pnl = balance - initial_capital
        
        report = [
            "==========================================",
            " 📊 総合パフォーマンス・リスク・税務報告書",
            "==========================================",
            f"【口座概要】 現在残高: {balance:,.0f}円 | 累計損益: {total_pnl:,.0f}円",
            "",
            "--- 🛡️ リスク分析ユニット (Risk Assessment) ---",
            f"・総取引数     : {risk_metrics.get('total_trades', 0)} 回",
            f"・勝率         : {risk_metrics.get('win_rate', 0.0)} %",
            f"・PF (Profit Factor) : {risk_metrics.get('profit_factor', 0.0)}",
            f"・最大ドローダウン    : {risk_metrics.get('max_drawdown_pct', 0.0)} %",
            f"・シャープレシオ      : {risk_metrics.get('sharpe_ratio', 0.0)}",
            f"・想定最大損失(VaR95%): -{risk_metrics.get('var_95', 0):,.0f}円",
            "",
            "--- 💴 税務関係ユニット (Tax Calculation) ---",
            f"・当年累計実現損益 : {tax_metrics.get('net_realized_pnl', 0):,.0f}円",
            f"・課税対象所得     : {tax_metrics.get('taxable_income', 0):,.0f}円",
            f"・概算見積税額     : {tax_metrics.get('estimated_tax', {}).get('total', 0):,.0f}円",
            f"  └ 内訳 (国税: {tax_metrics.get('estimated_tax', {}).get('national', 0):,.0f}円 / 復興: {tax_metrics.get('estimated_tax', {}).get('reconstruction', 0):,.0f}円 / 住民: {tax_metrics.get('estimated_tax', {}).get('local', 0):,.0f}円)",
            "=========================================="
        ]
        return "\n".join(report)

    def export_csv_ledger(self, trade_history: list, filename: str = "trade_ledger.csv"):
        """確定申告用 取引明細帳のCSV出力 (UTF-8 with BOM)"""
        keys = ["timestamp", "symbol", "side", "amount", "price", "pnl", "fee"]
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for trade in trade_history:
                    row = {k: trade.get(k, "") for k in keys}
                    writer.writerow(row)
        except Exception as e:
            print(f"CSV Export Error: {e}")
