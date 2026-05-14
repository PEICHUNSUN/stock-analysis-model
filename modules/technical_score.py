# modules/technical_score.py
# 模組四：技術面評分（-25 到 +25 分）
# 評分依據：均線位置、均線排列、RSI、成交量

# ── 技術面評分設計說明 ────────────────────────────────
# 總分範圍：-25 ~ +25，分四個子項目：
#
# 1. 均線位置分   -10 ~ +10  → 收盤價站在哪幾條均線上方
# 2. 均線排列分   -8  ~ +8   → 均線是多頭/空頭排列
# 3. RSI 分數    -4  ~ +4   → RSI 位置判斷超買/超賣/健康
# 4. 成交量分     -3  ~ +3   → 量能是否配合價格方向
# ─────────────────────────────────────────────────────


def score_ma_position(close, ma5, ma10, ma20, ma60) -> tuple[int, str]:
    """
    均線位置分：收盤價站在幾條均線上方
    滿分 +10，最低 -10
    """
    if close is None:
        return 0, "無法判斷（數據缺失）"

    above = []
    below = []

    checks = [("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60)]
    for name, ma in checks:
        if ma is None:
            continue
        if close > ma:
            above.append(name)
        else:
            below.append(name)

    count_above = len(above)
    total       = len(above) + len(below)

    if total == 0:
        return 0, "無法判斷（均線數據缺失）"

    # 根據站上幾條均線給分
    score_map = {4: 10, 3: 6, 2: 2, 1: -4, 0: -10}
    score = score_map.get(count_above, 0)

    if count_above == 4:
        desc = f"站上全部均線（{', '.join(above)}）"
    elif count_above == 0:
        desc = f"跌破全部均線（{', '.join(below)}）"
    else:
        desc = f"站上 {', '.join(above)}；低於 {', '.join(below)}"

    return score, desc


def score_ma_alignment(ma5, ma10, ma20, ma60) -> tuple[int, str]:
    """
    均線排列分：判斷多頭/空頭排列
    完美多頭排列（MA5>MA10>MA20>MA60）→ +8
    完美空頭排列（MA5<MA10<MA20<MA60）→ -8
    """
    mas = [(v, n) for v, n in [(ma5, "MA5"), (ma10, "MA10"), (ma20, "MA20"), (ma60, "MA60")] if v is not None]

    if len(mas) < 2:
        return 0, "均線數據不足，無法判斷排列"

    values = [v for v, _ in mas]

    # 計算相鄰均線的大小關係
    bullish_pairs = sum(1 for i in range(len(values)-1) if values[i] > values[i+1])
    bearish_pairs = sum(1 for i in range(len(values)-1) if values[i] < values[i+1])
    total_pairs   = len(values) - 1

    if bullish_pairs == total_pairs:
        return 8, "完美多頭排列（短均線全部在長均線上方）"
    elif bullish_pairs == total_pairs - 1:
        return 4, "接近多頭排列（大部分均線向上排列）"
    elif bearish_pairs == total_pairs:
        return -8, "完美空頭排列（短均線全部在長均線下方）"
    elif bearish_pairs == total_pairs - 1:
        return -4, "接近空頭排列（大部分均線向下排列）"
    else:
        return 0, "均線糾結（多空方向不明）"


def score_rsi(rsi) -> tuple[int, str]:
    """
    RSI 分數：
    > 70 → 超買，給負分（短期過熱）
    50-70 → 多頭健康區間，給正分
    40-50 → 中性偏弱
    30-40 → 弱勢但接近超賣
    < 30 → 超賣，給小正分（可能反彈）
    """
    if rsi is None:
        return 0, "無法判斷（RSI 數據缺失）"

    if rsi > 75:
        return -4, f"RSI {rsi:.1f} 嚴重超買，短期風險高"
    elif rsi > 70:
        return -2, f"RSI {rsi:.1f} 超買區間，注意回調"
    elif rsi >= 55:
        return 4, f"RSI {rsi:.1f} 多頭健康區間"
    elif rsi >= 45:
        return 2, f"RSI {rsi:.1f} 中性偏多"
    elif rsi >= 35:
        return -2, f"RSI {rsi:.1f} 偏弱，空方佔優"
    elif rsi >= 30:
        return -3, f"RSI {rsi:.1f} 接近超賣"
    else:
        return 1, f"RSI {rsi:.1f} 超賣區間，留意反彈機會"


def score_volume(volume_ratio) -> tuple[int, str]:
    """
    成交量配合分：
    放量上漲/縮量下跌 → 正分
    縮量上漲/放量下跌 → 給分較低（需配合價格方向，這裡只看量能強度）
    """
    if volume_ratio is None:
        return 0, "無法判斷（成交量數據缺失）"

    if volume_ratio >= 2.0:
        return 3, f"量能大幅放大（{volume_ratio}x），市場關注度高"
    elif volume_ratio >= 1.5:
        return 2, f"量能放大（{volume_ratio}x），動能增強"
    elif volume_ratio >= 0.8:
        return 1, f"量能正常（{volume_ratio}x）"
    elif volume_ratio >= 0.5:
        return -1, f"量能萎縮（{volume_ratio}x），動能不足"
    else:
        return -3, f"量能極度萎縮（{volume_ratio}x），市場觀望"


def get_technical_summary(close, ma5, ma10, ma20, ma60) -> str:
    """
    根據均線位置輸出一句話的技術面描述
    （用在最終報告的摘要）
    """
    if close is None or ma20 is None:
        return "技術數據不足，無法判斷"

    if close > ma20 and ma5 and ma5 > ma20:
        if ma60 and close > ma60:
            return "多頭格局，站上所有均線"
        else:
            return "中短期偏多，但仍在季線壓力下"
    elif close < ma20:
        if ma60 and close < ma60:
            return "空頭格局，跌破所有均線"
        else:
            return "中短期偏弱，跌破月線"
    else:
        return "整理格局，均線糾結"


def calculate_technical_score(stock_data: dict) -> dict:
    """
    輸入：stock_data（來自 stock_data.py 的 dict）
    輸出：包含各項技術分數、總分、描述的 dict
    """
    close        = stock_data.get("close")
    ma5          = stock_data.get("ma5")
    ma10         = stock_data.get("ma10")
    ma20         = stock_data.get("ma20")
    ma60         = stock_data.get("ma60")
    rsi          = stock_data.get("rsi")
    volume_ratio = stock_data.get("volume_ratio")

    pos_score,  pos_desc  = score_ma_position(close, ma5, ma10, ma20, ma60)
    align_score, align_desc = score_ma_alignment(ma5, ma10, ma20, ma60)
    rsi_score,  rsi_desc  = score_rsi(rsi)
    vol_score,  vol_desc  = score_volume(volume_ratio)

    total = pos_score + align_score + rsi_score + vol_score
    total = max(-25, min(25, total))  # 限制在 -25 ~ +25

    summary = get_technical_summary(close, ma5, ma10, ma20, ma60)

    return {
        "technical_score" : total,
        "summary"         : summary,
        "breakdown": {
            "均線位置": {"score": pos_score,   "desc": pos_desc},
            "均線排列": {"score": align_score,  "desc": align_desc},
            "RSI狀態" : {"score": rsi_score,   "desc": rsi_desc},
            "成交量"  : {"score": vol_score,   "desc": vol_desc},
        }
    }


# ── 測試用 ───────────────────────────────────────────
if __name__ == "__main__":
    from stock_data import get_stock_data

    ticker = input("請輸入股票代號（例如 TSLA）：").strip().upper()
    print(f"\n📡 正在抓取 {ticker} 數據...\n")

    stock_data = get_stock_data(ticker)
    result     = calculate_technical_score(stock_data)

    print(f"【{ticker} 技術面評分結果】")
    print(f"\n  技術面總分  : {result['technical_score']:+d} 分（範圍 -25 ~ +25）")
    print(f"  技術面摘要  : {result['summary']}")
    print(f"\n  ── 分項明細 ──")
    for name, item in result["breakdown"].items():
        print(f"  {name:8s} : {item['score']:+3d} 分  │  {item['desc']}")