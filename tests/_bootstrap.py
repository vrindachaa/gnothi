"""Shared test bootstrap: make the plugin modules importable both as a plain
directory (via sys.path, used by this test run) and the way Hermes's loader
actually imports them (as a package with __path__ set) — exercised by
test_loader_discovery.py for DEV-12-style evidence."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import core  # noqa: E402
import stats  # noqa: E402
import tools  # noqa: E402
import schemas  # noqa: E402
