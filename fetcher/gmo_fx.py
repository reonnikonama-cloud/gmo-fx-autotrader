import requests
import pandas as pd
from datetime import datetime
from utils.logger import logger

class GmoFxFetcher:
    BASE_URL = "https://forex-api.coin.z.com/public/v1"

    def fetch_ticker(self) -> dict:
        """リアルタイムの最新レート（Ticker）を取得"""
        url = f"{self.BASE_URL}/ticker"
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
        """指定時間足のローソク足データを取得（1day等はYYYY指定に自動切替）"""
        now = datetime.now()
        
        # GMO API仕様: 1day/1week/1month は YYYY(4桁)、それ以外は YYYYMMDD(8桁)
        if interval in ["1day", "1week", "1month"]:
            date_str = now.strftime("%Y")
        else:
            date_str = now.strftime("%Y%m%d")

        url = f"{self.BASE_URL}/klines?symbol={symbol}&interval={interval}&date={date_str}"

        try:
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            data = res.json()

            if data.get("status") != 0 or "data" not in data:
                logger.error(f"GMO FX Klines API Error ({symbol}, {interval}): {data}")
                return pd.DataFrame()

            klines = data.get("data", [])
            if not klines:
                return pd.DataFrame()

            df = pd.DataFrame(klines)
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)

            return df

        except Exception as e:
            logger.error(f"GMO FX Klines Fetch Error ({symbol}, {interval}): {e}")
            return pd.DataFrame()
