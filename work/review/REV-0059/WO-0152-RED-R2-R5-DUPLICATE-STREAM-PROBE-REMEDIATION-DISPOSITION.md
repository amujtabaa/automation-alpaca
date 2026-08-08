# WO-0152 E3 R2-R5 duplicate-stream-probe remediation disposition

Status: DRAFT - RE-GATE ONLY - NOT ACCEPTED  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059

## Why a replacement correction is required

The exact independent R2-R4 result
`48079e3b54beedddbb56382de2b05f49e6f887e2173c17d24e6131de0bce1889`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. Its sole P1 did not concern
the positive 32-mandate schedule: that schedule is bounded and can construct
valid unique-stream generations. The P1 is that the schedule deliberately
contains only unique streams and permits only its one loop mint, while the
required failure-capable public A -> B -> A-stream control needs one otherwise
valid mandate with fresh identities, a fresh authentic binding, and A's stream.

Reusing A itself would fail the separate acquisition-ID, protection-ID, and
binding-freshness gates even if stream ownership were removed. Constructing a
fresh public mandate with A's stream fails its sealed binding check. The
control therefore cannot isolate the no-nonadjacent-reuse rule under R2-R4.

## Narrow R2-R5 correction

Under the standing in-flight root-correction authorization and every retained
safety exclusion, R2-R5 replaces only the missing duplicate-stream probe
construction rule. It retains all 32 positive schedule entries, their unique
streams, the one bounded schedule-loop mint, and every R2-R3/R2-R4
environment, terminal, boundedness, provenance, and source-policy rule.

R2-R5 adds only one zero-argument test-only pre-genesis fixture:
`_nonadjacent_duplicate_stream_probe_mandate_fixture`. It may make one direct
literal private mint to construct exactly one complete public
`AcquisitionMandate` with fresh fixed acquisition/protection/binding identities
and the literal A stream. The probe is neither a schedule member nor a
positive-chain input. It is callable only by the named public A -> B ->
duplicate-A-stream control.

This is a test-configuration seam only. It grants no production/public API,
runtime, controller, currentness, effect, claim, broker, persistence, actor,
or caller-configurable authority. It adds no production source and no test
implementation before an independent R2-R5 `ACCEPT` at P0=0/P1=0.

## Retention and isolation

- R2-R4 contract, manifest, request, disposition, and independent result
  remain byte-stable retained evidence.
- The local partial E3 baseline remains isolated at SHA-256
  `e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79`.
  It is neither R2-R5 candidate input nor acceptance evidence and must remain
  byte-identical through this documentation-only preflight.
- If the eventual valid public probe is admitted by current E2 behavior, E3
  must preserve the minimized trace and return bounded E2 remediation. It may
  not mask the defect, reuse a stream in the positive chain, or modify
  production code under this work order.
- The paired E2/E3 unchanged 93% exact-head Python 3.11/3.12 closeout remains
  mandatory; WO-0151 remains `REVIEW`.
