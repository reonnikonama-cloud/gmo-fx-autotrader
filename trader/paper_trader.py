import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from trader.gmo_rules import GMORuleValidator

JST = timezone(timedelta(hours=9))

class Portfolio:
    def __init__(self, initial_capital: float = 1000000.0):
        self.balance = initial_capital
        self.realized_pnl = 0.0

class PaperTraderTeam:
    def __init__(self, initial_capital: float = 1000000.0):
        self.portfolio = Portfolio(initial_capital)
        self.positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []

    def place_order(self, symbol: str, side: str, amount: float, rates: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        price = rates[symbol]["ask"] if side == "BUY" else rates[symbol]["bid"]
        validation = GMORuleValidator.validate_order(symbol, amount, self.portfolio.balance, price)
        
        if not validation["valid"]:
            return {"status": "REJECTED", "reason": validation["reason"]}

        fee = validation["fee"]
        self.portfolio.balance -= fee

        pos_id = str(uuid.uuid4())[:8]
        position = {
            "id": pos_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "entry_price": price,
            "sl": None,
            "tp": None,
            "timestamp": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        }
        self.positions.append(position)
        return {"status": "ACCEPTED", "id": pos_id, "price": price, "fee": round(fee, 2)}

    def close_position(self, pos_id: Any, exit_price: float) -> Dict[str, Any]:
        """指定したポジションを決済し、損益計算・残高更新・履歴保存を行う"""
        pos_idx: Optional[int] = None
        
        # ID検索（文字列UUID / リストインデックス数値の両方に対応）
        if isinstance(pos_id, int) and 0 <= pos_id < len(self.positions):
            pos_idx = pos_id
        else:
            for idx, p in enumerate(self.positions):
                if str(p.get("id")) == str(pos_id):
                    pos_idx = idx
                    break

        if pos_idx is None:
            return {"status": "NOT_FOUND", "pnl": 0.0}

        pos = self.positions.pop(pos_idx)
        side = pos.get("side", "BUY")
        amount = pos.get("amount", 0.0)
        entry_price = pos.get("price", pos.get("entry_price", exit_price))

        # 確定損益計算 (BUY: (Exit - Entry) * Amount, SELL: (Entry - Exit) * Amount)
        if side == "BUY":
            pnl = (exit_price - entry_price) * amount
        else:
            pnl = (entry_price - exit_price) * amount

        # 口座残高および実現損益の更新
        self.portfolio.balance += pnl
        self.portfolio.realized_pnl += pnl

        # 取引履歴の追加
        trade_record = {
            "id": pos.get("id"),
            "symbol": pos.get("symbol"),
            "side": f"CLOSE_{side}",
            "amount": amount,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "timestamp": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        }
        self.trade_history.append(trade_record)

        return {"status": "CLOSED", "pnl": pnl, "trade_record": trade_record}

    def process_account_health_and_losscut(self, rates: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        total_unrealized_pnl = 0.0
        total_required_margin = 0.0
        total_units = 0.0

        for pos in self.positions:
            sym = pos["symbol"]
            if sym not in rates:
                continue
            current_price = rates[sym]["bid"] if pos["side"] == "BUY" else rates[sym]["ask"]
            pnl = (current_price - pos["price"]) * pos["amount"] if pos["side"] == "BUY" else (pos["price"] - current_price) * pos["amount"]
            total_unrealized_pnl += pnl
            total_required_margin += pos["amount"] * current_price * GMORuleValidator.MARGIN_RATIO_REQUIRED
            total_units += pos["amount"]

        effective_asset = self.portfolio.balance + total_unrealized_pnl
        margin_ratio = (effective_asset / total_required_margin * 100.0) if total_required_margin > 0 else 999.0

        losscut_executed = False
        losscut_loss = 0.0
        losscut_fee = 0.0

        if margin_ratio < GMORuleValidator.LOSSCUT_EXEC_RATIO and self.positions:
            losscut_executed = True
            losscut_fee = total_units * GMORuleValidator.LOSSCUT_FEE_PER_UNIT
            losscut_loss = total_unrealized_pnl
            net_loss = total_unrealized_pnl - losscut_fee

            self.portfolio.balance += net_loss
            self.portfolio.realized_pnl += net_loss

            self.trade_history.append({
                "symbol": "ALL",
                "side": "LOSSCUT",
                "amount": total_units,
                "pnl": net_loss,
                "timestamp": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            })

            self.positions.clear()
            margin_ratio = 0.0

        return {
            "status": "HEALTHY" if margin_ratio >= GMORuleValidator.LOSSCUT_ALERT_RATIO else "WARNING",
            "margin_ratio": round(margin_ratio, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 1),
            "losscut_executed": losscut_executed,
            "realized_pnl_loss": round(losscut_loss, 1),
            "total_losscut_fee": round(losscut_fee, 1)
        }

    def generate_daily_report(self, date_str: str) -> Dict[str, Any]:
        total_trades = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t.get("pnl", 0) > 0)
        win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

        return {
            "date": date_str,
            "balance": round(self.portfolio.balance, 1),
            "ending_balance": round(self.portfolio.balance, 1),
            "realized_pnl": round(self.portfolio.realized_pnl, 1),
            "trades_count": total_trades,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1)
        }
