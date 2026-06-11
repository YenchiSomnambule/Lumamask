"""conftest.py — make `import app` resolve to lumamask-ui/app.py."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
