import os
from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# トレード設定パラメータ
INITIAL_CAPITAL = 1_000_000.0
RISK_RATIO = 0.02
ALLOWED_SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY"]
