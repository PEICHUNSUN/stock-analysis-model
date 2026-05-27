# modules/ai_report.py
# 模組六：簡化版 AI 報告生成（不需要 API，完全免費）
# 使用樣板 + 邏輯判斷自動生成投資分析報告

def get_macro_analysis(macro_data: dict, macro_result: dict) -> str:
    """根據 Macro 數據生成環境分析"""
    market_mode = macro_result.get("market_mode", "Neutral")
    macro_score = macro_result.get("macro_score", 50)
    cpi_yoy = macro_data.get("CPI_YoY")
    vix = macro_data.get("VIX")

    if market_mode == "Risk-on":
        mode_desc = "風險資產偏好強，市場情緒樂觀"
        outlook = "有利於成長股與周期股表現"
    elif market_mode == "偏多":
        mode_desc = "經濟基本面溫和向好，市場情緒中性偏多"
        outlook = "適合均衡配置"
    elif market_mode == "Neutral":
        mode_desc = "總經環境處於平衡狀態，多空力道相當"
        outlook = "需要關注技術面與個股基本面"
    elif market_mode == "Risk-off":
        mode_desc = "經濟信號轉弱，市場風險偏好下降"
        outlook = "防禦性資產相對走強"
    else:  # 強 Risk-off
        mode_desc = "總經環境明顯惡化，市場陷入恐慌"
        outlook = "建議規避風險，增加現金部位"

    inflation_status = "通膨仍高" if cpi_yoy and cpi_yoy > 3.5 else "通膨回落中"
    risk_status = "市場恐慌" if vix and vix > 25 else "市場平靜"

    return f"""{mode_desc}。{inflation_status}，{risk_status}。{outlook}。"""


def get_technical_analysis(stock_data: dict, tech_result: dict) -> str:
    """根據技術數據生成技術分析"""
    close = stock_data.get("close")
    ma5 = stock_data.get("ma5")
    ma20 = stock_data.get("ma20")
    ma60 = stock_data.get("ma60")
    rsi = stock_data.get("rsi")
    tech_summary = tech_result.get("summary", "")

    position_analysis = ""
    if close and ma20:
        if close > ma20:
            if ma5 and ma5 > ma20:
                position_analysis = "價格站在月線上方，短期均線向上排列"
            else:
                position_analysis = "價格突破月線，多頭啟動"
        else:
            position_analysis = "價格跌破月線，空頭警訊"
    
    rsi_analysis = ""
    if rsi:
        if rsi > 70:
            rsi_analysis = "RSI 超買區，短期風險較高"
        elif rsi > 55:
            rsi_analysis = "RSI 處於多頭健康區間"
        elif rsi > 45:
            rsi_analysis = "RSI 中性"
        else:
            rsi_analysis = "RSI 偏弱，有反彈空間"

    return f"{position_analysis}。{rsi_analysis}。{tech_summary}。"


def get_scenario_bullish(ticker: str, stock_data: dict, high_20d: float, close: float) -> str:
    """
    多頭情境：給一個機械式的「短期上檔目標」。
    註：這不是真正的技術壓力位（那需要分析歷史高點、整數關卡、量價結構等）。
    這裡只是「近 20 日高點 +5%」的簡單估算，明示計算方式避免誤導。
    """
    if high_20d and close:
        target = round(high_20d * 1.05, 2)
        return (
            f"若多頭延續，{ticker} 短期上檔目標約 ${target}"
            f"（估算方式：近 20 日高點 ${high_20d} × 1.05，**非真實技術壓力位**）。"
            f"建議持股待漲，並依個人策略設定停損。"
        )
    else:
        return f"若多頭延續，{ticker} 應繼續挑戰更高位置。建議持股，設定合理停損保護利潤。"


def get_scenario_bearish(ticker: str, stock_data: dict, low_20d: float, close: float) -> str:
    """
    反轉情境：給一個機械式的「短期下檔風險區」。
    同上，這不是真正的技術支撐位，只是「近 20 日低點 -5%」的簡單估算。
    """
    if low_20d and close:
        risk_zone = round(low_20d * 0.95, 2)
        return (
            f"若反轉確認，{ticker} 短期下檔風險區約 ${risk_zone}"
            f"（估算方式：近 20 日低點 ${low_20d} × 0.95，**非真實技術支撐位**）。"
            f"建議減少倉位，跌破近期低點應重新評估。"
        )
    else:
        return f"若反轉確認，{ticker} 應迅速下跌。建議立即減倉，設定嚴格停損。"


