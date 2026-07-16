# SOL-0001 — CROSSWISE REVIEW (Claude seat reviewing the Sol/Codex drop)

**Run provenance:** ultracode workflow `wf_568baeb1-f56` — 52 agents, 0 errors, 1.75M subagent
tokens, 381 tool calls. Mid-run right-sized per doc 17 v1.1 (R7–R11): conformance+drift ran
pre-tiering and replayed from cache; adversarial (sonnet ×2 + opus ×1), tiered verification
(P0/P1 = two independent refuters, survive only if NEITHER refutes; P2/P3 = one), synthesis
(opus/high). Raw per-agent returns: `crosswise-raw-result.json` (this dir) + the workflow
journal. Counts: 36 raw findings → 34 verification-confirmed → ~7 deduplicated clusters (several
lenses independently converged on the same defects — treated as corroboration, not volume).

**Companion documents:** `incumbent-findings-triage.md` (the reciprocal direction — Sol's
findings against OUR code, triaged and pinned) · `INTAKE-CHECKLIST.md` (the review contract).

**Bottom line:** contract, purity, and shared-rail conformance are EXCELLENT — and the drop is
**DO-NOT-MERGE / DO-NOT-ENTER-W4 as shipped**: one history-fold defect livelocks every
post-fill exit on production-shaped event logs, and the headline fade/hold mechanism is
decoratively tested. Both fixable; the remediation list for Sol's operator is §4 of the
synthesis below. The review also caught one regression in OUR OWN WO-0029A work (DRIFT-SVD-2,
filed separately — the crosswise lane cutting both ways again).

---

Tree clean at end (`git status --porcelain` empty). All load-bearing facts re-verified fresh in this container. Synthesis follows.

---

# SOL-0001 Crosswise Review — Synthesis

**Reviewer:** implementation seat (Claude), crosswise per SOL-KICKOFF.
**Drop under review:** `work/collab/SOL-0001/impl/` — `sol_policy.py` `sha256=b32b8ccd98e7b7a8378b6580eb8d5f3c9a193f412f5f3388e3ea169471ad1e5a`, `test_sol_policy.py` `sha256=6bdfa700746d…`, `sol_conformance_plugin.py` `sha256=1e7b1adb6a81…`.
**Toolchain (this container, pasted):** Python **3.11.15** (repo pins 3.12), ruff 0.15.20, mypy 2.2.0 (compiled: yes), pytest 9.1.1.
**Frozen base:** `5a194104ee5d542e0b838929dacee7008c6d3336` — real, ancestor of HEAD, verified.
**Reviewer hygiene:** nothing under `app/`, `tests/`, or `work/collab/SOL-0001/impl/` modified; tree clean at start and end.

