# REV-0074 R12 independent capability/scope findings

Exact candidate reviewed: `78f96af9f2597fe981f3b760f72923c5e331e379`, tree
`c3fe51651d906707934f78c66107c9dca10a9969`.

## P1 — The exclusive setup-import rule excludes the receipt/lifecycle test path

Location: frozen contract R12 setup-capability importer allowlist.

Mechanism: only four tests could import the sole setup issuer, while the scoped
`test_persistence_input_receipt.py` needs database-backed lifecycle/restart coverage.

Impact: AC-3 would require an undeclared indirect route, a frozen-boundary violation, or omitted
coverage.

Smallest complete correction: add `test_persistence_input_receipt.py` to the explicit importer
allowlist while retaining fresh-`tmp_path` and no-`app/**` restrictions.

## P1 — Setup-only classification has no production bootstrap path for planned startup

Location: frozen contract R12 capability matrix.

Mechanism: the initial profile/application/scope/checkpoint/controller/protection writes were
setup-only while production setup issuance was test-only and normal runtime issuance required the
very rows that bootstrap must create.

Impact: WO-0169 could not lawfully establish its first durable baseline without a bypass.

Smallest complete correction: freeze one bounded UoW-owned genesis/bootstrap transaction with exact
zero-state precondition, seed rows, write order, and validation rules; keep setup capability
test-only.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 0

Unverified: No SQLite, DDL, runtime composition, tests, Ruff, or mypy were run.
