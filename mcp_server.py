# mcp_server.py
# 把現有的股票分析模型包成 MCP Server，讓 Claude Desktop / Claude Code 可以呼叫。
#
# 設計原則：這個檔案只做「轉接」，不放任何業務邏輯。
#   - 業務邏輯仍在 modules/ 裡，保持可獨立測試
#   - 這層只負責：把 Python dict 轉成 MCP 可序列化格式、處理錯誤、寫好 docstring 給 LLM 看

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Claude Desktop 啟動 MCP server 時，cwd 不一定是專案目錄。
# 用 __file__ 自己定位，確保：(1) .env 抓得到、(2) modules 找得到、(3) DB 路徑正確
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)  # company_score.py 用相對路徑找 stock_database.json

from mcp.server.fastmcp import FastMCP

from modules.macro_data    import get_macro_data
from modules.macro_score   import calculate_macro_score
from modules.stock_data    import get_stock_data
from modules.technical_score import calculate_technical_score
from modules.company_score import calculate_final_score, load_stock_db
from modules.ai_report     import generate_report_simple


mcp = FastMCP(
    "stock-analysis-model",
    instructions=(
        "提供美股的多層次評分分析：總體經濟環境（Macro）、個股基本面（Company）、技術面（Technical）。"
        "適用於『分析某支股票』、『現在市場環境如何』、『多支股票比較』等問題。"
        "注意：這是量化框架的客觀輸出，不是投資建議。"
    ),
)


@mcp.tool()
def get_macro_status() -> dict:
    """
    回傳當下美國總體經濟環境的完整評分。
    不需要 ticker。適合回答「現在市場環境如何」、「該不該重倉」這類總體問題。

    回傳：
        macro_score (0-100)、market_mode（Risk-on / 偏多 / Neutral / Risk-off / 強Risk-off）、
        各指標分數明細、建議倉位（含 VIX 動態調整）。
    """
    macro_data   = get_macro_data()
    macro_result = calculate_macro_score(macro_data)
    return {
        "raw_indicators" : macro_data,
        "scores"         : macro_result["scores"],
        "macro_score"    : macro_result["macro_score"],
        "market_mode"    : macro_result["market_mode"],
        "position_advice": macro_result["position_advice"],
    }


@mcp.tool()
def score_stock(ticker: str) -> dict:
    """
    回傳指定股票的「純評分」結果（不生成文字報告，比 analyze_stock 快）。
    適合：多支股票比較、批次評分、需要結構化資料而非文字報告的場景。

    Args:
        ticker: 美股代號，例如 "TSLA"、"NVDA"、"AAPL"。

    回傳：
        final_score (0-100)、recommendation、各層評分分解
        （macro_scaled、macro_adj、company_adj、tech_score）、技術面摘要。
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return {"error": "ticker 不能為空"}

    try:
        macro_data   = get_macro_data()
        macro_result = calculate_macro_score(macro_data)
        stock_data   = get_stock_data(ticker)
        tech_result  = calculate_technical_score(stock_data)
        score_result = calculate_final_score(ticker, macro_result, tech_result, stock_data)
    except Exception as e:
        return {"error": f"評分失敗：{e}", "ticker": ticker}

    return {
        "ticker"          : ticker,
        "company_name"    : stock_data.get("company_name", ticker),
        "final_score"     : score_result["final_score"],
        "recommendation"  : score_result["recommendation"],
        "breakdown": {
            "macro_scaled"    : score_result["macro_scaled"],
            "macro_adj"       : score_result["macro_adj"],
            "macro_adj_desc"  : score_result["macro_adj_desc"],
            "company_adj"     : score_result["company_adj"],
            "company_adj_desc": score_result["company_adj_desc"],
            "tech_score"      : score_result["tech_score"],
            "tech_summary"    : score_result["tech_summary"],
        },
        "fundamentals": {
            "pe_ratio"    : stock_data.get("pe_ratio"),
            "eps"         : stock_data.get("eps"),
            "gross_margin": stock_data.get("gross_margin"),
            "market_cap"  : stock_data.get("market_cap"),
        },
        "market_mode": score_result["market_mode"],
        "note"       : score_result.get("note", ""),
    }


@mcp.tool()
def analyze_stock(ticker: str, event_context: str = "") -> dict:
    """
    完整分析：總經 + 個股基本面 + 技術面，並生成自然語言報告。
    適合：「幫我分析 TSLA」這類完整需求。比 score_stock 慢但內容最完整。

    Args:
        ticker: 美股代號，例如 "TSLA"。
        event_context: 選填。若使用者提到的突發事件（例如「Fed 剛升息」、「公司財報利多」）
                       可傳入，會被附加在報告末尾的「突發事件影響分析」段落。

    回傳：
        包含完整評分（同 score_stock）+ 自然語言 report 字串 + 倉位建議。
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return {"error": "ticker 不能為空"}

    try:
        macro_data   = get_macro_data()
        macro_result = calculate_macro_score(macro_data)
        stock_data   = get_stock_data(ticker)
        tech_result  = calculate_technical_score(stock_data)
        score_result = calculate_final_score(ticker, macro_result, tech_result, stock_data)
        report = generate_report_simple(
            ticker        = ticker,
            macro_data    = macro_data,
            macro_result  = macro_result,
            stock_data    = stock_data,
            tech_result   = tech_result,
            score_result  = score_result,
            event_context = event_context,
        )
    except Exception as e:
        return {"error": f"分析失敗：{e}", "ticker": ticker}

    return {
        "ticker"         : ticker,
        "company_name"   : stock_data.get("company_name", ticker),
        "final_score"    : score_result["final_score"],
        "recommendation" : score_result["recommendation"],
        "market_mode"    : macro_result["market_mode"],
        "position_advice": macro_result["position_advice"],
        "report"         : report,
    }


@mcp.tool()
def list_supported_stocks() -> list[dict]:
    """
    列出資料庫中已有屬性標註的股票（這些股票的 Macro Adjustment 會更準）。
    其他股票仍可用 analyze_stock / score_stock 分析，但會以基本面 API 數據為主、
    缺少質性屬性（Growth / Defensive 等）的調整。
    """
    db = load_stock_db()
    return [
        {
            "ticker"    : ticker,
            "name"      : info.get("name", ""),
            "attributes": info.get("attributes", []),
            "notes"     : info.get("notes", ""),
        }
        for ticker, info in db.get("stocks", {}).items()
    ]


if __name__ == "__main__":
    # Claude Desktop / Claude Code 透過 stdio transport 連線
    mcp.run(transport="stdio")
