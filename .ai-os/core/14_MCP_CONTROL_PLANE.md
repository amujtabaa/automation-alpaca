# MCP Control Plane

## Purpose

The AI Project OS should remain a repo-installed, version-controlled operating layer. A custom MCP server should be an optional **control plane** that makes the OS easier to access, query, validate, and operate across Claude Code, Codex, and other MCP-capable agents.

The central rule:

> MCP is the OS access layer, not the OS source of truth.

The source of truth remains in repository artifacts:

```text
.ai-os/ or package docs
pkl/
work/
templates/
rules/
scripts/
CLAUDE.md
AGENTS.md
```

The MCP server reads and writes those artifacts in controlled ways. It should not hide project truth inside a private database.

## Why this layer exists

MCP is useful for the AI Project OS because it can expose targeted resources, reusable prompts, and bounded tools without forcing agents to load the entire OS into context. This matches the OS thesis: give each session the smallest useful context and enforce outcomes through artifacts, scripts, review, and evidence.

The official MCP documentation describes MCP as an open standard that connects AI applications to external systems, including data sources, tools, and workflows. That maps well to this OS because the repo contains data sources (PKL, work orders, ledgers), tools (harness scripts), and workflows (Fable, prompt templates, review, hygiene, disposition).

## Non-goal

Do not rewrite the entire AI Project OS as MCP-only.

MCP should not replace:

- version-controlled OS docs
- PKL pages
- ADRs
- work orders
- result records
- ledgers
- tests
- CI
- human review

MCP should make those artifacts easier to use.

## Recommended architecture

```text
Claude Code ─┐
Codex      ──┼── MCP client → ai-os-mcp server → repo filesystem
Other IDE  ─┘                                ├→ .ai-os / docs
                                             ├→ pkl/
                                             ├→ work/
                                             ├→ templates/
                                             ├→ rules/
                                             └→ scripts/
```

The AI OS MCP server should be local-first and repo-scoped.

Preferred first transport:

```text
stdio local server
```

Later packaging path:

```text
MCPB or equivalent bundled local package
```

## Derived views

```text
Repo artifacts are canonical.
MCP responses are derived views.
```

If the MCP server and repo files disagree, the repo files win.

## Role split

| Layer | Responsibility |
|---|---|
| Repo OS | durable source of truth |
| Adapter shims | tool-native entry points: `CLAUDE.md`, `AGENTS.md`, generic prompt |
| Skills | on-demand deep workflow guidance |
| MCP resources | targeted read access to OS/project artifacts |
| MCP prompts | reusable task framing exposed through the MCP interface |
| MCP tools | validation, routing, install planning, hygiene, disposition, context packet generation |
| Scripts/CI/hooks | deterministic enforcement |
| Human | final judgment, approval, deletion, merge |

## Minimal MCP surface

Keep the first MCP small. Too many tools create tool-selection bloat and can consume context.

Recommended MVP:

```text
Resources:
- ai-os://version
- ai-os://manifest
- ai-os://fable/core
- ai-os://prompt/{name}
- ai-os://pkl/index
- ai-os://work/active

Prompts:
- ai_os_create_work_order
- ai_os_implementation
- ai_os_debugger
- ai_os_reviewer
- ai_os_pkl_curator
- ai_os_handoff

Tools:
- ai_os_doctor
- ai_os_get_context_packet
- ai_os_validate_work_order
- ai_os_hygiene_report
- ai_os_disposition_review
```

No writes are required for the MVP.

## Development phases

### Phase 1 — Read-only MCP

Expose resources, prompts, and read-only tools.

Allowed:

- inspect OS version
- inspect manifest
- list active work orders
- generate context packets
- validate work order structure
- report hygiene issues

Not allowed:

- modify files
- delete files
- activate hooks
- change CI
- edit `CLAUDE.md` or `AGENTS.md`

### Phase 2 — Proposed writes

Generate proposed files or patches, but do not apply them automatically.

Examples:

- proposed work order
- proposed PKL update
- proposed disposition result
- proposed install plan
- proposed adapter-shim patch

### Phase 3 — Controlled writes

