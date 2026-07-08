"""Consolidated script tests for the AI Project OS harness (WO-0601).

Covers: version consistency in both layouts (Finding 1), both Fable dialects
(Finding 2 / D1), work-order scope checks, honest stub exit codes (Finding 9),
and the MCP spec check in both layouts.
"""
from conftest import PKG, SCRIPTS, run_script

VERSION_SCRIPT = "check_version_consistency.py"
MCP_SCRIPT = "check_mcp_spec.py"
FABLE_SCRIPT = SCRIPTS / "check_fable_done.py"
SCOPE_SCRIPT = SCRIPTS / "check_work_order_scope.py"


# ===== Version consistency: must work in BOTH supported layouts (Finding 1) =====

def test_version_check_passes_in_package_layout():
    result = run_script(SCRIPTS / VERSION_SCRIPT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERSION CHECK PASSED" in result.stdout


def test_version_check_passes_in_simulated_install_layout(installed_repo):
    """Red on v0.5.0: the script anchored on __file__ position and reported
    every checked file as missing once installed under .ai-os/."""
    script = installed_repo / ".ai-os" / "scripts" / VERSION_SCRIPT
    result = run_script(script, cwd=installed_repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERSION CHECK PASSED" in result.stdout


# ===== Fable DONE checker: both dialects (Finding 2, decision D1) =====

YAML_DIALECT_TRANSCRIPT = """\
fable_done:
  task: "example"
  done_when_results:
    - item: "behavior x"
      status: MET
      evidence: "pytest -q -> 3 passed"
  status: VERIFIED

evidence:
  command: "pytest -q"
  result: PASS
  decisive_output: "3 passed"
"""

PROSE_DIALECT_TRANSCRIPT = """\
[DONE] Done-when items: behavior x -> met |
Evidence: pytest -q -> 3 passed |
Scope check: all changed lines trace to the task |
STATUS: VERIFIED
"""

VERIFIED_WITHOUT_EVIDENCE_TRANSCRIPT = """\
[DONE] Done-when items: behavior x -> met |
STATUS: VERIFIED
"""


def _transcript(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_yaml_dialect_passes(tmp_path):
    transcript = _transcript(tmp_path, "yaml.md", YAML_DIALECT_TRANSCRIPT)
    result = run_script(FABLE_SCRIPT, [transcript])
    assert result.returncode == 0, result.stdout
    assert "FABLE CHECK PASSED" in result.stdout


def test_prose_dialect_passes(tmp_path):
    """Red on v0.5.0: the checker only accepted [FABLE DONE] / fable_done: and
    rejected the skill-edition prose transcript."""
    transcript = _transcript(tmp_path, "prose.md", PROSE_DIALECT_TRANSCRIPT)
    result = run_script(FABLE_SCRIPT, [transcript])
    assert result.returncode == 0, result.stdout
    assert "FABLE CHECK PASSED" in result.stdout


def test_verified_without_evidence_fails(tmp_path):
    transcript = _transcript(tmp_path, "bad.md", VERIFIED_WITHOUT_EVIDENCE_TRANSCRIPT)
    result = run_script(FABLE_SCRIPT, [transcript])
    assert result.returncode == 1, result.stdout
    assert "FABLE CHECK FAILED" in result.stdout


# ===== Scope check: forbidden / out-of-scope / in-scope =====

WORK_ORDER = """\
---
type: Work Order
status: ACTIVE
---

## Allowed paths

```yaml
allowed_paths:
  - src/mod/**
  - tests/mod/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - src/auth/**
```
"""


def _work_order(tmp_path):
    p = tmp_path / "WO-0001.md"
    p.write_text(WORK_ORDER, encoding="utf-8")
    return p


def test_in_scope_changes_pass(tmp_path):
    result = run_script(SCOPE_SCRIPT, [_work_order(tmp_path)], stdin_text="src/mod/a.py\ntests/mod/test_a.py\n")
    assert result.returncode == 0, result.stdout
    assert "SCOPE CHECK PASSED" in result.stdout


def test_out_of_scope_change_fails(tmp_path):
    result = run_script(SCOPE_SCRIPT, [_work_order(tmp_path)], stdin_text="docs/readme.md\n")
    assert result.returncode == 1
    assert "outside allowed paths" in result.stdout


def test_forbidden_path_change_fails(tmp_path):
    result = run_script(SCOPE_SCRIPT, [_work_order(tmp_path)], stdin_text="src/auth/keys.py\n")
    assert result.returncode == 1
    assert "forbidden path changed" in result.stdout


# The Phase-1 "stubs must exit 3" tests were retired in WO-0603: the disposition
# and hygiene stubs were replaced by real checks (covered in test_phase3_checks.py).


# ===== MCP spec check: Phase 1 file set + installed-layout skip =====

def test_mcp_spec_check_passes_in_package_layout():
    result = run_script(SCRIPTS / MCP_SCRIPT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP SPEC CHECK PASSED" in result.stdout


def test_mcp_spec_check_skips_cleanly_when_mcp_not_installed(installed_repo):
    """In an installed repo without the (conditional) .ai-os/mcp tree, the check
    must skip with a clear message instead of failing on every missing path."""
    script = installed_repo / ".ai-os" / "scripts" / MCP_SCRIPT
    result = run_script(script, cwd=installed_repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skip" in result.stdout.lower()


def test_mcp_spec_check_fails_on_missing_spec_file(tmp_path):
    """Negative case (D6b): an mcp/ tree missing required spec files fails."""
    repo = tmp_path / "repo"
    (repo / "mcp").mkdir(parents=True)
    (repo / "AI_OS_MANIFEST.yaml").write_text('os_version: "0.7.0"\n', encoding="utf-8")
    (repo / "mcp" / "README.md").write_text("mcp", encoding="utf-8")
    result = run_script(SCRIPTS / MCP_SCRIPT, cwd=repo)
    assert result.returncode == 1, result.stdout
    assert "missing" in result.stdout
