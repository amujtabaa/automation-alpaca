---
type: Work Order
title: "Reset kernel A: value identity and fill-position integrity"
status: DRAFT
work_order_id: RESET-WO-01
wave: RESET-M1A
model_tier: strong
risk: high
disposition: []
owner: implementation-seat
created: 2026-07-29
---

# RESET-WO-01 — Value identity and fill-position integrity

## Goal

Create the I/O-free economic fact foundation: exact value types, immutable
`FILL | TRADE_CORRECT | TRADE_BUST` identity/lineage, fill-family-derived position and cost
basis, and broker-authoritative overfill/conflict quarantine.

This is M1 work order 1 of 5. Correction/bust support is limited to the pure execution-fact
primitives required by this fill/position semantic center. It does not implement protection,
acquisition, venue attempts, broker effects, reconciliation I/O, persistence, or runtime wiring.

## Activation condition

Do not activate from this packet. M0 must first:

1. land the human-approved exact ADR text and clause migration matrix;
2. update old ADR statuses/backlinks and the safety-core/PKL architecture references;
3. disposition the independent review of those exact canonical files;
4. assign the next conflict-free canonical `WO-NNNN` ID;
5. replace this staged path/commands with the canonical active work order;
6. receive Ameen's explicit activation.

## Context packet

Read completely:

- `AGENTS.md`
- `CLAUDE.md` safety core
- the accepted reset authority ADR
- the accepted reset protection/execution ADR's fill/integrity clauses
- `docs/adr/ADR-001-overfill-quarantine.md`
- `docs/adr/ADR-008-order-status-event-provenance.md` fill provenance clauses
- `docs/adr/ADR-012-submit-recovery-operator-release.md` fill-authority separation only
- `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` INV-1, INV-4, INV-5, INV-7, INV-9
- `work/queue/ARCH-RESET-2026-07/02-target-architecture.md`
- `work/queue/ARCH-RESET-2026-07/03-domain-specification.md` position-integrity paragraphs
- `app/position.py`
- `work/queue/R6A-CONSOLIDATION-PROGRAM.md` section 1 and
  `work/active/SIGNAL-R6aR-STATE.md` only for operator-ratified D-7(a) runtime authority/evidence
- only the existing fill/position tests named in the canonical activation record

The R6 documents preserve the human runtime decision only; R6 implementation remains evidence
and is not target authority or a reset dependency.

## Preserved runtime contract

Operator-ratified D-7(a) is settled authority: Python 3.11 and 3.12 are supported, Python 3.12 is
the development default, and 3.12-only syntax is illegal. M0 does not reopen that decision. It
must verify the actual interpreter/CI command spellings and applicable full gates on the reset
branch and replace the staged command labels below before activation.

## Allowed paths

The canonical activation replaces `RESET-WO-01` with its assigned ID.

```yaml
allowed_paths:
  - app/execution_core/values.py
  - app/execution_core/identity.py
  - app/execution_core/fills.py
  - app/execution_core/position.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_values.py
  - tests/execution_core/test_fill_position.py
  - tests/execution_core/test_fill_position_stateful.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-NNNN*.md
  - work/completed/WO-NNNN*.md
  - work/completed/keep/WO-NNNN*.md
  - work/ledger.jsonl
  - pkl/log.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/events/**
  - app/broker/**
  - app/monitoring.py
  - app/main.py
  - app/server.py
  - app/api/**
  - ui/**
  - docs/adr/**
  - .github/**
```

## Required domain surface

Implement frozen/immutable types for:

- non-negative integer `Quantity`;
- integer `PriceUnits` plus explicit positive decimal `PriceScale` and tick metadata;
- broker/environment/account/symbol/order/root-fill/source-event identities;
- immutable normalized `BrokerFillFact`, `BrokerTradeCorrectFact`, and
  `BrokerTradeBustFact`;
- exact predecessor/root lineage and the effective head/economics for each root fill;
- `BasisAuthority` with `AVAILABLE | BASIS_RECONCILIATION_PENDING`;
- `PositionState` with raw signed quantity, optional authoritative basis, exact average-cost inputs,
  root-fill sequence, and current effective heads sufficient for a separately invoked slow ordered
  fold. A pending state stores no derived candidate as current or cached authority;
