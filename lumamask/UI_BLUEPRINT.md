# Lumamask UI Blueprint
> Design reference: Linear (linear.app) — near-black dark theme, information-dense, minimal chrome, no decorative gradients or shadows, coloured label chips, underline-style tabs, keyboard-first feel.

---

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

## 3. 技術架構

### 推薦方案：Flask + 單頁 HTML

```
lumamask-ui/
├── app.py                  ← Flask 後端
├── templates/
│   └── index.html          ← 前端（HTML + CSS + JS 全部 inline，單一檔案）
└── run_ui.bat              ← 雙擊啟動，自動開瀏覽器
```

啟動方式：雙擊 `run_ui.bat` → 自動開瀏覽器到 `http://localhost:5000`

---

## 4. 設計系統（Design Tokens）

### 色彩（Linear-inspired）

```css
/* Backgrounds — layered dark surfaces, no gradients */
--bg-app:        #08090a;   /* page background — same as Linear's body */
--bg-surface:    #111318;   /* card / panel surface */
--bg-elevated:   #1a1d24;   /* inputs, hover states */
--bg-border:     #2a2d36;   /* dividers, input borders */

/* Text */
--text-primary:  #e8eaf0;   /* main content */
--text-secondary:#8b8fa8;   /* labels, hints */
--text-muted:    #4a4e63;   /* placeholder, disabled */

/* Accent — single primary action colour */
--accent:        #5e6ad2;   /* Linear's own indigo-purple */
--accent-hover:  #6b77e0;

/* Entity label chip colours — muted, not saturated */
--chip-person:   #1d3557;   /* dark blue bg */  color: #93c5fd;
--chip-org:      #2d1b6e;   /* dark purple bg */ color: #c4b5fd;
--chip-money:    #14532d;   /* dark green bg */  color: #86efac;
--chip-iban:     #450a0a;   /* dark red bg */    color: #fca5a5;
--chip-email:    #431407;   /* dark orange bg */ color: #fdba74;
--chip-phone:    #164e63;   /* dark cyan bg */   color: #67e8f9;
--chip-location: #3b1a0a;   /* dark amber bg */  color: #fcd34d;
--chip-default:  #1e2030;                        color: #8b8fa8;

/* Status */
--status-ok:     #22c55e;
--status-warn:   #f59e0b;
--status-error:  #ef4444;
```

### 字型

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
/* monospace for masked text / tokens */
font-family-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;

/* Scale */
--text-xs:   11px;
--text-sm:   12px;   /* labels, chips, metadata */
--text-base: 13px;   /* body — Linear uses 13px as base */
--text-md:   14px;   /* section headings */
--text-lg:   16px;   /* page title */

/* Weight */
--weight-normal:  400;
--weight-medium:  500;
--weight-semibold:600;
```

### 間距（4px grid）

```
4px  — chip padding (vertical)
6px  — chip padding (horizontal)
8px  — tight spacing between elements
12px — input field padding
16px — section padding
24px — panel padding
```

### 邊框 & 圓角

```css
border: 1px solid var(--bg-border);   /* all borders — single weight, no glow */
border-radius: 4px;   /* chips, inputs, buttons — Linear uses 4–6px max */
border-radius: 6px;   /* panels, cards */
/* NO box-shadow on interactive elements. NO drop shadows. */
/* Hover state: background colour change only, no border colour change. */
```

---

## 5. 頁面布局（Linear-style two-panel）

```
┌──────────────────────────────────────────────────────────────────┐
│  ○  Lumamask                                    [localhost:5000]  │  ← browser chrome
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Lumamask          ← page title, --text-lg, --text-primary       │
│  Sensitive document processor                                    │
│  ─────────────────────────────────────────────────────────────  │  ← --bg-border divider
│                                                                  │
│  ┌─────────────────────────┐  ┌───────────────────────────────┐  │
│  │  INPUT                  │  │  OUTPUT                       │  │
│  │  (40% width)            │  │  (60% width)                  │  │
│  │                         │  │                               │  │
│  │  API Key                │  │  Detected  Masked  Reply  ✓   │  │  ← underline tabs
│  │  ┌─────────────────┐    │  │  ───────────────────────────  │  │
│  │  │ ••••••••••••  👁 │    │  │                               │  │
│  │  └─────────────────┘    │  │  [tab content]                │  │
│  │                         │  │                               │  │
│  │  Document               │  │                               │  │
│  │  [↑ Upload .txt]        │  │                               │  │
│  │  ┌─────────────────┐    │  │                               │  │
│  │  │                 │    │  │                               │  │
│  │  │  paste or type  │    │  │                               │  │
│  │  │  document here  │    │  │                               │  │
│  │  │                 │    │  │                               │  │
│  │  └─────────────────┘    │  │                               │  │
│  │                         │  │                               │  │
│  │  Instruction            │  │                               │  │
│  │  ┌─────────────────┐    │  │                               │  │
│  │  │ Summarise in    │    │  │                               │  │
│  │  │ two sentences.  │    │  │                               │  │
│  │  └─────────────────┘    │  │                               │  │
│  │                         │  │                               │  │
│  │  [  Run Lumamask  ]     │  │                               │  │
│  │                         │  │                               │  │
│  └─────────────────────────┘  └───────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. 元件規格（Component Specs）

