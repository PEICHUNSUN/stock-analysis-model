# backtest.py
# 回測系統：驗證股票分析模型的有效性
# 使用過去 100 天的歷史數據（免費版限制），逐日計算評分並對比實際績效

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import time

# 導入所有模組
from modules.macro_data import get_macro_data
from modules.macro_score import calculate_macro_score
from modules.stock_data import get_stock_data
from modules.technical_score import calculate_technical_score

load_dotenv()

AV_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")
AV_BASE = "https://www.alphavantage.co/query"


def get_historical_daily_data(ticker: str, days: int = 100) -> pd.DataFrame:
    """
    從 Alpha Vantage 抓取歷史每日數據（免費版）
    返回 DataFrame：Date, Open, High, Low, Close, Volume
    """
    print(f"  📥 抓取 {ticker} 過去 {days} 天的每日數據...")
    
    try:
        resp = requests.get(AV_BASE, params={
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",  # 免費版只支持 compact（最近 100 天）
            "apikey": AV_API_KEY,
        }, timeout=15)
        
        data = resp.json()
        
        # 檢查是否有錯誤訊息
        if "Information" in data or "Note" in data:
            msg = data.get("Information") or data.get("Note")
            print(f"  ⚠️  API 警告：{msg}")
            return pd.DataFrame()
        
        ts = data.get("Time Series (Daily)")
        
        if not ts:
            print(f"  ❌ 無法獲取 {ticker} 數據")
            return pd.DataFrame()
        
        # 轉成 DataFrame
        df = pd.DataFrame.from_dict(ts, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=True)
        
        # 只保留需要的欄位
        df = df.rename(columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume",
        })[["Open", "High", "Low", "Close", "Volume"]]
        
        # 轉成 float
        for col in df.columns:
            df[col] = df[col].astype(float)
        
        print(f"  ✅ 獲得 {len(df)} 天的數據（{df.index[0].date()} 到 {df.index[-1].date()}）")
        return df
        
    except Exception as e:
        print(f"  ❌ 抓取失敗：{e}")
        return pd.DataFrame()


def calculate_daily_score(
    ticker: str,
    price: float,
    historical_df: pd.DataFrame,
    current_idx: int,
    macro_data: dict,
) -> dict:
    """
    計算某一天的完整評分
    """
    
    # 構造當時的股票數據（使用當時到目前為止的 MA、RSI 等）
    df_up_to_now = historical_df.iloc[:current_idx+1]
    
    if len(df_up_to_now) < 20:  # 需要至少 20 天算基本指標
        return None
    
    close = df_up_to_now["Close"]
    
    # 計算技術面指標
    try:
        import ta
        
        # 計算可用的均線（不是所有都能算）
        ma5 = close.rolling(window=5).mean().iloc[-1]
        ma10 = close.rolling(window=10).mean().iloc[-1]
        ma20 = close.rolling(window=20).mean().iloc[-1]
        
        # MA60 需要 60 天，不一定有
        ma60 = None
        if len(df_up_to_now) >= 60:
            ma60 = close.rolling(window=60).mean().iloc[-1]
        else:
            ma60 = ma20  # 不夠 60 天，用 MA20 代替
        
        # RSI
        if len(close) >= 14:
            rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
        else:
            rsi = 50  # 不夠 14 天，用中性值
        
        # 成交量
        vol_ma5 = df_up_to_now["Volume"].rolling(window=5).mean().iloc[-1]
        current_vol = df_up_to_now["Volume"].iloc[-1]
        volume_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 1.0
        
        # 高低點
        high_20d = close.tail(20).max()
        low_20d = close.tail(20).min()
        
    except Exception as e:
        print(f"    ⚠️  計算技術指標失敗：{e}")
        return None
    
    # 構造 stock_data dict
    stock_data = {
        "close": float(price),
        "ma5": float(ma5) if not pd.isna(ma5) else None,
        "ma10": float(ma10) if not pd.isna(ma10) else None,
        "ma20": float(ma20) if not pd.isna(ma20) else None,
        "ma60": float(ma60) if not pd.isna(ma60) else None,
        "rsi": float(rsi) if not pd.isna(rsi) else None,
        "volume_ratio": float(volume_ratio),
        "high_20d": float(high_20d),
        "low_20d": float(low_20d),
        # 簡化：用當前的基本面
        "company_name": ticker,
        "sector": "Unknown",
        "revenue": None,
        "eps": None,
        "pe_ratio": None,
        "gross_margin": None,
        "market_cap": None,
    }
    
    try:
        # 計算 Macro Score
        macro_result = calculate_macro_score(macro_data)
        
        # 計算技術面評分
        tech_result = calculate_technical_score(stock_data)
        
        # 簡化計算：直接合併 Macro 和 Technical
        macro_score = macro_result.get("macro_score", 50)
        tech_score = tech_result.get("technical_score", 0)
        final_score = macro_score * 0.5 + tech_score
        final_score = max(0, min(100, final_score))  # 限制在 0-100
        
        # 決定推薦
        if final_score >= 75:
            recommendation = "🟢 Strong Buy"
        elif final_score >= 65:
            recommendation = "🟢 Buy"
        elif final_score >= 55:
            recommendation = "🟡 Watch+"
        elif final_score >= 45:
            recommendation = "🟡 Watch"
        elif final_score >= 35:
            recommendation = "🟠 Cautious"
        else:
            recommendation = "🔴 Avoid"
        
        return {
            "date": df_up_to_now.index[-1],
            "price": float(price),
            "macro_score": macro_score,
            "market_mode": macro_result.get("market_mode", "Neutral"),
            "tech_score": tech_score,
            "final_score": final_score,
            "recommendation": recommendation,
        }
        
    except Exception as e:
        print(f"    ⚠️  計算評分失敗：{e}")
        return None


