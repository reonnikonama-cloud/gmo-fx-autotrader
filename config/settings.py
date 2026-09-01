import os
from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv()

# APIキー・通知設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# トレード設定パラメータ（初期資金: 5万円 / 1トレード許容リスク: 1%）
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 50000.0))
RISK_RATIO = float(os.getenv("RISK_RATIO", 0.01))

# 取引スタイル設定 ("SCALPING", "DAYTRADE", "SWING", "POSITION")
# 環境変数から取得し、未指定の場合は "DAYTRADE" をデフォルト採用
TRADING_STYLE = os.getenv("TRADING_STYLE", "DAYTRADE").upper()

# 許可する取引通貨ペア一覧
ALLOWED_SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY"]
