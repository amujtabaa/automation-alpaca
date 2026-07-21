# Cross-model review — staged-packet convention

Canonical protocol: `.ai-os/core/15_CROSS_MODEL_REVIEW.md`; repository packet shape:
`work/review/README.md`. This page records dispatch mechanics only. It never replaces the
three-seat rule, the new-invariant probe obligation, or human disposition.

## The loop

1. **Author stages and commits the request.** Create
   `work/review/REV-NNNN/request.md` with role, exact targets/commit range, human-gated surfaces,
   numbered questions, current file/line pointers, added/amended invariants, required fresh probes,
   verdict vocabulary, and explicit out-of-scope boundaries.
2. **Push the branch under review.** The reviewer must read a stable, reachable branch state.
   `SET-ON-DISPATCH` is allowed while text is still being assembled; freeze the exact range before
   the result is treated as a gate.
3. **A different model reviews.** The independent seat re-derives from code/spec and writes only
   `result.md` with findings and one verdict:
   `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`. It never edits `request.md`.
4. **Author/human dispositions.** The reviewed party does not rewrite reviewer-owned findings.
   Accepted fixes or disagreements go in a separate `disposition.md` (or a disclosed addendum
   where the protocol permits), with fresh evidence.
5. **Close the gate.** Only human disposition after an ACCEPT / ACCEPT-WITH-CHANGES result clears
   the review gate. Update the append-only ledger in the same close-out commit.

## Conventions

- Archive packet ids never port into master. Cite their branch/ref as provenance and allocate a
  fresh master REV id.
- In-process validation is a first-pass filter and never counts as independent review.
- Human-gated or ADR changes always receive a tracked REV packet, including when discussion also
  occurred in PR threads.
- A result covers only the declared targets and commit range. Material post-result changes require
  a fresh or explicitly extended review.
- Requests must expose never-reviewed semantic forks and negative space; do not hide them inside a
  success narrative.
- New/amended `INV-*` entries require at least one fresh-probe line in the packet, not a rerun of
  the implementer's pin.
- Review findings are reviewer-owned. The reviewed party may not edit them in place.