### 6.1 全域 Shell

```
body background: --bg-app (#08090a)
max-width: 1280px, centred
padding: 24px
font: 13px Inter, --text-primary
```

頁面頂部（無 navbar/sidebar — 單頁工具，不需要）：
```
Lumamask                          ← h1, --text-lg, --weight-semibold
Sensitive document processor      ← p, --text-sm, --text-secondary
```
底部一條 `1px solid --bg-border` 分隔線，16px margin bottom。

---

### 6.2 輸入面板（Input Panel）

背景 `--bg-surface`，border `1px solid --bg-border`，border-radius `6px`，padding `24px`。

#### API Key 欄位

```
Label:  API Key          ← --text-sm, --text-secondary, margin-bottom 6px
Input:  type="password"
        background: --bg-elevated
        border: 1px solid --bg-border
        border-radius: 4px
        padding: 10px 12px
        font: 13px Inter
        color: --text-primary
        width: 100%
        NO focus ring glow — only border-color change to --accent on focus

右側眼睛圖示 (👁):
        position: absolute, right 10px
        color: --text-muted
        cursor: pointer
        hover: color --text-secondary
```

#### Document 欄位

```
Label:  Document         ← --text-sm, --text-secondary
上傳按鈕:
        text: "↑ Upload .txt"
        background: transparent
        border: 1px solid --bg-border
        border-radius: 4px
        padding: 5px 10px
        font: --text-sm, --text-secondary
        hover: background --bg-elevated
        margin-bottom: 8px

Textarea:
        background: --bg-elevated
        border: 1px solid --bg-border
        border-radius: 4px
        padding: 12px
        font: 13px 'JetBrains Mono' (monospace)   ← 文件內容用等寬字
        color: --text-primary
        min-height: 200px
        resize: vertical
        width: 100%
        placeholder color: --text-muted
        NO scrollbar styling beyond browser default
```

#### Instruction 欄位

```
Label:  Instruction      ← --text-sm, --text-secondary
Textarea:
        同 Document textarea 樣式，但 font: 13px Inter（非等寬）
        min-height: 60px
        placeholder: "e.g. Summarise this invoice in two sentences."
```

#### Run 按鈕

```
Normal state:
  text: "Run Lumamask"
  background: --accent (#5e6ad2)
  color: white
  border: none
  border-radius: 4px
  padding: 8px 16px
  font: --text-sm, --weight-medium
  cursor: pointer
  width: 100%
  letter-spacing: 0.01em

Hover:
  background: --accent-hover (#6b77e0)
  NO transform, NO shadow

Loading state:
  disabled: true
  background: --bg-elevated
  color: --text-muted
  text: shows progress steps (see §6.5 Loading)
  cursor: not-allowed
```

---

### 6.3 輸出面板（Output Panel）

背景 `--bg-surface`，border `1px solid --bg-border`，border-radius `6px`。

#### Tabs（Linear underline style）

