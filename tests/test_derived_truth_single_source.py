"""Structural gates: derived sequence truth is single-sourced (ADR-014 adjacent).

WO-0140's round-2 P0s shared one root cause — "what epoch sequence does this
history prove?" had several independent implementations, so fixing any one said
nothing about the others (REV-0045 addendum-02; AUDIT-0001 named the same
meta-root a campaign earlier). The cure was one shared function,
``contributed_epoch_sequence``, consumed everywhere.

**REV-0045 addendum-03 P1-4:** the first version of this gate matched exact
string constants in a hard-coded file list and required only an import. Codex
defeated it with ``event.payload.get("epoch_" + "sequence")`` — a parallel
derivation restored in a listed store, all three tests green. The analyzer in
``tests/_derived_truth_gate.py`` now folds string expressions, refuses
unauditable computed payload keys, requires a real call site, and discovers
store modules instead of enumerating them.

The adversarial fixtures below are the point: they replay the demonstrated
evasion and its siblings against the analyzer itself, so this control is
exercised by committed negative evidence rather than asserted to work.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests._derived_truth_gate import (
    DYNAMIC_KEY_MARKER,
    analyze_parser_ownership,
    analyze_store_module,
    discover_store_modules,
    fold_str,
)

REPO = Path(__file__).resolve().parents[1]

_CLEAN_STORE = """
from app.events.projectors import contributed_epoch_sequence

class InMemoryStateStore(StateStore):
    def floor(self, producer_id):
        floor = 0
        for event in self._execution_events:
            contributed = contributed_epoch_sequence(event, producer_id=producer_id)
            if contributed is not None:
                floor = max(floor, contributed)
        return floor
"""


def _store(body: str) -> str:
    return (
        "from app.events.projectors import contributed_epoch_sequence\n"
        "class InMemoryStateStore(StateStore):\n"
        "    def legitimate(self, event, producer_id):\n"
        "        return contributed_epoch_sequence(event, producer_id=producer_id)\n"
        "    def floor(self, producer_id):\n" + body
    )


# --------------------------------------------------------------------------- #
# The gate, over the real tree
# --------------------------------------------------------------------------- #


def test_every_state_store_is_discovered_not_enumerated() -> None:
    """R4: stores are found by subclass, so a third store cannot dodge the gate."""

    modules = discover_store_modules(REPO)
    assert set(modules) == {"app/store/memory.py", "app/store/sqlite.py"}, modules


def test_no_store_derives_the_carrier_or_reads_an_unauditable_key() -> None:
    """R1-R3 over the real store modules."""

    problems: list[str] = []
    for label, path in discover_store_modules(REPO).items():
        problems += analyze_store_module(path.read_text(), label=label)
    assert problems == [], problems


def test_release_key_parsing_lives_only_in_the_ratified_module() -> None:
    """R4: the decoder prefix appears in exactly one module, named exactly."""

    problems: list[str] = []
    for path in sorted((REPO / "app").rglob("*.py")):
        label = path.relative_to(REPO).as_posix()
        problems += analyze_parser_ownership(path.read_text(), label=label)
    assert problems == [], problems


# --------------------------------------------------------------------------- #
# Adversarial fixtures — the analyzer must CATCH each of these
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "expression,expected",
    [
        ('"epoch_sequence"', "epoch_sequence"),
        ('"epoch_" + "sequence"', "epoch_sequence"),  # the demonstrated evasion
        ('"epoch" + "_" + "sequence"', "epoch_sequence"),
        ('"".join(["epoch_", "sequence"])', "epoch_sequence"),
        ('"_".join(["epoch", "sequence"])', "epoch_sequence"),
    ],
)
def test_folder_defeats_literal_splitting(expression: str, expected: str) -> None:
    node = ast.parse(expression, mode="eval").body
    assert fold_str(node) == expected


def test_gate_catches_the_exact_evasion_codex_demonstrated() -> None:
    """``event.payload.get("epoch_" + "sequence")`` in a listed store — the
    parallel derivation that left the previous gate 3/3 green."""

    source = _store(
        '        raw = event.payload.get("epoch_" + "sequence")\n        return raw\n'
    )
    problems = analyze_store_module(source, label="app/store/memory.py")
    assert any("folded literal" in p for p in problems), problems


@pytest.mark.parametrize(
    "body",
    [
        '        return event.payload.get("epoch_sequence")\n',
        '        return event.payload["epoch_sequence"]\n',
        '        return event.payload.get("".join(["epoch_", "sequence"]))\n',
        "        cur.execute(\"SELECT json_extract(payload, '$.epoch_sequence')\")\n",
    ],
)
def test_gate_catches_every_carrier_read_shape(body: str) -> None:
    problems = analyze_store_module(_store(body), label="app/store/memory.py")
    assert problems, "a carrier read was not detected"


def test_gate_refuses_an_unauditable_computed_key() -> None:
    """A key the gate cannot fold is a key it cannot audit — refused outright,
    which closes the evasion class rather than one evasion."""

    source = _store("        return event.payload.get(some_name)\n")
    problems = analyze_store_module(source, label="app/store/memory.py")
    assert any("computed key" in p for p in problems), problems


def test_disclosed_dynamic_key_is_allowed() -> None:
    """The two legitimate idempotency-comparison loops disclose and pass."""

    source = _store(
        f"        # {DYNAMIC_KEY_MARKER}: idempotency comparison over a known map\n"
        "        return all(event.payload.get(k) == v for k, v in items)\n"
    )
    assert analyze_store_module(source, label="app/store/memory.py") == []


def test_gate_rejects_a_dead_import_that_is_never_called() -> None:
    """R3: importing the helper proves nothing about derivation."""

    source = (
        "from app.events.projectors import contributed_epoch_sequence\n"
        "class InMemoryStateStore(StateStore):\n"
        "    def floor(self, producer_id):\n"
        "        return 0\n"
    )
    problems = analyze_store_module(source, label="app/store/memory.py")
    assert any("never CALLS" in p for p in problems), problems


def test_gate_accepts_a_correct_store() -> None:
    """Non-vacuity: the clean shape must pass, or the gate proves nothing."""

    assert analyze_store_module(_CLEAN_STORE, label="app/store/memory.py") == []


def test_second_parser_is_refused_outside_the_ratified_module() -> None:
    source = 'prefix = "producer_release:"\n'
    assert analyze_parser_ownership(source, label="app/store/memory.py")
    assert analyze_parser_ownership(source, label="app/events/projectors.py") == []


def test_parser_exemption_does_not_match_a_lookalike_module() -> None:
    """The old rule exempted any path ending in projectors.py."""

    source = 'prefix = "producer_release:"\n'
    assert analyze_parser_ownership(source, label="app/store/projectors.py")
