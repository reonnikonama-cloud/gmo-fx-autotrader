# main.py
import os
import time
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta
import pandas as pd

from config.settings import GEMINI_API_KEY, DISCORD_WEBHOOK_URL, ALLOWED_SYMBOLS, INITIAL_CAPITAL, RISK_RATIO
from trader.paper_trader import PaperTraderTeam
from trader.strategy import BasicStrategy
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.notifier import WebhookNotifier
from fetcher.gmo_fx import GmoFxFetcher

PORT = int(os.getenv("PORT", 10000))
JST = timezone(timedelta(hours=9))

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return

def run_health_check_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
    server.serve_forever()

def generate_fallback_candle_data(base_price: float, count: int = 30) -> pd.DataFrame:
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
        data.append({"timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"), "open": round(open_p, 3), "high": round(high_p, 3), "low": round(low_p, 3), "close": round(close_p, 3)})
    return pd.DataFrame(data)

def run_system_loop():
    print("==========================================")
    print(" GMOコイン 外国為替FX 自動トレードシステム 稼働開始")
    print("==========================================")

    trader = PaperTraderTeam(initial_capital=INITIAL_CAPITAL)
    strategy = BasicStrategy(short_window=5, long_window=20, rsi_window=14, atr_window=14)
    analyzer = MarketAnalyzer(api_key=GEMINI_API_KEY)
    notifier = WebhookNotifier(webhook_url=DISCORD_WEBHOOK_URL)
    gmo_fetcher = GmoFxFetcher()

    last_date = datetime.now(JST).strftime("%Y-%m-%d")

    while True:
        now_jst = datetime.now(JST)
        current_date = now_jst.strftime("%Y-%m-%d")
        print(f"\n--- {current_date} {now_jst.strftime('%H:%M:%S')} ---")

        # 1. 実市場レート（GMOコイン API）取得
        rates = gmo_fetcher.fetch_ticker()

        # サーキットブレーカー（日次最大損失）確認
        is_cb_active = strategy.check_circuit_breaker(trader.portfolio.balance)
        if is_cb_active:
            print("【警告】日次許容損失の上限（5%）に達したため、新規注文を一時停止中")

        for symbol in ALLOWED_SYMBOLS:
            if symbol not in rates: continue
            current_ask, current_bid = rates[symbol]["ask"], rates[symbol]["bid"]

            # 2. 実ローソク足データ取得 (取得不能時は自動フォールバック)
            df_candles = gmo_fetcher.fetch_klines(symbol, interval="15min")
            if df_candles.empty or len(df_candles) < 20:
                df_candles = generate_fallback_candle_data(base_price=(current_ask + current_bid) / 2)

            # 3. 戦略シグナルおよび可変SL/TP判定
            analysis = strategy.generate_signal(df_candles)
            sig = analysis["signal"]
            reason = analysis["reason"]
            atr = analysis.get("atr", 0.10)

            print(f"[{symbol}] Bid: {current_bid:.3f} | Ask: {current_ask:.3f} | ATR: {atr:.3f} | Signal: {sig} ({reason})")

            if sig in ["BUY", "SELL"]:
                amount = strategy.calculate_position_size(trader.portfolio.balance, current_ask if sig == "BUY" else current_bid, RISK_RATIO, atr)
                order_res = trader.place_order(symbol, sig, amount, rates)
                if order_res["status"] == "ACCEPTED":
                    print(f"  └> 【約定成功】{sig} {amount:,} 通貨 (価格: {order_res['price']:.3f}, SL: {analysis['sl_price']}, TP: {analysis['tp_price']})")
                    notifier.notify_trade_executed({
                        "symbol": symbol,
                        "side": sig,
                        "amount": amount,
                        "price": order_res["price"],
                        "fee": order_res["fee"],
                        "sl": analysis['sl_price'],
                        "tp": analysis['tp_price']
                    })
                else:
                    print(f"  └> 【注文拒否】{order_res['reason']}")

        # 4. 口座ヘルスチェック及びロスカット処理
        health = trader.process_account_health_and_losscut(rates)
        print(f"口座状態: {health['status']} | 維持率: {health['margin_ratio']}% | 含み損益: {health['unrealized_pnl']}円")

        if health["losscut_executed"]:
            print("  └> 【警告】強制ロスカット実行")
            notifier.notify_losscut(health)

        # 5. 日次AI市場レポート送信
        if current_date != last_date:
            print("\n------------------------------------------")
            print(" 日次レポートおよびAI市場分析の生成中...")
            print("------------------------------------------")
            daily_summary = trader.generate_daily_report(last_date)
            ai_report = analyzer.generate_daily_ai_report(daily_summary, trader.positions, rates)
            print("\n[AI市場要約レポート]\n" + ai_report + "\n")
            notifier.notify_daily_report(daily_summary, ai_report)
            last_date = current_date

        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_health_check_server, daemon=True).start()
    run_system_loop()
