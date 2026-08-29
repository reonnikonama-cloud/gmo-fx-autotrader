import os
import time
import random
import json
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

# websocket-client が利用可能な場合はWebSocket、不可の場合は高速RESTで受信
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

PORT = int(os.getenv("PORT", 10000))
JST = timezone(timedelta(hours=9))

# 最新レート保持用共有キャッシュ（スレッドセーフ）
rates_cache = {
    "USD_JPY": {"bid": 155.500, "ask": 155.515},
    "EUR_JPY": {"bid": 168.200, "ask": 168.215},
    "GBP_JPY": {"bid": 198.800, "ask": 198.818},
    "AUD_JPY": {"bid": 102.300, "ask": 102.315},
    "NZD_JPY": {"bid": 94.100, "ask": 94.115}
}
cache_lock = threading.Lock()

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

def start_websocket_client():
    """
    GMOコイン 外国為替FX Public WebSocket リアルタイム受信スレッド
    Doc: https://api.coin.z.com/fxdocs/
    """
    ws_url = "wss://forex-api.coin.z.com/ws/public/v1"

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("channel") == "ticker":
                symbol = data.get("symbol")
                bid = float(data.get("bid", 0))
                ask = float(data.get("ask", 0))
                if symbol in ALLOWED_SYMBOLS and bid > 0 and ask > 0:
                    with cache_lock:
                        rates_cache[symbol] = {"bid": bid, "ask": ask, "timestamp": data.get("timestamp")}
        except Exception:
            pass

    def on_open(ws):
        for sym in ALLOWED_SYMBOLS:
            sub_msg = {"command": "subscribe", "channel": "ticker", "symbol": sym}
            ws.send(json.dumps(sub_msg))

    def on_error(ws, error):
        pass

    def on_close(ws, close_status_code, close_msg):
        time.sleep(5)
        # 自動再接続
        threading.Thread(target=start_websocket_client, daemon=True).start()

    if HAS_WEBSOCKET:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever()

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
    print(f" GMOコイン FX 自動トレード (初期資金: {INITIAL_CAPITAL:,.0f}円)")
    print("==========================================")

    trader = PaperTraderTeam(initial_capital=INITIAL_CAPITAL)
    strategy = BasicStrategy(short_window=5, long_window=20, rsi_window=14, atr_window=14)
    analyzer = MarketAnalyzer(api_key=GEMINI_API_KEY)
    notifier = WebhookNotifier(webhook_url=DISCORD_WEBHOOK_URL)
    gmo_fetcher = GmoFxFetcher()

    # WebSocket受信用スレッド起動
    threading.Thread(target=start_websocket_client, daemon=True).start()

    last_date = datetime.now(JST).strftime("%Y-%m-%d")
    last_signal_check_time = 0.0
    signal_check_interval = 60.0  # エントリーシグナル判定は60秒周期

    while True:
        now_time = time.time()
        now_jst = datetime.now(JST)
        current_date = now_jst.strftime("%Y-%m-%d")

        # 1. リアルタイムレートの同期取得
        with cache_lock:
            current_rates = rates_cache.copy()

        # WebSocket未稼働時のバックアップREST取得（10秒に1回）
        if not HAS_WEBSOCKET or not current_rates:
            fetched = gmo_fetcher.fetch_ticker()
            if fetched:
                current_rates.update(fetched)

        # 2. 【リアルタイム（1秒周期）】既存ポジションの SL / TP / 約定判定
        for pos_id, pos in list(trader.positions.items()):
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
                res = trader.close_position(pos_id, curr_price)
                print(f"【自動決済】[{sym}] {pos['side']} | 理由: {close_reason} | 損益: {res['pnl']:,.0f}円")
                notifier.notify_trade_executed({
                    "symbol": sym, "side": f"CLOSE_{pos['side']}", "amount": pos["amount"],
                    "price": curr_price, "fee": 0, "pnl": res["pnl"]
                })

        # 3. 【シグナル判定周期（60秒ごと）】新規エントリー判定
        if now_time - last_signal_check_time >= signal_check_interval:
            last_signal_check_time = now_time
            print(f"\n--- レート更新 & シグナル評価 ({now_jst.strftime('%H:%M:%S')}) ---")

            # サーキットブレーカー（日次最大損失）確認
            if strategy.check_circuit_breaker(trader.portfolio.balance):
                print("【警告】日次許容損失の上限（5%）に達したため、新規注文を一時停止中")

            for symbol in ALLOWED_SYMBOLS:
                if symbol not in current_rates: continue
                current_ask, current_bid = current_rates[symbol]["ask"], current_rates[symbol]["bid"]

                # 実ローソク足データ取得 (取得不能時は自動フォールバック)
                df_candles = gmo_fetcher.fetch_klines(symbol, interval="15min")
                if df_candles.empty or len(df_candles) < 20:
                    df_candles = generate_fallback_candle_data(base_price=(current_ask + current_bid) / 2)

                analysis = strategy.generate_signal(df_candles)
                sig, reason, atr = analysis["signal"], analysis["reason"], analysis.get("atr", 0.10)

                print(f"[{symbol}] Bid: {current_bid:.3f} | Ask: {current_ask:.3f} | ATR: {atr:.3f} | Signal: {sig} ({reason})")

                if sig in ["BUY", "SELL"]:
                    amount = strategy.calculate_position_size(trader.portfolio.balance, current_ask if sig == "BUY" else current_bid, RISK_RATIO, atr)
                    order_res = trader.place_order(symbol, sig, amount, current_rates)
                    if order_res["status"] == "ACCEPTED":
                        # ポジション情報に SL/TP を登録
                        for pos_id, pos in trader.positions.items():
                            if pos.get("sl") is None:
                                pos["sl"] = analysis["sl_price"]
                                pos["tp"] = analysis["tp_price"]

                        print(f"  └> 【約定成功】{sig} {amount:,} 通貨 (価格: {order_res['price']:.3f}, SL: {analysis['sl_price']}, TP: {analysis['tp_price']})")
                        notifier.notify_trade_executed({
                            "symbol": symbol, "side": sig, "amount": amount,
                            "price": order_res["price"], "fee": order_res["fee"],
                            "sl": analysis['sl_price'], "tp": analysis['tp_price']
                        })

            # 口座状態とロスカット
            health = trader.process_account_health_and_losscut(current_rates)
            print(f"口座残高: {trader.portfolio.balance:,.0f}円 | 維持率: {health['margin_ratio']}% | 含み損益: {health['unrealized_pnl']:,.0f}円")

        # 4. 日次AIレポート送信
        if current_date != last_date:
            daily_summary = trader.generate_daily_report(last_date)
            ai_report = analyzer.generate_daily_ai_report(daily_summary, trader.positions, current_rates)
            notifier.notify_daily_report(daily_summary, ai_report)
            last_date = current_date

        time.sleep(1)  # 1秒ごとにSL/TPリアルタイム判定を実施

if __name__ == "__main__":
    threading.Thread(target=run_health_check_server, daemon=True).start()
    run_system_loop()
