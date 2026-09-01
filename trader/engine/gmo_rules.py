from typing import Dict, Any

class GMORuleValidator:
    MIN_ORDER_UNIT = 1000          # 国内FX最小発注単位 (1,000通貨)
    LEVERAGE = 25.0                # 個人口座上限レバレッジ
    MARGIN_RATIO_REQUIRED = 0.04   # 必要証拠金率 (1 / 25.0)
    API_FEE_RATE = 0.00002
    LOSSCUT_ALERT_RATIO = 100.0
    LOSSCUT_EXEC_RATIO = 50.0

    @classmethod
    def validate_order(cls, symbol: str, amount: float, balance: float, price: float) -> Dict[str, Any]:
        if amount < cls.MIN_ORDER_UNIT or amount % cls.MIN_ORDER_UNIT != 0:
            return {"valid": False, "reason": f"発注単位は{cls.MIN_ORDER_UNIT:,}通貨刻みです"}
        
        required_margin = amount * price * cls.MARGIN_RATIO_REQUIRED
        fee = amount * price * cls.API_FEE_RATE
        
        if required_margin + fee > balance:
            return {"valid": False, "reason": f"必要証拠金・手数料オーバー (必要: {required_margin + fee:,.0f}円 / 残高: {balance:,.0f}円)"}
        
        return {"valid": True, "required_margin": required_margin, "fee": fee}
