---
type: Work Order
title: "Reset kernel B: venue ownership and recovery lifecycle"
status: CLOSED
work_order_id: WO-0146
wave: RESET-M1B
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Codex implementation seat
created: 2026-08-01
branch: codex/arch-reset-2026-07-r1
base_sha: dfb8ed30ebed788f1158d7f8be49b44d505c355b
staged_source: work/queue/ARCH-RESET-2026-07/06-roadmap.md#M1--Pure-reference-kernel
predecessor: WO-0145
activation_ci: "GitHub Actions run 30706138534 (#677): Python 3.11 job 91385483099 SUCCESS; Python 3.12 job 91385483131 SUCCESS"
---

# WO-0146 — Reset kernel B: venue ownership and recovery lifecycle

`[FABLE • FULL • verification: DIRECT + independent review • task: pure venue-recovery kernel]`

## Activation and authority

Ameen explicitly approved all four proposed next actions on 2026-08-01: activate RESET-WO-02,
produce a read-only branch/worktree retirement manifest, land the five M1 slices as one independently
reviewed non-squashed master milestone, and begin only manifest-approved retirement after exact
merged-master CI. This activates only RESET-WO-02 as canonical `WO-0146`; later M1 slices remain
sequentially gated. The accepted ADRs, preserved safety core, and staged roadmap remain controlling.

The exact predecessor closeout `dfb8ed30ebed788f1158d7f8be49b44d505c355b` passed unchanged
Python 3.11/3.12 CI and independent review with no unresolved P0/P1. No credentials are available or
needed. Force `BROKER_ADAPTER=mock`; do not discover or use credentials, call Alpaca Paper, perform
broker/network I/O, execute SQL/DDL, initialize a database, alter persistence, wire runtime code,
open or merge a PR, or delete/clean any branch, worktree, or artifact during this WO. Existing
database-bearing suites may run only under the prior disposable-test-database authorization; their
legacy fixtures are evidence, not a dependency of this pure slice. The prohibited R1 DDL result is
inadmissible and supplies no design or acceptance evidence.

## Fable gate

```yaml
fable_gate:
  goal: "Build the deterministic venue-effect, one-to-many ownership, closure, ambiguity, and ADR-012 recovery semantic center without I/O or persistence."
  assumptions:
    - claim: "ADR-020/021, ADR-012, and M1 item 2 uniquely determine the pure venue-recovery boundary."
      status: VERIFIED
      evidence: "Clause comparison and AR-02/AR-05 counterexamples agree; adapter completeness and persistence remain later typed inputs/gates."
    - claim: "Human-attested intervals can share the canonical fill fold without a second arithmetic lane."
      status: VERIFIED
      evidence: "WO-0145 already carries authority on root heads; WO-0146 admits it only after exact leg/capacity/cumulative/evidence/long-only checks."
    - claim: "Standing human authority covers this slice and in-scope remediation without activating later slices."
      status: VERIFIED
      evidence: "Ameen approved options 1–4; this work order records their sequential gates and exact exclusions."
  approach: "Commit this docs-only gate, write RED examples/state machines and mutation pins, implement one pure atomic transition seam across venue and recovery state, refactor, then independently review."
  alternatives_considered:
    - "Reuse Spine v2 recovery/store code — rejected because it remains read-only evidence and mixes persistence/runtime concerns."
    - "Infer closure from known-leg terminality or not-found — rejected because AR-02 proves latent acceptances."
    - "Apply later broker evidence unconditionally after attestation — rejected because it can double-count one interval."
  out_of_scope:
    - "SQLite, schema, migration, DDL/SQL, stores, event repositories, adapters, SDKs, network, broker, UI/API, clock, or runtime wiring"
    - "Trading modes, kill/manual controls, request budgets, complete symbol_may_execute, and final-claim authority (RESET-WO-03)"
    - "Protection/trailing (RESET-WO-04), acquisition/cross-side integration (RESET-WO-05), RTH/native handoff, and predictive liquidity"
    - "External cutover/credential/origin/rollback proof beyond generation/client/owner identity rejection"
    - "PR, merge, branch/worktree/artifact deletion, or cleanup"
  done_when:
    - behavior: "Named examples and generated histories prove effects versus attempts, AR-02 multi-acceptance/closure, AR-05 compaction/closure chains, restart, and status precedence."
      test: "Focused venue ownership and stateful suites"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_venue_ownership.py tests/execution_core/test_venue_stateful.py"
    - behavior: "ADR-012 human fill/release and matching/mismatching later broker evidence are exact, idempotent, capacity-safe, long-only, and non-global."
      test: "Focused recovery suite"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_venue_recovery.py"
    - behavior: "Every named safety mutant fails live and the restored tree passes focused/static/full gates on Python 3.11/3.12."
      test: "Mutation ledger, import boundary, repository gates, unchanged CI"
      command: "Run documented mutants; Ruff, mypy, import contracts, AI-OS, R2/full coverage, then exact-head dual-version CI."
    - behavior: "Independent exact-head review reports no unresolved P0/P1."
      test: "Reviewer-owned M1B packet"
      command: "Blind spec-first review of exact diff, tests, mutation evidence, and deferred claims."
  blast_radius: "Only the pure app.execution_core package, isolated tests, and WO/PKL closeout records; no incumbent runtime or schema consumer."
  rollback: "Revert only WO-0146 commits while preserving WO-0145, the retirement manifest, all worktrees, and preserved artifacts."
```

## Split-review stop and bounded re-gate (2026-08-01)

The first-pass green result is superseded. Because `venue.py` crossed the roadmap's approximate
800-line split-review threshold, hostile Saboteur, New-Hire, and Safety/Security passes re-derived
the slice and reproduced four P0 classes plus multiple P1s. Commit `865ebc2` freezes 20 failing
counterexamples; its tests pass Ruff/diff checks but are intentionally RED. Work stopped before any
WO-03 activation, closeout, PR, merge, runtime, database, broker, or retirement action.

The P0s were: unreserved matching broker evidence could later apply a second delta; a forged public
checkpoint could omit claim/provenance and admit human authority; a released leg could accept later
human economics; and an `INVALIDATED` parent did not permanently refuse release.

The user's standing authorization for in-flight findings and options 1-4 re-gates only bounded
WO-0146 remediation; it does not waive the stop, broaden paths, activate WO-03, or authorize any
runtime/schema/broker/credential/merge/deletion action. Remediation must reserve corroborating facts
at zero delta; deeply validate claim/scope/owner/closure/input/coverage checkpoint coherence; require
an active `NEEDS_REVIEW` leg for human fills; block invalidated/released paths; remove forged operator
status ingestion; enforce release cumulative/capacity/terminal parity; finalize only after all legs
and the parent close; preserve replay/conflict integrity and occurrence uniqueness; use one pending
absence representation and valid closure successors; and bind acceptance proof to exact scope,
occurrence, claim, and immutable evidence. Adapter certification remains a later typed input.

No prior green output is admissible. Fresh focused/static/mutation evidence and a new independent
exact-head `REV-0048` result are mandatory.

## Independent checkpoint re-review and second bounded re-gate (2026-08-01)

The remediation green following the split review is also superseded. Three fresh independent
reviewers attacked checkpoint construction, execution binding/restart, and revision/closure
semantics. They reproduced additional P0/P1 failures: late acceptance after closed rejected or
never-dispatched outcomes was refused instead of invalidating; retained operator authority could be
rewritten; checkpoint evolution helpers allowed reconciliation/history stripping; human authority
could survive removal or reordering of its review gates; cross-symbol account-registry advancement
stranded otherwise valid snapshots; human/corroborated truth could not be safely hydrated; sibling
fills bypassed effect-wide capacity; and revision replay, post-closure conflict, bust/status, and
non-tail mapping cases could wedge or falsely preserve finality. The reviewers added failure-first
contracts in the three dedicated hardening suites listed below. No reviewer changed production.

Ameen's standing authorization for all in-flight findings re-gates these directly necessary
WO-0146 corrections only. It does not activate WO-0147, authorize runtime/schema/database/broker
work, or authorize merge, deletion, or cleanup. The accepted remediation boundary is:

- keep public broker hydration strict while adding venue-provenance hydration for exact retained
  human roots and zero-economic corroborations;
- admit only cryptographically monotonic account-registry projection, record every catch-up outcome,
  and quarantine independently advanced owned-symbol truth until attribution is resolved;
- commit indexed prefix and broker-root-count proofs without materializing retained history;
- make the checkpoint object read-only by moving all construction capability to module-private
  verified functions;
- replay control-plane input order so first human authority exists only after the exact effect and
  leg both reached `NEEDS_REVIEW` and before release;
- bind every coverage, corroboration, revision head/history, reconciliation, closure, and registry
  outcome to its exact source input; semantic aliases must point backward to a retained direct
  source and can never replace it;
