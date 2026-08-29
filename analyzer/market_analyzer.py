import os
from google import genai
from typing import Dict, Any, Optional

class MarketAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=key) if key else None

    def generate_daily_ai_report(self, daily_summary: Dict[str, Any], positions: Any = None, rates: Any = None) -> str:
        if not self.client:
            return "APIキーが設定されていないため、AI日次レポートの生成をスキップします。"

        prompt = (
            f"本日のトレード日次レポートと市場分析を作成してください。\n"
            f"【日次サマリー】: {daily_summary}\n"
            f"【保有ポジション】: {positions}\n"
            f"【最新レート】: {rates}"
        )
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            return f"日次レポート生成エラー: {e}"
