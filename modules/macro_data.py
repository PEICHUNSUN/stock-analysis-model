# modules/macro_data.py
# 模組一：抓取總體經濟數據
# 數據來源：FRED API + yfinance（VIX）

import os
from dotenv import load_dotenv
from fredapi import Fred
import yfinance as yf
import pandas as pd

# 載入 .env 裡的 API Key
load_dotenv()


def get_macro_data() -> dict:
    """
    從 FRED 抓取總經指標，從 yfinance 抓 VIX
    回傳一個 dict，包含所有指標的最新數值
    """

    fred = Fred(api_key=os.getenv("FRED_API_KEY"))

    # ── FRED 指標對照表 ──────────────────────────────
    # 代號說明：
    #   CPIAUCSL   → CPI（消費者物價指數，年增率需自己算）
    #   GS10       → 10年期公債殖利率
    #   UNRATE     → 失業率
    #   NAPM       → ISM 製造業 PMI
    #   RSAFS      → 零售銷售額
    #   GDP        → 美國 GDP（季度，較慢更新）
    # ────────────────────────────────────────────────
    # 註：Business_Confidence 用 OECD BSCI 而非 ISM PMI，
    # 因為 ISM 在 2017 年將 PMI 從 FRED 撤下（變付費）。
    # BSCI 與 PMI 概念類似（>100 = 擴張，類比 PMI > 50），但 OECD 更新頻率較慢。
    fred_series = {
        "CPI"                : "CPIAUCSL",
        "10Y_Yield"          : "GS10",
        "Unemployment"       : "UNRATE",
        "Business_Confidence": "BSCICP03USM665S",
        "Retail_Sales"       : "RSAFS",
        "GDP"                : "GDP",
        "VIX"                : "VIXCLS",
    }

    result = {}

    # 抓 FRED 數據
    for name, series_id in fred_series.items():
        try:
            series = fred.get_series(series_id)        # 抓整段歷史
            latest_value = series.dropna().iloc[-1]    # 取最新一筆（忽略空值）
            result[name] = round(float(latest_value), 4)
        except Exception as e:
            print(f"⚠️  無法抓取 {name}（{series_id}）：{e}")
            result[name] = None

    # 計算 CPI 年增率（YoY %）
    # 原始 CPI 是指數值，我們需要的是「跟去年同期相比漲了多少 %」
    try:
        cpi_series = fred.get_series("CPIAUCSL").dropna()
        cpi_yoy = (cpi_series.iloc[-1] / cpi_series.iloc[-13] - 1) * 100
        result["CPI_YoY"] = round(float(cpi_yoy), 4)
    except Exception as e:
        print(f"⚠️  無法計算 CPI 年增率：{e}")
        result["CPI_YoY"] = None

    return result


# ── 測試用（直接執行這個檔案時才會跑）──────────────────
if __name__ == "__main__":
    print("📡 正在抓取總經數據...\n")
    data = get_macro_data()

    print("【總經數據結果】")
    for key, value in data.items():
        print(f"  {key:20s} : {value}")