def backtest_ticker(ticker: str, days: int = 100, lookahead: int = 20) -> dict:
    """
    對某支股票進行回測
    
    參數：
    - ticker: 股票代號
    - days: 回測天數（預設 100 天，免費版限制）
    - lookahead: 未來期間（預設 20 天）
    """
    
    print(f"\n{'='*60}")
    print(f"【{ticker} 回測開始】")
    print(f"{'='*60}")
    
    # Step 1：抓歷史數據
    hist_df = get_historical_daily_data(ticker, days=days)
    if hist_df.empty:
        return {"ticker": ticker, "error": "無法獲取數據"}
    
    # 檢查是否有足夠的數據進行 lookahead
    available_days = len(hist_df) - lookahead
    if available_days < 20:
        return {
            "ticker": ticker, 
            "error": f"數據不足。只有 {len(hist_df)} 天，無法進行 {lookahead} 天的 lookahead 回測。建議至少 {lookahead + 20} 天數據。"
        }
    
    # Step 2：抓當前 Macro 數據
    print(f"  📊 抓取總經數據...")
    try:
        macro_data = get_macro_data()
    except Exception as e:
        print(f"  ⚠️  Macro 數據抓取失敗：{e}")
        return {"ticker": ticker, "error": f"無法獲取 Macro 數據：{e}"}
    
    # Step 3：逐日回測
    print(f"  ⏳ 逐日計算評分...")
    results = []
    
    for idx in range(20, len(hist_df) - lookahead):  # 至少 20 天以計算基本指標
        if idx % 10 == 0:
            progress = f"{idx}/{len(hist_df) - lookahead}"
            print(f"    進度：{progress}")
        
        current_date = hist_df.index[idx]
        current_price = hist_df["Close"].iloc[idx]
        
        # 計算當時的評分
        score = calculate_daily_score(
            ticker=ticker,
            price=current_price,
            historical_df=hist_df,
            current_idx=idx,
            macro_data=macro_data,
        )
        
        if score is None:
            continue
        
        # 計算未來 lookahead 天的股價
        future_idx = idx + lookahead
        if future_idx >= len(hist_df):
            break
        
        future_price = hist_df["Close"].iloc[future_idx]
        return_pct = (future_price - current_price) / current_price * 100
        
        # 判斷是否漲跌
        is_up = return_pct > 0
        
        score["future_price"] = float(future_price)
        score["return_pct"] = float(return_pct)
        score["is_up"] = is_up
        
        results.append(score)
    
    if not results:
        return {"ticker": ticker, "error": "沒有有效的回測信號"}
    
    print(f"  ✅ 計算完成，共 {len(results)} 個信號")
    
    # Step 4：計算績效指標
    return calculate_backtest_metrics(ticker, results, lookahead)


