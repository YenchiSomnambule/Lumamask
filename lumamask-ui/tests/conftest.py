"""conftest.py — make `import app` and `import entry` resolve to lumamask-ui/."""

import os
import sys
from unittest.mock import MagicMock

# Add lumamask-ui/ to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub out webview so entry.py can be imported on non-Windows systems
if "webview" not in sys.modules:
    sys.modules["webview"] = MagicMock()
