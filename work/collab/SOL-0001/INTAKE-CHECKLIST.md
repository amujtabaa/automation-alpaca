# SOL-0001 intake + crosswise review protocol (prepared before deliverables landed)

Status: WAITING ON FILES — the Sol/Codex session edited `work/collab/SOL-0001/impl/` in its own
sandbox (test_sol_policy.py +501, sol_policy.py +933, sol_conformance_plugin.py +79,
MANIFEST.md); nothing has been pushed to any branch of this repository yet. Once committed, run
this protocol top to bottom. Reviewer: implementation seat (Claude), crosswise per the
SOL-KICKOFF packet; results feed the consolidation memo and the W4 bake-off harness spec.

## 0. Provenance + integrity

- [ ] MANIFEST.md read FIRST: which baseline SHA did Sol code against? (Kickoff pinned the
      decide() contract at the pre-remediation baseline; anything later is a bonus, anything
      earlier needs a note.)
- [ ] Deliverables map to the packet's D1–D4; anything missing is recorded, not assumed.
- [ ] No files outside `work/collab/SOL-0001/**` were touched by the drop (the screenshot says
      4 files, all inside — verify against `git show --stat`).

## 1. Contract conformance (mechanical gates, run before any judgement)

- [ ] `sol_policy.decide(envelope, snapshots, *, now, history)` — EXACT frozen signature; no
      extra required kwargs, no mutation of inputs, returns only `app.sellside.types` variants.
- [ ] Purity: no wall-clock (`datetime.now`/`time.time`/`utcnow()` calls at decision time), no
      RNG, no IO, no imports from app internals beyond the allowed contract surface
      (`app.sellside.types`, `app.models` read-only shapes). grep + read.
- [ ] Sol's own test suite runs green IN THIS CONTAINER (their +501 tests; pinned toolchain).
- [ ] The conformance plugin runs: our envelope-policy test surface against sol_policy's decide
      (whatever adapter shape they shipped — inspect before executing; it must not monkeypatch
      app/ modules persistently).

## 2. Rail conformance vs the REMEDIATED tip (the deconfliction core)

Sol coded against a baseline that PREDATES four contract-relevant changes. For each, check
whether sol_policy's behavior assumes the old world:

| Post-baseline change | What Sol might assume | Check |
|---|---|---|
| `validate_action` gained TTL + session-phase rails (WO-0024) | Sol calls validate_action expecting the old rail set, or reimplements it | Sol's plan-time D-3 half must use the SHARED validate_action, not a fork |
| Working-order predicate is live-derived (WO-0025); the old "any submit EVER → REPRICE" was a BUG | Sol may have faithfully reproduced the buggy monotone predicate from the baseline code — meaning every Sol second leg would false-diverge at OUR seam | Read their kind-selection; run a two-leg scenario through stage |
| Reduce-only position gate at the seam (WO-0026) | Sol sizes only off envelope.remaining | OK at plan time (the seam gates), but flag if Sol's tests assert venue submission for qty > position |
| Redrive staleness/validation (WO-0024) | n/a at policy level | note only |

- [ ] Hard rails: floor/qty/cooldown/budget produce NoAction/refusal (never a clamped action);
      soft bounds clamp+ClampNote. Same taxonomy as ours.
- [ ] Trail-floor invariant + ratchet monotonicity: run OUR regime tapes + the WO-0028
      ATR-expansion-collapse tape against sol_policy (the tape that killed our M6).
- [ ] Structural-hold: this is Sol's headline territory (the P2 finding). Verify their
      mechanism stays inside hard rails on the pullback tape and on the crash tape (no
      structural hold below floor, none that survives a stop breach).

## 3. Adversarial pass (Fable discipline applies to THEIR work too)

- [ ] Their tests: mutation-check at least (a) their ratchet/monotonicity, (b) their fade/hold
      trigger, (c) one rail. A suite that survives its own mechanism's deletion is decorative
      (the TC-01 lesson).
- [ ] Their evidence claims in MANIFEST vs what actually runs here (fresh pasted output only).
- [ ] "Attractive-but-unimplemented ideas" were explicitly removed by Sol's last pass — verify
      the memo matches the code (their stated goal; hold them to it).

## 4. Outputs

- [ ] `work/collab/SOL-0001/CROSSWISE-REVIEW.md` — findings table, held list, conformance-run
      evidence, deconfliction deltas.
- [ ] Consolidation recommendation: what merges into `app/sellside/` NOW (only
      contract-conformant, rail-safe, mutation-hardened pieces) vs what waits for the W4
      five-metric harness bake-off (mechanism-quality claims — exit efficiency etc. — are
      EMPIRICAL, not review, questions).
- [ ] W4 harness spec addendum: the exact scenario set both policies run (our tapes + Sol's
      tapes + the structural-hold pullback tape), five-metric scorer, no peeking.
- [ ] Ledger entry + SOL-0001 packet disposition.
