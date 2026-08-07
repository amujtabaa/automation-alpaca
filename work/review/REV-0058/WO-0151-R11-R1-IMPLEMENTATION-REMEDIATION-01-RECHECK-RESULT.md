# WO-0151 R11 R1 implementation remediation 01 focused recheck result

Review posture: fresh independent exact-delta recheck of the sole P1 retained in
`WO-0151-R11-R1-IMPLEMENTATION-ACCEPTANCE-RESULT.md`. The predecessor
`ACCEPT-WITH-CHANGES` result remains negative evidence and was not rewritten.

## Exact target verification

- Branch: `codex/arch-reset-2026-07-r1`
- Tracked parent and local HEAD: `b6cf1aadfd0aae27ada3262b854c2af30912c0d5`
- Recheck request SHA-256: `6055c6c1c59e55614e44a211717406e5fa5dc0280d065258e734648ef2a706fd`
- Candidate-manifest SHA-256: `2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`
- Retained predecessor-result SHA-256: `84484417c9dce913e8280ec517883646bd3f557678d4ea482734e72f9d929aba`
- Retained mutation-evidence SHA-256: `96509cbae091046d4df51c27cfbb45274ab038499c9fe90f3fc57c72bd42de79`

All controlling WO, R11, R11-R1, RED-manifest, preflight-result, original
candidate-manifest, original request, predecessor-result, and mutation-record
hashes matched the remediation manifest. The tracked delta remained exactly the
11 authorized implementation paths. Relative to the original implementation
manifest, only `acquisition.py`, `authority.py`, `test_acquisition.py`, and
`test_protection.py` changed hashes.

| Exact candidate path | Verified SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85` |
| `app/execution_core/acquisition.py` | `3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7` |
| `app/execution_core/authority.py` | `d59da7c2659f1decbd3ae30755813106af693ce89d6db91e47bc7489d3f2c4fb` |
| `app/execution_core/identity.py` | `8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a` |
| `app/execution_core/protection.py` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` |
| `app/execution_core/venue.py` | `0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f` |
| `tests/execution_core/test_acquisition.py` | `d8156e007ef21584f8bc03081e60b8a79027a09ee9d8b4f0379458ef510f0f7c` |
| `tests/execution_core/test_authority.py` | `f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791` |
| `tests/execution_core/test_import_boundary.py` | `f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4` |
| `tests/execution_core/test_protection.py` | `18c1ac5f50575fd36c2554b816c3313d9c6adcd4c98877fb9f879193d283f330` |
| `tests/execution_core/test_venue_ownership.py` | `63d6f7b04803b7e08c857b1ff9131e5bf8d792a2de2611998ef7d9677a6da754` |

## Focused P1 recheck

### 1. Applied-fact matrix

The missing composite routes are now failure-capable at the E2 boundary:

- A normal current first `FILL` establishes `FLOOR_ONLY`, direct lineage, one
  registry/currentness-head advance, and inert replay
  (`tests/execution_core/test_acquisition.py:2294-2368`).
- Current follow-on `FILL`, tail `TRADE_CORRECT`, tail `TRADE_BUST`, and non-tail
  correction/reconciliation advance the exact generation economics, lineage,
  protection, and controller head once without creating or claiming an ordinary
  effect (`tests/execution_core/test_acquisition.py:2699-3105`).
- Retired `FILL`, `TRADE_CORRECT`, tail `TRADE_BUST`, and non-tail reconciliation
  `TRADE_BUST` update only the routed retired generation, retain it as
  `RETIRED_UNSERVING`, enter the bounded `HARD_BAIL` recovery class, and replay
  without a second registration, effect, or claim
  (`tests/execution_core/test_acquisition.py:3325-3684`).
- A live successor BUY instead uses the single atomic fact-plus-preemption
  receipt, and its pre-fact final claim is stale
  (`tests/execution_core/test_acquisition.py:3687-3792`).

The controller routes facts through direct request/effect/fact lineage, applies
one authority transition, replaces one generation economics record, and advances
one controller/currentness head (`app/execution_core/acquisition.py:4082-4546`).
No audit/history scan or second aggregate writer was found.

### 2. Owner-local inactive-successor correction

The root correction is at the authority owner. The no-preemption result is
available only after all canonical-fact currentness, exact execution, scope,
session, mandate/binding, ordinal, controller-head, reconciliation, and
predecessor-authority checks pass. It then additionally requires:

- an authentic inactive descriptor;
- the active slot to be that exact same descriptor object;
- the descriptor's successor generation to equal the current generation; and
- its predecessor effect to equal the direct fact relation's effect.

See `app/execution_core/authority.py:7287-7383`. Any active successor BUY must
instead authenticate the exact active effect/descriptor and safe local venue
view before the one fact-plus-preemption permit is minted
(`app/execution_core/authority.py:7384-7465`). Acquisition uses the ordinary
canonical-fact source only when that owner returns no preemption; otherwise it
uses the specialized atomic mutation, never both
(`app/execution_core/acquisition.py:4182-4360`). Stale, copied, forked,
cross-scope, mismatched-effect, and mismatched-generation inputs remain
fail-closed through these independent exact-source checks.

### 3. Thirteen named mutations

The retained mutation record identifies one exact production mutation, one
focused control, and the observed semantic RED reason for M01-M13. Static
re-derivation confirmed the controls reach the named fences rather than a
shared superficial assertion:

- M01-M04 cover owner matcher, semantic comparison, cursor/execution linkage,
  and terminal no-work.
- M05-M11 cover preemption purpose, current context, waiting/provenance, goal
  independence, exit-goal/current-transition binding, and the one-cancel cap.
- M12-M13 cover the single head advance and final-claim currentness
  revalidation.

The strengthened owner-matcher and final-claim controls use reachable forged or
pre-minted inputs that remain authentic enough to depend on the exact removed
fence. The evidence records every mutation restored before the next run and
pins the restored production hashes. Repeating the temporary source mutations
was not necessary because the immutable execution record, present controls,
and restored code/control relation reconcile exactly.

## Fresh reproduced evidence

- Complete pure `tests/execution_core`: **1,353 collected, 100%, exit code 0**.
- Independently selected matrix/mutation controls: **17/17 passed**.
- Ruff check for `app/execution_core` and `tests/execution_core`: passed.
- Ruff format verification for the exact 11 Python paths: passed; 11 already
  formatted.
- Mypy `app`: passed with no issues in 87 source files.
- `git diff --check HEAD --`: passed.
- Work-order scope, ledger, PKL, and disposition checks: passed from the
  canonical `.ai-os/scripts` paths.
- Final post-test request, manifest, mutation-record, and 11-path hash recheck:
  passed.

No R2 or full-repository database-capable fixture, SQL/DDL, database engine,
broker/network path, credential, runtime, persistence, M2, merge, deletion,
cleanup, force-push, or rebase was used.

## Findings

No P0, P1, or P2 finding remains within this focused exact-delta recheck.

The original P1 is **closed for the exact candidate frozen by manifest SHA-256
`2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`**.

## Unverified subsequent gates

- Repository-configured full-repository branch-coverage gate.
- Unchanged exact-head GitHub Actions Python 3.11 and 3.12 jobs.
- WO/PKL/ledger/provenance/evidence closeout reconciliation.

These remain subsequent WO-0151 closeout gates and were outside this focused
pure/static recheck.

## Verdict

**ACCEPT**

- P0: **0**
- P1: **0**
- P2: **0**
