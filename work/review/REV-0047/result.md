---
type: Review Result
rev_id: REV-0047
reviewer_model: Codex (GPT-5)
verdict: BLOCK
date: 2026-07-31
---

## Verdict

**BLOCK.** The frozen documentation-only target correctly reproduces the authority-manifest, all
15 manifest-covered packet files, and all three canonical ADR copies. It also has a clean
documentation-only diff from the stated parent. However, WO-0144 reports successful rehashing of
the *complete R1 archive* while the target tree contains no such archive or other byte source from
which its quoted digest can be recomputed. That makes the claimed verification non-reproducible and
blocks acceptance under `AGENTS.md`.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| F-001 | P0 | `work/queue/WO-0144-architecture-reset-m0-documentation-landing.md:182-185`, `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md:16-22` | WO-0144 declares a PASS for a SHA-256 recheck of the approved “manifest/archive” and says the approved hashes matched. The ratification index identifies `51e4…053f` as the **complete R1 archive** digest, but the target tree has no R1 archive (or equivalent immutable byte source) at all. `10-ratification.md:94-96` further says that archive digest exists only in a separately preserved evidence/approval record. Independently rehashing the target objects reproduced the manifest digest, all 15 records, and ADR-020..022 copies, but cannot reproduce the complete-archive digest. | Exact-digest approval is the authority boundary for M0. A clean checkout therefore cannot reproduce a verification claim marked PASS/VERIFIED; that is a P0 by the repository review rule, and it leaves the accepted authority unit only partially auditable. | Do not accept M0 as VERIFIED until the exact archive bytes are retained or made immutably retrievable in the review context and a fresh hash result is recorded. If that cannot fit the M0 documentation-only scope, amend the work order and downgrade the archive check to explicitly UNVERIFIED rather than claiming PASS. |
| F-002 | P1 | `work/queue/WO-0144-architecture-reset-m0-documentation-landing.md:198-200`, `work/queue/ARCH-RESET-2026-07/09-seat-prompts.md:3,11-21`, `work/queue/ARCH-RESET-2026-07/11-first-work-order.md:249-253` | The recorded mutable-token scan says “0 unresolved mutable tokens.” The manifest-covered packet deliberately contains bracketed placeholders: `09-seat-prompts.md` instructs the user to replace them before use and has values such as `[BRANCH_AND_SHA]`; staged RESET-WO-01 also has five `[PYTHON_3_11]`/`[PYTHON_3_12]` command labels. | The result is not a failure-capable static check as reported. These markers are expected in frozen/staged packet material, but a future reviewer cannot distinguish intentional exact bytes from an unintended unresolved token when the evidence asserts zero. | Correct the evidence to enumerate the intentional, manifest-covered template markers and make the check assert both their exact allowlisted locations/counts and zero markers outside that set. Do not alter the ratified packet bytes merely to satisfy the scan. |
| F-003 | P2 | `README.md:138-157` | The root README’s reset caveat is remote from the later active-voice instructions to run `uvicorn app.main:app --reload` and to enable Signal Seat with `SIGNAL_SEAT_ENABLED=true`. Those lines remain a copy-pastable legacy activation path in the main repository entry point. | A context-free maintainer following the local section can start or enable frozen legacy behavior despite the reset’s explicit disabled/unmounted Signal Seat target. This is a navigation safety risk, not evidence that M0 executed anything. | Put a direct “frozen legacy only — not authorized for reset use” warning immediately above the run/Signal Seat instructions, or move that material under a clearly labeled historical section. |

## Perspective synthesis

- **Production saboteur:** F-001 is a severity-promoted P0. The evidence gate says the archive
  was checked, yet a fresh checkout cannot perform that check; a bad or substituted archive would
  be indistinguishable at the stated authority boundary.
- **Context-free new maintainer:** F-003. The root README still presents runnable backend and
  Signal Seat instructions as a local operational path after the reset headline has scrolled away.
- **Security/data-integrity auditor:** F-001 and F-002. The detached archive identity is not
  independently auditable from the claimed evidence, and the token-scan PASS masks known mutable
  placeholders instead of proving their containment.

F-001 was independently reached by the production-saboteur and security/data-integrity lenses and
is promoted to P0. The perspectives otherwise describe distinct defects and are not double-counted.

## Independent evidence recomputed

- Reviewed only `6d5937492788aa0ab1cf8348321fa01ee57df920..0ea28eb8fa0cbc789cfbf8685a79e30703e5cbe0`.
  The target's sole parent and merge base are the stated base.
- The diff has 47 changed paths, 0 deletions, 0 renames, 0 paths outside WO-0144's allowlist, and
  no application/test/configuration changes; `git diff --check` is clean.
- SHA-256 verification: manifest `c81e49ac3b36d7d99f0974cf34f2f89330e3336eea5877341f3b170aec1a2258`
  matched; 15 manifest records/0 mismatches; all three canonical ADR bodies exactly matched their
  packet source and quoted digest. The archive digest is the exception in F-001.
- The target's 36 recorded refs contain no pre-existing conflicting ADR-020, ADR-021, or ADR-022
  identity; the extra capture ref points to the target tree itself. The recorded R6 and reserved
  refs resolve to the SHAs quoted by the ratification index.
- Static link/fence inspection found 46 changed Markdown files, 70 relative links, 0 broken links,
  and 0 unbalanced-fence files.
- Static configuration supports the documentation claim only: `.github/workflows/ci.yml:17-20`
  contains 3.11 and 3.12 matrix legs, and `pyproject.toml:49-52` has a 3.11 mypy target. No Python
  or CI execution was performed.

## Fresh invariant probes

The new authority gives an unambiguous specified disposition to all four requested probes (this is
document review only, not implementation validation):

1. Acknowledgements/statuses are non-economic: `ADR-021:43-51` and `ADR-020:122-126`.
2. Same-identity, same-payload correction/bust retries are no-ops: `ADR-021:64-73`.
3. Missing, branched, stale, or scope-conflicting predecessor lineage reaches reconciliation with
   zero economic mutation: `ADR-021:64-71`.
4. A broker-authoritative overfill applies exactly and quarantines, including negative position:
   `ADR-021:48-50,72-73`.

## Proposed Fixes Summary

Resolve F-001 before accepting M0. Then make the recorded static evidence discriminate deliberate
ratified/staged placeholders from unintended ones (F-002), and make the README’s legacy runtime
instructions locally unmistakable (F-003). No reviewed implementation, ADR body, or request file
was edited by this review.

## Notes / unverified items

- The complete R1 archive bytes and therefore its SHA-256 could not be verified from this checkout;
  this is the blocking finding, not an assumption that the quoted digest is wrong.
- Per the review request, no application, test, Python, SQL/DDL, database, ORM, parser, broker,
  credential, or network tooling was executed. The authority's runtime semantics and Python-version
  claims were assessed statically only.
- Ref checks used the 36 recorded local refs in this checkout; no network fetch was performed.
