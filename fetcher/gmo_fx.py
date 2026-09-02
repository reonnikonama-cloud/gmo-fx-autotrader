import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from utils.logger import logger

class GmoFxFetcher:
    # 2種類の Base URL を定義（Ticker用とPublicデータ用）
    FX_BASE_URL = "https://forex-api.coin.z.com/public/v1"
    PUBLIC_BASE_URL = "https://api.coin.z.com/public/v1"

    def fetch_ticker(self) -> dict:
        """リアルタイムの最新レート（Ticker）を取得"""
        url = f"{self.FX_BASE_URL}/ticker"
        try:
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            data = res.json()

            if data.get("status") != 0 or "data" not in data:
                logger.error(f"GMO FX Ticker API Error: {data}")
                return {}

            rates = {}
            for item in data.get("data", []):
                symbol = item.get("symbol")
                if symbol:
                    rates[symbol] = {
                        "bid": float(item.get("bid", 0)),
                        "ask": float(item.get("ask", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                    }
            return rates

        except Exception as e:
            logger.error(f"GMO FX Ticker Fetch Error: {e}")
            return {}

    def fetch_klines(self, symbol: str, interval: str = "15min") -> pd.DataFrame:
        """GMO FX API からローソク足データを取得（Base URLおよび日付のフォールバック付き）"""
        now_utc = datetime.now(timezone.utc)

        # 1day, 1week, 1month は YYYY (4桁)、それ以外は YYYYMMDD (8桁)
        if interval in ["1day", "1week", "1month"]:
            dates_to_try = [now_utc.strftime("%Y")]
        else:
            dates_to_try = [
                now_utc.strftime("%Y%m%d"),
                (now_utc - timedelta(days=1)).strftime("%Y%m%d")  # 当日データがない場合は前日
            ]

        # 両方の Base URL で試行
        base_urls = [self.PUBLIC_BASE_URL, self.FX_BASE_URL]

        for base_url in base_urls:
            for date_str in dates_to_try:
                url = f"{base_url}/klines?symbol={symbol}&interval={interval}&date={date_str}"
                try:
                    res = requests.get(url, timeout=5)
                    if res.status_code == 404:
                        continue  # 404の場合は次のURL/日付条件へ

                    res.raise_for_status()
                    data = res.json()

                    if data.get("status") == 0 and "data" in data and data["data"]:
                        df = pd.DataFrame(data["data"])
                        for col in ["open", "high", "low", "close"]:
                            if col in df.columns:
                                df[col] = df[col].astype(float)
                        return df

                except Exception:
                    continue

        logger.error(f"GMO FX Klines Fetch Failed ({symbol}, {interval}): 全リクエストが404でした。")
        return pd.DataFrame()
