# Architecture-reset war-game

Scope: **FULL** under `.ai-os/core/18_WARGAME_PROTOCOL.md`. The reset changes event-log truth,
schema, stateful artifacts, protection/order semantics, and accepted ADRs.

## M1 — Assumption ledger

No load-bearing `ASSUMED` item is ratified. Each is converted to a named gate.

| ID | Claim | Label and evidence | Resolution |
|---|---|---|---|
| A1 | Duplicated truth is the treadmill root | `TRACED`: `work/review/AUDIT-0001-quarantine-treadmill.md`; R6 store/projector audit | One reducer/one writer |
| A2 | Current stores contain independent business decisions | `TRACED`: current memory/SQLite/core implementations | Persistence may perform technical checks, not policy |
| A3 | Full-history live folds create startup/latency failure domains | `TRACED`: REV-0044/R6 records and paths | Receipts/history are not live authority |
| A4 | Current hard-floor meanings conflict | `TRACED`: `app/protection.py`, ADR-010 §2, sell-policy validator | Trigger/guard split |
| A5 | Existing database compatibility is unnecessary | `INHERITED`: Ameen 2026-07-29 | Clean database |
| A6 | Modular monolith meets latency/load | `ASSUMED → GATE M2-G1/M5-G1` | Queue/SQLite benchmarks on target hardware |
| A7 | SQLite remains suitable | `INHERITED` only for stack choice; new schema/concurrency is `ASSUMED → M2-G1` | Crash/performance/corruption evidence |
| A8 | Serialized account checkpoint is simpler | `ASSUMED → GATE M2-G2` | Size/write/restart benchmark; reject if budgets fail |
| A9 | Pre-call claim prevents blind resend | `ASSUMED → GATE M1B/M2-G3` | Must include claim/kill race, all readers, recovery/release |
| A10 | Generated reference model improves defect discovery | `TRACED`: current Hypothesis practice and duplicated-store failures | Mutation/stateful gate |
| A11 | Top-of-book can validate first behavior | `ASSUMED → GATE M5-G2` | Fixed child cap; shadow/replay comparison; depth no authority |
| A12 | 8%/7.5%/8%/2.5 ATR defaults are useful | `ASSUMED → GATE M5-G3` | Calibration only; versioned change |
| A13 | Two-quote or trade+quote evidence balances error/delay | `ASSUMED → GATE M5-G4` | Phantom/gap tape measurement |
| A14 | Current Alpaca adapter contains portable behavior | `ASSUMED → GATE M4-G1` | Port rule-by-rule after conformance |
| A15 | Current Alpaca session/order facts remain valid | `ASSUMED → GATE M4-G2` | Re-verify primary docs and Paper |
| A16 | Explicit integer scale/tick value type is sufficient | `ASSUMED → GATE M1A-G1` | Generic compatible-scale tests; adapter limits later |
| A17 | Native RTH handoff can avoid overlap | `ASSUMED → GATE M7-G1` | Capability/fault traces |
| A18 | Measured handoff gap is acceptable | `ASSUMED → GATE M7-G2` | Separate human ratification |
| A19 | Signal Seat can be removed from beta | `TRACED`: original reports omit R6; feature disabled now; not core mission | Unmounted/absent from schema |
| A20 | AI can implement without broad freelancer | `INHERITED`: user preference plus bounded module plan | Reassess only at external specialist blocker |
| A21 | One effect maps to at most one broker order | `REJECTED`: ADR-002 explicitly permits multiple concrete acceptances | Immutable one-to-many venue owners |
| A22 | Stream reconnect plus position parity proves no fill loss | `REJECTED`: offsetting omitted fills can preserve net position | Adapter coverage cursor/interval gate |
| A23 | SQLite serialization implies one process writer | `REJECTED`: a network call outlives a SQLite transaction | Process-lifetime OS lock + full takeover fence |
| A24 | Inbound priority protects broker request capacity | `REJECTED`: broker rate limits are a separate outbound resource | One request arbiter with reserved capacity |

## M2 — Lifecycle totality

### Checkpoint and fill chain

