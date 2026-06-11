"""
test_entry.py — Unit tests for entry.py helper functions.

pywebview and tkinter are mocked throughout; no GUI is shown.
Flask is mocked so no server is started.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_entry():
    """Import entry module, patching webview so it doesn't fail on Linux."""
    webview_mock = MagicMock()
    with patch.dict("sys.modules", {"webview": webview_mock}):
        import importlib
        import entry
        importlib.reload(entry)
    return entry, webview_mock


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:

    def test_returns_path_relative_to_script_when_no_meipass(self):
        import entry
        result = entry.resource_path("templates")
        assert result.endswith("templates")
        assert os.path.isabs(result)

    def test_uses_meipass_when_set(self, tmp_path, monkeypatch):
        import entry
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        result = entry.resource_path("something")
        assert result == str(tmp_path / "something")

    def test_meipass_overrides_file_location(self, tmp_path, monkeypatch):
        import entry
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        result = entry.resource_path("x")
        assert result == str(tmp_path / "x")


# ---------------------------------------------------------------------------
# _configure_spacy
# ---------------------------------------------------------------------------

class TestConfigureSpacy:

    def test_sets_spacy_data_when_dir_exists(self, tmp_path, monkeypatch):
        import entry
        spacy_dir = tmp_path / "spacy_models"
        spacy_dir.mkdir()
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        monkeypatch.delenv("SPACY_DATA", raising=False)

        entry._configure_spacy()

        assert os.environ.get("SPACY_DATA") == str(spacy_dir)

    def test_does_not_set_spacy_data_when_dir_missing(self, tmp_path, monkeypatch):
        import entry
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        monkeypatch.delenv("SPACY_DATA", raising=False)

        entry._configure_spacy()

        assert "SPACY_DATA" not in os.environ

    def teardown_method(self):
        os.environ.pop("SPACY_DATA", None)


# ---------------------------------------------------------------------------
# _add_lumamask_src
# ---------------------------------------------------------------------------

class TestAddLumamaskSrc:

    def test_inserts_lumamask_src_into_sys_path(self, tmp_path, monkeypatch):
        import entry
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        src = str(tmp_path / "lumamask_src")
        if src in sys.path:
            sys.path.remove(src)

        entry._add_lumamask_src()

        assert src in sys.path

    def test_does_not_duplicate_if_already_present(self, tmp_path, monkeypatch):
        import entry
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        src = str(tmp_path / "lumamask_src")
        if src not in sys.path:
            sys.path.insert(0, src)

        entry._add_lumamask_src()

        assert sys.path.count(src) == 1

    def teardown_method(self):
        # Clean up any test paths left in sys.path
        sys.path[:] = [p for p in sys.path if "lumamask_src" not in p
                       or os.path.exists(p)]


# ---------------------------------------------------------------------------
# _wait_for_flask
# ---------------------------------------------------------------------------

class TestWaitForFlask:

    def test_returns_true_when_server_is_ready(self):
        """Start a real local socket server and confirm wait returns True."""
        import entry
        with socket.socket() as srv:
            srv.bind(("127.0.0.1", 0))
            port = srv.getsockname()[1]
            srv.listen(1)
            assert entry._wait_for_flask("127.0.0.1", port, timeout=3.0) is True

    def test_returns_false_when_nothing_listening(self):
        import entry
        # Use a port that's almost certainly free
        result = entry._wait_for_flask("127.0.0.1", 19999, timeout=0.6)
        assert result is False

    def test_eventually_succeeds_when_server_starts_late(self):
        """Server comes up 0.4 s after wait starts — should still succeed."""
        import entry
        with socket.socket() as srv:
            srv.bind(("127.0.0.1", 0))
            port = srv.getsockname()[1]

            def _delayed_listen():
                time.sleep(0.4)
                srv.listen(1)

            t = threading.Thread(target=_delayed_listen, daemon=True)
            t.start()
            assert entry._wait_for_flask("127.0.0.1", port, timeout=4.0) is True


# ---------------------------------------------------------------------------
# _show_error
# ---------------------------------------------------------------------------

class TestShowError:

    def test_falls_back_to_stderr_when_tkinter_unavailable(self, capsys, monkeypatch):
        import entry
        monkeypatch.setitem(sys.modules, "tkinter", None)
        entry._show_error("Something went wrong")
        captured = capsys.readouterr()
        assert "Something went wrong" in captured.err

    def test_uses_tkinter_messagebox_when_available(self):
        import entry
        tk_mock = MagicMock()
        with patch.dict("sys.modules", {"tkinter": tk_mock,
                                         "tkinter.messagebox": tk_mock.messagebox}):
            entry._show_error("test message")
        # Verify messagebox.showerror was called
        tk_mock.messagebox.showerror.assert_called_once()
        args = tk_mock.messagebox.showerror.call_args[0]
        assert "test message" in args


# ---------------------------------------------------------------------------
# main() — integration smoke tests (everything mocked)
# ---------------------------------------------------------------------------

class TestMain:

    def _make_server(self):
        """Create a server on a free port; return (server, port)."""
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        return srv, port

    def test_main_opens_window_when_server_ready(self, monkeypatch):
        import entry
        webview_mock = MagicMock()

        srv, port = self._make_server()
        try:
            monkeypatch.setattr(entry, "_configure_spacy", lambda: None)
            monkeypatch.setattr(entry, "_add_lumamask_src", lambda: None)
            monkeypatch.setattr(entry, "_start_flask", lambda: None)
            monkeypatch.setattr(
                entry, "_wait_for_flask",
                lambda host="127.0.0.1", port=5000, timeout=30.0: True,
            )
            with patch.dict("sys.modules", {"webview": webview_mock}):
                entry.main()
        finally:
            srv.close()

        webview_mock.create_window.assert_called_once()
        webview_mock.start.assert_called_once()

    def test_main_calls_sys_exit_when_server_fails(self, monkeypatch):
        import entry
        webview_mock = MagicMock()

        monkeypatch.setattr(entry, "_configure_spacy", lambda: None)
        monkeypatch.setattr(entry, "_add_lumamask_src", lambda: None)
        monkeypatch.setattr(entry, "_start_flask", lambda: None)
        monkeypatch.setattr(
            entry, "_wait_for_flask",
            lambda **kw: False,
        )
        monkeypatch.setattr(entry, "_show_error", lambda msg: None)

        with patch.dict("sys.modules", {"webview": webview_mock}):
            with pytest.raises(SystemExit) as exc:
                entry.main()
        assert exc.value.code == 1
        webview_mock.start.assert_not_called()
