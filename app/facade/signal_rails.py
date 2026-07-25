"""Signal Seat rails Protocol seam (ADR-009 A-4).

R5a declares only the body-blind ingest admission contract and its construction
presence check. R6 / WO-0104 owns the real refilling bucket, non-refilling
budget, quarantine epoch, and human-release provider. No production fake or
fallback is selectable here.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RailsDecision:
    """Body-blind admission verdict for one ingest attempt."""

    allowed: bool
    http_status: int = 0
    reason: str = ""


@runtime_checkable
class SignalRails(Protocol):
    """Admission seam consulted from authenticated producer identity alone."""

    async def check_ingest(self, producer_id: str) -> RailsDecision:
        """Return the admission decision without reading the request body."""
        ...


def is_conforming_rails(candidate: object) -> bool:
    """Return whether a candidate satisfies the callable rails presence seam.

    A runtime-checkable Protocol only proves attribute presence. Construction
    additionally requires a real instance with a bound async method whose
    signature accepts the producer identity, so sync/class/wrong-arity wiring
    fails before serving rather than on the first request.
    """

    if not isinstance(candidate, SignalRails):
        return False
    if isinstance(candidate, type):
        return False
    check = getattr(candidate, "check_ingest", None)
    if not (inspect.iscoroutinefunction(check) and inspect.ismethod(check)):
        return False
    try:
        inspect.signature(check).bind("probe-producer-id")
    except TypeError:
        return False
    return True
