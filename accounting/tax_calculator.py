# accounting/tax_calculator.py
from datetime import datetime

class TaxCalculator:
    """
    税務関係ユニット
    日本の店頭FX（申告分離課税 20.315%）に準拠
    - 所得税: 15%
    - 復興特別所得税: 0.315% (所得税額の2.1%)
    - 住民税: 5%
    """
    TAX_RATE_NATIONAL = 0.15
    TAX_RATE_RECONSTRUCTION = 0.00315
    TAX_RATE_LOCAL = 0.05

    def calculate_annual_tax(self, trade_history: list, target_year: int = None) -> dict:
        if target_year is None:
            target_year = datetime.now().year

        year_pnls = []
        for t in trade_history:
            close_time = t.get("timestamp") or t.get("close_time")
            if close_time:
                try:
                    if datetime.strptime(close_time[:10], "%Y-%m-%d").year == target_year:
                        year_pnls.append(t.get("pnl", 0.0))
                except ValueError:
                    pass

        gross_profit = sum([p for p in year_pnls if p > 0])
        gross_loss = sum([p for p in year_pnls if p < 0])
        net_realized_pnl = gross_profit + gross_loss  # 差引実現損益

        # 課税所得金額（損失の場合は0円）
        taxable_income = max(0.0, net_realized_pnl)

        national_tax = round(taxable_income * self.TAX_RATE_NATIONAL)
        reconstruction_tax = round(taxable_income * self.TAX_RATE_RECONSTRUCTION)
        local_tax = round(taxable_income * self.TAX_RATE_LOCAL)
        total_tax = national_tax + reconstruction_tax + local_tax

        return {
            "year": target_year,
            "net_realized_pnl": round(net_realized_pnl, 0),
            "gross_profit": round(gross_profit, 0),
            "gross_loss": round(gross_loss, 0),
            "taxable_income": round(taxable_income, 0),
            "estimated_tax": {
                "national": national_tax,
                "reconstruction": reconstruction_tax,
                "local": local_tax,
                "total": total_tax
            }
        }
