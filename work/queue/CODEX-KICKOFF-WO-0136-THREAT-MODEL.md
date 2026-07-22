# Codex CLOUD kickoff — WO-0136 signal-endpoint threat model (mid-tier, doc-only)

> Operator launch prompt, drafted by the planning seat 2026-07-22. Paste into a FRESH **cloud**
> Codex session (bounded mid-tier documentation work — cloud-suitable per the repo-primer
> execution preference; no local strongest-model needed). Doc-only, non-gated, closes out
> fully in-session. Feeds Signal Seat R5 — its GAP register becomes R5's requirement list.

---

Codex, you are the implementer seat producing **WO-0136 — the signal-endpoint threat model**, a
STRIDE analysis of the signal seat's first external-input surface, written *before* R5 builds the
endpoint/auth/launcher so R5 inherits an adversarial requirements checklist. Read `AGENTS.md`, the
`CLAUDE.md` safety core, then **`work/queue/WO-0136-signal-endpoint-threat-model.md` IN FULL — it is
your complete contract** (required content, allowed/forbidden paths, acceptance, stop conditions).
This is analysis, not implementation: you synthesize accepted ADR/spec text + the pre-found attack
corpus into one document; you never edit accepted text or code.

## Setup — sync first, verify, then work

- **Step 0 (execute yourself):** `git status --short` (clean, else STOP) → `git fetch origin` →
  confirm `git log --oneline -1 origin/master` is `8d8c0d8` **or a descendant** →
  `git checkout -b codex/wo-0136-threat-model origin/master` →
  `git fetch origin archive/claude-wo-0001-install-checks-2x5ys8` (the pre-found attack corpus lives
  on this archive ref; you read it with `git show origin/archive/claude-wo-0001-install-checks-2x5ys8:<path>`).
- **Precondition guard (fail closed — ALL must hold, else STOP and report which failed):**
  1. `work/queue/WO-0136-signal-endpoint-threat-model.md` exists on your branch.
  2. `docs/adr/ADR-009-signal-seat-boundary.md` shows **Status: Accepted** (2026-07-21).
  3. `docs/adr/ADR-013-external-ingress.md` shows **Status: Proposed** (the Option-C seed you size,
     never approve).
  4. The archive ref is reachable:
     `git show origin/archive/claude-wo-0001-install-checks-2x5ys8:app/launch_guard.py | head -3`
     returns content.