- require effect-wide capacity, exact revision lineage/mapping, current closure parity, clean
  execution bindings, and no unresolved evidence for `OPERATOR_RECONCILED`; later contradictions
  demote the effect to `NEEDS_REVIEW` rather than leaving a falsely serving final state.

All earlier green claims remain inadmissible. Fresh focused/stateful/static/mutation/full-suite and
exact-head independent evidence are required after the final production freeze.

## Fresh implementation checkpoint evidence (2026-08-01, pre-review)

The production source was restored after every mutation and then frozen for this checkpoint.
Current-source evidence:

- deterministic execution-core contract: 318 passed across fill, import-boundary, ownership,
  recovery, binding/restart, checkpoint, and provenance suites;
- fill/position state machine: 7 passed; venue state machine: 2 passed;
- Ruff: all execution-core source/tests passed; mypy: 7 source files passed; `git diff --check`:
  passed;
- five live safety mutants were killed by their focused pins: removing unresolved registry release
  blocking; removing the ordered effect review gate; allowing an alias to replace its direct
  provenance source; removing effect-wide sibling overfill latching; and allowing unresolved
  execution-integrity bits in an operator-final checkpoint. The restored source passed all six
  parametrized/targeted mutation pins.

These are implementation-seat results, not acceptance. No SQL/DDL, database engine or fixture,
broker adapter, Alpaca activity, credential, network, runtime wiring, merge, deletion, or cleanup
was used. Full repository/R2 evidence and independent exact-head `REV-0048` remain mandatory.

## REV-0048 blocking verdict and third bounded re-gate (2026-08-01)

The canonical-Ruff implementation target `ba9e1268e4645ec36f620f14d361f709916aa690`
reproduced all 327 pure cases and focused static gates, but reviewer-owned `REV-0048/result.md`
returned `BLOCK`. That result is preserved unchanged at commit `007c757`. Its fresh probes found:

- **P0:** every rebuilt serving checkpoint rescanned and recopied retained terminal-closure history;
  broker-economic predecessor validation could make the path worse than linear. Direct inspection
  also found the same-root append-only `input_records` ledger reconstructed, partitioned, deduped,
  and copied on ordinary transitions. This violates ADR-020's rule that no live transition performs
  work proportional to audit-history length.
- **P1:** `_BOOK_CONSTRUCTION_TOKEN` was an importable module global. An ordinary importer could use
  it with the dataclass initializer or `dataclasses.replace` to mint a standalone checkpoint carrying
  false human coverage while the paired execution snapshot still held zero quantity. A later bound
  reducer failed closed, but checkpoint-only consumers had already received false authority.

A separately authorized full repository baseline on that blocked object forced
`BROKER_ADAPTER=mock`. R2 passed all 61 cases. The full behavior suite passed 4,944 tests with 11
skips and one expected failure, but the unchanged 93% combined line/branch coverage gate failed at
92.13%. Its
coverage artifact is preserved as `.coverage_wo0146_full_authorized_1`, SHA-256
`a2dd3f14eadcc24af643d503acb214076cafe1e88cf8bd569d5e9a4313310256`. Existing fixtures used only
authorized disposable test SQLite; no persistent database, broker, credential, Alpaca activity,
network, runtime wiring, merge, deletion, or cleanup occurred. The behavior pass is diagnostic and
does not accept the blocked object or satisfy the coverage gate.

Ameen's standing authorization for all in-flight findings and refinements re-gates only this bounded
WO-0146 remediation. It does not activate WO-0147 or authorize runtime, schema, broker, credential,
merge, deletion, or cleanup work. The accepted correction boundary is:

- replace serving-checkpoint closure and input audit tuples with persistent indexed proof whose
  append, identity lookup, current-head/predecessor check, and direct-source lookup are independent
  of retained audit-history length; materialization remains an explicit slow audit operation;
- validate only the newly appended immutable audit fact plus bounded current state on live
  transitions, while a separate verified hydration/audit seam may perform a full fold;
- remove importable construction authority, direct dataclass initialization, and `replace` minting;
  every externally usable reconstruction must authenticate exact human/corroborated roots against
  its paired `ExecutionSnapshot` before yielding a checkpoint;
- add RED public-boundary, scaling/tripwire, and mutation pins for both findings; and
- close the unchanged 93% repository coverage floor only with real failure-capable tests of current
  behavior. Do not lower the floor, add exclusions/skips, or change behavior solely for coverage.

All earlier green and the blocked full-suite baseline remain inadmissible as final acceptance.
Fresh focused/stateful/static/mutation/R2/full-coverage evidence plus a new reviewer-owned exact-head
remediation result with no unresolved P0/P1 are mandatory after the next production freeze.

## Final-freeze review stop and fourth bounded re-gate (2026-08-01)

The preliminary final-freeze review invalidated source hash
`1b5e53c6b6c582d4af989d2900d940db044a9d69f9662c01c38d610c89dccd75` after reproducing two
additional CatchUp P0s. First, an unresolved independently advanced MSFT registry could set the new
account-wide reconciliation gate while leaving an already finalized AAPL effect effectively
`OPERATOR_RECONCILED`; the source-symbol epoch did not revoke sibling authority already issued in
the same account. Second, a healthy same-registry cross-symbol target projection persisted its
`CatchUpExecutionRegistry` input without a direct immutable outcome, so the live `APPLIED`
checkpoint failed verified audit hydration. The same pass also found and the implementation seat
already closed a related zero-economic provenance path by refusing to evolve registry-only progress
whose position/root/integrity binding had not changed; that repair remains subject to this new
freeze and review.

The two new P0s trigger this work order's mandatory stop. Work paused before any formal acceptance,
commit, push, CI, WO-0147 activation, runtime/schema/database/broker activity, merge, deletion, or
cleanup. Incomplete account-authority-epoch scaffolding had begun when the reviewer reiterated the
two-P0 stop; it is unverified partial work and carries no green or completion claim.

Ameen's explicit standing authorization for all in-flight findings and refinements, together with
the approved options 1-4, re-gates only the directly necessary WO-0146 repair:

- add one constant-work account authority epoch so an unresolved account reconciliation lazily
  demotes every previously finalized effect without scanning symbols/effects, while preserving the
  existing effect-local closure demotion and scope-specific execution epochs;
- retain a bounded immutable direct outcome for same-registry target projection, bind it to the
  declared target/source registry and exact resulting target binding, classify exact replay from
  the indexed outcome, and include it in verified hydration/direct-provenance checks; and
- add RED cross-symbol already-finalized, healthy projection restart, changed replay, mutation, and
  audit-parity pins, then repeat every focused/static/stateful/full-coverage and independent review
  gate on a new exact freeze.

This re-gate does not activate WO-0147, authorize persistence/schema/DDL/SQL, broker or credential
use, runtime wiring, PR/merge, branch/worktree retirement, deletion, cleanup, or rely on the
inadmissible R1 DDL execution. All evidence from the invalidated freeze is diagnostic only.

## Mixed-account proof review stop and fifth bounded re-gate (2026-08-01)

The fourth-gate production freeze at `venue.py` SHA-256
`0e0df3b452006d881fb1e3bf1c3c14ae611870d61827fe06e979ecbd5cb74fda` is invalidated. A fresh
read-only reviewer reproduced two additional P0s in the same execution-registry outcome proof root.
First, a healthy target-only projection from a canonical mixed-symbol account registry was accepted
live but could fail audit hydration: live validation correctly treated the account high-water to
source high-water suffix as empty, while hydration incorrectly required the target's entire older
lag interval to belong to the source symbol. Second, one mutable record shape represented both an
unresolved source advance and a resolved target projection; hydration inferred the security-relevant
kind from an unauthenticated boolean plus internally compared commitments. Replacing an unresolved
record's fields could therefore relabel it as resolved and consistently clear the account-wide
reconciliation count and authority epoch.

The same pass found one P1 in the target identity boundary: `CatchUpExecutionRegistry` accepted a
`PositionScope` subclass through generic `isinstance` validation even though replay identity relied
on equality. An overloaded subclass could therefore compare equal to more than one runtime target.

These two P0s trigger the mandatory stop. The repository-wide coverage run against the invalidated
freeze was terminated as diagnostic-only before completion. No production edit, acceptance,
commit, push, CI, WO-0147 activation, runtime/schema/database/broker activity, merge, retirement,
deletion, or cleanup followed that freeze.

Ameen's explicit standing authorization for in-flight findings and refinements re-gates only the
directly necessary WO-0146 correction:

- separate unresolved source-advance and resolved target-projection outcomes with an exact typed
  discriminator that hydration does not infer from caller-controlled equality or a boolean;
- bind each outcome to its retained `CatchUpExecutionRegistry` source, target scope, exact canonical
  account prefix/result, and the appropriate exact source or target execution binding;
- require the exact target checkpoint and `PositionScope` type at construction and replay;
- apply the one-symbol suffix proof only to genuinely new account history, never to a target's
  already-canonical mixed-symbol lag interval; and
