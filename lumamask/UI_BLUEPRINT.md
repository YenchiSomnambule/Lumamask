# Lumamask UI Blueprint

## 1. 現況摘要（Current System）

Lumamask 是一個 Python CLI 工具，流程如下：

```
用戶的 .txt 文件
       ↓
  detect()          ← Presidio + spaCy，找出敏感實體
       ↓
  pseudonymize()    ← 替換成 [PERSON_1]、[AMT_1] 等 token
       ↓
  ask_claude()      ← 只把 masked 版本傳給 Claude API
       ↓
  restore()         ← 把 token 換回真實值
       ↓
  4 sections 輸出
```

核心檔案位置（`lumamask/lumamask/`）：
- `detect.py` — 實體偵測（Presidio + 3 個自訂 regex recognizer）
- `pseudonymize.py` — 替換敏感值為 token
- `restore.py` — 還原 token 為真實值
- `llm.py` — 呼叫 Claude API（`claude-sonnet-4-6`）
- `pipeline.py` — 串接以上四步，回傳 dict
- `cli.py` — argparse CLI 介面

`pipeline.run_pipeline(text, instruction)` 回傳：
```python
{
    "original": str,           # 原始文字
    "masked": str,             # 去識別化版本
    "map": dict,               # token → 真實值對照表
    "ai_reply_tokenised": str, # Claude 回覆（含 token）
    "ai_reply_restored": str   # Claude 回覆（還原後）← 用戶要的
}
```

---

## 2. UI 需求

- 用戶上傳或貼上 `.txt` 文件內容
- 輸入想問 Claude 的問題（instruction）
- 輸入 Anthropic API key（不儲存到磁碟）
- 點擊執行，看到 4 sections 輸出
- 不需要用命令列，純 GUI 操作

---

## 3. 技術架構建議

### 推薦方案：Flask + 單頁 HTML（最容易上手且可擴展）

```
lumamask-ui/
├── app.py                  ← Flask 後端（主要邏輯）
├── templates/
│   └── index.html          ← 前端（HTML + CSS + JS，單一檔案）
├── static/
│   └── style.css           ← 可選，也可內嵌於 index.html
└── run_ui.bat              ← 雙擊啟動，自動開瀏覽器
```

啟動方式：雙擊 `run_ui.bat` → 自動開瀏覽器到 `http://localhost:5000`

### 替代方案：Streamlit（最快實作，pure Python）
若要更快交付，改用 Streamlit，只需一個 `app.py`，`streamlit run app.py` 即可。

---

## 4. 頁面布局設計

```
┌─────────────────────────────────────────────────────┐
│  🔒 Lumamask  — Sensitive Document Processor        │
├──────────────────────┬──────────────────────────────┤
│   INPUT PANEL        │   OUTPUT PANEL               │
│                      │                              │
│  API Key:            │  [Tab: Summary]              │
│  [••••••••••] 👁     │   • 1 PERSON                 │
│                      │   • 3 MONEY_AMOUNT           │
│  Document:           │   • 1 IBAN_CODE ...          │
│  ┌──────────────┐    │                              │
│  │ Upload .txt  │    │  [Tab: Masked Version]       │
│  │ OR paste ↓   │    │   Dear [PERSON_1],           │
│  └──────────────┘    │   Amount: [AMT_1] ...        │
│  ┌──────────────┐    │                              │
│  │              │    │  [Tab: AI Reply (masked)]    │
│  │  (text area) │    │   [PERSON_1] owes [AMT_1]..  │
│  │              │    │                              │
│  └──────────────┘    │  [Tab: ✅ Final Answer]      │
│                      │   John Smith owes $26,000... │
│  Instruction:        │                              │
│  ┌──────────────┐    │  [📋 Copy] [💾 Save .txt]   │
│  │ 請摘要重點   │    │                              │
│  └──────────────┘    │                              │
│                      │                              │
│  [▶ Run Lumamask]    │   ⚠ 0 items may be missed   │
│                      │                              │
└──────────────────────┴──────────────────────────────┘
```

---

## 5. Flask 後端規格（`app.py`）

