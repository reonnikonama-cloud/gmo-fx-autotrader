import time
import json
import traceback
import threading
from datetime import datetime, timezone, timedelta
import pandas as pd

from config.settings import GEMINI_API_KEY, DISCORD_WEBHOOK_URL, ALLOWED_SYMBOLS, INITIAL_CAPITAL, RISK_RATIO
from trader.paper_trader import PaperTraderTeam
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

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

JST = timezone(timedelta(hours=9))

def generate_fallback_candle_data(base_price: float, count: int = 30) -> pd.DataFrame:
    import random
    now = datetime.now(JST)
    data = []
    current = base_price
    for i in range(count):
        dt = now - timedelta(minutes=(count - i) * 15)
        change = random.uniform(-0.15, 0.15)
        open_p = current
        close_p = open_p + change
        high_p = max(open_p, close_p) + random.uniform(0.01, 0.05)
        low_p = min(open_p, close_p) - random.uniform(0.01, 0.05)
        current = close_p
        data.append({
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": round(open_p, 3),
            "high": round(high_p, 3),
            "low": round(low_p, 3),
            "close": round(close_p, 3)
        })
    return pd.DataFrame(data)

class SystemOrchestrator:
    """システム全体を統合統括する核エンジン（JST 06:00 取引日バッチ統合版）"""

    def __init__(self):
        self.trader = PaperTraderTeam(initial_capital=INITIAL_CAPITAL)
        self.strategy = BasicStrategy(short_window=5, long_window=20, rsi_window=14, atr_window=14)
        self.market_analyzer = MarketAnalyzer(api_key=GEMINI_API_KEY)
        self.risk_analyzer = RiskAnalyzer()
        self.tax_calculator = TaxCalculator()
        self.reporter = PerformanceReporter()
        self.notifier = DiscordNotifier(webhook_url=DISCORD_WEBHOOK_URL)
        self.gmo_fetcher = GmoFxFetcher()
        self.optimizer = StrategyOptimizer(initial_capital=INITIAL_CAPITAL)
        
        # 新規コンポーネント: JST 06:00 切り替え用日次バッチプロセッサ
        self.daily_batch_processor = DailyBatchProcessor(notifier=self.notifier)

        self.rates_cache = {
            "USD_JPY": {"bid": 155.500, "ask": 155.515},
            "EUR_JPY": {"bid": 168.200, "ask": 168.215},
            "GBP_JPY": {"bid": 198.800, "ask": 198.818},
            "AUD_JPY": {"bid": 102.300, "ask": 102.315},
            "NZD_JPY": {"bid": 94.100, "ask": 94.115}
        }
        self.cache_lock = threading.Lock()
        
        self.start_time = time.time()
        self.last_signal_check_time = 0.0
        self.signal_check_interval = 60.0
        self.last_heartbeat_time = time.time()
        self.heartbeat_interval = 21600.0  # 6時間

    def start_websocket(self):
        if not HAS_WEBSOCKET:
            logger.warning("websocket-client ライブラリ未導入のため HTTP ポーリングにフォールバックします。")
            return

        ws_url = "wss://forex-api.coin.z.com/ws/public/v1"

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("channel") == "ticker":
                    symbol = data.get("symbol")
                    bid = float(data.get("bid", 0))
                    ask = float(data.get("ask", 0))
                    if symbol in ALLOWED_SYMBOLS and bid > 0 and ask > 0:
                        with self.cache_lock:
                            self.rates_cache[symbol] = {"bid": bid, "ask": ask, "timestamp": data.get("timestamp")}
            except Exception as e:
                logger.error(f"WebSocketメッセージ処理エラー: {e}")

        def on_open(ws):
            logger.info("WebSocket接続確立。購読リクエスト送信開始...")
            for sym in ALLOWED_SYMBOLS:
                sub_msg = {"command": "subscribe", "channel": "ticker", "symbol": sym}
                ws.send(json.dumps(sub_msg))

        def on_error(ws, e):
            logger.error(f"WebSocketエラー: {e}")

        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"WebSocket切断検出 ({close_status_code}: {close_msg})。")

        while True:
            try:
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                ws.run_forever()
            except Exception as e:
                logger.error(f"WebSocketループ例外発生: {e}")
            
            logger.info("5秒後にWebSocket再接続を試みます...")
            time.sleep(5)

    def run_loop(self):
        logger.info("==========================================")
        logger.info(f" GMOコイン FX 自動トレードシステム起動")
        logger.info(f" 初期資金: {INITIAL_CAPITAL:,.0f}円 | 1トレードリスク比率: {RISK_RATIO*100:.1f}%")
        logger.info("==========================================")

        threading.Thread(target=self.start_websocket, daemon=True).start()

        while True:
            try:
                now_time = time.time()
                now_jst = datetime.now(JST)

                with self.cache_lock:
                    current_rates = self.rates_cache.copy()

                if not HAS_WEBSOCKET or not current_rates:
                    fetched = self.gmo_fetcher.fetch_ticker()
                    if fetched:
                        current_rates.update(fetched)

                # ① リアルタイム SL/TP 決済監視
                self._process_realtime_sl_tp(current_rates)

                # ② テクニカル分析 ＆ シグナル評価 (1分周期)
                if now_time - self.last_signal_check_time >= self.signal_check_interval:
                    self.last_signal_check_time = now_time
                    self._process_signal_evaluation(now_jst, current_rates)

                # ③ 定期的ハートビート通知 (6時間周期)
                if now_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    self.last_heartbeat_time = now_time
                    self._send_heartbeat()

                # ④ 日次バッチ実行（JST 06:00切り替え判定）
                self.daily_batch_processor.run_daily_batch_if_needed(self._fetch_daily_stats_and_optimize)

                time.sleep(1)

            except Exception as e:
                err_trace = traceback.format_exc()
                logger.critical(f"【メインループ致命的エラー】: {e}\n{err_trace}")
                self.notifier.notify_system_error(err_trace)
                time.sleep(10)

    def _fetch_daily_stats_and_optimize(self, target_date: str) -> dict:
        """DailyBatchProcessorから呼び出されるデータ抽出・パラメータ最適化処理"""
        logger.info("==========================================")
        logger.info(f" 日次バッチ処理 ＆ 戦略最適化実行 [対象取引日: {target_date}]")
        logger.info("==========================================")

        # 1. バックテスト＆パラメータ最適化
        historical_data = {}
        for symbol in ALLOWED_SYMBOLS:
            df = self.gmo_fetcher.fetch_klines(symbol, interval="15min")
            if df.empty or len(df) < 20:
                base_price = self.rates_cache.get(symbol, {}).get("bid", 150.0)
                df = generate_fallback_candle_data(base_price=base_price, count=50)
            historical_data[symbol] = df

        if historical_data:
            current_p = self.strategy.get_parameters()
            best_p = self.optimizer.optimize_parameters(historical_data, current_p)
            self.strategy.update_parameters(best_p)

        # 2. 取引集計＆元帳CSV出力
        daily_summary = self.trader.generate_daily_report(target_date)
        self.reporter.export_csv_ledger(self.trader.trade_history, f"trade_ledger_{target_date}.csv")

        # DailyBatchProcessor へ返却する辞書データ
        return {
            "realized_pnl": daily_summary.get("realized_pnl", 0.0),
            "trades_count": daily_summary.get("trades_count", 0),
            "win_rate": daily_summary.get("win_rate", 0.0),
            "ending_balance": self.trader.portfolio.balance
        }

    def _send_heartbeat(self):
        uptime_seconds = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}時間{minutes}分{seconds}秒"

        open_positions_count = len(self.trader.positions) if hasattr(self.trader.positions, "__len__") else 0

        status_info = {
            "uptime": uptime_str,
            "balance": self.trader.portfolio.balance,
            "open_positions": open_positions_count,
            "params": self.strategy.get_parameters(),
            "cb_triggered": self.strategy.circuit_breaker_triggered
        }
        logger.info(f"【死活監視】ハートビート通知を送信します。稼働時間: {uptime_str}")
        self.notifier.notify_heartbeat(status_info)

    def _get_position_iterator(self):
        positions = self.trader.positions
        if isinstance(positions, dict):
            return list(positions.items())
        elif isinstance(positions, list):
            return list(enumerate(positions))
        return []

    def _process_realtime_sl_tp(self, current_rates: dict):
        for pos_id, pos in self._get_position_iterator():
            sym = pos.get("symbol")
            if not sym or sym not in current_rates:
                continue

            bid, ask = current_rates[sym]["bid"], current_rates[sym]["ask"]
            curr_price = bid if pos["side"] == "BUY" else ask

            sl, tp = pos.get("sl"), pos.get("tp")
            close_reason = None

            if pos["side"] == "BUY":
                if sl and curr_price <= sl:
                    close_reason = f"SL到達 ({curr_price:.3f} <= {sl})"
                elif tp and curr_price >= tp:
                    close_reason = f"TP到達 ({curr_price:.3f} >= {tp})"
            elif pos["side"] == "SELL":
                if sl and curr_price >= sl:
                    close_reason = f"SL到達 ({curr_price:.3f} >= {sl})"
                elif tp and curr_price <= tp:
                    close_reason = f"TP到達 ({curr_price:.3f} <= {tp})"

            if close_reason:
                res = self.trader.close_position(pos_id, curr_price)
                logger.info(f"【自動決済】[{sym}] {pos['side']} | 理由: {close_reason} | 損益: {res['pnl']:,.0f}円")
                self.notifier.notify_trade_executed({
                    "symbol": sym, "side": f"CLOSE_{pos['side']}", "amount": pos["amount"],
                    "price": curr_price, "fee": 0, "pnl": res["pnl"]
                })

    def _process_signal_evaluation(self, now_jst: datetime, current_rates: dict):
        logger.info(f"--- レート更新 & シグナル評価 ({now_jst.strftime('%H:%M:%S')}) ---")

        if self.strategy.check_circuit_breaker(self.trader.portfolio.balance):
            logger.warning("【サーキットブレーカー発動中】日次許容損失上限（5%）到達のため新規注文停止中")

        for symbol in ALLOWED_SYMBOLS:
            if symbol not in current_rates:
                continue

            current_ask, current_bid = current_rates[symbol]["ask"], current_rates[symbol]["bid"]

            df_candles = self.gmo_fetcher.fetch_klines(symbol, interval="15min")
            if df_candles.empty or len(df_candles) < 20:
                df_candles = generate_fallback_candle_data(base_price=(current_ask + current_bid) / 2)

            analysis = self.strategy.generate_signal(df_candles)
            sig, reason, atr = analysis["signal"], analysis["reason"], analysis.get("atr", 0.10)

            logger.info(f"[{symbol}] Bid: {current_bid:.3f} | Ask: {current_ask:.3f} | ATR: {atr:.3f} | Signal: {sig} ({reason})")

            if sig in ["BUY", "SELL"]:
                amount = self.strategy.calculate_position_size(
                    self.trader.portfolio.balance, current_ask if sig == "BUY" else current_bid, RISK_RATIO, atr
                )
                order_res = self.trader.place_order(symbol, sig, amount, current_rates)
                
                if order_res.get("status") == "ACCEPTED":
                    for pos_id, pos in self._get_position_iterator():
                        if pos.get("symbol") == symbol and pos.get("sl") is None:
                            pos["sl"] = analysis.get("sl_price")
                            pos["tp"] = analysis.get("tp_price")

                    logger.info(f"  └> 【約定成功】{sig} {amount:,} 通貨 (価格: {order_res['price']:.3f}, SL: {analysis.get('sl_price')}, TP: {analysis.get('tp_price')})")
                    self.notifier.notify_trade_executed({
                        "symbol": symbol, "side": sig, "amount": amount,
                        "price": order_res["price"], "fee": order_res.get("fee", 0),
                        "sl": analysis.get('sl_price'), "tp": analysis.get('tp_price')
                    })

        health = self.trader.process_account_health_and_losscut(current_rates)
        logger.info(f"口座残高: {self.trader.portfolio.balance:,.0f}円 | 維持率: {health.get('margin_ratio', 'N/A')}% | 含み損益: {health.get('unrealized_pnl', 0):,.0f}円")