```text
ABSENT -> VERSION_0
VERSION_N + valid input -> VERSION_N+1 bound to exact fill high-water/hash
VERSION_N + failed transaction -> VERSION_N
binding/hash/position mismatch -> HALTED
verified cutover -> READ_ONLY_ARCHIVE
```

Writer: sequenced command processor/reducer plus SQLite unit of work. No automatic repair.

### Inbox

```text
UNSEEN -> APPLIED | REFUSED | RECONCILIATION_PENDING
RECONCILIATION_PENDING + verified same-high-water fold -> APPLIED
APPLIED/REFUSED/RECONCILIATION_PENDING + same hash -> same canonical outcome
existing identity + different hash -> typed CONFLICT / RECONCILE
```

Technical identity result is a reducer input. Repository code cannot invent economic handling.

### Fill and position integrity

```text
UNSEEN broker fill -> RECORDED -> raw position delta
exact duplicate -> no economic delta
same identity / different economics -> FILL_IDENTITY_CONFLICT
broker SELL beyond long qty -> exact negative raw qty + OVERFILL_QUARANTINE
```

Integrity is monotonic in ordinary processing. No clamp/hide/reject of authoritative overfill.
`TRADE_CORRECT` and `TRADE_BUST` are first-occurrence immutable execution facts linked to an exact
predecessor `FILL`/revision. They substitute the root head at the original root sequence and apply
only the old-fold-to-new-fold delta through the same reducer; they never overwrite prior economics
in place or subtract an earlier root naively after later dependent facts (`AR-04` -> `PA-04`).

### Broker effect

```text
REQUESTED -> CANCELED_BEFORE_DISPATCH
REQUESTED -> DISPATCH_CLAIMED
DISPATCH_CLAIMED -> ACKNOWLEDGED | REJECTED | OUTCOME_UNKNOWN
OUTCOME_UNKNOWN -> ACKNOWLEDGED | REJECTED | NEEDS_REVIEW
NEEDS_REVIEW -> OPERATOR_RECONCILED only when every owned leg is exactly closed
                and parent acceptance_set_state is CLOSED
```

Every edge is a reducer transition. Dispatcher performs I/O only. Claim rechecks kill/mode,
expiry, scope, capability, quantity, and symbol-wide ownership.

The durable ever-claimed predicate is separate and monotonic:

```text
NO_CLAIM_ROW -> immutable broker_effect_claims row -> EVER_CLAIMED
EVER_CLAIMED -> never absent, even if mutable effect fields are corrupted
```

`NEVER_DISPATCHED` requires `NO_CLAIM_ROW`; decision receipts never supply that predicate.

### Venue attempt

```text
LOCAL_PLANNED -> SUBMIT_CLAIMED -> SUBMIT_UNKNOWN | WORKING | TERMINAL_REJECTED
WORKING -> PARTIALLY_FILLED | CANCEL_PENDING | REPLACE_PENDING | TERMINAL_*
CANCEL_PENDING -> CANCEL_UNKNOWN | TERMINAL_CANCELED | TERMINAL_FILLED
REPLACE_PENDING -> REPLACE_UNKNOWN | predecessor/successor authoritative states
any potentially-live state -> NEEDS_REVIEW when evidence cannot close
NEEDS_REVIEW -> OPERATOR_RECONCILED only for one exact leg/occurrence
```

Transport acknowledgement never supplies an order-terminal edge. Delayed status cannot regress;
new fills still apply. One effect may own multiple concrete legs; every leg closes independently.
Terminalizing one discovered leg does not prove that the occurrence created no latent sibling.
Only a coverage-backed canonical `broker_effects.acceptance_set_state=CLOSED` reducer fact can
close discovery and release occurrence-wide ownership (`AR-02` -> `PA-02`). The checkpoint retains only active or
unresolved legs; compaction of a terminal leg requires an immutable terminal-closure ledger fact
whose one root and non-branching same-owner ordinal chain prevent restart, duplicate observation,
forked heads, or stale generation from reactivating it
(`AR-05` -> `PA-05`).

