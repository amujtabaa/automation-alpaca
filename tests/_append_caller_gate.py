"""Analyzer for the append-seam caller gate (WO-0141R §5.4).

The F-1 reachability fact — *no production writer can mint a `PRODUCER_*` event
whose dedupe-key producer disagrees with its payload producer* — is what let the
ratified program keep D-1-b as defense-in-depth rather than promoting it. It was
established by enumerating every caller of the public append seam and showing
each one's `event_type` domain is closed.

An enumeration in a document is inert evidence (AUDIT-0003 S-3): true at one SHA,
silently false at the seventh caller. This analyzer makes it machine-consumed and
failure-capable.

**The first version of this gate was defeated five ways in one sitting**, by the
same author who wrote it, using the same split-literal shape that defeated the
derived-truth gate as REV-0045 P1-4:

    getattr(store, "append_" + "execution_event")(ev)     # rule A
    fn = store.append_execution_event; await fn(ev)        # rule A
    ExecutionEvent(event_type=getattr(E, "PRODUCER_" + "RELEASED"))   # rule B
    from app.models import ExecutionEventType as E; E.PRODUCER_RELEASED  # rule B
    from app.models import ExecutionEvent as Ev; Ev(...)               # rule B

Writing a second gate that matched those five shapes would have been the same
mistake a third time. The rule below is therefore **refuse what cannot be
audited**, not *match what I thought of*:

* Names are constant-folded before comparison, so a split or interpolated
  literal is caught exactly like a plain one.
* Import aliases are resolved, so renaming `ExecutionEvent` or
  `ExecutionEventType` at import time changes nothing.
* A `getattr` whose attribute name does not fold to a constant is refused
  outright — it cannot be audited by any static rule.
* Binding the seam to a name (`fn = store.append_execution_event`) counts as a
  call site, because the alias is only useful in order to call it.
* An `ExecutionEvent(...)` whose `event_type` does not fold to a known member is
  refused unless the line carries an explicit disclosure marker.

Rules:

* **A — the append seam is a closed set.** Every production reference to
  `append_execution_event` must be in the ratified enumeration. The gate does not
  judge whether a new caller is safe; it refuses to let one appear without a
  human re-deriving F-1.
* **B — `PRODUCER_*` events have exactly two constructors**, the builders that
  mint the dedupe key from the same `producer_id` they put in the payload.
"""

from __future__ import annotations

import ast
from pathlib import Path

APPEND_SEAM = "append_execution_event"
PRODUCER_EVENT_PREFIX = "PRODUCER_"
EVENT_TYPE_ENUM = "ExecutionEventType"
EVENT_CLASS = "ExecutionEvent"
BUILDER_MODULE = "app/store/core.py"
DYNAMIC_MARKER = "append-caller-gate: dynamic-ok"

# The ratified F-1 enumeration (program §0, discharged 2026-07-28). Each entry's
# event_type domain was shown closed and non-PRODUCER_*. Changing this set is a
# reachability-argument change, not a mechanical edit.
RATIFIED_APPEND_CALLERS = frozenset(
    {
        "app/monitoring.py",
        "app/reconciliation.py",
    }
)