```
Tab bar:
  background: transparent
  border-bottom: 1px solid --bg-border
  padding: 0 24px
  display: flex, gap: 0

每個 Tab:
  text: --text-sm, --text-secondary
  padding: 10px 14px
  border-bottom: 2px solid transparent   ← key: NOT a box
  margin-bottom: -1px                    ← overlaps panel border
  cursor: pointer
  NO background on hover — only text colour change to --text-primary

Active Tab:
  color: --text-primary
  border-bottom: 2px solid --accent      ← Linear-style underline

Tab labels:
  "Detected (N)"   ← N = total entity count, shown after run
  "Masked"
  "AI Reply"
  "Answer"         ← default active tab after run; use ✓ prefix once complete: "✓ Answer"
```

Tab content padding: `24px`.

---

### 6.4 Tab 內容規格

#### Tab 1 — Detected

Linear-style compact list rows：

```
每行格式：
  [entity chip]  [偵測到的原始文字，truncated]  [count badge]

例：
  [PERSON]        Sandra Holloway                              1
  [MONEY_AMOUNT]  $26,639.75, $23,575.00, $3,064.75 ...       6
  [IBAN_CODE]     GB82WEST12345698765432                       1
  [ORGANIZATION]  Maple Ridge Consulting Inc., RBC Royal ...   9

Row 樣式:
  height: 32px
  display: flex, align-items: center
  border-bottom: 1px solid --bg-border (最後一行無)
  hover: background --bg-elevated

Count badge:
  background: --bg-elevated
  color: --text-secondary
  border-radius: 10px
  padding: 1px 6px
  font: --text-xs, monospace
  margin-left: auto
```

Entity chip 樣式（對應色彩見 §4）：
```
  border-radius: 4px
  padding: 2px 6px
  font: --text-xs, --weight-medium
  font-family: monospace
  width: 120px (fixed, left-aligned)

  例：[PERSON]        ← blue bg + blue text
      [MONEY_AMOUNT]  ← green bg + green text
      [IBAN_CODE]     ← red bg + red text
```

底部警告行（若有 miss）：
```
  ⚠ 1 entity may have been missed — review Masked tab before sending.
  color: --status-warn
  font: --text-xs
  margin-top: 12px
```

---

#### Tab 2 — Masked

```
Content:
  font: 13px 'JetBrains Mono'
  color: --text-primary
  background: --bg-elevated
  border-radius: 4px
  padding: 16px
  white-space: pre-wrap
  overflow-y: auto
  max-height: 500px

Token 高亮（inline）:
  [PERSON_1] → <span class="token token-person">[PERSON_1]</span>
  每個 token 用對應 entity chip 顏色，border-radius: 3px, padding: 1px 4px
  NO bold, NO italic — colour only, consistent with Linear label style
```

JS regex：
```javascript
const TOKEN_RE = /\[([A-Z_]+)_(\d+)\]/g;
function highlightTokens(text) {
    return text.replace(TOKEN_RE, (_, type, n) =>
        `<span class="token token-${type.toLowerCase()}">[${type}_${n}]</span>`);
}
```

---

#### Tab 3 — AI Reply

同 Tab 2 樣式（monospace + token highlight），但內容為 `ai_reply_tokenised`。

標題行（tab 內頂部）：
```
  Claude's response (tokens preserved)    ← --text-xs, --text-muted, margin-bottom 12px
```

---

#### Tab 4 — Answer（主要輸出）

```
Content:
  font: 13px Inter（非等寬）
  color: --text-primary
  line-height: 1.6
  padding: 0
  white-space: pre-wrap

底部 action bar:
  margin-top: 16px
  border-top: 1px solid --bg-border
  padding-top: 12px
  display: flex, gap: 8px

  [Copy]    ← ghost button（透明背景，--bg-border border）
  [Save .txt] ← 同 ghost style

  Ghost button:
    border: 1px solid --bg-border
    border-radius: 4px
    padding: 5px 10px
    font: --text-sm, --text-secondary
    background: transparent
    hover: background --bg-elevated
```

---

### 6.5 Loading 狀態

**不使用大型 spinner。** 仿 Linear 的 activity log 風格，在 Run 按鈕位置顯示逐步進度文字：

```
Run 按鈕區域替換為：

  ── Detecting entities...         ← step 1，顯示約 1–3s
  ── Masking document...           ← step 2
  ── Asking Claude...              ← step 3（最久，10–20s）
  ── Restoring values...           ← step 4

樣式：
  font: --text-sm, --text-secondary
  每行前一個細小點動畫 (●) 或 Linear 風格的方形 spinner (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏)
  純 CSS animation，NO loading overlay
```

