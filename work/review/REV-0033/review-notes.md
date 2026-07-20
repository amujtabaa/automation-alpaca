# REV-0033 review notes (Claude, independent seat) — working log

Target: 194343c..9a7af3b (frozen implementation), close-out head f027752 (app/tests identical — verified).
Diffstat: 86 files, 21,655 insertions, 1,321 deletions (verified).

## Progress
- [x] Synced to f027752; frozen-range claim VERIFIED (git diff 9a7af3b..f027752 -- app tests: empty)
- [ ] P1 gates reproduced
- [ ] P2 packet read
- [ ] P3 cluster deep-reads
- [ ] P4 mutations + fresh probes
- [ ] P5 verdict

## Evidence

### P1 gates (local, at f027752)
- ruff check + format: PASS (258 files). mypy app/: PASS (64 files). lint-imports: 6 kept/0 broken.
- git diff --check 194343c..9a7af3b: clean. AI-OS hygiene: all 5 PASS. Frozen-range diffstat matches (86/21655/1321).

### P4a fresh probes (reviewer-authored, both stores)
- INV-002: 29/29 PASS incl. position-positive explicit QUARANTINED (one durable event), raw FILL retained,
  public list + BUY-mint refusal + pre-existing CREATED BUY claim refusal, ALL re-verified after SQLite
  close/reopen; LOCAL-authority excess rejected with zero mutation.
- INV-081: 10/10 PASS — epoch closes at ADMISSION (create_candidate refuses "exit may execute"),
  exit driven to flat, intent converges, fresh post-convergence candidate admits+dispatches, no regrow.
- INV-060: 12/12 PASS — ordinary flatten under HALTED denied WITHOUT consuming the grant; explicit
  capability consumes exactly once; grantless emergency call refused outright (InvalidOrderError).

### P3 agent: emergency capability cluster — all 6 checks VERIFIED
- Flag flows facade->store->planner; sole production True-caller is the emergency facade path.
- Reuse re-runs all ADR-003 preconditions before the short-circuit; no second grant write.
- Outcome table: BUYS_OPEN retains; FLAT/EXISTING/CREATED consume atomically; rejects roll back to one reusable grant.
- No await inside flatten lock hold -> no double-spend interleave; session-mismatch raises; grant is session-scoped.
- Parity: structurally identical; NIT: memory-only _assert_symbol_envelope_preempted assertion (defensive, no sqlite twin).
- NUANCE (candidate finding): FLATTEN_EXISTING consumes the single-use grant against a merely in-flight
  pre-existing PROTECTION_FLOOR exit; if that dies venue-side, position held under HALTED with grant spent.
  Recoverable (re-authorize allowed). Judged design-consistent ("one authorized exit; a live exit existed").

### P3 agent: explicit-quarantine projection cluster — all 6 checks VERIFIED
- One pure projector (projectors.py:141-194) collects explicit QUARANTINED + negative-fold FILL; memory passes
  whole event list; sqlite selects IN ('fill','quarantined') (the prior P1 site, fixed); all three consumers
  (public list, candidate mint memory:3733/sqlite:5237, final claim memory:4000/sqlite:5513) route through the
  shared lock-held helper. No FILL-only ADR-001 gate remains anywhere (full sweep listed).
- Producer authority: LOCAL/synthetic overfill -> FILL_REJECT, no quarantine; QUARANTINED only when
  broker-authoritative, co-written atomically with the raw FILL (both stores, both fill paths).
- Restart: sqlite derives from persisted rows per call (no cache); pinned by store-parity tests.
- Never mis-consumed: not a lifecycle status; never folds position; MANUAL_FLATTEN/PROTECTION_FLOOR exits
  short-circuit BEFORE the quarantine gate (risk-reducing SELLs unblocked).
- DOC NIT (candidate finding, LOW): projectors.py:152-158 docstring says quarantine holds "until an audited
  reconciliation/review explicitly clears it" but NO clear path exists — permanent cross-session latch.
  Fail-safe (stronger than required); docstring overstates. Flag for doc fix / operator confirmation.

