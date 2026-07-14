"""Pytest adapter that redirects portable WO-0018 tests to SOL-0001.

The manifest documents the exact 35 rival-facing / 17 incumbent-only split.
This plugin refuses to run if the selected test modules did not bind the rival
``decide`` before collection, preventing an accidentally green incumbent run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import settings

_TARGET: ModuleType | None = None
_TARGET_PATH: Path | None = None
_TARGET_SHA: str | None = None
_DECIDE_TEST_FILES = {
    "test_wo0018_sellside_policy.py",
    "test_wo0018_sellside_properties.py",
}


def pytest_configure(config: pytest.Config) -> None:
    global _TARGET, _TARGET_PATH, _TARGET_SHA

    configured = os.environ.get("SOL_POLICY_TARGET")
    _TARGET_PATH = (
        Path(configured) if configured else Path(__file__).with_name("sol_policy.py")
    ).resolve()
    spec = importlib.util.spec_from_file_location(
        "_sol0001_policy_under_test", _TARGET_PATH
    )
    if spec is None or spec.loader is None:
        raise pytest.UsageError(f"cannot load SOL policy: {_TARGET_PATH}")
    target = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = target
    spec.loader.exec_module(target)
    if not callable(getattr(target, "decide", None)):
        raise pytest.UsageError(f"{_TARGET_PATH} has no callable decide")

    import app.sellside.policy as incumbent_policy

    incumbent_policy.decide = target.decide
    _TARGET = target
    _TARGET_SHA = hashlib.sha256(_TARGET_PATH.read_bytes()).hexdigest()

    settings.register_profile(
        "sol0001_conformance",
        database=None,
        derandomize=True,
    )
    settings.load_profile("sol0001_conformance")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    assert _TARGET is not None
    seen = False
    for item in items:
        if item.path.name not in _DECIDE_TEST_FILES:
            continue
        seen = True
        module = getattr(item, "module", None)
        if module is None or getattr(module, "decide", None) is not _TARGET.decide:
            raise pytest.UsageError(
                f"{item.path.name} did not bind SOL-0001 decide before collection"
            )
    if not seen:
        raise pytest.UsageError("no rival-facing conformance tests were collected")


def pytest_report_header(config: pytest.Config) -> str:
    return f"SOL target={_TARGET_PATH} sha256={_TARGET_SHA}"
