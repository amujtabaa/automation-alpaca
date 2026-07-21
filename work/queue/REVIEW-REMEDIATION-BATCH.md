# ULTRA-batch review remediation — triage + WOs + operator gates

> Planning-seat artifact, 2026-07-21. Consolidates every finding from the four independent
> Claude-seat reviews (REV-0034/0035/0036/0037, all deposited in their packets on this branch)
> plus the two Codex self-review P1s. **No P0. No live safety-invariant violation. No
> economic-truth hole. All four gated reviews PASS** (ACCEPT / ACCEPT-WITH-CHANGES). This note
> lives on `codex/ultra-beta-batch`; the remediation runs on this branch so the whole batch
> merges to master as one clean fast-forward.

## Verdict summary

| Review | WO | Verdict | Blocking findings |
|---|---|---|---|
| REV-0036 | 0121 safety-doc labels | ACCEPT | none |
| REV-0034 | 0127 ADR-009 gate | ACCEPT-WITH-CHANGES | C-1 (P2) stale anchors, C-2 (P3) range → **WO-0133** |
| REV-0037 | 0124 cancel convergence | ACCEPT-WITH-CHANGES | none (2 P2 advisory) |
| REV-0035 | 0114 **release valve** | ACCEPT-WITH-CHANGES | **P1-1 inert-pin** + P2-1 → **WO-0132** |
| self-review | 0123 recorder | P1 | unbounded at max_segments=1 → **WO-0130** |
| self-review | 0125 replay | P1 | FSM-illegal transitions accepted → **WO-0131** |

## Remediation WOs (drafted, this branch)

- **WO-0130** — recorder retention bound + bootstrap external-venv guard (non-gated, cheapest, first).
- **WO-0131** — envelope replay fails closed on FSM-illegal transitions (**gated event-truth**;
  stages REV-0038 for the Claude seat).
- **WO-0132** — release-valve `HUMAN_ATTESTED` fill-rail direct pin (REV-0035 P1-1) +
  `claim_occurrence` conservatism (P2-1); Claude-seat re-verifies the mutation, appends the
  REV-0035 disposition.
- **WO-0133** — ADR-009/spec citation re-baseline + range reconciliation (REV-0034 C-1/C-2);
  runs LAST so anchors settle against the merged tree.

## Advisory / deferred (NOT auto-executed — recorded for the operator)

- **REV-0037 P2-1 — malformed-lineage → deduped `needs_review` record.** Today a persistently
  corrupt cancel lineage is surfaced only by a recurring log, not a durable operator-visible
  record. Emitting a deduped `needs_review` is a NEW human-gated event-log write → its own
  future WO + decision, deliberately not folded in. (Pre-existing WO-0036 behavior, not a
  regression.)
- **REV-0037 P2-2 — per-child escalation isolation.** A permanent recovery-write fault on one
  exhausted child could stall sibling cancels in a legacy multi-child envelope (v1 has one
  child, so low reachability; fail-closed throughout). Advisory follow-up.
- **REV-0035 P2-2 / REV-0037 caveat — full CI-form suite on pinned Python 3.12.** The reviews
  ran under 3.11 (env limit) and reproduced the load-bearing subset + mutations; a fresh full
  `--cov` run on 3.12 before beta reliance closes the gap. Not a code fix — a verification step
  (fold into the merge checklist).

## Operator gates (human-only; after remediation lands)

1. **Accept ADR-012** (release valve) — Proposed today; beta reliance gates on acceptance +
   REV-0035 dispositioned + WO-0132's pin. Yours to give.
2. **Accept ADR-009** (signal seat) — Proposed; flips to Accepted after WO-0133's anchors land
   and REV-0034 is dispositioned. This is what unblocks Signal Seat R4–R7.
3. **Merge decision** — once WO-0130/0132/0133 close, WO-0131 returns REV-0038 ACCEPT, and the
   two ADR acceptances are given, the branch fast-forwards to master. The four review results +
   dispositions ride along.

## Sequencing

WO-0130 (independent) ∥ WO-0132 (release-valve, shares core.py — rebase) ∥ WO-0131 (gated, own
review) → then WO-0133 last (anchors settle). None touches the others' primary surface except
core.py (WO-0132 vs the already-landed WO-0124 code — rebase, no live conflict). The Claude-seat
re-verifications (REV-0035 pin recheck; REV-0038 replay review) run out-of-session after.
