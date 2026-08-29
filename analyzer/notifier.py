import os
import requests
from typing import Dict, Any, Optional

class WebhookNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    def send_notification(self, title: str, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        content = f"**{title}**\n{message}"
        if data:
            content += f"\n```json\n{data}\n```"

        if not self.webhook_url:
            print(f"[Notifier LOG] Webhook未設定のためコンソール表示:\n{content}")
            return False

        try:
            response = requests.post(self.webhook_url, json={"content": content})
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"[Notifier ERROR] 送信失敗: {e}")
            return False

    def notify_trade_executed(self, trade_info: Dict[str, Any]) -> bool:
        symbol = trade_info.get("symbol", "N/A")
        side = trade_info.get("side", "N/A")
        amount = trade_info.get("amount", 0)
        price = trade_info.get("price", 0)
        fee = trade_info.get("fee", 0)

        title = f"【約定通知】{symbol} {side}"
        message = (
            f"- 通貨ペア: {symbol}\n"
            f"- 売買: {side}\n"
            f"- 数量: {amount:,.1f} 通貨\n"
            f"- 約定価格: {price}\n"
            f"- 手数料: {fee}円"
        )
        return self.send_notification(title, message, data=trade_info)

    def notify_losscut(self, result_info: Dict[str, Any]) -> bool:
        title = "【緊急警告】強制ロスカットが執行されました"
        message = (
            f"- 維持率: {result_info.get('margin_ratio', 0):.2f}%\n"
            f"- 確定損失: {result_info.get('realized_pnl_loss', 0):,} 円\n"
            f"- 発生手数料: {result_info.get('total_losscut_fee', 0):,} 円"
        )
        return self.send_notification(title, message, data=result_info)

    def notify_daily_report(self, daily_summary: Dict[str, Any], ai_analysis: str) -> bool:
        title = f"📊 【日次報告】{daily_summary.get('date', '')} トレード＆AI市場分析"
        message = (
            f"**口座残高**: {daily_summary.get('balance', 0):,} 円\n"
            f"**本日損益**: {daily_summary.get('realized_pnl', 0):+,} 円\n"
            f"**勝率**: {daily_summary.get('win_rate', 0)}%\n\n"
            f"--- **AI分析要約** ---\n{ai_analysis}"
        )
        return self.send_notification(title, message, data=daily_summary)
