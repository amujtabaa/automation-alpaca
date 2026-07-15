---
type: Review Request
rev_id: REV-0026
title: ADR-009 re-review — REV-0025 BLOCK remediation (D-1 construction-refusal bind, D-2 release-gate, F-002..F-007)
status: WITHDRAWN   # 2026-07-14 — Ameen LOCKED the spec after REV-0025 rather than run a fifth spec-only round; remaining items are WO-time contracts verified against real code + TDD. The REV-0022→0025 packets are the amendment-design review record. This request is retained for provenance only; do NOT dispatch.
targets: ["ADR-009 (A-1 clause 6, A-4)", "docs/spec/signal-seat/**", "WO-0102/0103/0104", "pkl/architecture/signal-seat.md"]
human_gated_surfaces: [order-submission, event-log-vocabulary, schema-migration, transport-boundary]
prior_packet: REV-0025 (verdict BLOCK, 7 P1s — this packet verifies their closure)
commit_range: SET-ON-DISPATCH   # branch under active fix — Codex reviews whatever is pushed when pointed at this request; freeze the reviewed SHA in result.md frontmatter
created: 2026-07-14
---

# Review Request REV-0026 — did the D-1/D-2 remediation close REV-0025-F-001..F-007?

## Your role
Independent review seat — same protocol as REV-0022/0024/0025. Re-derive from the repo, findings
only, do not push fixes. This is a **targeted re-review**: REV-0025 found **no A-2/A-3 regression**
and credited several sub-items as landed — do not re-litigate those unless the new changes regressed
them. Your question is narrow: **do the two human-decided resolutions + the five mechanical fixes
close REV-0025-F-001..F-007 as binding, internally coherent, implementable text an implementer cannot
lawyer around?**

## What changed since your BLOCK (reviewed `209496d` → this range)
Two design decisions were made by the human (Ameen, 2026-07-14) and drafted, plus five mechanical fixes:

- **F-001 → D-1 construction-time bind refusal.** The proxy-private guarantee moves off the
  reachable-503 posture onto **app construction/import**: the sanctioned launcher (`app/server.py`,
  `python -m app`) mints an **opaque one-shot code-owned capability** (explicitly NOT an env var,
  config value, importable pre-authorized `app`, or zero-arg factory) before importing the app; with
  `signal_seat_enabled` on, **building the app without the capability raises**, so the module-level
  `app` import target is removed/refuses and a bare `uvicorn app.main:app` (any `--lifespan`) fails at
  **import** — Uvicorn opens **no listener** (connection refused, true pre-serve failure). The 503
  ASGI request guard is retained only as **defense-in-depth**. (ADR A-1 clause 6, 04-auth §1, WO-0102.)
- **F-002 → mutation-sensitive launch proof.** The WO-0102 subprocess test sets all *unrelated*
  startup preconditions (operator key, producer map, rails present), asserts the **exact A-1 bind/
  provenance failure** (not a generic pre-serve error another guard could supply), adds a same-config
  **sanctioned-loopback positive control** reaching a ready listener, and asserts socket-level
  connection-refused for the hostile bare-uvicorn cases.
- **F-003 → linearizable atomic budget.** The check-reserve-debit + terminal event append are one
  memory-lock/SQLite-transaction; a step-2 pass does not pre-grant a slot (re-check-and-debit at step
  4); concurrency/slow-body/crash tests required. (ADR A-4, 03-rails §1a/§4, WO-0104.)
- **F-004 → restart-durable consumed budget.** Both the pinned per-cycle limit AND the
  consumed/remaining count are durable rail state, restored before serving and replay-reconstructable;
  a restart cannot zero consumed (which would grant a fresh budget without release). (03-rails §1a,
  02-lifecycle §4, WO-0104.)
- **F-005 → D-2 release/deployment gate + permanent guard.** The rails-presence guard is a **standing
  invariant WO-0104 satisfies by wiring the real provider — never deleted**; production is proven to
  construct the real provider; fakes are confined to a test-only construction path production can't
  select; the WO-0103 conversion half is a binding release/deployment gate + a **joint mounted-app
  conversion oracle** (ingest → approval → exactly one atomically-linked intent), not a new runtime
  check; the route matrix asserts **required routes exist**. (ADR A-4, 03-rails §2, WO-0102/0103/0104.)
- **F-006 → propagation.** WO-0102's "zero store writes" now carries the one epoch-opener carve-out;
  "write-free" is reserved for post-opener rejects; every "constant/bounded total storage" claim is
  narrowed to attributable-rejection traffic (accepted signals explicitly rate-bounded, not globally
  finite — matching the Option-E scope correction).
- **F-007 → matrix route.** `POST /api/session/close` classified operator-only in the §1a matrix.
- **Extras (from the concurrent auto-review):** boundary rejection precedes idempotent replay so a
  quarantined producer's identical replay is 403/429 not 200 (01-schema §3); `SIGNAL_APPROVED` carries
  `record_id`.

## Questions to answer
1. **F-001 closed?** Does construction-time refusal actually prevent a listener on a forbidden bind —
   is the capability genuinely unforgeable by the bare-uvicorn/import path (no env/config/importable/
   zero-arg escape)? Is the module-level `app` removal/refusal airtight? Is flag-off unaffected?
2. **F-002 closed?** Is the proof now mutation-sensitive — would removing *only* the bind or *only*
   the provenance check fail a test, with unrelated guards satisfied and a loopback positive control?
3. **F-003/F-004 closed?** Is the budget decision linearizable and crash-atomic under concurrency and
   slow bodies, and is consumed budget durable/replay-stable across restart under raised and lowered
   config, in both stores — with no way to earn a fresh budget without `PRODUCER_RELEASED`?
4. **F-005 closed?** Is the guard genuinely permanent-and-satisfied (not deleted), is a permissive
   fake structurally unselectable in production, and does the joint conversion oracle bind the WO-0103
   half so enablement can't happen without atomic conversion? Is the release/deployment gate an
   enforceable statement, not discipline?
5. **F-006/F-007 + extras closed?** Any surviving "zero writes"/"write-free"/"finite total storage"
   contradiction? Is every mounted mutating route classified? Does boundary-vs-replay precedence hold?
6. **Coherence / regressions:** do the new clauses contradict each other, the unamended ADR body, the
   spec, the as-built seams (`app/main.py` construction, `app/store/base.py` atomicity), or the still-
   CLOSED A-2/A-3?

## Where to look
- `docs/adr/ADR-009-signal-seat-boundary.md` §A-1 clause 6 + §A-4 (the review target).
- `work/review/REV-0025/result.md` — your own findings and closure criteria.
- `docs/spec/signal-seat/01..05`; `pkl/architecture/signal-seat.md`.
- `work/queue/WO-0102/0103/0104` — whether the test contracts carry the resolutions.
- `app/main.py` (`create_app`, module-level `app`), `app/store/base.py` (atomicity), `README.md`.

## Verdict vocabulary
`ACCEPT` | `ACCEPT-WITH-CHANGES` (enumerate) | `BLOCK` (enumerate). Write findings to
`work/review/REV-0026/result.md`; Ameen dispositions in `disposition.md`. An ACCEPT/
ACCEPT-WITH-CHANGES clears the gate REV-0022 opened: ADR-009 may then be marked Accepted and
WO-0102..0104 unfreeze per the joint-enablement sequencing.
