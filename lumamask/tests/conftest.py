"""
conftest.py — Session-scoped pytest fixtures.

The spaCy model (en_core_web_md) is expensive to load. Pre-warm the
AnalyzerEngine once per test session so individual tests don't pay the
startup cost. Import detect._get_analyzer() to trigger initialisation.
"""

import pytest
from lumamask.detect import _get_analyzer


@pytest.fixture(scope="session", autouse=True)
def warm_analyzer():
    """Load the Presidio AnalyzerEngine (and spaCy model) once for the whole session."""
    _get_analyzer()
