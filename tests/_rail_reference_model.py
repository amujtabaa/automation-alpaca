"""An independent reference model for producer-rail sequence truth (WO-0141 §5.1).

**Read this header before treating this file as independent evidence.**

WO-0141 §5.1 calls for reviewer-owned holdouts. This file is *not* that: it was
written by the same seat that implemented the kernel, so it cannot rule out a
common-mode error where the implementation and its check share one wrong idea.
What it *is* is **pre-registered** — written from the ratified decision block
rather than from the delivered code, and committed before the structural
consolidation it will be used to verify. Pre-registration constrains one failure
mode (shaping the oracle to fit the implementation); it does not substitute for
independence, and it must not be described as though it does.

The reviewer is asked to either adopt this model as a holdout after reading it,
or replace it with one of their own. Until then, agreement between this model
and the kernel is weak evidence, not a gate.

What it models, deliberately narrowly: the *sequence* semantics where all four
open P0s live. It re-derives, from the ratified rules alone:

* which producer a rail event belongs to (D-1-a),
* which sequences a history PROVES (D-2-b),
* which release-key sequences a history has CONSUMED (occupancy),
* where the next release may therefore land.

It imports nothing from ``app.events.projectors`` or from any store, and it does
not reuse the length-prefixed decoder — it re-implements decoding from the
encoder's documented shape, so a bug in the shared decoder cannot hide here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Deliberately imported: the event model and the enum are DATA, not the logic
# under test. Re-declaring them would test nothing and drift.
from app.models import ExecutionEvent, ExecutionEventType

_RELEASE_PREFIX = "producer_release:"
_READABLE_MAX = 2**63 - 1


def decode_release_key(dedupe_key: str | None) -> tuple[str, int] | None:
    """Independently invert ``signal_dedupe_key("producer_release", pid, seq)``.

    The encoder's documented shape is ``prefix + "|".join(f"{len(p)}:{p}")``.
    This walks that shape directly rather than calling the production decoder,
    so the two are independent implementations of one specification.
    """

    if not isinstance(dedupe_key, str) or not dedupe_key.startswith(_RELEASE_PREFIX):
        return None
    body = dedupe_key[len(_RELEASE_PREFIX) :]
    parts: list[str] = []
    while True:
        digits = ""
        while body and body[0].isdigit() and body[0].isascii():
            digits, body = digits + body[0], body[1:]
        if not digits or (len(digits) > 1 and digits[0] == "0"):
            return None
        if not body.startswith(":"):
            return None
        body = body[1:]
        width = int(digits)
        if len(body) < width:
            return None
        parts.append(body[:width])
        body = body[width:]
        if not body:
            break
        if not body.startswith("|"):
            return None
        body = body[1:]
    if len(parts) != 2:
        return None
    producer, sequence_text = parts
    if not sequence_text or not all(c.isdigit() and c.isascii() for c in sequence_text):
        return None
    if len(sequence_text) > 1 and sequence_text[0] == "0":
        return None
    sequence = int(sequence_text)
    if sequence < 1 or sequence > _READABLE_MAX:
        return None
    return producer, sequence


@dataclass
class RailFacts:
    """What one history says about one producer's sequence domain."""

    proven: int = 0
    occupied: set[int] = field(default_factory=set)

    def next_mintable(self, *, mint_max: int) -> int | None:
        candidate = self.proven + 1
        while candidate in self.occupied:
            candidate += 1
        return None if candidate > mint_max else candidate


def owner_of(event: ExecutionEvent) -> str | None:
    """D-1-a: whose event is this? ``None`` when the event answers ambiguously.

    A release must agree with itself — the producer named inside its dedupe key
    and the producer named in its payload are the same claim made twice, and a
    disagreement means the event is not attributable to anybody.
    """

    payload_producer = event.payload.get("producer_id")
    if not isinstance(payload_producer, str):
        return None
    if event.event_type is not ExecutionEventType.PRODUCER_RELEASED:
        return payload_producer
    decoded = decode_release_key(event.dedupe_key)
    if decoded is None:
        return None
    key_producer, _ = decoded
    return payload_producer if key_producer == payload_producer else None


def proven_sequence(event: ExecutionEvent) -> int | None:
    """What a STRUCTURALLY WELL-FORMED event proves about its own sequence.

    This is the narrow structural reading, matching the ratified rule: an opener
    proves its bounded payload carrier; a release proves only its producer-bound
    key, because the ratified release payload is closed and carries no sequence.

    Callers decide whether the event was ACCEPTED — proof requires both (D-2-b).
    """

    if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
        raw = event.payload.get("epoch_sequence")
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None
        return raw if 1 <= raw <= _READABLE_MAX else None
    if event.event_type is ExecutionEventType.PRODUCER_RELEASED:
        decoded = decode_release_key(event.dedupe_key)
        return None if decoded is None else decoded[1]
    return None


def occupied_sequence(event: ExecutionEvent, *, producer_id: str) -> int | None:
    """Which release-key sequence this event CONSUMED for ``producer_id``.

    Unconditional on validity: the UNIQUE index does not read payloads. Openers
    never appear because they mint into a different key prefix.
    """

    if event.event_type is not ExecutionEventType.PRODUCER_RELEASED:
        return None
    decoded = decode_release_key(event.dedupe_key)
    if decoded is None:
        return None
    key_producer, sequence = decoded
    return sequence if key_producer == producer_id else None


def observed_facts(
    events: list[ExecutionEvent], *, producer_id: str, accepted: set[int]
) -> RailFacts:
    """Fold raw events into this producer's sequence facts.

    ``accepted`` holds the log sequences (``event.sequence``) the fold under test
    ACCEPTED. Passing that in — rather than re-deriving acceptance — keeps this
    model narrow: it is an oracle for the SEQUENCE rules, not a second copy of
    the whole rail state machine, which would be neither independent nor
    obviously correct.
    """

    facts = RailFacts()
    for event in events:
        consumed = occupied_sequence(event, producer_id=producer_id)
        if owner_of(event) == producer_id and event.sequence in accepted:
            proven = proven_sequence(event)
            if proven is not None:
                facts.proven = max(facts.proven, proven)
        if consumed is not None:
            facts.occupied.add(consumed)
    return facts
