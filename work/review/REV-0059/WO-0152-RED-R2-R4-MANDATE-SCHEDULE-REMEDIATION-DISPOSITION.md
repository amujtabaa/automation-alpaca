# WO-0152 E3 R2-R4 mandate-schedule remediation disposition

Status: DRAFT - RE-GATE ONLY - NOT ACCEPTED  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059

## Why a replacement correction is required

The accepted R2-R3 packet remains controlling historical evidence for the
environment predecessor, terminal-parent, and sixteen-member boundedness
tripwire rules.  After its documentation-only activation, the first permitted
E3 controls established a local, uncommitted public-contract baseline at
`tests/execution_core/test_acquisition_stateful.py`.  That baseline is
preserved unchanged and is not R2-R4 acceptance evidence.

Static constructibility review then found two linked R2-R3 fixture defects:

1. `_mint_dual_mandate_binding` mints one exact `DualMandateBinding`, while
   every distinct `AcquisitionMandate` needs its own matching sealed binding.
   R2-R3 permits one lexical private mint site but forbids every stated
   repetition mechanism, so it cannot construct even distinct A/B/C mandates.
2. E3 requires a real 32-generation serial proof.  A fixed A/B/C-only
   fixture cannot supply the distinct approved market-stream generations
   required by ADR-020 R2 and ADR-021 R2; cycling those three values would be
   an architecture violation, not a valid boundedness control.

The user authorized this narrow root correction and continued in-flight issue
resolution under every existing safety exclusion.  R2-R4 replaces only the
approved-mandate fixture rule with one statically bounded, fixed 32-entry
pre-genesis schedule.  It adds no production source, public API, runtime,
database, broker, credential, or operational capability.

## Retention and isolation

- R2-R3 contract, manifest, request, independent ACCEPT, activation records,
  and every prior R0 through R2-R3 packet remain byte-stable retained evidence.
- The partial untracked E3 module has SHA-256
  `E10E623230744F4A4C43CBC11CC0850562F32E8EE64286EFB5EF0BA2FF3D6B79`
  at this re-gate baseline.  It contains only the already permitted raw-genesis
  and sibling-history controls.  It is excluded from this documentation-only
  candidate and must not change until an independent R2-R4 ACCEPT.
- The old claim that the future E3 module was absent remains true only at the
  earlier R2-R3 freeze and is not rewritten.

## Required next gate

R2-R4 requires a fresh immutable manifest and an independent exact
`ACCEPT` with P0=0/P1=0 before the schedule, serial, source-policy, replay,
mutation, or boundedness implementation expands.  Existing tests and the
partial baseline do not substitute for that review.

If the required public A -> B -> A nonadjacent market-stream reuse control
shows that the current E2 reducer admits reuse, E3 must preserve the minimized
trace and return a bounded E2 semantic remediation.  It must not add an E3
workaround, reuse streams, or weaken the ADR rule.

The paired E2/E3 exact-head Python 3.11/3.12 success at the unchanged 93%
coverage threshold remains mandatory.  WO-0151 remains REVIEW.
