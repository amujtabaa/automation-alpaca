"""The Signal-Seat rails SEAM (ADR-009 A-4) — the ONLY rails surface WO-0102 ships.

WO-0102 defines the Protocol the body-blind ingest dependency consults *before*
the request body is read (authenticate → **rails check** → bounded read → parse).
The rails *implementation* — the refilling rate bucket, the non-refilling
invalid/conflict budget, the producer-quarantine epoch, and the human release —
is **WO-0104's** (`03-rails.md §1/§1a/§4/§5`). Nothing here debits, quarantines,
or releases; it only declares the seam and the presence contract.

**Rails-presence startup guard (A-4).** With ``signal_seat_enabled`` on,
``create_app`` fails fast unless a conforming rails provider is wired. A
Protocol-presence check cannot tell a real provider from a permissive fake, so
the *production* entrypoint is separately proven to construct WO-0104's real
provider, and any permissive fake is confined to a **test-only** construction
path production config/environment cannot select (`03-rails.md §2`). This module
provides only the presence check; the real/fake distinction is enforced by
wiring, not by this Protocol.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RailsDecision:
    """The rails verdict for one ingest attempt (evaluated body-blind).

    ``allowed`` True → proceed to the bounded body read + parse. False → reject at
    the boundary with ``http_status`` (429 over rate/budget, 403 quarantined
    producer) and ``reason`` — zero body processing, zero store writes beyond the
    at-most-one epoch-opening append the rails impl owns (WO-0104).
    """

    allowed: bool
    http_status: int = 0
    reason: str = ""


@runtime_checkable
class SignalRails(Protocol):
    """The rails seam the body-blind ingest dependency consults (WO-0102 seam only).

    A conforming provider decides admission from ``producer_id`` alone — never the
    body (FastAPI would read a body-model before dependencies can reject, defeating
    the A-4 ordering; the handler takes the raw ``Request``). WO-0104 implements the
    real bucket/budget/quarantine/release behind this seam.
    """

    async def check_ingest(self, producer_id: str) -> RailsDecision:
        """Body-blind admission decision for one ingest from ``producer_id``."""
        ...


def is_conforming_rails(candidate: object) -> bool:
    """True iff ``candidate`` structurally satisfies :class:`SignalRails` — the
    rails-presence startup guard's check (A-4). Presence only; the real-vs-fake
    distinction is enforced by the production entrypoint's wiring, never here.

    A ``runtime_checkable`` Protocol only checks ATTRIBUTE PRESENCE, so a provider
    whose ``check_ingest`` is a *synchronous* ``def`` would pass — then the
    body-blind dependency's ``await rails.check_ingest(...)`` raises ``TypeError``
    (500) on the first producer request instead of failing fast at startup. Since
    this is the PERMANENT A-4 rails-presence gate, also require ``check_ingest``
    to be a coroutine function so a non-async provider is rejected at construction
    (auto-review round 6)."""

    if not isinstance(candidate, SignalRails):
        return False
    # Reject a CLASS object (round-13): `SomeRails` (the class, not an instance)
    # satisfies the Protocol and its `check_ingest` is a coroutine function, but
    # `await rails.check_ingest(pid)` would raise TypeError (missing self) on the
    # first request. Require a real instance whose `check_ingest` is a BOUND async
    # method, so a miswired provider fails at construction, not with a 500 later.
    if isinstance(candidate, type):
        return False
    check = getattr(candidate, "check_ingest", None)
    return inspect.iscoroutinefunction(check) and inspect.ismethod(check)
