"""Analyzer for the derived-truth single-source gate (REV-0045 P1-4 repair).

The first gate attested SPELLING, not derivation: it matched the exact string
constants ``"epoch_sequence"`` / ``"producer_release:"`` inside a hard-coded
tuple of two store files, and its positive half required only that those files
IMPORT the shared helper. Codex defeated it in one line —
``event.payload.get("epoch_" + "sequence")`` restored a parallel derivation in a
listed store while all three gate tests stayed green.

This analyzer replaces spelling checks with four structural rules:

* **R1 — folded literals.** Every string expression is constant-folded before
  comparison (concatenation, f-strings, ``"".join`` of constants), so a split
  or interpolated literal is caught exactly like a plain one.
* **R2 — auditable payload keys.** A store may read ``payload`` only with a
  constant key. A computed key cannot be audited by any static rule, so it is
  refused unless the line carries an explicit disclosure marker. This closes
  the evasion CLASS rather than the one evasion that was demonstrated.
* **R3 — the helper is called, not merely imported.** An import proves nothing
  about derivation; the gate requires a real call node.
* **R4 — discovery, not enumeration.** Store modules are found by locating
  ``StateStore`` subclasses, so a third store cannot appear outside the gate,
  and the parser exemption names one exact module rather than any path ending
  in ``projectors.py``.

Kept deliberately separate from the test module so the gate's own logic can be
exercised by committed adversarial fixtures — a control that has never been
attacked is not failure-capable, which is the defect this file exists to fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_CARRIER_KEYS = frozenset({"epoch_sequence"})
FORBIDDEN_SQL_FRAGMENTS = ("$.epoch_sequence",)
PARSER_PREFIX = "producer_release:"
# WO-0141R: the kernel's ratified derivation entry points. A store must call at
# least one. This is a SET, not a widening of the rule: R1/R2 still refuse every
# local derivation and every unauditable payload key, so the only thing a store
# can do with these is delegate. Adding a name here is a claim that the function
# is kernel-owned and single-sourced — check that before adding one.
SHARED_HELPERS = frozenset(
    {
        "contributed_epoch_sequence",
        "next_release_sequence",
    }
)
PARSER_MODULE = "app/events/projectors.py"
DYNAMIC_KEY_MARKER = "derived-truth-gate: dynamic-key-ok"


def fold_str(node: ast.AST) -> str | None:
    """Best-effort constant fold of a string expression, else ``None``.

    Handles the shapes an evasion realistically takes: a plain constant,
    ``"a" + "b"``, an f-string whose parts are all constant, and
    ``"".join([...])`` over constants.
    """

    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = fold_str(node.left), fold_str(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts = [fold_str(v) for v in node.values]
        return None if any(p is None for p in parts) else "".join(parts)  # type: ignore[arg-type]
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "join"
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.List, ast.Tuple))
        ):
            sep = fold_str(func.value)
            items = [fold_str(e) for e in node.args[0].elts]
            if sep is not None and not any(i is None for i in items):
                return sep.join(items)  # type: ignore[arg-type]
    return None


def _is_payload_read(node: ast.AST) -> ast.AST | None:
    """Return the key expression if ``node`` reads a ``payload`` mapping."""

    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "payload"
            and node.args
        ):
            return node.args[0]
    if isinstance(node, ast.Subscript):
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "payload":
            return node.slice
    return None


def analyze_store_module(source: str, *, label: str) -> list[str]:
    """Violations of R1-R3 for one store module."""

    violations: list[str] = []
    tree = ast.parse(source)
    lines = source.splitlines()

    for node in ast.walk(tree):
        # R1 — any folded string equal to a forbidden carrier, anywhere.
        folded = fold_str(node)
        if folded is not None:
            if folded in FORBIDDEN_CARRIER_KEYS:
                violations.append(
                    f"{label}:{getattr(node, 'lineno', '?')}: derives the epoch-sequence "
                    f"carrier directly (folded literal {folded!r}) — route it through "
                    f"one of {sorted(SHARED_HELPERS)}"
                )
            for fragment in FORBIDDEN_SQL_FRAGMENTS:
                if fragment in folded:
                    violations.append(
                        f"{label}:{getattr(node, 'lineno', '?')}: SQL reads the carrier "
                        f"({fragment!r}) — route it through the kernel"
                    )

        # R2 — payload reads must use auditable constant keys.
        key = _is_payload_read(node)
        if key is not None and fold_str(key) is None:
            lineno = getattr(node, "lineno", 0)
            # Window covers the node line plus three above, so a disclosure
            # may wrap onto multiple comment lines.
            context = "\n".join(lines[max(0, lineno - 4) : lineno])
            if DYNAMIC_KEY_MARKER not in context:
                violations.append(
                    f"{label}:{lineno}: payload read with a computed key cannot be "
                    f"audited; use a constant key or disclose with "
                    f"'# {DYNAMIC_KEY_MARKER}: <reason>'"
                )

    # R3 — the shared helper must actually be CALLED.
    called = any(
        isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id in SHARED_HELPERS)
            or (isinstance(n.func, ast.Attribute) and n.func.attr in SHARED_HELPERS)
        )
        for n in ast.walk(tree)
    )
    if not called:
        violations.append(
            f"{label}: never CALLS any of {sorted(SHARED_HELPERS)} — an import "
            "alone proves no derivation goes through the shared source"
        )
    return violations


def analyze_parser_ownership(source: str, *, label: str) -> list[str]:
    """R4 — only the one ratified module may hold the release-key prefix."""

    if label == PARSER_MODULE:
        return []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if fold_str(node) == PARSER_PREFIX:
            return [
                f"{label}:{getattr(node, 'lineno', '?')}: second release-key parser — "
                f"decoding lives only in {PARSER_MODULE}"
            ]
    return []


def discover_store_modules(repo_root: Path) -> dict[str, Path]:
    """Find every StateStore implementation, so a NEW store cannot dodge the gate."""

    found: dict[str, Path] = {}
    for path in sorted((repo_root / "app" / "store").glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == "StateStore" for b in node.bases
            ):
                found[path.relative_to(repo_root).as_posix()] = path
                break
    return found
