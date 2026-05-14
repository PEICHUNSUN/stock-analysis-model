# main.py
# 股票分析模型 - 主程式入口
# 整合所有模組，從輸入股票代號到輸出完整分析報告

import sys
import time
from datetime import datetime

# 導入所有模組
from modules.macro_data import get_macro_data
from modules.macro_score import calculate_macro_score
from modules.stock_data import get_stock_data
from modules.technical_score import calculate_technical_score
from modules.company_score import calculate_final_score
from modules.ai_report import generate_report_simple


def print_header():
    """打印歡迎畫面"""
    print("\n" + "="*60)
    print("📊 股票分析模型 v1.0")
    print("="*60)
    print("結合總體經濟、個股基本面、技術面的智能投資決策系統")
    print("="*60 + "\n")


def print_section(title: str):
    """打印分段標題"""
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def save_report(ticker: str, report: str):
    """將報告存到檔案"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"output/{ticker}_{timestamp}_report.txt"
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✅ 報告已存檔：{filename}")
    except Exception as e:
        print(f"\n⚠️  存檔失敗：{e}")


def main():
    """主程式"""
    print_header()

    # ── Step 1：使用者輸入 ──────────────────────────
    ticker = input("請輸入股票代號（例如 TSLA、NVDA、AAPL）：").strip().upper()
    
    if not ticker:
        print("❌ 代號不能為空！")
        sys.exit(1)

    print(f"\n🔍 分析股票：{ticker}")

    # ── Step 2：抓取總經數據 ──────────────────────────
    print_section("Step 1：分析總體經濟環境")
    print("📡 正在抓取總經數據...")
    
    try:
        macro_data = get_macro_data()
        print("✅ 總經數據抓取成功")
    except Exception as e:
        print(f"❌ 總經數據抓取失敗：{e}")
        sys.exit(1)

    # ── Step 3：計算 Macro Score ──────────────────────
    print("⚙️  計算 Macro Score...")
    macro_result = calculate_macro_score(macro_data)
    
    print(f"  Macro Score：{macro_result['macro_score']} / 100")
    print(f"  市場模式：{macro_result['market_mode']}")
    print(f"  建議倉位：{macro_result['position_advice']['current_position']}%")

    # ── Step 4：抓取個股數據 ──────────────────────────
    print_section("Step 2-3：分析個股基本面與技術面")
    print(f"📋 正在抓取 {ticker} 數據...")
    
    try:
        stock_data = get_stock_data(ticker)
        print(f"✅ 數據抓取成功：{stock_data.get('company_name', ticker)}")
    except Exception as e:
        print(f"❌ 個股數據抓取失敗：{e}")
        sys.exit(1)

    # ── Step 5：計算技術面評分 ──────────────────────
    print("⚙️  計算技術面評分...")
    tech_result = calculate_technical_score(stock_data)
    print(f"  技術面分數：{tech_result['technical_score']:+d} 分")
    print(f"  {tech_result['summary']}")

    # ── Step 6：計算綜合評分 ──────────────────────────
    print_section("Step 4-7：計算綜合評分")
    print("⚙️  整合所有評分...")
    
    try:
        score_result = calculate_final_score(ticker, macro_result, tech_result, stock_data)
        print(f"  Final Score：{score_result['final_score']} 分")
        print(f"  投資建議：{score_result['recommendation']}")
    except Exception as e:
        print(f"❌ 評分計算失敗：{e}")
        sys.exit(1)

    # ── Step 9：突發事件（可選）──────────────────────
    print_section("Step 9：突發事件調整（選填）")
    print("是否有突發事件要加入分析？（直接按 Enter 跳過）")
    event_context = input("事件描述：").strip()

    # ── Step 8：生成報告 ──────────────────────────────
    print_section("生成最終分析報告")
    print("📄 正在生成報告...")
    time.sleep(1)
    
    try:
        report = generate_report_simple(
            ticker        = ticker,
            macro_data    = macro_data,
            macro_result  = macro_result,
            stock_data    = stock_data,
            tech_result   = tech_result,
            score_result  = score_result,
            event_context = event_context,
        )
        print("✅ 報告生成成功\n")
    except Exception as e:
        print(f"❌ 報告生成失敗：{e}")
        sys.exit(1)

    # ── 輸出報告 ──────────────────────────────────────
    print("="*60)
    print(report)
    print("="*60)

    # ── 詢問是否存檔 ──────────────────────────────────
    save_choice = input("\n💾 是否存檔報告？(y/n)：").strip().lower()
    if save_choice == "y":
        save_report(ticker, report)

    print("\n✅ 分析完成！感謝使用 📊\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  使用者中斷程式執行")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 發生錯誤：{e}")
        sys.exit(1)