import traceback
from google import genai
from utils.logger import logger

class LossAnalyzer:
    """Geminiを活用した負けトレード（敗因）自動分析モジュール"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key) if api_key else None

    def analyze_trade_failure(self, trade_info: dict, market_context: dict) -> str:
        """損失トレード発生時にGeminiへプロンプトを投げて敗因を特定"""
        if not self.client:
            return "Gemini APIキーが未設定のため敗因分析をスキップしました。"

        prompt = f"""
あなたは優秀なFXプロトレーダー兼リスクアナリストです。
以下の「負けトレードデータ」と「エントリー時点の相場環境」を分析し、なぜ失敗したのか（敗因）と今後の改善案を簡潔にまとめてください。

【トレードデータ】
- 通貨ペア: {trade_info.get('symbol')}
- 取引スタイル: {trade_info.get('style')}
- 注文種別: {trade_info.get('side')}
- エントリー価格: {trade_info.get('entry_price')}
- 決済価格: {trade_info.get('close_price')}
- 確定損益: {trade_info.get('pnl'):,.0f}円
- 決済理由: {trade_info.get('close_reason')}

【エントリー時の指標状況】
- RSI: {market_context.get('rsi')}
- 短期/長期SMA状態: {market_context.get('ma_status')}
- 検知パターン: {market_context.get('patterns')}

【回答フォーマット】
1. 主な敗因（1〜2行）
2. 相場環境とのミスマッチ（レンジでのトレンドフォロー等）
3. 提示すべき対策（次回以降の同パターン回避策）
"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"【LossAnalyzerエラー】: {e}")
            return f"敗因分析中にエラーが発生しました: {e}"
