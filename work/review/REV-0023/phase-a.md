# REV-0023 Phase A — W3 Execution Envelope wave, internal adversarial review

- **Reviewed commit:** `f092ca7` (`feat/execution-envelope` tip; `15e6a81` above it is work/-docs only).
- **Method:** four independent critic subagents, fresh contexts, H1–H11 inlined verbatim, pinned SHA:
  spec-attacker (ADR-010 vs implementation), interleaving-attacker (concurrency, real stores + gather),
  test-critic (mutation testing, 13 mutations), completeness-critic (claims vs omissions).
  Test-critic temporarily mutated app code and restored (`git status` clean, baseline 410 passed /
  3 xfailed re-confirmed post-restoration). Interleaving evidence re-run on a pristine detached
  worktree of `f092ca7` to insulate it from the test-critic's concurrent mutations.
- **Charter:** findings only — nothing fixed in Phase A. Raw critic reports retained in the session
  task outputs; probe/repro scripts under the session scratchpad (paths quoted per finding in the
  FINDING files).
- **Baseline:** all W3 suites green at the pin except the two previously filed xfail(strict=True)
  findings. Every finding below is therefore currently UNPINNED behavior.

## 1. Deduplicated findings (ranked)

Cross-critic convergence was strong: the two highest-impact defects were each found independently
by 2–3 critics through different lenses. IDs below are the canonical cluster IDs; per-critic IDs in
parentheses.

| # | Cluster | Sev | H-ref | Found by | One-line claim | FINDING file |
|---|---------|-----|-------|----------|----------------|--------------|
| F1 | Reduce-only unenforced | **P0** | H1 | SPEC-01 | No enforcement seam re-reads live position: 180 sh SOLD against a 0-share position, both venue submits succeeded. | FINDING-W3-reduce-only-unenforced.md |
| F2 | Test-integrity: `or True` tautology + unpinned rails | **P0 (test)** | H1/H9/H7 | TC-01 (+TC-02/04/05/06/08) | Reprice venue-targeting assertion is `X or True`; aiming the venue replace at a wrong order id survived the entire suite (410 passed). Ratchet monotonicity also unpinned (TC-02). | FINDING-W3-test-integrity.md |
| F3 | Redrive re-validation bypass | **P1** | H1/H5/H6 | INT-001 + SPEC-03 + CC-03 (3 independent) | `redrive_staged_envelope_action` re-checks nothing and runs BEFORE decide()'s TTL/phase/stale gates: oversized submit after a raced fill (80 sh vs remaining 40), venue submit after TTL, restart-redrive on zero market data. **WO-0024's status guard does NOT close this — envelope is ACTIVE in every repro.** | FINDING-W3-redrive-revalidation-bypass.md |
| F4 | Multi-leg false-divergence livelock | **P1** | H5/H2 | SPEC-04 + CC-02 (2 independent) | Plan-time "working order" = any submit event EVER (history); write-time = live order NOW. Every envelope's second leg (incl. every tranche exit and stop-triggered continuation) freezes with a false ENVELOPE_PLAN_DIVERGENCE; resume → re-freeze livelock. Devalues the INV-082 defect tripwire on routine flow. | FINDING-W3-multileg-false-divergence-livelock.md |
| F5 | Synthetic-fill envelope bypass | **P1** | H1/H8 | CC-01 | Reconciliation-inferred fills call `append_fill` directly, never `record_envelope_fill`: ceiling silently re-arms; 200 sh reached the venue under a 100-sh ceiling. F4 currently MASKS the venue leg — fixing F4 alone converts F5 into a live oversell. Remediate together. | FINDING-W3-synthetic-fill-envelope-bypass.md |
| F6 | Supersession exposure | **P1 (latent)** | H9/H1 | SPEC-02 + INT-002 (2 independent) | Supersede neither cancels/adopts the predecessor's resting venue order (two live SELLs, 180 sh vs one 100-sh approval) nor conserves remaining (successor resets to full ceiling; a racing fill's decrement is erased). Latent: no production caller of `supersede_envelope` yet; P1 the moment the amendment flow wires up. | FINDING-W3-supersession-exposure.md |
| F7 | Memory `_atomic` misses `_envelopes` | **P1** | H3/H10 | TC-03 | Memory-store rollback doesn't snapshot envelopes: injected crash mid-transition leaves envelope=APPROVED while the log rolls back to CREATED-only — state/log disagree, replay broken in the memory store. Concealed by the sqlite-only atomicity test. | FINDING-W3-memory-atomic-envelope-rollback.md |
| F8 | Lifecycle/eventing gaps (grouped) | **P2/P3** | H2/H6/H7/H10 | SPEC-05..10, CC-04/05/06 | FROZEN-overfill clamps a hard rail and terminates COMPLETED (no BREACHED edge); expiry disposition is one-shot post-terminal (failed venue cancel never retried); disposition cancels emit no envelope-provenance events while `_BUDGET_ACTIONS` counts an event species never written; quarantine pause mislabeled `policy_error` freeze; no envelope projector/replay-parity coverage for the 13 new event types; `replaces_used` has no writer (cockpit budget column reads 0 forever; models.py comment false — doc/code conflict recorded); naive `expires_at` passes approval then TypeErrors tick 1; ADR-010 §5's "write-time rejection ⇒ software defect" is falsified by the repo's own pinned test; Protocol-via-`cast` makes mypy-green vacuous at the seams. | FINDING-W3-envelope-lifecycle-eventing-gaps.md |

