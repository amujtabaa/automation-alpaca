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

## Serial acquisition-generation R2 ratification - accepted 2026-08-05

Ameen approved the ARCH-RESET-2026-07 serial acquisition-generation decision only at frozen
candidate-manifest SHA-256
d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c. The independent static
preflight result SHA-256
c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9 concluded ACCEPT,
P0=0, P1=0, P2=0 for that exact candidate. REV-0053 through REV-0055 remain retained, negative
or unaccepted evidence; they are not authority.

The canonical ADR bodies below are byte-identical copies of their approved R2 candidates. Their
embedded PROPOSED / DRAFT ONLY text remains deliberately unchanged so the approved bytes and
hashes remain verifiable. This index, not a body edit, records their accepted status.

| Current authority | Exact accepted body SHA-256 | Immutable predecessor | Disposition |
|---|---|---|---|
| ADR-020 R2 - current-state execution kernel with acquisition-generation lineage | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | ADR-020 R1 35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838 | Accepted complete replacement |
| ADR-021 R2 - position protection, serial acquisition generations, and liquidity execution | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | ADR-021 R1 ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0 | Accepted complete replacement |
| ADR-023 R1 - bounded market occurrence authority | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | accepted ADR-023 body and R1 amendment provenance | Retained controlling overlay for market occurrence, stream generation, cursor, evidence, and recovery |

ADR-020 R2 and ADR-021 R2 replace their R1 bodies in full as current architecture authority.
ADR-022 is unchanged. The selected model permits distinct reducer-minted
AcquisitionGenerationId values with immutable direct root/effect/owner lineage, one aggregate
SymbolAcquisitionController, at most one LIVE generation, exactly one active protection/broker
authority, and immutable equal EmergencyRecoveryCompatibility for successors. It forbids concurrent
generations, per-generation protection controllers, generic policy arbitration, audit-history scans,
caller-shaped authority, market-stream reset/reuse, and ownership transfer.

This approval authorizes only the documentation reconciliation recorded here and the drafting of
three future pure-M1 work-order candidates. It does not activate any candidate, grant application
or test implementation authority for the R2 serial-generation scope, or alter WO-0149's formal
lifecycle. SQL/DDL and database work, persistence/runtime wiring, credentials, broker/Alpaca/network
activity, M2, master merge, pull request, push, deletion, cleanup, force-push, and rebase remain
unapproved.

## WO-0149 formal supersession - authorized 2026-08-05

Ameen separately authorized formal supersession of WO-0149 solely because ratified ADR-020 R2 and
ADR-021 R2 replace its one-lifetime same-symbol acquisition premise. The work order and every
related artifact remain retained evidence; no historical body, partial material, review result, or
prior authority is erased or treated as accepted R2 implementation evidence.

WO-0149 is now SUPERSEDED by DRAFT-only WO-0150, WO-0151, and WO-0152. This is a lifecycle and
documentation reconciliation only. It activates none of those drafts and authorizes no application
or test implementation, SQL/DDL, database/persistence/runtime work, credentials, broker/Alpaca/
network activity, M2, master merge, pull request, push, deletion, cleanup, force-push, or rebase.

## WO-0151 / WO-0152 coverage-gate ordering amendment - authorized 2026-08-07

Ameen authorized a narrow lifecycle and evidence correction after exact-head GitHub Actions push
run #741 / ID `31185454392` for `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`. Python 3.11 job
`92888729393` and Python 3.12 job `92888729623` completed the functional/static gates and each
reported 5,934 passed tests, 11 skipped, and one expected failure. Both failed only the unchanged
93% combined coverage threshold at 91.34%.

This result is positive exact-head functional/static evidence and negative coverage evidence. It
does not establish overall CI success, effective WO-0151 `CLOSED`, M1 completion, or a coverage
exception. WO-0151 remains effectively `REVIEW`. The user authorized WO-0152 only to be drafted
and independently preflighted as a test-only generated/stateful/replay/boundedness proof layer.
It may activate only after a frozen exact E3 RED contract independently returns `ACCEPT` with zero
unresolved P0/P1. The unchanged 93% gate remains mandatory for one paired E2/E3 exact-head
Python 3.11/3.12 closeout before either effective closure or M1 completion.

This amendment authorizes no production-code change, coverage threshold reduction, exclusion or
pragma, CI-workflow change, runtime wiring, persistent database or direct SQL/DDL work,
credentials, Alpaca/broker/network activity, M2, master merge, pull request, deletion/cleanup
beyond the separately approved uncommitted coverage-experiment restoration, force-push, or rebase.

