"""entry.py — desktop entry point for Lumamask.exe"""

import sys
import os
import threading
import time
import socket


def resource_path(relative: str) -> str:
    """Resolve path relative to the bundle root or the script directory."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _configure_spacy():
    """Point spaCy at the bundled model directory when running from exe."""
    spacy_data = resource_path("spacy_models")
    if os.path.isdir(spacy_data):
        os.environ["SPACY_DATA"] = spacy_data


def _add_lumamask_src():
    """Make `from lumamask.xxx import ...` work inside the bundle."""
    src = resource_path("lumamask_src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _start_flask() -> threading.Thread:
    import app as flask_app
    t = threading.Thread(
        target=lambda: flask_app.app.run(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False
        ),
        daemon=True,
    )
    t.start()
    return t


def _wait_for_flask(host: str = "127.0.0.1", port: int = 5000, timeout: float = 30.0) -> bool:
    """Block until the Flask server accepts connections or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _show_error(message: str) -> None:
    try:
        import tkinter
        import tkinter.messagebox
        root = tkinter.Tk()
        root.withdraw()
        tkinter.messagebox.showerror("Lumamask", message)
        root.destroy()
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)


def main() -> None:
    _configure_spacy()
    _add_lumamask_src()

    _start_flask()

    if not _wait_for_flask():
        _show_error("Failed to start local server. Please try again.")
        sys.exit(1)

    import webview

    window = webview.create_window(
        "Lumamask",
        "http://127.0.0.1:5000",
        width=1280,
        height=820,
        resizable=True,
        min_size=(900, 600),
    )
    webview.start()
    # Flask daemon thread exits automatically when the main thread ends.


if __name__ == "__main__":
    main()
