import hmac
import hashlib
import time
import json
import requests
from typing import Dict, Any, Optional
from utils.rate_limiter import RateLimiter
from utils.logger import logger

class GmoFxClient:
    """GMOコイン 外為FX REST API 通信専用クライアント"""

    BASE_URL = "https://forex-api.coin.z.com/private"
    PUBLIC_URL = "https://forex-api.coin.z.com/public"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = RateLimiter(max_requests_per_sec=4.0)

    def _get_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Private API 用 HMAC-SHA256 署名ヘッダー生成"""
        timestamp = str(int(time.time() * 1000))
        text = timestamp + method + path + body
        sign = hmac.new(
            self.api_secret.encode("utf-8"),
            text.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": sign,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, params: Optional[dict] = None, data: Optional[dict] = None, private: bool = True) -> Dict[str, Any]:
        """統一リクエスト処理"""
        self.rate_limiter.wait()  # アクセス制限の適用

        base_url = self.BASE_URL if private else self.PUBLIC_URL
        url = f"{base_url}{endpoint}"
        body_str = json.dumps(data) if data else ""

        headers = self._get_headers(method, f"/private{endpoint}", body_str) if private else {}

        try:
            res = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=body_str if data else None,
                timeout=5
            )
            res.raise_for_status()
            result = res.json()

            if result.get("status") != 0:
                logger.error(f"GMO FX API Error [{method} {endpoint}]: Status Code {result.get('status')}")
                return result

            return result

        except Exception as e:
            logger.error(f"HTTP Communication Error [{method} {endpoint}]: {e}")
            return {"status": -1, "error": str(e)}

    def get(self, endpoint: str, params: dict = None, private: bool = True) -> dict:
        return self._request("GET", endpoint, params=params, private=private)

    def post(self, endpoint: str, data: dict = None, private: bool = True) -> dict:
        return self._request("POST", endpoint, data=data, private=private)

    def put(self, endpoint: str, data: dict = None, private: bool = True) -> dict:
        return self._request("PUT", endpoint, data=data, private=private)

    def delete(self, endpoint: str, data: dict = None, private: bool = True) -> dict:
        return self._request("DELETE", endpoint, data=data, private=private)
