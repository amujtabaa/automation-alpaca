# Claude Adapter

Use Claude-specific files only as adapters, not as the conceptual center of the system.

Recommended Claude mapping:

```text
CLAUDE.md                  -> short shim equivalent to root AGENTS.md
.claude/skills/fable       -> Fable implementation skill
.claude/skills/fable-review-> review skill if supported
hooks                      -> deterministic checks where available
```

The protocol language should remain model-agnostic: agent, runtime, instruction file, capability bundle, work order, harness.

Dialect note: the Fable skill edition running in Claude Code emits the prose block dialect (`[GATE]`, `[FIX]`, `[DONE] ... STATUS: X`). Checkers accept it as an equivalent of the canonical YAML blocks defined in `06_FABLE_V3_EXECUTION_PROTOCOL.md`.
