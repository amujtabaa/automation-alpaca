# WO-0152 E3 RED contract R2 — sibling-history environment handoff

Status: REPLACEMENT CANDIDATE — DRAFT ONLY — NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling composite: WO-0152-RED-CONTRACT-R1.md,
WO-0152-RED-CONTRACT-R1-R1.md, and this R2

## 1. Retained result and exact R2 scope

The R0, R1, and R1 remediation 01 packets/results remain immutable retained
preflight evidence. R1 remediation 01 result SHA-256
`8654e55a40dc6215c1f860ff87f9751e1d6d1c0e03f374c3a4a8e544f769945f`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. It accepted the R1/R1
terminal fixture repairs and retained only the pre-bootstrap canonical
same-account sibling-history bridge.

The user authorized resolving issues arising in flight under all existing
safety exclusions. R2 corrects only that P1 by extending the existing
`_serving_environment_predecessor_fixture`. It does not add a new fixture,
private production helper, public API, production change, test implementation,
runtime capability, or production authority.

All R1/R1 requirements remain controlling except the R1 section 3.2
environment-fixture limit and R1/R1 section 3 sibling-history/static-table
language explicitly replaced below. The paired E2/E3 unchanged 93% closeout,
two-batch limit, safety core, allowed paths, and exclusions remain unchanged.

## 2. R2 extension of the existing environment predecessor

### R2-01 — exact fixed public sibling lifecycle

`_serving_environment_predecessor_fixture` first performs its existing
single copied deny-only genesis setup and exactly six literal environment
writes: phase `SERVING`, mode `ACTIVE`, supervisor fence
`PAPER_MUTATION_ELIGIBLE`, kill `False`, one fixed `SessionId`, and one fixed
positive `RequestBudget`.

Inside that same helper only, it then owns one fixed, straight-line public
OTHER-symbol lifecycle. The OTHER `PositionScope` has the exact same broker,
environment, and account as the fixed target scope but a different fixed
symbol. It uses no acquisition mandate, acquisition controller, private
reducer, existing test fixture, caller-supplied object, dynamic command, loop,
or state-machine command.

The exact public sequence is:

1. `apply_execution_authority_input` with one fixed generic
   `CreateBrokerEffect(BUY OTHER)`;
2. `apply_execution_authority_input` with the exact resulting effect and one
   fixed `ClaimEffect`;
3. `apply_venue_recovery_input` with one fixed
   `RecordTransportOutcome(ACKNOWLEDGED)`;
4. `apply_venue_recovery_input` with one fixed `DiscoverVenueLeg` for the
   exact claimed OTHER effect and one fixed OTHER leg;
5. `apply_venue_recovery_input` with one fixed
   `ObserveVenueStatus(NEEDS_REVIEW, cumulative_quantity=0)` for that leg; and
6. `apply_venue_recovery_input` with one fixed `RecordBrokerFillEvidence`
   carrying one exact canonical BUY `FILL` for that same effect, leg, and
   OTHER symbol.

Every step consumes exactly the immediately preceding local authority, book,
and/or execution output as applicable, has its exact public output type, and
must be `APPLIED`. The final fill must have `quantity_delta == 1`; no later
venue observation or fact is allowed in this helper.

### R2-02 — one bounded adapter-handoff representation

Only after the complete public chain and all pre-install guards below, the
helper may make exactly one additional `copy.copy(final_authority)` and exactly
one literal `object.__setattr__(copied_authority, "venue",
final_transition.book)`. `final_authority` is the exact authority returned by
the local public claim step. The original authority, original book, original
execution, and every predecessor object remain unchanged. The copied authority
differs only at `venue` and that value is exactly the final public transition's
`book`.

Before that one copied-state write, the helper MUST prove through public
values/readers that:

- every local authority/venue result is `APPLIED`, and the final fill has
  `quantity_delta == 1`;
- the exact OTHER execution is `CONSISTENT`, has no account reconciliation
  requirement, and is nonempty only through the fixed canonical fact;
- `final_book.execution_registry_count` and
  `final_book.execution_registry_commitment` exactly equal the final
  execution's seen-facts count and commitment, and
  `final_book.execution_binding(OTHER_SCOPE)` is present;
- the OTHER scope is same-account/different-symbol and the target binding is
  absent; and
- the original authority/book/execution identity and commitment observations
  still equal their pre-chain values wherever the public lifecycle did not
  return a replacement.