> **Overall gate: DO-NOT-MERGE-AS-SHIPPED, DO-NOT-ENTER-W4-AS-SHIPPED.** Contract/purity are clean, but a single history-fold defect (`_child_state`'s `envelope_id` filter + non-registration of reprice-minted orders) **livelocks every post-fill protective exit and every tranche second-leg on production-shaped event logs**, and Sol's fade/hold mechanism — its headline claim — is **decoratively tested** (mutation survivor). Both are consolidation-blocking. W4 tape metrics on the as-shipped policy would measure the livelock, not the mechanism.

---

## 1. Verdict per INTAKE-CHECKLIST section

### §0 Provenance + integrity — **PARTIAL / FLAGGED**
- Baseline SHA: **VERIFIED** `5a19410` ("W3: SOL-KICKOFF collaboration packet"), pre-remediation baseline exactly as kickoff pinned; 41 commits behind tip. WO-0024/25/26/27/28/29A all post-date it.
- D1–D4 mapping: **INCOMPLETE.** Shipped: D2 (`sol_policy.py`+tests+plugin), D4 (`findings.md`). **Absent: D1 (`design-memo.md`), D3 (`tapes.md`)** — verified absent at packet root just now. MANIFEST itself flags them "pending packet finalization."
- Scope: **CLEAN.** Import commit touched only `work/collab/SOL-0001/**`.
- **Integrity failure:** MANIFEST `Final impl/sol_policy.py SHA-256:` is the literal placeholder **`<FINAL_SHA256>`** (re-verified line 6). By its own contract ("finalizer must verify companions present before committing") the packet was **committed unfinalized**. Independently pinned hash recorded above.
- **Note (stale-finding correction for orchestrator):** several review lenses reported "MANIFEST.md absent, only 3 files." That is now false — MANIFEST.md (8601 B) is present at packet root. The *placeholder* and *missing companions* findings stand; the *"MANIFEST missing"* findings (F1/SUITE-F1) are **superseded**.

### §1 Contract conformance (mechanical) — **PASS**
- Signature `decide(envelope, snapshots, *, now, history)` **EXACT** (sol_policy.py:701) — param shape identical to incumbent via `inspect.signature`; `now`/`history` keyword-only, no extra required kwargs. Return annotation is the 6-variant `app.sellside.types` union (additive vs unannotated incumbent).
- Purity **HELD** three ways: grep (zero wall-clock/RNG/IO hits), `sys.addaudithook` across 8 `decide()` calls (0 audit events), ZoneInfo tzdata read is import-time only. No input mutation (deepcopy-equality), no hidden mutable module state, determinism A/B/A.
- Import surface **CONFORMANT** — stdlib + `app.models`/`app.marketdata.service` shapes + `app.sellside.types` + `app.sellside.policy.validate_action`.
- Sol suite **GREEN in this container**: `33 passed`, re-run just now (33 dots). ruff check `All checks passed!`.
- Plugin runs; **does not persistently monkeypatch `app/`** (in-process rebind only, tree clean after). Meets §1 wording. Blast-radius caveat → §F below.

### §2 Rail conformance vs remediated tip — **MIXED: rails PASS, working-order predicate FAILS**
| Post-baseline change | Verdict |
|---|---|
| WO-0024 TTL+session rails | **PASS.** Sol uses the **shared** `validate_action` (not a fork) — proven load-bearing: runtime identity `sol.validate_action is shared.validate_action == True`; both new rails fire through Sol's imported name; RailViolation→BreachSignal generically, no rail-name switch, so unknown-to-baseline rails pass through. Sol's cooldown/budget pre-check sets match incumbent set-for-set. |
| WO-0025 live-derived working predicate | **FAIL — see F1 cluster below.** Sol did *not* copy the buggy monotone predicate, but its replacement fold is broken a different way on production-shaped logs. |
| WO-0026 reduce-only seam gate | **PASS at plan time.** Sol sizes off `envelope.remaining` (exact parity, sol_policy.py:736 == incumbent:253); fuzz 108 states → 0 qty>remaining; shared validator re-clamps last. No test asserts submission for qty>position. |
| WO-0024 redrive | n/a at policy level. |
- Hard-rail taxonomy **MATCHES**: below-floor→`BreachSignal(rail=floor_price)`; participation→clamp+ClampNote or `NoAction(NO_LIQUIDITY)` at zero capacity; budget→`ExhaustedSignal`. Sol contains zero internal floor logic yet emits `BreachSignal floor_price` — proof it originates in the shared rail.
- Trail-floor + ratchet monotonicity **HELD** across our crash tape, WO-0028 ATR-expansion-collapse tape, and thin/gappy tapes: 0 violations, planned qty ∈ (0, remaining], limit ≥ floor.
- Structural-hold **P0 CLEARED**: on a true breakdown Sol trips `stop_triggered` at the same tick as incumbent and returns `Breach(floor_price)` below the hard floor. The monitoring/hold return is structurally unreachable once `last_price ≤ ws.stop`. **Sol cannot hold below the floor.** No missed stop.

### §3 Adversarial pass — **FAIL (fade/hold coverage decorative)**
- Mutation (a) ratchet/monotonicity: **KILLED** by 2 tests (`stop = candidate` → `test_working_stop_is_monotone_*` + prefix-monotone). Real coverage.
- Mutation (c) rails: **KILLED** — zero-liquidity guard `if False:` → 2 fail; shared-validator deletion → 2 fail (incl. dedicated `test_shared_validator_is_mandatory_not_decorative`); `_spread_stressed=False` → 1 fail; `_tranche_filled` gutted → 1 fail. Rails not decorative.
- Mutation (b) fade/hold trigger: **SURVIVES — DECORATIVE.** Re-verified trigger at sol_policy.py:567–570. Neutering `tightening=False` (flips STALL_FADE from tightest trail `lo` to loosest `hi`) → **0 failures across all 33 Sol tests AND all 35 rival-facing conformance nodes.** Provably non-equivalent (mutant flips reported regime `stall_fade→uncertain` on Sol's own crash_tape; stop coincides only because the redundant `last_move` disjunct still forces tightening). Per TC-01, **the five-regime fade leg has zero effective coverage.**
- MANIFEST evidence vs actual: **counts reproduce** (33 / 35 / 52 green; mypy clean; ruff check clean). **One claim FALSE:** "3 files already formatted" — re-verified just now: `ruff format --check` → *"Would reformat sol_policy.py … 1 file would be reformatted, 2 files already formatted"* (cosmetic line-join at the `tightening` expression). Likely Sol's Windows `.venv-review` ruff drift.
- "Attractive-but-unimplemented ideas removed, memo matches code": **UNVERIFIABLE/BLOCKED** — no `design-memo.md`; `findings.md` has no removed/unimplemented inventory (grep removed|unimplemented|dropped: no matches).

### §4 Outputs — this document + ledger disposition below.

---

## 2. Consolidation split

### MERGE-NOW candidates (contract-conformant, rail-safe, mutation-hardened) — **NONE ship independently**
The rail-safe, well-tested pieces (shared-validator threading; ratchet/monotonicity via `compute_working_stop`; zero-liquidity guard; hard-rail taxonomy) are **correct and mutation-hardened**, but they are **not separable** from the same file's broken `_child_state` fold and decorative fade leg. There is **no clean sub-unit to lift into `app/sellside/` today.**
- **Conditional merge-now (only after F1+F2 fixed together):** the ratchet/trail-floor machinery and the shared-validator wiring. These are the parts with real coverage and parity.

### W4-BAKE-OFF items (mechanism-quality = empirical, not review)
- **Fade/hold (STALL_FADE tightening)** — headline claim; currently decorative in test, so its quality is *entirely* unmeasured. Route to W4 tapes **and** require added tests before any credit.
- **Structural-hold on contracting-volume pullback** — empirical datum: under the plugin, our strict-xfail `test_trend_pullback_resume_takes_one_tranche_and_survives` **still xfails** → Sol does **not** beat incumbent's structural hold on that tape. On every low-vol pull-to-VWAP construction the pull flips regime to `stall_fade`, tightens to `lo`, and Sol (tighter stop) exits **at least as early** as incumbent. **Headline hold advantage did not manifest on tape.** W4 must confirm or bury it.
- **Protective-exit-vs-participation divergence (SOL-RO-2)** — on a zero-volume stop breach Sol returns `NoAction(NO_LIQUIDITY)` and holds the **entire** position; incumbent 1-share-probes ("protection beats participation politeness"). Sol silently inverts an explicit incumbent safety comment. **Adjudicate before merge**; route the exit-efficiency question to the five-metric bake-off, but the safety-comment inversion is a human-gated call.

### APP-SIDE items surfaced (not charged to Sol; route to WO-0031/consolidation)
- **DRIFT-SVD-2:** WO-0029A `refused_stale` payload keeps `tranche:true`; incumbent tranche accounting latches on any `ENVELOPE_ACTION` payload tranche → a benignly-refused tranche (no order minted) permanently consumes the single tranche entitlement. Contradicts the amendment's "envelope UNTOUCHED, replan works immediately." Candidate one-line fix.

---

## 3. W4 harness spec addendum

**Precondition:** do **not** run W4 on `sol_policy.py` as shipped — fix the F1 cluster first (else every post-fill leg livelocks and metrics measure the stall). Sol's fixture shape must **not** be used to build tapes (it masks F1).

**Shared scenario set (both policies, identical inputs):**
1. Our WO-0018/WO-0021 regime tapes (incl. the strict-xfail trend-pullback-resume tape).
2. WO-0028 ATR-expansion-collapse tape (the one that killed M6).
3. WO-0020 crash_tape (true-breakdown stop-exit).
4. **Structural-hold pullback tape** — low-vol orderly pull-to-VWAP, contracting volume, no true breakdown; the tape where a genuine fade/hold mechanism should beat a naive trail. (This is D3 territory — **Sol must deliver `tapes.md`; it does not exist yet.**)
5. Thin/gappy/air-pocket tape — irregular 15–90 s gaps, near-zero-volume ticks, gap-down print — to stress participation-cap + staleness gating and the SOL-RO-2 protective divergence.
6. **Production-shaped history variants** of 3–5: terminal FILLED/CANCELED/REJECTED and FILL events carrying `order_id` with **`envelope_id=None`** (the real store shape, `app/store/core.py:1810-1819`, `:212-224`), plus `refused_stale` / `divergence` events. This is the shape that exposes F1/DRIFT-SVD-1/DRIFT-SVD-3 and that Sol's suite never emits.

**Five-metric scorer:** exit efficiency (realized vs theoretical-optimal exit), capture of held value (prize retention on the pullback tape), max adverse excursion post-stop, protective-exit latency (ticks from breach to staged reduce), rail-violation count (must be 0 — any >0 disqualifies the run, not scores it).

**No-peeking:**
- Run each policy in a **separate, unpatched pytest process.** Never cite the 52-node hybrid as incumbent evidence — its 17 "incumbent" nodes execute inside the rival-patched process (`sol_conformance_plugin.py:47-49` rebinds `app.sellside.policy.decide` session-wide, no restore; `validate_action` is *not* patched, so those nodes are genuine, but the decide surface is polluted).
- Feed **both** policies the production-shaped histories (§6); never the `envelope_id=env.id` fixture shape.
- Decision purity is guaranteed (injected `now`, no RNG/IO) so tape replays are deterministic and reproducible — pin the tape SHAs in the harness spec.

---

## 4. Drift-remediation list for Sol's operator

Diff `5a19410..HEAD` (b772709/tip) before touching anything; Sol coded 41 commits behind. Priority order:

1. **[P1 — BLOCKING] Fix `_child_state` history fold (F1 + F2 together — a partial fix exposes the other).**
   - `_own_history` filters `event.envelope_id == envelope.id` (sol_policy.py:254). Production terminal + FILL events carry `envelope_id=None` and route by `order_id` (`app/monitoring.py:670-673` widens `decide()`'s history by `order_id` membership for exactly this reason). Result: the fold **never sees a terminal**, `child.working` latches True on first submit forever → every later plan becomes REPRICE → seam refuses `STAGE_REFUSED_STALE` → **permanent per-tick livelock; tranche second legs never planned** (blocked at :827). Fix: fold terminals/FILLs matched by `order_id` from the **UNFILTERED** history, as `app/sellside/policy.py:135-158` does.
   - The `reprice` branch (sol_policy.py:294) never registers the reprice-minted order's own `order_id` (only sets `anonymous_working` when `working_ids` is empty). After submit(A)→reprice(B)→CANCELED(A) the fold reports `working=False` while B is live → plans SUBMIT over a live order → seam refuses `structural`. Fix: follow the newest chain and register B's `order_id` (incumbent returns `ord-B` at :147-158).
   - Add tests using the **production event shape** (`envelope_id=None`, `order_id` set) — mirror `tests/test_wo0025_multileg.py:108-117`, which the MANIFEST conformance selection currently *excludes*.

2. **[P1 — BLOCKING] Give the fade/hold mechanism real coverage.** Add a test that pins STALL_FADE→tightest-trail (`lo`) behavior such that `tightening=False` fails. Today the fade leg is decorative (mutation survivor); its W4 quality claims cannot be credited until a killing test exists and the classifier's fade output (observable `regime` field) is asserted independently of the redundant `last_move` disjunct.

3. **[P2] WO-0029A vocabulary integration.** Zero coverage of `refused_stale`/`divergence` anywhere in the drop (grep clean; the `action_event` helper can't express a refusal). Consequences at tip:
   - **DRIFT-SVD-3:** `_tranche_filled` records a `refused_stale` (`order_id=None`, `tranche:true`) as an anonymous tranche; a later deduped positive fill of a *different* order then falsely consumes the tranche entitlement — breaks Sol's own MANIFEST design claim. Fix the anonymous-latch fold to require a real order_id.
   - Add refusal-vocabulary tests.

4. **[P2] ADJUDICATED (Ameen, 2026-07-12): incumbent behavior but REPORTED** — 1-share probe stays, carries a participation ClampNote, and dynamically sizes up on venue minimum-size rejections (see incumbent-findings-triage.md WO-0031(c) for the full spec). Sol's hold-all is rejected for consolidation; the exit-efficiency comparison still runs in W4. Original item text follows for the record: holding the entire position on a zero-volume crash vs the incumbent's 1-share protective probe silently inverts an explicit safety comment. This is a gated-surface decision, not an operator choice.

5. **[P2] Finalize the packet.** Fill the `<FINAL_SHA256>` placeholder (`b32b8ccd98e7b7a8378b6580eb8d5f3c9a193f412f5f3388e3ea169471ad1e5a`). Deliver the missing **D1 `design-memo.md`** (with the removed/unimplemented-ideas inventory the §3 check requires) and **D3 `tapes.md`** (required for the W4 harness).

6. **[P3] Housekeeping.**
   - Re-run `ruff format` on the pinned 0.15.20 — one cosmetic line-join at :567-570; MANIFEST's "3 files already formatted" is false here.
   - `_phase_and_close` duplicates the ET session windows (4:00/9:30/16:00/20:00) instead of using shared `app.sellside.session.session_context` — a **third** uncovered copy, not pinned by `tests/test_wo0018_sellside_session.py`. Risk bounded (shared rail backstops), but consolidate onto the shared window.
   - `EXPIRED`/`REPLACED` in Sol's child-terminal set are declared-only vocabulary at tip (zero producers). Dormant, but a future `EXPIRED` producer + seam-live row → SUBMIT into a refused-stale loop. Note only.
   - Auxiliary helpers (`aggregate`, `compute_working_stop`) are TZ-env-dependent on **naive** `updated_at` (bar bucketing `obs.at.timestamp()`, :384). Unreachable through `decide()` (naive `now`→OUT_OF_PHASE; naive snapshots dropped by phase filter) — footgun only if the W4 harness drives helpers directly with naive fixtures.
   - Certify on **Python 3.12** before merge — this green run is 3.11.15 semantics.

**Ledger disposition:** SOL-0001 packet **NOT FINALIZED** (self-declared; placeholder hash, missing D1/D3). Contract + purity + shared-rail conformance **ACCEPT**. Working-order fold + fade coverage **REJECT-PENDING-FIX**. No merge, no W4 entry, until items 1–2 land and items 3/5 close.