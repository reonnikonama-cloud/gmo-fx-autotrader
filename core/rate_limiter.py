import time
import threading

class RateLimiter:
    """1秒間のリクエスト回数を厳格に制限し 429 エラーを防ぐクラス"""

    def __init__(self, max_requests_per_sec: float = 4.0):
        self.interval = 1.0 / max_requests_per_sec
        self.last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_request_time = time.time()
