---
type: Review Request
rev_id: REV-0109
round: 2 of 2 maximum
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only static DDL remediation review
date: 2026-08-28
---

# REV-0109 round two — exact-route and catalog-evidence remediation

## Reviewer role and finite boundary

Use a fresh context. Reproduce the three round-one findings, then inspect only their exact
remediations and regressions those changes could introduce. You may also report a newly
demonstrated current-candidate product safety, data-integrity, authority, or scope P0/P1. Create
only `work/review/REV-0109/result-r2.md`; do not edit any existing file, commit, or push.

This is the final REV-0109 review round. The cap does not force acceptance: any open P0/P1 returns
to Ameen as an explicit blocker rather than opening a third packet. `ACCEPT` requires zero open
P0/P1. No SQLite connection, database, DDL installation, held-suite collection/execution,
migration, unlock, later work order, promotion, or merge is authorized.

## Read order

1. `AGENTS.md`, especially safety and independent-review rules.
2. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
3. This request, then `request.md`, reviewer-owned `result.md`, and author-owned `disposition.md`.
4. `work/queue/M2-EXECUTION-2026-08-21/38-REV-0109-R2-DDL-MANIFEST.md`.
5. Remediation diff `6271f353df4c770daccf3c3835bb865fd2ea2f79..0b8398531563414bab9f56a44cb2461278134c8a`.
6. Exact candidate source/tests named below, read as source only where they are held.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168d-hybrid-r1`.
- Round-one packet/disposition head and remediation parent:
  `6271f353df4c770daccf3c3835bb865fd2ea2f79`, tree
  `90bb390146116ed0fedc72a37affd23a0b89b881`.
- Round-two source candidate: `0b8398531563414bab9f56a44cb2461278134c8a`, tree
  `834790e5f6d9a88deccb8b04e52434c6677329d5`.
- Original REV-0108 source predecessor remains
  `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, tree
  `f5ee0646d74047d373ce6b09728177453bd45c82`.
- Candidate `schema.py` Git blob:
  `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`.
- Candidate `schema.py` file SHA-256:
  `94fce06fdeeb1a5c85d09d785246b1c0a9171d560e52ca3c5a59a3eda531b0ae`.