## WO-0152 R1 test-only setup clarification - authorized 2026-08-07

The initial WO-0152 RED candidate and its independent ACCEPT-WITH-CHANGES
result remain retained negative preflight evidence. They established two
deliberate pure-M1 constructibility boundaries: no public producer mints an
approved opaque dual mandate binding, and no public M1 input certifies the
parent acceptance closure required after a root-owning predecessor.

Ameen authorized only a replacement R1 draft/freeze/review with two separately
named test-only setup exceptions in the one future
tests/execution_core/test_acquisition_stateful.py module. First,
_approved_acquisition_mandates_fixture may make one statically allowlisted
private _mint_dual_mandate_binding call site to produce only fixed complete
immutable A/B/C operator-approved mandate inputs before genesis. Second,
_certified_terminal_parent_fixture may, only after the fully public
claim/discovery/terminal-observation lifecycle, apply one exact sealed parent
closure through the existing internal venue transition under an isolated
temporary certification hook. It must bind exact claim/effect/scope, all
owned-leg terminal evidence, no active attempt, flat consistent execution,
clear reconciliation, an OPEN parent, and one fixed proof digest; it may
install only the resulting venue book in a copied authority state.

Both are test-only deferred M2 configuration/adapter-certification setup, not
execution, controller, currentness, effect, claim, broker, runtime,
persistence, or actor authority. Static allowlist controls and per-test
isolation/restoration are mandatory. All other private access/imports,
opaque-value construction, post-setup mutation, production/API change,
database/SQL/DDL, runtime/network/broker work, CI-workflow change, M2, merge,
deletion, cleanup, force-push, and rebase remain prohibited.

This authorization permits only the R1 draft correction, records, replacement
freeze, and independent preflight. Test-only WO-0152 implementation may begin
only if the exact R1 candidate independently returns ACCEPT with P0=0/P1=0;
the paired E2/E3 unchanged 93% exact-head closeout remains mandatory.

## WO-0152 R1 remediation 01 status - 2026-08-07

The first R1 candidate and its independent result are retained evidence, not
activation authority. The reviewer returned `ACCEPT-WITH-CHANGES` with P0=0,
P1=2, and P2=0: its exact static exception table omitted the already authorized
copied-authority venue installation, and its pre-close reconciliation-clear
condition lacked a lawful bounded proof.

Under the existing two-fixture authorization, R1 remediation 01 may correct
only those two contract defects. It expressly permits one `copy.copy(authority)`
and one literal `object.__setattr__(copied_authority, "venue", applied.book)`
after the internal closure has returned APPLIED and all guards pass. It also
requires the terminal fixture itself to own a fixed, APPLIED-only public
claim/discovery/terminal-observation/final-canonical-fact/reducer chain from an
exact clean claim before entering the temporary hook or sole internal reducer
call. That source-proven chain replaces neither a private reconciliation reader
nor a history scan.

R1 remediation 01 creates no third fixture, no new private production access,
no public API, no production or test implementation, and no operational
authority. It remains DRAFT/preflight-only until a fresh exact independent
review returns `ACCEPT` with P0=0/P1=0. The unchanged paired E2/E3 93%
exact-head condition and every standing safety exclusion remain in force.

The exact independent R1 remediation 01 result
`8654e55a40dc6215c1f860ff87f9751e1d6d1c0e03f374c3a4a8e544f769945f`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. It accepted the two named
fixture repairs but found that public sibling venue observations cannot install
their evolved book into opaque authority before target bootstrap under the
two-fixture allowance. This result is retained negative preflight evidence;
WO-0152 remains DRAFT and no E3 test work, activation, or third test-only
fixture is authorized by this index.

## WO-0152 R2 sibling-history correction - authorized 2026-08-07

After the retained R1 remediation 01 result
`8654e55a40dc6215c1f860ff87f9751e1d6d1c0e03f374c3a4a8e544f769945f`
identified the pre-bootstrap sibling-history constructibility P1, Ameen
authorized Codex to address issues arising in flight under the standing safety
and scope exclusions. That authority is applied only to a narrow WO-0152 R2
draft/freeze/review correction.

R2 may extend the already named `_serving_environment_predecessor_fixture`;
it may not add a fixture or production/public capability. After its existing
six-field deny-only-to-serving setup, the helper may own one fixed public
same-account OTHER-symbol generic BUY/claim/venue/canonical-FILL chain. Only
after exact public APPLIED, identity, consistency, reconciliation, binding,
target-unbound, and original-isolation guards, it may make one additional
copied-authority literal `venue` installation from the final public venue
transition. A pure public target-bootstrap assertion follows the installation
and creates no additional authority.

