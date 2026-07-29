"""Analyzer for the append-seam caller gate (WO-0141 §5.4).

The F-1 reachability fact — *no production writer can mint a `PRODUCER_*` event
whose dedupe-key producer disagrees with its payload producer* — is what let the
ratified program keep D-1-b as defense-in-depth in WO-0142 instead of promoting
it ahead of WO-0141. It was established by enumerating every caller of the
public append seam and showing each one's `event_type` domain is closed.

**An enumeration in a document is inert evidence** (AUDIT-0003 S-3). It was true
at the SHA where it was written and silently false the first time a seventh
caller appears. This analyzer makes it machine-consumed and failure-capable:
adding a caller, or constructing a `PRODUCER_*` event outside the two ratified
builders, fails the build and forces the reachability argument to be re-derived
rather than assumed to still hold.

Two rules:

* **A — the append seam is a closed set.** Every production call of
  `append_execution_event` must appear in the ratified enumeration. The gate does
  not judge whether a new caller is safe; it refuses to let one appear without a
  human re-deriving F-1.
* **B — `PRODUCER_*` events have exactly two constructors.** Any
  `ExecutionEvent(...)` whose `event_type` is a `PRODUCER_*` member must live in
  the one module that mints the dedupe key from the same `producer_id` it puts in
  the payload.

Written as an analyzer over source text rather than as assertions inside a test
so its own logic can be attacked by committed fixtures — the P1-4 lesson: a gate
that has never been attacked is not failure-capable.
"""

from __future__ import annotations

import ast
from pathlib import Path

APPEND_SEAM = "append_execution_event"
PRODUCER_EVENT_PREFIX = "PRODUCER_"
EVENT_TYPE_ENUM = "ExecutionEventType"
BUILDER_MODULE = "app/store/core.py"

# The ratified F-1 enumeration (program §0, discharged 2026-07-28). Each entry's
# event_type domain was shown closed and non-PRODUCER_*. Changing this set is a
# reachability-argument change, not a mechanical edit.
RATIFIED_APPEND_CALLERS = frozenset(
    {
        "app/monitoring.py",
        "app/reconciliation.py",
    }
)


def _attr_chain(node: ast.AST) -> str | None:
    """Dotted name for an attribute/name chain, else ``None``."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attr_chain(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def find_append_callers(source: str, *, label: str) -> list[tuple[str, int]]:
    """Every call of the public append seam in one module."""

    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Matches `store.append_execution_event(...)` and a bare call alike;
        # the private per-store `_append_*_unlocked` sinks are deliberately NOT
        # matched — they take events the two ratified builders already minted.
        if isinstance(func, ast.Attribute) and func.attr == APPEND_SEAM:
            found.append((label, getattr(node, "lineno", 0)))
        elif isinstance(func, ast.Name) and func.id == APPEND_SEAM:
            found.append((label, getattr(node, "lineno", 0)))
    return found


def find_producer_event_constructions(source: str, *, label: str) -> list[str]:
    """Rule B — `ExecutionEvent(event_type=ExecutionEventType.PRODUCER_*)`
    outside the one ratified builder module."""

    if label == BUILDER_MODULE:
        return []
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if _attr_chain(node.func) not in {"ExecutionEvent", "models.ExecutionEvent"}:
            continue
        for keyword in node.keywords:
            if keyword.arg != "event_type":
                continue
            chain = _attr_chain(keyword.value)
            if chain is None:
                continue
            head, _, member = chain.rpartition(".")
            if head.endswith(EVENT_TYPE_ENUM) and member.startswith(
                PRODUCER_EVENT_PREFIX
            ):
                violations.append(
                    f"{label}:{getattr(node, 'lineno', '?')}: constructs "
                    f"{chain} outside {BUILDER_MODULE} — a PRODUCER_* event must "
                    "be minted by the ratified builders, which derive the dedupe "
                    "key from the same producer_id they place in the payload"
                )
    return violations


def production_modules(repo_root: Path) -> dict[str, Path]:
    """Discovered, not enumerated: every production module under ``app/``."""

    return {
        path.relative_to(repo_root).as_posix(): path
        for path in sorted((repo_root / "app").rglob("*.py"))
    }