Acceptance state is `OPEN -> CLOSED -> INVALIDATED`. `CLOSED` requires exhaustive proof;
`INVALIDATED` is reached only when later acceptance evidence disproves that retained proof and is a
permanent non-release state in generation 1. No edge returns it to `OPEN` or `CLOSED`.

### Venue identity owner

```text
UNSEEN concrete broker id -> immutably bound to effect occurrence/scope
same owner/scope -> exact duplicate
same broker id / different owner or scope -> CONFLICT + HALT
one effect -> zero, one, or multiple owned broker ids
```

The identity row is immutable; mutable per-leg status lives in the versioned checkpoint and must
match the owner set at startup.

### Human-attested recovery

```text
NEEDS_REVIEW + missing economic fills
  -> capacity-capped HUMAN_ATTESTED fill(s)
  -> exact cumulative leg-fill parity
  -> non-economic OPERATOR_RECONCILED
```

The release changes no quantity, cannot use broker overfill authority, clears one leg only, and
cannot create a successor in the same transition.

### Protection

`FLOOR_ONLY -> TRAIL_ACTIVE -> EXIT_NORMAL -> HARD_BAIL`, with direct hard-bail edges and
`qty==0 AND no attempt may execute -> FLAT`. A terminal ownership fact may finalize flat after a
prior fill established zero. Hard bail has no ordinary resume. Trigger corroboration consumes
distinct, deduplicated, strictly advancing observation occurrences; replaying one quote twice
cannot satisfy a two-observation rule (`AR-06` -> `PA-06`). Hard-bail authority preserves the
immutable versioned formula/rule and fill-derived inputs separately from the mutable armed trigger;
recalculation may tighten but not loosen that trigger (`AR-07` -> `PA-06`).

BUY-resolution waiting is orthogonal to protection policy:
`EXIT_WAITING_BUY_RESOLUTION(policy_state)` retains whether `policy_state` is `EXIT_NORMAL` or
`HARD_BAIL`; waiting alone never promotes normal exit to hard bail (`AR-08` -> `PA-06`). `FLAT` is
not allowed to hide later broker truth: a correlated late BUY fill applies its exact delta and
immediately re-enters a protected `HARD_BAIL`/critical state (`AR-09` -> `PA-06`).

### Acquisition

No BUY effect exists without an immutable approved protection reference. First fill instantiates
floor protection. Exit intent with a potentially-live BUY enters durable
`EXIT_WAITING_BUY_RESOLUTION(policy_state)` without rewriting the underlying `EXIT_NORMAL` or
`HARD_BAIL` policy; it may require human release and is not called bounded.

### Native/local ownership

```text
LOCAL_EMULATED -> HANDOFF_TO_NATIVE -> NATIVE_CONFIRMED
NATIVE_CONFIRMED -> HANDOFF_TO_LOCAL -> LOCAL_EMULATED
either handoff -> OWNERSHIP_AMBIGUOUS
```

Both directions require incumbent terminal/reconcile, fill ingestion, broker parity, residual
recompute, atomic claim, and authoritative successor working status.

### Trading mode and manual control

`HALTED`/kill permits cancel/query/reconcile only, except a command-carried one-shot emergency
grant. `REDUCING` allows capped reduce-only work. Symbol-wide unknown work blocks acquisition,
protection, flatten, emergency reduce, and handoff.

### Runtime and process ownership

```text
OS_LOCK_ABSENT -> acquire or EXIT_NO_IO
BOOTSTRAPPING -> RECONCILING -> SERVING
commit/publication unknown -> STOP_CLAIMS -> reload -> RECONCILING
stream gap -> REDUCING -> covered paginated interval -> eligible to SERVE
```

No mutating claim is legal before `SERVING`. A successor process starts only after OS lock release
and never inherits a predecessor's serving phase.

The application-generation identity is committed before startup can serve and is carried by every
immutable claim, broker effect, and execution fact. Every creating broker-visible identity is
generation/Paper-account bound. The supervisor fence also matches exact Alpaca/Paper REST/stream
origins, account, deployment, mode, and recognized credential fingerprint at startup and final
claim; a live endpoint/credential performs no I/O. Before the first reset effect/fact, an aborted cutover
may return to the isolated old environment after both processes are stopped and verified. After
the first reset effect or execution fact, the old build cannot regain broker authority; returning
requires a separately reviewed flat/no-open-order re-cutover into a fresh single generation
(`AR-03` -> `PA-03`).

