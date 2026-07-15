---
type: Review Request
rev_id: REV-0027
subject: WO-0102 Signal Seat ingestion endpoint — independent CODE review
work_order: WO-0102
reviewed_commit: 5a93f73
scope: signal-seat surface (code, not spec)
date: 2026-07-15
---

# Review Request — REV-0027 (WO-0102 code)

First independent CODE-review packet for WO-0102 (the ingestion endpoint), per the
WO's closeout gate: "a review packet is queued and dispositioned ACCEPT /
ACCEPT-WITH-CHANGES before the work is relied on for a beta milestone." All prior
staged packets (REV-0022/0024/0025) reviewed the ADR/spec **design**; this reviews
the shipped **code**.

## Scope (files)

- `app/api/routes_signals.py`, `app/api/schemas.py` (SignalProposal)
- `app/facade/signals.py`, `app/facade/signal_rails.py`
- `app/launch_guard.py`, `app/server.py` (A-1 bind boundary)
- `app/main.py` (create_app guards, operator-enforcement middleware, actor binding)
- `app/api/deps.py` (credential validation, role separation, get_actor)
- `app/config.py` (signal_* settings, role-separation overlap)
- `app/store/core.py` (plan_signal_ingest, canonical hash, dedupe key, freshness)
- `app/store/memory.py` + `app/store/sqlite.py` (ingest_signal, list_signals — parity)
- `app/events/projectors.py` (project_signal_records fold)

## Review targets

ADR-009 A-1..A-4 + LOCKED spec 00-06 + CLAUDE.md invariants (INV-1..9, safety core):
auth/credential boundary, dedup/replay correctness, dual-store parity, malformed-input
→ quarantine totality, freshness/TTL/expiry, A-1 launch/bind guarantee, projector
terminal-state handling, and forward-compatibility with WO-0103/0104 events.

## Review streams

1. **Codex (GPT-5) GitHub-app auto-review** — reviewed every WO-0102 commit
   (cc346b1..5a93f73, 11 rounds); each round's findings (P0→P2) were folded and
   re-verified through the full gate; the final rounds returned no findings.
2. **Opus fresh-context adversarial deep-dive** — a single-pass independent trace
   of the whole surface against the ADR/spec/invariants (this packet's `result.md`).
