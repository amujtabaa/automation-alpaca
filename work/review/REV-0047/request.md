---
type: Review Request
rev_id: REV-0047
title: "Architecture reset M0 documentation landing"
status: AWAITING_REVIEW
targets: [WO-0144, ARCH-RESET-2026-07-R1, ADR-020, ADR-021, ADR-022]
human_gated_surfaces: [architecture authority, event-truth migration, schema and cutover decisions, execution invariants]
commit_range: 6d5937492788aa0ab1cf8348321fa01ee57df920..0ea28eb8fa0cbc789cfbf8685a79e30703e5cbe0
created: 2026-07-31
---

## Your Role

You are the **independent review seat**, using a different model from the implementation author.
Follow `AGENTS.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, and the applicable reset authority in
`CLAUDE.md`. Produce findings only and do not edit any file except `result.md` in this folder.

Use three hostile perspectives: production saboteur, context-free new maintainer, and security/data-
integrity auditor. Each perspective must identify at least one concrete defect, risk, or fragile
assumption. Deduplicate the final findings and promote severity when multiple perspectives agree.

## What You're Reviewing

Review the frozen M0 documentation commit only:

```text
base:   6d5937492788aa0ab1cf8348321fa01ee57df920
target: 0ea28eb8fa0cbc789cfbf8685a79e30703e5cbe0
diff:   git diff 6d5937492788aa0ab1cf8348321fa01ee57df920..0ea28eb8fa0cbc789cfbf8685a79e30703e5cbe0
```

The change lands the exact hash-ratified reset packet, byte-identical proposed ADR bodies under
conflict-free canonical identities, a separate acceptance index, partial-supersession backlinks,
and reset-versus-frozen-legacy navigation. It must not claim that any runtime, schema, cutover,
database, broker activity, or implementation was executed or validated.

No application/test execution, Python execution, SQL/DDL, database engine/client/parser/ORM,
broker call, credential use, network access, deletion, cleanup, push, merge, or implementation is
needed or permitted for this review. Git/file/hash inspection is sufficient.

## Where to Look First

1. `work/queue/WO-0144-architecture-reset-m0-documentation-landing.md`
2. `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`
3. `work/queue/ARCH-RESET-2026-07/10-ratification.md`
4. `work/queue/ARCH-RESET-2026-07/12-proposed-adr-set.md`
5. `docs/adr/ADR-020-current-state-execution-kernel.md`
6. `docs/adr/ADR-021-position-protection-liquidity-execution.md`
7. `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`
8. Modified `AGENTS.md`, `CLAUDE.md`, legacy ADR backlinks, overview/navigation docs, and PKL pages.
9. Static Python evidence only: `.github/workflows/ci.yml` and `pyproject.toml`.

## Required Review Questions

- Do the approved manifest/archive identities reproduce, and are the 15 numbered packet files plus
  the three canonical ADR copies byte-exact?
- Is every changed path documentation-only and traceable to M0, with no deletion or hidden
  implementation?
- Are ADR-020 through ADR-022 and WO-0144 actually conflict-free across all recorded refs?
- Does the separate index accurately distinguish accepted architecture authority from unexecuted
  implementation, schema, cutover, and broker claims?
- Are the DDL incident, non-persistent effects, inadmissibility, and non-reliance stated without
  laundering the prohibited execution into evidence?
- Do partial-supersession backlinks preserve every retained clause rather than superseding whole
  legacy ADRs by implication?
- Can any current/high-authority page still be read as making Spine v2, universal event-log truth,
  dual-store business parity, or Signal Seat the reset target?
- Are Python 3.11/3.12 statements supported by static configuration without claiming execution?
- Is `RESET-WO-01` still exact, staged, unnumbered, inactive, and separately gated?

## Fresh Invariant Probes

These are new counterexample probes for the amended quantity-authority wording; verify that the
landed authority gives each an unambiguous disposition:

1. A `SUBMITTED` or `ACCEPTED` acknowledgement arrives after a fill. It must never change position
   quantity or fill economics.
2. The same broker `TRADE_CORRECT` fact is ingested twice with identical identity and payload. Only
   the first occurrence may revise economics; the duplicate must be a no-op.
3. A `TRADE_BUST` names no valid predecessor or conflicts with the predecessor's economic chain.
   It must not mutate raw quantity by guess, clamp, or rewrite.
4. A broker-authoritative fill exceeds local approved quantity. The exact fact still changes raw
   position and triggers quarantine; local bounds cannot hide broker reality.

## Evidence Expectations

- Recompute hashes and inventory independently; do not rely only on WO-0144's recorded PASS lines.
- Inspect full changed files where authority or navigation semantics depend on surrounding text.
- Attempt to disprove the clean-scope and no-activation claims.
- Label findings P0/P1/P2 and cite exact `file:line` evidence.
- Treat inability to reproduce a completion claim as P0 under `AGENTS.md`.

## How to Respond

Create `result.md` in this folder. Use verdict `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`.
End with anything not verified. Do not modify `request.md` or any reviewed file.
