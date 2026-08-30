import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from core.orchestrator import SystemOrchestrator
from utils.logger import logger

PORT = int(os.getenv("PORT", 10000))

class HealthCheckHandler(BaseHTTPRequestHandler):
    def _send_ok(self):
        """ヘルスチェック用レスポンス"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self._send_ok()

    def do_POST(self):
        self._send_ok()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()

    def log_message(self, format, *args):
        # アクセスログを出力せず非表示化
        return

def run_health_check_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
    logger.info(f"ヘルスチェックサーバーをポート {PORT} で起動しました。")
    server.serve_forever()

if __name__ == "__main__":
    # ヘルスチェックサーバーの並行起動
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()

    # メインオーケストレーター実行
    try:
        orchestrator = SystemOrchestrator()
        orchestrator.run_loop()
    except KeyboardInterrupt:
        logger.info("ユーザー操作によりシステムを終了します。")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"システム停止エラー: {e}")
        sys.exit(1)