## M3 — Consumer inventory and unsafe-control sweep

| Artifact | Every control reader | Required classification |
|---|---|---|
| Checkpoint/execution-fact binding | Startup, command processor, integrity verifier | Mismatch halts; no guessed repair |
| Execution facts/integrity | Reducer, position, residual cap, protection, acquisition, reconciliation, cockpit | `FILL`/`TRADE_CORRECT`/`TRADE_BUST` are immutable and predecessor-linked; duplicate/conflict/overfill paths explicit |
| Broker effect | Reducer, claim command, dispatcher/arbiter read, kill/expiry/cancel, startup, reconciler, operator release | Only committed serving/rate-authorized claim calls broker |
| Venue identity owner | Reducer, checkpoint verifier, `symbol_may_execute`, reconciler, operator release | One effect may have many; broker ID has one immutable owner; occurrence release also requires canonical `broker_effects.acceptance_set_state=CLOSED` |
| Venue attempt/observation | Reducer, `symbol_may_execute`, protection/acquisition/flatten/handoff, reconciler, cockpit | Every leg closes independently; active/unresolved checkpoint is bounded by immutable terminal closure facts; terminal non-regression; ack ≠ terminal |
| Protection state | Reducer, executor goal, alert/read view | Distinct trigger occurrences, immutable formula plus armed value, orthogonal BUY wait, and late-fill recovery are reducer-owned; UI/alert cannot transition |
| Acquisition state | Reducer, `symbol_may_execute`, protection preemption | Mandatory protection authority |
| Trading mode/emergency grant | Admission, effect creation, final claim, manual controls | Kill/claim race ordered; grant one-shot/scoped |
| Native/local owner | Reducer, claim, reconciler, cockpit | Time/ack alone cannot confirm |
| Current market | Reducer protection/executor inputs | Overflow/stale invalidates evidence |
| Broker fact coverage | Startup/reconnect/gap recovery, serving gate, cockpit | Full paginated overlap required; parity alone insufficient |
| Engine phase/process lock | Startup, claim, API, dispatcher, takeover | One process and one application generation; no mutating claim before serving; no old-build broker rollback after reset authority begins |
| Request budget/priority | Claim reducer, broker arbiter, reconciliation | Entry/reprice cannot exhaust reserved emergency capacity |
| Decision receipt | Incident/read/export only | No control reader; failed write rolls back |
| Configuration version | Mandate, reducer, capability, replay | No historical reinterpretation |

Unsafe-control questions:

1. **Needed action omitted:** reserved broker mailbox, market evidence invalidation, entry shedding,
   transaction-duration gate, gap reconciliation.
2. **Unsafe action taken:** kill/claim ordering, symbol-wide `may_execute`, stale/status legal
   transitions, fill identity/integrity.
3. **Wrong timing:** commit before publish/call; cancel ack not terminal; handoff parity/residual
   re-read.
4. **Applied too long/short:** hard bail only clears at flat; unknown has ADR-002/012 release;
   Signal Seat absent; native ownership requires authoritative state.

## M4a — Prospective-hindsight brief

Assume the reset caused an incident:

1. Crash after broker acceptance caused resend.
2. Kill committed after `REQUESTED` but before claim, yet BUY still dispatched.
3. Dispatcher/reconciler became extra state writers.
4. Cancel acknowledgement freed single-flight before order terminal.
5. Delayed `SUBMITTED` regressed a `FILLED` attempt.
6. Fill ledger/checkpoint diverged without a binding high-water.
7. Broker overfill was clamped/rejected.
8. Non-flat cutover invented local position without a fill.
9. Acquisition filled without approved protection authority.
10. Hard bail waited indefinitely on unknown BUY without an explicit state/alert.
11. Manual flatten or hard bail bypassed `HALTED`/unknown-attempt rules.
12. Local→native handoff used stale quantity or HTTP ack as protection.
13. Shared queue/long transaction starved broker fills.
14. Phantom data triggered; corroboration delayed a real gap.
15. Static emergency guard became another floor.
16. Mandatory audit failure was mislabeled optional.
17. Broad W01 reintroduced multiple semantic centers.
18. Summary ADR approval silently changed accepted safety clauses.
19. A second concrete acceptance was overwritten by one effect row.
20. Operator release closed an unknown leg before missing fills entered canonical quantity.
21. A stale `REQUESTED` BUY dispatched while startup reconciliation was still running.
22. Queue overflow lost two offsetting fills while position parity appeared correct.
23. Entry/reprice calls exhausted the request budget needed for cancel/reconciliation.
24. Two processes each claimed and called the broker.
25. Commit succeeded, cache publication failed, and the old in-memory state continued.

