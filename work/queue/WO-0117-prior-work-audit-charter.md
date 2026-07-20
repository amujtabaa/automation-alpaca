---
type: Work Order
title: "AUDIT-0002 charter: findings-only cross-model audit of prior work orders, docs, queue, and review packets"
status: DRAFT
work_order_id: WO-0117
wave: post-R2 beta-prep (the roadmap's full-repo-audit phase)
model_tier: strong
risk: medium
disposition: []
owner: Ameen / planning seat drafted 2026-07-20 / auditor: Codex session (seat rule below)
created: 2026-07-20
gated_surface: none touched (read-only, findings-only; remediation is separately authorized)
---

# Work Order: AUDIT-0002 — verification-first audit of prior work

> **Findings-only.** The auditor produces evidence-backed findings and verdicts — it pushes
> zero fixes, edits zero source/test/doc/PKL files, and weakens nothing (AGENTS.md review
> seat: "Produce findings only. Do not push fixes."). Root-cause remediation, if any, happens
> in a SEPARATE session via scoped work orders (next free ids) with the normal
> red-first/dual-store/review gates — per Ameen's 2026-07-20 direction.

## Goal

Re-derive, with fresh evidence against the current tree, whether prior work orders' completion
claims, ADR/INVARIANTS prose, queued-work premises, and review-packet records still hold —
and report every gap as a P0/P1 finding in an `AUDIT-0002` packet.

## Context packet

Read only these first:

- `AGENTS.md` (Codex adapter + review-seat rules) + `CLAUDE.md` safety core
- `.ai-os/core/15_CROSS_MODEL_REVIEW.md` (packet protocol) + `.ai-os/templates/fable-core-v3.md`
- `work/review/AUDIT-0001-quarantine-treadmill.md` (format precedent)
- `work/review/REV-0029/result.md` + `disposition.md` (method precedent: fresh probes, by-property closure)
- `pkl/process/review-hardening.md` (Tier-1/2/3 review rules from the post-mortem)
- `work/ledger.jsonl` + `work/completed/**` (the audited population)
- `docs/adr/` + `docs/INVARIANTS.md` (Tier-2 subject matter)
- Target files per tier, opened tier-by-tier (smallest useful packet)

## Allowed paths

```yaml
allowed_paths:
  - work/review/AUDIT-0002-priorwork/**   # the packet: report, findings, evidence, probe harnesses
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**          # read, probe, never edit
  - tests/**        # temporary probes live in the packet folder, never in tests/
  - docs/**
  - pkl/**
  - work/queue/**   # findings may PROPOSE re-cuts; the planning seat executes them
  - work/active/**
  - .github/**
```

## Seat rule (binding)

The auditor of a target must not be the model that built it; in-process validation never
counts. Builder map to honor (extend it with evidence as you go):

- **Codex-built — EXCLUDED from a Codex session's adjudication:** WO-0106 (Part A
  consolidation), WO-0113 (REV-0033 header: "implementer was Codex"). List them in the packet
  as `DEFERRED — other-seat audit required`; do not self-adjudicate.
- **Claude/Sol-built — Codex audits:** the W0-W3 era WOs (WO-0001..WO-0036 window),
  WO-0108/0109/0110/0111/0112, the campaign artifacts.
- Re-adjudicating one's own prior REVIEW verdicts (e.g. Codex re-scoring REV-0029) is also
  self-review — record such targets as DEFERRED. Mechanical existence/consistency checks
  (Tier 4) are exempt: checking that a packet HAS a disposition is not re-adjudication.

## Tiers and targets

- **Tier 0 — excluded:** the R2 consolidation surface (WO-0036/0105-0113 code semantics) —
  freshly reviewed three rounds (REV-0029 r1-r3, REV-0033, both dispositioned). Re-enter only
  by a concrete cross-tier lead, and say so in the finding.
- **Tier 1 — closed-WO completion claims (highest expected yield):** for each closed WO in
  `work/completed/**` predating R2 (WO-0001..WO-0035 window), re-verify its done-when/claims
  with fresh probes against the CURRENT tree: named tests exist, run, and can fail (the
  REV-0029 P0-4 inert-pin class — spot mutation checks where cheap); claimed behavior still
  holds under post-R2 semantics; deviations recorded in the WO actually happened.
