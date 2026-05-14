# modules/stock_data.py
# 模組三：抓取個股數據（基本面 + 技術面原始數據）
# 數據來源：全部改用 Alpha Vantage API（穩定、免費）

import os
import time
import requests
import pandas as pd
import ta
from dotenv import load_dotenv

load_dotenv()

AV_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
AV_BASE    = "https://www.alphavantage.co/query"


def _av_get(params: dict, label: str = "") -> dict:
    """
    Alpha Vantage 統一請求函式，含自動重試
    免費版限制：每分鐘 5 次請求
    """
    params["apikey"] = AV_API_KEY

    for attempt in range(3):
        try:
            resp = requests.get(AV_BASE, params=params, timeout=15)
            data = resp.json()

            # Alpha Vantage 超過限流時會回傳這個訊息
            if "Note" in data or "Information" in data:
                msg = data.get("Note") or data.get("Information")
                print(f"  ⚠️  API 限流（{label}），15 秒後重試...")
                time.sleep(15)
                continue

            return data

        except Exception as e:
            if attempt < 2:
                print(f"  ⚠️  第 {attempt+1} 次請求失敗（{label}），5 秒後重試...")
                time.sleep(5)
            else:
                print(f"  ⚠️  無法取得數據（{label}）：{e}")

    return {}


def get_fundamental_data(ticker: str) -> dict:
    """從 Alpha Vantage OVERVIEW 抓基本面"""
    data = _av_get({"function": "OVERVIEW", "symbol": ticker}, label="基本面")

    if not data or "Symbol" not in data:
        print(f"  ⚠️  無法取得 {ticker} 基本面數據")
        return {}

    revenue      = _to_float(data.get("RevenueTTM"))
    gross_profit = _to_float(data.get("GrossProfitTTM"))
    # 毛利率 = 毛利 / 營收（Alpha Vantage 只給金額，要自己算比率）
    gross_margin = gross_profit / revenue if (gross_profit and revenue) else None

    return {
        "company_name": data.get("Name", ticker),
        "sector"      : data.get("Sector", "Unknown"),
        "revenue"     : revenue,
        "eps"         : _to_float(data.get("EPS")),
        "pe_ratio"    : _to_float(data.get("PERatio")),
        "gross_margin": gross_margin,
        "market_cap"  : _to_float(data.get("MarketCapitalization")),
    }


def get_technical_data(ticker: str) -> dict:
    """
    從 Alpha Vantage TIME_SERIES_DAILY 抓歷史價格
    計算 MA5/10/20/60、RSI、成交量比
    """
    # 抓每日價格（outputsize=compact = 最近 100 天）
    time.sleep(12)  # 避免超過每分鐘 5 次限制
    data = _av_get({
        "function"   : "TIME_SERIES_DAILY",
        "symbol"     : ticker,
        "outputsize" : "compact",
    }, label="歷史價格")

    ts = data.get("Time Series (Daily)")
    if not ts:
        print(f"  ⚠️  無法取得 {ticker} 歷史價格")
        return _empty_technical()

    # 轉成 DataFrame，最新的在最上面
    df = pd.DataFrame.from_dict(ts, orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index(ascending=True)
    df = df.rename(columns={
        "1. open"  : "open",
        "2. high"  : "high",
        "3. low"   : "low",
        "4. close" : "close",
        "5. volume": "volume",
    })
    df = df.astype(float)

    close  = df["close"]
    volume = df["volume"]

    # 移動平均線
    ma5  = close.rolling(window=5).mean()
    ma10 = close.rolling(window=10).mean()
    ma20 = close.rolling(window=20).mean()
    ma60 = close.rolling(window=60).mean()

    # RSI（14日）
    rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()

    # 成交量比（今日量 / 5日均量）
    vol_ma5      = volume.rolling(window=5).mean()
    volume_ratio = round(float(volume.iloc[-1]) / float(vol_ma5.iloc[-1]), 2) \
                   if float(vol_ma5.iloc[-1]) > 0 else None

    def safe(series):
        val = series.iloc[-1]
        return round(float(val), 2) if not pd.isna(val) else None

    return {
        "close"       : safe(close),
        "volume"      : int(volume.iloc[-1]),
        "volume_ratio": volume_ratio,
        "ma5"         : safe(ma5),
        "ma10"        : safe(ma10),
        "ma20"        : safe(ma20),
        "ma60"        : safe(ma60),
        "rsi"         : safe(rsi_series),
        "high_20d"    : round(float(close.tail(20).max()), 2),
        "low_20d"     : round(float(close.tail(20).min()), 2),
    }


def get_stock_data(ticker: str) -> dict:
    """整合基本面 + 技術面，回傳完整個股數據 dict"""
    ticker = ticker.upper()

    print(f"  📋 抓取基本面（Alpha Vantage）...")
    fundamental = get_fundamental_data(ticker)

    print(f"  📈 抓取技術面（Alpha Vantage）...")
    technical = get_technical_data(ticker)

    return {
        "ticker"      : ticker,
        "company_name": fundamental.get("company_name", ticker),
        "sector"      : fundamental.get("sector", "Unknown"),
        "revenue"     : fundamental.get("revenue"),
        "eps"         : fundamental.get("eps"),
        "pe_ratio"    : fundamental.get("pe_ratio"),
        "gross_margin": fundamental.get("gross_margin"),
        "market_cap"  : fundamental.get("market_cap"),
        **technical,
    }


def _empty_technical() -> dict:
    """技術面數據抓取失敗時回傳空值"""
    return {
        "close": None, "volume": None, "volume_ratio": None,
        "ma5": None, "ma10": None, "ma20": None, "ma60": None,
        "rsi": None, "high_20d": None, "low_20d": None,
    }


def _to_float(value) -> float | None:
    """安全轉換字串為 float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_number(value, suffix="", is_percent=False, decimals=2):
    """數字格式化輔助函式"""
    if value is None:
        return "N/A"
    if is_percent:
        return f"{value * 100:.{decimals}f}%"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.{decimals}f}B{suffix}"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M{suffix}"
    return f"{value:.{decimals}f}{suffix}"


# ── 測試用 ───────────────────────────────────────────
if __name__ == "__main__":
    ticker = input("請輸入股票代號（例如 TSLA）：").strip().upper()
    print(f"\n📡 正在抓取 {ticker} 數據...\n")

    data = get_stock_data(ticker)

    print(f"\n【{data['company_name']}（{data['ticker']}）數據結果】")
    print(f"\n  ── 基本面 ──")
    print(f"  產業別      : {data['sector']}")
    print(f"  總營收      : {format_number(data['revenue'], suffix=' USD')}")
    print(f"  EPS         : {format_number(data['eps'], suffix=' USD')}")
    print(f"  本益比      : {format_number(data['pe_ratio'], suffix='x')}")
    print(f"  毛利率      : {format_number(data['gross_margin'], is_percent=True)}")
    print(f"  市值        : {format_number(data['market_cap'], suffix=' USD')}")
    print(f"\n  ── 技術面 ──")
    print(f"  最新收盤價  : {data['close']}")
    print(f"  MA5         : {data['ma5']}")
    print(f"  MA10        : {data['ma10']}")
    print(f"  MA20        : {data['ma20']}")
    print(f"  MA60        : {data['ma60']}")
    print(f"  RSI(14)     : {data['rsi']}")
    print(f"  20日高點    : {data['high_20d']}")
    print(f"  20日低點    : {data['low_20d']}")
    print(f"  成交量比    : {data['volume_ratio']}x（今日量 / 5日均量）")