This models the intentionally deferred M2 adapter-composition boundary for
test-only E3 proof. It grants no execution, controller, currentness, effect,
claim, broker, runtime, persistence, actor, API, or operational authority. A
replacement R2 freeze and independent exact `ACCEPT` with P0=0/P1=0 remain
required before WO-0152 activation or any E3 test implementation. The paired
E2/E3 unchanged 93% exact-head Python 3.11/3.12 closeout and every standing
exclusion remain in force.

## WO-0152 R2-R1 activation-gate correction - 2026-08-07

Before a reviewer returned any result, the first R2 candidate was stopped: the
current work order still named the superseded R1 acceptance in its future
activation condition. `result-r2.md` remains absent. The R2 disposition,
contract, request, and manifest remain retained unaccepted evidence; no
semantic, source, test, or operational conclusion is drawn from them.

Under the same in-flight issue-resolution authority, R2-R1 corrects only that
stale future-gate reference and records its own exact lifecycle paths. It
requires a fresh independent R2-R1 `ACCEPT` with P0=0/P1=0 before any WO-0152
activation. It preserves all R2 sibling-history constraints, every original
scope exclusion, and the paired E2/E3 unchanged 93% exact-head closeout.

## WO-0152 R2-R2 current-gate and boundedness-tripwire correction - 2026-08-07

R2-R1 independently returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0, at result
SHA-256 `098b2a3791505064406cd1087a654dc89a3a96d9b42906d7ec491cb4bca5bae9`.
Its sole finding was that two active PKL clauses still named an R2 rather than
R2-R1 activation result. During the same bounded static constructibility pass,
the exact public tripwire required for the already mandated E3 boundedness
proof was found missing from the static exception table; it must include the
history-materializing public `VenueRecoveryBook.effect` method as well as the
named collection/index materializers.

Under the user's existing in-flight issue-resolution authorization, R2-R2 may
correct only those current activation predicates and freeze one named,
public-only, restoring boundedness test tripwire. It preserves all R2/R2-R1
sibling-history, fixture, terminal-certification, public-API, and closeout
constraints. Only a fresh independent R2-R2 `ACCEPT` with P0=0/P1=0 may
activate WO-0152. No test implementation, production/API, database, SQL/DDL,
runtime, broker/network, credential, CI workflow, M2, merge, deletion,
cleanup, force-push, or rebase authority is added.

## WO-0152 R2-R3 static-exception consistency correction - 2026-08-07

Before an independent R2-R2 verdict, the author found that its broad static
prohibition would reject inherited exact operations in the existing environment,
approved-mandate, and terminal-parent fixtures. It also treated the public
keyed `SeenFactIndex.observation_at` method as a property. `result-r2-r2.md`
remains absent; the R2-R2 packet is retained unaccepted evidence.

R2-R3 corrects only those static-table contradictions. It retains the exact
sixteen-member public boundedness tripwire: a source-level adjudication
confirmed `VenueRecoveryBook.effect` remains trapped because it materializes
retained per-effect contradiction history. R2-R3 permits only the inherited
lexical fixture exceptions and fourteen property-shaped/two method-shaped
restoring traps; it adds no fixture, public API, production capability, or
operational authority. Only a fresh independent R2-R3 `ACCEPT` with P0=0/P1=0
may activate WO-0152. Every standing exclusion and paired E2/E3 unchanged 93%
exact-head closeout remains in force.

## WO-0152 R2-R3 independent acceptance and documentation-only activation - 2026-08-07

The exact R2-R3 replacement contract SHA-256
`881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`,
candidate manifest SHA-256
`ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`,
and independent result SHA-256
`8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`
are controlling. The independent result is `ACCEPT`, P0=0/P1=0/P2=0.

Under the earlier narrow coverage-gate ordering authorization and the standing
scope exclusions, WO-0152 is activated only for the named test-only E3 proof
layer. Its documentation-only activation SHA must be recorded before test
source is created. WO-0151 remains `REVIEW`; run #741 remains functional/static
success and 91.34% coverage-only negative evidence; paired E2/E3 exact-head
Python 3.11/3.12 success at the unchanged 93% gate remains mandatory. This
adds no production/API, runtime, database/SQL/DDL, broker/network, credential,
M2, merge, deletion, cleanup, force-push, or rebase authority.

