# WO-0150 RED-contract independent preflight request

Status: **INDEPENDENT REVIEW — documentation-only exact-commit gate**

Review the exact commit at HEAD that first contains
work/review/REV-0057/WO-0150-RED-CONTRACT.md. Record its full SHA-1 before analysis. Refuse the
request if HEAD is not that immutable candidate or if the candidate contains paths other than
the RED contract and this request.

## Context and review target

Read only the smallest relevant packet:

- AGENTS.md and CLAUDE.md's permanent safety core;
- work/queue/WO-0150-reset-kernel-e1-generation-lineage.md;
- work/review/REV-0057/WO-0150-RED-CONTRACT.md;
- ratified ADR-020 R2 sections 2–4 and ADR-021 R2 sections 2 and 5;
- the relevant public seams in identity.py, fills.py, venue.py, and __init__.py; and
- the current import-boundary and venue-ownership test conventions as necessary.

The candidate is documentation only. Do not make application or test changes, execute SQL/DDL,
initialize a database, access credentials, access a broker/Alpaca/network, change CI, merge,
delete, clean up, commit, or push. Write findings only to
work/review/REV-0057/result.md; do not edit this request or the contract.

## Questions to resolve

1. Does the proposed E1 boundary trace exactly to accepted ADR-020/ADR-021 and WO-0150, without
   silently adding architecture or requiring an ADR clarification?
2. Does AcquisitionGenerationId bind every required coordinate with a deterministic,
   replay-stable, fail-closed format and no caller-provided authority path?
3. Is the split between one-record-per-generation GenerationRegistry and separate permanent
   AcquisitionLineageIndex sound, bounded, and free of a controller history collection?
4. Does the public surface expose only inert construction/read capabilities and direct lookup,
   while keeping admission, registration, currentness, policy, protection, effect eligibility,
   and semantic AcquisitionLineageRelation work out of E1?
5. Does the venue-correlation rule prevent private-field access and audit/history materialization,
   including the existing VenueRecoveryBook.effect() materialization behavior?
6. Are the RED controls failure-capable and sufficient to catch coordinate loss, direct-route
   loss, a late A fact landing on B/C, current-symbol fallback, unbounded collection placement,
   leaked mutation APIs, and an E1 policy expansion?
7. Does any unresolved ambiguity prevent a safe GREEN implementation? If so, state the smallest
   correction or whether an ADR decision is actually necessary.

## Result format

Use reproduced-static or reasoned-static evidence tags for each conclusion. List each finding
with priority, exact file/line, evidence, why it matters, and smallest resolution. End with:

- BLOCK, ACCEPT-WITH-CHANGES, or ACCEPT;
- exact P0/P1/P2 counts;
- candidate SHA and candidate path set;
- items intentionally not executed; and
- whether WO-0150 may advance to its explicitly authorized activation/RED implementation gate.

The review must stay materiality-bounded: assess realistic provenance, boundedness, lifecycle,
capital-safety, and maintainability risks. Do not manufacture an open-ended review queue from
 style preferences or deliberately deferred E2/M2 concerns.
