# utils/logger.py
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "trading_system", log_file: str = "logs/app.log", level=logging.INFO) -> logging.Logger:
    """
    コンソール出力およびファイル出力（ログローテーション機能付き）を管理するロガーを初期化
    """
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 重複ハンドラー登録の防止
    if logger.handlers:
        return logger

    # 構造化ログフォーマット: [日時] [レベル] [ファイル名:行番号] メッセージ
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. コンソール出力ハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. ファイル出力ハンドラー（5MBに達したら5世代分バックアップ作成）
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# システム全体で共通利用するデフォルトロガーインスタンス
logger = setup_logger()