- `PositionIntegrity` with `CONSISTENT`, `EXECUTION_FACT_CONFLICT`,
  `EXECUTION_RECONCILIATION_REQUIRED`, and `OVERFILL_QUARANTINE`;
- pure
  `apply_broker_execution_fact(position, integrity, root_heads, seen_facts, fact) -> ExecutionTransition`;
- separate pure
  `derive_ordered_basis_candidate(position_snapshot, root_heads) -> BasisCandidate`, used only by
  tests and the later slow immutable-snapshot restoration path. The fast fact-application function
  never calls this helper for a non-tail revision.

No global equity price scale is assumed. Mandates and locally generated prices compare/operate only
after explicit compatible scale/tick validation. An authoritative broker fill/correction/bust that
exposes incompatible reported scale/tick data still applies its exact raw-quantity/root-head truth;
basis authority becomes `BASIS_RECONCILIATION_PENDING` and no derived price is authorized. The fact
is not rejected, clamped, or delayed. Adapter-specific scale/tick limits remain an M4 gate.

The execution-fact primitives contain no query, retry, release, order-status, persistence high-
water, cancellation, protection, or serving-state machinery. This slice returns typed
reconciliation-required integrity when lineage is incomplete. For a valid revision with later
economic roots, it applies exact raw quantity/root-head truth and returns
`BASIS_RECONCILIATION_PENDING` without computing or storing an ordered-fold candidate. The separate
pure derivation helper proves the arithmetic in tests and is available to the later slow worker;
later M1/M2 slices own the venue effects, immutable-snapshot high-water revalidation, and
authoritative restoration. RESET-WO-02 owns venue recovery and later runtime work consumes these
typed results.

## Required behavior

- [ ] A first valid broker BUY fill creates the exact positive raw quantity and cost basis.
- [ ] A valid broker SELL fill reduces the raw quantity.
- [ ] `FILL` has a unique source-event/root-fill ID and positive absolute quantity/price.
  `TRADE_CORRECT` has its own source-event ID, exact predecessor/root IDs, and positive revised
  absolute quantity/price. `TRADE_BUST` has the same lineage fields and revised absolute
  quantity zero.
- [ ] Applying the same `(broker, environment, account, source_event_id)` with identical full payload twice is
  an economic no-op and returns the original result classification.
- [ ] Only a broker-authoritative correction/bust whose predecessor is the current effective head
  of a broker-authoritative root and whose broker/environment/account/order/symbol/side scope
  matches may replace that root. A human-attested root cannot be revised directly; overlapping
  broker evidence is typed reconciliation-required for the later venue-recovery slice.
- [ ] A valid correction/bust atomically replaces the predecessor head and substitutes the revised
  head at that root `FILL`'s original sequence. It always applies the old-to-new exact raw-quantity
  delta. If no later economic root exists, it may apply the exact basis delta immediately; if later
  roots exist, authoritative basis becomes unavailable under `BASIS_RECONCILIATION_PENDING` and
  the transition does not run or cache the ordered fold. Only the separate slow pure helper may
  derive a candidate from an explicit immutable snapshot. The transition never appends revised
  economics as another positive fill, naively subtracts an old root from basis after later
  dependent facts, or mutates/deletes the immutable predecessor.
- [ ] Missing, stale, branched, out-of-order, or scope-conflicting predecessor lineage sets
  `EXECUTION_RECONCILIATION_REQUIRED`, changes no economics, and returns a typed non-serving
  classification for the later recovery slice.
- [ ] The ordered effective-root fold preserves the accepted long-only average-cost rule in the
  original packet's named source, `app/position.py`:
  BUY adds quantity/notional; SELL proportionally reduces remaining long basis; flat/negative
  carries no long basis. Replacing an earlier head must produce the same result as folding the
  ordered roots with only their new effective heads.
- [ ] The same source-event identity with changed type, predecessor, root, side, quantity, price,
  or order scope preserves the first fact and sets `EXECUTION_FACT_CONFLICT`; no second economic
  delta is applied.