### P3 agent: accepted-submit fallback cluster — all 5 checks VERIFIED
- 5 producers collapse to 2 shared finalizers (monitoring._finalize_accepted_submit; reconciliation
  ._finalize_accepted_envelope_order); audit best-effort, fallback written on recovery-failure independent
  of audit; exact identity (dedupe accepted_submit_unpersisted:{order}:{broker} + full scope); cancellation
  branches route through recovery/fallback too.
- Consumers complete: cross-side rails, direct-SELL single-flight, final claim + CAPI, safe-local-cancel
  exclusion (any uncertainty event blocks local cancel — fail-safe), startup collision check. No omitted gate.
- Not mis-consumed (absent from lifecycle/fill projectors); no second venue call (repair takes no adapter;
  redrive marks fallback orders already_covered); replay idempotent (dedupe + recovery (local,broker) identity).
- Restart: sqlite rebuilds uncertainty index from persisted events at initialize; memory rebuilds from its
  canonical event log (projection, not side-dict).
- NIT (cosmetic): monitoring.py:2567 recovery write omits client_order_id=order.id (envelope twin passes it);
  all identity keys on (local_order_id, broker_order_id) so no consumer affected. Normalize-worthy.

### P2 packet/record skim
- WO-0113 record: fable_gate + per-cluster VERIFIED entries + C1-C5 matrices all present in progress log
  (C1 choke-point matrix, C2 twin-write matrix incl. "nine" closed parity gaps, C3 consumable-state,
  C4 projection-scope, C5 exclusion audit). REV-0031 disposition: ACCEPT-WITH-CHANGES; REV-0032: BLOCK;
  both with per-finding disposition sections.
- NOTE for result.md: the five RATIFIED_YES operator decisions are evidenced by the operator's own
  in-chat YAML relay + the autonomous-completion prompt to Codex (not an in-repo signed artifact);
  operator should confirm they match intent at merge.

### P4b planned mutations (execute after suite finishes; in-place edit-back only)
M1 sqlite quarantine projection -> FILL-only (sqlite.py ~6764): expect SQLite list/mint/claim pins red (3), memory green.
M2 memory create_candidate exit-epoch admission refusal neutered: expect lifecycle-closure admission pin red.
M3 memory safe-local-cancel uncertainty exclusion neutered (_local_created_cancel_eligible_unlocked): expect safe-local-cancel pin red.
M4 envelope accepted-ack fallback write neutered (reconciliation.py ~1451 record_accepted_submit_uncertainty): expect submit-acceptance-fallback / wo0111 double-persist pins red.
M5 emergency isolation neutered (memory flatten: treat ordinary flatten as override_active when grant exists): expect isolation pin red (ordinary-flatten-denied test fails).
M6 memory terminal-cleanup source-exclusion or one-reconcile neutered: expect store-parity/terminal-fill pin red.

### P4b mutations — ALL CONFIRMED (exact reds; in-place restores; tree pristine after)
M1 FILL-only sqlite quarantine reader -> 7 exact sqlite pins red (mint/claim/restart, both corpora); restored green.
M2 memory epoch-admission neuter -> test_candidate_creation_is_refused_during_exit_preemption[memory]; restored.
M3 memory uncertainty exclusion neuter -> test_accepted_direct_sell_cannot_be_canceled_as_local_created[memory]; restored.
M4 envelope fallback producer removed -> double-persist owner pins red (submit/reprice x audit-ok/fails) + both restart-repair pins; restored.
M5 ambient-grant regression -> test_ordinary_flatten_cannot_consume_emergency_grant[memory]; restored.
M6 source-exclusion removed -> terminal_fill_excludes_source... + wo0112 F2 pin; restored.
Post-restore: git diff app/ empty (PRISTINE); 117-test targeted sweep green.

### Remaining gates reproduced
Codex oracle 61/61; Claude oracle 22+6 skips; hardening 12/12; scaling passed (1.063/10.009/9.102, limits unchanged).
Full suite: exit 0 (1 local run); no Hypothesis StopTest in my run. INV-003/004 probes PASS (durable
fill_duplicate_conflict audit on changed-price replay; filled_quantity caps at immutable qty).

### VERDICT: ACCEPT-WITH-CHANGES (see result.md) — F1 doc/contract quarantine-clear; F2 scope-auth
window; F3 client_order_id nit; F4 grant-on-existing design confirm; F5 notes.
