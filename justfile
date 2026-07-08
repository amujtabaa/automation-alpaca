# ClaudeFast Command Runner
# Install just: brew install just / scoop install just / cargo install just
# Then run: just <command>

# Windows compatibility
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Show available commands
default:
    @just --list

# ─── Launch Claude Code ───────────────────────

# Start Claude (optionally with a slash command)
# Examples:
#   just cc              → launches claude
#   just cc team-plan    → launches claude with /team-plan
cc *CMD:
    @if ("{{CMD}}" -eq "") { claude } elseif (Test-Path ".claude/commands/{{CMD}}.md") { claude --init "/{{CMD}}" } else { Write-Host "Error: .claude/commands/{{CMD}}.md not found"; Write-Host ""; Write-Host "Available commands:"; Get-ChildItem ".claude/commands/*.md" | ForEach-Object { $_.BaseName }; exit 1 }

# Start Claude with Agent Teams enabled (required for /team-build)
# Examples:
#   just team            → launches claude with Agent Teams
#   just team team-plan  → launches with Agent Teams + /team-plan
team *CMD:
    @$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = "1"; if ("{{CMD}}" -eq "") { claude } elseif (Test-Path ".claude/commands/{{CMD}}.md") { claude --init "/{{CMD}}" } else { Write-Host "Error: .claude/commands/{{CMD}}.md not found"; exit 1 }

# ─── Utilities ────────────────────────────────

# List available slash commands
commands:
    @Write-Host "Available commands:"; Get-ChildItem ".claude/commands/*.md" | ForEach-Object { Write-Host "  $($_.BaseName)" }