Process finding (already remediated): CC-07 — W3-STATE.md was stale at the pinned SHA; corrected in
`15e6a81` mid-review. Noted so Phase B sees the timeline honestly.

Not re-reported (previously filed, honored by all four critics):
FINDING-W3-staged-order-outlives-preemption (P1 → WO-0024) and
FINDING-W3-lase-pullback-structural-hold (P2 → W4/SOL).

## 2. Claims attacked and NOT falsified (consolidated)

Each item below was actively attacked by at least one critic and held:

- **Fill dedupe / INV-076 / H8** — canonical `fill:{order_id}:{source_fill_id}` key holds under
  gather-duplicate races and replay; transitions/raw appends cannot move `remaining_quantity`;
  mutation of the dedupe gate killed (TC M7). Defect confined to the reconciliation *path* (F5),
  not the dedupe mechanism.
- **Single-ACTIVE-per-intent (status level) / H9** — concurrent supersedes yield exactly one ACTIVE
  successor; approval blocks under the same lock; sqlite partial unique index backstop. (F6 breaks
  the *intent* of H9 via the venue order, not the two-ACTIVE property.)
- **Kill/HALTED atomicity / H3** — every store method under review is a single lock hold with no
  internal await (await-point map, interleaving-attacker); no constructible window at approval,
  activation, or staging; kill hook mutation killed by the direct test (TC M2); triple race
  kill×approve×supersede ends HALTED with zero ACTIVE envelopes in every schedule. Known accepted
  boundary: kill landing between a successful claim and the adapter call (documented D-P2 scope).
- **Max-outstanding=1 / double-stage** — concurrent double staging yields ≤1 venue submit; loser
  fail-closes via structural divergence.
