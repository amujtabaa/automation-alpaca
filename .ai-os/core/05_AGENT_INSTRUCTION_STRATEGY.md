# Agent Instruction Strategy

## Root rule

Keep always-on instructions small enough to be remembered and obeyed.

## Root AGENTS.md should contain only

```text
- project purpose in 3-5 lines
- setup commands
- test/lint/typecheck commands
- architecture defaults
- sensitive-surface warnings
- how to find work orders and PKL pages
- Fable activation rule
- completion evidence rule
```

## Root AGENTS.md should not contain

```text
- full Fable protocol
- full architecture guide
- every template
- logs
- long research summaries
- historical conversation context
- speculative best practices
```

## Nested instructions

Use nested AGENTS.md files for module-specific rules:

```text
apps/api/modules/payments/AGENTS.md
apps/api/modules/auth/AGENTS.md
apps/web/AGENTS.md
```

Nested files should override or refine the root, not repeat it.

## Probe-and-refine loop

For each major repo or module:

1. Create 3-5 synthetic bug-fix tasks.
2. Run a coding agent with the current AGENTS.md and work-order template.
3. Record where it wastes time, touches wrong files, or misunderstands architecture.
4. Add only minimal guidance that would have prevented the error.
5. Re-run the probes.
6. Keep guidance only if it improves behavior.

## Instruction budget

Target sizes:

```text
Root AGENTS.md: within root_instruction_max_lines from rules/ai-os-rules.yaml (single source; currently 150)
Nested AGENTS.md: 20-80 lines
Fable compact: 80-160 lines
Work order: 1-3 pages
PKL context packet: usually 3-7 pages, not the whole PKL
```


## Neutral-core rule

The OS core is canonical. Tool-specific instruction files are adapters.

```text
.ai-os/   = source of truth for the operating system
CLAUDE.md = Claude Code adapter shim
AGENTS.md = Codex/generic adapter shim
```

Do not treat either `CLAUDE.md` or `AGENTS.md` as the whole OS. Keep both short and route agents to the current work order, linked PKL pages, and relevant Fable skill/template.

## Adapter parity

Claude Code and Codex should receive the same operating rules in different native formats. If a rule changes, update the neutral OS core first, then regenerate or patch both adapter shims.


## MCP adapter neutrality

If an MCP server is used, it is a shared access/control layer for Claude Code, Codex, and other MCP-capable clients. It must not become a Claude-only or Codex-only integration.

The adapter hierarchy remains:

```text
.ai-os/ and repo artifacts = canonical
MCP server = optional access/control plane
CLAUDE.md = Claude adapter shim
AGENTS.md = Codex/generic adapter shim
```

Adapter shims may mention the MCP server only as an optional helper, not as a prerequisite.
