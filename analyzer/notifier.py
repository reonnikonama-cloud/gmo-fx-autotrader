# analyzer/notifier.py
import requests
import json
from utils.logger import logger

class WebhookNotifier:
    """Discord Webhookを使用した各種通知モジュール（死活監視・ハートビート対応版）"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_message(self, content: str) -> bool:
        if not self.webhook_url or self.webhook_url.startswith("YOUR_"):
            logger.warning("Discord Webhook URLが未設定のため通知をスキップしました。")
            return False

        try:
            payload = {"content": content}
            headers = {"Content-Type": "application/json"}
            res = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            if res.status_code in [200, 204]:
                return True
            else:
                logger.error(f"Discord通知失敗: Status {res.status_code}, Response: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Discord Webhook送信エラー: {e}")
            return False

    def notify_trade_executed(self, trade_info: dict):
        side_emoji = "🟢" if "BUY" in trade_info["side"] else "🔴" if "SELL" in trade_info["side"] else "⚪"
        msg = (
            f"{side_emoji} **【約定通知】** [{trade_info['symbol']}]\n"
            f"・種別: {trade_info['side']}\n"
            f"・数量: {trade_info['amount']:,} 通貨\n"
            f"・価格: {trade_info['price']:.3f}\n"
        )
        if "sl" in trade_info and trade_info["sl"]:
            msg += f"・SL (損切): {trade_info['sl']:.3f}\n"
        if "tp" in trade_info and trade_info["tp"]:
            msg += f"・TP (利確): {trade_info['tp']:.3f}\n"
        if "pnl" in trade_info:
            pnl_emoji = "🎉" if trade_info["pnl"] >= 0 else "💸"
            msg += f"・確定損益: {pnl_emoji} {trade_info['pnl']:,.0f} 円\n"

        self.send_message(msg)

    def notify_daily_report(self, summary: dict, report_text: str):
        msg = f"📊 **【日次サマリー報告】**\n{report_text}"
        self.send_message(msg)

    def notify_heartbeat(self, status_info: dict):
        """定期的（6時間ごと）なシステム生死確認（ハートビート）通知"""
        msg = (
            f"💓 **【システム死活監視 - ハートビート】**\n"
            f"・ステータス: 🟢 正常稼働中 (Active)\n"
            f"・通算稼働時間: {status_info.get('uptime', 'N/A')}\n"
            f"・現在口座残高: {status_info.get('balance', 0):,.0f} 円\n"
            f"・保有ポジション数: {status_info.get('open_positions', 0)} 件\n"
            f"・適用中パラメータ: `{status_info.get('params', {})}`\n"
            f"・サーキットブレーカー: {'🔴 発動中' if status_info.get('cb_triggered') else '🟢 正常'}\n"
        )
        self.send_message(msg)

    def notify_system_error(self, error_msg: str):
        """緊急事態・未捕捉エラー発生時の即時通知"""
        msg = (
            f"🚨 **【緊急アラート】システム異常・未捕捉例外発生**\n"
            f"```\n{error_msg[:1800]}\n```\n"
            f"※ 詳細はサーバー内のログファイル `logs/app.log` を確認してください。"
        )
        self.send_message(msg)
