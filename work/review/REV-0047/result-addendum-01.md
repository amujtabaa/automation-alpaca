---
type: Review Result Addendum
rev_id: REV-0047
addendum: 01
reviewer_model: Codex (GPT-5)
reviewed_target: 116822d38d5fd1d50744f8d0cf05c544a1f601a4
base: 6d5937492788aa0ab1cf8348321fa01ee57df920
verdict: ACCEPT
date: 2026-07-31
relationship: Independent remediation re-review of reviewer result.md; the original result is preserved unchanged.
---

## Verdict

**ACCEPT.** F-001, F-002, and F-003 from the preserved REV-0047 result are closed. The four-file
remediation changes only documentation/governance records, introduces no new P0/P1 regression, and
does not activate M0 or RESET-WO-01.

The complete R1 archive remains unavailable in this checkout. That is now a truthful, explicitly
non-passing provenance limitation rather than a falsely reproducible verification result. For this
documentation-only M0 gate, the retained manifest and byte-exact authority files provide the local
audit boundary; the archive digest is correctly recorded as external human-approval provenance.

## Resolution of prior findings

| Prior finding | Status | Exact evidence | Re-review result |
|---|---|---|---|
| F-001 -- archive digest falsely reported as rehashed | CLOSED | `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md:18-21` labels the digest human-approved provenance and says archive bytes are not retained/re-hashable. `work/queue/WO-0144-architecture-reset-m0-documentation-landing.md:160-163,192-193,219` requires and records `UNVERIFIED_IN_CHECKOUT`, rather than PASS. Target-tree inspection found no archive-like R1 artifact, consistent with the disclosed limitation. | The clean-checkout non-reproducibility is no longer represented as successful evidence. The exact manifest and its covered authority files, rather than unavailable archive bytes, are the locally verifiable M0 identity boundary. |
| F-002 -- false zero-template-token PASS | CLOSED | `WO-0144:168-172,198` now specifies an exact marker allowlist check and reports `21 occurrences / 14 unique; prompt 16, staged WO 5`. Independent scan of all 46 initial-M0 Markdown files found exactly those 21 markers, only in `09-seat-prompts.md` (16) and staged `11-first-work-order.md` (5). | The reported count, location partition, and absence outside the two deliberate template/staged documents reproduce. `RESET-WO-01` remains byte-identical to the original M0 target. |
| F-003 -- legacy runtime instructions ambiguous in root README | CLOSED | `README.md:138-145` renames the section to frozen legacy instructions and directly prohibits running it under M0, setting `SIGNAL_SEAT_ENABLED=true`, credentials, or Alpaca Paper access; it also states Signal Seat is disabled/unmounted in the reset target. | The warning now directly governs the adjacent command and Signal Seat material, resolving the context-free-reader path identified in F-003. |

## Independent static evidence

- Reviewed exact target `116822d38d5fd1d50744f8d0cf05c544a1f601a4` against base
  `6d5937492788aa0ab1cf8348321fa01ee57df920`; their merge base is the stated base.
- The remediation commit changes only `README.md`, the ratification index, `pkl/log.md`, and
  WO-0144. The cumulative range contains 49 paths (47 M0 delivery paths plus the reviewer-owned
  request/result), 0 deletions, 0 renames, and 0 application/test/cockpit/harness/workflow/migration
  paths. `git diff --check` is clean.
- The authority manifest SHA-256 is
  `c81e49ac3b36d7d99f0974cf34f2f89330e3336eea5877341f3b170aec1a2258`; all 15 records matched.
  ADR-020, ADR-021, and ADR-022 each remain byte-identical to their respective manifest-covered
  source and quoted SHA-256.
- The recorded refs contain no conflicting pre-existing ADR-020/021/022 identity. The extra
  Codex capture ref resolves to the reviewed target tree, not a divergent ADR body.
- No application, test, Python, SQL/DDL, database, ORM, parser, broker, credential, or network
  tooling was executed during this re-review.

## Adversarial lens reconciliation

- **Production saboteur:** the archive cannot be rehashed from a clean checkout. This remains a
  fragile external-provenance dependency, but it is no longer a hidden or falsely passing gate;
  accepting M0 does not convert it into implementation or runtime evidence.
- **Context-free new maintainer:** the local README warning now appears before the copied command
  and explicitly forbids reset use, credentials, Paper calls, and Signal Seat activation.
- **Security/data-integrity auditor:** manifest, all 15 covered files, and all three canonical ADR
  mappings reproduce exactly; the intentional bracket markers are confined to the declared frozen
  template/staged files. No new trust boundary or secret-bearing material was added.

No unresolved P0, P1, or P2 finding remains in this remediation range.

## Unverified items

- The complete R1 archive bytes and SHA-256 remain `UNVERIFIED_IN_CHECKOUT`; this addendum does not
  attest that the external archive digest is correct, only that the target no longer claims it was
  locally rehashed.
- Runtime semantics, broker behavior, database/schema claims, and Python 3.11/3.12 execution were
  not exercised, by review-scope prohibition. Static configuration and prior packet identity were
  inspected only.
- Ref checks cover the recorded refs in this checkout; no network fetch was performed.