- add RED three-symbol mixed-history restart and forged kind/commitment/attribution hydration pins,
  then repeat all focused, static, stateful, repository-coverage, mutation, and independent-review
  gates on a new exact freeze.

This fifth re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. All
evidence from the invalidated freeze remains diagnostic only.

## Coordinated recovery-rewrite stop and sixth bounded re-gate (2026-08-01)

The fifth-gate source freeze at `venue.py` SHA-256
`3b86ca2e3b2c578036eea45af47de36cb8963a75213eb74c0e4dd9a771f86680` and `recovery.py`
SHA-256 `656a75d298058f7deb1cb85d570df4133d095f9b8e2a3130d84f14939e9f30b2` is invalidated.
Its 403-case pure suite, 61-case R2 oracle, static checks, and six import contracts passed, but those
results are diagnostic only. The repository-wide branch-coverage run was stopped before completion.

A fresh independent pass reproduced one P0 that the same-symbol relabel pin did not cover. The new
concrete outcome types prevented rewriting only the outcome. Audit hydration still allowed both the
retained `CatchUpExecutionRegistry` command and outcome to be substituted together. For a
cross-symbol unresolved source advance whose target economics stayed unchanged, replacing the
command's claimed prior account point and source binding with the result, then supplying a matching
resolved projection outcome, passed all self-consistency checks and rebuilt the account unresolved
count and authority epoch as zero. The command commitment authenticated only the replacement
command; it did not chain that command to the actual preceding book registry and binding heads.

Ameen's explicit standing authorization for in-flight findings and refinements re-gates only the
directly necessary WO-0146 correction:

- add a predecessor-linked, domain-separated account-registry transition chain and exact per-scope
  binding-head chain whose retained prior commitments are authenticated in input order;
- require every CatchUp command precondition to equal the then-current chained account and source
  heads, and require each outcome to produce the uniquely chained result heads;
- anchor the final reconstructed account and per-scope heads to the book's exact indexed current
  state before deriving unresolved counts or authority epochs; and
- add a RED cross-symbol coordinated command-plus-outcome rewrite pin, chain omission/reordering and
  predecessor mutation pins, then repeat all focused, stateful, static, mutation, R2, repository
  coverage, and independent-review gates on a new exact freeze.

This sixth re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. No
evidence from the invalidated fifth freeze is admissible for acceptance.

## Self-anchored transition-chain stop and seventh bounded re-gate (2026-08-01)

The sixth-gate source freeze at `venue.py` SHA-256
`24eb986e36d902d64821142c123effe80780e6663dcad4572f9d78178c204b1e` and `recovery.py`
SHA-256 `656a75d298058f7deb1cb85d570df4133d095f9b8e2a3130d84f14939e9f30b2` is invalidated.
Its 28-case binding-recovery and 179-case focused recovery/hardening suites, Ruff, mypy, and diff
checks passed, but those results are diagnostic only. The full pure execution-core run was stopped
after the P0 was established.

Three independent passes converged on one P0: the predecessor-linked transition proof remained
self-anchored inside the mutable hydration book. It authenticated the order and content of the
retained command/outcome pair only against other retained fields. A coordinated rewrite could
therefore replace the command, outcome, proof nodes, and stored head together; a coordinated
omission could remove the entire tuple; and a coordinated reorder could rebuild a syntactically
valid chain. Because replay skipped unowned broker facts and did not carry the actual account and
per-scope semantic heads through every transition to an externally supplied final state, each
coordinated mutation could erase or relabel an unresolved source advance and clear the account-wide
authority revocation.

Ameen's explicit standing authorization for in-flight findings and refinements re-gates only the
directly necessary WO-0146 correction:

- derive recovery completeness from the externally supplied exact execution snapshot rather than
  treating a mutually consistent set of retained book fields as its own authority;
- carry a bounded account-wide reconciliation state through exact snapshot binding and every
  cross-symbol registry projection, and close replay's final account state to that external value;
- require every externally observed canonical registry advance not attributable to a direct venue
  command to have one exact unresolved source-advance origin, so coordinated record omission is
  independently detectable; and
- add RED fully coordinated rewrite, omission, and reorder pins that rebuild all internal proof
  fields, then repeat every focused, stateful, static, mutation, R2, repository-coverage, and
  independent-review gate on a new exact freeze.

This seventh re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. No
evidence from the invalidated sixth freeze is admissible for acceptance.

## Inner-component subclass stop and eighth bounded re-gate (2026-08-01)

The seventh-gate source freeze at `venue.py` SHA-256
`2df56baaaaad51692b3804bbf575f0fe360a959f2ae136b635396fdd9f76c413`, `position.py` SHA-256
`6a992d98ef78fa916c4c6d19c5b8a00749807ff3c2bc77ae9636bc594467b160`, and `recovery.py`
SHA-256 `20a58133e9fdbae9ddb7606664674397947adaea0e13b8033ace1f8d79ba2bce` is invalidated. Its 406-case
pure execution-core suite, Ruff, mypy, import contracts, diff check, and 61-case R2 oracle passed;
all are diagnostic only. The repository-wide branch-coverage run was terminated immediately when
the P0 below was reproduced, and its partial coverage file remains preserved.

A fresh constructor-boundary pass found one P0 beneath the exact outer `ExecutionSnapshot` check.
`ExecutionSnapshot.bind_verified` and the common component binder admitted `PositionState`,
`RootHeadIndex`, and `SeenFactIndex` subclasses. Their `type(self)` constructors preserved the
subclass inside an exact outer snapshot. An overridden registry prefix/suffix/count/commitment
method could therefore behave safely during binding and differently during CatchUp validation,
forging monotonicity or source-scope attribution while satisfying the outer exact-type check.

Ameen's standing authorization for in-flight findings and refinements re-gates only the directly
necessary WO-0146 correction:

- require exact component types at every public snapshot construction and canonical fact-reducer
  entry, not merely an exact outer snapshot;
- prevent internal rebinding, projection, and venue CatchUp from preserving or accepting component
  subclasses or overloaded identity/registry behavior;
- add RED delayed-behavior `SeenFactIndex`, `RootHeadIndex`, and `PositionState` subclass pins for
  public binding, direct fact application, exact snapshot construction, recovery binding, and
  CatchUp source/target inputs; and
- repeat every focused, stateful, static, mutation, R2, repository-coverage, and independent-review
  gate on a new exact freeze.

This eighth re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. No
evidence from the invalidated seventh freeze is admissible for acceptance.

## Fresh-book bootstrap stop and ninth bounded re-gate (2026-08-01)

The eighth-gate source freeze at `venue.py` SHA-256
`80f84e166c9bda6d1cce1122098ec8630aad7b4d08e83ba315ad2e4e2acde967` and `position.py`
SHA-256 `0e87b8889ed1573491dbf6090d6b51069d2635b9fa8e11d1900e3f2faea3a1d0` is invalidated. Its
418-case pure execution-core suite, Ruff, mypy, diff check, and 61-case R2 oracle passed, but all
results are diagnostic only. The repository-wide branch-coverage run was terminated immediately
after the P0 below was reproduced; no new coverage artifact had been emitted at termination, and
the previously preserved coverage artifacts remain unchanged. The terminated run is inadmissible.

A fresh restart-boundary pass reproduced one P0 through pure public APIs. After an independent
same-symbol registry advance, the legitimate pre-CatchUp execution snapshot still carried the
genesis reconciliation cursor and no account restriction. Although CatchUp correctly produced a
new restricted snapshot, the retained pre-CatchUp snapshot could be paired with a new
same-generation `VenueRecoveryBook.empty(...)`. Because genesis is a valid prefix of an empty
book, the first `RequestedEffect` registered successfully and erased the later unresolved account
restriction and reconciliation history.

Ameen's standing authorization for in-flight findings and refinements re-gates only the directly
necessary WO-0146 correction:

- admit the first effect in a brand-new venue book only against the unique exact flat execution
  genesis; any nonempty registry, economics, integrity restriction, or advanced cursor requires a
  separately authenticated hydration/bootstrap authority outside this constructor;
- refuse both a restricted post-CatchUp snapshot and a retained nonempty genesis-cursor snapshot
  when either is paired with a fresh same-generation book;
- preserve the declared deferred boundary: later persistence/cutover work must independently pin
  the latest trusted book/snapshot pair and may not treat a newly minted empty book as authority;
  and
- repeat every focused, stateful, static, mutation, R2, repository-coverage, and independent-review
  gate on a new exact freeze.

This ninth re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. No
evidence from the invalidated eighth freeze is admissible for acceptance.

## Validation-order stop and tenth bounded re-gate (2026-08-01)

The ninth-gate source freeze at `venue.py` SHA-256
`d8c2f1980d601e7d7146d36272e27799ee546c15669d4354cfb9106ab4d2922b` and `position.py`
SHA-256 `0e87b8889ed1573491dbf6090d6b51069d2635b9fa8e11d1900e3f2faea3a1d0` is invalidated. Its
419-case pure execution-core suite, Ruff, mypy, import/scope/diff checks, 61-case R2 oracle, and one
independent restart/cursor ACCEPT are diagnostic only. The repository coverage run was terminated
before completion when a separate component-boundary reviewer returned the two P1s below; no new
coverage artifact had been emitted.

