---
type: Review Disposition
rev_id: REV-0071
work_order_id: WO-0166
status: ACCEPTED
date: 2026-08-22
recorded_by: Codex implementation and checkpoint seat after fresh adversarial acceptance
---

# REV-0071 disposition

## Decision

Accept terminal result `result-final.md` unchanged as the authoritative `ACCEPT`, P0=0/P1=0/P2=0
review of source/test candidate `b00c2dec5fab7f87fd30aecc130a29bec600bf39`, tree
`3da4736c39747f14a0d3663d1f6871cc07f740ac`. Preserve every earlier request and result as negative
evidence; no superseded candidate is accepted by this disposition.

## Findings resolved

1. Post-closure owner admission now durably and atomically makes the exact predecessor generation
   unresolved, quarantines and advances controller currentness, and stales successor authority.
2. Every late owner can retain one exact immutable invalidation record and evidence-bound negative
   terminal, including multiple owners and owners discovered after `INVALIDATED`.
3. Raw default reopen cannot replace exact invalidation evidence or substitute owner, observation,
   acceptance-set, or effect coordinates before required connection verification.

## Bound evidence

- Accepted `SCHEMA_DDL`: 146,417 UTF-8 bytes, SHA-256
  `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`.
- Installed catalog SHA-256:
  `145393452d7bd0f0227076f14daa5b6115e44581609e456646b82de663df0a08`.
- Terminal result SHA-256:
  `b04b73fe3ff48433a81c096ed41ba1416777e81222670a794c651a91eebb1939`.
- Fresh author evidence: 82 focused schema tests; 1,690 execution-core tests on CPython 3.12.13;
  CPython 3.14.5/SQLite 3.50.4 catalog reproduction; Ruff, formatting, mypy over 91 files, 32
  import-boundary tests, six import contracts, actual changed-path scope, ledger, and whitespace.
- Terminal fresh review: three `ACCEPT` verdicts, each P0=0/P1=0/P2=0 and 82/82 focused tests.

## Distillation and follow-up

Retain the completed work order and complete REV-0071 chain with `RESULT_SUMMARY_KEPT` and
`ARCHIVED`. No PKL or ADR update is required because this schema realizes existing accepted
architecture without changing it. This disposition does not activate WO-0167, authorize a
configured database or migration, or authorize merge to `master`.
