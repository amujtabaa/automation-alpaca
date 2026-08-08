# WO-0149 scope-check correction independent review addendum 02

Review target: `work/review/REV-0052/frozen-candidate.md`

Target SHA-256: `0936E114642F5B531A9996EB5685F39024B2982BB1F5BD348FF8048DBB13086D`

Review mode: independent static, exact-candidate review. No tests, application code, SQL/DDL,
database tooling, broker activity, network activity, or Git mutation was executed.

## Reviewed correction

The task-scoped one-command correction at `frozen-candidate.md:386` replaces the invalid
`--base` scope-check invocation with:

```powershell
git diff --name-only <activation-commit-sha>..HEAD | .\.venv\Scripts\python.exe .ai-os\scripts\check_work_order_scope.py work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
```

Static evidence: `check_work_order_scope.py` reads the work-order path from its first positional
argument and changed paths from standard input. The corrected command provides both inputs; the
candidate contains no remaining `--base` token. Its adjacent start-gate text requires replacement
with the exact documentation-only activation SHA before execution.

## Findings

No findings.

The correction is confined to the post-authorization required-command block. The frozen candidate
continues to state `implementation_authority: NOT_GRANTED`, prohibits application/test
implementation pending later explicit authority, and leaves the normative M1E contract and allowed
scope unchanged.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: Runtime execution and external provenance were intentionally not performed under this
static review boundary.

This ACCEPT grants no implementation authority.
