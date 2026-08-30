import time
import json
import requests
from utils.logger import logger

class WebhookNotifier:
    """Discord Webhookを使用した各種通知モジュール（Embed対応・リトライ・レート制限制御）"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _post_payload(self, payload: dict) -> bool:
        if not self.webhook_url or self.webhook_url.startswith("YOUR_"):
            logger.warning("Discord Webhook URLが未設定のため通知をスキップしました。")
            return False

        headers = {"Content-Type": "application/json"}

        for attempt in range(3):
            try:
                res = requests.post(
                    self.webhook_url,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=10
                )
                if res.status_code in [200, 204]:
                    return True
                elif res.status_code == 429:
                    retry_after = res.json().get("retry_after", 2000) / 1000.0
                    logger.warning(f"Discord Webhook レート制限適用中。{retry_after:.1f}秒待機します...")
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"Discord通知失敗: Status {res.status_code}, Response: {res.text}")
                    return False
            except Exception as e:
                logger.error(f"Discord Webhook送信エラー (試行 {attempt + 1}/3): {e}")
                time.sleep(2)
        return False

    def send_message(self, content: str) -> bool:
        return self._post_payload({"content": content})

    def send_embed(self, title: str, description: str, fields: list, color: int = 3066993) -> bool:
        """DailyBatchProcessor 用の Embed 形式通知"""
        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "fields": fields,
                    "color": color
                }
            ]
        }
        return self._post_payload(payload)

    def notify_trade_executed(self, trade_info: dict):
        side = trade_info.get("side", "")
        side_emoji = "🟢" if "BUY" in side else "🔴" if "SELL" in side else "⚪"
        
        msg = (
            f"{side_emoji} **【約定通知】** [{trade_info.get('symbol', 'UNKNOWN')}]\n"
            f"・種別: {side}\n"
            f"・数量: {trade_info.get('amount', 0):,} 通貨\n"
            f"・価格: {trade_info.get('price', 0.0):.3f}\n"
        )
        if trade_info.get("sl"):
            msg += f"・SL (損切): {trade_info['sl']:.3f}\n"
        if trade_info.get("tp"):
            msg += f"・TP (利確): {trade_info['tp']:.3f}\n"
        if "pnl" in trade_info:
            pnl = trade_info["pnl"]
            pnl_emoji = "🎉" if pnl >= 0 else "💸"
            msg += f"・確定損益: {pnl_emoji} {pnl:,.0f} 円\n"

        self.send_message(msg)

    def notify_daily_report(self, summary: dict, report_text: str):
        msg = f"📊 **【日次サマリー報告】**\n{report_text}"
        self.send_message(msg)

    def notify_heartbeat(self, status_info: dict):
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
        msg = (
            f"🚨 **【緊急アラート】システム異常・未捕捉例外発生**\n"
            f"```\n{error_msg[:1800]}\n```\n"
            f"※ 詳細はサーバー内のログファイル `logs/app.log` を確認してください。"
        )
        self.send_message(msg)

# クラス名のエイリアスを設定（既存と新規の呼び出し差異を吸収）
DiscordNotifier = WebhookNotifier
