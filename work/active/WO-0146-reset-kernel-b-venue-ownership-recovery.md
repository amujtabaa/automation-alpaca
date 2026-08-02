---
type: Work Order
title: "Reset kernel B: venue ownership and recovery lifecycle"
status: ACTIVE
work_order_id: WO-0146
wave: RESET-M1B
model_tier: strong
risk: high
disposition: []
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
skips and one expected failure, but the unchanged 93% branch-coverage gate failed at 92.13%. Its
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