The exact component types were enforced at public venue entry, but two secondary seams performed
work in the wrong order. Internal account-registry projection called an overridable source prefix
proof before its own exact component validation. Venue recovery hydration checked exact outer
component types but compared an embedded `PositionScope` subclass before the common exact-scope
guard. The same review identified `VenueExecutionCheckpoint.from_execution` as an unverified
parallel seam that read inner registry properties after checking only the outer snapshot.

Ameen's standing authorization for in-flight findings and refinements re-gates only the directly
necessary WO-0146 correction:

- run the common exact component/scope guard before any target or source property/proof access in
  internal registry projection;
- reject non-exact position and root-index scopes before recovery hydration performs scope binding,
equality, replay, or registry work;
- apply the same early component guard in the public checkpoint factory and explicit audit
  hydration factory; and
- add RED delayed prefix-proof, delayed scope-equality, and delayed checkpoint-property pins, then
  repeat every focused, stateful, static, mutation, R2, repository-coverage, and independent-review
  gate on a new exact freeze.

This tenth re-gate does not activate WO-0147 or authorize persistence/schema/DDL/SQL, broker or
credential use, runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup. No
evidence from the invalidated ninth freeze is admissible for acceptance.

## Coverage-discovery stop and eleventh bounded re-gate (2026-08-01)

The tenth-gate source freeze and all evidence derived from it are invalidated. Its 4,998-passed,
11-skipped, one-xfailed behavioral repository run is diagnostic only because the unchanged 93%
coverage gate failed at 91.34%. The subsequent coverage-remediation pass was required to add
failure-capable tests without lowering or excluding the gate; it exposed two new defects before a
new acceptance freeze could be declared.

First, `HumanCoverage` accepted a partially populated broker-corroboration tuple when
`broker_corroborated` was false. Audit hydration later treated any retained `broker_fact` as
attributed even when its matching evidence digest and source input were absent. That could suppress
the required unowned-observation external-origin rejection without exact corroboration provenance.
This is a P0 audit-provenance bypass. Second, `_audit_hydrate_book` inspected
`attribution_resolved` on retained execution-reconciliation entries before enforcing their exact
outcome types. The malformed case failed closed, but an untrusted property could run before the
declared type boundary; this is a P1 validation-order defect.

Ameen's standing authorization for in-flight WO-0146 findings and refinements re-gates only the
directly necessary correction:

- require broker corroboration fields to be an all-or-none tuple whose presence exactly matches
  `broker_corroborated`;
- reject non-exact execution-reconciliation entries before audit hydration reads any property;
- retain the RED partial-corroboration and malformed-entry pins, plus the broader failure-capable
  coverage matrices that discovered them; and
- repeat every focused, stateful, static, mutation, R2, repository-coverage, and independent-review
  gate on a new exact freeze.

No tenth-gate coverage union, timed-out coverage run, or pre-fix independent review is admissible
for acceptance. This eleventh re-gate does not activate WO-0147 or authorize persistence,
schema/DDL/SQL, broker or credential use, runtime wiring, PR/merge, branch/worktree retirement,
deletion, or cleanup.

## Exact-subclass review stop and twelfth bounded re-gate (2026-08-01)

Implementation checkpoint `320afbb` and its pre-checkpoint full-suite artifact
`.coverage_wo0146_full_authorized_12` are invalidated for acceptance. The behavioral run remains
diagnostic evidence that 5,067 tests passed with 11 skips and one expected failure at 93.018072%
coverage, but two independent final-review probes found exact-type gaps after that run.

First, `VenueRecoveryBook.empty()` and audit hydration accepted a `VenueScope` subclass. A delayed
attribute override could make a retained book report a different generation/account scope after
effects and execution bindings were established. Second, the canonical broker reducer, retained
`SeenFact`, and revision/coverage evidence records accepted subclasses of broker fill, correction,
or bust facts. Those are capital/provenance inputs whose computed root and economics must not be
overridable after base-dataclass validation. Both are P1 exact identity-boundary violations; no
quantity defect was relied upon or accepted.

Ameen's standing authorization for in-flight WO-0146 findings and refinements re-gates only the
directly necessary correction:

- require the exact `VenueScope` type at empty-book construction and audit validation before any
  scope property is retained or read;
- require exact canonical broker fact types at the public position reducer, retained first-fact
  observation, canonical commitment, revision evidence/reconciliation, and broker coverage head;
- retain six failure-first cases covering all three broker fact kinds, both revision record paths,
  coverage heads, initial scope construction, and audit hydration; and
- repeat every focused, stateful, static, mutation, R2, repository-coverage, and independent-review
  gate on the new exact freeze.

The six cases failed on `320afbb` with `DID NOT RAISE TypeError` and passed after exact-type
enforcement. Ruff and mypy pass on the corrected source. Five live semantic mutants were then
exercised from exact checkpoint `9ce0f44`: unresolved registry truth no longer blocking release;
the ordered effect review gate removed; semantic aliases allowed to replace direct provenance;
effect-wide sibling overfill latching removed; and operator-final validation allowed unresolved
execution-integrity bits. The alias attack required a coordinated removal of both independent
guards; removing either one alone survived safely because the other still rejected the forged
checkpoint. The coordinated property mutant failed its pin, all other mutants failed their focused
pins, and the restored six-case pin set passed. Restored SHA-256 values were
`684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c` for `recovery.py` and
`0772dc92f3c6714a6d353a83ac931a016ca22f15cdbaec5e9dfd58814a942141` for `venue.py`; the tracked
tree was clean after every restore. No earlier full-suite, coverage, or review result satisfies this
twelfth gate. It does not activate WO-0147 or authorize persistence,
schema/DDL/SQL, broker or credential use, runtime wiring, PR/merge, branch/worktree retirement,
deletion, or cleanup.

### Twelfth-gate final implementation evidence (pre-independent-review)

Exact production/test checkpoint `9ce0f44` passed 497/497 execution-core cases, 61/61 R2 cases,
Ruff check and format, mypy over all seven execution-core source files, all six Import Linter
contracts, exact scope, and diff checks. The restored five-mutant/six-pin set passed as recorded
above.

With `BROKER_ADAPTER=mock`, the authoritative repository run collected 5,085 tests and completed in
1,158 seconds: 5,073 passed, 11 skipped, and one expected failure. The unchanged 93% combined
line/branch gate passed at exactly `93.01344791915334%`: 17,366 covered lines of 18,322 statements
and 6,012 covered branches of 6,812. Preserved artifact
`.coverage_wo0146_full_authorized_13` is 1,757,184 bytes with SHA-256
`fdf57e561de4d37b6ccb339778791f2402ee333c4e3f17d22e170afbf5bce3f6`; its JSON report is
1,724,663 bytes with SHA-256
`ad7045af350a3e698a7785c4563027e5674b5e504e39b196b7342f4ea56e3c26`.

Existing full-suite fixtures used only their authorized disposable test SQLite databases and
test-only SQL/DDL. No credential, Alpaca Paper activity, broker/network call, persistent application
database, runtime wiring, PR/merge, deletion, or cleanup occurred. The prohibited R1 DDL incident
and its result were not cited, reused, or relied upon. These are implementation-seat results; an
independent exact-head addendum and dual-version CI remain mandatory before closeout.

## Nested-value P0 stop and thirteenth bounded re-gate (2026-08-01)

Reviewer-owned `REV-0048/result-addendum-01.md` returned `BLOCK` at exact checkpoint `9ce0f44` and
is preserved unchanged with SHA-256
`f7cff72992ab831b8be2839d3741c6a02cd1ff9a5a32b0ae32f6124a097a012a`. It confirmed the prior
`VenueScope` and outer broker-fact subclass P1s closed, then reproduced a deeper P0. An exact outer
`BrokerFillFact` could retain a subclassed `Quantity` that validated as one value and later applied
another, or a subclassed `ExecutionScope` that validated as `BUY` and later applied as `SELL`.
Those pure probes produced real altered raw quantity/direction. Exact outer-type checks therefore
did not yet prove immutable capital or provenance inputs.

Checkpoint `9ce0f44`, `.coverage_wo0146_full_authorized_13`, its 5,073-pass/93.013448% result, and
the in-progress exact-head CI runs are diagnostic only and inadmissible for acceptance. Ameen's
standing in-flight-remediation authority re-gates only the directly necessary correction:

- make the common execution-fact component guard exact before reading key, scope, identity,
  quantity, or price properties;
- make compound execution/root/venue identities reject subclassed components;
- recursively require exact price components at canonical fact and position-cache boundaries, and
  require exact basis objects and rational payloads wherever cached basis may be retained;