The exact documentation-only activation commit is
`a3ceee237d8635f280bd6f200f492bef919170f9`. A normal branch push reported
`a2b84ab..a3ceee2` to `origin/codex/arch-reset-2026-07-r1`. A later non-mutating
live `ls-remote` query could not acquire Windows credentials; this record relies
on the successful push result, does not claim an independent live-ref query, and
uses no credential workaround. No E3 test source exists at this reconciliation
point.

## WO-0152 R2-R4 fixed mandate-schedule re-gate - authorized 2026-08-07

After R2-R3 activation, the first permitted public E3 controls were created as
an uncommitted local baseline. A focused constructibility pass found that the
accepted one-lexical-mint/no-loop fixture rule cannot construct distinct A/B/C
sealed bindings, and its A/B/C-only configuration cannot support the required
32-generation serial proof without prohibited market-stream reuse.

Ameen authorizes R2-R4 to replace only that approved-mandate fixture rule with
one zero-argument, test-only, pre-genesis immutable 32-entry schedule. A, B,
and C remain first; every entry must use distinct acquisition/protection
identities and a distinct approved MarketStreamGenerationId while sharing the
fixed scope, session, complete terms, and equal EmergencyRecoveryCompatibility.
One statically bounded loop over the fixed literal schedule may exercise one
lexical private dual-mandate mint call once per entry. Static and behavioral
controls must prove cardinality, fixed inputs, uniqueness, no caller input,
no aliases/wrappers/dynamic targets/post-genesis invocation, and no other
private access.

R2-R4 preserves all R2-R3 environment, terminal, boundedness, provenance,
and safety restrictions. It permits no production/API/runtime, database or
SQL/DDL, broker/network/credential, CI-workflow, M2, merge, deletion, cleanup,
force-push, or rebase authority. A fresh immutable R2-R4 manifest and
independent P0=0/P1=0 ACCEPT are required before further E3 test expansion.
The partial local test baseline is retained but is not R2-R4 acceptance
evidence. The paired E2/E3 unchanged 93% exact-head closeout remains mandatory.

## WO-0152 R2-R5 duplicate-stream-probe re-gate - authorized in-flight correction 2026-08-07

The independent exact R2-R4 preflight result
`48079e3b54beedddbb56382de2b05f49e6f887e2173c17d24e6131de0bce1889`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. It confirmed the positive
32-mandate schedule is bounded, but found that its all-unique-stream rule and
sole schedule-loop mint cannot construct the distinct sealed A-stream-reuse
probe required for a failure-capable public nonadjacent-reuse control.

Under Ameen's standing authorization to resolve in-flight root-level issues
within the existing WO-0152 safety boundary, R2-R5 may replace only that
probe-construction clause. It retains the 32 unique schedule and its one
bounded loop mint, and adds one zero-argument, test-only, pre-genesis
`_nonadjacent_duplicate_stream_probe_mandate_fixture`. The fixture may use exactly one fixed literal
private dual-mandate mint to return one otherwise complete public mandate with
fresh acquisition/protection/binding identities and the same literal stream as
A. It is usable only by the named A -> B -> A-stream control and grants no
caller-shaped configuration, production/API/runtime, controller, effect,
claim, broker, persistence, or actor authority.

R2-R5 requires a fresh immutable manifest and independent `ACCEPT` at
P0=0/P1=0 before further E3 test expansion. All R2-R3/R2-R4 retained evidence,
the partial baseline, exclusions, and paired E2/E3 unchanged 93% exact-head
closeout remain in force.

## WO-0152 R2-R5 independent acceptance - 2026-08-07

The exact R2-R5 documentation-only candidate independently `ACCEPT`ed at
P0=0/P1=0/P2=0. Its contract SHA-256 is
`79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e`, its
manifest SHA-256 is
`3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946`, and
its independent result SHA-256 is
`f3c86daa71a36108bb2757f853d922e992c7c77eed4d7d7626b5e9091e3d5245`.

R2-R5 therefore permits only the active work order's existing test-only E3
scope after this acceptance publication is committed and its exact SHA
reconciled. It does not authorize production/API/runtime, database/SQL/DDL,
broker/network/credential, CI-workflow, M2, merge, deletion, cleanup,
force-push, or rebase work. The public duplicate-stream control remains a
required E2-disagreement detector: if it admits the valid probe, preserve the
trace and return bounded E2 remediation rather than changing E3 or production
under this acceptance.

## WO-0152 R2-R5 acceptance-publication SHA reconciliation - 2026-08-07

