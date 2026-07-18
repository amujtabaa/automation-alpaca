# ClaudeFast Hooks Guide

This guide documents all hooks included in the ClaudeFast framework.

## Overview

ClaudeFast includes hooks across two categories: **automation hooks** that run during normal development, and **validator hooks** used by slash commands to enforce output quality.

### Automation Hooks

| Hook                    | Type                    | Purpose                                               |
| ----------------------- | ----------------------- | ----------------------------------------------------- |
| **SkillActivationHook** | UserPromptSubmit        | Recommends skills based on prompt content             |
| **ContextRecoveryHook** | StatusLine + PreCompact | Threshold-based backups + pre-compaction backup       |
| **FormatterHook**       | PostToolUse             | Auto-formats files with Prettier after Write/Edit     |
| **LibraryHook**         | Stop                    | Auto-syncs library-managed file edits back to library |
| **PermissionHook**      | PermissionRequest       | Auto-approves safe operations (external npm package)  |

### Validator Hooks

| Hook                     | Type        | Purpose                                                           |
| ------------------------ | ----------- | ----------------------------------------------------------------- |
| **BiomeValidator**       | PostToolUse | Runs Biome lint/format on JS/TS/JSX/TSX/JSON/CSS after Write/Edit |
| **ValidateNewFile**      | Stop        | Enforces that a new file was created in a target directory        |
| **ValidateFileContains** | Stop        | Enforces that a file contains required sections/strings           |

---

## Folder Structure

```
.claude/hooks/
├── .gitignore                    # Ignores logs and state files
├── cf-hooks-guide.md             # This file
├── SkillActivationHook/
│   └── skill-activation-prompt.mjs
├── ContextRecoveryHook/
│   ├── backup-core.mjs           # Shared backup logic
│   ├── statusline-monitor.mjs    # Full-featured StatusLine (ANSI colors, progress bars, API usage)
│   ├── trigger-backup.mjs        # Backup trigger helper (called by statusline)
│   └── conv-backup.mjs           # PreCompact trigger
├── FormatterHook/
│   └── formatter.mjs
├── LibraryHook/
│   ├── library-sync.mjs          # Stop hook -- mtime check + push
│   ├── library-path-resolver.mjs # Shared per-device path resolver
│   ├── pending-sync.json         # State file (lastSyncAt, lastError)
│   └── logs/                     # Push history (rotated at 500 lines)
└── Validators/
    ├── biome-validator.mjs       # PostToolUse: Biome lint/format
    ├── validate-new-file.mjs     # Stop: new file existence check
    └── validate-file-contains.mjs # Stop: required content check
```

> **Cross-platform note**: All hooks are `.mjs` files invoked directly via `node`. No platform-specific wrappers (`.cmd`, `.sh`, `.ps1`) are needed. This works identically on Windows, Linux, and macOS since Claude Code requires Node.js.

---

## How Hooks Work Together

### The Context Recovery Flow

```
You're working...
     ↓
StatusLine monitors context continuously (statusline-monitor.mjs via Node.js)
     ↓
Token-based trigger: first backup at 50k tokens used, then every 10k after
  OR percentage threshold crossed (30%, 15%, 5% free) -- whichever fires first
     ↓
StatusLine calls backup-core.mjs directly:
  - Parses transcript JSONL
  - Extracts: user requests, Claude responses, files, tasks, agents, skills, MCPs
  - Saves to .claude/backups/{number}-backup-{date}.md
  - Updates state with currentBackupPath and lastBackupAtTokens
     ↓
StatusLine displays backup path on line 4 whenever a backup exists:
  "[!] Opus 4.6 | 150k / 200k | 75% used 150,000 | 8% free 16,500 | thinking: On"
  "-> .claude/backups/3-backup-10th-Feb-2026-5-45pm.md"
     ↓
Context gets full → Compaction happens
     ↓
PreCompact Hook fires (async):
  - Creates final backup via backup-core.mjs
     ↓
User runs /clear → Loads backup file into fresh session
```

**Key change (Jan 2026)**: No automatic re-injection. Use `/clear` after compaction and load the backup manually. This avoids confusion from having both compaction summary and injected context.

### The Formatter Flow

```
Claude writes or edits a file
     ↓
PostToolUse Hook fires (matcher: Write|Edit)
     ↓
FormatterHook checks file extension
     ↓
If supported (.js, .ts, .json, .md, etc.):
  - Runs npx prettier --write on the file
     ↓
File is formatted, Claude continues
```

### The Library Sync Flow

