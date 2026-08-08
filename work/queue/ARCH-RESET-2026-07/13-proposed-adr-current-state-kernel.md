# Proposed ADR — Current-state execution kernel and audit separation

## Status

Proposed. Becomes Accepted only when Ameen approves the exact packet hashes and M0 lands this text
unchanged under an available canonical ADR number.

## Context

The current system distributes business decisions across the event projector, memory store,
SQLite store, and orchestration code. Repeated P0/P1 findings show that parity between independent
derivations proves agreement, not correctness. Full-history folds have also entered startup and
single-writer live paths.

The beta has one account, few symbols, Alpaca Paper, and no requirement to preserve direct use of
old databases/logs. A distributed system or wholesale framework migration is unjustified.

## Decision

### One writer and one transition kernel

One account sequencer owns every capital-relevant state transition:

\[
(\text{typed input},\ \text{current state})
\rightarrow
(\text{new state},\ \text{decision receipts},\ \text{broker effects})
\]

The pure reducer performs no I/O, clock/UUID/random reads, sleeping, SDK calls, persistence, or
logging. All nondeterministic values enter explicitly.

SQLite repositories, broker adapters, dispatchers, reconcilers, APIs, and tests do not reproduce
business branches. Technical dedupe/version checks enter the reducer as typed facts.

Effect claim and every broker outcome are sequenced inputs. The dispatcher:

1. requests `ClaimEffect`;
2. waits for its committed reducer result;
3. performs only the authorized I/O;
4. submits the normalized outcome back through the sequencer.

It never mutates operational state directly.

### Production persistence

SQLite is the only beta production persistence implementation. Tests exercise the reducer and a
thin SQLite unit-of-work harness; there is no second hand-written in-memory trading engine.

One transaction:

- identifies/deduplicates the input;
- loads the exact current checkpoint/effect/unified-execution-chain high-water;
- runs the reducer;
- inserts first-occurrence `FILL`, `TRADE_CORRECT`, or `TRADE_BUST` facts and advances their one
  unified execution chain;
- writes new current state, immutable venue-identity owners or next-ordinal terminal closures, and
  canonical occurrence-level acceptance-set closure/invalidation state in `broker_effects`;
- for `ClaimEffect`, inserts the immutable `broker_effect_claims` row before the effect-state edge;
- writes a mandatory decision receipt;
- records the canonical input outcome;
- commits before in-memory publication or broker I/O.

The execution checkpoint is bound to `(last_execution_sequence, execution_chain_sha256)`. Every
economic write transaction establishes the state/fact invariant inductively. Normal startup checks
the state hash, singleton application generation, indexed last sequence/chain hash, pending-basis
state, and broker parity; it does not refold every historical root. A separately measured,
non-serving M2/cutover/repair audit substitutes every root's current immutable head at that root
`FILL`'s original sequence, applies the accepted ordered long-only average-cost fold, and requires
exact position/basis agreement. Any audit mismatch halts.
`TRADE_CORRECT` and `TRADE_BUST` are broker-authoritative linked facts: each names one broker-
authoritative root and its current predecessor, matches exact broker/environment/account/order/
symbol/side scope, and changes state by the atomic delta between the old and revised folds. A
naive post-hoc subtraction/addition after later economic facts is forbidden. They never overwrite
a prior fact. A missing, branched,
out-of-order, root-conflicting, or scope-conflicting adjustment halts in reconciliation; beta does
not guess or auto-repair.

A non-tail correction/bust never causes a history fold inside the fast write transaction, but the
valid canonical fact and exact signed root-quantity delta commit immediately. The same transaction
sets `BASIS_RECONCILIATION_PENDING`, makes basis unavailable, records cancellation/reconciliation
effects for every potentially live exposure-increasing BUY and any newly oversized SELL, blocks
entry, and forces every positive long residual into restricted `HARD_BAIL`. Actual broker
outcomes remain occurrence-tracked. While any conflicting leg/set remains potentially live, only
cancel/query/reconcile may claim; after the ordinary uncertainty gate passes, basis-independent,
quantity-capped risk reduction is eligible. A slow worker
derives basis from an immutable chain snapshot; only a sequenced transaction that revalidates the
exact high-water may restore basis and its dependent formula values. A stale/disputed basis
candidate is discarded without reversing canonical quantity truth.

