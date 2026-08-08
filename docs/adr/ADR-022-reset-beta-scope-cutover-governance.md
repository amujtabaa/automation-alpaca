# Proposed ADR — Reset beta scope, cutover, and development governance

## Status

Proposed. Becomes Accepted only when Ameen approves the exact packet hashes and M0 lands this text
unchanged under an available canonical ADR number.

## Context

The original mission is a narrow, reliable, liquidity-aware protection/acquisition engine for
US equities. Signal Seat hostile-ingress machinery and broad event-log recovery are later scope
expansions and currently dominate blocker effort. Webull/IBKR/Tradier are important future broker
targets but are not prerequisites for proving the broker-neutral kernel with Alpaca Paper.

## Decision

### Beta boundary

- Alpaca Paper and live-shadow only.
- One account, long US equities, small symbol count.
- Manual approval of acquisition/protection authority.
- Extended-hours limit execution; exact broker combinations are capability-tested.
- No live trading mode, shorting, options, crypto, multi-account, or automatic signal approval.
- Signal Seat is disabled, unmounted, absent from the new schema, and not loaded at startup.
- No Webull, IBKR, or Tradier adapter in the reset milestones.

Any future Signal Seat must preserve the untrusted-advisor principle and receive a new
threat/auth/finite-audit ADR. Existing R6 producer rails are frozen evidence, not a reset
dependency.

### Branch and data cutover

- Freeze `master@6d5937492788aa0ab1cf8348321fa01ee57df920`.
- Freeze the active R6 branch at an explicitly recorded M0 SHA; do not merge it.
- Create the reset branch from frozen master.
- Archive old databases/logs read-only; no direct compatibility or bidirectional migration.
- Inventory, disable, and verify disabled every legacy backend, worker, service, scheduled task,
  launcher, watchdog, and automatic restart path capable of reaching the account. A stopped process
  is not proof of a disabled restart path.
- Revoke or isolate every legacy broker credential and legacy writable database path. Inventory
  every legacy claimed/in-flight/outcome-unknown mutating occurrence and its deterministic
  identity/scope. Prove exhaustive acceptance closure plus overlapping broker order/execution
  coverage from before last possible legacy egress through a post-disable watermark; flat/no-open
  state alone is insufficient.
- Commit a supervisor-owned fence naming exact broker=`ALPACA`, environment=`PAPER`, Paper REST/
  stream base origins, account identity, selected application generation, database, deployment
  identity, mode, and recognized query-credential-handle fingerprint in `RECONCILIATION_ONLY`.
  All checkpoint, inbox, fact, effect, immutable claim, owner, closure, and receipt rows bind to
  that singleton generation. Only after the cutover/adapter gates pass may the supervisor
  atomically grant `PAPER_MUTATION_ELIGIBLE`; startup and every final claim compare every field, and
  a live endpoint/credential or any mismatch performs no broker I/O.
- Require the initial Alpaca Paper account to be flat with no open or unknown order after the
  post-disable coverage/occurrence proof.
- Require each reset `SUBMIT`/`REPLACE` client identity to be nonempty, unique in its generation/
  Paper account, and deterministically bound to application generation plus broker/environment/
  account/request occurrence. A legacy/cross-generation collision is external ambiguity and never
  binds to a reset owner.
- Do not invent or infer an opening-inventory fact. External positions/orders halt cutover and are
  resolved outside the reset engine.
- Before the first reset mutating effect, rollback to an old build must repeat the same flat,
  no-open/unknown-order, prior-generation occurrence-closure, post-disable coverage,
  generation-fence, credential-isolation, and datastore checks. After the first reset mutating
  effect or execution fact, the old build cannot regain
  broker authority without a separately reviewed flat recutover; otherwise it is read-only and the
  reset database is preserved.

The exact cutover and rollback proof is defined in `04-persistence-and-cutover.md`. The OS
process-lifetime owner lock coordinates reset processes but does not substitute for this
cross-generation fence.

### Borrowing

- Directly use Hypothesis stateful testing.
- Borrow Nautilus order/emulation/reconciliation/adapter-test contracts selectively.
- Borrow LEAN capability/test organization and run Webull work only as a later separate spike.
- Borrow Barter single-authority/read-replica topology and Exchange Core fixed-point/sequencing
  principles.