```
Claude finishes a turn (any combination of edits, tool calls, or just a reply)
     ↓
Stop hook fires: library-sync.mjs runs synchronously
     ↓
Reads .claude/library.json + pending-sync.json (lastSyncAt timestamp)
     ↓
Resolves library path on this device:
  - process.env.CLAUDE_LIBRARY_PATH   (env override)
  - ~/.claude/library-paths.json      (registry keyed by library_remote)
  - autodetect under ~/GitHub, ~/code, ~/projects, ~/src
  - actionable error written to pending-sync.json.lastError if all fail
     ↓
mtime walk over managed paths (skills/agents/commands/hooks/rules/CLAUDE.md/...)
  - Early-bail on first hit. Skips logs/, sync artifacts, .log files.
  - Typical no-op cost: ~50ms.
     ↓
If nothing changed:
  Clear lastError, leave lastSyncAt unchanged, exit 0. Done.
     ↓
If something changed:
  Run `node <library-path>/sync.mjs --push --project <project> --yes` (synchronous, ~4-5s)
  Update lastSyncAt = Date.now() on success, persist lastError on failure.
  Exit 0 either way -- never blocks the turn end.
```

**Key design**: One hook, one synchronous run, per turn. Per-device path resolution lives in `library-path-resolver.mjs`. State is a flat `{ lastSyncAt, lastError }` -- no detached worker, no debounce timer, no Windows console flash. Multiple turns that touch managed files produce one commit per turn, which makes git history readable (each commit ties to exactly one Claude turn). Turns that touch nothing managed fire the Stop hook but exit early on the mtime walk and produce zero commits.

### The Biome Validator Flow

```
Claude writes or edits a file
     ↓
PostToolUse Hook fires (matcher: Write|Edit)
     ↓
BiomeValidator checks file extension
     ↓
If supported (.js, .ts, .jsx, .tsx, .json, .css):
  - Runs npx @biomejs/biome check --write (auto-fixes what it can)
     ↓
If unfixable errors remain:
  - Returns {"result": "block"} -- Claude must fix before continuing
If all clean (or Biome not installed):
  - Returns {"result": "continue"} -- Claude proceeds
```

### The Stop Validator Flow (Slash Commands)

```
User runs /team-plan [prompt]
     ↓
Claude generates the plan file in .claude/tasks/
     ↓
Claude attempts to stop (finish the command)
     ↓
Stop Hook fires: validate-new-file.mjs
  - Checks git status + recent files in .claude/tasks/
  - If no new .md file found → BLOCKS with action required message
     ↓
Stop Hook fires: validate-file-contains.mjs
  - Finds newest file in .claude/tasks/
  - Checks for required sections (## Objective, ## Step by Step Tasks, etc.)
  - If sections missing → BLOCKS with list of missing sections
     ↓
Both pass → Command completes successfully
```

**Key design**: Stop validators use `{"result": "block"}` with actionable error messages that tell Claude exactly what to fix. Claude cannot finish the command until validators pass.

---

## Hook Details

### 1. SkillActivationHook (UserPromptSubmit)

**Location**: `.claude/hooks/SkillActivationHook/`

**What it does**:

- Reads your prompt before Claude processes it
- Matches against skill trigger rules in `.claude/skills/skill-rules.json`
- Outputs skill recommendations that get injected into context

**Files**:

- `skill-activation-prompt.mjs` - Main logic (invoked directly via `node`)

**Configuration**: See `.claude/skills/skill-rules.json`

---

### 2. ContextRecoveryHook (StatusLine + PreCompact)

**Location**: `.claude/hooks/ContextRecoveryHook/`

This hook uses a multi-file architecture for clean separation of concerns.

#### Architecture

| File                     | Trigger                 | Responsibility                                                   |
| ------------------------ | ----------------------- | ---------------------------------------------------------------- |
| `backup-core.mjs`        | Called by others        | Parse transcript, format markdown, save file, update state       |
| `statusline-monitor.mjs` | StatusLine (continuous) | 4-line ANSI colored display, threshold detection, backup trigger |
| `trigger-backup.mjs`     | Called by statusline    | Lightweight Node wrapper to invoke backup-core.mjs               |
| `conv-backup.mjs`        | PreCompact hook         | Handle pre-compaction event                                      |

#### StatusLine Monitor (statusline-monitor.mjs) - v5

**What it does**:

1. Receives context metrics from Claude Code's statusLine feature (JSON via stdin)
2. Displays 4-line colored status with model info, token counts, and usage bars
3. Fetches Anthropic usage API data (5-hour, weekly, extra) with 60s cache
4. Calculates "free until autocompact" (remaining - 33k token buffer)
5. Token-based backups: first at 50k tokens used, then every 10k after (primary system)
6. Percentage-based backups: thresholds at 30%, 15%, 5% free + continuous below 5% (safety net)
7. Shows backup path on line 4 whenever a backup exists for the session

