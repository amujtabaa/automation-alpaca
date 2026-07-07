# Spine v2 Prompts

This directory contains bounded handoff prompts for Claude Code, Codex, and independent review seats.

Use these prompts in fresh sessions. Do not paste all prompts into one session. Each phase should have one working context and should stop at its review gate.

Recommended order:

1. `CLAUDE_CODE_PHASE_0_HANDOFF.md` — inventory, harness, characterization, no behavior changes.
2. `CODEX_PHASE_0_HANDOFF.md` — independent review of Phase 0 output.
3. `CLAUDE_CODE_PHASE_1_FACADE_SEAM.md` — facade seam only, no execution-behavior migration.
4. `INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` — review before accepting any major architectural migration.

Historical `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_*.md` files are non-binding unless explicitly reactivated by a new ADR.
