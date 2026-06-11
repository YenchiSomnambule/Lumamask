"""
test_detect_bundled.py — Tests for detect._get_analyzer() SPACY_DATA branch.

Exercises the exe-bundle code path where SPACY_DATA env var is set and
spaCy is loaded directly from the given path rather than via the NlpEngine
provider.  The real spaCy model is used so the test also validates that the
SPACY_DATA path (pointing at the actual installed model) works end-to-end.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def reset_analyzer():
    """Force _get_analyzer() to re-initialise for each test."""
    import lumamask.detect as det
    old = det._analyzer
    det._analyzer = None
    yield
    det._analyzer = None
    if old is not None:
        det._analyzer = old


class TestSpacyDataEnvVar:

    def test_normal_path_works_without_spacy_data(self, monkeypatch):
        """Standard (non-bundled) path: SPACY_DATA not set."""
        monkeypatch.delenv("SPACY_DATA", raising=False)
        from lumamask.detect import _get_analyzer
        analyzer = _get_analyzer()
        assert analyzer is not None

    def _spacy_data_dir(self):
        """Return the directory that contains en_core_web_md/ (mirrors bundle layout)."""
        import en_core_web_md
        # __file__ is .../en_core_web_md/__init__.py → parent is en_core_web_md/ → parent is dist-packages/
        return os.path.dirname(os.path.dirname(en_core_web_md.__file__))

    def test_bundled_path_works_with_valid_spacy_data(self, monkeypatch):
        """Bundle path: SPACY_DATA points at directory containing en_core_web_md/."""
        monkeypatch.setenv("SPACY_DATA", self._spacy_data_dir())

        from lumamask.detect import _get_analyzer
        analyzer = _get_analyzer()
        assert analyzer is not None

    def test_detect_still_works_with_spacy_data_set(self, monkeypatch):
        """End-to-end: detect() returns results when using the bundled path."""
        monkeypatch.setenv("SPACY_DATA", self._spacy_data_dir())

        from lumamask.detect import detect
        results = detect("Send $1,000 to john.doe@example.com")
        entity_types = {r["entity_type"] for r in results}
        assert "MONEY_AMOUNT" in entity_types
        assert "EMAIL_ADDRESS" in entity_types

    def test_bundled_path_invalid_raises(self, monkeypatch, tmp_path):
        """Bundle path with a non-existent model dir should raise."""
        monkeypatch.setenv("SPACY_DATA", str(tmp_path))  # no model inside
        from lumamask.detect import _get_analyzer
        with pytest.raises(Exception):
            _get_analyzer()
