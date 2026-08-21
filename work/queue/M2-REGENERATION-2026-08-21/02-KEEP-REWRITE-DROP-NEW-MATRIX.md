# One-pass M2 reconciliation matrix

Status: **CANDIDATE — EACH BOUNDED ITEM CLASSIFIED ONCE**

## Classification rules

- `KEEP`: retain the exact semantic obligation or exact-byte accepted authority; old lifecycle and
  candidate authority do not follow.
- `REWRITE`: preserve the owning requirement but re-derive its representation, authority routing,
  evidence, or work-order placement from current accepted sources and frozen research.
- `DROP`: do not carry the item into the new candidate except as explicit negative provenance.
- `NEW`: add a research/human/verification obligation absent from the old c9 packet.

## Obsolete-candidate items

Every bounded semantic or lifecycle center present in the six extracted c9 files appears exactly
once below.

| ID | Old item | Class | Fresh disposition and evidence |
| --- | --- | --- | --- |
| O-01 | `WO-0158b`, `REV-0067`, and obsolete branch lifecycle | `DROP` | Fresh identities are `WO-0164`, `REV-0069`, and `codex/m2-regeneration-gate-a-r1`; no old lifecycle resumes. |
| O-02 | Old authority manifest, preflight candidate, and c9 candidate hashes | `DROP` | All are `INVALIDATED / REGENERATION_REQUIRED` under final research; current packet receives a new external manifest and commit. |
| O-03 | 17-row c9 source/ADR freeze | `REWRITE` | Retain it as comparison provenance only. Freeze then-current exact implementation surfaces separately after Gate B; do not reuse c9 application hashes. |
| O-04 | Canonical 89-row source-coverage stream (`G` records) | `KEEP` | Preserve as independently reproduced old-contract evidence at 89 rows/digest `95e826f2...`; it is not the complete fresh research source universe. |
| O-05 | A01-A13 fact truth, one writer, direct lineage, controller, acceptance, and atomicity semantics | `KEEP` | These remain accepted ADR-020/021/022 plus safety-core obligations. |
| O-06 | C01-C12 ADR-023 strict cursor, invalidation, source fence, baseline, and exhaustion sequence | `KEEP` | ADR-023 bytes match accepted current authority exactly; retain all steps together. |
| O-07 | CR-01 through CR-19 cold-restart negative controls | `KEEP` | Carry as later failure-capable M2 runtime/test obligations; none is relabeled PASS. |
| O-08 | Historical relation/SQL-family matrix | `REWRITE` | Keep invariant vocabulary and disproof value while dropping table/trigger/index syntax as authority. New candidate remains schema-neutral. |
| O-09 | H01-H08 transaction, outbox, audit, startup, cutover, and retention semantics | `KEEP` | Preserve direct-current proof, old-or-new UoW, claim-before-I/O, acceptance authority, supervisor fence, recutover, and read-only history. |
| O-10 | ADR-020 through ADR-023 accepted only through old Gate-A planning route | `REWRITE` | Current ratification index is the acceptance authority; unchanged embedded proposed text is provenance, not uncertainty. |
| O-11 | Exact ADR-023 bytes | `KEEP` | Current accepted repository SHA-256 equals tar SHA-256 `9a61d4...`. |
| O-12 | Exact ADR-024 bytes and profile/source separation semantics | `KEEP` | Current accepted repository SHA-256 equals tar SHA-256 `93a3ba...`. |
| O-13 | ADR-024 classified as a conditional proposal needing Gate-B adoption | `REWRITE` | ADR-024 was accepted 2026-08-09 by the ratification index. M2 implementation remains inactive, but profile semantics are current authority. |
| O-14 | D2-A parser-ready DDL and proposed table/constraint text | `DROP` | No SQL/DDL is produced or parser/execution claim made at this Gate A. Any later schema is a separately human-gated work order after Gate B. |
| O-15 | D3-A refusal to manufacture Paper mutation eligibility from local documentation/fake coverage | `KEEP` | Capability/credential/call evidence remains later M4 authority; this candidate stays `NOT_READY`. |
| O-16 | D4-A lock/WAL/`synchronous=FULL` proposed design choice | `REWRITE` | Preserve one-process owner-lock and durability evidence obligations. Select no exact SQLite settings here; target-build/filesystem/WAL tests must justify them later. |
| O-17 | D5-A old implementation graph and `WO-0159` through `WO-0163` | `DROP` | Those IDs/hashes belong to the abandoned lane. Fresh implementation slices are proposed descriptively and receive IDs only after Gate B. |
| O-18 | D6-A total typed input/reducer/result matrix | `REWRITE` | Preserve totality/no-new-dispatcher principle; regenerate the exact matrix from then-current M1 surfaces in the first post-Gate-B implementation contract. |
| O-19 | Proposed ADR-025 canonicalization path | `DROP` | No new ADR is created by this planning wave. Accepted ADR-024 already supplies the profile boundary; any genuinely new architecture decision requires a separately reviewed ADR. |
| O-20 | Old builder checks, old Stage-1/2 CI, and self-disproof as candidate acceptance | `DROP` | Retain as history only. Fresh `REV-0069` and fresh packet checks determine this candidate; no old CI establishes current acceptance. |

