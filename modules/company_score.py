# modules/company_score.py
# 模組五：個股綜合評分
# 整合 Macro Score + Macro Adjustment + Company Adjustment + Technical Score
# 輸出 Final Score 與投資建議

import json
import os

# 載入股票資料庫
DB_PATH = os.path.join(os.path.dirname(__file__), "../config/stock_database.json")

# ── 從真實基本面數據推導 adjustments 的門檻 ─────────────
# profitable / high_valuation 直接從 API 數據判斷，
# ai_narrative / high_competition 屬於質性判斷，仍從資料庫讀
FUNDAMENTAL_THRESHOLDS = {
    "profitable_eps_min" : 0.0,   # EPS > 0 → 視為獲利
    "high_valuation_pe"  : 30.0,  # PE > 30 → 視為高估值
}

def load_stock_db() -> dict:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_macro_adjustment(ticker: str, market_mode: str, db: dict) -> tuple[int, str]:
    """
    根據市場模式 × 股票屬性，計算 Macro Adjustment
    例如：Risk-on 環境下，Growth 股加分、Defensive 股扣分
    """
    stocks = db.get("stocks", {})
    macro_adj_table = db.get("macro_adjustment", {})

    if ticker not in stocks:
        return 0, f"⚠️  {ticker} 不在資料庫中，Macro Adjustment = 0"

    stock_info  = stocks[ticker]
    attributes  = stock_info.get("attributes", [])
    mode_table  = macro_adj_table.get(market_mode, {})

    total = 0
    details = []
    for attr in attributes:
        score = mode_table.get(attr, 0)
        total += score
        details.append(f"{attr} {score:+d}")

    desc = f"市場模式「{market_mode}」× 屬性（{', '.join(details)}）= {total:+d}"
    return total, desc


def derive_adjustments(stock_data: dict, db_adjustments: dict) -> dict:
    """
    優先用真實 API 數據判斷 profitable / high_valuation；
    若數據缺失，fallback 到資料庫的人工標註。
    ai_narrative / high_competition 屬質性判斷，永遠從資料庫讀。
    """
    derived = dict(db_adjustments)  # 先以 DB 為基準

    eps = stock_data.get("eps")
    pe  = stock_data.get("pe_ratio")

    if eps is not None:
        derived["profitable"] = eps > FUNDAMENTAL_THRESHOLDS["profitable_eps_min"]

    # 負 PE 代表公司在虧錢，不應視為「便宜」，跳過 PE 判斷讓 EPS 主導
    if pe is not None and pe > 0:
        derived["high_valuation"] = pe > FUNDAMENTAL_THRESHOLDS["high_valuation_pe"]

    return derived


def get_company_adjustment(
    ticker: str,
    stock_data: dict,
    db: dict,
) -> tuple[int, str]:
    """
    結合真實基本面數據 + 資料庫質性標註，計算 Company Adjustment
    """
    stocks    = db.get("stocks", {})
    adj_score = db.get("adjustment_scores", {})

    db_info        = stocks.get(ticker, {})
    db_adjustments = db_info.get("adjustments", {})
    adjustments    = derive_adjustments(stock_data, db_adjustments)

    eps = stock_data.get("eps")
    pe  = stock_data.get("pe_ratio")

    total   = 0
    details = []

    if adjustments.get("profitable"):
        score = adj_score.get("profitable", 0)
        total += score
        label = f"獲利穩定（EPS {eps:.2f}）" if eps is not None else "獲利穩定"
        details.append(f"{label} {score:+d}")

    if adjustments.get("ai_narrative"):
        score = adj_score.get("ai_narrative", 0)
        total += score
        details.append(f"AI/成長敘事 {score:+d}")

    if adjustments.get("high_valuation"):
        score = adj_score.get("high_valuation", 0)
        total += score
        label = f"高估值（PE {pe:.1f}x）" if pe is not None and pe > 0 else "高估值"
        details.append(f"{label} {score:+d}")

    if adjustments.get("high_competition"):
        score = adj_score.get("high_competition", 0)
        total += score
        details.append(f"高競爭 {score:+d}")

    if not details:
        if ticker not in stocks and eps is None and pe is None:
            return 0, f"⚠️  {ticker} 不在資料庫且基本面數據缺失，Company Adjustment = 0"
        return 0, "無特殊調整 = 0"

    return total, "、".join(details) + f" = {total:+d}"


