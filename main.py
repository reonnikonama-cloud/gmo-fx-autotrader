import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from core.orchestrator import SystemOrchestrator

PORT = int(os.getenv("PORT", 10000))

class HealthCheckHandler(BaseHTTPRequestHandler):
    def _send_ok(self):
        """常に最小限のレスポンス (2 bytes) を返却"""
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
    server.serve_forever()

if __name__ == "__main__":
    # Renderヘルスチェックおよび cron-job.org 用HTTPサーバーの並行起動
    threading.Thread(target=run_health_check_server, daemon=True).start()

    # 全モジュールを統括するオーケストレーターの実行
    orchestrator = SystemOrchestrator()
    orchestrator.run_loop()
