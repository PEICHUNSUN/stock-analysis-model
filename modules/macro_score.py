# modules/macro_score.py
# 模組二：根據總經數據計算 Macro Score，判斷市場模式與建議倉位

# ── 倉位設定 ────────────────────────────────────────
# 未來開始做槓桿/做空時，把 enable_leverage 改成 True
# True  → 最高倉位可到 120%
# False → 最高倉位上限 100%
enable_leverage = False

# ── 評分門檻（可自行調整）────────────────────────────
THRESHOLDS = {
    # CPI 年增率（%）：通膨越低越好
    "CPI_YoY": {
        "excellent": 2.0,   # <= 2.0 → 滿分 25
        "good":      3.0,   # <= 3.0 → 18分
        "neutral":   4.0,   # <= 4.0 → 10分
        "bad":       5.5,   # <= 5.5 → 3分
                            # >  5.5 → 0分
    },
    # 10年期公債殖利率（%）：越低越好
    "10Y_Yield": {
        "excellent": 3.5,   # <= 3.5 → 滿分 20
        "good":      4.0,   # <= 4.0 → 14分
        "neutral":   4.5,   # <= 4.5 → 8分
        "bad":       5.0,   # <= 5.0 → 3分
                            # >  5.0 → 0分
    },
    # 失業率（%）：越低越好
    "Unemployment": {
        "excellent": 4.0,   # <= 4.0 → 滿分 20
        "good":      4.5,   # <= 4.5 → 14分
        "neutral":   5.5,   # <= 5.5 → 8分
        "bad":       6.5,   # <= 6.5 → 3分
                            # >  6.5 → 0分
    },
    # OECD 商業信心指數 BSCI（> 100 = 擴張，類比 PMI > 50）
    # 註：ISM PMI 在 2017 年從 FRED 撤下（付費），BSCI 是免費替代
    "Business_Confidence": {
        "excellent": 101.0, # >= 101 → 滿分 15
        "good":      100.0, # >= 100 → 10分
        "neutral":   99.0,  # >= 99  → 5分
        "bad":       97.0,  # >= 97  → 2分
                            # <  97  → 0分
    },
    # VIX 恐慌指數：越低越好
    "VIX": {
        "excellent": 15.0,  # <= 15 → 滿分 20
        "good":      20.0,  # <= 20 → 14分
        "neutral":   25.0,  # <= 25 → 8分
        "bad":       30.0,  # <= 30 → 3分
                            # >  30 → 0分
    },
}

# ── 市場模式對應表（可自行調整門檻）─────────────────
MARKET_MODE_THRESHOLDS = {
    75: "Risk-on",
    60: "偏多",
    45: "Neutral",
    30: "Risk-off",
    0:  "強Risk-off",
}

# ── 倉位建議對應表 ────────────────────────────────────
# 格式：(Macro Score 下限, 基礎倉位%, VIX 25-30時%, VIX > 30時%)
POSITION_TABLE = [
    (80, 100, 75, 50),
    (60,  85, 60, 35),
    (45,  65, 45, 25),
    (35,  35, 20, 10),
    (0,   10, 10, 10),
]


def score_cpi(cpi_yoy: float) -> int:
    t = THRESHOLDS["CPI_YoY"]
    if cpi_yoy <= t["excellent"]: return 25
    if cpi_yoy <= t["good"]:      return 18
    if cpi_yoy <= t["neutral"]:   return 10
    if cpi_yoy <= t["bad"]:       return 3
    return 0


def score_yield(yield_10y: float) -> int:
    t = THRESHOLDS["10Y_Yield"]
    if yield_10y <= t["excellent"]: return 20
    if yield_10y <= t["good"]:      return 14
    if yield_10y <= t["neutral"]:   return 8
    if yield_10y <= t["bad"]:       return 3
    return 0


def score_unemployment(unemployment: float) -> int:
    t = THRESHOLDS["Unemployment"]
    if unemployment <= t["excellent"]: return 20
    if unemployment <= t["good"]:      return 14
    if unemployment <= t["neutral"]:   return 8
    if unemployment <= t["bad"]:       return 3
    return 0


def score_business_confidence(bci: float) -> int:
    """OECD BSCI 評分（替代 ISM PMI，因為 PMI 已從 FRED 撤下）"""
    t = THRESHOLDS["Business_Confidence"]
    if bci >= t["excellent"]: return 15
    if bci >= t["good"]:      return 10
    if bci >= t["neutral"]:   return 5
    if bci >= t["bad"]:       return 2
    return 0