def calculate_backtest_metrics(ticker: str, results: list, lookahead: int) -> dict:
    """
    根據回測結果計算績效指標
    """
    
    if not results:
        return {"ticker": ticker, "error": "無有效回測結果"}
    
    df_results = pd.DataFrame(results)
    
    # 基本統計
    total_signals = len(df_results)
    buy_signals = len(df_results[df_results["recommendation"].str.contains("Buy", na=False)])
    hit_count = len(df_results[df_results["is_up"]])
    hit_rate = hit_count / total_signals * 100 if total_signals > 0 else 0
    
    # 報酬統計
    returns = df_results["return_pct"].values
    avg_return = np.mean(returns)
    win_rate = len(df_results[df_results["return_pct"] > 0]) / total_signals * 100
    
    # 夏普比率（假設無風險利率 2%）
    excess_returns = returns - 2
    std_dev = np.std(excess_returns)
    sharpe_ratio = np.mean(excess_returns) / std_dev if std_dev > 0 else 0
    
    # 最大回撤（簡化計算）
    cumulative_returns = (1 + df_results["return_pct"] / 100).cumprod()
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - running_max) / running_max * 100
    max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
    
    # 按信號類型統計
    try:
        recommendation_stats = df_results.groupby("recommendation").agg({
            "recommendation": "count",
            "is_up": lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0,
            "return_pct": "mean"
        }).rename(columns={"recommendation": "count", "is_up": "hit_rate", "return_pct": "avg_return"}).to_dict()
    except:
        recommendation_stats = {}
    
    return {
        "ticker": ticker,
        "backtest_period": f"{df_results['date'].min().date()} 到 {df_results['date'].max().date()}",
        "lookahead_days": lookahead,
        "total_days": len(df_results),
        
        # 核心指標
        "total_signals": total_signals,
        "buy_signals": buy_signals,
        "hit_count": hit_count,
        "hit_rate": round(hit_rate, 2),
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 2),
        
        # 按信號類型詳細統計
        "by_recommendation": recommendation_stats,
    }


def print_backtest_report(metrics: dict):
    """打印回測報告"""
    
    if "error" in metrics:
        print(f"\n❌ {metrics['ticker']} 回測失敗：{metrics['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"【{metrics['ticker']} 回測報告】")
    print(f"{'='*60}")
    print(f"\n📅 回測期間：{metrics['backtest_period']}")
    print(f"📊 未來期間：{metrics['lookahead_days']} 天")
    print(f"📈 總交易日：{metrics['total_days']} 日")
    
    print(f"\n【核心績效指標】")
    print(f"  總信號數       : {metrics['total_signals']} 個")
    print(f"  買入信號       : {metrics['buy_signals']} 個")
    print(f"  命中數         : {metrics['hit_count']} 個")
    print(f"\n  ✅ 命中率      : {metrics['hit_rate']}%")
    print(f"  ✅ 勝率        : {metrics['win_rate']}%")
    print(f"  ✅ 平均報酬    : {metrics['avg_return']}%")
    print(f"  ✅ 夏普比率    : {metrics['sharpe_ratio']}")
    print(f"  ⚠️  最大回撤   : {metrics['max_drawdown']}%")
    
    if metrics.get("by_recommendation"):
        print(f"\n【按信號類型統計】")
        for rec, stats in metrics["by_recommendation"].items():
            if isinstance(stats, dict):
                print(f"  {rec}")
                print(f"    數量：{stats.get('count', 0)} | 命中率：{stats.get('hit_rate', 0):.2f}% | 平均報酬：{stats.get('avg_return', 0):.2f}%")
    
    print(f"\n{'─'*60}\n")


# ── 主程式 ───────────────────────────────────────────
if __name__ == "__main__":
    tickers = ["TSLA", "CRCL", "NVDA"]
    
    print("\n" + "="*60)
    print("📈 股票分析模型 - 回測系統")
    print("="*60)
    print(f"回測股票：{', '.join(tickers)}")
    print(f"回測期間：過去 100 天（免費版限制）")
    print(f"評估期間：未來 20 天")
    print("="*60)
    
    all_metrics = {}
    
    for ticker in tickers:
        try:
            metrics = backtest_ticker(ticker, days=100, lookahead=20)  # ← 改成 100 天
            all_metrics[ticker] = metrics
            print_backtest_report(metrics)
            
            # 避免 API 限流
            time.sleep(15)
            
        except Exception as e:
            print(f"\n❌ {ticker} 回測出錯：{e}")
    
    # 保存回測結果
    print("\n💾 正在保存回測結果...")
    try:
        output = {
            "timestamp": datetime.now().isoformat(),
            "tickers": tickers,
            "summary": {
                k: {
                    "hit_rate": v.get("hit_rate", 0),
                    "win_rate": v.get("win_rate", 0),
                    "avg_return": v.get("avg_return", 0),
                    "sharpe_ratio": v.get("sharpe_ratio", 0),
                }
                for k, v in all_metrics.items()
                if "error" not in v
            }
        }
        
        os.makedirs("output", exist_ok=True)
        filename = f"output/backtest_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 回測結果已保存到 {filename}")
    except Exception as e:
        print(f"⚠️  保存失敗：{e}")