Documentation-only commit `ef5e53a5d49e189942545f52b7784ad7648fbf28` published
the exact accepted R2-R4/R2-R5 packet. This append-only reconciliation records
that immutable publication SHA before resumed E3 work. It grants only the
already active, test-only R2-R5 scope; every production/API/runtime, database/
SQL/DDL, broker/network/credential, CI-workflow, M2, merge, deletion, cleanup,
force-push, and rebase exclusion remains unchanged.

## WO-0152 FR-08 return and WO-0151 R12 root remediation - 2026-08-07

The first accepted WO-0152 R2-R5 public duplicate-stream control produced a
real implementation disagreement with the accepted ADRs. The exact frozen
evidence is `work/review/REV-0059/evidence.md`, SHA-256
`d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`; its
test snapshot was SHA-256
`1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`.
The control establishes a valid A -> B -> fresh binding carrying retired A's
MarketStreamGenerationId. It expected `REFUSED` but the kernel returned
`APPLIED` because successor admission checks only the immediately prior stream.

This confirms a bounded WO-0151 E2 P1 against existing ADR-020 R2 and ADR-021
R2 semantics; it does not amend either ADR or authorize broader architecture.
WO-0152 remains active but is paused at its mandated FR-08 boundary. WO-0151
is effectively reopened only for R12 RED preflight and, after a fresh exact
independent P0=0/P1=0 `ACCEPT`, a limited pure remediation: one private,
sealed, non-enumerable direct MarketStreamGenerationId-to-generation provenance
index owned by `GenerationRegistry`. The index must be seeded at genesis,
checked before successor registration, atomically extended on valid successors,
and retained across record replacement. Controller history, authority duplicate
state, scans, public APIs, runtime/persistence, and all previously excluded
operational surfaces remain out of scope. The paired E2/E3 93% exact-head
Python 3.11/3.12 closeout is unchanged.

## WO-0151 R12 independent RED acceptance - 2026-08-07

The exact R12 controller-lifetime stream-provenance packet independently
`ACCEPT`ed with P0=0/P1=0/P2=0. Its contract SHA-256 is
`36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`, its
manifest SHA-256 is
`a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`, and
its result SHA-256 is
`0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5`.

This acceptance confirms the existing ADRs already authorize the root repair:
one private immutable sealed direct MarketStreamGenerationId-to-generation
route map within `GenerationRegistry`, direct candidate lookup before successor
authority registration, atomic successor insertion, retention across record
replacement, and fail-closed authentication. It introduces no new ADR,
public API, controller collection, authority duplicate, scan, runtime,
persistence, broker, database/SQL/DDL, CI-workflow, M2, merge, deletion,
cleanup, force-push, or rebase authority. A documentation-only activation and
exact-SHA reconciliation still precede implementation. WO-0152 remains paused
until focused R12 implementation acceptance; paired E2/E3 exact-head 93%
Python 3.11/3.12 closeout remains mandatory.

## WO-0151 R12 activation-delta integrity correction - 2026-08-07

The immutable R12 semantic manifest predates later current-posture and
acceptance records. It is retained unchanged and does not silently cover them.
Before publication, a separate exact activation-delta manifest and independent
P0=0/P1=0 acceptance must therefore verify only the named work-order, PKL,
ledger, ratification, and activation-disposition records. The correction also
makes the top-level WO-0151 authority explicitly historical R11/R11-R1
provenance; it grants no present R12 source/test authority.

After that focused acceptance, exactly one documentation publication commit
and one constrained exact-SHA reconciliation may occur. The reconciliation may
only activate the frozen R12 `acquisition.py`/`test_acquisition.py` scope and
record the first commit's SHA; it cannot alter R12 semantics, public/API scope,
E3's FR-08 pause, the paired 93% closeout, or any existing safety exclusion.

## WO-0151 R12 activation-delta acceptance and publication - 2026-08-07

The separate R12 activation-delta manifest
`59ab3d16a4057fe2d3e763d5909ba1751ba0266453551ba07830b2c872bb68f4`
independently `ACCEPT`ed at P0=0/P1=0/P2=0; its result is
`b8382a504c8bb9ac5456067e758a81ec42f9f546ed6194fae4f31b814378e28d`.
Documentation-only commit `a124b3cda866e2a5aaf99d4527e7b231dd4f675d`
published the accepted R12 packets. This exact-SHA reconciliation activates
only the frozen pure E2 R12 source/test path and no broader authority.

WO-0152 remains ACTIVE but paused until focused R12 implementation acceptance
and subsequent public detector confirmation. The R12 contract, public surface,
E3 evidence, 93% paired exact-head closeout, and every prior operational
exclusion remain unchanged.