- **Tier 2 — docs-vs-code conformance:** ADR-001..ADR-009 decision text and
  `docs/INVARIANTS.md` INV-001..INV-089 vs current code and pins (REV-0029 precedent: docs
  overclaimed in four places). Verify each "Pinned by:" list names real, passing,
  failure-capable tests. ADR-010/INV-090/091 only via cross-tier lead (Tier 0).
- **Tier 3 — queue/backlog currency:** WO-0022 (superseded by executed reviews?), WO-0029
  (placeholder needing re-cut — verify its DONE/PARTIAL cross-references), WO-0102/0103/0104
  (are the REV-0022 remediation gates actually cleared or still standing?), W3/W4 seed notes.
  Plus two stranded lines preserved as `archive/*` branches during the 2026-07-20 cleanup:
  `archive/claude-wo-0001-install-checks-2x5ys8` (tip `fc81951` — 47 commits of finished
  WO-0102 auto-review work, ancestors of nothing on master: is the "WO-0102 is complete"
  claim in WO-0104's banner satisfied on master, or stranded on that line?) and
  `archive/collab-sol-0001` (tip `38180e1` — 22 W3-era commits incl. the WO-0019a merge:
  re-landed via another path, or lost?).
  Output: per-item verdict CURRENT / STALE / SUPERSEDED + evidence, for the planning seat.
- **Tier 4 — review-packet integrity:** every `work/review/REV-*` and FINDING-* file: has a
  result + disposition or a recorded supersession; verdict↔disposition consistency; dangling
  packets (planning-time example: `REV-0030` has `result.md`, no `disposition.md`). Purely
  mechanical; no verdict re-scoring.

## Method (binding)

- Verification-first: every claim checked against fresh command output or file:line reads;
  no reliance on conversation memory or this charter's own assertions (re-derive them too).
- Finding format: AGENTS.md taxonomy — P0/P1, file:line, why it matters, what resolves it;
  concrete repro or probe output for behavioral claims; per-tier verdict
  (CLEAN / FINDINGS(n) / DEFERRED) + an explicit could-not-verify list.
- Temporary probe harnesses live under the packet folder and are clearly named as probes;
  they never enter `tests/` and never mutate app state files.
- Remediation proposals: name the fix shape and a candidate WO title — do NOT create, number,
  or activate work orders; the planning seat cuts them from the packet.
- **Immediate-surface rule:** a P0 on a LIVE safety surface (order submission, fills,
  quarantine, kill switch, flatten) is surfaced to Ameen the moment it is confirmed — not
  held for the packet's end.

## Required commands

```bash
ruff check . && mypy app/ && lint-imports        # baseline: confirm the anchor tree is green first
pytest -q                                        # baseline suite state, recorded in the packet
git diff --stat                                  # at close: work/review/AUDIT-0002-priorwork/** ONLY
```

## Acceptance criteria

- [ ] Packet `work/review/AUDIT-0002-priorwork/report.md` (+ findings/evidence files): every
      tier covered or explicitly DEFERRED with reason; builder map recorded per target.
- [ ] Zero edits outside the packet folder (git diff proof pasted).
- [ ] Every finding evidence-backed and reproducible; every DEFERRED target named for the
      other seat.
- [ ] NEEDS-INPUT/remediation-candidate list batched for Ameen (planning seat cuts WOs).
- [ ] Fable DONE block; `VERIFIED` = audit executed per charter, NOT "repo is clean".

## Stop conditions

Stop the tier and record it if: a probe would require mutating app state or calling a broker;
a target demands self-adjudication (defer instead); scope pressure ("just fix it while
you're there") — the answer is always a finding, never an edit. Session budget exhausted →
close the packet with covered/uncovered tiers explicitly listed; an incomplete audit that
says so is acceptable, a silently partial one is not.

## Model-tier rationale

`strong` — adversarial re-derivation of completion claims across eras of the codebase;
REV-0029 demonstrated both the yield and the subtlety (six in-process lenses missed three
P0 classes).

## Notes

- Sequence after (or interleaved behind) WO-0116 so the audited tree's bookkeeping is
  truthful; read-only, so it may run beside WO-0114/0115 lanes without conflict.
- AUDIT-0001 spawned WO-0036 — the precedent for findings → separately authorized work.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`; packet remains in `work/review/` per review retention.