- Do not adopt those runtimes, add another language/process, or copy unclear-license code in the
  foundation.

Generic conformance tests/adapters/simulator fixes may be contributed later. Protection policy,
trigger evidence, hybrid trail, urgency, liquidity scoring/repricing, handoff, calibration, and
incident corpus remain proprietary.

### Delivery governance

M1 is split into:

1. value/identity and fill-position-integrity;
2. venue ownership and recovery lifecycle: attempt/effect separation, multi-acceptance, ADR-012,
   and unknown outcomes;
3. trading-mode, manual-control, request-budget, and symbol-wide execution authority;
4. position protection and hybrid trail;
5. acquisition and cross-side integration.

One work order introduces at most one semantic/durable concept. It has exact allowed paths,
invariants, generated/mutation/fault tests, commands, stop conditions, and close-out paths.

Stop-loss:

- one pre-build refutation, one revision, focused recheck;
- two P0s or three same-root P1s return to the reference model/ADR;
- a second defect in one lifecycle edge cannot receive another path-local guard;
- optional functionality that complicates startup/protection is disabled.

Independent review is blind/spec-first and consolidated at human-gated milestones. The reviewer
does not inherit builder rationale and provides a reproduction or code-anchored proof obligation.

Codex/Claude are the default development seats. A broad freelancer engagement is deferred. A
later human specialist may receive a capped adapter/operations/performance deliverable with no
live credentials.

### Human gates

1. Exact ADR packet ratification and M0 documentation landing.
2. First work-order activation after M0 evidence.
3. First outbound Alpaca Paper credential/call use.
4. Native replace or RTH handoff after paper traces.
5. Legacy deletion.
6. Any promotion beyond paper/live-shadow.

Gate 3 evidence must include the disabled-legacy inventory, supervisor generation fence,
credential/datastore isolation, complete inventory and exhaustive closure of legacy
claimed/in-flight/outcome-unknown occurrences, post-disable overlapping order/execution coverage,
flat/no-open-or-unknown-order report, exact Alpaca/Paper/account/origin/recognized-credential
binding, live-endpoint/credential negative control, and explicit pre-first-effect status. Any
proposed old-build reactivation after the first reset effect is a new human-gated recutover, not
routine rollback.

Questions within a work order are batched only for accepted-authority conflict, financial
authority expansion, unverified broker fact, unexpressible schema/state, protected deletion, or
necessary forbidden-path change.

Generation 1 also requires one process-lifetime OS owner lock and the committed
`BOOTSTRAPPING -> RECONCILING -> SERVING` fence before any mutating effect claim. `SERVING` also
requires unified execution-fact-chain integrity, exact owner-to-active-leg-or-terminal-closure
mapping, complete execution coverage, and canonical classification of every effect acceptance set
as defined in `02-target-architecture.md`, `04-persistence-and-cutover.md`, and the proposed current-
state-kernel ADR. `broker_effects` is the sole persisted acceptance-set authority: only `CLOSED`
releases, while `OPEN`/`INVALIDATED` remains in `symbol_may_execute=false`. A terminal owner has one
non-branching ordinal closure chain with one greatest-ordinal head.
Multi-process failover is out of scope.

## Preserved authority

API/UI/import/type boundaries and every safety-core/Spine invariant remain binding. Position and
cost basis change only through canonical execution facts: first-occurrence broker/human `FILL`
facts and immutable broker-authoritative `TRADE_CORRECT`/`TRADE_BUST` revisions of one exact fill
root. No status or acknowledgement changes quantity. ADR-009's untrusted-producer principle
remains the minimum for any future producer; this ADR disables rather than weakens current Signal
Seat security.

## Consequences

- The first end-to-end broker position is created only after acquisition and protection are both
  implemented; earlier SELL work uses simulator/live-shadow inputs.
- R6 work is not “completed by tolerance”; it is removed from beta dependency.
- Multi-broker ambitions remain compatible through ports/capabilities without delaying Alpaca
  proof.
- Terminal order history remains queryable through immutable owners/closures without growing the
  operational checkpoint with campaign length.
- A legacy build is not a broker-facing rollback target after reset economic activity begins.
- Calendar time includes paper soak and review; typing speed is not the readiness gate.
