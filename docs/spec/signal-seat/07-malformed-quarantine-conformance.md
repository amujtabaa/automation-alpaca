# 07 — Malformed-input and quarantine conformance

**Status:** retained future-reactivation conformance; not an implementation instruction for reset
beta.

## Purpose and provenance

This specification distills the durable contract from the two branch-only tests formerly held at
`codex/signal-tests-staging` tip `24d3746a35e30f736a6c5e3541720f0d47b0d751`. The branch is being
retired only after this extraction; no executable test harness is ported into M1.

| Source file at that tip | Bytes | SHA-256 |
| --- | ---: | --- |
| `tests/test_signal_malformed_input_matrix.py` | 8064 | `af614174b0b9350574f3ef220818be8f8334cee72663d44fffd34f73a6a37bea` |
| `tests/test_signal_quarantine_totality.py` | 9774 | `3ac9634600f63f06e97a862d06a6ccc9221e4d55d2736cd1e85ec091d465d747` |

The source material was written for the prior Signal Seat architecture. This document preserves
its security and data-integrity requirements without retaining a dependency on that branch, its
test client, its database fixture, or its historical route implementation.

## Reset-beta boundary

ADR-022 controls the current posture: Signal Seat is disabled, unmounted, absent from the reset
schema, and not loaded at startup. Nothing here grants a route, storage, credential, producer,
database, or execution capability. A future reactivation requires a new ADR and separately
activated work order that re-derives these requirements against the then-current architecture.

## Required classification matrix for any future authenticated intake

| Input boundary | Required result | Durable record |
| --- | --- | --- |
| Unauthenticated request | Refuse at the authentication boundary; no proposal record. | None. |
| Authenticated but wire-unparseable payload (including empty/non-JSON bytes) | Refuse at the parse boundary; no proposal record. | None. |
| Authenticated, parseable structured payload that fails proposal validation | Terminal quarantine; preserve recoverable offending fields. | Exactly one representable quarantine record, or an idempotent replay of the same record. |
| Authenticated, parseable valid proposal | Admit only through the separately approved future lifecycle. | Future lifecycle record, not a quarantine surrogate. |

The distinction is deliberate: authenticated malformed content is an auditable rejected fact;
unattributable or unparseable bytes are not safely attributable to a producer and remain boundary
refusals. Record construction itself must be total: malformed input must not turn into an internal
error or an unrecorded loss of an attributable fact.

## Quarantine totality and representability

For every quarantined record:

- The terminal status and nonempty reason are explicit; no later ordinary intake path silently
  turns the record into a proposal.
- Every typed field is valid for its domain or carries a documented sentinel/`None`; invalid raw
  data never occupies a typed field merely to retain it.
- `raw_fields` is nonempty when it is the recovery location for offending content and preserves
  the attributable raw structure as safely representable data.
- The complete record and all stored strings are UTF-8 serializable on both the write response and
  the operator read/list path. A malformed surrogate or normalization edge must not create a later
  read-path failure.
- The record can be reconstructed, serialized, and listed without raising. A quarantine that is
  writeable but unreadable is not conformant.

## Cross-store parity and adversarial input classes

Any future durable and in-memory implementations must produce the same classification, identity,
terminal status, representability, and operator-visible result for the same attributable input.
The conformance set must include, at minimum:

- every parseable top-level JSON shape (object, array, scalar, boolean, and null), unrelated
  objects, and missing required fields;
- signal identity whitespace, reserved synthetic-prefix attempts, invalid characters, oversized
  identifiers, and non-string values;
- symbol, side, timestamp, TTL, advisory quantity/price, thesis, and provenance type/domain
  violations;
- Unicode, malformed UTF-8/surrogate handling, non-ASCII normalization-sensitive symbols, and
  raw-field serialization;
- huge integers, signed-64-bit overflow, non-finite/oversized numeric values, and values that a
  durable store cannot represent natively;
- unhashable or structurally unexpected values that could otherwise escape as an internal error.

## Identity, collision, retry, and idempotence

- Distinct malformed payloads without a valid producer-visible identity must receive distinct
  synthetic identities; whitespace-only or forged reserved identities cannot collapse facts.
- A producer cannot squat or choose the synthetic malformed namespace.
- An exact resend of the same attributable malformed payload is an idempotent replay of its
  terminal quarantine record, not a second record.
- Distinct bodies never become an accidental replay merely because their valid identity field is
  absent, invalid, blank, or normalized to the same value.

## Future evidence gate

A future ADR/work order must turn this document into executable, failure-capable conformance tests
for the selected future architecture. That work must prove both stores and every authenticated
ingress path meet this matrix, while preserving the reset safety core: no direct broker authority,
no position truth, no fill synthesis, and no bypass of operator/human gates.