def get_score_narrative(
    score_result: dict,
    macro_result: dict,
    stock_data:   dict,
) -> str:
    """
    根據實際分數與基本面動態生成「評分主導因素」的描述。
    取代原本寫死的「主要受到技術面的支撐...」那一段。
    """
    macro_scaled = score_result.get("macro_scaled", 25)
    macro_adj    = score_result.get("macro_adj", 0)
    company_adj  = score_result.get("company_adj", 0)
    tech_score   = score_result.get("tech_score", 0)
    market_mode  = macro_result.get("market_mode", "Neutral")

    # macro_scaled 範圍 0~50，以 25 為中性點換算成「相對貢獻」
    contributions = [
        ("Macro 環境",  macro_scaled - 25),
        ("市場模式調整", macro_adj),
        ("公司基本面",   company_adj),
        ("技術面",      tech_score),
    ]
    biggest = max(contributions, key=lambda x: abs(x[1]))

    if biggest[1] >= 5:
        first = f"本次評分主要受到{biggest[0]}的支撐（{biggest[1]:+d} 分）"
    elif biggest[1] <= -5:
        first = f"本次評分主要受到{biggest[0]}的拖累（{biggest[1]:+d} 分）"
    else:
        first = "各項分數接近中性，無明顯主導因素"

    second = f"Macro 環境處於 {market_mode}"

    # 第三句：根據真實 PE / EPS 描述基本面風險
    pe  = stock_data.get("pe_ratio")
    eps = stock_data.get("eps")
    concerns = []
    if eps is not None and eps <= 0:
        concerns.append("尚未獲利")
    if pe is not None and pe > 50:
        concerns.append(f"估值偏高（PE {pe:.1f}x）")
    elif pe is not None and pe > 30:
        concerns.append(f"估值略貴（PE {pe:.1f}x）")

    if concerns:
        third = "個股基本面需關注：" + "、".join(concerns)
    elif pe is not None and pe > 0 and eps is not None:
        third = f"個股基本面穩健（PE {pe:.1f}x、EPS {eps:.2f}）"
    else:
        third = ""

    parts = [first, second] + ([third] if third else [])
    return "。".join(parts) + "。"


def get_investment_advice(final_score: int, recommendation: str, pa: dict) -> str:
    """投資建議"""
    position = pa.get("current_position", 65)
    vix_status = pa.get("vix_status", "")

    if final_score >= 75:
        action = "積極建立部位，逢低加碼"
    elif final_score >= 65:
        action = "正常配置，可考慮加碼"
    elif final_score >= 55:
        action = "觀察為主，等待更明確訊號"
    elif final_score >= 45:
        action = "保持現有部位，勿追高"
    elif final_score >= 35:
        action = "謹慎持股，考慮減倉"
    else:
        action = "建議規避，增加現金"

    return f"建議倉位：{position}%。{action}。{vix_status}。"


def generate_report_simple(
    ticker          : str,
    macro_data      : dict,
    macro_result    : dict,
    stock_data      : dict,
    tech_result     : dict,
    score_result    : dict,
    event_context   : str = "",
) -> str:
    """
    簡化版報告生成（完全免費，不需要 API）
    使用樣板 + 邏輯判斷自動生成
    """

    pa = macro_result.get("position_advice", {})
    final_score = score_result.get("final_score", 50)
    recommendation = score_result.get("recommendation", "Watch")
    note = score_result.get("note", "")
    high_20d = stock_data.get("high_20d")
    low_20d = stock_data.get("low_20d")
    close = stock_data.get("close")

    # 生成各個段落
    macro_analysis = get_macro_analysis(macro_data, macro_result)
    technical_analysis = get_technical_analysis(stock_data, tech_result)
    score_narrative = get_score_narrative(score_result, macro_result, stock_data)
    scenario_bullish = get_scenario_bullish(ticker, stock_data, high_20d, close)
    scenario_bearish = get_scenario_bearish(ticker, stock_data, low_20d, close)
    investment_advice = get_investment_advice(final_score, recommendation, pa)

    event_section = ""
    if event_context.strip():
        event_section = f"""
【突發事件影響分析】
{event_context}
"""

    report = f"""
【{ticker} 分析報告】

🌍 總體環境
{macro_analysis}

📊 個股評分：{final_score}分（{recommendation}）
{score_narrative}

📈 技術位置
{technical_analysis}

【未來20天情境分析】

✅ 多頭情境（延續機率較高時）
{scenario_bullish}

⚠️ 反轉情境（需注意的訊號）
{scenario_bearish}

【操作建議】
➡️ {investment_advice}

【重要提示】
- 此分析基於模型自動生成，僅供參考，不構成投資建議
- 請根據自身風險承受度與投資目標進行決策
- 定期檢視部位，設置適當的停損/停利點位
{event_section}
免責聲明：本報告僅供教育與學習之用，投資涉及風險，過去績效不代表未來結果。
"""

    if note:
        report = report.replace("【重要提示】", f"【重要提示】\n- {note}")

    return report


# ── 測試用 ───────────────────────────────────────────
if __name__ == "__main__":
    from macro_data import get_macro_data
    from macro_score import calculate_macro_score
    from stock_data import get_stock_data
    from technical_score import calculate_technical_score
    from company_score import calculate_final_score

    ticker = input("請輸入股票代號（例如 TSLA）：").strip().upper()

    print(f"\n📡 正在抓取數據...\n")
    macro_data   = get_macro_data()
    macro_result = calculate_macro_score(macro_data)

    print(f"  📋 抓取個股數據...")
    stock_data   = get_stock_data(ticker)
    tech_result  = calculate_technical_score(stock_data)
    score_result = calculate_final_score(ticker, macro_result, tech_result, stock_data)

    # Step 9：突發事件（選填）
    print(f"\n📝 是否有突發事件要加入分析？（直接按 Enter 跳過）")
    event_context = input("事件描述：").strip()

    print(f"\n📄 正在生成分析報告...\n")
    report = generate_report_simple(
        ticker        = ticker,
        macro_data    = macro_data,
        macro_result  = macro_result,
        stock_data    = stock_data,
        tech_result   = tech_result,
        score_result  = score_result,
        event_context = event_context,
    )

    print("=" * 60)
    print(report)
    print("=" * 60)