Every cause is now mapped to the lifecycle/consumer contracts above, exact proposed ADRs, the
fresh-account cutover, the five-work-order M1 split, or a named later gate.

## M4b — Fresh-context refutation pass 1

Verdict: **BLOCK**. The fresh agent plus independent ADR/persistence subreviews returned 18
material findings. All were applied before ratification.

| ID | Sev | Finding | Packet correction |
|---|---|---|---|
| M4B-01 | P0 | Fresh DB + non-flat account violated fill-only truth | Flat/no-open-order cutover required; no adoption fact |
| M4B-02 | P0 | Overfill/negative position absent | Position-integrity quarantine and first W01 properties |
| M4B-03 | P0 | Acquisition could fill without protection authority | Mandatory immutable protection reference |
| M4B-04 | P0 | `REQUESTED` effect survived kill before claim | `CANCELED_BEFORE_DISPATCH`; claim revalidates through reducer |
| M4B-05 | P0 | Dispatcher/reconciler were extra writers | I/O-only dispatcher; all edges sequenced/reduced |
| M4B-06 | P0 | Effect ack conflated with order terminal | Separate `BrokerEffect` and `VenueAttempt` lifecycles |
| M4B-07 | P0 | Unknown closure accepted weak not-found | Exact occurrence/scope; ADR-002/012 release retained |
| M4B-08 | P0 | Broker status could regress | Provenance + legal monotonic transition contract |
| M4B-09 | P0 | Per-mandate ownership missed cross-side exposure | One symbol-wide `may_execute` at three choke points |
| M4B-10 | P0 | Native handoff stale-sized/ack-confirmed | Fill/parity/residual re-read; authoritative working confirmation |
| M4B-11 | P1 | Zero quantity could never later finalize flat | Terminal ownership fact may complete flat without qty change |
| M4B-12 | P1 | Checkpoint/fills lacked binding/repair rule | Fill sequence/hash chain; mismatch halts; canonical inbox outcome |
| M4B-13 | P1 | Mandatory audit contradicted optional failure claim | Mandatory decision receipt vs optional export made explicit |
| M4B-14 | P1 | Priority queue was only prose | Separate mailboxes, overflow/gap semantics, transaction budget |
| M4B-15 | P0 | Summary ratification activated code before exact ADRs | Exact ADR files/hash approval; M0-only authorization |
| M4B-16 | P0 | Accepted safety clauses could disappear on rename | Clause-level migration matrix; exact preservation |
| M4B-17 | P1 | First work order had many semantic centers/no close-out | W01 narrowed to fill-position integrity; M1 split five ways |
| M4B-18 | P1 | BUY ambiguity delay falsely called bounded | Durable waiting condition, alert, accepted human release |

## M4b — Focused corrective recheck

Verdict: **BLOCK**. A second blind reader found seven remaining P0/P1 gaps. The packet was revised
again by simplifying each mechanism rather than adding path-local guards.

