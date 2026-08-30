import logging
from datetime import datetime, timezone, timedelta
from analyzer.notifier import DiscordNotifier

class DailyBatchProcessor:
    def __init__(self, notifier: DiscordNotifier):
        self.notifier = notifier
        self.last_processed_date = None

    @staticmethod
    def get_trading_day(dt: datetime = None) -> str:
        """JST 06:00切り替えの取引日（YYYY-MM-DD）を取得"""
        jst = timezone(timedelta(hours=9))
        if dt is None:
            dt = datetime.now(jst)
        else:
            dt = dt.astimezone(jst)

        if dt.hour < 6:
            dt -= timedelta(days=1)

        return dt.strftime("%Y-%m-%d")

    def run_daily_batch_if_needed(self, fetch_daily_stats_func) -> bool:
        current_trading_day = self.get_trading_day()

        if self.last_processed_date == current_trading_day:
            return False

        if self.last_processed_date is not None and self.last_processed_date != current_trading_day:
            logging.info(f"【日次バッチ起動】取引日切り替え: {self.last_processed_date} -> {current_trading_day}")
            
            stats = fetch_daily_stats_func(self.last_processed_date)
            self._send_daily_report(self.last_processed_date, stats)
            self.last_processed_date = current_trading_day
            return True

        self.last_processed_date = current_trading_day
        return False

    def _send_daily_report(self, target_date: str, stats: dict):
        pnl = stats.get("realized_pnl", 0.0)
        color = 3066993 if pnl >= 0 else 15158332
        pnl_sign = "+" if pnl > 0 else ""

        fields = [
            {"name": "日次実現損益", "value": f"**{pnl_sign}{pnl:,.0f} 円**", "inline": True},
            {"name": "取引件数", "value": f"{stats.get('trades_count', 0)} 件", "inline": True},
            {"name": "勝率", "value": f"{stats.get('win_rate', 0.0):.1f} %", "inline": True},
            {"name": "口座残高（FX余力）", "value": f"{stats.get('ending_balance', 0.0):,.0f} 円", "inline": False},
        ]

        self.notifier.send_embed(
            title=f"📊 日次取引レポート [{target_date}]",
            description=f"取引日 `{target_date}`（JST 06:00〜翌06:00）の集計が完了しました。",
            fields=fields,
            color=color
        )
