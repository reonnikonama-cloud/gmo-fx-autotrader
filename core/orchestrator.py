import time
import traceback
import threading
from datetime import datetime, timezone, timedelta

from config.settings import GEMINI_API_KEY, DISCORD_WEBHOOK_URL, ALLOWED_SYMBOLS, INITIAL_CAPITAL, RISK_RATIO
from trader.gmo_fx_engine import GMOFXEngine
from trader.strategy import BasicStrategy
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.risk_analyzer import RiskAnalyzer
from analyzer.notifier import DiscordNotifier
from analyzer.optimizer import StrategyOptimizer
from fetcher.gmo_fx import GmoFxFetcher
from accounting.tax_calculator import TaxCalculator
from reporter.report_generator import PerformanceReporter
from reporter.daily_batch import DailyBatchProcessor
from utils.logger import logger

JST = timezone(timedelta(hours=9))

class SystemOrchestrator:
    """GMOコイン FX 実データ専用 統合管理エンジン"""

    def __init__(self):
        self.trader = GMOFXEngine(initial_capital=INITIAL_CAPITAL)
        self.strategy = BasicStrategy(short_window=5, long_window=20, rsi_window=14, atr_window=14)
        self.market_analyzer = MarketAnalyzer(api_key=GEMINI_API_KEY)
        self.risk_analyzer = RiskAnalyzer()
        self.tax_calculator = TaxCalculator()
        self.reporter = PerformanceReporter()
        self.notifier = DiscordNotifier(webhook_url=DISCORD_WEBHOOK_URL)
        self.gmo_fetcher = GmoFxFetcher()
        self.optimizer = StrategyOptimizer(initial_capital=INITIAL_CAPITAL)
        
        self.daily_batch_processor = DailyBatchProcessor(notifier=self.notifier)

        self.rates_cache = {}
        self.cache_lock = threading.Lock()
        
        self.start_time = time.time()
        self.last_signal_check_time = 0.0
        self.signal_check_interval = 60.0
        self.last_heartbeat_time = time.time()
        self.heartbeat_interval = 21600.0  # 6時間

    def run_loop(self):
        logger.info("==========================================")
        logger.info(" GMOコイン FX 自動トレードシステム起動")
        logger.info(f" 初期資金: {INITIAL_CAPITAL:,.0f}円 | レバレッジ: 25倍")
        logger.info("==========================================")

        while True:
            try:
                now_time = time.time()
                now_jst = datetime.now(JST)

                # 最新のレートをREST APIから取得（またはWebSocketキャッシュ）
                fetched = self.gmo_fetcher.fetch_ticker()
                if fetched:
                    with self.cache_lock:
                        self.rates_cache.update(fetched)

                with self.cache_lock:
                    current_rates = self.rates_cache.copy()

                # ① リアルタイム SL/TP 決済監視 ＆ 証拠金維持率監視
                if current_rates:
                    self._process_realtime_sl_tp(current_rates)
                    health = self.trader.check_account_health_and_losscut(current_rates)
                    if health.get("losscut_executed"):
                        self.notifier.notify_system_error("【警告】証拠金維持率低下によりロスカットが実行されました。")

                # ② テクニカル分析 ＆ シグナル評価 (1分周期)
                if now_time - self.last_signal_check_time >= self.signal_check_interval:
                    self.last_signal_check_time = now_time
                    self._process_signal_evaluation(now_jst, current_rates)

                # ③ 定期的ハートビート通知
                if now_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    self.last_heartbeat_time = now_time
                    self._send_heartbeat()

                # ④ 日次バッチ実行（JST 06:00切り替え）
                self.daily_batch_processor.run_daily_batch_if_needed(self._fetch_daily_stats_and_optimize)

                time.sleep(1)

            except Exception as e:
                err_trace = traceback.format_exc()
                logger.critical(f"【メインループエラー】: {e}\n{err_trace}")
                self.notifier.notify_system_error(err_trace)
                time.sleep(10)

    def _process_realtime_sl_tp(self, current_rates: dict):
        """ポジションごとのSL/TP判定"""
        for pos_id, pos in list(self.trader.positions.items()):
            sym = pos.get("symbol")
            if not sym or sym not in current_rates:
                continue

            bid, ask = current_rates[sym]["bid"], current_rates[sym]["ask"]
            curr_price = bid if pos["side"] == "BUY" else ask

            sl, tp = pos.get("sl"), pos.get("tp")
            close_reason = None

            if pos["side"] == "BUY":
                if sl and curr_price <= sl:
                    close_reason = f"SL到達 ({curr_price:.3f} <= {sl:.3f})"
                elif tp and curr_price >= tp:
                    close_reason = f"TP到達 ({curr_price:.3f} >= {tp:.3f})"
            elif pos["side"] == "SELL":
                if sl and curr_price >= sl:
                    close_reason = f"SL到達 ({curr_price:.3f} >= {sl:.3f})"
                elif tp and curr_price <= tp:
                    close_reason = f"TP到達 ({curr_price:.3f} <= {tp:.3f})"

            if close_reason:
                res = self.trader.close_position(pos_id, curr_price, reason=close_reason)
                logger.info(f"【自動決済】[{sym}] {pos['side']} | 理由: {close_reason} | 損益: {res['pnl']:,.0f}円")
                self.notifier.notify_trade_executed({
                    "symbol": sym, "side": f"CLOSE_{pos['side']}", "amount": pos["amount"],
                    "price": curr_price, "fee": 0, "pnl": res["pnl"]
                })

    def _process_signal_evaluation(self, now_jst: datetime, current_rates: dict):
        """シグナル評価および新規注文発行"""
        for symbol in ALLOWED_SYMBOLS:
            if symbol not in current_rates:
                continue

            # GMOコインAPIから実ローソク足データを取得
            df_candles = self.gmo_fetcher.fetch_klines(symbol, interval="15min")
            
            # 休場中やデータ取得失敗時はスキップ（疑似データ生成は行わない）
            if df_candles.empty or len(df_candles) < 20:
                continue

            analysis = self.strategy.generate_signal(df_candles)
            sig, atr = analysis["signal"], analysis.get("atr", 0.10)

            if sig in ["BUY", "SELL"]:
                amount = self.strategy.calculate_position_size(
                    self.trader.balance, 
                    current_rates[symbol]["ask"] if sig == "BUY" else current_rates[symbol]["bid"], 
                    RISK_RATIO, atr
                )
                
                order_res = self.trader.place_order(symbol, sig, amount, current_rates)
                
                if order_res.get("status") == "ACCEPTED":
                    new_pos_id = order_res["id"]
                    # SL/TPの設定
                    if new_pos_id in self.trader.positions:
                        self.trader.positions[new_pos_id]["sl"] = analysis.get("sl_price")
                        self.trader.positions[new_pos_id]["tp"] = analysis.get("tp_price")

                    logger.info(f"【約定成功】{symbol} {sig} {amount:,}通貨 (価格: {order_res['price']:.3f})")
                    self.notifier.notify_trade_executed({
                        "symbol": symbol, "side": sig, "amount": amount,
                        "price": order_res["price"], "fee": 0,
                        "sl": analysis.get('sl_price'), "tp": analysis.get('tp_price')
                    })

    def _fetch_daily_stats_and_optimize(self, target_date: str) -> dict:
        daily_summary = self.trader.generate_daily_report(target_date)
        self.reporter.export_csv_ledger(self.trader.trade_history, f"trade_ledger_{target_date}.csv")
        return daily_summary

    def _send_heartbeat(self):
        uptime_seconds = int(time.time() - self.start_time)
        status_info = {
            "uptime": f"{uptime_seconds // 3600}時間{(uptime_seconds % 3600) // 60}分",
            "balance": self.trader.balance,
            "open_positions": len(self.trader.positions),
            "params": self.strategy.get_parameters(),
            "cb_triggered": self.strategy.circuit_breaker_triggered
        }
        self.notifier.notify_heartbeat(status_info)
