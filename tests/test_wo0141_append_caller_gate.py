"""WO-0141 §5.4 — the F-1 caller enumeration, as a gate rather than a table.

The reachability argument that kept D-1-b as defense-in-depth (rather than
promoting it ahead of this work order) rests on a closed set of append-seam
callers and a closed set of `PRODUCER_*` constructors. Both were verified by
hand and written into `R6A-CONSOLIDATION-PROGRAM.md` §0.

A hand-verified table is exactly the inert evidence AUDIT-0003 S-3 names: true
at one SHA, silently false at the next. These tests make the argument
machine-consumed, and the adversarial fixtures make it failure-capable — the
P1-4 lesson, where a gate that had never been attacked turned out to attest
spelling rather than substance.

Note what this gate does and does not claim. It does **not** prove a new caller
would be unsafe. It refuses to let one appear silently, forcing F-1 to be
re-derived by a human. That is the durable property; "no seventh caller exists"
is not something a test can keep true on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._append_caller_gate import (
    RATIFIED_APPEND_CALLERS,
    find_append_callers,
    find_producer_event_constructions,
    find_unauditable_dynamic_access,
    production_modules,
)

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# The gate, over the real tree
# --------------------------------------------------------------------------- #


def test_append_seam_callers_match_the_ratified_enumeration() -> None:
    """Rule A: the set of production modules calling the public append seam is
    exactly the enumerated one.

    If this fails, do NOT edit the constant to match. Re-derive F-1 for the new
    caller — establish that its ``event_type`` domain is closed and contains no
    ``PRODUCER_*`` member — and only then record it, in the same change that
    updates the program's §0 table.
    """

    callers: dict[str, list[int]] = {}
    for label, path in production_modules(REPO).items():
        for module, lineno in find_append_callers(path.read_text(), label=label):
            callers.setdefault(module, []).append(lineno)

    assert set(callers) == set(RATIFIED_APPEND_CALLERS), (
        f"append-seam caller set changed: {sorted(callers)} != "
        f"{sorted(RATIFIED_APPEND_CALLERS)} — re-derive F-1 before recording it"
    )


def test_the_enumeration_is_not_vacuous() -> None:
    """A gate over an empty set proves nothing. The six ratified call sites must
    actually be found."""

    total = sum(
        len(find_append_callers(path.read_text(), label=label))
        for label, path in production_modules(REPO).items()
    )
    assert total == 6, f"expected the 6 enumerated call sites, found {total}"


def test_producer_events_are_constructed_only_by_the_ratified_builders() -> None:
    """Rule B: the two `core.py` builders are the only constructors, which is
    what makes a key/payload producer mismatch unmintable."""

    problems: list[str] = []
    for label, path in production_modules(REPO).items():
        problems += find_producer_event_constructions(path.read_text(), label=label)
    assert problems == [], problems


# --------------------------------------------------------------------------- #
# Adversarial fixtures — the analyzer must CATCH each of these
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source",
    [
        # plain shapes
        "async def f(store, ev):\n    return await store.append_execution_event(ev)\n",
        "async def f(ev):\n    return await append_execution_event(ev)\n",
        "async def f(self, ev):\n    return await self._store.append_execution_event(ev)\n",
        # the five evasions that defeated the FIRST version of this gate, plus
        # the f-string shape found while re-attacking the second version
        'async def f(s, e):\n    return await getattr(s, "append_" + "execution_event")(e)\n',
        'async def f(s, e):\n    return await getattr(s, "_".join(["append", "execution", "event"]))(e)\n',
        'async def f(s, e):\n    return await getattr(s, f"append_{"execution_event"}")(e)\n',
        "async def f(s, e):\n    fn = s.append_execution_event\n    return await fn(e)\n",
    ],
)
def test_gate_finds_a_seventh_caller_in_every_call_shape(source: str) -> None:
    """The planted caller, in every shape the author could construct against it.

    The first version of this gate matched only the three plain shapes and was
    defeated four ways in one sitting — by the same split-literal trick that
    defeated the derived-truth gate as REV-0045 P1-4. Matching the four new
    shapes would have repeated the mistake, so the analyzer folds names and
    refuses what it cannot fold; these fixtures are the evidence, not the rule.
    """

    assert find_append_callers(source, label="app/newmodule.py")


def test_an_unfoldable_dynamic_name_is_refused_rather_than_missed() -> None:
    """The evasion CLASS, not the evasions: a name the gate cannot fold is a
    name it cannot audit, so it is refused outright."""

    source = 'async def f(s, e, n):\n    return await getattr(s, "append_" + n)(e)\n'
    assert find_unauditable_dynamic_access(source, label="app/newmodule.py")


def test_a_disclosed_dynamic_access_is_allowed() -> None:
    """Non-vacuity: a gate that cannot be satisfied gets disabled (the P1-5
    failure mode), so a legitimate dynamic access may disclose and pass."""

    source = (
        "def f(s, n):\n"
        "    # append-caller-gate: dynamic-ok: reflective config probe\n"
        "    return getattr(s, n)\n"
    )
    assert find_unauditable_dynamic_access(source, label="app/newmodule.py") == []


@pytest.mark.parametrize(
    "source",
    [
        'def f():\n    return ExecutionEvent(event_type=getattr(ExecutionEventType, "PRODUCER_" + "RELEASED"))\n',
        "from app.models import ExecutionEventType as E\ndef f():\n    return ExecutionEvent(event_type=E.PRODUCER_QUARANTINED)\n",
        "from app.models import ExecutionEvent as Ev\ndef f():\n    return Ev(event_type=ExecutionEventType.PRODUCER_RELEASED)\n",
        "def f(t):\n    return ExecutionEvent(event_type=t)\n",
    ],
)
def test_rule_b_survives_aliasing_and_computed_members(source: str) -> None:
    """Renaming the class or the enum at import time, computing the member name,
    or passing the type through a variable must all fail closed."""

    assert find_producer_event_constructions(source, label="app/newmodule.py")


def test_gate_ignores_the_private_per_store_sinks() -> None:
    """Non-vacuity in the other direction: the private sinks take events the
    ratified builders already minted, so matching them would make the gate fire
    forever and get disabled — the P1-5 failure mode, where a guard that cannot
    pass is a guard nobody keeps."""

    source = "def f(self, cur, ev):\n    return self._insert_execution_event(cur, ev)\n"
    assert find_append_callers(source, label="app/store/sqlite.py") == []


@pytest.mark.parametrize(
    "member",
    ["PRODUCER_RELEASED", "PRODUCER_QUARANTINED"],
)
def test_gate_catches_a_producer_event_built_outside_the_builders(
    member: str,
) -> None:
    """Both ratified `PRODUCER_*` members, not just the one the author had in
    mind — the P0-2 lesson about driving one path of a vocabulary."""

    source = (
        "def f():\n"
        "    return ExecutionEvent(\n"
        f"        event_type=ExecutionEventType.{member},\n"
        '        dedupe_key="producer_release:1:a|1:1",\n'
        '        payload={"producer_id": "b"},\n'
        "    )\n"
    )
    problems = find_producer_event_constructions(source, label="app/monitoring.py")
    assert problems, f"a hand-built {member} event was not detected"


def test_builder_module_is_exempt_by_exact_path_not_by_suffix() -> None:
    """The P1-4 lesson applied here: an exemption matched by filename suffix
    would let `app/anything/core.py` mint producer events unchecked."""

    source = (
        "def f():\n"
        "    return ExecutionEvent(event_type=ExecutionEventType.PRODUCER_RELEASED)\n"
    )
    assert find_producer_event_constructions(source, label="app/store/core.py") == []
    assert find_producer_event_constructions(source, label="app/signals/core.py")


def test_gate_does_not_fire_on_a_non_producer_event() -> None:
    """Non-vacuity: ordinary event construction must stay legal everywhere."""

    source = (
        "def f():\n"
        "    return ExecutionEvent(event_type=ExecutionEventType.ENVELOPE_ACTION)\n"
    )
    assert find_producer_event_constructions(source, label="app/monitoring.py") == []
