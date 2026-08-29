# fetcher/gmo_fx.py
import urllib.request
import json
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd

JST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

class GmoFxFetcher:
    """
    GMOコイン 外国為替FX Public API 取得クラス
    Official Doc: https://api.coin.z.com/fxdocs/
    """
    BASE_URL = "https://forex-api.coin.z.com/public/v1"

    def __init__(self):
        self.last_known_rates = {
            "USD_JPY": {"bid": 155.500, "ask": 155.515},
            "EUR_JPY": {"bid": 168.200, "ask": 168.215},
            "GBP_JPY": {"bid": 198.800, "ask": 198.818},
            "AUD_JPY": {"bid": 102.300, "ask": 102.315},
            "NZD_JPY": {"bid": 94.100, "ask": 94.115}
        }

    def fetch_ticker(self) -> dict:
        """
        全銘柄の最新Bid/Askを取得
        GET /v1/ticker
        """
        url = f"{self.BASE_URL}/ticker"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_json = json.loads(response.read().decode('utf-8'))
                    if res_json.get("status") == 0 and "data" in res_json:
                        rates = {}
                        for item in res_json["data"]:
                            symbol = item.get("symbol")
                            rates[symbol] = {
                                "bid": float(item["bid"]),
                                "ask": float(item["ask"]),
                                "high": float(item.get("high", 0)),
                                "low": float(item.get("low", 0)),
                                "timestamp": item.get("timestamp")
                            }
                        self.last_known_rates.update(rates)
                        return rates
        except Exception as e:
            logger.warning(f"GMO FX Ticker Fetch Error (Fallback to last known): {e}")

        return self.last_known_rates

    def fetch_klines(self, symbol: str, interval: str = "15min") -> pd.DataFrame:
        """
        ローソク足データの取得
        GET /v1/klines?symbol=USD_JPY&priceType=ASK&interval=15min&date=YYYYMMDD
        """
        now_jst = datetime.now(JST)
        date_str = now_jst.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/klines?symbol={symbol}&priceType=ASK&interval={interval}&date={date_str}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_json = json.loads(response.read().decode('utf-8'))
                    if res_json.get("status") == 0 and "data" in res_json:
                        raw_data = res_json["data"]
                        if raw_data:
                            records = []
                            for row in raw_data:
                                # row format: {"openTime": "...", "open": "...", "high": "...", "low": "...", "close": "..."}
                                dt = datetime.fromtimestamp(int(row["openTime"]) / 1000, tz=JST)
                                records.append({
                                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                                    "open": float(row["open"]),
                                    "high": float(row["high"]),
                                    "low": float(row["low"]),
                                    "close": float(row["close"])
                                })
                            df = pd.DataFrame(records)
                            return df.sort_values("timestamp").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"GMO FX Klines Fetch Error ({symbol}): {e}")

        return pd.DataFrame()
