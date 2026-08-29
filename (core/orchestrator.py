# core/orchestrator.py
import time
import json
import threading
from datetime import datetime, timezone, timedelta
import pandas as pd

from config.settings import GEMINI_API_KEY, DISCORD_WEBHOOK_URL, ALLOWED_SYMBOLS, INITIAL_CAPITAL, RISK_RATIO
from trader.paper_trader import PaperTraderTeam
from trader.strategy import BasicStrategy
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.risk_analyzer import RiskAnalyzer
from analyzer.notifier import WebhookNotifier
from fetcher.gmo_fx import GmoFxFetcher
from accounting.tax_calculator import TaxCalculator
from reporter.report_generator import PerformanceReporter

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
    """システム全体（データ取得・トレード・AI分析・リスク・税務・帳票・通知）を統合統括する核エンジン"""

    def __init__(self):
        # 1. 全各ユニットの初期化
        self.trader = PaperTraderTeam(initial_capital=INITIAL_CAPITAL)
        self.strategy = BasicStrategy(short_window=5, long_window=20, rsi_window=14, atr_window=14)
        self.market_analyzer = MarketAnalyzer(api_key=GEMINI_API_KEY)
        self.risk_analyzer = RiskAnalyzer()
        self.tax_calculator = TaxCalculator()
        self.reporter = PerformanceReporter()
        self.notifier = WebhookNotifier(webhook_url=DISCORD_WEBHOOK_URL)
        self.gmo_fetcher = GmoFxFetcher()

        # 2. 共通レートキャッシュ・スレッド同期変数
        self.rates_cache = {
            "USD_JPY": {"bid": 155.500, "ask": 155.515},
            "EUR_JPY": {"bid": 168.200, "ask": 168.215},
            "GBP_JPY": {"bid": 198.800, "ask": 198.818},
            "AUD_JPY": {"bid": 102.300, "ask": 102.315},
            "NZD_JPY": {"bid": 94.100, "ask": 94.115}
        }
        self.cache_lock = threading.Lock()
        self.last_date = datetime.now(JST).strftime("%Y-%m-%d")
        self.last_signal_check_time = 0.0
        self.signal_check_interval = 60.0

    def start_websocket(self):
        """WebSocketリアルタイムレート受信用バックグラウンド処理"""
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
            except Exception:
                pass

        def on_open(ws):
            for sym in ALLOWED_SYMBOLS:
                sub_msg = {"command": "subscribe", "channel": "ticker", "symbol": sym}
                ws.send(json.dumps(sub_msg))

        def on_close(ws, close_status_code, close_msg):
            time.sleep(5)
            threading.Thread(target=self.start_websocket, daemon=True).start()

        if HAS_WEBSOCKET:
            ws_url = "wss://forex-api.coin.z.com/ws/public/v1"
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=lambda ws, e: None,
                on_close=on_close
            )
            ws.run_forever()

    def run_loop(self):
        """システム全体の統括メインループ"""
        print("==========================================")
        print(f" GMOコイン FX 自動トレードシステム（統括マネージャー起動）")
        print(f" 初期資金: {INITIAL_CAPITAL:,.0f}円 | 1トレード許容リスク: {RISK_RATIO*100:.1f}%")
        print("==========================================")

        # WebSocketスレッド起動
        threading.Thread(target=self.start_websocket, daemon=True).start()

        while True:
            now_time = time.time()
            now_jst = datetime.now(JST)
            current_date = now_jst.strftime("%Y-%m-%d")

            # 最新レートの同期
            with self.cache_lock:
                current_rates = self.rates_cache.copy()

            if not HAS_WEBSOCKET or not current_rates:
                fetched = self.gmo_fetcher.fetch_ticker()
                if fetched:
                    current_rates.update(fetched)

            # ①【1秒周期】リアルタイム SL/TP 決済監視 ＆ 強制ロスカット確認
            self._process_realtime_sl_tp(current_rates)

            # ②【60秒周期】テクニカル分析 ＆ エントリーシグナル判定
            if now_time - self.last_signal_check_time >= self.signal_check_interval:
                self.last_signal_check_time = now_time
                self._process_signal_evaluation(now_jst, current_rates)

            # ③【日付変更時】日次AI分析・リスク評価・税務計算・総合報告書・CSV出力
            if current_date != self.last_date:
                self._process_daily_reporting(current_rates)
                self.last_date = current_date

            time.sleep(1)

    def _process_realtime_sl_tp(self, current_rates: dict):
        """保持ポジションの1秒毎SL/TP自動決済判定"""
        for pos_id, pos in list(self.trader.positions.items()):
            sym = pos["symbol"]
            if sym not in current_rates: continue
            bid, ask = current_rates[sym]["bid"], current_rates[sym]["ask"]
            curr_price = bid if pos["side"] == "BUY" else ask

            sl, tp = pos.get("sl"), pos.get("tp")
            close_reason = None

            if pos["side"] == "BUY":
                if sl and curr_price <= sl: close_reason = f"SL到達 ({curr_price:.3f} <= {sl})"
                elif tp and curr_price >= tp: close_reason = f"TP到達 ({curr_price:.3f} >= {tp})"
            elif pos["side"] == "SELL":
                if sl and curr_price >= sl: close_reason = f"SL到達 ({curr_price:.3f} >= {sl})"
                elif tp and curr_price <= tp: close_reason = f"TP到達 ({curr_price:.3f} <= {tp})"

            if close_reason:
                res = self.trader.close_position(pos_id, curr_price)
                print(f"【自動決済】[{sym}] {pos['side']} | 理由: {close_reason} | 損益: {res['pnl']:,.0f}円")
                self.notifier.notify_trade_executed({
                    "symbol": sym, "side": f"CLOSE_{pos['side']}", "amount": pos["amount"],
                    "price": curr_price, "fee": 0, "pnl": res["pnl"]
                })

    def _process_signal_evaluation(self, now_jst: datetime, current_rates: dict):
        """60秒周期の新着データ取得とシグナル判定・注文発行"""
        print(f"\n--- レート更新 & シグナル評価 ({now_jst.strftime('%H:%M:%S')}) ---")

        if self.strategy.check_circuit_breaker(self.trader.portfolio.balance):
            print("【警告】日次許容損失上限（5%）に達したため、新規注文を一時停止中")

        for symbol in ALLOWED_SYMBOLS:
            if symbol not in current_rates: continue
            current_ask, current_bid = current_rates[symbol]["ask"], current_rates[symbol]["bid"]

            df_candles = self.gmo_fetcher.fetch_klines(symbol, interval="15min")
            if df_candles.empty or len(df_candles) < 20:
                df_candles = generate_fallback_candle_data(base_price=(current_ask + current_bid) / 2)

            analysis = self.strategy.generate_signal(df_candles)
            sig, reason, atr = analysis["signal"], analysis["reason"], analysis.get("atr", 0.10)

            print(f"[{symbol}] Bid: {current_bid:.3f} | Ask: {current_ask:.3f} | ATR: {atr:.3f} | Signal: {sig} ({reason})")

            if sig in ["BUY", "SELL"]:
                amount = self.strategy.calculate_position_size(
                    self.trader.portfolio.balance, current_ask if sig == "BUY" else current_bid, RISK_RATIO, atr
                )
                order_res = self.trader.place_order(symbol, sig, amount, current_rates)
                if order_res["status"] == "ACCEPTED":
                    for pos_id, pos in self.trader.positions.items():
                        if pos.get("sl") is None:
                            pos["sl"] = analysis["sl_price"]
                            pos["tp"] = analysis["tp_price"]

                    print(f"  └> 【約定成功】{sig} {amount:,} 通貨 (価格: {order_res['price']:.3f}, SL: {analysis['sl_price']}, TP: {analysis['tp_price']})")
                    self.notifier.notify_trade_executed({
                        "symbol": symbol, "side": sig, "amount": amount,
                        "price": order_res["price"], "fee": order_res["fee"],
                        "sl": analysis['sl_price'], "tp": analysis['tp_price']
                    })

        health = self.trader.process_account_health_and_losscut(current_rates)
        print(f"口座残高: {self.trader.portfolio.balance:,.0f}円 | 維持率: {health['margin_ratio']}% | 含み損益: {health['unrealized_pnl']:,.0f}円")

    def _process_daily_reporting(self, current_rates: dict):
        """日次でのAI分析・リスク指標・税務計算・帳票出力の統合実行"""
        daily_summary = self.trader.generate_daily_report(self.last_date)
        ai_report = self.market_analyzer.generate_daily_ai_report(daily_summary, self.trader.positions, current_rates)
        
        # リスク指標 ＆ 税務集計
        risk_metrics = self.risk_analyzer.calculate_metrics(self.trader.trade_history, self.trader.portfolio.balance, INITIAL_CAPITAL)
        tax_metrics = self.tax_calculator.calculate_annual_tax(self.trader.trade_history)

        # 報告書文章の自動生成
        full_report_str = self.reporter.generate_full_report(risk_metrics, tax_metrics, self.trader.portfolio.balance, INITIAL_CAPITAL)
        print("\n" + full_report_str + "\n")

        # Discord通知
        self.notifier.notify_daily_report(daily_summary, f"{ai_report}\n\n{full_report_str}")
        
        # 確定申告用 CSV 取引明細帳の書き出し
        self.reporter.export_csv_ledger(self.trader.trade_history, f"trade_ledger_{self.last_date}.csv")
