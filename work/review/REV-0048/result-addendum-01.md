---
type: Review Result Addendum
rev_id: REV-0048
addendum: 01
reviewer_model: Codex (GPT-5)
reviewed_target: 9ce0f442db4b9a261fbed4003da377bfb497ec9e
base: dfb8ed30ebed788f1158d7f8be49b44d505c355b
verdict: BLOCK
date: 2026-08-01
relationship: Independent remediation re-review of reviewer result.md; the original request.md and result.md are preserved unchanged.
---

## Verdict

**BLOCK.** The preserved result's P0-1 and P1-1 are closed, and the two intervening exact-subclass
findings are closed at their stated outer-object boundaries. However, the exact broker-fact gate at
the reviewed checkpoint remains bypassable through nested value subclasses. Fresh, database-free
counterexamples made an exact `BrokerFillFact` apply economics and direction different from those
observed by its constructor. This violates the canonical-fact and long-only safety boundary and is a
new P0.

## Resolution of prior findings

| Prior finding | Status | Exact evidence | Re-review result |
|---|---|---|---|
| P0-1 -- live transitions scanned retained terminal history | CLOSED | `app/execution_core/venue.py` now retains bounded current indexes and moves retained-history reconstruction to the explicit audit path. The failure-capable tripwire `tests/execution_core/test_venue_checkpoint_hardening.py:537-603` passed for both `closure_history` and `input_records`. | Ordinary transitions did not touch either trapped audit-history view in the fresh focused run. |
| P1-1 -- importable book-construction capability | CLOSED | `tests/execution_core/test_venue_provenance_hardening.py:282-305` proves `_BOOK_CONSTRUCTION_TOKEN`, `_rebuild_book`, and `_evolve_book` are absent and direct/subclass construction is rejected. | The focused construction-capability pin passed. |
| Intervening P1 -- `VenueScope` subclass admitted by `empty`/audit hydration | CLOSED | `app/execution_core/venue.py:1692-1693,3232-3234` requires the exact `VenueScope` type. `tests/execution_core/test_venue_provenance_hardening.py:308-330` uses a delayed account-reporting subclass against both entry points. | The delayed-scope regression passed. |
| Intervening P1 -- broker fact subclasses admitted at reducer/recovery seams | CLOSED AS STATED | `app/execution_core/fills.py`, `position.py`, and `recovery.py` now use exact outer types for fill/correct/bust facts. The fill/correct/bust reducer/`SeenFact` pins and correct/bust recovery-record pins passed 5 cases. Static trace found the same outer-type rejection at the remaining fill recovery seams. | Direct subclasses of `BrokerFillFact`, `BrokerTradeCorrectFact`, and `BrokerTradeBustFact` are rejected. The new P0 below shows why outer-type exactness alone is insufficient. |

## New finding

| ID | Severity | Finding | Evidence and resolution |
|---|---|---|---|
| P0-2 | P0 | **An exact broker fact can carry delayed nested subclasses that change validated economics or direction before application.** The outer `type(fact)` gate therefore does not establish an immutable canonical fact. | `app/execution_core/fills.py:171-173` implements component validation with `isinstance`; `fills.py:257-288,598-614` consequently accepts subclassed `ExecutionScope` and `Quantity` inside an exact `BrokerFillFact`. `app/execution_core/position.py:1142-1173,1554-1572` exact-checks only the outer fact and then trusts `fact.scope.side` and `fact.quantity.value`. Fresh probe A constructed an exact fill with `DelayedQuantity(1)`, changed the subclass after validation, and obtained `APPLIED`, `quantity_delta=100`, `raw_quantity=100`. Fresh probe B constructed an exact fill whose delayed scope validated as `BUY`, changed it to report `SELL`, and obtained `APPLIED`, `quantity_delta=-1`, `raw_quantity=-1`. Resolve by rejecting subclasses (or making subclassing impossible) for every nested canonical identity, scope, economics, and price component at fact construction/admission, then add delayed-value failure pins for fill, correction, bust, recovery records, and canonical encoding. |

## Independent evidence

- Reviewed exact target `9ce0f442db4b9a261fbed4003da377bfb497ec9e` against base
  `dfb8ed30ebed788f1158d7f8be49b44d505c355b`. The cumulative range contains 23 files,
  22,472 insertions, and 72 deletions; `git diff --check` is clean.
- Fresh pure focused tests: **9 passed** -- the two audit-history tripwires, the opaque-construction
  pin, delayed `VenueScope` rejection at both seams, three broker reducer/`SeenFact` subclass cases,
  and two revision recovery-record subclass cases.
- The work-order evidence records five semantic mutants: unresolved-registry release, ordered-effect
  review-gate removal, coordinated semantic-alias provenance replacement, effect-sibling overfill
  unlatching, and operator-final acceptance with unresolved execution-integrity bits. I inspected
  their recorded failure/restoration evidence but did not rerun source mutations under this
  read-only reviewer scope. None addresses P0-2.
- Authoritative coverage artifacts reproduce by file identity:
  `.coverage_wo0146_full_authorized_13` is 1,757,184 bytes with SHA-256
  `fdf57e561de4d37b6ccb339778791f2402ee333c4e3f17d22e170afbf5bce3f6`; its JSON export is
  1,724,663 bytes with SHA-256
  `ad7045af350a3e698a7785c4563027e5674b5e504e39b196b7342f4ea56e3c26`. The export reports
  17,366/18,322 lines and 6,012/6,812 branches covered (93.01344791915334% combined).
- The restored production hashes match the WO: `recovery.py`
  `684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c` and `venue.py`
  `0772dc92f3c6714a6d353a83ac931a016ca22f15cdbaec5e9dfd58814a942141`.

## Adversarial lens reconciliation

- **Production saboteur:** outer fact identity can remain exact while a nested subclass changes its
  reported economics after validation; the canonical reducer then applies the substituted value.
- **Context-free new maintainer:** the new exact-outer checks and tests plausibly look complete, but
  `_require_type` silently preserves subclass authority for every nested component.
- **Security/data-integrity auditor:** an initially BUY fill can become an applied SELL and create a
  negative raw position. The checkpoint cannot be accepted as enforcing exact immutable broker
  truth until this admission path is closed and pinned.

## Unverified items

- Full repository and external Python 3.11/3.12 exact-head CI were not rerun by this review. The
  supplied full-suite/coverage artifacts were hash- and inventory-checked, not treated as evidence
  against the independently reproduced P0-2.
- No SQL/DDL, database engine or fixture, application/runtime wiring, network, broker, credentials,
  Alpaca Paper activity, or git mutation was exercised.
