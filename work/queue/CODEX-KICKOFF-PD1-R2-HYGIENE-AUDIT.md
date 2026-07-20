# Codex kickoff — consolidated: hygiene sweep + prior-work audit + PD-1 + R2 backfill verification

> Operator launch prompt (drafted by the planning seat, 2026-07-20). Paste into a fresh Codex
> session in `automation-alpaca`. Remediation of audit findings is explicitly OUT of this
> session — it runs later, separately authorized.

---

Codex, you are the implementer/auditor seat in `automation-alpaca`. Read `AGENTS.md`, then the
`CLAUDE.md` safety core — both bind on everything below. Execution discipline is Fable v3
(`.ai-os/templates/fable-core-v3.md`): GATE before building, TDD, fresh pasted evidence, FIX
blocks with root cause, dispositions on close. No completion claims without evidence.

## Setup and anchor

- Branch from current `master` — it already contains the planning artifacts
  (`work/queue/WO-0114..0117` + `PD1-R2-PLANNING-PACKAGE.md`, merged 2026-07-20) and the code
  anchor `88833e3d` (PR #9 merge; no app/test code has changed since).
- Work on one feature branch. Never push to `master`. No PR unless I ask.
- Paper-only posture: no live trading, no Alpaca credentials in this session at all — no lane
  below needs a broker.

## Mode notes (Codex Local vs Codex Cloud)

- **Local (Windows, the operator's clone):** use the existing `.venv`. Lane B's real-DB
  artifact is reachable here (the D-BF-5 default keeps it on this machine) and the
  planning-package §5 runbook is PowerShell-native. Keep ALL pytest scratch in the OS temp
  dir (pytest's default basetemp) — never create repo-root scratch dirs (the `.pytest-tmp-*`
  class; gitignored since 68f5cfe, but the tree stays clean).
- **Cloud (GitHub):** bootstrap first — Python 3.12 venv, install the project + dev tools per
  `pyproject.toml`, then run a baseline gate (`ruff check . && mypy app/ && pytest -q
  --collect-only`) before any lane and paste it as your environment evidence. Treat Lane B's
  artifact as unavailable unless my launch message explicitly provides it into the cloud
  environment — the D-BF-5 default keeps real paper data off remote runners, so expect Lane B
  to end `NEEDS-INPUT` here. Translate runbook commands to bash command-for-command.

## Your four lanes, in order

**Lane H — hygiene sweep (`work/queue/WO-0116-work-ledger-hygiene-sweep.md`). Start here.**
Flip/disposition/move/ledger ONLY what evidence proves finished; append-only ledger; zero
deletions (batch deletion recommendations for me); zero historical-body rewrites; ambiguity →
NEEDS-INPUT batch; correctness doubts → hand to Lane A as targets, never fix. Activate the WO
(status → ACTIVE, move to `work/active/`) as your first commit, and close it out with the work.

**Lane A — findings-only audit (`work/queue/WO-0117-prior-work-audit-charter.md`).**
Run AUDIT-0002 per the charter: Tier 1 closed-WO completion claims (fresh probes, inert-pin
checks), Tier 2 ADR/INVARIANTS-vs-code, Tier 3 queue currency, Tier 4 review-packet integrity.
Findings only — you edit nothing outside `work/review/AUDIT-0002-priorwork/`. **Seat rule:**
you built WO-0106 and WO-0113 — record them (and any re-scoring of your own REV-0029 verdicts)
as `DEFERRED — other-seat audit required`; do not self-adjudicate. A confirmed P0 on a live
safety surface is surfaced to me immediately, not held for the packet. Remediation happens in
a separate session I will authorize from your packet.

**Lane P — PD-1 release valve (`work/queue/WO-0114-pd1-needs-review-release-valve.md`).**
BLOCKED until I ratify D-PD1-1..4 (register: `work/queue/PD1-R2-PLANNING-PACKAGE.md` §2). If
my launch message ratifies them (see the decision block below), activate and execute the WO
exactly as scoped: red-first, both stores + restart parity, the full test matrix, no venue
calls, no synthetic fills, ADR-012 + INV-096 + hardening-gate updates shipped with the change.
Your implementation then queues an independent review packet for the CLAUDE seat (next free
REV id) — your own session's validation does not count. If I have NOT ratified, do not touch
Lane P code; you may draft the ADR-012 text and test skeletons as proposals inside the WO's
notes for my review, nothing more.

**Lane B — R2 real-data backfill verification (`work/queue/WO-0115-r2-real-paper-backfill-verification.md`).**
BLOCKED until I answer D-BF-5..7 and supply the real DB artifact. No artifact ⇒ the lane ends
`NEEDS-INPUT` — synthetic fixtures cannot satisfy this gate. With the artifact: follow the WO
and the PowerShell runbook in the planning package §5 — immutable source (SHA-256 ×3, `mode=ro`
URI only, never the store initializer), classify every working-copy write to one of the 8
named startup mechanisms, second-open idempotency, OBS-3 characterization (report-only),
verdict `VERIFIED` or `BLOCKED`/`NEEDS-INPUT`.

## My decision block (I will edit this at launch; unanswered = lane stays blocked)

- D-PD1-1 (provenance): [ ] default (hybrid-honest) / [ ] alt A / [ ] alt B / [ ] pending
- D-PD1-2 (status name): [ ] default `operator_reconciled` / [ ] other: ____ / [ ] pending
- D-PD1-3 (surface): [ ] default API-only / [ ] API+cockpit / [ ] pending
- D-PD1-4 (fills): [ ] default separate-commands, same WO / [ ] own WO / [ ] atomic / [ ] pending
- D-BF-5 (artifact): path/handling: ____ / [ ] pending (no artifact yet)
- D-BF-6 (fixtures): [ ] default yes-gated / [ ] report-only / [ ] pending
- D-BF-7 (anomalies): [ ] default report-only / [ ] pending

## Cross-lane rules

1. Order: H first (truthful tree), then A; P/B whenever unblocked — they are independent of H/A
   and of each other. Separate commits per lane; never mix a hygiene flip with a code change.
2. The safety core and human-gated surfaces are never overridden by momentum: order
   submission, cancel/replace, kill switch, flatten, event-log truth, schema/migration,
   deletions of tests/docs/ADRs all stop for explicit approval.
3. Batch questions: keep every lane's NEEDS-INPUT items in one running list and surface them
   together; don't stall an unblocked lane on another lane's question.
4. Evidence discipline everywhere: `VERIFIED` / `UNVERIFIED` / `BLOCKED` / `NEEDS-INPUT` only,
   with pasted fresh output. Close-out ships with the work (status flip + disposition + ledger
   + file move in the same commit — CI enforces it).
5. End-of-session deliverable: per-lane status table; commits pushed to your branch; the
   AUDIT-0002 packet; the consolidated NEEDS-INPUT batch; nothing merged, no PR.
