# 📊 Stock Analysis Model

> 一個結合總體經濟分析、個股基本面與技術面的 AI 輔助投資決策模型

---

## 🧠 專案理念

本模型的目標是建立一個**由上而下（Top-Down）**的分析框架，用**數據和邏輯**建立一個適合自己的投資決策。

### 核心問題
- ❌ 社群媒體充斥不確定的預測
- ❌ 沒有一套自己的評分體系
- ❌ 無法量化「為什麼要買/賣」這支股票

### 核心解答
- ✅ 自動化抓取官方經濟數據（FRED、Alpha Vantage）
- ✅ 建立可調參數的評分系統，易於回測優化
- ✅ 結合 Macro + Company + Technical 三層分析
- ✅ 輸出量化的投資建議與倉位建議

---

## 🏗️ 系統架構

```
輸入股票代號 (e.g. TSLA)
        ↓
【模組一】抓總體經濟數據 ← FRED API
  CPI / 10Y / 失業率 / OECD 商業信心(BSCI) / 零售銷售 / GDP / VIX
  註：ISM PMI 在 2017 年從 FRED 撤下（變付費），故改用 OECD BSCI 作為替代
        ↓
【模組二】Macro Score 計算（0-100分）
  評分門檻參數化，便於未來回測調整
  → 輸出：Market Mode（Risk-on / 偏多 / Neutral / Risk-off / 強Risk-off）
  → 同時建議倉位 (10% ~ 100%) 與 VIX 動態調整
        ↓
【模組三】抓個股數據 ← Alpha Vantage API
  基本面：營收、EPS、本益比、毛利率、市值
  技術面：MA5/10/20/60、RSI(14)、成交量比、20日高低點
        ↓
【模組四】技術面評分（-25 ~ +25分）
  均線位置（-10~+10）+ 均線排列（-8~+8）
  + RSI 狀態（-4~+4）+ 成交量（-3~+3）
        ↓
【模組五】個股綜合評分（0-100分）
  Macro Score × 0.5（縮放避免權重過大）
  + Macro Adjustment（根據市場模式 × 股票類型）
  + Company Adjustment（基本面調整：獲利/AI敘事/估值/競爭）
  + Technical Score
  → 輸出：Final Score & Investment Recommendation
        ↓
【模組六】生成完整分析報告
  包含環境分析、技術位置、未來情境分析、操作建議
        ↓
【模組七】主程式（main.py）
  一鍵執行完整分析流程
```

---

## 🔑 關鍵設計決策

### 1. **Macro Score 門檻的參數化**
**決策**：把所有評分門檻（CPI、殖利率、失業率等）存在 `macro_score.py` 頂部的 `THRESHOLDS` 字典

**原因**：
- 便於回測時快速調整參數，不用改多個地方
- 清楚記錄「我認為什麼樣的 CPI 算好」
- 面試時可以解釋為什麼選這些門檻

**面試說明**：「我設計的系統把所有評分邏輯參數化，這樣在回測階段可以系統地優化每個指標的權重，而不是寫死在程式裡。」

---

### 2. **API 來源選擇：Alpha Vantage 而非 yfinance**
**決策**：基本面和技術面都用 Alpha Vantage，放棄 yfinance

**背景**：
- yfinance 常被 Yahoo Finance 限流，導致數據不穩定
- 在開發過程中多次遇到「無法連線」的問題

**最終方案**：
- 基本面 → Alpha Vantage OVERVIEW API
- 技術面 → Alpha Vantage TIME_SERIES_DAILY API
- 加入自動重試機制 + 請求間隔控制（避免超過 API 限流）

**優勢**：
- ✅ 有官方 API Key，限流機制明確可控
- ✅ 數據來源統一，易於除錯
- ✅ 免費版足夠（每天 25 次請求）

**面試說明**：「在實際開發中發現免費 API 穩定性很重要。我的解決方案是統一用有明確額度限制的 Alpha Vantage，並在程式中加入智能重試和請求間隔控制。」