Allow bounded writes after explicit approval.

Examples:

- create work-order file
- update ledger entry
- create compact work-result file
- update PKL page
- install marker block in `CLAUDE.md` or `AGENTS.md`

Phase-3 writes are additive-only. Deletion is **permanently excluded from MCP**: it is executed only by a human or a repo script consuming a human-approved deletion list.

Still require human approval for:

- hooks
- CI workflows
- global config
- destructive changes
- broad refactors

### Phase 4 — Packaged distribution

Package the server for local installation, then optionally bundle it for easier setup.

## What MCP should do especially well

### 1. Context packet generation

The most valuable tool is `ai_os_get_context_packet`.

It should return:

```yaml
work_order: work/active/WO-0000.md
prompt_type: implementation
fable_mode: FULL
model_tier: medium
read:
  - CLAUDE.md or AGENTS.md adapter shim
  - templates/prompts/implementation.md
  - pkl/modules/<module>.md
  - relevant source/test paths only
allowed_paths:
  - apps/api/src/modules/example/**
forbidden_paths:
  - apps/api/src/modules/auth/**
verification_commands:
  - pytest tests/modules/example -q
stop_conditions:
  - required context missing
  - needed change outside allowed paths
  - architecture decision required
```

This helps cheaper models by giving them narrow, structured context.

### 2. Hygiene and anti-bloat

MCP can report:

- completed work orders still in active folders
- raw prompts marked for deletion but not deleted
- PKL pages over size budget
- adapter shims over size budget
- version mismatches
- unevaluated prompt templates
- stale result records

### 3. Disposition review

MCP can recommend a disposition from the vocabulary defined canonically in `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`). It should not delete without approval.

### 4. Install planning

MCP can inspect a repo and return an install plan:

- files that will be created
- files that will be modified
- marker blocks to insert/replace
- adapter skills to install
- hooks/CI proposed but not activated
- conflicts requiring human review

## What MCP should not do

Avoid broad tools such as:

```text
ai_os_improve_repo
ai_os_fix_everything
ai_os_make_production_ready
ai_os_review_all_files
ai_os_refactor_project
```

These recreate drift.

Avoid unrestricted shell execution through MCP. Claude Code and Codex already have their own command-running mechanisms. The MCP should operate OS artifacts, not become a second terminal.

## Tool-design rules

- Tools should be narrow and named by outcome.
- Tools should return structured data.
- Tools should avoid long prose unless producing a human report.
- Tools should distinguish read-only, proposed-write, and apply modes.
- Tools that write files must support dry run.
- Tools that delete must only propose deletion unless explicitly approved.
- Tools should never silently overwrite human-authored instruction files.
- Tools should log any mutation to `work/ledger.jsonl` or a dedicated MCP operations log.

## Tool mode policy

Every tool declares its mode:

```text
read_only
proposed_write
approved_write
```

MVP tools are `read_only`. Write modes stay disabled until explicitly approved (see phases above).

## Context discipline

Every resource/tool response should be as small as possible while still useful. Return paths and summaries by default; return full file contents only when requested and only for directly relevant files.

## Versioning

The MCP design layer follows the package version in `VERSION.md` and `AI_OS_MANIFEST.yaml`.

If the MCP server eventually becomes separately packaged, it may have its own runtime version, but the embedded OS-control-plane spec should still state which AI Project OS package version it targets.

## Review checklist

Before implementing or enabling an MCP server, review:

- Is repo OS still canonical?
- Are writes off by default?
- Are tool names few and clear?
- Are outputs structured?
- Does `ai_os_get_context_packet` avoid loading stale history?
- Does install flow preserve existing `CLAUDE.md` and `AGENTS.md`?
- Does the hygiene flow support deletion rather than archival bloat?
- Does the MCP surface help both Claude Code and Codex?
- Can the same workflow still run without MCP?

## Bottom line

The custom MCP is worth building if it remains small and local-first.

The ideal role:

```text
Repo OS = durable operating system
MCP    = access/control plane
Agent  = reasoning and coding runtime
Harness = deterministic enforcement
Human  = final authority
```
