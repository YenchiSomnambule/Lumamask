# Lumamask — EXE Packaging Blueprint

**Goal:** Ship `Lumamask.exe` — a single double-clickable file that opens a native desktop window
(no browser, no Python install required) and runs the full pseudonymisation pipeline.

**Stack:** PyWebView (native window) + Flask (local HTTP backend) + PyInstaller (bundler)

---

## Architecture

```
User double-clicks Lumamask.exe
        │
        ▼
  entry.py  ──► starts Flask server on port 5000 (background thread)
        │         polls until server is ready
        ▼
  pywebview.create_window("Lumamask", "http://localhost:5000")
        │
        ▼
  Native OS window shows the existing index.html UI
        │
  User closes window
        ▼
  Flask thread is killed → process exits cleanly
```

No browser is opened. The user sees only a native Windows window titled "Lumamask".

---

## Files to Create / Modify

### 1. `lumamask-ui/entry.py` — New entry point

Replaces the `if __name__ == "__main__"` block in `app.py`.
Flask runs in a daemon thread; PyWebView blocks the main thread.

```python
"""entry.py — desktop entry point for Lumamask.exe"""

import sys
import os
import threading
import time
import socket

# ── resource path helper (needed when PyInstaller unpacks to _MEIPASS) ──────
def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

# ── tell spaCy where its model data lives inside the bundle ─────────────────
import spacy
spacy.util.registry.resolve  # force registry init
os.environ["SPACY_DATA"] = resource_path("spacy_models")

# ── import Flask app (must happen after env vars are set) ───────────────────
sys.path.insert(0, resource_path("lumamask_src"))   # see §4 below
import app as flask_app

# ── start Flask in a background daemon thread ────────────────────────────────
def _run_flask():
    flask_app.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

t = threading.Thread(target=_run_flask, daemon=True)
t.start()

# ── wait for Flask to be ready (max 30 s) ────────────────────────────────────
def _wait_for_flask(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 5000), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False

if not _wait_for_flask():
    import tkinter, tkinter.messagebox
    root = tkinter.Tk(); root.withdraw()
    tkinter.messagebox.showerror("Lumamask", "Failed to start local server.")
    sys.exit(1)

# ── open native window ────────────────────────────────────────────────────────
import webview

window = webview.create_window(
    "Lumamask",
    "http://127.0.0.1:5000",
    width=1280,
    height=820,
    resizable=True,
    min_size=(900, 600),
)
webview.start()   # blocks until window is closed
# process exits here — Flask daemon thread dies automatically
```

---

### 2. `lumamask-ui/lumamask.spec` — PyInstaller spec file

This is the most critical file. It tells PyInstaller what to bundle.

```python
# lumamask.spec
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── spaCy model: locate en_core_web_md installed on this machine ─────────────
import spacy
import en_core_web_md
SPACY_MODEL_PATH = os.path.dirname(en_core_web_md.__file__)

# ── collect data files ────────────────────────────────────────────────────────
datas = [
    # Flask HTML template
    ("templates/index.html",       "templates"),
    # spaCy model (bundles into spacy_models/en_core_web_md/...)
    (SPACY_MODEL_PATH,             "spacy_models/en_core_web_md"),
    # lumamask source package (detect, pseudonymize, restore, llm, pipeline)
    ("../lumamask/lumamask",       "lumamask_src/lumamask"),
]

# ── hidden imports PyInstaller won't find automatically ──────────────────────
hiddenimports = [
    # presidio
    "presidio_analyzer",
    "presidio_analyzer.nlp_engine",
    "presidio_analyzer.predefined_recognizers",
    "presidio_anonymizer",
    # spaCy internals
    "spacy.lang.en",
    "spacy.lang.en.stop_words",
    "spacy.pipeline.ner",
    "spacy.pipeline.tok2vec",
    "en_core_web_md",
    # Flask / Werkzeug
    "flask",
    "werkzeug.serving",
    "werkzeug.debug",
    # pywebview backends (Windows uses EdgeChromium or MSHTML)
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
    # anthropic SDK
    "anthropic",
    "httpx",
    # standard lib extras
    "tkinter",
]

hiddenimports += collect_submodules("presidio_analyzer")
hiddenimports += collect_submodules("presidio_anonymizer")

a = Analysis(
    ["entry.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "PIL", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Lumamask",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # compress with UPX if installed (optional)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # no CMD window pops up
    icon="lumamask.ico",         # optional — see §5
    onefile=True,
)
```

---

### 3. `lumamask-ui/build.bat` — One-click build script

```bat
@echo off
echo =============================================
echo  Lumamask EXE Builder
echo =============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing build dependencies...
pip install pyinstaller pywebview --quiet

echo [2/3] Building Lumamask.exe (this takes 3-5 minutes)...
pyinstaller lumamask.spec --clean --noconfirm

echo [3/3] Done!
echo.
echo  Output: dist\Lumamask.exe
echo  Size will be ~300-500 MB (includes Python + spaCy model)
echo.
pause
```