---

### 3. **倉位建議 = Macro Score + VIX 二層過濾**
**設計**：
```
基礎倉位（來自 Macro Score）
  ↓
VIX > 30?  →  進一步降低倉位
VIX > 25?  →  小幅降低倉位
VIX ≤ 25?  →  使用基礎倉位
```

**原因**：
- Macro Score 反映中長期趨勢（基本面）
- VIX 反映短期市場恐慌（情緒面）
- 兩者結合 = 既不過度保守，也不冒不必要的風險

**面試說明**：「倉位建議不只看經濟基本面，還要動態考慮市場情緒。我的設計讓倉位在市場恐慌時自動縮減，但不會走極端。」

---

### 4. **個股屬性資料庫（stock_database.json）**
**設計**：每支股票有三個維度的信息
```json
{
  "TSLA": {
    "attributes": ["Growth", "Cyclical"],
    "adjustments": {
      "profitable": false,
      "ai_narrative": true,
      "high_valuation": true,
      "high_competition": true
    },
    "notes": "高波動、高估值，對 Macro 環境極為敏感"
  }
}
```

**優勢**：
- 支持動態 Macro Adjustment（Risk-on 時 Growth 股加分）
- Company Adjustment 有據可查（不是主觀印象）
- 易於擴展（新增股票就加新 entry）

**局限**：需要定期更新，目前只覆蓋 12 支主流股

---

### 5. **技術面評分的四維度分解**
**設計**：技術分數分成四個獨立維度

| 維度 | 範圍 | 評分邏輯 |
|------|------|---------|
| 均線位置 | -10~+10 | 收盤價站在幾條均線上方 |
| 均線排列 | -8~+8 | 是否為多頭/空頭排列 |
| RSI 狀態 | -4~+4 | 超買/超賣/健康區間 |
| 成交量 | -3~+3 | 量能是否配合價格 |

**優勢**：
- 清楚看到技術面的「痛點」在哪（例如均線排列很好但 RSI 超買）
- 易於解釋為什麼某支股票技術面分數是多少
- 便於未來優化單個維度的權重

**面試說明**：「我把技術面分成四個獨立維度而不是用單一技術指標，這樣可以細粒度地診斷股票的強弱。」

---

### 6. **簡化版 AI 報告（無 API 成本）**
**決策**：用樣板 + 邏輯判斷生成報告，而不是呼叫 Claude API

**背景**：
- Claude API 需要付費（約 $5 起起價）
- 簡化版同樣可以生成有意義的分析

**實現方式**：
- 每個報告段落寫成函式（`get_macro_analysis()`、`get_scenario_bullish()` 等）
- 函式根據分數和指標輸出相應的文字
- 完全沒有網路請求，執行速度快

**權衡**：
- ✅ 成本：$0
- ✅ 速度：快
- ❌ 自然度：不如 Claude 的自然語言處理

**面試說明**：「我設計了兩個版本——一個用 Claude API 生成更自然的報告，一個用樣板快速生成。這展示了我對成本效益的考量，在實際產品開發中很常見。」

---

### 7. **Macro Score 縮放（乘以 0.5）**
**問題**：如果 Macro Score 直接用 0-100，會過度主導 Final Score

**解決**：
- Macro Score 乘以 0.5，變成 0-50
- Technical Score 為 -25~+25
- Company Adj 為 -30~+30
- 這樣三部分的權重更均衡

**面試說明**：「評分系統設計的關鍵是權重平衡。我通過縮放確保宏觀環境、公司基本面、技術面能各自發揮作用，而不被單一因素主導。」

---

## 🚀 安裝與使用

### 1. 複製專案
```bash
git clone https://github.com/你的帳號/stock-analysis-model.git
cd stock-analysis-model
```

### 2. 安裝套件
```bash
pip install -r requirements.txt
```

