# Fresh M2 Gate-A planning candidate

Status: **CANDIDATE — REV-0069 REQUIRED — NOT RATIFIED — NOT IMPLEMENTATION AUTHORITY**

## Decision requested at Gate B

Accept or reject this documentation-only M2 persistence/restart plan as the basis for separately
activated implementation work orders. Acceptance would not itself authorize source/test changes,
SQL/DDL, a database, runtime composition, credentials, broker calls, orders, promotion, or merge.

## Supported M2 objective

M2 may later make the already accepted pure M1/M1.5 semantics durable in one SQLite-backed reset
kernel without creating a second trading engine. The target is one modular monolith, one sequenced
writer, direct bounded current proof, one atomic fact/state/effect/claim boundary, and fail-closed
startup/cold restart. Immutable audit evidence explains decisions but never replaces live current
state.

The candidate is inside human-selected `PKG-MIN`. `PKG-HARD` follows only after PKG-MIN evidence.
`PKG-ADV` remains conditional; no advanced/model/vendor path is part of M2.

## Non-negotiable accepted authority

1. **Fact truth:** only first-occurrence canonical `FILL` and valid exact-root,
   immediate-predecessor, broker-authoritative `TRADE_CORRECT`/`TRADE_BUST` revisions change raw
   quantity or economics. Submitted, accepted, status, receipts, and projections do not.
2. **One writer and pure semantic owner:** persistence authenticates and stores existing reducer
   inputs/outcomes; it does not independently decide fills, lineage, protection, risk, closure,
   currentness, or eligibility.
3. **Three identities remain separate:** application generation, acquisition generation, and
   market-stream generation are immutable and non-substitutable.
4. **Direct current proof:** root/effect/owner-to-generation routes, current economics heads,
   controller currentness, one-LIVE status, acceptance authority, and closure heads use direct
   bounded lookup. Normal startup/hydration never folds audit history.
5. **One aggregate authority:** one exact scope has one canonical aggregate position, one bounded
   acquisition controller, at most one LIVE acquisition generation, one active normal protection
   state, and one active broker authority.
6. **Atomicity:** a transition persists old complete state or new complete state. Fact/revision,
   economics, lineage, controller/currentness, protection, venue/effect/claim, checkpoint/outcome,
   and receipt cannot split across durable commits.
7. **Acceptance authority:** an occurrence acceptance set is exactly `OPEN`, `CLOSED`, or
   `INVALIDATED`; only exact `CLOSED` proof releases. Flatness, local cancel, one terminal leg,
   not-found response, or receipt does not.
8. **Claim before I/O:** one immutable committed claim precedes an external effect. Ambiguous
   publication or broker timeout fails closed; never blind-resubmit.
9. **Profiles:** accepted ADR-024 provides one immutable `ExecutionConnectionProfile` per
   application generation and a distinct `MarketDataSourceProfile`. Every capital-relevant durable
   authority is profile-scoped. M2-M8 remains Alpaca Paper only; no profile hot swap, routing,
   failover, or second active provider.
10. **Cold market restart:** all ADR-023 C01-C12 requirements remain one indivisible sequence:
    exact stream/mode binding, fixed cursor, epoch/coordinate precedence, invalidation, warm-exact
    proof, source-authoritative post-ack fence, strict `F > cursor`, no-cursor exception,
    baseline-first delivery, buffered `<=F` exclusion, unsupported-source non-serving, split
    reducers, and terminal no-wrap exhaustion.

## Schema-neutral durable topology

This is a semantic ownership map, not DDL, table naming, or serialization approval.