def get_investment_recommendation(final_score: int) -> str:
    """根據 Final Score 輸出投資建議"""
    if final_score >= 75:
        return "🟢 Strong Buy（強力買入）"
    elif final_score >= 65:
        return "🟢 Buy（買入）"
    elif final_score >= 55:
        return "🟡 Watch+（積極觀察）"
    elif final_score >= 45:
        return "🟡 Watch（觀察）"
    elif final_score >= 35:
        return "🟠 Cautious（謹慎）"
    else:
        return "🔴 Avoid（避開）"


def calculate_final_score(
    ticker       : str,
    macro_result : dict,   # 來自 macro_score.py 的輸出
    technical_result: dict, # 來自 technical_score.py 的輸出
    stock_data   : dict,   # 來自 stock_data.py 的輸出（提供真實基本面）
) -> dict:
    """
    整合所有評分，計算 Final Score
    
    Final Score =
        Macro Score (0~100, 縮放為 0~50)
        + Macro Adjustment
        + Company Adjustment
        + Technical Score (-25~+25)
    """
    db = load_stock_db()

    macro_score   = macro_result.get("macro_score", 50)
    market_mode   = macro_result.get("market_mode", "Neutral")
    tech_score    = technical_result.get("technical_score", 0)
    tech_summary  = technical_result.get("summary", "")

    # Macro Score 縮放：原本 0-100，縮放成 0-50 避免 Macro 權重過大
    macro_scaled = round(macro_score * 0.5)

    # 各項調整分
    macro_adj, macro_adj_desc   = get_macro_adjustment(ticker, market_mode, db)
    company_adj, company_adj_desc = get_company_adjustment(ticker, stock_data, db)

    # 計算 Final Score
    final_score = macro_scaled + macro_adj + company_adj + tech_score

    # 限制在 0 ~ 100
    final_score = max(0, min(100, final_score))

    recommendation = get_investment_recommendation(final_score)

    # 取得股票備註
    note = db.get("stocks", {}).get(ticker, {}).get("notes", "")

    return {
        "ticker"          : ticker,
        "market_mode"     : market_mode,
        "macro_score"     : macro_score,
        "macro_scaled"    : macro_scaled,
        "macro_adj"       : macro_adj,
        "macro_adj_desc"  : macro_adj_desc,
        "company_adj"     : company_adj,
        "company_adj_desc": company_adj_desc,
        "tech_score"      : tech_score,
        "tech_summary"    : tech_summary,
        "final_score"     : final_score,
        "recommendation"  : recommendation,
        "note"            : note,
    }


# ── 測試用 ───────────────────────────────────────────
if __name__ == "__main__":
    from macro_data import get_macro_data
    from macro_score import calculate_macro_score
    from stock_data import get_stock_data
    from technical_score import calculate_technical_score

    ticker = input("請輸入股票代號（例如 TSLA）：").strip().upper()
    print(f"\n📡 正在抓取數據...\n")

    macro_data   = get_macro_data()
    macro_result = calculate_macro_score(macro_data)

    print(f"  📋 抓取個股數據...")
    stock_data   = get_stock_data(ticker)
    tech_result  = calculate_technical_score(stock_data)

    result = calculate_final_score(ticker, macro_result, tech_result, stock_data)

    print(f"\n{'='*50}")
    print(f"【{ticker} 綜合評分結果】")
    print(f"{'='*50}")
    print(f"\n  🌍 市場模式      : {result['market_mode']}")
    print(f"\n  ── 分數組成 ──")
    print(f"  Macro Score     : {result['macro_score']} × 0.5 = {result['macro_scaled']:+d} 分")
    print(f"  Macro Adjustment: {result['macro_adj']:+d} 分  │  {result['macro_adj_desc']}")
    print(f"  Company Adj     : {result['company_adj']:+d} 分  │  {result['company_adj_desc']}")
    print(f"  Technical Score : {result['tech_score']:+d} 分  │  {result['tech_summary']}")
    print(f"\n  {'─'*40}")
    print(f"  Final Score     : {result['final_score']} 分")
    print(f"  投資建議        : {result['recommendation']}")
    if result['note']:
        print(f"\n  📝 備註          : {result['note']}")

    pa = macro_result.get("position_advice", {})
    print(f"\n  💼 建議倉位      : {pa.get('current_position')}%")
    print(f"  {pa.get('vix_status', '')}")