| ID | Sev | Finding | Packet correction |
|---|---|---|---|
| M4B-19 | P0 | Ratification did not name exact ADR hashes | Exact ratification-unit SHA-256 table and approval wording |
| M4B-20 | P0 | Singular broker ID lost multiple concrete acceptances | Immutable one-to-many `venue_identity_owners`; per-leg checkpoint state |
| M4B-21 | P0 | ADR-012 fill/release split was unrepresentable | Authority-bearing fills plus separate exact-leg non-economic release |
| M4B-22 | P0 | Stale outbox could dispatch before startup parity | Persisted `BOOTSTRAPPING -> RECONCILING -> SERVING` claim fence |
| M4B-23 | P1 | Stream-gap recovery had no coverage proof | Persisted coverage watermark plus paginated overlapping interval gate |
| M4B-24 | P1 | Inbound priority did not protect broker-call capacity | One outbound arbiter, committed priority/sequence, reserved emergency capacity |
| M4B-25 | P1 | One writer had no process fence | Process-lifetime OS lock and full fail-closed takeover |

## M4c — Changed-claim verification

Verdict: **PASS**. A fresh narrow reviewer found no remaining P0/P1 in M4B-19 through M4B-25 or
in the resulting schema/ADR/work-order consistency. The reviewer explicitly verified:

- exact hash-bound ratification with a separate post-M0 implementation activation;
- zero/one/multiple concrete acceptances and per-leg closure;
- separate human-attested fill ingestion and non-economic release, including later broker
  evidence without double-counting;
- the persisted startup/serving fence and stream-gap coverage proof;
- one outbound request arbiter with reserved capacity and immediate claims;
- the process-lifetime owner lock, takeover sequence, and commit/publication-unknown reload;
- executable DDL support for both fill authorities and immutable venue owners; and
- the five bounded M1 slices.

Final mechanical QA and insertion of the real SHA-256 ratification table do not change a reviewed
mechanism. Any later byte change to a hashed file requires new hashes and a focused review of the
changed claim.

## RESET-PACKET-R1 review-amendment counterexamples

Review label: **ADVERSARIAL PLANNING-SEAT REVIEW—NOT AN INDEPENDENT EXTERNAL AUDIT**.

Status: **ACCEPTED DISPOSITION, NOT YET A RECORDED R1 REVIEW PASS OR ACTIVATION**. The earlier M4c
pass does not cover these changed claims. Each row requires its named static counterexample, the
roadmap gate, presence in the listed exact proposed ADR target, refreshed hashes, and focused
adversarial planning-seat verification before ratification. A third review seat is not required
for this bounded R1 packet review.

R1 verification is static. It does not rely on schema execution, and it does not adopt the
historical M4c phrase “executable DDL support” as evidence for any changed R1 schema claim.