| Durable authority family | Owning accepted semantics | Minimum durable obligation | Explicit refusal |
| --- | --- | --- | --- |
| Application generation and selected execution profile | ADR-022/024 | Immutable generation/profile identity and commitment; exact selected Alpaca Paper coordinates; supervisor-fence comparison coordinates remain separate where ADR-022 requires them | Mutable defaults, live profile, profile overwrite, credential or raw account material |
| Market-source profile and stream authority | ADR-023/024/R04 research | Immutable source-profile commitment, stream generation/mode, exact cursor binding, rights/entitlement/currentness evidence coordinates | Execution identity implying market authority, local clock/caller fence, raw tape as live truth |
| Controller/current checkpoint | ADR-020/021 | One bounded scope controller, one currentness head, at most one LIVE generation, compatibility commitment, aggregate checkpoint, active/unresolved keys only | Retired collection in serving checkpoint, current-symbol inference, second controller |
| Acquisition-generation registry and routes | ADR-020/021 | Immutable generation provenance, direct current economics head, direct root/effect/owner routes, bounded closure summary | Predecessor/history scan, caller-minted lineage, ownership transfer/reset |
| Canonical execution facts and revisions | Safety core/ADR-020 | Immutable fact/root/predecessor/scope/profile binding, unified current chain/head, one economic application | Status/receipt authority, overwrite, branch, cross-profile substitution |
| Effects, claims, owners, acceptance, and closures | ADR-020/022 | Claim-before-I/O, immutable concrete ownership, canonical acceptance state, one nonbranching greatest closure head | Dispatcher write authority, blind retry, flat/not-found release, branch closure |
| Protection and market cursor | ADR-021/023 | Existing authentic protection state/commitment, exact fixed market cursor, invalidation/baseline/halt/exhaustion state, one active authority | Persistence-built sealed relation, normal-policy transfer, cursor/history reconstruction |
| Decision receipt and audit evidence | Research/accepted testing model | Transactionally correlated explanation and immutable evidence coordinates | Receipt as economic/current/claim/recovery authority or live history fold |

No historical c9 SQL statement, trigger, index, provider-literal key, row name, or SQLite pragma is
adopted. Exact representation and target-build durability settings require a later human-gated
schema work order and failure-capable temporary-database evidence.

## Atomic transition contract

For one admitted typed input, the future unit of work must:

1. authenticate the exact selected application/profile/source/scope/session and direct current
   proof slice;
2. invoke the existing owning pure composite reducer inside the transaction boundary;
3. treat `REFUSED`, replay, conflict, and no-op exactly as the owning reducer specifies—never as a
   partial economic or authority write;
4. write every changed fact/head, aggregate, route, controller/currentness, protection/market edge,
   venue/effect/claim/owner/closure, checkpoint/outcome, and decision receipt atomically;
5. commit before making any effect externally eligible;
6. let only the post-commit dispatcher attempt one eligible effect; and
7. route every broker observation back through normalized authenticated input and the sequencer.

A commit-publication ambiguity, direct-index mismatch, stale currentness head, profile mismatch,
forked revision, missing acceptance coverage, or uncertain external outcome leaves the system
non-serving/reconciliation-only.

## Startup and cold-restart contract

Startup order is conceptual and must later be proved on the exact target build/filesystem:

1. acquire the single process-lifetime owner lock before database or adapter work;
2. verify immutable application/profile identity, datastore identity, schema/version commitment,
   checkpoint integrity, direct route totality, one-LIVE/controller uniqueness, current heads,
   claim/owner/closure consistency, and supervisor-fence coordinates;
3. enter `BOOTSTRAPPING`, then `RECONCILING`; never infer serving from a successful open;
4. resolve every claimed/in-flight/outcome-unknown effect through deterministic identity and
   complete query/stream coverage without blind retry;
5. classify ADR-023 warm exact only when adapter quiescence, atomic last cursor publication, and no
   possible later publication are all proved;
6. otherwise invalidate volatile market authority before adapter work, subscribe, obtain a
   source-authoritative post-ack fence covering all pre-ack emission, require strict
   `F > retained cursor` or the exact no-cursor initial exception, exclude buffered `<=F`, and
   deliver the sole fresh non-halted baseline at `F` before any later `>F` work; and
7. enter `SERVING` only after all exact gates pass. Missing capability or evidence remains
   `RECONCILIATION_ONLY`/non-serving.

No startup path scans full facts, receipts, retired generations, owners, closures, or market tape
to manufacture current authority.

## Human policy dependencies

### Non-trade financial facts

The human selected preparation of an explicit exclusion/quarantine policy rather than an economic-
fact extension. Until that later policy/ADR is accepted, fees, dividends, interest, transfers,
cash adjustments, and other non-execution financial mutations must not be represented as canonical
execution facts or silently alter trading quantity/cost basis. Encountering one remains an explicit
quarantine/decision gap, not a guessed zero-impact event.

### Numeric risk

Ameen Mujtabaa is the sole human risk-policy owner. The software and this packet select no loss,
exposure, capital, emergency, or change-control number. Before any relevant serving/promotion gate,
a versioned human policy must bind the exact numeric limits, owner, change procedure, and refusal
behavior. `UNKNOWN` never means zero or unlimited.

These dependencies do not authorize an ADR or policy body in this wave and do not block review of
the M2 structural plan; they remain explicit pre-serving/pre-promotion gates.

## Fresh post-Gate-B implementation sequence