- apply the same exact nested-component rule to venue command/state value validation; and
- retain delayed quantity, execution-scope, account-identity, price-component, and venue-scope
  failure-first pins, then repeat every focused, stateful, static, mutation, R2,
  repository-coverage, independent-review, and dual-version CI gate.

All five new cases failed on `9ce0f44` with `DID NOT RAISE TypeError` and passed after the initial
nested fact boundary was sealed. A preliminary 502-case execution-core run and its static checks
were then invalidated by the retained-state P0 below; they are diagnostic only. No prior full-suite,
coverage, review, or CI result satisfies this thirteenth gate.

## Retained-state P0 stop and fourteenth bounded re-gate (2026-08-01)

A separate read-only implementation-seat adversarial pass found that audit hydration still accepted
a `BrokerEffect` subclass. It could validate capacity four, later report capacity 99 without changing
the stored commitment, and admit quantity five. The adjacent retained-owner seam was also P0: an
exact `VenueIdentityOwner` could retain a subclassed `VenueEffectScope`, validate as `BUY`, later
report `SELL`, and cause canonical execution to apply the opposite signed delta. Work stopped again;
the preliminary thirteenth-gate result was not accepted.

The same bounded sweep found P1 variants in position basis/price caches, dispatch claims, shared
snapshot bindings, execution bindings, and passive retained input/attempt/closure values. Several
verifiers also read equality, hash, or value properties before checking exact type. The directly
necessary correction now:

- exact-checks canonical fact, identity, price, basis, position-cache, shared-binding, and retained
  venue-state components before any overridable property is read;
- validates exact passive-state shapes both on normal construction where compatible and again at
  hydration/storage boundaries, so deserialization cannot bypass constructor checks;
- moves input-record and owner/claim/effect/binding validation ahead of uniqueness, equality,
  indexing, commitment, or economic reads; and
- keeps the global `values.py` module unchanged and remains within the listed execution-core paths.

Eight new failure-first test functions reproduced the retained-effect, cached-basis/price/fold,
shared-binding, owner/claim, input-ID, attempt-quantity, and closure-ID defects before their fixes.
One additional exact execution-binding read-order pin was added from static reasoning and passed on
first execution after that guard had already been corrected. A fresh read-only retained-value audit
then reported no remaining P0 and no remaining P1 in this defect class.

The exact corrected tree now passes all 511 collected execution-core cases, Ruff check and format,
mypy over seven execution-core source files, all six import contracts, scope, and diff checks. The
R2 gate first failed only because Windows denied pytest's shared user-temp directory; the unchanged
61-case suite passed with `BROKER_ADAPTER=mock` and a new preserved workspace-local base-temp path.
Its existing SQLite cases used only their authorized disposable test fixtures. No credential,
Alpaca activity, persistent application database, runtime wiring, PR/merge, deletion, or cleanup was
used. The fresh mutation, current pure/static gates, and authoritative repository coverage now pass
as recorded below. The first repository-coverage attempt failed the unchanged floor and is
diagnostic only. Independent exact-head review and dual-version CI remain mandatory; no earlier
artifact satisfies this fourteenth gate.

## Fourteenth-gate mutation completion and coverage remediation (2026-08-01--2026-08-02)

Exact production checkpoint `bd5943768ab41592c6445892248ade86f1a79bbf` survived nine
coordinated live mutation groups. Every mutation was restored before proceeding:

1. Removing the complete unresolved-reconciliation release policy was killed by the release and
   parent-finalization pin. A narrower leg-only removal survived safely because the independent
   execution/scope guards still blocked release.
2. Removing the ordered human effect-and-leg review gates killed both ordering pins; removing only
   the effect gate killed its dedicated pin.
3. Coordinated removal of missing-source, direct-source, and backward-alias provenance checks was
   killed by the semantic-alias retargeting pin. Partial removals survived safely because the
   remaining independent checks still rejected the forged checkpoint.
4. Removing the sibling effect-wide overfill latch was killed by the aggregate broker-fill pin.
5. Allowing operator-final state with unresolved execution-integrity bits killed both parameter
   rows; the later stale-binding failure confirmed that the intended earlier guard was absent.
6. Weakening the common fill-component exact-type guard to `isinstance` was killed by delayed
   quantity, execution-scope, and price-component pins. Compound identity remained independently
   protected.
7. Removing the pre-read exact `VenueExecutionBinding` guard was killed by its property-access trap.
8. Removing the pre-index exact `VenueInputRecord` shape guard was killed by its identity-access
   trap.
9. Coordinated removal of the four exact price-scalar guards, four `_SnapshotBinding` metadata
   guards, and the `PositionState` binding guard killed all nine new coverage-remediation rows.

The restored production SHA-256 values are:

- `fills.py`: `50832e3849aa3d3be888dd400a646dca04180dcf885aecabdecac0b3dbab6666`
- `identity.py`: `b7fbf9556031e00ca93fcd49c54deeaec2d0f56f614d6c396d92108c4960fcc2`
- `position.py`: `b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767`
- `recovery.py`: `684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c`
- `venue.py`: `b6f288a5b36878b017268934ae170f577c8c85faf63a84fc71c89809151edc98`

The first fourteenth-gate repository run collected 5,099 tests and completed in 1,127.6 seconds:
5,087 passed, 11 skipped, and one expected failure. Its behavior result is diagnostic only because
the unchanged combined line/branch coverage floor failed at `92.93816463174478%`: 17,525 of
18,500 lines and 6,072 of 6,890 branches, or 23,597 of 25,390 combined obligations. Passing 93%
required 16 additional covered obligations.

The failed diagnostic artifacts are preserved unchanged:

- `.coverage_wo0146_full_authorized_14`: 1,765,376 bytes; SHA-256
  `8392639ffa087fb767c690599fcaa52bd299c5c6819d06ff6be632b7ac8d510b`
- `.coverage_wo0146_full_authorized_14.json`: 1,739,156 bytes; SHA-256
  `77e5759b023161e263c746d4fb4eac16c503ce106447045c037aa07d5f918b63`

Coverage remediation changed tests only. Nine failure-capable cases now exercise four
noncanonical reported-price scalar payloads, four malformed retained snapshot-binding metadata
variants, and one noncanonical retained position binding. Coordinated removal of their corresponding
production guards made all nine rows fail; the restored source makes all nine pass. The resulting
pure execution-core suite passes all 520 collected cases. Ruff check passes, all 17 inspected files
are format-clean, mypy passes all seven execution-core source modules, Import Linter keeps all six
contracts with none broken, and the diff check passes. The unchanged exact production object had
already passed all 61 R2 cases with `BROKER_ADAPTER=mock` and a preserved workspace-local base-temp
path; the coverage remediation changes no R2-tested production code.

The fresh authoritative repository rerun collected 5,108 tests and completed in 1,165.0 seconds:
5,096 passed, 11 skipped, and one expected failure. The unchanged 93% combined line/branch gate
passes at exactly `93.00512012603387%`: 17,534 of 18,500 lines and 6,080 of 6,890 branches. The
preserved `.coverage_wo0146_full_authorized_15` artifact is 1,765,376 bytes with SHA-256
`aba5362c36543ac73a6bac620afbcc7c4574d6edfbfc8c83effc408843a70fe8`; its JSON report is
1,739,084 bytes with SHA-256
`a97237e1ae1ed4daa7ef1cbb92ef59f1752a118cebf3dddacf2eedba7b5c248a`.

Both repository runs forced `BROKER_ADAPTER=mock`. Existing database-bearing cases used only the
previously authorized disposable test-only SQLite fixtures, including their fixture SQL/DDL. No
persistent application database, credentials, Alpaca activity, broker/network I/O, runtime wiring,
PR/merge, deletion, or cleanup occurred. The prohibited R1 DDL execution result was not used for
design, validation, coverage, or acceptance evidence.

The exact final checkpoint still requires reviewer-owned
`REV-0048/result-addendum-02.md` with no unresolved P0/P1 and unchanged Python 3.11/3.12 exact-head
CI. Until both gates pass, WO-0146 remains active and WO-0147 remains inactive.

## Public-command boundary P1 stop and fifteenth bounded re-gate (2026-08-02)

Independent exact-head review of `1de7173bd01dfa35a39da4c8683eaff338c5f2e0` reproduced one
additional P1 exact-boundary/read-order defect before writing an acceptance artifact. The public
`apply_venue_recovery_input` entrypoint read `item.input_id` and dispatched through `isinstance`
before proving that the outer command was one exact admitted venue/recovery input type. A
`RequestedEffect` subclass with an armed `input_id` getter therefore executed subclass behavior
before rejection. Unique mutating paths eventually failed closed in input-proof construction and no
unsafe state acceptance or quantity change was reproduced, but early refusal/reconciliation paths
could return a transition for a subclass instead of rejecting the noncanonical command.

A failure-first public-boundary pin reproduced the premature property read with
`AssertionError: input_id read before exact command type check`. The bounded fix centralizes the
exact admitted-command set already used by canonical identity and applies that guard immediately
after exact book/execution validation, before any command property, dispatch, replay, equality,
commitment, or economic access. The new pin then passes with `TypeError` before the armed getter.

