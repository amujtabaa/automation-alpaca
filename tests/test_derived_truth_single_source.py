"""ADR-014-adjacent structural gates: derived sequence truth is single-sourced.

WO-0140's four round-2 P0s shared one root cause — "what epoch sequence does
this history prove?" had seven independent implementations across the two
stores and the projector, so fixing any one said nothing about the others
(REV-0045 addendum-02; AUDIT-0001 called the same meta-root "the same truth
derived independently in two places" a full campaign earlier). The cure was a
single helper, ``contributed_epoch_sequence``, consumed everywhere.

These gates keep it that way MECHANICALLY. They are source-level (AST) checks:
a new parallel derivation compiles and passes behavioral tests just fine —
that is exactly how the class recurred — so only a structural gate can refuse
it at commit time. If one of these fails, the fix is to route the new consumer
through the shared helper in ``app/events/projectors.py``, not to widen the
allowlist.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

STORE_MODULES = ("store/memory.py", "store/sqlite.py")


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_stores_never_read_the_payload_epoch_sequence_carrier() -> None:
    """The stores must derive sequence truth ONLY via the shared projector
    helper — never by reading the raw payload carrier themselves.

    A payload read appears in source as the string constant "epoch_sequence"
    (dict access) or a SQL fragment containing "$.epoch_sequence"
    (json_extract). Keyword arguments to the ratified builders do not appear
    as string constants, so legitimate minting is invisible to this gate.
    """

    for rel in STORE_MODULES:
        constants = _string_constants(APP / rel)
        offenders = [
            value
            for value in constants
            if value == "epoch_sequence" or "$.epoch_sequence" in value
        ]
        assert offenders == [], (
            f"app/{rel} reads the payload epoch-sequence carrier directly "
            f"({offenders!r}); route it through contributed_epoch_sequence() "
            "instead — parallel derivations are how REV-0045's P0-3/P0-4 "
            "recurred."
        )


def test_release_key_parsing_lives_only_in_the_projector() -> None:
    """The length-prefixed release-key PARSER exists exactly once.

    Minting uses signal_dedupe_key("producer_release", ...) — the constant
    without a trailing colon. Parsing starts from the prefix WITH the colon,
    "producer_release:". Any module other than the projector holding the
    parsing prefix is a second decoder waiting to diverge from the mint
    (REV-0045 P0-5's shape).
    """

    holders = []
    for path in APP.rglob("*.py"):
        if any(str(path).endswith(m) for m in ("projectors.py",)):
            continue
        if any(v == "producer_release:" for v in _string_constants(path)):
            holders.append(str(path.relative_to(APP.parent)))
    assert holders == [], (
        f"second release-key parser prefix found in {holders!r}; the decoder "
        "is app/events/projectors.py:sequence_from_release_dedupe_key only."
    )


def test_stores_consume_the_shared_sequence_source() -> None:
    """Positive half of the gate: both stores import the shared helper —
    the single-source rule holds structurally, not by accident of grep."""

    for rel in STORE_MODULES:
        tree = ast.parse((APP / rel).read_text())
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "contributed_epoch_sequence" in imported, (
            f"app/{rel} no longer imports contributed_epoch_sequence — "
            "if its floor was rewritten, the shared-source rule just broke."
        )
