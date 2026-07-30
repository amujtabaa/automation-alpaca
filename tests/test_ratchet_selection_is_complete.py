"""The ADR-015 ratchet's test selection may not silently fall behind.

`pyproject.toml`'s `pytest_add_cli_args_test_selection` names the test modules
mutmut runs against the mutated kernel. It was written before WO-0141 and still
listed four files, so every pin added since was invisible to the ratchet — a
mutant that inverted the dispatch in `contributed_epoch_sequence`, making it
return `None` for every event, survived a complete run because the test that
pins that behavior was not selected.

That is the same failure as the F-1 caller table and the same cure: an
enumerated list is only durable when something machine-consumed refuses to let
it drift. This gate does not judge whether a test is *good*; it refuses to let a
test module that exercises the mutated source appear outside the selection
without a human deciding.

Deliberately narrow in one respect: modules are matched by whether they import
the mutated module, not by name. Naming conventions are a spelling check, and
this project has already shipped three gates that attested spelling.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# `tomllib` is stdlib from 3.11, and D-7(a) (ratified 2026-07-29) sets the supported
# floor at 3.11 — so the third-party `toml` fallback that used to sit here was
# unreachable on every interpreter this repo runs on. Its comment also said "the
# pinned interpreter is 3.12", which the same ratification made false. Removed rather
# than re-worded: a dead branch guarded by a version check invites the reader to
# believe some supported interpreter takes it.
from tomllib import loads

REPO = Path(__file__).resolve().parents[1]

# Modules that import the kernel but are deliberately NOT run under mutation,
# each with the reason. A static AST gate cannot be killed by a mutant of the
# code it reads, so running it would only add noise to the survivor count.
DELIBERATELY_EXCLUDED = {
    # AST/structural gates: they read source text, so a behavioral mutant of the
    # kernel cannot change their outcome.
    "tests/test_derived_truth_single_source.py": "static AST gate over source text",
    "tests/test_wo0141_append_caller_gate.py": "static AST gate over source text",
    "tests/r2_conformance_oracle.py": "AST/spec oracle, not a behavioral suite",
}


def _mutated_modules() -> list[str]:
    config = loads((REPO / "pyproject.toml").read_text("utf-8"))["tool"]["mutmut"]
    return [p.replace("/", ".").removesuffix(".py") for p in config["source_paths"]]


def _selected() -> set[str]:
    config = loads((REPO / "pyproject.toml").read_text("utf-8"))["tool"]["mutmut"]
    return set(config["pytest_add_cli_args_test_selection"])


def _imports_any(source: str, modules: list[str]) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(
                node.module == m or node.module.startswith(m + ".") for m in modules
            ):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    alias.name == m or alias.name.startswith(m + ".") for m in modules
                ):
                    return True
    return False


def test_every_test_module_touching_the_kernel_is_selected_or_excused() -> None:
    """The list may not fall behind the tests that exercise the mutated source.

    If this fails, do NOT delete the assertion. Either add the module to
    `pytest_add_cli_args_test_selection` in `pyproject.toml`, or add it to
    `DELIBERATELY_EXCLUDED` with a reason a reviewer can check.
    """

    mutated = _mutated_modules()
    assert mutated, "mutmut source_paths is empty; the ratchet mutates nothing"

    selected = _selected()
    missing: list[str] = []
    for path in sorted((REPO / "tests").glob("*.py")):
        label = path.relative_to(REPO).as_posix()
        if label in selected or label in DELIBERATELY_EXCLUDED:
            continue
        if _imports_any(path.read_text(), mutated):
            missing.append(label)

    assert missing == [], (
        f"test modules exercise {mutated} but are not in the mutation ratchet's "
        f"selection: {missing}. Add them to pytest_add_cli_args_test_selection, "
        "or excuse them in DELIBERATELY_EXCLUDED with a reason."
    )


def test_the_selection_is_not_vacuous_and_every_entry_exists() -> None:
    """A selection naming files that do not exist runs fewer tests than it
    appears to — the quiet way a ratchet stops meaning anything."""

    selected = _selected()
    assert len(selected) >= 4, "suspiciously small selection"
    for label in sorted(selected):
        assert (REPO / label).is_file(), f"selected test module does not exist: {label}"


def test_exclusions_carry_a_reason_and_still_exist() -> None:
    """An exclusion list is a set of claims; each must be checkable."""

    for label, reason in DELIBERATELY_EXCLUDED.items():
        assert (REPO / label).is_file(), f"excluded module no longer exists: {label}"
        assert len(reason) > 15, f"exclusion for {label} needs a real reason"


@pytest.mark.parametrize(
    "source,expected",
    [
        ("from app.events.projectors import contributed_epoch_sequence\n", True),
        ("import app.events.projectors\n", True),
        ("from app.events import projectors\n", False),  # see the note below
        ("from app.store.memory import InMemoryStateStore\n", False),
    ],
)
def test_import_detection_shapes(source: str, expected: bool) -> None:
    """Pins what the detector does and does NOT see.

    `from app.events import projectors` is NOT detected — the import target is
    the package, not the module. That is a real limitation, pinned here rather
    than left for someone to discover: this gate reduces the chance of drift, it
    does not eliminate it, and saying so is the difference between a control and
    a claim.
    """

    assert _imports_any(source, ["app.events.projectors"]) is expected
