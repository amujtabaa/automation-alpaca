"""Regression pins for completed-folder work-order disposition hygiene (WO-0120)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / ".ai-os" / "scripts"


def _load_checker():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_work_order_disposition", _SCRIPTS / "check_work_order_disposition.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def test_completed_folder_rejects_noncompleted_status(tmp_path: Path) -> None:
    completed = tmp_path / "work" / "completed" / "keep"
    completed.mkdir(parents=True)
    (completed / "WO-0999-fixture.md").write_text(
        """---
type: Work Order
title: completed-folder draft fixture
status: DRAFT
work_order_id: WO-0999
disposition: [RESULT_SUMMARY_KEPT]
---
""",
        encoding="utf-8",
    )

    failures, warnings = checker.analyze(tmp_path)

    assert warnings == []
    assert any(
        "WO-0999" in failure and "completed folder" in failure for failure in failures
    )
