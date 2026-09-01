from typing import Dict
import pandas as pd

def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, bool]:
    """1本足・2本足・3本足の全ローソク足パターン検知関数"""
    results = {
        "bullish_marubozu": False, "bearish_marubozu": False,
        "doji": False, "hammer_pinbar": False, "shooting_star_pinbar": False,
        "bullish_engulfing": False, "bearish_engulfing": False,
        "bullish_harami": False, "bearish_harami": False,
        "piercing_line": False, "dark_cloud_cover": False,
        "three_red_soldiers": False, "three_black_crows": False,
        "morning_star": False, "evening_star": False
    }

    if len(df) < 3:
        return results

    c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

    def body(c): return abs(c['close'] - c['open'])
    def range_total(c): return max(c['high'] - c['low'], 0.0001)
    def is_bull(c): return c['close'] > c['open']
    def is_bear(c): return c['close'] < c['open']

    # 1本足
    results["doji"] = (body(c0) / range_total(c0)) <= 0.10
    results["bullish_marubozu"] = is_bull(c0) and (body(c0) / range_total(c0) >= 0.75)
    results["bearish_marubozu"] = is_bear(c0) and (body(c0) / range_total(c0) >= 0.75)

    lower_shadow0 = min(c0['open'], c0['close']) - c0['low']
    upper_shadow0 = c0['high'] - max(c0['open'], c0['close'])
    results["hammer_pinbar"] = (lower_shadow0 >= 2 * body(c0)) and (upper_shadow0 <= body(c0) * 0.5)
    results["shooting_star_pinbar"] = (upper_shadow0 >= 2 * body(c0)) and (lower_shadow0 <= body(c0) * 0.5)

    # 2本足
    results["bullish_engulfing"] = is_bear(c1) and is_bull(c0) and (c0['open'] <= c1['close']) and (c0['close'] >= c1['open'])
    results["bearish_engulfing"] = is_bull(c1) and is_bear(c0) and (c0['open'] >= c1['close']) and (c0['close'] <= c1['open'])
    results["bullish_harami"] = is_bear(c1) and is_bull(c0) and (c0['open'] > c1['close']) and (c0['close'] < c1['open'])
    results["bearish_harami"] = is_bull(c1) and is_bear(c0) and (c0['open'] < c1['close']) and (c0['close'] > c1['open'])

    c1_mid = c1['open'] - (body(c1) / 2)
    results["piercing_line"] = is_bear(c1) and is_bull(c0) and (c0['open'] < c1['low']) and (c0['close'] > c1_mid) and (c0['close'] < c1['open'])
    c1_mid_bear = c1['open'] + (body(c1) / 2)
    results["dark_cloud_cover"] = is_bull(c1) and is_bear(c0) and (c0['open'] > c1['high']) and (c0['close'] < c1_mid_bear) and (c0['close'] > c1['open'])

    # 3本足
    results["three_red_soldiers"] = is_bull(c2) and is_bull(c1) and is_bull(c0) and (c2['close'] < c1['close'] < c0['close']) and (c2['open'] < c1['open'] < c0['open'])
    results["three_black_crows"] = is_bear(c2) and is_bear(c1) and is_bear(c0) and (c2['close'] > c1['close'] > c0['close']) and (c2['open'] > c1['open'] > c0['open'])
    results["morning_star"] = is_bear(c2) and (body(c1) < body(c2) * 0.4) and is_bull(c0) and (c0['close'] > (c2['open'] + c2['close']) / 2)
    results["evening_star"] = is_bull(c2) and (body(c1) < body(c2) * 0.4) and is_bear(c0) and (c0['close'] < (c2['open'] + c2['close']) / 2)

    return results
