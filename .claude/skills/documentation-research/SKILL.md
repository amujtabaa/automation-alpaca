---
name: documentation-research
description: "Fetch up-to-date library documentation using Context7 API. Use when user needs current docs, API references, how to use a library, or mentions Context7."
---

# Documentation Research

This skill covers three capabilities:

1. **Documentation Fetching** - Get up-to-date docs for any library (Context7 API)
2. **Skills Registries** - Discover and install AI coding skills:
   - **Context7** (`ctx7` CLI) - Search, install, manage skills with full CLI
   - **skills.sh** - Simple one-command installs, leaderboard discovery

---

## Skills Registries

Two registries for discovering and installing AI coding skills. Both support Claude Code.

### Context7 (ctx7 CLI)

The Context7 Skills Registry is a centralized system for discovering and installing AI coding skills across assistants (Claude Code, Cursor, Codex, etc.).

> **Note:** Uses the `ctx7` npm CLI directly. No Python scripts needed.

#### Quick Access

```bash
# Run without installing
npx ctx7

# Or install globally
npm install -g ctx7
```

#### Core Commands

| Command                                 | Shortcut  | Purpose                         |
| --------------------------------------- | --------- | ------------------------------- |
| `ctx7 skills search [query]`            | `ctx7 ss` | Search registry for skills      |
| `ctx7 skills install [project] [skill]` | `ctx7 si` | Install a skill                 |
| `ctx7 skills info [project]`            | -         | View project's available skills |
| `ctx7 skills list --claude`             | -         | List installed skills           |
| `ctx7 skills remove [skill]`            | -         | Uninstall a skill               |

#### Installation Examples

```bash
# Install single skill to current project
ctx7 skills install /anthropics/skills pdf

# Install multiple skills
ctx7 skills install /anthropics/skills pdf commit

# Install globally (available in all projects)
ctx7 skills install /anthropics/skills pdf --global

# Target specific assistant
ctx7 skills install /anthropics/skills pdf --claude
```

#### Supported Assistants

Skills auto-install to the correct directory:

- Claude Code: `.claude/skills/`
- Cursor: `.cursor/skills/`
- Codex: `.codex/skills/`
- OpenCode: `.opencode/skills/`

#### Best Practices

1. **Search before installing** - Browse what's available: `ctx7 skills search react`
2. **Check project skills** - View all skills in a project: `ctx7 skills info /vercel/skills`
3. **Use global for personal tools** - Install frequently-used skills globally
4. **Use local for project-specific** - Keep project skills in the repo for team sharing

### skills.sh

An open ecosystem for AI agent skills with leaderboard-based discovery. Simpler than Context7 - just one command.

**Website:** https://skills.sh

#### Install

```bash
# Install any skill by owner/repo
npx skills add <owner/repo>

# Examples
npx skills add vercel-labs/agent-skills
npx skills add anthropics/claude-code-skills
```

#### Discovery

Browse skills at https://skills.sh:

- **All Time** - Most installed skills overall
- **Trending (24h)** - Recently popular skills

#### Popular Skills

| Skill                       | Installs | Description                    |
| --------------------------- | -------- | ------------------------------ |
| vercel-react-best-practices | 34.5K    | React patterns and conventions |
| web-design-guidelines       | 26.2K    | Design system principles       |
| remotion-best-practices     | 14.8K    | Video generation with Remotion |
| frontend-design             | 5.2K     | Frontend architecture patterns |

#### Supported Assistants

- Claude Code
- Cursor
- Cline
- GitHub Copilot
- Gemini
- And others

#### When to Use Which Registry

| Need                            | Use                                  |
| ------------------------------- | ------------------------------------ |
| Search/browse skills by keyword | Context7 (`ctx7 skills search`)      |
| See what's popular/trending     | skills.sh leaderboard                |
| Install from known repo         | Either works                         |
| Manage installed skills         | Context7 (`ctx7 skills list/remove`) |
| Quick one-off install           | skills.sh (`npx skills add`)         |

### Skills vs Documentation

| User Need                            | Use                                 |
| ------------------------------------ | ----------------------------------- |
| "How do I add a skill for X?"        | Skills Registries                   |
| "What are best practices for React?" | Skills Registries (install a skill) |
| "How does routing work in Next.js?"  | Documentation Fetching              |
| "What's the API for Supabase auth?"  | Documentation Fetching              |

---

## Documentation Fetching (Python Scripts)

Uses `context7-scripts/` Python scripts to call the Context7 MCP API for library documentation.

**IMPORTANT: ALWAYS execute through a sub-agent to preserve context window. NEVER run Context7 scripts directly in the main conversation.**

### Sub-Agent Execution (REQUIRED)

Spawn a sub-agent to fetch and condense docs:

```
Task tool:
  subagent_type: general-purpose
  model: haiku

Prompt:
---
You are a documentation research agent. Fetch docs and return ONLY relevant, condensed info.

**Query**: [USER'S QUESTION]

**Steps**:
1. Read ".claude/skills/documentation-research/SKILL.md" for scripts and error prevention
2. Execute resolve_library.py for "[library]"
3. Execute get_docs.py with --topic "[topic]" --tokens 3000

**Return**: Key steps, essential code, critical notes.
Do NOT return raw docs. Synthesize for the query.
---
```

### Scripts (context7-scripts/)

These Python scripts call the Context7 MCP API. Run with `uv run` for automatic dependency management.

#### 1. Resolve Library ID

```bash
uv run context7-scripts/resolve_library.py "library name"
```

#### 2. Fetch Documentation

```bash
uv run context7-scripts/get_docs.py "/org/library"
uv run context7-scripts/get_docs.py "/org/library" --topic "feature"
uv run context7-scripts/get_docs.py "/org/library" --tokens 10000
```

### Common Library IDs

| Library  | ID                 |
| -------- | ------------------ |
| Next.js  | /vercel/next.js    |
| React    | /facebook/react    |
| Supabase | /supabase/supabase |
| Prisma   | /prisma/prisma     |
| Polar    | /polarsource/polar |

### Error Prevention

**Windows paths**: Always use forward slashes, even on Windows:

```bash
# Correct
uv run "C:/Github/project/.claude/skills/documentation-research/context7-scripts/get_docs.py" "/org/lib"

# Wrong - backslashes fail in bash
uv run "C:\Github\project\..." "/org/lib"
```

**Git Bash path conversion**: The scripts auto-fix Git Bash converting `/org/lib` to `C:/Program Files/Git/org/lib`.
