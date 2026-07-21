---
type: Review Request
rev_id: REV-0036
title: Safety-record label reconciliation for REV-0033 and completed import/mypy ratchets
status: STAGED
reviewer_seat: Claude
targets: [ADR-002, ADR-003, ADR-006, ADR-007, ADR-008, INVARIANTS-annotations, pyproject-comment]
human_gated_surfaces: [accepted-ADR-text, invariant-record-text, event-log-truth-records]
commit_range: eab9e57..SET-ON-DISPATCH
created: 2026-07-21
---

# Review Request REV-0036 — nonsemantic safety-record reconciliation

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, `CLAUDE.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request, and the curated
targets below. Re-derive every record claim from the current tree. Produce findings only in
`work/review/REV-0036/result.md`; do not edit this request, accepted ADRs, `docs/INVARIANTS.md`,
or configuration.

Return one verdict: `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`. Each finding must identify file:line,
why it matters, and what resolves it. In-process validation is evidence, not independent review.

## Gate state and narrow authorization

WO-0121 is human-gated because it annotates accepted ADR and invariant records. The operator
authorized the annotation-only WO in the ULTRA batch; no implementation, safety decision, event
vocabulary, invariant meaning, threshold, import contract, or mypy configuration value is changed.
WO-0121 stays `REVIEW` until this packet returns and the human dispositions it. No beta milestone
may rely on these corrected labels merely because the implementer checks pass.

The active WO's original allowed-path list omitted `pyproject.toml` even though F004 and the WO's
required behavior explicitly require deleting its contradictory future-step comment. The
implementer narrowed the contract to that one comment deletion only; review this scope correction
as part of the packet.

## What changed

1. **REV-0033 gate-state annotations.** Eleven dated closure notes were added without rewriting
   historical text: ADR-002, ADR-003, ADR-008, and eight WO-0113-labeled invariant blocks. Each
   says REV-0033 returned ACCEPT-WITH-CHANGES and its disposition is RESOLVED, links the canonical
   disposition, preserves the preceding pending label as history, and disclaims semantic change.
2. **Current-snapshot expansion.** AUD2-F003 originally cited five invariant blocks. Three later
   current-tree labels (INV-091, INV-092, INV-094) carried the identical stale pending state, so
   they receive the same record-only annotation. This is same-class closure, not a new decision.
3. **ADR-006 current-state record.** A dated appended section records six live import-linter
   contracts, including `sellside-is-a-pure-policy`, while retaining the original five-contract
   adoption baseline.
4. **ADR-007 current-state record.** A dated appended section records the fully burned-down
   application punch-list, live `warn_unused_ignores = true`, and whole-`app/` type gate while
   retaining the original baseline/limitation history.
5. **Config-comment cleanup.** The stale comment saying the next step is to consider enabling
   `warn_unused_ignores` was deleted. The already-live `warn_unused_ignores = true` value and every
   other configuration line are unchanged.

## Curated targets and truth sources

- REV-0033 truth: `work/review/REV-0033/disposition.md:4-5,81`.
- Closure annotations:
  - `docs/adr/ADR-002-timeout-quarantine.md:66`
  - `docs/adr/ADR-003-manual-flatten-halted-reducing.md:39`
  - `docs/adr/ADR-008-order-status-event-provenance.md:79`
  - `docs/INVARIANTS.md:143,162,452,565,722,1084,1108,1145`
- Import record: `docs/adr/ADR-006-import-boundaries.md:110`; six contract headers at
  `.importlinter:33,51,66,95,134,182`.
- Type record: `docs/adr/ADR-007-mypy-typecheck-gate.md:52`;
  `pyproject.toml:54,72-76`.
- Audit source: `work/review/AUDIT-0002-priorwork/report.md:93-134`.
- Active contract: `work/active/WO-0121-safety-doc-label-reconciliation.md`.

## Invariant accounting and fresh probes

**Added or amended invariant semantics: none.** The eight inserted invariant notes are
non-normative gate-state annotations. No `INV-*` heading, rule, rationale, or pin text is changed.
The new-invariant probe obligation therefore has no new semantic invariant to map.

Required independent disproof attempts:

1. Remove every `WO-0121 closure record` block from the candidate text and compare the remainder
   byte-for-byte with the pre-WO semantic head. Any difference is a BLOCK: the edit was not
   additive-only.
2. Try to find a WO-0113 `pending REV-0033` label in the five target documents that lacks a nearby
   dated closure note, or any closure note claiming a verdict other than the canonical
   ACCEPT-WITH-CHANGES / RESOLVED pair.
3. Count actual `[importlinter:contract:*]` headers and run `lint-imports`; disprove the six-kept,
   zero-broken claim.
4. Inspect `pyproject.toml` for any application `ignore_errors = true` override and run
   `mypy app/`; disprove full punch-list burn-down or the whole-app green claim.
5. Diff `pyproject.toml` against the pre-WO head. It must show exactly one deleted stale comment
   and zero setting/value changes.
6. Search the branch diff for `app/`, `tests/`, `.github/`, thresholds, event names, invariant
   definitions, or altered historical sentences. Any such mutation is outside authorization.

## Questions to answer

1. Does every closure note state exactly what REV-0033 and its disposition prove—no more and no
   less—and preserve the original decision history?
2. Are the three additional current-tree invariant annotations legitimate same-class stale-label
   closure rather than semantic scope creep?
3. Do ADR-006 and ADR-007 accurately distinguish historical adoption baseline from stronger
   already-shipped current gates?
4. Was the pyproject scope correction and edit limited to the one contradictory comment?
5. Can any reader interpret an annotation as changing an invariant, authorizing a new behavior,
   or self-clearing this independent review gate?

## Out of scope

- Re-reviewing WO-0113 implementation correctness beyond confirming the recorded REV-0033 gate
  state.
- Changing any ADR/invariant semantics, test pin, event vocabulary, import boundary, or mypy value.
- Application/test/CI changes, live trading, credentials, schema work, or a new execution path.
- Writing the disposition, ledger entry, or moving WO-0121 to completed; those occur only after
  the independent result and human disposition.