- **Overfill (ACTIVE) → BREACHED, never negative, never hidden** — concurrent 70+70 on remaining
  100 floors at 0 and breaches. (FROZEN-path variant is F8's SPEC-05.)
- **Budget across crash-restart (sqlite) / H7** — derived from durable ENVELOPE_ACTION events; no
  free replaces after crash; budget off-by-one mutation killed by the targeted chaos test (property
  strategy can't reach the edge — TC-06, in F2).
- **Redrive-vs-redrive single claim / INV-021** — the submission claim serializes; ≤1 venue call.
- **Freeze/resume storms** — fill-to-zero while FROZEN never auto-resumes; exactly one resume wins
  and chains COMPLETED once.
- **Floor + qty rails at both call sites (fresh staging)** — every below-floor/over-remaining stage
  attempt caught at the seam; D-3 divergence mutation killed across 9 tests both stores (TC M4).
  The double-check gap is TTL/phase/redrive (F3), not floor/qty on the fresh path.
- **H4 flatten preemption (status level) / INV-081** — envelope cancellation inside flatten's
  atomic unit, ordering asserted, both stores; flatten-preemption mutation killed (TC M3). Residual
  is the already-filed staged-order FINDING (WO-0024).
- **H6 bad-data fail-closed** — all six bad-data classes fail closed before any venue call on the
  fresh path (`_snapshot_invalid_reasons` covers None/stale/non-finite/≤0/negative-volume/crossed).
  Redrive bypass of these gates is F3.
- **DST/session math** — no constructible wrong `time_to_phase_close`; US DST transitions can't
  intersect trading windows; naive `now` rejected.
- **WO-0019a adapter claims** — SDK method names exist on pinned alpaca-py 0.43.5; wrong-name
  mutation killed 6 tests (X-002 defeated today; autospec hardening in F2/TC-08).
- **Dual-store parametrization is genuine** — per-store mutations fail only their own variant;
  both P1 repros were run against both stores rather than assuming parity.
- **EnvelopeTapeBuffer bounding** — capped, deduped; restart-emptiness risk routes through F3.
- **Session close vs ACTIVE envelopes** — matches ratified D-013a; flagged to Phase B as a review
  question, not a finding.
- **Additive event types without schema bump** — safe for projections that exist; the missing
  envelope projection is F8/CC-04, not a schema-version defect.

Mutation matrix summary (test-critic): 13 mutations, 10 killed, 3 survivors (= TC-01, TC-02,
TC-04) plus two partial survivors (TC-05 dead race branch, TC-06 unreachable property edge).

## 3. Remediation mapping (drafts only — nothing fixed, all human-gated where marked)

| Cluster | Vehicle | Status |
|---------|---------|--------|
| F3 (+ original staged-order FINDING) | **WO-0024 (AMENDED draft)** — scope widened: status guard alone is provably insufficient; redrive must re-run full write-time validation (rails + TTL + phase + data-validity re-check) before the claim. | DRAFT, human-gated, awaiting approval |
| F4 + F5 | **WO-0025** (paired by necessity — fixing F4 alone weaponizes F5) | DRAFT |
| F1 | **WO-0026** (reduce-only enforcement seam; human-gated: order submission surface) | DRAFT, human-gated |
| F6 | **WO-0027** (supersession: predecessor order cancel/adopt + remaining conservation) | DRAFT — may be deferred while no production caller exists, but blocks wiring the amendment flow |
| F2 + F7 | **WO-0028** (test-integrity repairs + memory `_atomic` envelope snapshot; includes the one-character `or True` deletion — recommended FIRST, before Phase B verdict relies on the suite) | DRAFT |
| F8 | **WO-0029** (grouped; planning seat should re-cut — includes two ADR-010 text amendments: §5 defect-classification and §2/§3 FROZEN-overfill edge) | DRAFT, ADR portions human-gated |

## 4. Gate implications

- **ADR-010 acceptance (T5) blockers:** F1, F3, F4, F5 (and WO-0024's original finding). F6 blocks
  only the amendment-flow wiring. F8's ADR text contradictions (SPEC-05, SPEC-09) must be resolved
  in the ADR itself before acceptance — the code and the ADR currently disagree on what BREACHED
  means and on what a divergence signifies.
- **Phase B (Codex) proceeds against the same pin `f092ca7`** — per protocol, Phase A results are
  NOT shared with the Codex seat before its verdict. TC-01 (`or True`) means Phase B should not
  treat "suite green" as evidence on the replace-targeting surface; Codex will presumably find it
  independently, which is itself a useful calibration signal.
- **Safety posture note:** every P0/P1 above is in code that is NOT yet driven by real capital
  (paper-only, envelope flow behind human approval, no production supersede caller); the wave's
  fail-closed bias held everywhere except F1/F5's venue legs and F3's redrive — which is exactly
  why those rank where they do.
