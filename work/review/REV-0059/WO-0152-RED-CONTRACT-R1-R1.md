# WO-0152 E3 RED contract R1 remediation 01

Status: REPLACEMENT CANDIDATE — DRAFT ONLY — NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling composite: WO-0152-RED-CONTRACT-R1.md plus this remediation 01

## 1. Retained result and exact amendment scope

This is a narrow replacement freeze after the independent R1 result
ACCEPT-WITH-CHANGES, P0=0/P1=2/P2=0, SHA-256
880a4f2f8874d9e14a77523301a400ef84d02893d421e48822dfb648aa249408.
R1 contract SHA-256
3b2ba052df61f8e128f82b4ee408568774ff8cdd62a815e4387a821ab6f9709b
remains controlling except where this document explicitly replaces it.

The R0 packet and its P1 result remain retained negative evidence. The R1
packet and its two P1 result remain retained negative evidence. Neither is
rewritten, deleted, or used to claim activation.

This remediation adds no third fixture, private production name, public API,
production change, runtime capability, or authority. It corrects only:

1. the exact source allowlist for the already authorized copied-authority venue
   replacement; and
2. the source-proven public-chain proof that effect reconciliation is clear
   before the already authorized temporary internal parent closure.

All other R1 functional requirements, two-batch limit, coverage-order rule,
paired 93% closeout, safety boundaries, allowed paths, and exclusions remain
unchanged.

## 2. Replacement terminal-parent fixture contract

### R1-R1-01 — exact copied-state operation

The terminal fixture’s exact static exception set now expressly permits:

- exactly one copy.copy(authority) occurrence; and
- exactly one object.__setattr__(copied_authority, "venue", applied.book)
  occurrence.

The copy and setter occur only inside
_certified_terminal_parent_fixture, only after all public-chain guards pass and
the internal transition returns APPLIED with the required CLOSED postcondition.
The setter target is the copied authority object, the field-name literal is
exactly "venue", and no original authority or any other field may be written.

The self-source AST control MUST reject a second copy call, a second setter, a
dynamic target, a dynamic field name, a write to the original authority, or a
write to any field other than literal "venue".

### R1-R1-02 — locally owned reconciliation-clear proof

The terminal fixture MUST NOT accept a caller-supplied VenueRecoveryTransition,
VenueRecoveryBook, ExecutionSnapshot, tuple of transitions, arbitrary
candidate object, or generic pre-close state. It receives only the exact
APPLIED AcquisitionControllerTransition produced by the local fixed rooted-A
create-and-claim builder. That builder uses the fixed target mandate, known
effect, claim, scope, and one known leg from the R1 scenario.

The fixture itself owns the complete fixed ordered public suffix from that
claim result to the private close:

1. exact fresh acquisition claim result;
2. public discovery for the one fixed leg;
3. every fixed public outcome and canonical fact required before terminal,
   each applied to the immediately preceding local book/execution result;
4. public terminal observation for that same leg;
5. one exact final canonical FILL, TRADE_CORRECT, or TRADE_BUST that produces
   the required flat final execution, followed immediately by
   reduce_acquisition_controller on that exact transition so its returned
   authority, venue, execution, and controller are current together; and
6. the one authorized private parent closure only after all guards below.

The exact suffix is straight-line and fixed in the source. It must not be
parameterized by caller-provided transition objects, input identifiers, scopes,
effects, legs, facts, or extra commands. Every public reducer/composite result
in the suffix must be its exact output type and APPLIED. Every next public
operation consumes exactly the immediately preceding result’s book, execution,
controller, and authority as applicable. No public terminal observation may
follow the final canonical fact/reducer pair: that pair is the one lawful
authority-and-book alignment immediately before the private closure.

The claim base is decisive: the accepted specialized claim gate requires a
clear target effect. Effect-level reconciliation append paths produce
RECONCILIATION_REQUIRED rather than APPLIED. Therefore an exact locally owned
APPLIED-only suffix from that claim cannot acquire target-effect reconciliation.
The fixture also independently requires final execution raw quantity zero,
PositionIntegrity.CONSISTENT, and account_reconciliation_required false.

Immediately before the temporary hook, the fixture MUST prove through public
direct readers that:

- the locally carried authority venue is exactly the locally carried book and
  execution is exactly the local suffix output;
- the target effect has the fixed effect scope, exact claim occurrence,
  AcceptanceSetState.OPEN, and no existing acceptance proof;
- the exact known leg has the matching direct owner, no active attempt, and an
  exact terminal closure head;
- all scope/session/currentness and public acquisition-context checks required
  by the R1 rooted-A scenario are current; and