A separate evidence-integrity pass found no numerical, hash, scope, artifact, or restoration
contradiction, but identified one P1 provenance gap and one P2 date error. The date above now spans
both local execution days. Before the next exact review, the implementation seat must preserve a
hash-addressed transcript containing exact HEADs, commands, environments, exit codes, summaries,
mutation outcomes, and artifact identities. Causal no-network/no-credential/non-reliance statements
must be labeled as implementation-seat attestations unless independently reproduced or externally
verified.

Checkpoint `1de7173`, its 5,108-test behavior result, and
`.coverage_wo0146_full_authorized_15` are diagnostic only after this production change. Ameen's
standing authorization for in-flight remediation re-gates only this directly necessary correction.
Fresh failure pin, pure/static, mutation, R2, full repository coverage, durable transcript,
independent exact-head review, and unchanged Python 3.11/3.12 CI evidence are mandatory. This does
not activate WO-0147 or authorize runtime/schema/persistence work, broker or credential use,
PR/merge, branch/worktree retirement, deletion, or cleanup.

## Fifteenth-gate implementation evidence freeze (2026-08-02)

The public-command pin failed before the fix with the armed `input_id` getter, passed after the fix,
failed again when only the early entry guard was removed, and passed after restoration. The restored
`venue.py` SHA-256 is `eb16bb8a24ff47c0de66af884ba778a63bae60fd3fbdedd1bfbb2236c1a671db`;
the other four production hashes remain exactly those recorded by the fourteenth gate.

The restored tree passes all 521 collected execution-core cases in 130.0 seconds, Ruff check and
format over all 17 execution-core source/test files, mypy over seven source files, all six import
contracts, and diff check. The 61-case R2 suite passes with `BROKER_ADAPTER=mock` and a unique
workspace-local base-temp path.

The fresh authoritative repository run collected 5,109 tests and completed in 1,179.9 seconds:
5,097 passed, 11 skipped, and one expected failure. The unchanged combined line/branch coverage
floor passes at exactly `93.00594652069468%`: 17,537 of 18,503 lines and 6,080 of 6,890 branches.
The preserved `.coverage_wo0146_full_authorized_16` artifact is 1,765,376 bytes with SHA-256
`a46d40e58612413aa42c10add6a79f96c918313d385fe15a41feb068b574f798`; its JSON report is
1,739,738 bytes with SHA-256
`9f9b9cbdc78af92a134658299ef125303ee1418137bd61ee3aa1bfc3e5104b9e`.

The initial transcript frozen at implementation commit
`cd4295c29bc72bd7b16d9b6f7a6fb09f99ba1c4e` was 15,783 bytes with SHA-256
`fb119bd3d6919e5b9cbe6a6f5a7e0bcd2cb8686d0f26c05d0cd574d252a9a51e`. A final read-only evidence
audit blocked that version because it summarized some historical mutation commands with
placeholders and omitted the JSON-export and exact-scope commands. The production and test bytes at
`cd4295c` remained the unchanged implementation freeze; the evidence defect did not require a
production/test rerun.

The amended exact command, environment, exit, mutation, restoration, invalidation, source-hash,
scope, and artifact ledger is preserved as implementation-seat evidence in
`work/review/REV-0048/implementation-evidence-fifteenth-gate.md`, 24,556 bytes, SHA-256
`d11bcd322c3c8f0bfe45d73bdafab1093c64f76cfc13df24896ef627bb67721e`. It explicitly names
`cd4295c29bc72bd7b16d9b6f7a6fb09f99ba1c4e` as the implementation freeze, expands every mutation
node/base-temp command, records the `_16` JSON export, distinguishes the eight-decimal terminal
coverage report from the exact JSON-derived ratio, and includes the exact 25-path scope inventory
and passing scope-check command. The evidence-only successor changes no production or test byte;
the independent addendum must name that successor's exact SHA. The transcript distinguishes
implementation execution, independent reproduction, external pending evidence, and invalidated
results. Its safety/non-reliance statements remain implementation-seat attestations; they are not
silently elevated to independent proof.

Existing database-bearing repository/R2 cases used only the previously authorized disposable
test-only SQLite fixtures, including fixture SQL/DDL. No persistent application database,
credentials, broker activity, intentional network I/O, runtime wiring, PR/merge, deletion, or
cleanup occurred, and the prohibited R1 DDL result was not relied upon. These causal absence and
non-reliance statements are implementation-seat attestations pending independent/external evidence.

Independent exact-head addendum-02 and unchanged Python 3.11/3.12 CI remain mandatory. WO-0146 is
still active and WO-0147 remains inactive.

## Evidence-provenance P1 stop and evidence-only re-gate (2026-08-02)

The final read-only evidence audit of `cd4295c` found no P0, no numerical/hash/scope/source-restoration
contradiction, and no unexplained changed path. It did find one P1: the first transcript did not
fully reproduce its own exact-command claim. The mutation section used a `<BaseTemp>/<Nodes>`
template, M6/M9 named test groups rather than concrete node IDs, the `_16` JSON generation command
was absent, and the scope result was promised rather than pasted. It also found two P2 labels: the
eight-decimal terminal coverage report was labeled with the more precise JSON-derived ratio, and an
early diagnostic called the combined line/branch floor a branch-only gate.

This evidence-only re-gate resolves those documentation defects without changing source or tests.
The exact implementation freeze is
`cd4295c29bc72bd7b16d9b6f7a6fb09f99ba1c4e`; its parent is
`1de7173bd01dfa35a39da4c8683eaff338c5f2e0`. The post-activation scope command against
`d03e8eb6b83c397691c1028e4781b585b15de04b..cd4295c` exited `0` with
`SCOPE CHECK PASSED`, and cumulative base-to-freeze inventory contains exactly 25 allowed or
activation-only paths. The amended transcript contains the exact commands and outcomes. Because a
commit cannot record its own SHA without another successor, reviewer-owned addendum-02 must bind
the exact evidence-successor SHA and verify that its delta from `cd4295c` contains only this active
work order and the transcript. No implementation, mutation, R2, or full-suite result is silently
re-executed or relabeled.

Until that independent review passes, WO-0146 remains active and WO-0147 remains inactive. This
re-gate authorizes no source/test change, runtime/schema/database/broker work, credential use,
PR/merge, branch/worktree retirement, deletion, or cleanup.

## Frozen semantic contract

- Add exact generation/effect/occurrence/client/claim/closure/evidence identities and immutable full
  scope binding. `SUBMIT`, `CANCEL`, and `REPLACE` effects start `REQUESTED` with canonical
  `acceptance_set_state=OPEN`; creating client identities are nonblank and generation/account unique.
- Effect edges are `REQUESTED -> CANCELED_BEFORE_DISPATCH | DISPATCH_CLAIMED`, then claimed to
  `ACKNOWLEDGED | REJECTED | OUTCOME_UNKNOWN`, unknown to acknowledged/rejected/needs-review, and
  needs-review to operator-reconciled only after every owned leg is closed/released and the parent
  acceptance set is exactly `CLOSED`. The immutable claim is recorded with the claim edge. A
  stranded claimed effect becomes `OUTCOME_UNKNOWN`; it is never resent.
- Attempt order status and pending submit/cancel/replace operation are orthogonal. Acknowledgement is
  quantity-neutral and cannot terminalize an attempt. A fill during cancel/replace ambiguity updates
  economic truth without clearing that ambiguity. Delayed statuses cannot regress terminal/higher
  state; new canonical economic facts still apply.
- One effect owns zero, one, or many immutable concrete broker-order identities. Same exact owner is
  replay; cross-effect/generation/client/occurrence/symbol/side/economic scope is conflict and cannot
  overwrite. Every owner has exactly one active/unresolved leg or one current terminal-closure head.
- Terminal compaction removes only the active leg and appends the sole ordinal-1 closure root.
  Successors must name the same owner's immediately prior ordinal. Duplicate roots, gaps, stale or
  cross-owner predecessors, and branches fail closed. Later economics append the next closure; stale
  status cannot reactivate a closed leg.
- Acceptance edges are only `OPEN -> CLOSED -> INVALIDATED`. `NEVER_DISPATCHED` requires local
  cancellation and provable absence of an immutable claim. Other closure kinds are typed externally
  established `CONTRACT_COMPLETE_RESPONSE` or `COVERED_RECONCILIATION` facts; M1 never invents
  adapter completeness. Known-leg terminality, not-found, and position parity do not close `OPEN`.
  Late acceptance preserves the closure proof, appends contradiction evidence, and makes the set
  permanently `INVALIDATED`; no reopen/re-close exists.
- `IngestHumanAttestedFill` carries exact leg/effect/claim occurrence, stable source/root identity,
  price, incremental and prior/resulting cumulative quantity, actor, reason, and evidence. It may
  call the one canonical root-fill primitive only after exact binding, `NEEDS_REVIEW`, full-payload
  idempotency, order-capacity, cumulative-interval, and long-only checks. Its root authority is
  `HUMAN_ATTESTED`; it has no correction/bust or broker-overfill power.
