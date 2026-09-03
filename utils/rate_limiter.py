import time
import threading

class RateLimiter:
    """GMO API のリクエスト制限（Rate Limit）回避用クラス"""

    def __init__(self, max_requests_per_sec: float = 5.0):
        self.interval = 1.0 / max_requests_per_sec
        self.last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """リクエスト間隔が短すぎる場合は自動でスリープ"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_request_time = time.time()
