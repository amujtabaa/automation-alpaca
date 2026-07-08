# AI Project OS Version

Package version: **v0.8.0**  
Release date: **2026-07-07**

## Canonical version rule

`VERSION.md` and `AI_OS_MANIFEST.yaml` are the canonical version sources. Other files should reference this package release or identify themselves explicitly as component/schema versions.

## Component versions

| Component | Version | Notes |
|---|---:|---|
| Core docs | 0.8.0 | Main OS documentation set. |
| Manifest | 0.8.0 | Installer/source-of-truth metadata. |
| AI OS rules schema | 0.8.0 | `rules/ai-os-rules.yaml`. |
| Prompt rules schema | 0.8.0 | `rules/prompt-rules.yaml`. |
| MCP control-plane spec | 0.8.0 | `14_MCP_CONTROL_PLANE.md` and `mcp/`. |
| Adapter shims | 0.8.0 | Claude, Codex, and generic adapters. |
| Scripts | 0.8.0 | Tested harness checks; no stubs remaining. |

## Versioning policy

- Package releases use semantic-style versions: `MAJOR.MINOR.PATCH`.
- Component/schema versions should normally match the package release unless a component is deliberately versioned independently.
- If a component intentionally diverges, explain why in this file and `CHANGELOG.md`.
- The installer should report mismatches between `VERSION.md`, `AI_OS_MANIFEST.yaml`, rule-schema version fields, and MCP target metadata.

## v0.8.0 scope

v0.8.0 completes the mechanical enforcement layer: a formal ledger contract (`mcp/schemas/ledger_entry.schema.json` + `scripts/check_ledger.py`), real disposition and hygiene checks replacing the last stubs, a permanent additive-only MCP write policy (deletion excluded from MCP), the `pkl_root` manifest variable, and the completed 5-tool read-only MCP MVP (`ai_os_hygiene_report`, `ai_os_disposition_review` added). See `CHANGELOG.md`.

## v0.7.0 scope

v0.7.0 hardens the harness: a working read-only stdio MCP server (doctor, context packet, work-order validation; schema-validated, protocol smoke-tested), four scripts promoted out of stub status (manifest-rooted, rules-configured, tested), and a new `check_install.py` that validates repositories against the manifest `install_map`. See `CHANGELOG.md`.

## v0.6.0 scope

v0.6.0 is a correctness-and-simplification patch: manifest `install_map` + `not_installed` list, layout-independent scripts, honest stub exit codes (3 = NOT_IMPLEMENTED), dual Fable block dialects, single-source vocabulary/budgets in `rules/ai-os-rules.yaml`, de-opinionated adapter shims, shipped Fable skill payloads, and a stripped (non-registerable) MCP scaffold. See `CHANGELOG.md`.