Immediately after that one copied-state write, the helper MAY invoke the pure
public `refresh_acquisition_context(copied_authority, final_execution,
TARGET_SCOPE)` only as a constructibility assertion. It MUST require exact
`UNBOUND_BOOTSTRAP`, non-null returned authority/execution, and one zero-delta
bootstrap transition. It MUST retain and return the exact copied predecessor
and exact final sibling execution—not the refresh result—and may not add a
copy, setter, command, or state replacement because of that assertion.

The helper returns only the copied predecessor and exact final sibling
execution needed by the later public target bootstrap. It returns no book,
venue transition, effect, claim, leg, mutable authority reference, broker
object, actor, runtime object, or generic installer.

This is a test-only representation of deferred M2 adapter composition, not
execution, controller, currentness, effect, claim, broker, persistence,
runtime, or actor authority. It preserves the required nonempty same-account
sibling-history proof without creating a production seam.

### R2-03 — exact static limits and failure controls

The environment fixture has exactly two `copy.copy` calls: its existing
pre-genesis copied state and the one post-chain final-authority copy. It has
exactly seven `object.__setattr__` calls: the six listed environment fields
and the one literal `venue` write above. The terminal-parent fixture retains
its separate one-copy/one-literal-venue-write limit from R1/R1.

The E3 source control MUST reject:

1. any third copy or eighth setter in the environment fixture, any copy/setter
   outside the environment fixture or the terminal-parent fixture's separately
   enumerated R1/R1 allowance, or a write to an original authority;
2. a nonliteral/dynamic field, setter target, or venue source other than the
   exact final public transition book;
3. a missing, extra, reordered, substituted, or caller-supplied lifecycle
   input; a loop, comprehension, generated command list, or state-machine
   invocation of this helper;
4. early installation before all APPLIED, direct-binding, consistency,
   reconciliation, target-unbound, and identity guards;
5. private production imports/access other than the exact lexical names,
   fixtures, and call-site limits enumerated in the replacement static
   allowlist below; `object.__new__`, `_state_with`, dynamic lookup, history
   materializers, or imports from `tests.*`; and
6. cross-account, target-symbol, mismatched effect/claim/leg/fact, non-APPLIED,
   reconciliation-required, non-consistent, or changed-payload variants that
   could otherwise reach the copied-state write.

Named behavioral negative controls MUST prove each rejection prevents the
post-chain venue installation and preserves every original object. The existing
raw deny-only and post-target-bootstrap generic target-BUY refusal controls
remain mandatory; the permitted pre-target OTHER generic BUY must not be
mischaracterized as target-acquisition authority.

## 3. Replacement static allowlist table

The R1/R1 section 4 table is replaced only as follows:

| Fixture or local builder | Exact exception | Static limit |
| --- | --- | --- |
| _serving_environment_predecessor_fixture | copy.copy and object.__setattr__ | exactly two copies and seven literal setters: the six fixed pre-genesis environment fields plus one post-chain copied-authority `venue` write from final_transition.book |
| _approved_acquisition_mandates_fixture | app.execution_core.acquisition._mint_dual_mandate_binding | one lexical AST call site; fixed A/B/C configuration before genesis only |
| _certified_terminal_parent_fixture | AcceptanceProof, AcceptanceProofKind, CloseAcceptanceSet, app.execution_core.venue._apply_venue_input, temporary patch.object of _external_acceptance_closure_is_certified, copy.copy, and object.__setattr__ | one lexical private reducer site, one literal patch target, one fixed digest, one copied-authority literal venue write, and a locally owned APPLIED-only public suffix |
| _build_rooted_parent_public_suffix | no private production access | fixed straight-line public suffix only: terminal observation precedes the final flattening canonical fact/reducer pair; no supplied transition/book/execution parameters or dynamic commands |

## 4. R2 acceptance and stop rule

The independent reviewer must re-derive this R2 composite against the user
authorization, retained R0/R1/R1R1 evidence, accepted ADRs, current work
order, and frozen source. It must verify that no E3 test file exists, no test
runs, no production/test source changes, and no additional capability is
present at this preflight stage.

Only an exact independent `ACCEPT` with P0=0/P1=0 permits the already
authorized test-only WO-0152 activation and implementation. Any P0/P1 keeps
WO-0152 DRAFT and requires the smallest root correction or a new human
boundary. R2 does not satisfy, alter, or waive paired E2/E3 93% exact-head
closeout.