Old-item totals: `KEEP 8 / REWRITE 6 / DROP 6 / NEW 0`, exactly 20 rows.

## Fresh obligations absent from c9

| ID | New obligation | Class | Required treatment |
| --- | --- | --- | --- |
| N-01 | Frozen R01-R20/S01-S04 aggregate plus completed human overlay | `NEW` | Bind original and overlay hashes separately; preserve 155 decisions, findings, conflicts, refusals, and no authority laundering. |
| N-02 | Non-trade financial-fact exclusion/quarantine policy | `NEW` | Prepare a later versioned policy/ADR proposal; until accepted, unexpected fees/dividends/interest/cash adjustments cannot become execution facts or silently mutate trading state. |
| N-03 | Numeric-risk policy owned by Ameen Mujtabaa | `NEW` | Software must not invent loss, exposure, emergency, or change-control limits. No numeric value is selected by this packet. |
| N-04 | Human-selected package sequence | `NEW` | M2 work is inside `PKG-MIN`; `PKG-HARD` follows evidence; `PKG-ADV` remains conditional on the full conjunction and F-R20-15 isolation. |
| N-05 | No comparison and no specialist engagement | `NEW` | Select no new provider/vendor/platform/model and schedule no specialist/procurement scope. Alpaca Paper remains inherited accepted beta authority only. |
| N-06 | Research freshness/readiness burden | `NEW` | Preserve `NOT_RUN`, R16 G0-G7 `NOT_EVALUATED`, open P1/P2 findings, unknown lifecycle costs, claim-expiry ownership, and `NOT_READY / HOLD_ALL_PROMOTION`. |
| N-07 | Malformed tar-container manifest row | `NEW` | Preserve the 63-character row as negative evidence; use two independent 64-character handoff bindings and six valid inner rows. Require strict digest grammar in future manifests. |
| N-08 | Exact obsolete-branch terminal retirement | `NEW` | Delete only local/remote `codex/m2-planning-preflight-r1` after accepted comparison, successor publication, clean-worktree/ref proof, and exact post-delete absence checks. |

New-item total: `NEW 8`, exactly eight rows.

## Disproof pass

- No row classifies old c9 prose as accepted merely because its semantics remain useful.
- No accepted ADR byte is relabeled draft merely because its embedded status text is unchanged.
- No research recommendation becomes implementation authority.
- No `NOT_RUN`, `NOT_EVALUATED`, P1/P2 finding, unknown cost, or unavailable provider fact becomes
  PASS, zero, selected, or closed.
- No D2-A, D4-A, Stage-3, ADR-025, REV-0067, WO-0159-0163, or old candidate hash survives as an
  activation decision.
- Every retained semantic rule traces to the safety core/current accepted ADRs or to a frozen
  research hold; every new rule traces to the completed human overlay or observed verification.