- Human coverage is the half-open exact leg interval `(prior_cumulative, resulting_cumulative]` with
  committed economics. Later broker evidence matching that interval corroborates with zero second
  delta; an exactly disjoint uncovered interval may enter the broker fact reducer; partial overlap,
  changed economics, or unprovable mapping records reconciliation with zero guessed delta.
- `ReleaseVenueLeg` requires exact ownership, broker-terminal evidence, and equality of cumulative
  venue quantity to canonical fills attributed to that leg. It changes no economics/integrity,
  clears only that leg, releases no sibling or parent set, and creates no successor. Exact retry is
  a no-op; changed actor/reason/evidence/identity/economics conflicts.
- Keep `apply_broker_execution_fact` broker-only and broker-authoritative overfill exact. Broker
  correction/bust cannot revise a human root. Human support must not duplicate position arithmetic.

## Scope

```yaml
allowed_paths:
  - app/execution_core/identity.py
  - app/execution_core/fills.py
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/recovery.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_fill_position.py
  - tests/execution_core/test_fill_position_stateful.py
  - tests/execution_core/test_import_boundary.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_venue_stateful.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - tests/execution_core/test_venue_provenance_hardening.py
  - work/active/WO-0146-reset-kernel-b-venue-ownership-recovery.md
  - work/completed/keep/WO-0146-reset-kernel-b-venue-ownership-recovery.md
  - work/review/REV-0048/**
  - work/ledger.jsonl
  - pkl/log.md
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
activation_only_paths:
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - work/queue/ARCH-RESET-2026-07-M1-BRANCH-RETIREMENT-MANIFEST.yaml
forbidden_paths:
  - app/store/**
  - app/events/**
  - app/broker/**
  - app/api/**
  - app/monitoring.py
  - app/main.py
  - app/server.py
  - ui/**
  - docs/adr/ADR-020-current-state-execution-kernel.md
  - docs/adr/ADR-021-position-protection-liquidity-execution.md
  - docs/adr/ADR-022-reset-beta-scope-cutover-governance.md
  - work/queue/ARCH-RESET-2026-07/**
  - .github/**
```

`REV-0048` is reserved for the independent M1B review seat; the implementation seat may create
`request.md` and `disposition.md` but never reviewer-owned `result.md`. The manifest-covered packet
and accepted ADR bodies remain byte-immutable. Existing oversized `fills.py`/`position.py` edits are
limited to the verified human-root seam; material restructuring is a stop. `venue.py` and
`recovery.py` expose one atomic transition API rather than competing reducers.

## Required failure-capable evidence and stops

Named deterministic, independent-oracle, and Hypothesis histories must kill: ACK-as-terminal;
status regression; singular broker-ID overwrite; terminal-leg-closes-`OPEN`; false
`NEVER_DISPATCHED`; late-acceptance reopen; owner rebind; closure root/gap/branch/cross-owner bugs;
human over-capacity/negative SELL; release economic/global mutation; changed evidence retry;
attested/broker double count; claimed-effect resend; terminal-history scan/materialization; and
commitment/equality omissions for claim, proof, owner scope, closure head, or human evidence.

Stop if interval mapping needs a second economic lane, persistence, or adapter inference; if attempt
state cannot retain orthogonal cancel/replace ambiguity; if closure must infer completeness; if
WO-03 policy is needed; if PA-03 needs endpoint/credential/legacy rollback work; if broker-only
overfill or revision guards weaken; if runtime/schema/broker/ADR changes become necessary; or if two
P0s or three same-root P1s emerge. Close only after focused/full/static/dual-version gates and blind
review pass, then append one ledger row and reconcile PKL. Do not activate RESET-WO-03 here.

## Review disposition and closeout (2026-08-02)

Reviewer-owned `REV-0048/result.md` first returned `BLOCK` on retained-history live scans and an
importable checkpoint-construction capability. `result-addendum-01.md` confirmed those were closed
but returned `BLOCK` on delayed nested broker-fact component subclasses. Subsequent bounded
re-gates closed that P0 and the later checkpoint, provenance, retained-value, public-command, and
evidence-provenance findings without widening into persistence or runtime work.

The final independent addendum reviewed exact evidence target
`883c0b664708c3b1fba09f7f69b63e8c9b6f9d75`, whose production/test implementation freeze is
`cd4295c29bc72bd7b16d9b6f7a6fb09f99ba1c4e`. It verified byte-identical source/test trees across
that evidence-only successor, independently passed all 521 pure execution-core tests and focused
static gates, performed fresh construction/provenance, late-acceptance, sibling-capacity, and
public-command-boundary attacks, rehashed the `_16` evidence, and returned `ACCEPT` with no
unresolved P0/P1. The reviewer artifact is
`work/review/REV-0048/result-addendum-02.md`, 8,894 bytes, SHA-256
`79ec258b580c91b0bc78cb15b7cae2a1ccd99154ae99bd96e9e51b7e7769769d`; its containing review-artifact
commit is `c6b8481a206a6b116adfbe700e1e93fefe13b3ab`.

This closeout changes documentation/governance only. The final closeout commit cannot name its own
SHA or later workflow run. It must be pushed once, left unchanged, and accepted only by an external
record binding that exact SHA to the repository's unchanged successful Python 3.11 and Python 3.12
jobs. Until that succeeds, this `CLOSED` disposition is a non-activating closeout candidate:
the effective lifecycle remains `REVIEW`, `WO-0147` remains inactive, and no later work may rely on
closure. A red, canceled, mismatched-head, or incomplete job requires the candidate to be amended
and re-run; no post-success evidence-only successor is permitted.

```yaml
fable_done:
  task: "WO-0146 reset kernel B: venue ownership and recovery lifecycle"
  done_when_results:
    - item: "Pure venue ownership, ambiguity, closure, and ADR-012 recovery behavior is exact and deterministic."
      status: MET
      evidence: "The restored implementation freeze passed all 521 execution-core tests; named examples and stateful histories cover effect/attempt separation, one-to-many acceptances, immutable closure, unknown outcomes, human-attested fill/release, and later broker evidence."
    - item: "Every capital/authority guard is failure-capable and restored green."
      status: MET
      evidence: "The M1-M10 ledger records concrete commands, nodes, base-temp paths, decisive failures or disclosed safe survivors, and restoration. The final reviewer independently repeated stronger sibling-capacity and public-command mutants."
    - item: "Focused, static, R2, and repository coverage gates pass without a production dependency on persistence or broker code."
      status: MET
      evidence: "521 pure tests, Ruff check/format, mypy over seven files, six import contracts, 61 R2 cases under BROKER_ADAPTER=mock, and 5,109 repository cases passed. The unchanged combined line/branch floor passed at 93.00594652069468%."
    - item: "Independent review has no unresolved P0/P1."
      status: MET
      evidence: "REV-0048 result-addendum-02 returned ACCEPT at exact target 883c0b664708c3b1fba09f7f69b63e8c9b6f9d75 after fresh probes and source/test tree-identity verification."
    - item: "Allowed paths and broker, credential, persistence, runtime, merge, deletion, and cleanup exclusions remain respected."
      status: MET
      evidence: "The cumulative 25-path inventory is entirely allowed or activation-only. Existing R2/full fixtures used only authorized disposable test SQLite; no persistent application database, credential, broker/Paper activity, runtime wiring, merge, deletion, or cleanup occurred."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "No in-scope P0/P1 remains. Runtime persistence, adapters, supervisor policy, protection, acquisition, and cutover remain explicitly deferred to later gated slices."
  deferred:
    - "External exact-head Python 3.11/3.12 CI is the effectiveness gate for this immutable closeout candidate; effective lifecycle remains REVIEW until it succeeds."
  status: VERIFIED
  verification_scope: "Implementation, static, scope, evidence, and independent-review gates only; no in-commit claim that later CI has passed."
  acceptance_condition: "EXTERNAL_EXACT_HEAD_CI_REQUIRED_BEFORE_WO_0147"
```

WO-0146 is retained with `[PKL_UPDATED, RESULT_SUMMARY_KEPT]`. No ADR changed. No packet, accepted
ADR, runtime, persistence, broker, credential, branch/worktree, or preserved artifact was mutated or
removed. The prohibited R1 DDL result was not used for any design, test, review, or acceptance
conclusion.

## Exact-head Python 3.11 CI failure and bounded re-gate (2026-08-02)

