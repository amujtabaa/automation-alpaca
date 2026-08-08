# WO-0151 R13 successor protection-cursor remediation disposition

Status: **DOCUMENTATION-ONLY RED PRE-FLIGHT -- IMPLEMENTATION NOT GRANTED**

## Trigger and preserved evidence

The frozen WO-0152 FR-08 B-first-fill public detector is preserved at
`work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md`, SHA-256
`d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb`.
Its unstaged test source remains SHA-256
`c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`.

The public trace reaches a valid completed A-to-B successor and valid B first
canonical BUY fill. Venue and execution apply the fact, but the composite
reducer returns `REFUSED` instead of establishing fresh B protection.

## Root-cause classification

This is an E2 P0, not an E3 fixture or oracle defect. Existing successor
registration changes controller/currentness authority from A to B, but the
direct venue-owned protection cursor remains labelled A. The unchanged
ordinary protection projector correctly rejects B's first fill against that
old cursor, preventing an unprotected B exposure but leaving required applied
fact totality incomplete.

ADR-020 R2 and ADR-021 R2 already require one fresh B protection authority on
an atomic completed-flat successor and prohibit transfer of A's normal
protection state/cursor. R13 is therefore a constructibility and implementation
re-gate, not a new architecture decision.

## Narrow R13 boundary

The sole proposed correction is a private, domain-separated, zero-economic,
predecessor-linked venue cursor rollover composed by existing authority
successor registration after all completed-flat gates pass and before B
currentness is published. It must bind exact A/B mandates, scope, unchanged
execution, direct predecessor cursor, and exact successor-registration
commitment. Public venue inputs and ordinary venue proofs must remain unable to
change a bound mandate.

The frozen E3 detector remains downstream confirmation only. R13 may not edit,
format, weaken, stage, or use it as acceptance evidence. No public API,
protection API, runtime/persistence, database/SQL/DDL, broker/network,
credentials, CI-workflow, M2, merge, deletion, cleanup, force-push, or rebase
work is in scope.

## Required next gate

The exact R13 contract, manifest, and fresh independent review must return
`ACCEPT` with P0=0/P1=0 before ratification, activation, or any source/test
implementation. If constructibility requires public authority, a history scan,
protection-state transfer, an ADR change, or a wider semantic center, stop and
return a new bounded decision instead of weakening the detector.