- [ ] Any broker-authoritative fill-family transition that makes raw quantity negative is applied
  exactly and sets permanent `OVERFILL_QUARANTINE`. This includes a SELL overfill and a valid
  correction/bust that reduces an earlier BUY root below already-applied SELL quantity.
- [ ] Overfill is never clamped, hidden, relabeled flat, or rejected merely because it violates
  local expectations.
- [ ] Authorized residual SELL quantity is `max(raw_quantity, 0)` only as an authority cap; the
  raw negative position remains visible.
- [ ] Local/synthetic malformed fills fail validation before economic mutation.
- [ ] An authoritative broker fill/correction/bust that exposes incompatible scale/tick data still
  applies its exact raw-quantity/root-head delta, returns pending basis with no derived-price
  authority, and is never rejected as if it were a local proposal.
- [ ] `HUMAN_ATTESTED` input is not silently treated as broker-authoritative. Its separate
  capacity-capped `FILL` ingestion and non-economic leg-release path remain disabled in this
  slice and are implemented under RESET-WO-02. Human authority cannot emit
  `TRADE_CORRECT`/`TRADE_BUST`.
- [ ] No operation outside the canonical fill-family
  `FILL | TRADE_CORRECT | TRADE_BUST` transition can change raw quantity, root heads, or economic
  basis inputs. A later sequenced `RestoreBasis` command is not a new economic fact: after exact
  immutable-snapshot/high-water revalidation, it may only materialize the deterministic ordered
  fold and change basis authority from pending to `AVAILABLE`; it cannot change quantity, lineage,
  or economics. That command and its persistence checks are outside this slice.
- [ ] `OVERFILL_QUARANTINE` is permanent. Conflict/reconciliation-required integrity cannot
  self-clear through ordinary fact application in this slice; a later recovery/release contract
  must be separately authorized.
- [ ] Every result is deterministic from explicit inputs; no I/O, clock, UUID, randomness, SDK,
  store, or event-log dependency exists.

## Required tests

- [ ] Named examples for BUY, partial SELL, flat, duplicate, identity conflict, negative overfill,
  valid correction, valid bust, and every correction-lineage rejection class.
- [ ] The decisive examples include `BUY 10 @ 100 -> BUST` yielding quantity/basis zero and
  `BUY 10 @ 100 -> CORRECT 7 @ 101` yielding quantity 7/basis 707. They also include
  `BUY 10 @ 100 -> SELL 5 -> CORRECT root to BUY 7 @ 101`, whose revised ordered fold yields
  raw quantity 2 and pending basis in the fast transition; separately invoking the slow helper on
  the same immutable snapshot yields candidate 202 rather than a naive subtract/add value of 207.
  Current basis authority is unavailable until the later M2 gate. `BUY 10 -> SELL 8 -> BUST the BUY
  root` yields raw quantity -8 and permanent `OVERFILL_QUARANTINE`.
- [ ] `RuleBasedStateMachine` generates BUY/SELL, correction/bust chains, exact duplicate,
  conflicting duplicate, missing/stale/branched/out-of-order/scope-conflicting predecessor, and
  overfill histories.
- [ ] After every generated step: raw quantity and effective root heads equal the ordered fold. When
  basis authority is `AVAILABLE`, cost basis equals that fold; when it is pending, authoritative
  basis is absent and no candidate is stored in the transition/state; separately invoking the slow
  helper on that snapshot equals the fold. Duplicates add zero; conflicts and unresolved lineage
  add zero; valid replacements revise quantity and return either exact basis or the typed pending
  marker; overfill facts remain exact; integrity is monotonic.
- [ ] Mutants that (a) count a duplicate, (b) clamp overfill to zero, (c) reject negative, and
  (d) clear integrity, (e) append correction/bust as a positive fill, (f) accept a non-head
  predecessor, (g) let human authority correct/bust, (h) expose a non-tail candidate as current
  basis, (i) revise quantity without the exact available-basis or typed-pending result, (j) reject
  an authoritative broker fact because its tick/scale is incompatible, (k) call the slow ordered
  fold from fast non-tail fact application, and (l) omit quarantine when a correction/bust makes
  quantity negative are each killed by a named property.
