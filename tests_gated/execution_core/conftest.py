"""Import only pure test support for the explicitly invoked gated suites."""

from __future__ import annotations

import sys
from pathlib import Path


_SUPPORT_ROOT = Path(__file__).resolve().parents[2] / "tests" / "execution_core"
support_text = str(_SUPPORT_ROOT)
if support_text not in sys.path:
    sys.path.insert(0, support_text)
