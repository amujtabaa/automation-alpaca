# 01 — Schema: `SignalProposal`, `SignalRecord`, the approval payload

## 1. Wire schema — `SignalProposal` (request body of `POST /api/signals`)

Pydantic model in `app/api/schemas.py`. **`producer_id` is deliberately absent from the wire
schema** — the server derives it from the authenticated API key (ADR-009 identity binding). If a
client includes a `producer_id` field anyway, the request is rejected 422 when it mismatches the
credential-derived id, and silently ignored when it matches (tolerant to naive clients, never
spoofable).

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `signal_id` | `str` | 1–64 chars, `[A-Za-z0-9_-]+` | Producer-generated, deterministic (ULID or equivalent). Half of the idempotency key. |
| `issued_at` | `datetime` (ISO-8601, tz-aware) | plausibility-checked (`02-lifecycle.md §3`) | Naive datetimes are a 422 validation failure → quarantine path. |
| `ttl_seconds` | `int` | clamped semantics: valid range `[30, 86400]`; outside → quarantine | Signal expires at `issued_at + ttl_seconds`. |
| `symbol` | `str` | 1–10 chars, uppercased, `[A-Z.]+` | Instrument. |
| `direction` | `Literal["buy", "sell"]` | | Maps to the direction-aware conversion path (`05-conversion.md`). |
| `suggested_quantity` | `Optional[int]` | `> 0` if present | **Advisory, display-only.** Never flows into any order field (`05-conversion.md §2`). |
| `suggested_limit_price` | `Optional[float]` | finite, `> 0` if present | **Advisory, display-only.** Same rule. |
| `thesis` | `str` | 1–4000 chars | Human-readable rationale shown on the approval panel. |
| `provenance` | `dict[str, str]` | ≤ 20 keys, values ≤ 500 chars | Model/prompt/version identifiers, source citations. Opaque to the spine; stored and displayed verbatim. |

Validation failures split two ways (ADR-009: "validation failure → quarantine, not
rejection-and-forget"):

- **Malformed-but-attributable** (authenticated producer, parseable JSON, field constraint
  violated): recorded as `SIGNAL_QUARANTINED` with `quarantine_reason="validation"` and the
  offending fields in the payload. HTTP 422.
- **Unattributable garbage** (unauthenticated, or unparseable body): boundary-rejected
  (401 / 400) with **no** event append — an unauthenticated flood must not grow the log
  (`03-rails.md §4`).

## 2. Stored entity — `SignalRecord` (`app/models.py`, both stores)

```
class SignalStatus(str, Enum):
    RECEIVED = "received"          # pending operator action
    QUARANTINED = "quarantined"    # terminal (validation / duplicate-conflict / producer-quarantine sweep)
    EXPIRED = "expired"            # terminal (TTL lapse or implausible issued_at)
    REJECTED = "rejected"          # terminal (operator)
    APPROVED = "approved"          # terminal (operator; conversion succeeded atomically)

class SignalRecord(_Entity):
    id: str                        # server id (new_id()), NOT the dedupe key
    producer_id: str               # credential-derived, never body-derived
    signal_id: str                 # producer-supplied
    status: SignalStatus
    symbol: str
    direction: str                 # "buy" | "sell"
    issued_at: datetime
    ttl_seconds: int
    expires_at: datetime           # issued_at + ttl_seconds, precomputed, tz-aware UTC
    suggested_quantity: Optional[int]
    suggested_limit_price: ResponseSafeFloat
    thesis: str
    provenance: dict[str, str]
    payload_hash: str              # sha256 of the canonical proposal JSON — conflict detection
    quarantine_reason: Optional[str]
    created_at / updated_at / approved_at / rejected_at / expired_at / quarantined_at
    # Correlation (set on approval; 05-conversion.md §4):
    converted_kind: Optional[str]  # "candidate" | "sell_intent"
    converted_id: Optional[str]
    approved_by: Optional[str]     # operator actor
```

Unique index / dict key: **`(producer_id, signal_id)`** — never bare `signal_id` (ADR-009;
cross-producer duplicate ids are distinct signals).

## 3. Dedupe and idempotency

On `POST /api/signals` with an existing `(producer_id, signal_id)`:

- **Identical `payload_hash`** → idempotent replay: HTTP 200 with the existing record; **no new
  event appended** (mirrors `client_order_id` idempotency). Works in every signal status.
- **Different `payload_hash`** → duplicate-conflict: the **existing** record's status is untouched;
  the conflict is recorded **event-only** — one `SIGNAL_QUARANTINED` event (reason
  `"duplicate_conflict"`) whose payload embeds the conflicting proposal + both hashes, linked to
  the original record's id. **No second `SignalRecord` row is created** — `(producer_id,
  signal_id)` stays a true unique key in both stores (Codex PR #6: a same-key second row would
  contradict the unique index). HTTP 409. Further conflicting replays of the same `(producer_id,
  signal_id, payload_hash)` are boundary-rejected 409 with coalesced audit only (`03-rails.md §4`)
  — one conflict, one event.

## 4. The approval payload (request body of the approve route)

The operator's approval **carries the sizing** (ADR-009: producer sizing is advisory; the as-built
candidate path binds `suggested_quantity`/`suggested_limit_price`, so the operator's values are
what enter those fields):

| Field | Type | Constraints |
|---|---|---|
| `quantity` | `int` | `> 0`; for sells additionally `≤ live position` at conversion time (checked under the store lock) |
| `limit_price` | `float` | finite, `> 0` (`limit_price_reason` — the F1/BACKEND-1 rule) |
| `actor` | threaded from the authenticated operator credential + `X-Actor` audit label | |

The panel MAY pre-fill the form from the producer's suggested values; the **submitted** values are
the operator's own act. Test contract (WO-0103): a proposal whose suggestions differ from the
operator's entries produces an order carrying the operator's entries.

Rejection needs no payload beyond an optional `reason: str ≤ 500`.
