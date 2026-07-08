"""WO-0602 promotion tests (decision D6) + check_install.

Promoted scripts (no _stub suffix): check_work_order_scope, check_pkl,
check_version_consistency, check_fable_done. New behaviors: scope check
consumes sensitive_paths/forbidden_patterns from rules yaml; PKL check warns
on stale high-authority pages; check_install validates a repo against the
manifest install_map.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from conftest import PKG, SCRIPTS, run_script

RULES_YAML = """\
version: 0.7.0
os_version: 0.7.0
sensitive_paths:
  - "**/auth/**"
forbidden_patterns:
  - ".env"
  - "*.pem"
pkl_staleness_days: 90
"""

WORK_ORDER = """\
---
type: Work Order
status: ACTIVE
---

```yaml
allowed_paths:
  - src/**
```

```yaml
forbidden_paths:
  - docs/**
```
"""


def _rules_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "rules").mkdir(parents=True)
    (root / "AI_OS_MANIFEST.yaml").write_text("os_version: \"0.7.0\"\n", encoding="utf-8")
    (root / "rules" / "ai-os-rules.yaml").write_text(RULES_YAML, encoding="utf-8")
    wo = root / "WO-0001.md"
    wo.write_text(WORK_ORDER, encoding="utf-8")
    return root


# ===== promoted scope check: rules-yaml consumption =====

def test_scope_check_fails_on_forbidden_pattern_from_rules(tmp_path):
    root = _rules_repo(tmp_path)
    result = run_script(SCRIPTS / "check_work_order_scope.py", [root / "WO-0001.md"],
                        cwd=root, stdin_text="src/config/.env\n")
    assert result.returncode == 1, result.stdout
    assert "forbidden pattern" in result.stdout.lower()


def test_scope_check_warns_on_sensitive_path_from_rules(tmp_path):
    root = _rules_repo(tmp_path)
    result = run_script(SCRIPTS / "check_work_order_scope.py", [root / "WO-0001.md"],
                        cwd=root, stdin_text="src/auth/login.py\n")
    assert result.returncode == 0, result.stdout
    assert "sensitive" in result.stdout.lower()
    assert "checklist" in result.stdout.lower()


# ===== promoted PKL check: staleness warning for authority: high =====

STALE_HIGH_PAGE = """\
---
type: Module Knowledge
title: Old High Authority
status: active
authority: high
owner: architect
last_verified: 2020-01-01
tags: [old]
---

Content.
"""

FRESH_HIGH_PAGE = STALE_HIGH_PAGE.replace("2020-01-01", "2099-01-01").replace("Old", "Fresh")


def test_pkl_check_warns_on_stale_high_authority_page(tmp_path):
    root = _rules_repo(tmp_path)
    pkl = root / "pkl"
    pkl.mkdir()
    (pkl / "stale.md").write_text(STALE_HIGH_PAGE, encoding="utf-8")
    result = run_script(SCRIPTS / "check_pkl.py", [pkl], cwd=root)
    assert result.returncode == 0, result.stdout
    assert "stale" in result.stdout.lower()


def test_pkl_check_no_staleness_warning_for_fresh_page(tmp_path):
    root = _rules_repo(tmp_path)
    pkl = root / "pkl"
    pkl.mkdir()
    (pkl / "fresh.md").write_text(FRESH_HIGH_PAGE, encoding="utf-8")
    result = run_script(SCRIPTS / "check_pkl.py", [pkl], cwd=root)
    assert result.returncode == 0, result.stdout
    assert "stale" not in result.stdout.lower()


# ===== check_install =====

def _installed_repo(tmp_path: Path) -> Path:
    """Manifest-correct simulated install per the package install_map."""
    repo = tmp_path / "target"
    aios = repo / ".ai-os"
    (aios / "core").mkdir(parents=True)
    shutil.copy(PKG / "AI_OS_MANIFEST.yaml", aios / "AI_OS_MANIFEST.yaml")
    shutil.copy(PKG / "VERSION.md", aios / "VERSION.md")
    for doc in PKG.glob("[01]*.md"):
        name = doc.name
        if name.startswith(("01_", "02_")):
            continue
        (aios / "core" / name).write_text(doc.read_text(encoding="utf-8"), encoding="utf-8")
    for tree in ("adapters", "evals", "rules", "scripts", "templates"):
        shutil.copytree(PKG / tree, aios / tree)
    (repo / "pkl").mkdir()
    (repo / "work").mkdir()
    (repo / "CLAUDE.md").write_text(
        (PKG / "adapters" / "claude" / "CLAUDE.md.stub").read_text(encoding="utf-8"), encoding="utf-8")
    return repo


def test_check_install_passes_on_manifest_correct_install(tmp_path):
    repo = _installed_repo(tmp_path)
    result = run_script(SCRIPTS / "check_install.py", [repo])
    assert result.returncode == 0, result.stdout
    assert "INSTALL CHECK PASSED" in result.stdout


def test_check_install_fails_on_not_installed_leak(tmp_path):
    repo = _installed_repo(tmp_path)
    (repo / ".ai-os" / "core" / "01_DEEP_RESEARCH_FINDINGS.md").write_text("leak", encoding="utf-8")
    result = run_script(SCRIPTS / "check_install.py", [repo])
    assert result.returncode == 1, result.stdout
    assert "not_installed" in result.stdout


def test_check_install_fails_on_duplicate_marker_blocks(tmp_path):
    repo = _installed_repo(tmp_path)
    shim = repo / "CLAUDE.md"
    shim.write_text(shim.read_text(encoding="utf-8") * 2, encoding="utf-8")
    result = run_script(SCRIPTS / "check_install.py", [repo])
    assert result.returncode == 1, result.stdout
    assert "duplicate marker" in result.stdout.lower()


# ===== version check knows the server pyproject target =====

def test_version_check_covers_pyproject_target(tmp_path):
    text = (SCRIPTS / "check_version_consistency.py").read_text(encoding="utf-8")
    assert "target_ai_os_version" in text
