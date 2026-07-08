# Harness, Rules, and CI

## Purpose

A harness turns repeatable instructions into deterministic checks.

## Enforcement ladder

```text
1. Instruction: AGENTS.md tells the agent what to do
2. Protocol: Fable requires visible blocks
3. Work order: allowed paths and required commands are specified
4. Local script: validates path scope, frontmatter, tests, and logs
5. Hook: runs script during lifecycle
6. Pre-commit: blocks local commit
7. CI: blocks merge
8. Human review: resolves judgment and risk
```

## Minimum local checks

```text
python .ai-os/scripts/check_work_order_scope.py
python .ai-os/scripts/check_pkl.py
python .ai-os/scripts/check_fable_done.py
npm test / pytest / project test command
npm run lint / ruff / project lint command
npm run typecheck / mypy / project type command
```

All shipped checks are implemented, tested, and manifest-rooted (the former disposition and hygiene stubs are now real: `check_work_order_disposition.py`, `context_hygiene_report.py`; plus `check_install.py` and `check_ledger.py`). If a future starter check ships before it is real, it must carry a `_stub` suffix, exit `3` (`NOT_IMPLEMENTED`), and print a do-not-gate warning — never wire such a stub in as a blocking gate.

## Things to enforce mechanically

- forbidden path edits
- required path ownership
- missing PKL frontmatter
- missing ADR for architecture changes
- skipped tests
- changed tests with reduced assertions
- new dependency without approval
- secrets in diff
- no test changes for behavior changes
- high-risk surface changed without security checklist

## Things not to enforce purely mechanically

- whether architecture is elegant
- whether a test is meaningful
- whether a model’s root-cause explanation is correct
- whether a requirement was interpreted correctly
- whether a tradeoff is acceptable

Those require reviewer judgment.

## Hook strategy

Use hooks to run checks when available, but do not depend on a single tool. Keep checks as plain scripts that can run from Codex hooks, Claude hooks, pre-commit, CI, or manually.

## File-level harness concept

A file-level harness should validate the current work order against the actual diff:

```text
Inputs:
- work-order.md
- git diff --name-only
- ai-os-rules.yaml

Checks:
- every changed path matches allowed_paths
- no changed path matches forbidden_paths
- sensitive paths trigger required checklist
- test command evidence exists
- PKL update required? yes/no

Output:
- PASS / FAIL
- specific violations
```


## MCP and harness boundaries

MCP tools may report or orchestrate checks, but deterministic enforcement still belongs in scripts, hooks, tests, and CI.

Recommended boundary:

| Concern | MCP | Script/hook/CI |
|---|---|---|
| Context packet generation | yes | no |
| Work-order validation report | yes | optional |
| Changed-file scope check | report/propose | enforce |
| PKL frontmatter validation | report/propose | enforce |
| Test execution | do not wrap broadly | enforce/run directly |
| Deletion | propose only | never automatic without approval |
| CI activation | propose only | human-approved |

MCP should not become an unrestricted terminal or hidden CI substitute.
