# WO-0151 R12 nonadjacent market-stream remediation disposition

Status: **DOCUMENTATION-ONLY RED RE-GATE -- IMPLEMENTATION PROHIBITED PENDING INDEPENDENT ACCEPT**

## Trigger and retained evidence

The first accepted WO-0152 R2-R5 public duplicate-stream control froze an
otherwise valid A -> B -> fresh-binding-with-A-stream successor. The exact
test snapshot was SHA-256
`1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`; the
immutable observation record is `work/review/REV-0059/evidence.md`, SHA-256
`d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`.

The focused pure test command collected three controls: two passed and the
new stream-reuse control failed because it expected `REFUSED` and observed
`APPLIED`. No database, SQL/DDL, runtime, broker, network, credential, or CI
work ran. The E3 test source is retained as a frozen local working snapshot;
it is not an E3 acceptance candidate or a replacement for E2-owned RED
controls.

## Root-cause classification

This is P1 E2 nonconformance, not an ADR gap. ADR-020 R2 and ADR-021 R2
already require a distinct approved MarketStreamGenerationId for every serial
generation and prohibit reset, reuse, and transfer. The current successor
gate compares only the candidate stream with the immediate prior mandate. A
retired stream is therefore no longer represented in any direct ownership
index.

## R12 boundary

R12 reopens WO-0151's effective lifecycle for this root correction only. It
does not invalidate retained R11/R11-R1 evidence or reopen unrelated E2
semantics. The only admissible production change is a private, immutable,
sealed, non-enumerable direct MarketStreamGenerationId -> generation provenance
sub-index owned by `GenerationRegistry` in `app/execution_core/acquisition.py`.
It must be seeded at genesis, checked before successor authority registration,
atomically extended on a valid successor, and preserved across record
replacement. It must not be duplicated in authority, stored as controller
history, inferred from a predecessor walk, or obtained by a scan.

The only test source allowed is `tests/execution_core/test_acquisition.py`.
Directly necessary current work-order, PKL, ledger, provenance, and REV-0058
records are allowed. No public API, ADR body, runtime/persistence, database or
SQL/DDL, broker/network/credential, CI workflow, M2, merge, deletion, cleanup,
force-push, or rebase work is allowed.

## Required next gate

`WO-0151-RED-CONTRACT-R12.md`, its exact candidate manifest, and one fresh
independent review must return `ACCEPT` with P0=0/P1=0 before any R12 source
or test implementation. WO-0152 stays ACTIVE but implementation-paused under
FR-08 until the bounded repair is accepted and reconciled. The existing paired
E2/E3 exact-head Python 3.11/3.12 93% closeout remains mandatory.