The checkpoint also contains versioned engine phase, active/unresolved per-leg venue-attempt
state, broker execution-fact coverage, and account-wide request budgets. It does not duplicate
acceptance-set state: the closure/invalidation fields in `broker_effects` are the sole persisted
authority, and any in-memory view is reloaded from them. `INVALIDATED` permanently blocks release
in generation 1. Every creating client identity is nonempty, application-generation/Paper-account
unique, and bound to the generation/broker/environment/account/occurrence tuple.
`venue_identity_owners` is an immutable uniqueness ledger: one effect may own several concrete
broker IDs, but a composite parent key binds each owner to one exact effect, generation, client
binding, occurrence, symbol, and economic scope. A
terminal owner leaves the checkpoint and gains ordinal 1 of one immutable terminal-closure chain;
each later canonical `FILL`, `TRADE_CORRECT`, or `TRADE_BUST` that changes its terminal economics
appends the immediately successive ordinal for that same owner.
Root-ordinal, predecessor, and owner constraints make the greatest ordinal the unique current
head. Repository constraints and the atomic close
transition enforce that every owner maps to exactly one active/unresolved checkpoint leg or one
current terminal-closure head, never both. Startup verifies checkpoint legs and unresolved effects
through indexed owner/head lookups; it does not load or scan all terminal history.

Every created mutating occurrence starts with canonical `acceptance_set_state=OPEN`, which means it may
have an undiscovered broker acceptance and remains potentially live even if all currently known
legs are terminal. A locally canceled occurrence may close as `NEVER_DISPATCHED` only when
the immutable `broker_effect_claims` table has no row for the effect/generation; decision receipts
cannot prove absence. Otherwise only an adapter-certified complete response or an exact-occurrence query plus
complete cursor/interval coverage may commit `CLOSED`. Leg terminality, one not-found response, or
position parity cannot close the set. A delayed acceptance after closure preserves the proof,
appends contradiction evidence, and moves only to permanently non-releasable `INVALIDATED`. A
persisted/in-memory mismatch remains non-serving. The exact fields and transaction constraints are normative in
`04-persistence-and-cutover.md`.

### Authority

- First-occurrence canonical execution facts are the only source of raw position/cost-basis
  deltas: broker-authoritative fills, corrections, and busts, plus capacity-capped human-attested
  fills. Correction/bust roots are broker-authoritative; overlapping evidence for a human-attested
  interval remains reconciliation-required until exact mapping prevents double count. No
  acknowledgement or status observation changes quantity.
- Transactional current state governs what may happen now.
- Broker observations inform reducer-owned venue-attempt state; they do not overwrite local
  lifecycle blindly.
- Broker reports/reconciliation establish external parity and close ambiguity under ADR-002/012.
- Versioned configuration governs the exact mandate that references it.
- Mandatory decision receipts explain committed transitions but are never folded for live state.
- Replay tapes drive the reducer/simulator in testing and forensics; they are not operational
  counters.
- UI/read projections have no mutation authority.

### Fast and slow paths

The modular monolith uses distinct bounded mailboxes:

- reserved broker-order/fill facts;
- per-symbol protection-market facts;
- lower-priority control/entry work.

Broker overflow marks a stream gap and enters `REDUCING`/reconciliation; absence is never inferred
from the gap. Market overflow invalidates trigger evidence until a fresh baseline. Entry work is
shed first. Priority cannot preempt an in-flight transaction, so every transaction is bounded and
contains no network call, history fold, or report construction.

The broker adapter must close an execution-stream gap with a fully paginated overlapping
cursor/time/sequence interval from the last committed coverage watermark through a
post-resubscription watermark. Position parity alone cannot prove coverage because omitted fills
can offset. The same normalized stream/report contract must preserve and order `FILL`,
`TRADE_CORRECT`, and `TRADE_BUST`; unknown financial-state event kinds are not silently ignored.
If the adapter cannot prove the interval or represent the event vocabulary, the engine remains
non-serving.

One outbound request arbiter owns the adapter rate profile. It selects committed effects by
priority and sequence, reserves capacity for emergency cancel/query/reconciliation, and asks the
reducer to claim an effect only when a call slot is immediately available. The claim revalidates
and consumes the mutating-request budget; no claimed effect waits in another outbound queue.
Queries receive a sequenced, budget-consuming `ClaimBrokerQuery` immediately before I/O but do
not create a broker effect or venue owner.

No live transition performs work proportional to audit-history length. Incremental market state
is bounded. A tick-rounded trail increase is committed before gaining authority; restart cannot
loosen the persisted trail.

### Failure isolation

- A failed SQLite transaction emits no broker effect.
- In-memory state publishes only after commit.
- A commit-response or cache-publication uncertainty stops claims/commands, discards the cache,
  and reloads under startup reconciliation; it never continues at the presumed old state.
- A mandatory decision-receipt failure rolls back and is execution-storage fatal; this is not
  mislabeled optional.
- Optional tape/export/metrics/UI failure does not block the account engine.
- Signal Seat is absent from schema/startup.
- Corrupt historical receipts are not read to calculate current state.

### Process ownership and startup fence

Generation 1 permits one process on one local host and a non-network filesystem. Before opening
the execution database or starting an adapter, the process acquires a process-lifetime OS
advisory lock keyed by canonical `(broker, environment, account_key)` in a fixed local runtime
directory; lock metadata records the database path. A second path for the same account cannot
become another owner. Lock failure exits without broker I/O. SQLite transaction serialization is
not writer fencing.

