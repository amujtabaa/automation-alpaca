# WO-0152 E3 RED contract R2-R4 - fixed serial mandate schedule correction

Status: REPLACEMENT CANDIDATE - ACTIVE-WO RE-GATE ONLY - NOT ACCEPTED  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling retained composite: R1, R1-R1, R2, R2-R1, R2-R2, R2-R3, and this R2-R4

## 1. Narrow replacement and retained boundaries

R2-R4 replaces only the `_approved_acquisition_mandates_fixture` rule and
the connected fixed-A/B/C-only wording that made the required serial proof
nonconstructible.  Every accepted R2-R3 rule for
`_serving_environment_predecessor_fixture`,
`_certified_terminal_parent_fixture`,
`_build_rooted_parent_public_suffix`, and
`_forbid_live_acquisition_history_materialization` remains verbatim
controlling, including all sixteen boundedness targets and the fourteen
property/two method trap shapes.

This is an active-work-order re-gate for remaining E3 implementation.  The
existing local partial module is retained as an isolated baseline, not as
preflight evidence.  No schedule/minter/serial source may be added or changed
until this exact R2-R4 candidate receives independent ACCEPT at P0=0/P1=0.

No production code, public API, runtime behavior, database or SQL/DDL work,
broker/network/credential activity, CI workflow, M2 work, merge, deletion,
cleanup, force-push, or rebase is authorized.

## 2. Exact approved-mandate schedule

`_approved_acquisition_mandates_fixture` remains a zero-argument, test-only,
pre-genesis configuration fixture.  It returns only
`tuple[AcquisitionMandate, ...]`; it returns no binding, controller,
authority, effect, claim, broker object, actor, or runtime object.

The E3 module must define one module-local literal tuple named
`_E3_FIXED_MANDATE_SCHEDULE` containing exactly 32 immutable test-owned
entries in source order:

`A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z, AA, AB, AC, AD, AE, AF`.

Each literal entry must contain a nonblank unique acquisition-mandate ID, a
nonblank unique protection-mandate ID, and a distinct literal lower-case
64-hex `MarketStreamGenerationId`.  Entries A, B, and C are schedule indices
zero through two and remain the named short-trace mandates.  Values must not
be supplied by a caller, derived from controller state, concatenated,
unpacked, range-generated, comprehended, sliced, or function-generated.

Every resulting public mandate must bind the exact fixed target
`PositionScope`, fixed `SessionId`, complete fixed acquisition terms, and the
same exact `EmergencyRecoveryCompatibility` commitment.  Each entry must
construct its own public `ProtectionMandate` and `EvidencePolicy`, binding its
own distinct stream generation to the actual approved mandate rather than to
an unused descriptor.

## 3. One bounded private mint loop

The fixture may use canonical module import
`import app.execution_core.acquisition as acquisition` and exactly one
lexical direct call to `acquisition._mint_dual_mandate_binding(...)`.

That call must appear directly and unconditionally in the body of exactly one
ordinary `for entry in _E3_FIXED_MANDATE_SCHEDULE:` loop.  The loop may append
one matching public `AcquisitionMandate` to a test-local list per entry and
return its tuple.  It may not be nested, conditional, exception-wrapped,
lambda-wrapped, aliased, dynamically looked up, early-returned, broken,
continued, or invoked outside this fixture.  No other loop may invoke a named
fixture, private production name, patch, or post-setup production-object
mutation.  Other E3 loops must be finite test-owned loops bounded by the same
fixed 32-entry schedule or a literal slice of it and may use public reducers
only.

The fixture must prove exactly 32 returned mandates, positional correspondence
to the schedule, unique acquisition IDs/protection IDs/stream IDs/binding
commitments, exact binding-to-mandate correspondence, and common scope,
session, terms, and compatibility.  It must be invoked before any target
genesis, bootstrap, controller, effect, claim, fact, or stateful command.

## 4. Required schedule and architecture controls

The self-source control must parse the test module and prove:

1. exactly one literal 32-entry schedule and no dynamic/expanded entry source;
2. literal nonblank IDs and canonical 64-hex lower-case stream IDs, without
   duplicate acquisition, protection, or stream identities;
3. exact zero-argument fixture signature, one canonical acquisition import,
   one direct minter call, and exactly one direct loop over the schedule;
4. no `while`, nested/async loop, comprehension, range/enumerate/zip,
   alias/wrapper, branch, try/with, break, continue, or early return around
   the minter call; and
5. every R2-R3 private-access, mutation, patch, direct-reader, and
   boundedness-tripwire rule still holds.

Failure-capable source-only specimens must separately reject 31 or 33 entries;
duplicated identity or stream; dynamic or caller-supplied schedule; minter
alias, second/outside call, noncanonical target, conditional or nested-loop
call; early exit; post-genesis fixture invocation; and return of a binding
instead of the exact mandate tuple.  The manifest, rather than a duplicate
32-row AST expected-value table, supplies exact frozen schedule integrity.

The behavior controls must prove the 32 mandates are all distinct and that
A/B/C retain their named identities.  They must use a public aborted/no-root
successor chain for the 32-generation boundedness trace; that chain must not
invoke the terminal fixture, private closure, generic BUY, or a market-stream
reuse shortcut.  Rooted A/B/C and late-fact scenarios remain separate and
retain the one private terminal-closure cap.

A named public nonadjacent reuse control must attempt an A -> B -> A-stream
successor path and require refusal without a new generation, effect, claim,
or authority.  If current E2 behavior admits it, freeze the minimized trace
and return a bounded E2 semantic remediation.  The necessary root fix must
preserve sealed generation provenance and use direct bounded stream ownership;
E3 must not add a one-off test workaround or history scan.

## 5. Re-gate and evidence rules

The independent reviewer must re-derive this R2-R4 composite against the user
authorization, retained R0 through R2-R3 packet chain, active WO-0152,
accepted ADRs, provenance, and current source.  It must verify that:

- the prior R2-R3 artifacts remain byte-identical;
- the partial E3 module is the recorded untracked baseline and is not cited as
  R2-R4 acceptance evidence;
- no production or existing test file is changed by this documentation-only
  candidate; and
- all safety exclusions and the paired E2/E3 93% closeout remain unchanged.

The review is static only.  It must not run tests, database-capable fixtures,
SQL/DDL, network, broker, credential, runtime, CI, or coverage commands.
Only an independent exact `ACCEPT` with P0=0/P1=0 permits further E3 test
implementation under this replacement rule.