- [ ] A boundary test replaces the slow derivation helper with a failing sentinel and proves that
  valid non-tail fact application still commits exact raw quantity/root-head truth and returns
  pending basis without invoking it.
- [ ] A metamorphic oracle substitutes effective root heads at each root's original sequence,
  applies the independent `app/position.py` long-only arithmetic rule, and agrees with incremental
  transitions without copying their branch structure.
- [ ] Shrunk failures become ordinary regression examples.
- [ ] Import-boundary test proves the package has no SQLite, FastAPI, Streamlit, Alpaca SDK,
  sleep, network, incumbent store, or incumbent projector dependency.
- [ ] Determinism test compares complete transitions across repeated runs.

## Required commands

The runtime versions are not unresolved: D-7(a) requires both 3.11 and 3.12, with 3.12 as the
development default and no 3.12-only syntax. The M0 activation record verifies the actual
interpreter/CI spellings and full-gate commands on the reset branch, then replaces the staged
labels below with those exact commands:

```bash
[PYTHON_3_11] -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py
[PYTHON_3_12] -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py
[PYTHON_3_12] -m ruff check app/execution_core tests/execution_core
[PYTHON_3_12] -m ruff format --check app/execution_core tests/execution_core
[PYTHON_3_12] -m mypy app/execution_core
```

Run the repository full static/test gates after the focused corpus is green.

## Acceptance criteria

- [ ] One execution-fact application function contains all fill/correction/bust economic and
  lineage decision logic in this slice.
- [ ] Tests use an independent arithmetic oracle, not a second copy of production branches.
- [ ] Correction/bust facts replace exactly one current root contribution; no positive
  double-count, naive post-hoc basis subtraction, or stale/branched predecessor mutation is
  reachable.
- [ ] Non-tail correction/bust returns exact raw quantity and
  `BASIS_RECONCILIATION_PENDING`; no unauthoritative candidate is exposed as current basis.
- [ ] Broker-authoritative negative position is preserved and quarantined.
- [ ] The focused corpus passes under Python 3.11 and 3.12, and the package contains no
  3.12-only syntax.
- [ ] No incumbent runtime behavior or schema changes.
- [ ] Every required safety pin has RED-capable evidence.
- [ ] No file outside allowed paths changes.
- [ ] Independent blind review returns no unresolved P0/P1.
- [ ] Close-out moves the canonical work order, writes its single ledger line, and records PKL
  impact or explicit non-impact in the same change.

## Stop conditions

Stop and return one batched blocker if:

- an accepted source disagrees on broker-authoritative overfill application;
- exact identity/economic scope cannot be represented without broker adapter behavior;
- exact correction/bust predecessor/root lineage cannot be represented without persistence,
  querying the broker, or adding venue-recovery policy to this slice;
- accepted position authority does not uniquely determine an ordered effective-root fold for a
  correction/bust after later economic facts;
- value comparison requires an unapproved implicit scale conversion;
- the canonical reset branch cannot execute the D-7(a) Python 3.11 and 3.12 gates using the
  M0-verified commands;
- implementation needs persistence, an event projector, or broker I/O;
- the scope needs a current store/event modification;
- two P0s or three same-root P1s appear after implementation.

## Explicit M1 follow-ups

1. `RESET-WO-02`: one semantic center—venue ownership and recovery lifecycle—covering
   venue-attempt/transport-effect separation, multiple concrete acceptances, ADR-012
   human-attested fill ingestion and non-economic exact-leg release, and unknown outcomes.
2. `RESET-WO-03`: trading modes, manual controls, request budgets, and symbol-wide
   admission/final-claim authority.
3. `RESET-WO-04`: position-protection supervisor and hybrid trail.
4. `RESET-WO-05`: acquisition mandate, mandatory protection reference, and cross-side integration.

The later M2 persistence slice owns `RestoreBasis` fault/negative tests: a stale snapshot is refused,
and a successful restoration changes no raw quantity, root head, or economic input.