| Finding | Accepted disposition | Required failing counterexample and passing assertion | Gate and proposed-ADR target |
|---|---|---|---|
| `AR-02` latent second acceptance | `PA-02`: occurrence-level `broker_effects.acceptance_set_state=CLOSED` | Acceptance A is discovered and terminal, then acceptance B for the same request occurrence appears working. A terminal alone must keep `symbol_may_execute=false`; only canonical effect-row `CLOSED` plus complete coverage and closure of every leg may release it. A committed immutable claim row makes `NEVER_DISPATCHED` impossible even if effect state/timestamps are later corrupted. A late acceptance after `CLOSED` preserves the proof, appends contradiction evidence, and becomes permanently non-releasable `INVALIDATED`. | M1/M2/M3/M4 gates in `06-roadmap.md`; ownership/outbox clauses in `13-proposed-adr-current-state-kernel.md` and attempt/effect clauses in `14-proposed-adr-protection-execution.md` |
| `AR-03` legacy restart/stale rollback | `PA-03`: cross-generation fence | A legacy submit times out, the build is disabled, and a lagging report shows flat/no open order before the old request later appears. Reset stays `RECONCILIATION_ONLY` until that exact occurrence and overlapping post-disable order/execution coverage close. A reset creating-client ID must bind the new application generation and cannot collide with the old ID. Substituting a live endpoint/credential, different Paper account, or any fence field refuses broker I/O. After reset's first effect/fact, the old build performs no broker mutation; return requires both generations stopped and a separately reviewed flat/no-open-order fresh re-cutover with the same occurrence proof. | M0/M2/M3 gates in `06-roadmap.md`; process/persistence clauses in `13-proposed-adr-current-state-kernel.md` and cutover clauses in `15-proposed-adr-reset-scope.md` |
| `AR-04` correction/bust unrepresentable | `PA-04`: immutable linked `FILL`/`TRADE_CORRECT`/`TRADE_BUST` facts | Apply a fill, correction, bust, reordered duplicate, and restart. Each first occurrence replaces only its broker-authoritative root head, prior facts remain immutable, and replay produces the same ordered effective-root fold/hash chain. For `BUY 10 @ 100; SELL 5; CORRECT root to BUY 7 @ 101`, the canonical fact immediately changes raw quantity to 2, makes basis pending, and puts the positive residual in restricted `HARD_BAIL`; the high-water-checked refold restores basis 202, while naive 207 is forbidden. A racing fact invalidates only the stale basis candidate. Cancellation/reconciliation intent commits for live exposure-increasing BUYs and newly oversized SELLs; actual outcomes remain occurrence-tracked, and restricted hard-bail protection may claim only after the ordinary symbol-wide uncertainty gate passes. Under kill/`HALTED`, no SELL claims without the scoped grant; manual flatten and an open BUY parent retain their ordinary gates. | M1/M2/M3/M4 gates in `06-roadmap.md`; execution-fact clauses in `13-proposed-adr-current-state-kernel.md` and position-integrity clauses in `14-proposed-adr-protection-execution.md` |
| `AR-05` terminal legs unbound the checkpoint | `PA-05`: bounded active/unresolved legs plus immutable closure ledger | Terminalize and compact many legs, restart, then replay a stale terminal/working observation. Checkpoint size remains bounded, closure is still provable, and no closed leg or ownership can reactivate. Attempts to create a second ordinal-1 root, gap, cross-owner predecessor, or branch are refused; greatest ordinal is the sole head. | M1/M2/M3 gates in `06-roadmap.md`; checkpoint and terminal-closure clauses in `13-proposed-adr-current-state-kernel.md` |
| `AR-06` duplicate quote counted twice | `PA-06`: distinct deduplicated strictly advancing trigger occurrence | Deliver the same below-trigger quote occurrence twice. It must count once; only a later eligible occurrence with strictly advancing identity/sequence/time can satisfy the two-observation branch. | M1/M3/M5 gates in `06-roadmap.md`; trigger-evidence clauses in `14-proposed-adr-protection-execution.md` |
| `AR-07` absolute trigger displaced the fill-derived formula | `PA-06`: immutable formula/rule plus mutable armed trigger | Change fill-derived average cost with an additional authorized fill, replay/restart, and cross the old versus newly derived candidates. Exact arithmetic followed by upward valid-tick conversion reproduces each candidate; downward hard-bail rounding and activation below the approved gain fail. The armed trigger may tighten but never loosen or become an unexplained absolute. | M1/M3/M5 gates in `06-roadmap.md`; hard-bail formula/trigger clauses in `14-proposed-adr-protection-execution.md` |
| `AR-08` normal exit promoted to hard bail while waiting | `PA-06`: orthogonal `EXIT_WAITING_BUY_RESOLUTION(policy_state)` | Enter `EXIT_NORMAL`, discover an outcome-unknown BUY, wait/restart, then terminalize every known leg while the parent acceptance set remains open. The wait retains `policy_state=EXIT_NORMAL` and blocks a successor; only independent hard-bail evidence may promote it, and only exact parent `CLOSED` plus leg closure may release it. `OPEN` or quarantined `INVALIDATED` is never release authority. | M1/M3/M5 gates in `06-roadmap.md`; protection/wait clauses in `14-proposed-adr-protection-execution.md` |
| `AR-09` late BUY after `FLAT` | `PA-06`: re-enter protected `HARD_BAIL`/critical state | Establish `FLAT`, then ingest a correlated late BUY fill from prior ambiguity. The fill changes quantity exactly once and atomically exits `FLAT` into protected `HARD_BAIL`/critical handling; nonzero unprotected `FLAT` is impossible. | M1/M3/M5 gates in `06-roadmap.md`; position/protection late-fill clauses in `14-proposed-adr-protection-execution.md` |

`12-proposed-adr-set.md` is the clause-level index for these dispositions; it cannot satisfy a row
unless the exact proposed ADR text and its named counterexample both agree.