After acquiring the lock, the process commits `BOOTSTRAPPING` in safe trading mode before any
dispatcher or command-serving task exists, then commits `RECONCILING`. Mutating effect claims are
denied until broker order/position parity, complete execution-fact coverage, venue-owner
and terminal-closure integrity, canonical classification of every effect acceptance set, no
pending basis repair, and surviving-effect revalidation allow a committed account-level `SERVING`
edge. Every `OPEN`/`INVALIDATED` quarantine remains in `symbol_may_execute=false` and cannot release
same-symbol work. A crashed predecessor can be
replaced only after the OS releases its lock, and the successor always runs the full fence; there
is no TTL or dual-writer failover.

That lock fences reset-generation processes only. Clean cutover separately inventories, disables,
and verifies disabled every legacy service, scheduled task, launcher, watchdog, and automatic
restart path; isolates legacy credentials and writable databases; inventories every legacy
claimed/in-flight/outcome-unknown mutating occurrence; and proves each acceptance set closed with
overlapping order/execution coverage through a post-disable watermark. Flat/no-open state alone is
not closure. The supervisor fence first names exact Alpaca broker, Paper environment and REST/
stream origins, account identity, reset generation, database, deployment, mode, and recognized
query-credential fingerprint as `RECONCILIATION_ONLY`, then may atomically grant
`PAPER_MUTATION_ELIGIBLE` only after all cutover/adapter gates pass. Checkpoint, inbox, fact, effect,
immutable claim, owner, closure, and receipt rows bind to the singleton application generation. The
process performs no broker I/O unless every fence field matches; final claim repeats the comparison,
and a live endpoint/credential never matches.

### Fresh cutover

The initial reset cutover requires an Alpaca Paper account with no position, no open or unknown
order, exhaustive closure of every legacy mutating occurrence, and complete post-disable
order/execution coverage. There is no opening-inventory/adoption fact. External positions/orders
or an unprovable legacy occurrence halt cutover and are resolved outside the reset engine.

Old databases/logs are archived read-only and legacy launchers cannot write them or use a broker
credential. After the first reset mutating effect or execution fact, an old build may not regain
broker-facing authority. A return requires a separately reviewed flat recutover proving no open or
unknown order, exhaustive prior-generation occurrence closure through a post-disable watermark,
complete execution coverage, parity, and exact selected generation/datastore identity. Otherwise rollback stops reset broker I/O, preserves its database, and permits only
read-only observation by the old build. No bidirectional migration, stale-authority fallback, or
mixed-version writer is supported. The procedural detail is normative in
`04-persistence-and-cutover.md` and `15-proposed-adr-reset-scope.md`.

## Preserved authority

This ADR preserves:

- execution-fact-only position mutation, including immutable broker corrections/busts, and exact
  broker overfill visibility;
- deterministic identity and unknown-outcome quarantine;
- independent ownership of every concrete broker acceptance and ADR-012's separate
  human-fill/non-economic release boundary;
- one logical writer;
- thin API/UI and adapter-only broker SDK;
- immutable audit evidence and deterministic testing.

It supersedes only ADR-004's universal operational event-log truth, dual-store business parity,
and live full-history projection mechanics.

## Consequences

- Current state cannot be rebuilt solely from general audit receipts; broker reconciliation and
  the verified checkpoint/unified execution chain are required.
- Checkpoint corruption halts rather than invoking complex tolerant replay.
- SQLite performance is a measured M2 gate.
- Broker coverage and rate-limit behavior are adapter conformance gates, not inferred API facts.
- Generation 1 intentionally has no multi-process high availability.
- A later second production store, opening inventory, or event-sourced recovery requires a new
  ADR.

## Required evidence

- Pure reducer/stateful model tests.
- SQLite crash injection at every write/call boundary.
- Unified execution-chain/checkpoint mismatch tests, including fill-correction-bust head algebra,
  branch rejection, out-of-order predecessor, interleaved-SELL ordered refold, and restart.
- Claim-versus-kill race tests.
- Queue overflow/reconciliation tests.
- Multi-acceptance tests where a delayed sibling appears after all known legs close, false
  `NEVER_DISPATCHED` after a committed immutable claim and corrupted effect row, delayed acceptance
  after `CLOSED` producing terminal `INVALIDATED`, canonical-effect/in-memory acceptance mismatch,
  terminal-closure duplicate-root/gap/cross-owner/branch rejection, owner-parent account/symbol/
  occurrence/scope substitution, null/duplicate/cross-generation creating-client identity, and
  owner-to-active-leg-or-terminal-closure totality tests; human-attested
  fill/release, startup-fence, legacy-launcher restart, pre/post-first-effect rollback,
  second-process, commit/publication, broker-coverage gap, and live-endpoint/credential fence-
  mismatch tests;
- History-length scaling benchmark covering bounded normal startup separately from the non-serving
  full ordered-root/hash audit.
- Independent review before any paper broker effect relies on the design.
