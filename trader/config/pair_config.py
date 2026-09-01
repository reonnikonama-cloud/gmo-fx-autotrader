# スキャルピング設定 (1分足軸 / 固定RR)
SCALPING_PAIR_CONFIG = {
    "USD_JPY": {"tp_pips": 5.0,  "sl_pips": 5.0, "daily_target_pips": 30.0},
    "EUR_JPY": {"tp_pips": 6.0,  "sl_pips": 6.0, "daily_target_pips": 35.0},
    "GBP_JPY": {"tp_pips": 10.0, "sl_pips": 8.0, "daily_target_pips": 40.0},
}

# デイトレード設定 (15分〜1時間足軸 / 固定RR 1:1.7)
DAYTRADE_PAIR_CONFIG = {
    "USD_JPY": {"tp_pips": 25.5, "sl_pips": 15.0, "daily_target_pips": 30.0},
    "EUR_JPY": {"tp_pips": 35.6, "sl_pips": 20.0, "daily_target_pips": 40.0},
    "GBP_JPY": {"tp_pips": 50.0, "sl_pips": 25.0, "daily_target_pips": 50.0},
}

# スイングトレード設定 (4時間〜日足軸 / 固定RR 1:2.2〜1:2.5)
SWING_PAIR_CONFIG = {
    "USD_JPY": {"tp_pips": 110.0, "sl_pips": 50.0, "daily_target_pips": None},
    "EUR_JPY": {"tp_pips": 132.0, "sl_pips": 60.0, "daily_target_pips": None},
    "GBP_JPY": {"tp_pips": 204.8, "sl_pips": 80.0, "daily_target_pips": None},
}

# ポジショントレード設定 (日足〜週足軸 / 可変RR 1:3〜1:5)
POSITION_PAIR_CONFIG = {
    "USD_JPY": {"base_sl_pips": 150.0, "min_rr": 3.0, "max_rr": 5.0, "daily_target_pips": None},
    "EUR_JPY": {"base_sl_pips": 180.0, "min_rr": 3.0, "max_rr": 5.0, "daily_target_pips": None},
    "GBP_JPY": {"base_sl_pips": 250.0, "min_rr": 3.0, "max_rr": 5.0, "daily_target_pips": None},
}

STRATEGY_CONFIGS = {
    "SCALPING": SCALPING_PAIR_CONFIG,
    "DAYTRADE": DAYTRADE_PAIR_CONFIG,
    "SWING": SWING_PAIR_CONFIG,
    "POSITION": POSITION_PAIR_CONFIG
}