- the proof is exactly CONTRACT_COMPLETE_RESPONSE, binds that exact effect
  scope and claim, uses the one fixed EvidenceReference, and uses the one
  fixed 32-byte digest.

Only after those guards may the fixture enter the one temporary
patch.object hook and call its one lexical _apply_venue_input site. It requires
APPLIED with zero quantity delta, then requires public CLOSED parent proof
before making the one copied-authority venue replacement.

### R1-R1-03 — required negative controls

The E3 module MUST add all of these failure-capable controls:

1. reconciliation injection: substitute a same-effect conflicting public
   RecordBrokerFillEvidence or RecordBrokerRevisionEvidence in the locally
   owned suffix; require RECONCILIATION_REQUIRED and prove the test-local
   entered_private_transition marker remains false, the hook is not entered,
   no venue replacement is returned, and every original object is unchanged;
2. splice and order rejection: an AST source specimen adding a supplied
   transition/book/execution parameter, an extra/missing suffix command, or a
   terminal observation after the final canonical fact/reducer pair must fail
   the source control;
3. guard ordering: an AST source specimen moving the patch/private call above
   the APPLIED/current/flat/reconciliation guards must fail;
4. copied-state isolation: the original authority/book remains unchanged while
   only the copied authority receives the resulting venue; and
5. ordinary terminal negative cases: wrong effect/claim/scope/leg, a non-OPEN
   parent, active leg, nonterminal leg, inconsistent/nonflat execution,
   account reconciliation required, proof mismatch, or failed public suffix
   result all refuse before the hook/private transition.

These controls use public lifecycle inputs, test-owned source specimens, and a
test-local marker only. They add no private reconciliation reader, history
scan, production mutation, or test seam.

## 3. Clarified sibling-history and closure-count boundaries

The FR-01 unrelated-symbol account history is constructed before target
bootstrap only. From the fresh serving environment, the fixed same-account
OTHER symbol may use public CreateBrokerEffect(BUY), public ClaimEffect, public
venue discovery/status observations, and public canonical broker evidence with
its own exact OTHER execution snapshot. It uses no acquisition mandate, no
private reducer, and no certified-parent fixture. The target is then
bootstrapped from the bounded current sibling execution source.

The generic CreateBrokerEffect(BUY) refusal control applies after the target
has its active bootstrap/currentness reservation. It must not misclassify the
pre-bootstrap OTHER-symbol public history as target-acquisition authority.

The one lexical terminal closure site may execute at most once in each isolated
rooted scenario. The separate aborted A -> B -> C serial scenario requires no
terminal fixture invocation. No loop, generated rule, or long-sequence path
may invoke the private closure site.

## 4. Replacement static allowlist table

The R1 section 3.5 table is replaced by this exact-set table:

| Fixture or local builder | Exact exception | Static limit |
| --- | --- | --- |
| _serving_environment_predecessor_fixture | copy.copy and object.__setattr__ | only the six named pre-genesis environment fields |
| _approved_acquisition_mandates_fixture | app.execution_core.acquisition._mint_dual_mandate_binding | one lexical AST call site; fixed A/B/C configuration before genesis only |
| _certified_terminal_parent_fixture | AcceptanceProof, AcceptanceProofKind, CloseAcceptanceSet, app.execution_core.venue._apply_venue_input, temporary patch.object of _external_acceptance_closure_is_certified, copy.copy, and object.__setattr__ | one lexical private reducer site, one literal patch target, one fixed digest, one copied-authority literal venue write, and a locally owned APPLIED-only public suffix |
| _build_rooted_parent_public_suffix | no private production access | fixed straight-line public suffix only: terminal observation precedes the final flattening canonical fact/reducer pair; no supplied transition/book/execution parameters or dynamic commands |

The source control MUST reject every other private production import/access,
private value construction, object.__new__, history materializer, dynamic
lookup, import from tests.*, post-setup production object mutation, and all
private calls outside the two user-authorized fixtures. It must distinguish
test-local helper names from production-private names and require the guards
to dominate the one hook/private reducer block.

## 5. R1-R1 acceptance and stop rule

The independent reviewer must review the R1 + R1 remediation 01 composite
against the user authorization and all retained R0/R1 evidence. It must verify
that no E3 test file exists, no test runs, no production/test source changes,
and no new private capability is present at this preflight stage.

Only an exact independent ACCEPT with P0=0/P1=0 permits the separately
authorized test-only WO-0152 activation and implementation. Any P0/P1 keeps
WO-0152 DRAFT. This amendment does not satisfy, alter, or waive the paired
E2/E3 unchanged 93% exact-head closeout requirement.
