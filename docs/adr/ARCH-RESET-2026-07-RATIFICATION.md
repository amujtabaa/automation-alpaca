# Architecture reset ratification index — ARCH-RESET-2026-07-R1

## Status

**Accepted as architecture authority; M0 documentation landing independently accepted.** This
index records Ameen's 2026-07-31 approval of the unchanged R1 authority unit. It does not activate implementation,
`RESET-WO-01`, DDL/schema execution, a database, broker access, credentials, Paper activity,
live-shadow, live trading, deletion, cleanup, push, pull request, or merge.

The three canonical ADR bodies below remain byte-for-byte copies of their ratified proposed texts.
Their embedded `Proposed` sentences are preserved deliberately; this separate index records their
accepted status without changing a ratified byte.

## Detached authority identity

- Authority manifest SHA-256:
  `c81e49ac3b36d7d99f0974cf34f2f89330e3336eea5877341f3b170aec1a2258`
- Human-approved complete R1 archive SHA-256:
  `51e4bb1a7ce0c00f16cce57c0fa6f15aad33773f0c62ea57d637b55e8eba053f`.
  This digest is approval provenance. The archive bytes are not retained in this repository and
  cannot be independently rehashed from a clean checkout.
- Frozen reset base: `master@6d5937492788aa0ab1cf8348321fa01ee57df920`
- Frozen R6 evidence only: `codex/signal-r6a-rails-store@39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`
- Canonical packet copy: `work/queue/ARCH-RESET-2026-07/`

The R6 branch is evidence and a regression corpus. It is not merged, broadly cherry-picked, or
treated as target authority.

## Canonical accepted ADR mapping

ADR-014 through ADR-016 are already occupied by different accepted decisions on the frozen R6
evidence branch at `39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`. ADR-017 through ADR-019 are
reserved as draft gate identities on recorded ref
`origin/claude/wargame-roadmap-kickoff-2v2tan@fb6e93e556e94c3c5904b9218d530865c0f3a84b`.
The first three globally conflict-free canonical identities are therefore ADR-020 through ADR-022.

| Canonical ADR | Ratified source | SHA-256 of unchanged body | Disposition |
|---|---|---|---|
| [ADR-020 — Current-state execution kernel and audit separation](ADR-020-current-state-execution-kernel.md) | `13-proposed-adr-current-state-kernel.md` | `35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838` | Accepted by exact-digest approval; implementation deferred |
| [ADR-021 — Position protection and side-symmetric liquidity execution](ADR-021-position-protection-liquidity-execution.md) | `14-proposed-adr-protection-execution.md` | `ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0` | Accepted by exact-digest approval; implementation deferred |
| [ADR-022 — Reset beta scope, cutover, and development governance](ADR-022-reset-beta-scope-cutover-governance.md) | `15-proposed-adr-reset-scope.md` | `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798` | Accepted by exact-digest approval; implementation deferred |

The complete clause-by-clause disposition remains the unchanged
[`12-proposed-adr-set.md`](../../work/queue/ARCH-RESET-2026-07/12-proposed-adr-set.md).
Preserved clauses in ADR-001 through ADR-013 remain binding. Partial supersession is explicit in
that matrix and in backlinks added to ADR-004, ADR-008, ADR-009, ADR-010, and ADR-013; nothing is
superseded merely because the new authority is aggregated differently.

## Runtime and cutover record

- Python 3.11 and 3.12 are supported; Python 3.12 is the development default; production code may
  not require 3.12-only syntax. The reset base already carries both CI interpreter legs and a
  Python-3.11 static target. M0 records that fact but runs no code or tests.
- SQLite is the sole reset-beta production persistence implementation. The existing SQLite and
  in-memory implementations remain read-only evidence until separately authorized cutover work;
  neither is migrated or executed by M0.
- ADR-022 requires a cross-generation Alpaca/Paper/account/origin/credential fence at future
  cutover. M0 neither implements nor verifies that fence and grants or activates neither generation.
- Signal Seat is disabled and unmounted for the reset beta. ADR-009's untrusted-advisor principle
  remains preserved for any separately authorized future reintroduction.

## DDL incident provenance

During the first partial R1 packet pass, a delegated pass executed proposed DDL against an
in-memory SQLite database, exceeding the explicit prohibition. No persistent database or
database-like artifact was found, repository and worktree state remained clean, and work stopped
when the incident was discovered. That result is inadmissible as evidence of validity,
executability, migration safety, or operational correctness. No R1 or M0 conclusion relies on it;
schema execution remains a separately authorized future M2 gate.

## Retained gates

1. REV-0047 initially returned `BLOCK`; remediation target `116822d` corrected all three findings,
   and reviewer-owned addendum 01 returned `ACCEPT`. The M0 independent-review gate is satisfied.