**Implementation**: Pure Node.js with cross-platform APIs (`os.homedir()`, `os.tmpdir()`, `path.join()`). No platform-specific dependencies.

**Token calculation**:

- "Used" display: `input_tokens + cache_creation + cache_read` (matches `/context` header)
- "Free" display: deducts `output_tokens` AND autocompact buffer from window size (matches `/context` free space)

**StatusLine output (4 lines)**:

```
[!] Opus 4.6 | 150k / 200k | 75% used 150,000 | 8% free 16,500 | thinking: On
current: ●●●●●○○○○○ 42% | weekly: ●●●○○○○○○○ 32%
resets 5:00pm (3h16m)    | resets 12th, 7:00pm
-> .claude/backups/3-backup-10th-Feb-2026-5-45pm.md
```

Line 1: Model, tokens, used/free percentages, thinking status (with [!]/[!!]/[!!!] warnings)
Line 2: Usage limit progress bars (5-hour current, 7-day weekly, extra credits)
Line 3: Reset times with countdown for current, day-of-month for weekly
Line 4: (conditional) Backup path when context < 30% free until autocompact

#### PreCompact (conv-backup.mjs)

**What it does**:

1. Receives PreCompact event with transcript path
2. Calls `backup-core.mjs` to create backup
3. Runs with `async: true` (non-blocking)

#### Backup Core (backup-core.mjs)

**What it extracts**:

