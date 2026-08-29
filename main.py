# main.py
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from core.orchestrator import SystemOrchestrator

PORT = int(os.getenv("PORT", 10000))

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

if __name__ == "__main__":
    # Renderヘルスチェック用HTTPサーバーの並行起動
    threading.Thread(target=run_health_check_server, daemon=True).start()

    # 全モジュールを統括するオーケストレーターの実行
    orchestrator = SystemOrchestrator()
    orchestrator.run_loop()
