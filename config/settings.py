import os
from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# トレード設定パラメータ（初期資金: 5万円 / 1トレード許容リスク: 1%）
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 50000.0))
RISK_RATIO = float(os.getenv("RISK_RATIO", 0.01))

ALLOWED_SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY"]