- `SCHEMA_DDL`: 180,858 UTF-8 bytes; SHA-256 and
  `EXPECTED_EXECUTION_DDL_SHA256`:
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Static declarations: 28 tables, 29 indexes, 150 triggers, zero views.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- R4/R5 SQL-manifest SHA-256 identities, unchanged:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39` and
  `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`.
- Compact remediation manifest SHA-256:
  `8a1e21feab16934aff8ab2357e8a1374911e4fc6c4c6457ea50ed7176127cb51`.
- Round-one result remains unchanged at SHA-256
  `d34901ef25ae8b25f31e71f7c3c89ebdf6fc9dd5a78d0eb98d69574fb57dc732`.
- Round-one disposition remains unchanged at SHA-256
  `2a23fdf6177ac51d398207fa024010e327309838be83102ee8a8d9865a8f8715`.

Any later packet-hosting commit may add only this request and one append-only ledger line before
review. Verify that wrapper rule and review the exact source candidate above, not an inferred HEAD.

## Round-one findings and exact root remediations

1. **Market stream route splice.** New trigger
   `trg_durable_input_market_stream_exact_route` requires a `MARKET_OCCURRENCE` input's named
   stream to match its application generation, scope, acquisition generation, market-source
   profile, and session. The held test accepts an exact route, then substitutes a separately valid
   stream differing only by session and requires failure.
2. **Outbox/input route splice.** New trigger `trg_broker_outbox_exact_input_route` requires the
   retained durable input to match the outbox application generation, execution profile, scope,
   domain, and identity. `CLAIM_ACQUISITION_EFFECT` additionally requires the same acquisition
   generation; scope-wide `AUTHORITY` inputs remain acquisition-null by their existing shape
   check. Held tests prove positive exact routes and reject (a) another scope in the same
   application/profile and (b) another acquisition generation in the same scope.
3. **Attempt-two identity gap.** Attempt two is now only a byte-identical environmental or
   interruption retry with a distinct fresh `--basetemp` and zero tracked changes. Any product,
   DDL, test, fixture, or expectation edit stops the authority and requires a new reviewed packet.
4. **Catalog lifecycle made non-authorizing.** The compile-time `_SCHEMA_CATALOG_SHA256` is
   removed. Only the still-False human flag plus the expected and caller-approved exact DDL digest
   can authorize installer connection access and execution. After exact DDL installation on the
   verified empty target, the installer computes the observed catalog digest and stores it beside
   version and DDL identity in immutable `schema_meta`. Every reopen compares the current catalog
   to that retained observation. Held tests bind storage, immutability, spoof refusal, and
   post-install catalog-mutation refusal. This is integrity evidence, not approval.

## Closed review questions

1. Do the two triggers reject the round-one accepted counterexamples while retaining the intended
   exact positive paths, without creating a second authority or impossible ordinary route?
2. Are the held controls genuinely failure-capable if either route trigger or one bound coordinate
   is removed, and do they isolate cross-route, cross-scope, and cross-acquisition attribution?
3. Does the revised installer keep the human flag and exact approved DDL SHA-256 as the sole
   execution authority before connection access, while treating the observed catalog only as
   immutable post-install drift evidence?
4. Does connection verification fail closed on wrong version/DDL identity, malformed or missing
   retained catalog evidence, and current-catalog drift?
5. Is the two-attempt plan now exact, zero-change-only, and incapable of executing a modified test
   or DDL revision under the same decision?
6. Did the remediation alter any index/query manifest, public repository API, runtime composition,
   broker authority, or other behavior outside the authorized findings?

## Permitted static evidence

Source/Git inspection, no-import AST/literal extraction, hashing, `py_compile`, Ruff, mypy,
import-linter, governance checks, and the no-I/O focused tests below are allowed. Importing the
inert schema through those ordinary tests is permitted, but no connection constructor may run.
Do not collect, import, or execute anything under `tests_gated/`.

Author evidence, to reproduce independently where useful:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py tests/execution_core/test_persistence_write_capability.py
.\.venv\Scripts\ruff.exe check app/execution_core/persistence/schema.py tests/execution_core/test_sqlite_boundary.py tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py
.\.venv\Scripts\ruff.exe format --check app/execution_core/persistence/schema.py tests/execution_core/test_sqlite_boundary.py tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\lint-imports.exe
```

Author results: focused no-I/O tests 22 passed; Ruff clean; formatting clean; mypy 95 source files
clean; import-linter 6 kept/0 broken; `git diff --check` clean. Python compilation of all four
changed Python files passed. No held test was collected or executed.

## Proposed later human execution packet — review only

After `ACCEPT` with zero open P0/P1, Codex returns this exact candidate to Ameen. A separate human
approval would be required before a new flag-only unlock commit may branch from the exact accepted
source candidate. The unlock must change only
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN: Final[bool] = False` to `True`, be committed and published,
record commit/tree, and reverify clean tracked state, local equals origin, DDL bytes/digest,
schema blob, manifest, and unchanged R4/R5 identities before any connection access.

Attempt 1 would then be exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0109-r2-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Attempt 2 changes only `rev-0109-r2-attempt-1` to `rev-0109-r2-attempt-2`, and is allowed only
after a proven environmental/interruption failure with zero tracked changes. Before retry, recheck
clean tracked state, local equals origin, and every exact identity. Any assertion failure,
product/schema defect, ambiguous attribution, source/test/fixture change, or second failure stops
and returns to Ameen. No repair is authorized inside the execution packet.

## New-invariant probe obligation

No `INV-*` entry is added or amended by this remediation. Fresh invariant-probe lines are therefore
not applicable. The new held route-splice controls are behavior probes for existing durable-state
requirements, not new invariant declarations.

## Response contract

For each finding, give priority, exact `file:line`, governing requirement, evidence level, concrete
impact, smallest complete resolution, and a disproof pass. End with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

State explicitly that no SQLite/database/DDL/held-suite execution occurred.