def score_vix(vix: float) -> int:
    t = THRESHOLDS["VIX"]
    if vix <= t["excellent"]: return 20
    if vix <= t["good"]:      return 14
    if vix <= t["neutral"]:   return 8
    if vix <= t["bad"]:       return 3
    return 0


def get_market_mode(macro_score: int) -> str:
    """根據 Macro Score 判斷市場模式"""
    for threshold, mode in sorted(MARKET_MODE_THRESHOLDS.items(), reverse=True):
        if macro_score >= threshold:
            return mode
    return "強Risk-off"


def get_position_advice(macro_score: int, vix: float) -> dict:
    """
    根據 Macro Score 與 VIX 計算建議倉位
    回傳：目前建議倉位、VIX 警示說明
    """
    # 找出對應的倉位區間
    base, vix_mid, vix_high = 10, 10, 10
    for threshold, b, m, h in POSITION_TABLE:
        if macro_score >= threshold:
            base, vix_mid, vix_high = b, m, h
            break

    # 套用槓桿上限
    max_position = 120 if enable_leverage else 100
    base    = min(base, max_position)
    vix_mid = min(vix_mid, max_position)

    # 根據現在的 VIX 決定目前建議倉位
    if vix > 30:
        current = vix_high
        vix_status = f"⚠️  VIX {vix:.1f} 偏高（> 30），建議降至 {vix_high}%"
    elif vix > 25:
        current = vix_mid
        vix_status = f"⚠️  VIX {vix:.1f} 略高（> 25），建議降至 {vix_mid}%"
    else:
        current = base
        vix_status = f"✅ VIX {vix:.1f} 正常"

    return {
        "current_position" : current,
        "base_position"    : base,
        "vix_mid_position" : vix_mid,
        "vix_high_position": vix_high,
        "vix_status"       : vix_status,
    }


def calculate_macro_score(macro_data: dict) -> dict:
    """
    輸入：macro_data（來自 macro_data.py 的 dict）
    輸出：包含各項分數、總分、市場模式、倉位建議的 dict
    """

    # 安全取值：API 抓不到（None）時用中性預設值，避免崩潰
    # 用 `is None` 而非 `or`，這樣「真實值剛好是 0」不會被誤判為缺失
    # （例如 CPI YoY = 0 的零通膨情境）
    def _safe(value, default):
        return default if value is None else value

    cpi_yoy      = _safe(macro_data.get("CPI_YoY"),             3.5)
    yield_10y    = _safe(macro_data.get("10Y_Yield"),           4.5)
    unemployment = _safe(macro_data.get("Unemployment"),        4.5)
    bci          = _safe(macro_data.get("Business_Confidence"), 99.5)
    vix          = _safe(macro_data.get("VIX"),                 20.0)

    # 計算各項分數
    scores = {
        "CPI分數"      : score_cpi(cpi_yoy),
        "殖利率分數"    : score_yield(yield_10y),
        "失業率分數"    : score_unemployment(unemployment),
        "商業信心分數"  : score_business_confidence(bci),
        "VIX分數"      : score_vix(vix),
    }

    macro_score     = sum(scores.values())
    market_mode     = get_market_mode(macro_score)
    position_advice = get_position_advice(macro_score, vix)

    return {
        "scores"          : scores,
        "macro_score"     : macro_score,
        "market_mode"     : market_mode,
        "position_advice" : position_advice,
    }


# ── 測試用（直接執行這個檔案時才會跑）──────────────────
if __name__ == "__main__":
    from macro_data import get_macro_data

    print("📡 正在抓取總經數據...\n")
    macro_data = get_macro_data()

    print("⚙️  計算 Macro Score...\n")
    result = calculate_macro_score(macro_data)

    print("【Macro Score 結果】")
    for name, score in result["scores"].items():
        print(f"  {name:12s} : {score} 分")

    print(f"\n  總分        : {result['macro_score']} / 100")
    print(f"  市場模式    : {result['market_mode']}")

    pa = result["position_advice"]
    print(f"\n【倉位建議】")
    print(f"  目前建議倉位 : {pa['current_position']}%")
    print(f"  {pa['vix_status']}")
    print(f"  若 VIX 升至 25+，建議降至 {pa['vix_mid_position']}%")
    print(f"  若 VIX 升至 30+，建議降至 {pa['vix_high_position']}%")