No implementation identity is assigned until a human ratifies the exact Gate-B packet. Each future
order introduces at most one semantic/durable concept and receives its own review/authority:

1. **M2-I1 — immutable durable value/profile codec contract:** exact existing M1 values,
   ExecutionConnectionProfile/MarketDataSourceProfile known-answer encodings, no secrets, and total
   typed input/result ownership. No database.
2. **M2-I2 — schema and direct-current-proof foundation:** separately human-gated schema/DDL design
   and fresh temporary-database constraint tests for application/profile identity, checkpoint,
   controller/generation registry, direct routes, facts/heads, and acceptance/closure authority.
3. **M2-I3 — narrow SQLite repository hydration:** direct-key bounded reads/writes for existing pure
   reducer inputs/outcomes; no second in-memory trading engine and no history fold.
4. **M2-I4 — atomic composite unit of work and effect claims:** old-or-new transition,
   claim-before-I/O, post-commit outbox eligibility, ambiguity/restart refusal, and decision receipt.
5. **M2-I5 — startup, reconciliation, and ADR-023 cold recovery:** owner lock, full fence,
   direct-integrity gates, unknown-effect recovery, source-authoritative fence/baseline ordering,
   and non-serving unsupported source.
6. **M2-I6 — crash/restore/fault closeout:** failure injection at every commit/publication edge,
   independent restore, bounded startup, coverage/currentness mutants, target/stress evidence, and
   readiness handoff without promotion gain.

The first separately activated order must regenerate exact source/member/typed-route inventories
from the then-current accepted head. It may not reuse c9 application hashes or old WO-0159-0163.

## Failure-capable evidence ladder

Every item below is currently `NOT_RUN` unless identified as this packet's static verification:

| Gate | Required future evidence | Current state |
| --- | --- | --- |
| G-AUTH | Exact authority/input hashes, one-pass reconciliation, manifest grammar, ancestry, independent plan review | Static candidate evidence; independent review pending |
| G-CODEC | Independent literal known-answer profile/account/source preimages and mutations | `NOT_RUN` |
| G-SCHEMA | Fresh temporary SQLite parser/constraint/foreign-key/uniqueness/immutability negative controls under separate schema authority | `NOT_RUN` |
| G-ATOMIC | Crash at every composite write/commit/publication edge; old complete or new complete only | `NOT_RUN` |
| G-DIRECT | Direct indexed hydration/startup, no unrelated scan/history fold, one-LIVE/route/current-head mutants | `NOT_RUN` |
| G-COLD | CR-01 through CR-19, cursor-publication crashes, fence coverage/equality/delivery-order/source-capability mutants | `NOT_RUN` |
| G-EFFECT | Claim-before-I/O, timeout ambiguity, no blind retry, acceptance/closure/coverage mutants | `NOT_RUN` |
| G-RESTORE | Target filesystem/WAL/restore/fault evidence with independent restore destination | `NOT_RUN` |
| G-SOAK | At least 24-hour faulted soak plus incident/operator reconstruction on exact build/profile | `NOT_RUN` |
| G-R16 | Frozen R16 G0-G7 conjunction | `NOT_EVALUATED` |

No documentation result, local fake coverage, historical CI, or Paper-only observation may promote
any row to PASS. Evidence must be exact-build/profile/source scoped, dated, expiring where external
facts change, and owned.

## Explicit refusals

- No live trading, shorting, options, crypto, multi-account, Signal Seat, new broker, routing,
  failover, model/vendor writeback, automatic promotion, or provider selection.
- No second writer/store/engine, current-symbol lineage inference, caller-built authority,
  projection/receipt truth, history-derived serving authority, mutable profile, or profile hot swap.
- No raw provider/account secret or credential in database rows, logs, receipts, manifests, tests,
  or repository artifacts.
- No opening-inventory fact, old-build broker rollback after reset economic activity without a new
  reviewed flat recutover, or legacy/reset mixed writer.
- No parser/execution/operational claim for historical SQL; no configured database access.
- No conversion of open findings, `NOT_RUN`, `NOT_EVALUATED`, unknown cost, or source-expiry gaps
  into completion language.

## Gate-B acceptance boundary

Gate B may ratify only the exact candidate files and external manifest after `REV-0069` returns
`ACCEPT`, P0=0/P1=0. A later human action must separately activate the first implementation order
and any human-gated schema/database test surface. Until then:

`NOT_READY / HOLD_ALL_PROMOTION / M2 NOT IMPLEMENTED / NO BROKER AUTHORITY`