輸出面板在 loading 期間：顯示 skeleton 佔位（3 條灰色細線，--bg-elevated），不 blank。

---

### 6.6 錯誤處理

**不使用 alert()。** 在 Run 按鈕下方 inline 顯示：

```
  ✕ Claude API error 401: Invalid API key.

  樣式：
    color: --status-error
    font: --text-sm
    margin-top: 8px
    display: flex, align-items: center, gap: 6px

  ✕ 圖示：16×16 circle-x，純 CSS 或 SVG inline
```

---

## 7. Flask 後端規格（`app.py`）

```python
import os, sys
from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lumamask.pipeline import run_pipeline
from lumamask.detect import detect

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/run', methods=['POST'])
def run():
    data        = request.json
    api_key     = data.get('api_key', '').strip()
    text        = data.get('text', '').strip()
    instruction = data.get('instruction', '').strip()

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    if not text:
        return jsonify({'error': 'Document text is required'}), 400
    if not instruction:
        return jsonify({'error': 'Instruction is required'}), 400

    os.environ['ANTHROPIC_API_KEY'] = api_key
    try:
        result     = run_pipeline(text, instruction)
        detections = detect(text)
        counts     = {}
        for d in detections:
            et = d['entity_type']
            counts[et] = counts.get(et, 0) + 1

        return jsonify({
            'detection_summary': counts,          # {entity_type: count}
            'masked':            result['masked'],
            'ai_reply_masked':   result['ai_reply_tokenised'],
            'final_answer':      result['ai_reply_restored'],
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    finally:
        os.environ.pop('ANTHROPIC_API_KEY', None)

if __name__ == '__main__':
    import webbrowser, threading
    threading.Timer(1.2, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(debug=False, port=5000)
```

---

## 8. 啟動腳本（`run_ui.bat`）

```bat
@echo off
cd /d "%~dp0"
echo Starting Lumamask UI...
python app.py
pause
```

---

## 9. 目錄結構（完成後）

```
lumamask/              ← 現有 CLI 專案（不改動任何檔案）
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

lumamask-ui/           ← 新建 UI 專案（與 lumamask/ 同層）
  app.py
  run_ui.bat
  templates/
    index.html         ← 所有 CSS + JS inline，單一檔案
```

---

## 10. 安裝新增依賴

```bat
pip install flask
```
其餘套件（presidio, anthropic, spacy）已於 `install_windows.bat` 安裝。

---

## 11. 安全性注意事項

- API key **只存在 Python process 的記憶體**，`finally` 清除，不寫檔
- placeholder map（token ↔ 真實值）**不傳給前端**
- 後端只回傳前端需要顯示的 4 個欄位
- `debug=False`（Flask 生產模式）
- 僅 localhost，不對外開放

---

## 12. 給實作 Claude 的注意事項

1. **不要修改** `lumamask/` 目錄內任何檔案，UI 只是包一層 Flask
2. `sys.path.insert` 路徑依 `lumamask-ui/` 與 `lumamask/` 的相對位置調整
3. spaCy model 首次 load 需 3–5 秒；loading 期間前端應顯示 step 1 進度文字，不要讓用戶以為卡死
4. 所有錯誤以 JSON 回傳，前端 inline 顯示，不用 alert()，不讓 500 裸露
5. 整個前端放在 **單一 index.html**（CSS + JS inline），不需要 static server，避免 CORS 問題
6. Token 高亮 class name 用 `token-{type_lowercase}`（例 `token-person`、`token-money_amount`）
7. 字型：Inter（Google Fonts CDN）+ JetBrains Mono（Google Fonts CDN），兩個都用 `<link>` 引入
8. **不使用任何 UI framework**（無 Bootstrap、Tailwind、MUI）——純 CSS variables + vanilla JS，保持 Linear 的精準感
9. Tab 4 "Answer" 為 default active tab（run 完成後自動切換到此 tab）
10. Loading 進度：用 `setTimeout` 模擬 step 切換（偵測 1s → masking 1s → asking Claude 直到 response → restoring 0.5s）
