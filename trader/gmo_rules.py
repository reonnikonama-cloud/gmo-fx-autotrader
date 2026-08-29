from typing import Dict, Any

class GMORuleValidator:
    MIN_ORDER_UNIT = 100
    LEVERAGE = 20
    MARGIN_RATIO_REQUIRED = 0.05
    API_FEE_RATE = 0.00002
    LOSSCUT_ALERT_RATIO = 125.0
    LOSSCUT_EXEC_RATIO = 100.0
    LOSSCUT_FEE_PER_UNIT = 0.05

    @classmethod
    def validate_order(cls, symbol: str, amount: float, balance: float, price: float) -> Dict[str, Any]:
        if amount < cls.MIN_ORDER_UNIT or amount % cls.MIN_ORDER_UNIT != 0:
            return {"valid": False, "reason": f"発注単位は{cls.MIN_ORDER_UNIT}通貨刻みです"}
        
        required_margin = amount * price * cls.MARGIN_RATIO_REQUIRED
        fee = amount * price * cls.API_FEE_RATE
        
        if required_margin + fee > balance:
            return {"valid": False, "reason": "必要証拠金および手数料が口座残高を超えています"}
        
        return {"valid": True, "required_margin": required_margin, "fee": fee}