def fold_str(node: ast.AST) -> str | None:
    """Constant-fold a string expression, else ``None``.

    Shared shape with ``tests/_derived_truth_gate.fold_str`` on purpose: the
    evasion class is identical, so the folder must be too.
    """

    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = fold_str(node.left), fold_str(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts = [fold_str(v) for v in node.values]
        return None if any(p is None for p in parts) else "".join(parts)  # type: ignore[arg-type]
    if isinstance(node, ast.FormattedValue):
        # f"a{'b'}" — the interpolated slot holds a constant. Only foldable when
        # no conversion or format spec can change the rendered text.
        if node.conversion in (-1, None) and node.format_spec is None:
            return fold_str(node.value)
        return None
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


def _alias_map(tree: ast.AST) -> dict[str, str]:
    """Local name -> original name, for imports and simple assignments.

    Defeats `from app.models import ExecutionEvent as Ev`.
    """

    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.asname:
                    aliases[a.asname] = a.name.rsplit(".", 1)[-1]
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            if isinstance(target, ast.Name) and isinstance(value, ast.Name):
                aliases[target.id] = aliases.get(value.id, value.id)
    return aliases


def _resolve(name: str | None, aliases: dict[str, str]) -> str | None:
    seen: set[str] = set()
    while name is not None and name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def _attr_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """The attribute a node accesses, folding `getattr` and resolving aliases."""

    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if _resolve(node.func.id, aliases) == "getattr" and len(node.args) >= 2:
            return fold_str(node.args[1])
    return None


def _is_unauditable_getattr(node: ast.AST, aliases: dict[str, str]) -> bool:
    """A ``getattr`` whose attribute name cannot be folded is unauditable."""

    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return False
    if _resolve(node.func.id, aliases) != "getattr" or len(node.args) < 2:
        return False
    return fold_str(node.args[1]) is None


def _disclosed(lines: list[str], lineno: int) -> bool:
    """Is the marker anywhere in the contiguous comment block above ``lineno``?

    Deliberately NOT a fixed-size window. The derived-truth gate used a
    two-line window and a disclosure that wrapped onto a third line silently
    stopped counting — a control whose correctness depends on how the author
    wrapped a comment is not a control. This walks upward while the lines are
    comments or blank, so the block is bounded by the code around it.
    """

    index = lineno - 2  # zero-based line immediately above the node
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped:
            index -= 1
            continue
        if not stripped.startswith("#"):
            break
        if DYNAMIC_MARKER in stripped:
            return True
        index -= 1
    return False


def find_append_callers(source: str, *, label: str) -> list[tuple[str, int]]:
    """Rule A — every reference to the public append seam in one module.

    References, not just calls: binding the seam to a name is only useful in
    order to call it, and a gate that ignored the binding would be defeated by
    two lines instead of one.
    """

    tree = ast.parse(source)
    aliases = _alias_map(tree)
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)
        # Attribute access or getattr with a foldable name.
        name = _attr_name(node, aliases)
        if name == APPEND_SEAM:
            found.append((label, lineno))
            continue
        # A bare call to an imported/aliased function of the same name.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if _resolve(node.func.id, aliases) == APPEND_SEAM:
                found.append((label, lineno))
    return found


def find_unauditable_dynamic_access(source: str, *, label: str) -> list[str]:
    """Any ``getattr`` with a computed attribute name, anywhere in production.

    This closes the evasion CLASS rather than the shapes already demonstrated: a
    name the gate cannot fold is a name it cannot audit, so it is refused unless
    the line carries an explicit disclosure.
    """

    tree = ast.parse(source)
    aliases = _alias_map(tree)
    lines = source.splitlines()
    violations: list[str] = []
    for node in ast.walk(tree):
        if _is_unauditable_getattr(node, aliases):
            lineno = getattr(node, "lineno", 0)
            if not _disclosed(lines, lineno):
                violations.append(
                    f"{label}:{lineno}: getattr with a computed attribute name "
                    f"cannot be audited by the append-seam or PRODUCER_* rules; "
                    f"use a constant or disclose with '# {DYNAMIC_MARKER}: <reason>'"
                )
    return violations


def find_producer_event_constructions(source: str, *, label: str) -> list[str]:
    """Rule B — `ExecutionEvent` built with a `PRODUCER_*` type outside the
    ratified builder module, with aliases resolved and names folded."""

    if label == BUILDER_MODULE:
        return []
    tree = ast.parse(source)
    aliases = _alias_map(tree)
    lines = source.splitlines()
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        constructed = (
            _resolve(func.id, aliases)
            if isinstance(func, ast.Name)
            else (func.attr if isinstance(func, ast.Attribute) else None)
        )
        if constructed != EVENT_CLASS:
            continue
        lineno = getattr(node, "lineno", 0)
        for keyword in node.keywords:
            if keyword.arg != "event_type":
                continue
            member = _attr_name(keyword.value, aliases)
            if member is None:
                # An event_type the gate cannot resolve is one it cannot audit.
                if not _disclosed(lines, lineno):
                    violations.append(
                        f"{label}:{lineno}: ExecutionEvent built with an "
                        f"event_type this gate cannot resolve; use a constant "
                        f"member or disclose with '# {DYNAMIC_MARKER}: <reason>'"
                    )
                continue
            if member.startswith(PRODUCER_EVENT_PREFIX):
                violations.append(
                    f"{label}:{lineno}: constructs {EVENT_TYPE_ENUM}.{member} "
                    f"outside {BUILDER_MODULE} — a PRODUCER_* event must be "
                    "minted by the ratified builders, which derive the dedupe "
                    "key from the same producer_id they place in the payload"
                )
    return violations


def production_modules(repo_root: Path) -> dict[str, Path]:
    """Discovered, not enumerated: every production module under ``app/``."""

    return {
        path.relative_to(repo_root).as_posix(): path
        for path in sorted((repo_root / "app").rglob("*.py"))
    }
