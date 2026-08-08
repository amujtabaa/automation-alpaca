# WO-0152 E3 RED contract R2-R5 - duplicate-stream negative-probe correction

Status: REPLACEMENT CANDIDATE - ACTIVE-WO RE-GATE ONLY - NOT ACCEPTED  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling retained composite: R1, R1-R1, R2, R2-R1, R2-R2, R2-R3, R2-R4,
and this R2-R5

## 1. Narrow replacement and retained boundaries

R2-R5 replaces only R2-R4's missing construction rule for the named public
nonadjacent market-stream reuse control. The R2-R4 positive schedule remains
exactly a 32-entry literal schedule with unique streams and one bounded loop
mint. Every accepted R2-R3/R2-R4 rule for the environment predecessor,
terminal-parent closure, rooted public suffix, 16-target boundedness tripwire,
partial-test isolation, source policy, provenance, and safety exclusions
remains controlling.

This remains a documentation-only active-work-order re-gate. The local partial
E3 test module is a retained isolated baseline, not candidate implementation or
acceptance evidence. No schedule, probe, serial, replay, mutation, or
boundedness source may be added or changed until this exact R2-R5 candidate
receives independent `ACCEPT` at P0=0/P1=0.

No production source, public API, runtime behavior, database or SQL/DDL work,
broker/network/credential activity, CI workflow change, M2 work, merge,
deletion, cleanup, force-push, or rebase is authorized.

## 2. Retained positive 32-mandate schedule

`_approved_acquisition_mandates_fixture` remains the sole producer of the
positive schedule defined by R2-R4. It is zero-argument, test-only, and
pre-genesis; it returns only `tuple[AcquisitionMandate, ...]` containing the
32 literal schedule entries A through AF. It returns no binding, controller,
authority, effect, claim, broker object, actor, runtime object, or callable.

All 32 schedule entries retain literal, mutually unique acquisition-mandate
identities, protection-mandate identities, and canonical lowercase 64-hex
market-stream identities. They retain the exact fixed scope, session, complete
terms, and equal `EmergencyRecoveryCompatibility` commitment. A/B/C remain
indices zero through two. The sole schedule mint call remains direct and
unconditional inside its one bounded loop over the fixed literal schedule,
executes once per entry, and is never callable through alias, wrapper, dynamic
lookup, branch, exception path, nested loop, early exit, or caller input.

The positive schedule remains the only input to the 32-generation aborted/no-
root chain. The duplicate-stream probe below is not a schedule member, does
not count toward its 32 entries, and must never be used in that positive chain.

## 3. One fixed nonadjacent duplicate-stream negative probe

The E3 module may define exactly one additional zero-argument, test-only,
pre-genesis helper:

`_nonadjacent_duplicate_stream_probe_mandate_fixture() -> AcquisitionMandate`.

It returns exactly one immutable public `AcquisitionMandate`; it returns no
`DualMandateBinding`, controller, authority, effect, claim, broker object,
actor, runtime object, callable, or caller-supplied configuration.

The helper owns one module-local literal fixed probe descriptor. Its
acquisition-mandate ID and protection-mandate ID must be nonblank, unique, and
distinct from every positive schedule entry. It must use the same fixed scope,
session, complete acquisition terms, and
`EmergencyRecoveryCompatibility` commitment as the schedule. It constructs
its own public `ProtectionMandate` and `EvidencePolicy`.

Its literal lowercase 64-hex `MarketStreamGenerationId` must be byte-for-byte
equal to schedule entry A's literal stream and different from entry B's literal
stream. It must not obtain its stream, IDs, binding, descriptor, or terms by
indexing, unpacking, copying, replacing, mutating, or otherwise deriving an
existing mandate, binding, descriptor, controller, authority, or state.

The helper may contain exactly one direct, unconditional lexical call to
`acquisition._mint_dual_mandate_binding(...)`. That call must occur outside
every loop, branch, exception handler, context manager, lambda, wrapper,
alias, dynamic lookup, or nested function. It mints only the binding used by
the returned probe mandate. The helper may perform no other private production
access, production-object mutation, copy, replacement, patch, or test import.