The external effectiveness condition did not pass. GitHub Actions run `30746436486` (#682) targeted
the exact closeout candidate `4b9b47de1936a179478f1c638c4872a4b0935719`. Python 3.12 job
`91492722638` passed every step. Python 3.11 job `91492722592` passed checkout, dependency,
Ruff, mypy, import-boundary, contamination, AI-OS, and R2 gates, then failed the repository coverage
step with three `RecursionError` cases in
`tests/execution_core/test_fill_position_stateful.py`. The exact traceback enters the test helper
at line 234 while computing `repr(root_heads)` before the reducer call; Python 3.11 recursively
renders the private persistent radix tree until its recursion limit. The secondary coverage failure
reflects those three aborted tests, not a separately established coverage regression.

This invalidates the prior closeout candidate and keeps the effective lifecycle at `REVIEW`.
`WO-0147` remains inactive. Ameen's standing authorization for in-flight findings re-gates only the
directly necessary WO-0146 correction under the existing allowed path
`tests/execution_core/test_fill_position_stateful.py`, plus exact evidence/review/PKL reconciliation.
The failure is already RED evidence. Replace the test-only recursive structural rendering with the
kernel's public immutable commitments so the mutation/determinism assertion stays failure-capable
and constant-work; do not weaken the assertion or touch production unless a fresh counterexample
proves the diagnosis incomplete.

The successor candidate requires the three exact failed nodes, the complete execution-core suite,
static/scope/AI-OS gates, the authorized R2 and repository suites, independent exact-diff review,
and unchanged exact-head Python 3.11/3.12 CI. Any production change, assertion weakening, mismatched
head, or remaining version-specific failure stops the closeout. No broker, credential, Paper,
persistent database, runtime wiring, PR/merge, retirement, deletion, or cleanup authority is added.

### FIX — recursion-safe immutable-input guard

- **Root cause:** the stateful test helper recursively rendered auto-generated representations of
  `RootHeadIndex` and `SeenFactIndex`. Those representations descend through immutable persistent
  radix-node children and can exceed CPython 3.11's recursion limit before the reducer is called.
  No production call site relies on these representations.
- **Correction:** snapshot the public constant-work component commitments and bounded snapshot-
  binding/fact representations before and after both reducer calls. This preserves determinism and
  illicit-input-mutation detection without traversing private tree structure. No production file
  changed.
- **Fresh focused evidence:** the three exact failed nodes pass normally and with the local Python
  3.12 recursion limit reduced to 700; the full stateful file and all 521 execution-core tests pass.
  Ruff check/format, mypy over all seven execution-core source files, six import contracts, AI-OS
  install/version/ledger/PKL/disposition checks, and all 61 R2 cases pass with
  `BROKER_ADAPTER=mock` and a fresh disposable workspace-local test directory.
- **Failure capability:** three transient hostile reducers mutated a position component, an exact
  root-index binding, and the fact payload after the second deterministic call. The restored guard
  killed all three with the input-mutation assertion.
- **Still required:** authorized full repository coverage, independent exact-diff review, restored
  source/test hashing, and an immutable successor passing exact-head Python 3.11 and 3.12 CI.

### REV-0048 addendum-03 BLOCK and second bounded compatibility re-gate

Reviewer-owned `result-addendum-03.md` preserved a fresh P1 against exact repair freeze
`ba70c46b05f3ec3d653159f00193c03711ba82e7`: cached persistent-map commitments do not re-read an
illicitly mutated retained value. A reversible hostile reducer changed a stored `RootHead.quantity`
from 3 to 10 after the second call; the root commitment and binding representation remained
unchanged, so the first repair's guard returned normally. That weakens the old structural snapshot
and is an explicit WO stop. The result is retained unchanged at commit `f133da3` with verdict
`BLOCK`; the full/R2 green evidence cannot override it.

Ameen's standing authorization for in-flight findings re-gates only this same test-harness repair.
The RED evidence is the reviewer-owned retained-leaf survivor. Replace cached-commitment-only
comparison with a recursion-safe semantic fingerprint independently materialized from actual
position sequences, root-head leaves, and seen-fact leaves, while retaining bounded bindings and
fact payload. Add permanent hostile pins for nested retained values. The fingerprint is test-only
and may use the explicit slow/audit views; production constant-work requirements do not require a
test oracle to trust cached values. No production change is authorized or justified.

The new guard must kill root-head, seen-fact, position-sequence, binding, top-level component, and
fact-payload mutations; pass the exact Python 3.11 failure nodes at lowered recursion; and repeat
the focused/static/R2/full/review/exact-head-CI chain. WO-0147 remains inactive. All broker,
credential, Paper, persistent-database, runtime, merge, retirement, deletion, and cleanup
exclusions remain unchanged.

#### FIX — independently re-derived retained-leaf fingerprint

- **Root cause correction:** cached commitments remain in the snapshot, but are no longer trusted
  alone. The test-only fingerprint also materializes and renders each actual position-sequence,
  root-head, and seen-fact leaf through the public explicit slow/audit views, plus the bounded
  bindings and current fact. It never renders the private radix tree and changes no production
  path or constant-work live transition.
- **Permanent RED-to-GREEN pins:** nested `RootHead.quantity` and retained `SeenFact.fact.quantity`
  mutations are injected after the second reducer call and must raise the immutable-input
  assertion. A separate position-sequence pin proves a changed retained leaf changes the
  fingerprint while the cached position commitment remains unchanged.
- **Fresh focused evidence:** all ten stateful cases pass with the recursion limit reduced to 700;
  all 524 execution-core cases pass. Transient position-component, root-binding, and fact-payload
  mutants are also killed. Ruff check/format, mypy over seven source files, six import contracts,
  AI-OS install/version/ledger/PKL/disposition checks, and all 61 R2 cases pass under the mock broker
  with a fresh disposable workspace-local test directory.
- **Still required:** a fresh full repository coverage run, new exact-diff independent review, and
  unchanged exact-head Python 3.11/3.12 CI. Addendum-03 remains a preserved blocking artifact; only
  a reviewer-owned successor addendum may close its P1.

#### Re-gate — auxiliary persistent-map mutation bypass

- **Failed implementation freeze:** `1189d88` narrowed but did not close addendum-03's retained-leaf
  mutation class. Two independent read-only audits changed an existing
  `RootHeadIndex._broker_scope_counts` leaf and an existing
  `SeenFactIndex._prefix_commitments` leaf after the reducer's second call. In both cases the cached
  index commitment and the incomplete semantic fingerprint remained unchanged, the corresponding
  public query changed, and `_apply` returned normally. The freeze is therefore blocked and is not
  acceptance evidence.
- **Bounded corrective scope:** retain the production tree byte-for-byte; replace the incomplete
  test-only view with an iterative, non-recursive audit of every field and persistent-map node that
  can influence `PositionState`, `RootHeadIndex`, or `SeenFactIndex` behavior. Add permanent RED pins
  for broker-scope counts and prefix commitments before restoring them to GREEN. Preserve the
  existing root-head, seen-fact, position-sequence, top-level-component, binding, and fact-payload
  mutation controls.
- **Evidence treatment:** the repository-wide diagnostic run started at `1189d88` was stopped after
  the independent blocks made it obsolete; its partial disposable test directory remains preserved
  and is inadmissible for closeout. A new exact implementation freeze must pass focused lowered-
  recursion tests, the full static/R2/repository gates, hostile mutation probes, independent review,
  and exact-head Python 3.11/3.12 CI. WO-0147 remains inactive.

#### FIX — complete iterative semantic graph projection

- **RED:** the two permanent auxiliary-map cases reproduced the independent findings before the
  helper changed: the root broker-scope-count and seen-prefix-commitment parameters both failed
  because the expected immutable-input assertion did not occur; the existing root-head and
  seen-fact parameters remained green.
- **Root cause correction:** `_apply` now snapshots the complete input dataclass/tuple graph with an
  explicit work stack. The projection records every exact field, radix node, key/value leaf, cached
  commitment, structural edge, and shared/cyclic reference ordinal without recursively rendering a
  persistent container. The same projection is the authoritative output-determinism oracle, because
  ordinary `RootHeadIndex`/`SeenFactIndex` equality omits auxiliary caches and cannot prove complete
  transition identity under hostile corruption. A static call-site search found production binding,
  recovery, and venue checks use exact commitments rather than those equality methods, and normal
  public constructors derive the auxiliary maps. No production equality or transition path changed.
- **Permanent failure-capable controls:** five input-integration mutants cover retained root-head,
  seen-fact, broker-count, prefix-proof, and current-fact leaves; two output mutants cover divergent
  broker-count and prefix-proof maps; two position-sequence pins cover both root keys and effective
  head IDs; and six structural pins cover observed-root and overfill indexes, cached radix metadata,
  required sequence/binding alias topology, and a hostile radix cycle.
- **Fresh focused evidence:** all 15 named controls pass; all 22 stateful cases pass with Python's
  recursion limit reduced to 700; and all 536 execution-core cases pass under the forced mock broker.
  Ruff check/format, mypy over seven source files, six import contracts, AI-OS integrity, scope, and
  diff checks pass. All 61 R2 cases pass with the forced mock broker and fresh disposable test
  directory. Fresh full repository coverage, independent hostile review, and immutable exact-head
  Python 3.11/3.12 CI remain required before this re-gate can close.
