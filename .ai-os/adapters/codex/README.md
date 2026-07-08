# Codex Adapter

Use root `AGENTS.md` for minimal repo rules. Put longer workflows into focused skills.

Recommended Codex mapping:

```text
AGENTS.md                  -> minimal operating rules
.agents/skills/fable       -> Fable discipline skill (source: adapters/codex/skills/fable)
hooks                      -> deterministic checks where available (proposed-only; see .ai-os/proposed-hooks/)
```

Codex-specific note: Codex loads global and project instruction files, then nested instructions down to the working directory. Closer instructions override broader ones because they appear later in the combined prompt. Use this for module-specific guidance.
