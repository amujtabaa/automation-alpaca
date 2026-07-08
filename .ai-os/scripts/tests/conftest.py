"""Shared helpers for AI Project OS script tests."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2]
SCRIPTS = PKG / "scripts"


def run_script(script: Path, args=(), cwd: Path | None = None, stdin_text: str | None = None):
    """Run a package script in a subprocess and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        input=stdin_text,
        cwd=str(cwd or PKG),
    )


@pytest.fixture()
def installed_repo(tmp_path: Path) -> Path:
    """Simulate the post-install layout the manifest install_map declares.

    Core docs under .ai-os/core/, VERSION.md and the manifest under .ai-os/,
    rules under .ai-os/rules/, scripts under .ai-os/scripts/.
    """
    repo = tmp_path / "repo"
    aios = repo / ".ai-os"
    (aios / "core").mkdir(parents=True)
    (aios / "rules").mkdir()
    (aios / "scripts").mkdir()
    shutil.copy(PKG / "AI_OS_MANIFEST.yaml", aios / "AI_OS_MANIFEST.yaml")
    shutil.copy(PKG / "VERSION.md", aios / "VERSION.md")
    for doc in ("00_START_HERE.md", "14_MCP_CONTROL_PLANE.md"):
        shutil.copy(PKG / doc, aios / "core" / doc)
    for rule_file in (PKG / "rules").glob("*.yaml"):
        shutil.copy(rule_file, aios / "rules" / rule_file.name)
    for script in SCRIPTS.glob("*.py"):
        shutil.copy(script, aios / "scripts" / script.name)
    (repo / "pkl").mkdir()
    (repo / "work").mkdir()
    return repo
