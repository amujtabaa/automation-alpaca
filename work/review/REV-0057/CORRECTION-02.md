# CORRECTION-02 — narrow WO-0150 E1/E2 boundary re-gate

Status: **AUTHORIZED CORRECTION — fresh R1 RED acceptance required**

## Authority

The user authorized the narrow re-gate on 2026-08-05 after the reviewed first
GREEN candidate exposed self-authenticating mutation receipts. The authorization
permits only the matching WO-0150 amendment, R1 RED contract and review,
in-scope pure implementation/test corrections, evidence reconciliation, and
the existing closeout gates. All earlier safety boundaries remain unchanged.

## Correction

The original candidate placed successful generation registration, initial
lineage binding, and late-fact record/index mutation in E1. Each operation
requires authenticated controller admission/currentness or canonical-fact
provenance that exists only in the later E2 composite reducer. Local sealing of
raw values cannot supply that missing provenance.

The corrected E1 scope therefore retains only deterministic identity data,
opaque view/container declarations, empty reconciliation-only readers, the
direct no-history venue correlation bridge, and failure-capable boundary
controls. It removes rather than merely hides the raw-to-trusted receipt and
mutation helpers. All successful population and mutation moves to WO-0151's
future E2 composite transition.

## Preserved evidence and non-effects

- `request.md`, `result.md`, `recheck-request.md`, `recheck-result.md`, and
  `WO-0150-RED-CONTRACT.md` remain unchanged historical evidence.
- `WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md` records the independent
  findings that caused this correction.
- No accepted ADR changes, no new public exports, no E2 activation, and no
  runtime, database, broker, network, credentials, CI-workflow, merge,
  deletion, or cleanup authority result from this correction.
- A new exact R1 RED candidate and independent review are mandatory before the
  amended implementation is accepted or committed as a WO-0150 result.
