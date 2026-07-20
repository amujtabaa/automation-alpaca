# Codex kickoff — session 2 (parallel lane): WO-0119 bootstrap + WO-0118 perf closure

> Runs BESIDE the four-lane session (hygiene/audit/PD-1/backfill). Zero shared files with it
> except `work/ledger.jsonl` close-out appends — an expected, trivial merge conflict (keep both
> lines). Recommended mode: **Codex Cloud** or a second local clone — never the same working
> tree the four-lane session owns.

---

Codex, you are the implementer seat in `automation-alpaca`, session 2 of 2. Read `AGENTS.md`,
then the `CLAUDE.md` safety core. Fable v3 discipline throughout: GATE, TDD where code changes,
fresh pasted evidence, dispositions on close. No completion claims without evidence.

## Setup

- Branch from current `master` (contains WO-0118/WO-0119 in `work/queue/`). One feature branch,
  e.g. `codex/perf-bootstrap`. Never push `master`. No PR unless I ask.
- If in Codex Cloud: bootstrap manually this one time (Python 3.12 venv, install per
  `pyproject.toml`, paste a green `ruff check . && mypy app/ && pytest -q --collect-only`) —
  automating exactly that is WO-0119's job.
- Paper-only posture; zero credentials, zero broker calls, zero `data/` access — neither WO
  needs any of them.

## Task 1 — WO-0119 (`work/queue/WO-0119-cloud-bootstrap.md`). Start here.

Activate it (status → ACTIVE, move to `work/active/`, first commit), execute per its contract,
close it out with fresh-clone + rerun evidence in the same commit as the status flip.

## Task 2 — WO-0118 (`work/queue/WO-0118-perf-stress-scale-closure.md`)

**Check its sequencing gate first:** my launch message states whether Lane P (WO-0114) is
live in the other session. Lane P pending/unratified → proceed. Lane P live → run **Phase 1
(measurement) only** — it changes no files the other session touches — and stop before any
Phase 2 store edit, reporting Phase 1 results as the deliverable.

Phase 1 always: three-run target gate + `R2_STRESS=1` + Claude-ported gate + query plans,
pasted. Phase 2 only on material stress convexity, behavior-preserving per the Cluster E
contract, D9-style operator approval before any new index/DDL. Phase 3: record the beta-scale
budget; never loosen an existing limit — that is my decision, not yours.

## Rules

1. Separate commits per WO; close-out (status flip + disposition + ledger + file move) ships
   in the same commit as the finishing work — CI enforces it.
2. Any `app/store/*` change queues an independent review packet (next free REV id) for the
   Claude seat; measurement-only outcomes need none.
3. NEEDS-INPUT items batch into one list; don't stall Task 1 on Task 2's questions.
4. End-of-session deliverable: per-task status, pushed branch, evidence tables, the
   NEEDS-INPUT batch. Nothing merged, no PR.