2. `RESET-WO-01` remains an unchanged staged packet document. After the dual-version CI gate passed
   at `74799d322476117c8403c9ab39a72dffd61a0716` and Ameen explicitly authorized implementation,
   its first pure, I/O-free slice was canonicalized as `WO-0145` and is now closed.
3. No outbound Alpaca Paper call or credential use is authorized.
4. No broker-native replace/RTH handoff, legacy deletion, cleanup, or promotion beyond
   Paper/live-shadow is authorized.
5. After exact closeout `dfb8ed30ebed788f1158d7f8be49b44d505c355b` passed independent
   review and unchanged Python 3.11/3.12 CI, Ameen authorized options 1–4 on 2026-08-01. Only
   RESET-WO-02 was then activated as pure I/O-free `WO-0146`; the companion retirement manifest
   is inventory-only, and no deletion begins before the complete M1 merge and exact-master CI gates.
6. Repaired immutable `WO-0146` closeout `7d1c9e5babe5f60bcbbe9e54c6d6dd0bfecf5551`
   passed GitHub Actions run `30752961917` (#685): Python 3.11 job `91510146946` and Python 3.12
   job `91510146979` both succeeded. The separately authorized pure, deny-by-default execution-
   authority slice was activated as `WO-0147` without broker, credential, database, persistence,
   runtime, merge, or cleanup authority.
7. Immutable `WO-0147` closeout `3e39ee6a857ae61d850da1b841e85008b9a59fbb` passed GitHub
   Actions run `30794934357` (#687): Python 3.11 job `91626251701` and Python 3.12 job
   `91626251758` both succeeded. The separately authorized pure position-protection and hybrid-
   trailing slice is active as `WO-0148`; `WO-0149`, M2, broker/credential/database/persistence/
   runtime work, merge, deletion, and cleanup remain inactive.

## ADR-023 bounded-market amendment — accepted 2026-08-04

Ameen approved the exact proposed ADR-023 body at SHA-256
`898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259` together with its
“Exact WO-0148 re-gate required by ratification” section. The unchanged body is retained as
[`ADR-023-bounded-market-occurrence-authority.md`](ADR-023-bounded-market-occurrence-authority.md);
its embedded proposed-status text remains untouched, and this index records its accepted status.

ADR-023 narrowly supersedes ADR-021 lines 120–126 only for occurrence distinctness, aggregate
source-occurrence retention, and replay/restart classification. All other ADR-021 protection,
formula, trigger, trail, guard, execution, fill-truth, and safety clauses remain controlling.

The matching WO-0148 re-gate authorizes only this ADR record, this append-only ratification entry,
the active-WO and matching PKL reconciliation, replacement RED-contract work, and the already
allowed application/test, review, evidence, branch-push, and exact-head-CI work required to close
WO-0148. Application edits remain barred until a replacement immutable RED contract receives fresh
independent exact-commit `ACCEPT` with zero unresolved P0/P1.

No runtime wiring, persistent application-database or direct database work, broker/Alpaca/network
activity, M2 implementation, master merge, deletion, or cleanup is authorized. ADR-023's runtime
recovery-fence proof remains a later M2 gate and is inadmissible as an M1 acceptance claim.

## ADR-023 amendment R1 — accepted 2026-08-04

Ameen approved proposed ADR-023 amendment R1 at exact SHA-256
`F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9` together with its
exact ADR-023 text amendment and WO-0148 RED-contract re-gate.

The amendment replaces only the retained-state bullet in ADR-023 Section 3. Protection retains one
optional exact last-primary `ReportedPrice` solely for the next maximum-step comparison, while only
its existing canonical reported-price commitment is serialized as cursor part 13. The cursor
remains exactly 19 parts and 480 bytes; constant-history state/work, generation/mode, ordering,
baseline, invalidation, halt, exhaustion, and goal-suppression clauses are unchanged.

The exactly amended ADR-023 body has SHA-256
`9A61D4F952079B5F78DA7A8F1A17F70DC3099D20FB359596923C5938CC421EAF`. This is the
controlling ADR-023 body after R1; the original accepted hash above remains immutable provenance.

The matching RED-contract correction also permits only canonical private
`from dataclasses import field as _field` and only `_field(init=False)` as the class-level default
for `MarketOccurrence.occurrence_id`. Every broader field call, argument, default, factory, alias,
rebinding, or call site remains refused.

This approval authorizes only the named ADR-023 amendment, matching active-WO/PKL reconciliation,
the two named RED corrections, replacement RED freeze and review, and continuation of already
authorized WO-0148 application/test, review, evidence, branch-push, and exact-head-CI work after
the replacement RED gate passes. It authorizes no runtime wiring, persistent application-database
or direct database work, SQL/DDL, broker/Alpaca/network activity, credentials, M2 implementation,
master merge, deletion, or cleanup.

## WO-0148 conditional closeout gate - filed 2026-08-04

Ameen explicitly authorized WO-0148's mandatory fresh R2, full-repository branch-coverage, and
unchanged exact-head GitHub Actions Python 3.11/3.12 CI gates to use the existing mock-broker
fixtures and SQL/DDL only against disposable test-only SQLite files. This adds no authority for
credentials, Alpaca/broker/network activity, persistent application databases, runtime wiring,
CI-workflow changes, PR/merge, deletion/cleanup, WO-0149 activation, or M2.

The exact position-local application successor
`e9c2d58a8f16d2b3457dad5e4c5ed04ca24073ae` and reviewer record
`6696743337f9eae8dad0567be6d49333d9d100cc` close the application review with `ACCEPT`,
P0=0/P1=0/P2=0. The final tests-only runtime-envelope delta is separately retained with a preserved
initial P1 and corrective addenda ending `ACCEPT`, P0=0/P1=0/P2=0.

Definitive local evidence is 61/61 R2 cases and 5,847 repository tests with zero failures, zero
errors, 12 skipped outcomes, and raw combined line/branch coverage
`93.01194919026261%` (19,985/21,081 statements plus 7,181/8,126 branches). Existing fixtures ran
only under explicit mock/disposable-test authority. No prohibited R1 DDL result, credential,
broker/Paper result, persistent application database, or deferred runtime proof was used.

The filed `CLOSED` metadata remains effectively `REVIEW` until the immutable closeout `HEAD` passes
both unchanged exact-head workflow jobs. No reset work order is active while that gate is pending;
`WO-0149` and M2 remain inactive, and a failed, canceled, incomplete, or mismatched-head run reopens
WO-0148 rather than activating a successor.

## WO-0148 Python 3.11 oracle successor - filed 2026-08-04

The first conditional closeout `9f696dc4142f9876d0292afc029d6d561671e7b5` failed its exact-
head effectiveness gate. Push run `30989580232` (#691) passed Python 3.12 job `92252257437` and
failed Python 3.11 job `92252257396`: seven tests recursively rendered complete retained radix
graphs through generated dataclass equality after 5,828 other cases passed. No production reducer,
database fixture, or execution/protection decision raised. The result is negative evidence only.

Under Ameen's standing in-flight remediation authority, WO-0148 re-gated only its authority-
stateful test path and replaced shared recursive whole-graph test equality with one test-only,
alias-aware explicit-stack fingerprint. Independent successor review ended `ACCEPT`, P0=0/P1=0/
P2=0, after exact regression, deep-leaf, alias, and cycle controls. Fresh post-review evidence is
61/61 R2 cases and 5,848 repository tests with zero failures/errors, 11 skips, one expected failure,
and `93.01194919026261%` raw combined coverage.

The repaired closeout `HEAD` remains effectively `REVIEW` until one new unchanged exact-head
Python 3.11/3.12 run passes both jobs. No workflow, production, runtime, persistence, credential,
broker/Alpaca/network, PR/merge, deletion, cleanup, WO-0149, or M2 authority was added.

## WO-0148 external gate passed and WO-0149 documentation activation - filed 2026-08-05

The repaired immutable WO-0148 closeout `2462fb557172dd28a7475a763eca0b440c0298e3` passed
unchanged GitHub Actions push run `30996686588` (#693): Python 3.11 job `92275345844` and Python
3.12 job `92275345943` both concluded `SUCCESS`. This satisfies the exact-head external-success
condition recorded above. Run #691 remains negative evidence only and cannot satisfy any closeout
or activation claim. No prohibited R1 DDL result, persistent database result, or superseded result
was relied on.

WO-0145 through WO-0148 are consequently effective `CLOSED`. The smallest complete pure-M1E
WO-0149 specification was independently preflighted. `REV-0051` is retained for its original
candidate; its fresh Sol rerun found four P1 specification gaps, all resolved at the root.
`REV-0052/result.md` identified one P1 in its prior target; `result-addendum-01.md` accepted the
root correction, and the independent `result-addendum-02.md` accepted the final frozen candidate
SHA-256 `0936E114642F5B531A9996EB5685F39024B2982BB1F5BD348FF8048DBB13086D` with P0=0/P1=0.

The documentation/specification activation was published at
`a74998dbe34fabcf47467deb16f34180234fac3f`. A later explicit user authorization records bounded
WO-0149 application/test implementation, necessary evidence reconciliation, in-scope remediation,
commits/pushes, unchanged exact-head CI, and `BROKER_ADAPTER=mock` SQL/DDL only against disposable
test-only SQLite files. It grants no credentials, Alpaca/broker/network activity, persistent
application-database change, runtime wiring, CI-workflow change, PR/merge, deletion/cleanup,
rebase/force-push, M2, or master landing. No accepted ADR body changes or new architectural
decision are required.