- User requests (filtered to actual messages, no system/command output)
- Claude's key responses (direct text replies, commits, outcomes)
- Files modified (Write/Edit tools)
- Tasks (TaskCreate, TaskUpdate - Anthropic's task system)
- Sub-agent calls (Task tool)
- Skills loaded (Skill tool)
- MCP tool calls
- Build/test commands

**Backup filename format**: `{number}-backup-{day}{ordinal}-{month}-{year}-{hour}-{min}{ampm}.md`

**Example**: `3-backup-26th-Jan-2026-5-45pm.md`

**State tracking**: Updates `~/.claude/claudefast-statusline-state.json` with:

```json
{
  "sessionId": "abc123",
  "lastFreeUntilCompact": 25.5,
  "currentBackupPath": ".claude/backups/3-backup-26th-Jan-2026-5-45pm.md"
}
```

**Key improvement**: Backups are ~1-6 KB of structured data instead of 1-8 MB raw transcripts (99.9% reduction).

#### Recommended Workflow

After compaction:

1. Note the backup path shown in statusline
2. Run `/clear` to start fresh session
3. Load the backup file into the new session

This avoids confusion from having both compaction summary and injected context

---

### 3. FormatterHook (PostToolUse)

**Location**: `.claude/hooks/FormatterHook/`

**What it does**:

1. Triggers after Write or Edit tool completes
2. Checks if file extension is supported by Prettier
3. Runs `npx prettier --write` on the file

**Files**:

- `formatter.mjs` - Main logic (invoked directly via `node`)

**Supported extensions**:

- JavaScript/TypeScript: `.js`, `.jsx`, `.ts`, `.tsx`
- Data: `.json`, `.yaml`, `.yml`
- Markup: `.md`, `.mdx`, `.html`
- Styles: `.css`, `.scss`, `.less`
- Frameworks: `.vue`, `.svelte`

**Matcher**: `Write|Edit` (only triggers on these tools)

---

### 4. LibraryHook (Stop)

**Location**: `.claude/hooks/LibraryHook/`

**What it does**:

At the end of every Claude turn, scans library-managed files in the project for any modification since the last sync. If anything changed, runs `sync.mjs --push --yes` synchronously to commit the changes back to the central library repo (`claude-library`). One hook, one decision per turn, never blocks the turn end.

**Files**:

| File                        | Role                                                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `library-sync.mjs`          | Stop-hook driver. Reads manifest + state, walks managed paths for mtime > lastSyncAt, runs `sync.mjs --push` on hit |
| `library-path-resolver.mjs` | Pure-Node helper that resolves the local library path on this device (env / registry / autodetect / legacy)         |
| `pending-sync.json`         | State file: `{ lastSyncAt: <ms>, lastError: <string\|null> }`                                                       |
| `logs/library-sync.log`     | Rolling push history (capped at 500 lines)                                                                          |

> The pre-v5.3 `library-mtime-check.mjs` and `library-sync-worker.mjs` files were removed. The driver no longer spawns detached workers -- see the architectural note below.

**Per-device path resolution**:

The library lives at a different absolute path on every device. The resolver walks four sources (first hit wins):

1. `process.env.CLAUDE_LIBRARY_PATH` -- env override for CI / debugging
2. `~/.claude/library-paths.json` -- per-device registry keyed by `library_remote` (the git URL from `.claude/library.json`). Schema: `{ "$schema": "library-paths-v1", "libraries": { "<remote>": "<absolute-local-path>" } }`
3. Autodetect -- scan common GitHub roots (`~/GitHub`, `~/Github`, `~/github`, `~/code`, `~/projects`, `~/src`) for a checkout whose `git remote get-url origin` matches `library_remote`. On hit, self-registers into the registry so future runs take the fast path
4. Legacy `manifest.library_path` -- one-shot graceful migration for projects synced before v5.3. If valid on disk, auto-registers into the registry, then v5.4 can drop this branch

If all four fail, the resolver returns a user-actionable message that gets persisted to `pending-sync.json.lastError`:

```
Library path not registered on this device. Run `node sync.mjs --link`
from your library directory (<library-remote>) to register it.
```

**Detection logic**:

1. Read `.claude/library.json` (falls back to legacy `.library-manifest.json`)
2. Read `pending-sync.json.lastSyncAt`. If absent and the manifest has `synced_at`, seed from that. Otherwise claim "now" and skip this run (bootstrap path -- avoids spuriously pushing every managed file on first ever run)
3. Build the list of managed paths from the manifest (skills dirs, agent files, command files, hooks dirs, rules, CLAUDE.md, settings, MCP, deploy files)
4. mtime-walk each path with early-bail on the first hit. Skip `pending-sync.json`, `skill-rules.json`, `agent-rules.json`, `recommendation-log.json`, `.syncignore`, `.DS_Store`, `Thumbs.db`, any `.log` file, `logs/` and `node_modules/` directories, plus per-item ignore patterns from the manifest

**Behavior**:

| State                            | Action                                                                  |
| -------------------------------- | ----------------------------------------------------------------------- |
| Nothing changed since lastSyncAt | Clear `lastError`, leave `lastSyncAt` untouched, exit 0                 |
| Changes found, path resolved     | Run `node <library>/sync.mjs --push --project <project> --yes` (~4-5s)  |
| Changes found, path NOT resolved | Persist actionable error to `lastError`, do NOT advance `lastSyncAt`    |
| Push succeeds                    | Update `lastSyncAt = Date.now()`, clear `lastError`                     |
| Push fails (timeout, git error)  | Persist `err.stderr` or `err.message` (whichever is set) to `lastError` |
| Any unexpected throw             | Logged, `process.exit(0)` -- never blocks the turn end                  |

**Why we abandoned the detached worker** (architectural note):

The pre-v5.3 design used a `child_process.spawn(..., { detached: true, windowsHide: true })` worker that slept 180 seconds before pushing, debouncing rapid edits into a single library commit. On Windows, the worker reliably caused a console window to flash on screen at every spawn. The root cause is [nodejs/node#21825](https://github.com/nodejs/node/issues/21825) -- libuv's Windows process spawner has no clean way to fully detach a console child without inheriting one, regardless of `windowsHide`, `stdio: 'ignore'`, `detached: true` combinations. We tried each variant; all flashed.

We also tested wrapping the spawn through `cmd /c start "" /b` -- a pattern several mainstream Node tools use to dodge the same bug. That made the symptom worse: the cmd console stayed visible for the full 180s debounce, because `start /b` falls back to running synchronously inside cmd when cmd has no inherited console (and `windowsHide` strips that inherited console). The wrapper trades a one-second flash for a three-minute one. Dead end.

The Stop-hook design trades the 180s debounce for a per-turn push. Multiple edits in the same turn = one commit (still batched). Multiple turns that touch managed files = multiple commits (no longer batched). Turns that touch nothing managed fire the hook but produce no commit (mtime walk early-bails). The git history is cleaner -- each commit corresponds to exactly one Claude turn that changed something, which matches the unit users actually reason about.

**Dependencies**: requires a `claude-library` checkout reachable via the resolver chain. After cloning the library on a new device, run `node sync.mjs --link` once from the library directory to register the path.

---

### 5. PermissionHook (PermissionRequest) - External Package

> **Note**: Unlike the other hooks which are project-level (stored in `.claude/hooks/`), the PermissionHook is installed globally at the **device level**. It applies to all Claude Code sessions across all projects on your machine.

**Package**: `@abdo-el-mobayad/claude-code-fast-permission-hook`

**Install**: `npm install -g @abdo-el-mobayad/claude-code-fast-permission-hook`

**Setup**: Run `cf-approve install` (adds hook to `~/.claude/settings.json`)

**What it does**:

1. Intercepts all Claude Code permission requests before the native dialog appears
2. Uses a 3-tier decision system:
   - **Tier 1 (Fast)**: Instant allow/deny/passthrough based on hardcoded patterns
   - **Tier 2 (Cache)**: Returns cached decisions for repeat requests (168h TTL)
   - **Tier 3 (LLM)**: Queries gpt-4o-mini via OpenRouter for uncertain cases

**Decision Types**:

| Decision      | Behavior                                       |
| ------------- | ---------------------------------------------- |
| `allow`       | Auto-approve silently (user never sees dialog) |
| `deny`        | Block operation with message                   |
| `passthrough` | Show native Claude dialog (user decides)       |

**Fast Decision Lists** (in `fast-decisions.ts`):

```typescript
// Auto-approved tools
INSTANT_ALLOW_TOOLS: Read, Glob, Grep, Write, Edit, Task, TodoWrite, etc.

// Passthrough tools (user MUST see and respond)
INSTANT_PASSTHROUGH_TOOLS: AskUserQuestion

// Instant deny patterns
INSTANT_DENY_BASH_PATTERNS: rm -rf /, git push --force main, etc.
```

**Adding Passthrough Tools**:

To add more tools that should always show the native dialog:

```typescript
// In fast-decisions.ts
const INSTANT_PASSTHROUGH_TOOLS = new Set([
  "AskUserQuestion",
  // Add more tools here
]);
```

**Configuration**:

Config file: `~/.claude-code-fast-permission-hook/config.json`

```json
{
  "llm": {
    "provider": "openrouter",
    "apiKey": "sk-or-v1-xxx",
    "model": "gpt-4o-mini",
    "baseUrl": "https://openrouter.ai/api/v1",
    "systemPrompt": "..."
  },
  "cache": { "enabled": true, "ttlHours": 168 },
  "logging": { "enabled": true, "level": "info" }
}
```

**Commands**:

```bash
cf-approve install      # Install hook into Claude settings
cf-approve uninstall    # Remove hook
cf-approve config       # Reconfigure API key/provider
cf-approve clear-cache  # Clear cached decisions
cf-approve doctor       # Diagnose setup
cf-approve status       # Show current config
```

**Logs**: `~/.claude-code-fast-permission-hook/approval.jsonl`

---

### 6. BiomeValidator (PostToolUse)

**Location**: `.claude/hooks/Validators/biome-validator.mjs`

**What it does**:

1. Triggers after Write or Edit tool completes
2. Checks if the file extension is supported by Biome
3. Runs `npx @biomejs/biome check --write` to auto-fix lint/format issues
4. If unfixable errors remain, blocks Claude from continuing until they are resolved

**Supported extensions**: `.js`, `.jsx`, `.ts`, `.tsx`, `.json`, `.css`

**Behavior**:

| Scenario              | Result     | Effect                                  |
| --------------------- | ---------- | --------------------------------------- |
| Biome passes          | `continue` | Claude proceeds normally                |
| Biome auto-fixes      | `continue` | File updated silently, Claude proceeds  |
| Unfixable errors      | `block`    | Claude must fix errors before moving on |
| Biome not installed   | `continue` | Skipped with warning, Claude proceeds   |
| Unsupported file type | `continue` | Skipped, Claude proceeds                |

**Timeout**: 10 seconds

**Matcher**: `Write|Edit` (configured in `.claude/settings.json`)

---

### 7. ValidateNewFile (Stop Hook)

**Location**: `.claude/hooks/Validators/validate-new-file.mjs`

**What it does**:

1. Runs when a slash command (e.g., `/team-plan`) attempts to finish
2. Checks git status for new/untracked files in a target directory
3. Falls back to checking file modification times (within `--max-age` window)
4. Blocks the command from completing if no new file is found

**Parameters**:

| Flag              | Default         | Description                        |
| ----------------- | --------------- | ---------------------------------- |
| `-d, --directory` | `.claude/tasks` | Directory to check for new files   |
| `-e, --extension` | `.md`           | File extension to match            |
| `--max-age`       | `5`             | Max file age in minutes (fallback) |

**Used by**: `/team-plan` Stop hook

**Error message**: Tells Claude exactly what directory and pattern to create a file in, with "Do not stop until the file has been created."

---

### 8. ValidateFileContains (Stop Hook)

**Location**: `.claude/hooks/Validators/validate-file-contains.mjs`

**What it does**:

1. Runs when a slash command attempts to finish
2. Finds the newest file in the target directory (by git status + modification time)
3. Reads the file and checks for all required strings (case-sensitive)
4. Blocks if any required sections are missing

**Parameters**:

| Flag              | Default         | Description                               |
| ----------------- | --------------- | ----------------------------------------- |
| `-d, --directory` | `.claude/tasks` | Directory to search                       |
| `-e, --extension` | `.md`           | File extension to match                   |
| `--max-age`       | `5`             | Max file age in minutes                   |
| `--contains`      | (none)          | Required string (repeatable for multiple) |

**Used by**: `/team-plan` Stop hook with these required sections:

```
--contains "## Task Description"
--contains "## Objective"
--contains "## Relevant Files"
--contains "## Step by Step Tasks"
--contains "## Acceptance Criteria"
--contains "## Team Orchestration"
--contains "### Team Members"
```

**Error message**: Lists each missing section by name, with "Do not stop until all required sections are present in the file."

---

## Configuration

All hooks are configured in `.claude/settings.json`. Commands use `node` directly for cross-platform compatibility:

```json
{
  "statusLine": {
    "type": "command",
    "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/ContextRecoveryHook/statusline-monitor.mjs\""
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/SkillActivationHook/skill-activation-prompt.mjs\""
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/ContextRecoveryHook/conv-backup.mjs\"",
            "async": true
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/FormatterHook/formatter.mjs\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/LibraryHook/library-sync.mjs\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Key design**: All hooks invoke `node <file>.mjs` directly via `$CLAUDE_PROJECT_DIR`. No platform-specific wrappers (`.cmd`, `.sh`, `.ps1`). Works on Windows, Linux, and macOS since Claude Code requires Node.js.

**Note**: The `async: true` option allows PreCompact to run in the background without blocking Claude's execution. The new `async` flag (Claude Code v2.1+) extends this pattern to any hook -- see the [Async Hooks](#async-hooks-claude-code-v21) section below.

**Note**: Stop hooks (ValidateNewFile, ValidateFileContains) used by slash commands are not configured in `settings.json`. They are configured per-command in the slash command's YAML frontmatter. See `.claude/commands/team-plan.md` for an example. The LibraryHook above is the one Stop hook configured globally.

---

## Async Hooks (Claude Code v2.1+)

### What it is

Claude Code v2.1 (January 2026) introduced an `async: true` flag on hook commands. When set, the harness runs the hook in a managed background process: the current turn proceeds without waiting, and the hook's exit code, stdout, and stderr are surfaced on the next conversation turn instead of the current one. Anthropic's reference example is a periodic backup job:

```json
{
  "type": "command",
  "command": "node backup-script.js",
  "async": true,
  "timeout": 30
}
```

The harness owns the spawn, the lifecycle, and the result delivery. The hook script itself stays a plain Node script -- no `child_process.spawn({ detached: true })`, no `nohup`, no platform-specific incantation.

### Why it matters

Two specific capabilities show up here:

1. **Long-running background work without blocking the turn.** Anything that takes >2s -- batch image optimization, search-index rebuilds, log compaction, network-bound health checks -- can run while Claude continues responding. Before async hooks, the only options were "block the turn" or "spawn detached and hope".
2. **True detached execution without rolling your own.** This is the bigger win. Hand-rolled detached spawns hit [nodejs/node#21825](https://github.com/nodejs/node/issues/21825) on Windows -- the same bug that drove our LibraryHook off the worker pattern. Anthropic's harness has been hardened across Windows, macOS, and Linux, so any hook that previously wanted detached behavior should use `async: true` instead.

### When to use it

- Background backups or syncs that take >2 seconds and don't need to complete before the next turn
- Periodic batch operations: image optimization, search-index rebuilds, log rotation, generated-asset rebuilds
- Network-bound checks that shouldn't sit on the user's critical path -- API status polls, webhook deliveries, deployment health probes
- Any hook that would otherwise call `child_process.spawn` with `detached: true` to escape the blocking nature of a synchronous hook

### When NOT to use it

Async results land on the **next** turn, not the current one. So async is wrong for:

- Input validation -- the next tool call needs the verdict now
- Permission checks -- same reason
- Fast formatters that should block the edit until they finish (FormatterHook stays synchronous for this reason)
- Anything that gates the next step in the same turn

It's also wrong for races. There's no built-in dedup: 10 rapid edits = 10 sleeping async hooks unless you implement a lockfile inside the script. If your script hits a shared resource (git repo, database, single-writer file), wrap the work in your own `proper-lockfile`-style guard.

### The settings.json shape

```json
"PostToolUse": [{
  "matcher": "Edit|Write|MultiEdit",
  "hooks": [{
    "type": "command",
    "command": "node .claude/hooks/MyHook/long-job.mjs",
    "async": true,
    "timeout": 200
  }]
}]
```

`timeout` is in seconds. The official docs default is 600s; a few community guides (smartscope.blog, marc0.dev) cite 30s. Set it explicitly rather than relying on the implicit default -- the actual value has shifted between minor releases.

### Why we did NOT use it for LibraryHook

We considered async for the v5.3 refactor and chose Stop-hook anyway:

- **Version coverage.** Stop hooks work on Claude Code releases older than v2.1, so the LibraryHook ships to a wider customer base
- **Simplicity.** A single hook is simpler to reason about than `async PostToolUse` plus a Stop flush plus a SessionEnd flush to make sure pending work doesn't leak across sessions
- **Timing.** Per-turn pushes land while the user is reading Claude's response -- a natural idle moment. An async timer would land mid-response and feel less natural
- **Footprint.** One settings.json entry vs three; one log file to tail vs multiple

### Patterns this enables for future ClaudeFast hooks

- Background context-recovery upload to a remote service (the local backup stays synchronous; the upload goes async)
- Async agent dispatching for non-critical post-commit analysis -- code-quality scans, license checks, type-coverage diffs
- Periodic external API polling -- GitHub PR status, deployment health, npm audit, Algolia index drift
- Lockfile-coordinated batch jobs that survive across sessions (e.g. nightly skill-rules.json regeneration that picks up where it left off)

The mental model: if the work isn't on the user's critical path AND its result doesn't need to land in the current turn, it's a candidate for `async: true`.

---

## Debugging

### Check Hook Logs

Each hook writes to its own log directory:

```bash
# Skill Activation (state tracking)
cat .claude/hooks/SkillActivationHook/recommendation-log.json

# Context Recovery (all three files log here)
cat .claude/hooks/ContextRecoveryHook/logs/backup-core.log
cat .claude/hooks/ContextRecoveryHook/logs/statusline-monitor.log

# Formatter
cat .claude/hooks/FormatterHook/logs/formatter.log

# Library Sync
cat .claude/hooks/LibraryHook/logs/library-sync.log
cat .claude/hooks/LibraryHook/pending-sync.json
```

### Test Hooks Manually

You can test hooks by piping JSON to them (works on any platform):

```bash
# Test StatusLine Monitor
echo '{"session_id":"test","model":{"display_name":"Test"},"context_window":{"context_window_size":200000,"remaining_percentage":50}}' | node .claude/hooks/ContextRecoveryHook/statusline-monitor.mjs

# Test PreCompact
echo '{"session_id":"test","transcript_path":"","trigger":"manual"}' | node .claude/hooks/ContextRecoveryHook/conv-backup.mjs

# Test Formatter
echo '{"tool_name":"Write","tool_input":{"file_path":"test.js"}}' | node .claude/hooks/FormatterHook/formatter.mjs

# Test Library Sync (Stop hook -- mtime check + push if changed)
echo '{"session_id":"test"}' | node .claude/hooks/LibraryHook/library-sync.mjs

# Inspect state
cat .claude/hooks/LibraryHook/pending-sync.json

# Manually re-link library on this device (per-device registry)
node <library-path>/sync.mjs --link

# Test Biome Validator
echo '{"tool_name":"Write","tool_input":{"file_path":"test.ts"}}' | node .claude/hooks/Validators/biome-validator.mjs

# Test ValidateNewFile (Stop hook -- no stdin needed, uses CLI args)
echo '{}' | node .claude/hooks/Validators/validate-new-file.mjs --directory .claude/tasks --extension .md

# Test ValidateFileContains (Stop hook -- checks newest file for required sections)
echo '{}' | node .claude/hooks/Validators/validate-file-contains.mjs --directory .claude/tasks --extension .md --contains "## Objective"
```

### Check State File

To see current backup tracking state:

```bash
cat ~/.claude/claudefast-statusline-state.json
```

---

## Disabling Hooks

To disable an automation hook, remove or comment out its entry in `.claude/settings.json`.

To disable a Stop validator, remove its entry from the slash command's YAML frontmatter (e.g., in `.claude/commands/team-plan.md`).

To disable all hooks temporarily, rename the `hooks` key:

```json
{
  "_hooks_disabled": {
    ...
  }
}
```

---

## Customization

All backup customization is done in `ContextRecoveryHook/backup-core.mjs`:

### Customize Summary Format

Edit function `formatSummaryMarkdown()` to change how summaries are formatted.

### Change Backup Location or Filename Format

Edit these functions:

- `saveBackup()` - Change where backups are saved
- `formatFriendlyDate()` - Change date/time format (e.g., `26th-Jan-2026-4-30pm`)
- `getOrdinalSuffix()` - Change day suffix (1st, 2nd, 3rd, 4th, etc.)
- `getNextBackupNumber()` - Change numbering logic

### Modify What Gets Extracted

Edit function `parseTranscript()` to add or remove extraction logic.

### Change User Request Filtering

Look for the comment `// Skip tool results and system messages` to modify what user messages are filtered out.

### Change Backup Thresholds

Edit `ContextRecoveryHook/statusline-monitor.mjs`:

```javascript
// Token-based triggers (primary system)
const TOKEN_FIRST_BACKUP = 50000; // First backup at 50k tokens used
const TOKEN_UPDATE_INTERVAL = 10000; // Update every 10k tokens after that

// Percentage-based triggers (safety net, especially for 200k windows)
const BACKUP_THRESHOLDS = [30, 15, 5]; // Percentage thresholds
const CONTINUOUS_BACKUP_THRESHOLD = 5; // Below this, every decrease triggers backup
const AUTOCOMPACT_BUFFER_TOKENS = 33000; // Fixed 33k token buffer before autocompact
```

### Add ESLint to Formatter

Uncomment the ESLint section in `FormatterHook/formatter.mjs`:

```javascript
// Run ESLint for JS/TS files
if (ESLINT_EXTENSIONS.includes(ext)) {
  const eslintResult = runEslint(filePath);
  if (eslintResult.success) {
    log(`ESLint: success`);
  }
}
```

---

## Troubleshooting

### "Prettier not found"

Ensure Prettier is installed in your project:

```bash
pnpm add -D prettier
```

### Hooks not running

1. Check that `.claude/settings.json` has the hooks configured
2. Verify commands use `node .claude/hooks/...` (not `cmd /c` or `powershell`)
3. Check that Node.js is installed and in PATH

### StatusLine not showing

1. Verify `statusLine` is configured in settings.json (top level, not inside `hooks`)
2. Check that Node.js is installed: `node --version`
3. Test manually: `echo '{"session_id":"test","model":{"display_name":"Test"},"context_window":{"context_window_size":200000,"remaining_percentage":50}}' | node .claude/hooks/ContextRecoveryHook/statusline-monitor.mjs`

### Backups not being created

1. Check state file: `cat ~/.claude/claudefast-statusline-state.json`
2. Check logs: `cat .claude/hooks/ContextRecoveryHook/logs/backup-core.log`
3. Verify backup directory exists: `ls .claude/backups/`

### Biome validator blocking unexpectedly

1. Run Biome directly to see the full error: `npx @biomejs/biome check --write <file>`
2. If Biome is not needed, remove the biome-validator entry from `.claude/settings.json`
3. Biome auto-skips if not installed (graceful fallback)

### Library sync not pushing

1. Read the most recent error: `cat .claude/hooks/LibraryHook/pending-sync.json` -- the `lastError` field holds the last failure message
2. If `lastError` says "Library path not registered on this device", run `node <library-path>/sync.mjs --link` from your library directory. This writes the local path into `~/.claude/library-paths.json` keyed by your library's git remote
3. Tail recent hook fires: `tail -30 .claude/hooks/LibraryHook/logs/library-sync.log`
4. Verify the Stop hook is registered: `cat .claude/settings.json` -- look for the `"Stop"` block referencing `library-sync.mjs`
5. Manual test: pipe a fake Stop event into the hook directly with the test command above. The exit code is always 0, but the log output and `pending-sync.json.lastError` reveal the failure
6. Verify the manifest exists: `cat .claude/library.json | head -10` (older projects may still carry `.library-manifest.json` -- both are accepted)

### Stop validators blocking /team-plan

1. The validators are working as intended -- they enforce output structure
2. Check the error message: it tells Claude exactly what is missing
3. If the plan file exists but validators still block, check that the file is in `.claude/tasks/` and was created within the last 5 minutes
4. To temporarily bypass, remove the Stop hooks from `.claude/commands/team-plan.md` frontmatter

---

## References

- [Claude Code Hooks Documentation](https://code.claude.com/docs/en/hooks)
- [Anthropic Hooks Blog Post](https://claude.com/blog/how-to-configure-hooks)
- [smartscope: Claude Code hooks guide -- async coverage](https://smartscope.blog/en/generative-ai/claude/claude-code-hooks-guide/)
- [marc0.dev: Production patterns for async hooks (no dedup, lockfile guidance)](https://www.marc0.dev/en/blog/claude-code-hooks-production-patterns-async-setup-guide-1770480024093)
- [nodejs/node#21825 -- Windows detached-spawn console-flash bug](https://github.com/nodejs/node/issues/21825)
- [ClaudeFast Blog: Hooks Guide](/blog/tools/hooks/hooks-guide)
