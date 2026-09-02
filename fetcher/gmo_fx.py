import requests
import pandas as pd
from datetime import datetime
from utils.logger import logger

class GmoFxFetcher:
    BASE_URL = "https://forex-api.coin.z.com/public/v1"

    def fetch_klines(self, symbol: str, interval: str = "15min") -> pd.DataFrame:
        now = datetime.now()
        
        # --- GMOコイン API仕様に基づく date フォーマットの自動切り替え ---
        # 1day, 1week, 1month は YYYY (4桁)、それ以外(1min〜12hour)は YYYYMMDD (8桁)
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

            # レスポンスデータを DataFrame へ変換
            klines = data["data"]
            if not klines:
                return pd.DataFrame()

            df = pd.DataFrame(klines)
            # カラム整形処理...
            return df

        except Exception as e:
            logger.error(f"GMO FX Klines Fetch Error ({symbol}, {interval}): {e}")
            return pd.DataFrame()
