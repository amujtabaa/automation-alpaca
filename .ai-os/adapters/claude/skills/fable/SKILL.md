---
name: fable
description: Engineering discipline protocol for AI Project OS work. Activate for any implementation, bug-fix, debugging, refactoring, review, or testing task, or when the operator says "fable".
---

# Fable (Claude Code adapter skill)

This skill is a thin wrapper; the protocol text is maintained in one canonical
place. Do not fork or restate it here.

1. Read `.ai-os/templates/fable-core-v3.md` (installed layout) or
   `templates/fable-core-v3.md` (package layout) and follow it exactly.
2. Emit the canonical YAML blocks (`fable_gate`, `evidence`, `fable_fix`,
   `fable_done`). If your runtime's Fable edition emits the prose dialect
   (`[GATE]`, `[FIX]`, `[DONE] ... STATUS: X`), that is an accepted
   equivalent — do not mix dialects within one task.
3. Activate before any code-changing work in this repository. Use LITE mode
   only for single-file, low-risk, reversible edits; when in doubt, FULL.