Together, the positive schedule fixture and this probe fixture are the only
permitted private-minter call sites in the E3 module: the schedule site
executes exactly 32 times over the schedule; the probe site executes exactly
once. No other code may invoke, reference, alias, wrap, or dynamically resolve
the private minter.

## 4. Required public control and stop boundary

One named public control must build both the positive schedule and duplicate-
stream probe before target genesis. It then uses only public reducers and
projections to establish a valid aborted/no-root A -> B successor path and
attempt B -> duplicate-A-stream.

Immediately before that final attempt, the control must prove:

1. A -> B applied and B is the live predecessor;
2. the probe's acquisition ID, protection ID, and binding commitment are each
   distinct from A, B, and every positive schedule member;
3. the probe stream equals A's stream and differs from B's stream;
4. scope, session, terms, compatibility, bootstrap, admission, authority,
   controller head, and ordinal inputs are authentic, current, and otherwise
   valid; and
5. no generic BUY, terminal fixture, private closure, test-object mutation,
   or history scan participates.

The final transition must refuse without creating a generation, effect, claim,
or registration receipt and must retain the predecessor state, authority,
venue, execution, and protection by identity. The direct control is
failure-capable because it independently proves every other successor
coordinate valid; its only prohibited successor relation is the deliberately
reused nonadjacent stream authority.

If current E2 behavior admits the final transition, E3 must preserve the exact
minimized trace and return bounded E2 semantic remediation. It must not
weaken the assertion, mark it expected failure, change the E3 oracle, reuse a
stream in the positive chain, introduce a one-off E3 guard, or modify
production code. Any E2 correction must maintain direct bounded ownership and
must not use a history scan.

## 5. Required source and behavior controls

The self-source control must preserve every R2-R3/R2-R4 rule and additionally
prove all of the following:

1. exactly one zero-argument probe fixture with the exact return surface and
   one literal fixed probe descriptor;
2. exactly two direct private-minter call expressions in the whole E3 module;
3. the schedule minter is the sole minter in the one literal 32-entry loop,
   while the probe minter is the sole non-loop minter in its exact helper;
4. the probe IDs are literal, fresh, and distinct from all 32 positive IDs;
5. the probe stream is literal, equal to A, and unequal to B, while all 32
   positive schedule streams remain mutually unique;
6. the probe is neither returned by the positive tuple nor consumed by the
   32-generation positive chain; and
7. no caller input, schedule indexing/unpacking, copy, replace, alias,
   wrapper, dynamic attribute lookup, branch-selected descriptor, or
   production-object mutation participates in probe construction.

Failure-capable source-only specimens must separately reject a parameterized
or second probe helper; a third/outside/aliased minter; a probe with a
nonliteral or schedule-derived stream; probe reuse of A's mandate or binding;
duplicate probe IDs; a probe returned in the positive tuple; probe use in the
positive chain; and post-genesis fixture invocation. The existing R2-R3
negative specimens for private access, patching, direct-reader traps,
environment installation, terminal certification, and boundedness remain
required.

Behavior controls must prove the 32-valid-mandate schedule separately from the
one negative probe. They must not claim that a schedule's literal uniqueness
alone proves kernel-wide stream ownership; the named public probe is required
to detect a disagreement in E2 behavior.

## 6. Re-gate and evidence rules

The independent reviewer must re-derive this R2-R5 composite against the user
authorization, retained R0 through R2-R4 packet chain, active WO-0152,
accepted ADRs, provenance, and current source. It must verify that:

- all R2-R4 artifacts and result remain byte-identical;
- the partial E3 module remains the recorded isolated untracked baseline and
  is not cited as R2-R5 acceptance evidence;
- no production or existing test file is changed by this documentation-only
  candidate; and
- all exclusions and the paired E2/E3 unchanged 93% closeout remain unchanged.

The review is static only. It must not run tests, database-capable fixtures,
SQL/DDL, network, broker, credential, runtime, CI, or coverage commands. Only
an independent exact `ACCEPT` at P0=0/P1=0 permits further E3 test
implementation under this replacement rule.