---

### 4. Source layout adjustment

`entry.py` adds `lumamask_src/` to `sys.path` so that `from lumamask.pipeline import ...`
resolves correctly inside the bundle. The spec's `datas` copies the lumamask package into
`lumamask_src/lumamask/` inside the bundle.

No changes to `app.py` are needed except **removing the `if __name__ == "__main__"` block**
(entry.py takes over that role). The `app` object and `/api/run` route stay exactly as-is.

---

### 5. Optional: App icon

Create a 256×256 `lumamask.ico` file and place it in `lumamask-ui/`.
Remove `icon="lumamask.ico"` from the spec if you skip this.

---

## Build Instructions (step by step)

1. Install build tools:
   ```
   pip install pyinstaller pywebview
   ```

2. Verify spaCy model is installed on your build machine:
   ```
   python -m spacy validate
   ```
   Should show `en_core_web_md` as installed.

3. Run the build:
   ```
   cd C:\Users\louisb\Documents\GitHub\Lumamask\lumamask-ui
   pyinstaller lumamask.spec --clean
   ```

4. Output: `lumamask-ui\dist\Lumamask.exe`

5. Test it on a clean machine (no Python, no packages installed).

---

## Expected Output

| Property | Value |
|---|---|
| File | `dist/Lumamask.exe` |
| Size | ~300–500 MB |
| Cold start | 5–15 seconds (spaCy model loads) |
| Window | Native Windows window, 1280×820 |
| Browser required | No |
| Python required | No |
| Internet required | Only for Anthropic API calls |

---

## Known Challenges & Mitigations

### spaCy model path
PyInstaller changes `__file__` paths. `entry.py` sets `SPACY_DATA` env var to point
to the bundled model before any lumamask code is imported. The `_get_analyzer()` function
in `detect.py` needs a one-line fix to respect this:

```python
# In detect.py — _get_analyzer(), replace the nlp_configuration block:
model_name = "en_core_web_md"
spacy_data = os.environ.get("SPACY_DATA")
if spacy_data:
    spacy.util.registry.resolve  # ensure registry is live
    nlp = spacy.load(os.path.join(spacy_data, model_name))
    # ... pass nlp directly to NlpEngineProvider
```
*(Full diff shown in Implementation Notes below)*

### presidio hidden imports
Presidio uses dynamic `import_module()` internally. The `collect_submodules` call in the
spec file catches these, but if a recognizer fails to load at runtime, add its module path
to `hiddenimports` in the spec.

### PyWebView on Windows
PyWebView on Windows defaults to the Edge WebView2 runtime (ships with Windows 10/11).
If the target machine doesn't have it, add this fallback in `entry.py`:
```python
webview.start(gui="cef")   # fallback to bundled CEF browser
```
And add `pywebview[cef]` to the pip install in `build.bat`.

### Antivirus false positives
PyInstaller executables sometimes trigger antivirus warnings. Signing the exe with a code
signing certificate resolves this for distribution. For internal use, it can be ignored.

### File size
The main contributors: Python runtime (~30 MB), spaCy model (~50 MB), presidio + dependencies
(~80 MB), PyWebView/Edge glue (~20 MB). Expect 250–400 MB total. UPX compression in the spec
reduces this by ~30%.

---

## Implementation Notes — detect.py change

The only code change needed (besides adding `entry.py`) is in `detect.py`'s `_get_analyzer()`:

```python
# BEFORE (current):
configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
}
provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()

# AFTER (exe-compatible):
import os as _os
_spacy_data = _os.environ.get("SPACY_DATA")
if _spacy_data:
    import spacy as _spacy
    _nlp = _spacy.load(_os.path.join(_spacy_data, "en_core_web_md"))
    from presidio_analyzer.nlp_engine import SpacyNlpEngine
    nlp_engine = SpacyNlpEngine(models={"en": _nlp})
else:
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
```

This keeps the CLI and Flask dev server working unchanged (no `SPACY_DATA` env var set),
while enabling the bundled exe to find the model.

---

## Delivery Checklist

- [ ] Create `lumamask-ui/entry.py`
- [ ] Create `lumamask-ui/lumamask.spec`
- [ ] Create `lumamask-ui/build.bat`
- [ ] Patch `detect.py` `_get_analyzer()` for bundled spaCy path
- [ ] Remove `if __name__ == "__main__"` block from `app.py`
- [ ] Run `build.bat` on Windows build machine
- [ ] Test `dist/Lumamask.exe` on a clean machine
- [ ] (Optional) Add `lumamask.ico` icon
- [ ] (Optional) Sign the exe for distribution