- Never push master. No PR unless asked. Paper-only; zero credentials/broker/live. Pytest scratch
  in OS temp if you run anything (you shouldn't need to — this is doc-only).

## Decision block (pre-checked = ratified on paste; edit to override)

- [x] D-TM-1 **Advisory-only, hard boundary.** The deliverable is `docs/THREAT_MODEL_SIGNAL_SEAT.md`
      only. You NEVER edit `docs/adr/**`, `docs/spec/**`, `pkl/**`, `app/**`, `tests/**`, or
      `cockpit/**`. Findings propose; they never amend accepted text.
- [x] D-TM-2 **Every threat row terminates in exactly one of:** an existing accepted control (cited
      to a spec/ADR `file:line` anchor), an explicitly accepted risk (naming the ratifying
      decision), or a numbered **GAP** owned by a rung (R5 / R6 / R7 / ADR-013 / operator
      NEEDS-INPUT). No orphan threats — a self-audit table at the end proves zero orphans.
- [x] D-TM-3 **GAP register is written R5-ready:** each gap phrased as a *testable requirement*
      ("R5 must refuse …", never "R5 should consider …"), so the planning seat can lift the R5 rows
      straight into the R5 WO. This is the document's primary downstream product.
- [x] D-TM-4 **Archive citations use archive-ref provenance** — never bare `REV-0024`/`REV-0025`
      ids (they collide with master's namespace): cite as
      `archive REV-00xx @ origin/archive/claude-wo-0001-install-checks-2x5ys8`.
- [x] D-TM-5 **Option C (internet/webhook producers) is SIZED, not approved.** The internet-attacker
      section scopes what the future ADR-013 must answer; it approves nothing and proposes no
      deployment. Internet exposure stays STRUCTURALLY excluded today (loopback bind + construction
      bind guard + Funnel prohibition).
- [x] D-TM-6 **Non-gated close-out in-session.** No REVIEW packet. Close out fully in the finishing
      commit (below). A confirmed **P0-equivalent hole in ACCEPTED text** (a safety-surface threat
      the accepted controls demonstrably fail to cover) is the ONE exception: STOP, record the
      decision gap, and escalate to the operator immediately — do not silently downgrade it to a GAP
      row and do not draft an ADR amendment yourself.

## Continuity (short session; may still compact)

FIRST commit: `work/active/WO-0136-STATE.md` with this decision block **as pasted** + a section
checklist (assets/boundaries · attacker profiles · STRIDE-per-surface · appendix A A-1/A-4 · appendix
B pre-found attacks · GAP register · non-goals · self-audit). Update it at each section boundary.
After any pause/compaction re-read, in order: this contract → the state file → the WO file. Verify
with `git log`/`git status`, never memory.

## The work (mirror WO-0136 §"Required content"; the WO is authoritative)

Produce `docs/THREAT_MODEL_SIGNAL_SEAT.md`:

1. **Assets & trust boundaries** — producer keys, operator key, event-log integrity, the
   approval→conversion integrity chain (a signal NEVER executes without HUMAN approval — the crown
   jewel), host/port exposure, cockpit availability; boundaries per D-SIG-1 Option A (localhost
   producer), Option B (tailnet-serve config flip), Option C (internet, FUTURE/forbidden), browser↔
   cockpit↔API, env key custody.
2. **Attacker profiles** — malicious/compromised local producer; a non-producer local process;
   a tailnet node (Option B); an internet attacker (shown STRUCTURALLY excluded today);
   a compromised operator browser; operator misuse (fat-finger approval of a stale/spoofed thesis).
3. **STRIDE table per surface** — `POST /api/signals`, operator read/approve/reject routes, the
   producer-release route, the launcher/bind path, key custody/rotation, event log/audit, cockpit
   header plumbing. Ground each on the accepted spec (esp. `docs/spec/signal-seat/03-rails.md`,
   `04-auth-and-api.md` incl. the §1a route matrix) and ADR-009 A-1/A-4.
4. **Appendix A — clause traceability:** every ADR-009 A-1 and A-4 clause ↔ ≥1 threat row it
   mitigates. A clause mitigating nothing, or a threat with no clause, is itself a finding.
5. **Appendix B — pre-found attacks:** one row each, showing which accepted control now covers it —
   or a GAP. Mandatory rows: REV-0022 F-001 (unauthenticated reads / transport-credential boundary,
   master packet); archive REV-0024 (ASGI-seam bind-guard unenforceability; the **paced-hostility
   hole** — 10,080 events over 7 days at 1 req/min without breaching a refill bucket); archive
   REV-0025 (reachable-503 listener; non-mutation-sensitive launch proof; non-linearizable/durable
   budget; joint-enablement contradiction; **`POST /api/session/close` missing from the auth matrix**).
6. **GAP register** — numbered, owner rung, testable-requirement phrasing (D-TM-3).
7. **Non-goals** stated in the doc: no code, no spec/ADR edits, no pen-testing, no new deps;
   Option C sizes ADR-013 but approves nothing.

## Rules

1. Doc-only. Allowed paths: `docs/THREAT_MODEL_SIGNAL_SEAT.md` and `work/**`. Everything else is
   forbidden (WO-0136 §"Forbidden paths"). Scope pressure toward code/tests/spec → refuse; that's
   R5/R6/R7 work.
2. Advisory-only: findings propose, never amend accepted text. A P0-equivalent hole in accepted text
   escalates immediately (D-TM-6).
3. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT; anchor claims to `file:line`.
4. `git diff --stat` at close must be docs-only + `work/**`. Ledger append-only.

## Close-out (non-gated — ships in the finishing commit; CI enforces)

Status flip QUEUED→CLOSED, disposition `[RESULT_SUMMARY_KEPT]` (add `PKL_UPDATED` only if you
genuinely distill a security-posture PKL page — optional, not required), append a `work/ledger.jsonl`
line, move `work/queue/WO-0136-…md` (activate to `work/active/` first, then) to
`work/completed/keep/`, and move `work/active/WO-0136-STATE.md` into the close-out. Run
`python .ai-os/scripts/check_work_order_disposition.py` and `python .ai-os/scripts/check_ledger.py`
(both must pass) before the finishing commit. Push `codex/wo-0136-threat-model`. Report the GAP
register's R5 rows in your final summary so the planning seat can lift them. Nothing merged — the
operator fast-forwards master.

## NOT in this session

- The R5a/R5b WO drafting (planning seat, after — it consumes this GAP register).
- Any `app/`, `tests/`, `cockpit/`, ADR, or spec change.
- Approving Option C / ADR-013 (this doc sizes it only).
