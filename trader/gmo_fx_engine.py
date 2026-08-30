import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from utils.logger import logger

JST = timezone(timedelta(hours=9))

class GMOFXEngine:
    """GMOコイン 外国為替(FX) 実相場準拠 模擬・取引執行エンジン"""

    LEVERAGE = 25.0                       # 個人口座レバレッジ上限 (25倍)
    MARGIN_REQUIREMENT_RATE = 1.0 / 25.0  # 必要証拠金率 (4%)
    LOSSCUT_THRESHOLD = 50.0              # 証拠金維持率50%未満でロスカット
    ALERT_THRESHOLD = 100.0             # 証拠金維持率100%未満でアラート

    def __init__(self, initial_capital: float = 1_000_000.0):
        self.balance: float = initial_capital
        self.realized_pnl: float = 0.0
        # ポジション管理: { pos_id: position_dict }
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []

    def place_order(self, symbol: str, side: str, amount: float, rates: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """新規注文の発行と必要証拠金チェック"""
        if symbol not in rates:
            return {"status": "REJECTED", "reason": f"{symbol} のレート情報が存在しません"}

        # BUYはAsk(買値)、SELLはBid(売値)で約定
        price = rates[symbol]["ask"] if side == "BUY" else rates[symbol]["bid"]
        
        # 必要証拠金計算 (レバレッジ25倍)
        required_margin = (price * amount) * self.MARGIN_REQUIREMENT_RATE
        
        # 余力チェック（口座残高 < 必要証拠金の場合は注文拒否）
        if self.balance < required_margin:
            return {
                "status": "REJECTED", 
                "reason": f"証拠金不足 (必要: {required_margin:,.0f}円 / 残高: {self.balance:,.0f}円)"
            }

        pos_id = f"FX_{uuid.uuid4().hex[:8]}"
        position = {
            "id": pos_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "entry_price": price,
            "required_margin": required_margin,
            "sl": None,
            "tp": None,
            "opened_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.positions[pos_id] = position
        return {"status": "ACCEPTED", "id": pos_id, "price": price, "required_margin": required_margin}

    def close_position(self, pos_id: str, exit_price: float, reason: str = "SIGNAL") -> Dict[str, Any]:
        """指定したポジションの決済処理"""
        pos = self.positions.pop(pos_id, None)
        if not pos:
            return {"status": "NOT_FOUND", "pnl": 0.0}

        side = pos["side"]
        amount = pos["amount"]
        entry_price = pos["entry_price"]

        # 損益計算 (BUY: (Exit - Entry) * Amount, SELL: (Entry - Exit) * Amount)
        pnl = (exit_price - entry_price) * amount if side == "BUY" else (entry_price - exit_price) * amount

        # 口座情報の更新
        self.balance += pnl
        self.realized_pnl += pnl

        trade_record = {
            "id": pos["id"],
            "symbol": pos["symbol"],
            "side": f"CLOSE_{side}",
            "amount": amount,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "reason": reason,
            "closed_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        }
        self.trade_history.append(trade_record)

        return {"status": "CLOSED", "pnl": pnl, "trade_record": trade_record}

    def check_account_health_and_losscut(self, rates: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """リアルタイム維持率計算およびロスカット判定"""
        total_unrealized_pnl = 0.0
        total_required_margin = 0.0

        for pos_id, pos in list(self.positions.items()):
            sym = pos["symbol"]
            if sym not in rates:
                continue

            # 評価価格 (BUY保持時はBidで評価, SELL保持時はAskで評価)
            current_price = rates[sym]["bid"] if pos["side"] == "BUY" else rates[sym]["ask"]
            pnl = (current_price - pos["entry_price"]) * pos["amount"] if pos["side"] == "BUY" else (pos["entry_price"] - current_price) * pos["amount"]
            
            total_unrealized_pnl += pnl
            total_required_margin += (current_price * pos["amount"]) * self.MARGIN_REQUIREMENT_RATE

        # 有効保有資産 (純資産)
        effective_assets = self.balance + total_unrealized_pnl
        
        # 証拠金維持率 (%)
        margin_ratio = (effective_assets / total_required_margin * 100.0) if total_required_margin > 0 else 999.0

        losscut_executed = False

        # ロスカット判定 (維持率 50% 未満)
        if margin_ratio < self.LOSSCUT_THRESHOLD and self.positions:
            logger.critical(f"【ロスカット発動】維持率 {margin_ratio:.2f}% が下限（50%）を下回りました。全ポジション強制成行決済を実行します。")
            losscut_executed = True

            for pos_id, pos in list(self.positions.items()):
                sym = pos["symbol"]
                exit_price = rates[sym]["bid"] if pos["side"] == "BUY" else rates[sym]["ask"] if sym in rates else pos["entry_price"]
                self.close_position(pos_id, exit_price, reason="LOSSCUT")

            margin_ratio = 0.0

        return {
            "status": "HEALTHY" if margin_ratio >= self.ALERT_THRESHOLD else "WARNING",
            "margin_ratio": round(margin_ratio, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 1),
            "effective_assets": round(effective_assets, 1),
            "total_required_margin": round(total_required_margin, 1),
            "losscut_executed": losscut_executed
        }

    def generate_daily_report(self, date_str: str) -> Dict[str, Any]:
        """指定日の損益・勝率集計 (日付一致のみ抽出)"""
        daily_trades = [t for t in self.trade_history if t.get("closed_at", "").startswith(date_str)]
        
        total_trades = len(daily_trades)
        wins = sum(1 for t in daily_trades if t.get("pnl", 0) > 0)
        daily_realized_pnl = sum(t.get("pnl", 0) for t in daily_trades)
        win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

        return {
            "date": date_str,
            "balance": round(self.balance, 1),
            "realized_pnl": round(daily_realized_pnl, 1),
            "trades_count": total_trades,
            "win_rate": round(win_rate, 1)
        }
