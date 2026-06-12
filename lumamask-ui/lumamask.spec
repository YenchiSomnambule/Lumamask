# lumamask.spec — PyInstaller (>= 6.0) spec for Lumamask.exe
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── spaCy model: locate en_core_web_md installed on the build machine ────────
import en_core_web_md
SPACY_MODEL_PATH = os.path.dirname(en_core_web_md.__file__)

# ── collect data files ────────────────────────────────────────────────────────
datas = [
    # Flask HTML template
    ("templates/index.html",       "templates"),
    # spaCy model bundled under spacy_models/en_core_web_md/
    # (detect.py handles the versioned en_core_web_md-x.y.z/ sub-layout)
    (SPACY_MODEL_PATH,             "spacy_models/en_core_web_md"),
    # lumamask source package (detect, pseudonymize, restore, llm, pipeline)
    ("../lumamask/lumamask",       "lumamask_src/lumamask"),
]

# presidio ships recognizer config files (yaml/json) loaded at runtime
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
    # pywebview Windows backends (WebView2 renderer + WinForms glue)
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
    # anthropic SDK
    "anthropic",
    "httpx",
    # standard lib
    "tkinter",
    "tkinter.messagebox",
    # pkg_resources (pulled in by spaCy at runtime) vendors these; without
    # them the frozen app dies at startup in the pyi_rth_pkgres hook
    "pkg_resources.extern",
    "platformdirs",
    "jaraco.text",
    "jaraco.functools",
    "jaraco.context",
    "more_itertools",
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
    noarchive=False,
    # presidio opens conf files via paths relative to its modules
    # (recognizer_registry/../conf/*.yaml). Inside a frozen app the package
    # dirs don't exist on disk unless the source is collected too, and the
    # ".." component then fails to resolve. Collect presidio as source files.
    module_collection_mode={
        "presidio_analyzer": "pyz+py",
        "presidio_anonymizer": "pyz+py",
    },
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
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
)
