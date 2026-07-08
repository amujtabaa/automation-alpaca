---
name: fable
description: Engineering discipline protocol (Claude adapter for Fable v3). Use for ANY implementation, bug fix, debugging, refactoring, code review, testing, or TDD task — anything that writes or changes code. Also activates on "fable" or "fable mode". Enforces test-first development, root-cause debugging, scope discipline, and evidence-based completion claims per the canonical model-agnostic protocol in .ai-os/templates/fable-core-v3.md.
---

# Fable — Claude Adapter (v3)

**Canonical protocol:** `.ai-os/templates/fable-core-v3.md` (Fable v3, model-agnostic). This skill maps it onto Claude Code and adds this repo's wiring; it intentionally supersedes the OS package's thin wrapper skill (`.ai-os/adapters/claude/skills/fable/`). On any divergence in protocol substance, the canonical v3 file wins. Do not fork the protocol text here.

**Activate:** any code-changing task, or "fable" / "fable mode". **Deactivate:** "fable off".

## The Five Iron Laws (unchanged from v1; always in force)

1. No production code before a failing test, watched to fail for the right reason. Exceptions need explicit human sign-off.
2. No completion claim without fresh evidence pasted in the same reply. Statuses: VERIFIED | UNVERIFIED | BLOCKED | NEEDS-INPUT — nothing else.
3. No fix without a diagnosed root cause; "to see if it helps" is a labeled experiment, not a fix.
4. Touch only what the task requires; out-of-scope problems get logged, not fixed.
5. Surface assumptions before building; unsure whether to ask or assume → ask.

**Visible-deviation rule:** can't/won't follow a rule → `[FABLE DEVIATION] skipping X because Y`. Silent deviation is the only unforgivable failure.

## Required blocks — use the v3 YAML forms

Emit the structured blocks from v3, not v1 prose forms, so all seats (Claude, Codex, reviewers, harness scripts) parse the same shapes:

- Task header: `[FABLE • FULL|LITE • verification: DIRECT|DELEGATED • task: <n>]`
- `fable_gate:` before building (FULL tasks) — goal, assumptions (each VERIFIED|UNVERIFIED with evidence), approach + alternatives, out_of_scope, done_when (behavior/test/command triples), blast_radius, rollback. Irreversible actions wait for approval.
- `evidence:` for every verification — phase (RED|GREEN|REFACTOR|FULL_SUITE|MANUAL_QA), command, result PASS|FAIL|NOT_RUN, decisive_output pasted.
- `fable_fix:` for every bug — symptom, root_cause, evidence, fix, regression_test, red_green_verified, attempt #. **Circuit breaker at attempt 3:** stop, state what failed, return to the gate, discuss redesign with the human.
- DONE block closing every task: each done_when → met/not, evidence, scope check, status.

## Claude Code integration (this repo)

- **Work orders are the unit of work.** The `fable_gate` restates the work order's goal/done_when; `allowed_paths`/`forbidden_paths` in the order are hard scope for Law 4. No work order → request or draft one; don't freelance.
- **Delegation:** sub-agents dispatched via `/build` or Task calls inherit Fable. A sub-agent's report is an unverified claim until the dispatching context inspects diff + output (Law 2 applies across agents). Verification mode is DELEGATED when the human must run commands.
- **ClaudeFast interplay:** skill-activation suggestions never override the gate; `/team-plan` output feeds the gate, not replaces it; quality-engineer validation is in-process adversarial checking; it supplements pasted evidence and never counts as the independent cross-model review, which runs at the human's discretion per the CLAUDE.md Review policy.
- **Repo safety core:** the invariants and human-gated surfaces in `CLAUDE.md` bind inside every Fable task. Gated surfaces are never LITE.
- **On close:** assign work-order disposition (PKL_UPDATED | ADR_CREATED | RESULT_SUMMARY_KEPT | ARCHIVED | DELETED | SUPERSEDED | ABANDONED) and distill durable knowledge into PKL/ADRs per `.ai-os/` §12.

## Triage

LITE only when: fits one short prompt, ≤2 files, no interface/schema change, cheap to revert, touches nothing sensitive (auth, parsing, secrets, network, subprocess, payments, PII, **or any trading surface**). Behavior changes still get a test in LITE. When in doubt, or on any surprise: FULL, at the gate.

## Human commands honored

`fable status` · `fable audit` (re-check own last response against Laws/blocks, report violations honestly) · `fable gate` · `fable full` / `fable lite` · `fable off`.
