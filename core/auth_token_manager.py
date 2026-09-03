import time
import threading
from utils.logger import logger

class AuthTokenManager:
    """Private WSアクセストークン発行・50分周期自動延長マネージャー"""

    def __init__(self, rest_client):
        self.client = rest_client
        self.token = None
        self.is_running = False
        self._thread = None

    def start(self) -> str:
        """トークンを新規発行し、バックグラウンド更新を開始"""
        self.token = self._issue_token()
        if not self.token:
            raise RuntimeError("Private WS トークンの初回の発行に失敗しました。")

        self.is_running = True
        self._thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self._thread.start()
        logger.info(f"【AuthTokenManager】トークンを新規発行し、自動更新ループを開始しました。")
        return self.token

    def _issue_token(self) -> str:
        """POST /v1/ws-auth (トークン新規取得)"""
        res = self.client.post("/v1/ws-auth", private=True)
        if res.get("status") == 0 and "data" in res:
            return res["data"]
        logger.error(f"WSトークン発行失敗: {res}")
        return None

    def _extend_token(self) -> bool:
        """PUT /v1/ws-auth (トークン有効期限延長)"""
        res = self.client.put("/v1/ws-auth", private=True)
        if res.get("status") == 0:
            logger.info("【AuthTokenManager】Private WS トークンの有効期限を延命しました。")
            return True
        logger.error(f"WSトークン延長失敗: {res}")
        return False

    def _keep_alive_loop(self):
        """50分（3000秒）ごとに延命リクエストを送出"""
        while self.is_running:
            time.sleep(3000)
            if self.is_running:
                success = self._extend_token()
                if not success:
                    # 延命失敗時は再発行を試みる
                    logger.warning("トークン延長に失敗したため、再発行を試みます。")
                    self.token = self._issue_token()

    def stop(self):
        """DELETE /v1/ws-auth (トークン破棄)"""
        self.is_running = False
        if self.token:
            self.client.delete("/v1/ws-auth", private=True)
            logger.info("【AuthTokenManager】Private WS トークンを削除しました。")
            self.token = None