```python
# 依賴套件
# pip install flask
# 其餘已有：presidio-analyzer, presidio-anonymizer, anthropic, spacy

import os, sys
from flask import Flask, request, jsonify, render_template

# 加入 lumamask 模組路徑（UI 放在 lumamask/ 同層）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lumamask.pipeline import run_pipeline

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/run', methods=['POST'])
def run():
    data = request.json
    api_key   = data.get('api_key', '').strip()
    text      = data.get('text', '').strip()
    instruction = data.get('instruction', '').strip()

    # 驗證輸入
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    if not text:
        return jsonify({'error': 'Document text is required'}), 400
    if not instruction:
        return jsonify({'error': 'Instruction is required'}), 400

    # 設定環境變數（session-scoped，不寫入磁碟）
    os.environ['ANTHROPIC_API_KEY'] = api_key

    try:
        result = run_pipeline(text, instruction)
        # 不回傳 map（含敏感資料），只回傳前端需要的部分
        return jsonify({
            'detection_summary': _count_entities(result),
            'masked':            result['masked'],
            'ai_reply_masked':   result['ai_reply_tokenised'],
            'final_answer':      result['ai_reply_restored'],
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    finally:
        # 清除 key（不留在 process env 過久）
        os.environ.pop('ANTHROPIC_API_KEY', None)

def _count_entities(result):
    """回傳每種 entity type 的數量 dict。"""
    from lumamask.detect import detect
    detections = detect(result['original'])
    counts = {}
    for d in detections:
        counts[d['entity_type']] = counts.get(d['entity_type'], 0) + 1
    return counts

if __name__ == '__main__':
    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(debug=False, port=5000)
```

---

## 6. 前端規格（`templates/index.html`）

### 功能要求

| 元件 | 規格 |
|---|---|
| API Key 輸入 | `type="password"`，右側有顯示/隱藏切換按鈕 |
| 文件輸入 | 上傳 `.txt` 按鈕 + 大型 textarea（二擇一，上傳自動填入 textarea）|
| Instruction 輸入 | Textarea，placeholder 預設範例問題 |
| Run 按鈕 | 點擊後變 loading 狀態（spinner + 禁用） |
| 輸出區 | 4 個 Tab：Summary / Masked / AI Reply / Final Answer |
| Summary Tab | 列出每個 entity type 及數量，有顏色標記 |
| Masked Tab | monospace 字型，敏感 token 以橘色高亮 |
| Final Answer Tab | 預設選中此 Tab，清楚呈現 Claude 回覆 |
| Copy 按鈕 | 複製 Final Answer 到剪貼簿 |
| 錯誤處理 | API 錯誤、網路錯誤顯示紅色 alert，不 crash |

### Token 高亮 regex（前端 JS）
```javascript
function highlightTokens(text) {
    return text.replace(/\[([A-Z_]+)_(\d+)\]/g,
        '<span class="token">[$1_$2]</span>');
}
```

### Entity 顏色對照
```
PERSON       → 藍色
ORGANIZATION → 紫色
MONEY_AMOUNT → 綠色
IBAN_CODE    → 紅色
EMAIL_ADDRESS→ 橘色
PHONE_NUMBER → 青色
LOCATION     → 棕色
其他         → 灰色
```

---

## 7. 啟動腳本（`run_ui.bat`）

```bat
@echo off
cd /d "%~dp0"
echo Starting Lumamask UI...
python app.py
pause
```

---

## 8. 目錄結構（完成後）

```
lumamask/          ← 現有 CLI 專案（不改動）
  lumamask/
    detect.py
    pseudonymize.py
    restore.py
    llm.py
    pipeline.py
    cli.py
  samples/
  tests/
  requirements.txt

lumamask-ui/       ← 新建 UI 專案
  app.py
  run_ui.bat
  templates/
    index.html
  static/
    style.css      ← 可選
```

---

## 9. 安裝新增依賴

```bat
pip install flask
```
其餘套件（presidio, anthropic, spacy）已於 install_windows.bat 安裝。

---

## 10. 安全性注意事項

- API key **只存在 Python process 的記憶體**，`finally` 區塊清除，不寫檔
- placeholder map（token ↔ 真實值）**不傳給前端**
- 後端只回傳前端需要顯示的 4 個欄位
- `debug=False`（Flask 生產模式）
- 僅 localhost，不對外開放

---

## 11. 給實作 Claude 的注意事項

1. `run_pipeline()` 已完整可用，UI 只是在它外面包一層，**不要修改任何 lumamask/ 內的檔案**
2. Flask 的 `sys.path.insert` 要確保能找到 `lumamask` package（相對路徑依實際目錄結構調整）
3. spaCy model 第一次 load 需要約 3–5 秒，之後快取於 process，前端需要 loading indicator
4. 所有錯誤要 catch 並以 JSON 回傳，前端顯示給用戶，不要讓 500 直接暴露
5. 單一 HTML 檔案（inline CSS + JS），避免 CORS 問題，不需要額外 static server
