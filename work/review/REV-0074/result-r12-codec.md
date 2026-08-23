# REV-0074 R12 independent codec/lifecycle findings

Exact candidate reviewed: `78f96af9f2597fe981f3b760f72923c5e331e379`, tree
`c3fe51651d906707934f78c66107c9dca10a9969`.

## P1 — Persisted length fields are not bound to their documents

Locations: frozen contract R12 checkpoint, receipt, outcome, and outbox record definitions.

Mechanism: R12 retained `payload_length`, `receipt_length`, and `outcome_length`, but did not
require equality to the corresponding canonical document bytes. A length-only substitution could
therefore survive the stated digest and canonical-reencode checks.

Impact: persisted metadata for document kinds `0x02` through `0x05` would not be fully canonical.

Smallest complete correction: require each stored length to equal the exact document byte length at
construction, store, load, and checkpoint decode, with one length-only rejection control per kind.

## P1 — The kind-`0x05` digest does not bind `outbox_sequence`

Locations: frozen contract R12 outbox record and document grammar.

Mechanism: `outbox_sequence` is immutable ordered record identity but was absent from the canonical
outbox document. Re-encoding could not detect a sequence-only substitution.

Impact: a valid dispatch payload could be paired with altered ordering metadata.

Smallest complete correction: include `outbox_sequence` at one fixed kind-`0x05` position and
require record/store/load equality with a sequence-only rejection control.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 0

Unverified: No runtime, tests, SQLite/DDL, network, broker, or order features were executed.
