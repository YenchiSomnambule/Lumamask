# lumamask.spec — PyInstaller spec for Lumamask.exe
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── spaCy model: locate en_core_web_md installed on the build machine ────────
import en_core_web_md
SPACY_MODEL_PATH = os.path.dirname(en_core_web_md.__file__)

# ── collect data files ────────────────────────────────────────────────────────
datas = [
    # Flask HTML template
    ("templates/index.html",       "templates"),
    # spaCy model bundled under spacy_models/en_core_web_md/
    (SPACY_MODEL_PATH,             "spacy_models/en_core_web_md"),
    # lumamask source package (detect, pseudonymize, restore, llm, pipeline)
    ("../lumamask/lumamask",       "lumamask_src/lumamask"),
]

# Collect any *.json / *.cfg data files presidio ships
datas += collect_data_files("presidio_analyzer")
datas += collect_data_files("presidio_anonymizer")

# ── hidden imports PyInstaller won't discover automatically ──────────────────
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
    # pywebview Windows backends
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
    # anthropic SDK
    "anthropic",
    "httpx",
    # standard lib
    "tkinter",
    "tkinter.messagebox",
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
    excludes=["matplotlib", "PIL", "IPython", "jupyter", "notebook"],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no CMD window
    icon="lumamask.ico" if os.path.exists("lumamask.ico") else None,
    onefile=True,
)