### 3. 取得 API Key

| API | 申請網址 | 免費額度 |
|-----|---------|---------|
| FRED | [fred.stlouisfed.org/docs/api](https://fred.stlouisfed.org/docs/api/api_key.html) | 無限制 |
| Alpha Vantage | [alphavantage.co](https://www.alphavantage.co/support/#api-key) | 每天 25 次 |

### 4. 設定 .env
```bash
cp .env.example .env
# 編輯 .env，填入你的 API Key
```

格式：
```
FRED_API_KEY=你的FRED金鑰
ALPHA_VANTAGE_API_KEY=你的AlphaVantage金鑰
```

### 5. 執行分析
```bash
python3 main.py
```

輸入股票代號（例如 `TSLA`），等待分析完成 ✅

---

## 📁 專案結構

```
stock-analysis-model/
├── .env.example                    # API Key 範本
├── .gitignore                      # 保護敏感資料
├── README.md                       # 說明文件
├── requirements.txt                # 所需套件
├── main.py                         # 主程式入口 ⭐
├── config/
│   └── stock_database.json         # 股票屬性資料庫
├── modules/
│   ├── macro_data.py               # 抓總經數據
│   ├── macro_score.py              # Macro Score 計算
│   ├── stock_data.py               # 抓個股數據
│   ├── technical_score.py          # 技術面評分
│   ├── company_score.py            # 綜合評分
│   └── ai_report.py                # 報告生成
└── output/                         # 報告輸出目錄
```

---

## 🧪 回測與優化計畫

目前模型已有完整架構，後續改進方向：

### Phase 2：回測系統
- 用歷史數據驗證評分門檻
- 優化 Macro Score 的 CPI/失業率/殖利率 門檻
- 測試不同的 Macro Adj 權重

### Phase 3：擴展功能
- 加入更多股票到資料庫
- 支援投資組合分析（多支股票同時評分）
- 加入成本動能因子（Momentum）

### Phase 4：實際交易信號
- 回測時記錄交易信號與實際績效
- 計算模型的夏普比率、最大回撤
- 與市場指標比較（例如 S&P 500）

---

## ⚠️ 免責聲明

本模型僅供個人學習與參考使用，**不構成任何投資建議**。

- 投資有風險，過去績效不代表未來結果
- 請根據自身風險承受度與投資目標進行決策
- 定期檢視部位，設置適當的停損/停利點位

---

## 💡 技術亮點

| 亮點 | 說明 |
|------|------|
| **參數化設計** | 所有評分門檻可調，便於回測優化 |
| **API 穩定性** | 經過實際開發調試，選用最穩定的免費 API |
| **二層過濾** | Macro + VIX 倉位建議，均衡風險 |
| **屬性資料庫** | 動態 Adjustment，易擴展 |
| **成本意識** | 簡化版報告完全免費，同時提供 Claude API 版本 |
| **清晰邏輯** | 每個評分維度獨立，易於診斷和解釋 |

---

## 📖 使用指南

### 快速開始
```bash
python3 main.py
# → 輸入 TSLA
# → 等待 30 秒左右分析完成
# → 獲得完整分析報告
```

### 自訂個股屬性
編輯 `config/stock_database.json`，為新股票添加：
```json
"NEWSTOCK": {
  "name": "Company Name",
  "attributes": ["Growth", "Quality"],
  "adjustments": {
    "profitable": true,
    "ai_narrative": false,
    "high_valuation": true,
    "high_competition": false
  },
  "notes": "公司特性備註"
}
```

### 調整評分門檻
打開 `modules/macro_score.py`，修改 `THRESHOLDS` 字典中的數值。

例如，如果你認為 CPI 3.0% 就夠低了：
```python
"CPI_YoY": {
    "excellent": 2.0,   # <= 2.0 → 滿分 25
    "good":      3.0,   # ← 改這裡
    ...
}
```

---

