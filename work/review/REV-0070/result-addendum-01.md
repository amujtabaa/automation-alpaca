---
type: Review Result Addendum
rev_id: REV-0070
addendum: 01
reviewer_model: Codex (GPT-5)
reviewed_target: 3c85b17bc04fa587cac1995c8999155d6583006b
base: 66290630a0685facec328d4f7a53d50a2b24d068
verdict: ACCEPT
date: 2026-08-21
relationship: Independent remediation re-review of reviewer result.md; the original request and result are preserved unchanged.
---

## Verdict

**ACCEPT.** All three P1 findings in the preserved REV-0070 `result.md` are closed. The remediation
introduces no new P0, P1, or P2 finding and remains inside the authorized pure M2-I1 codec
boundary.

P0: 0
P1: 0
P2: 0

## Resolution of prior findings

| Prior finding | Status | Exact evidence | Re-review result |
| --- | --- | --- | --- |
| P1-1 — unreduced fractions accepted and silently normalized | CLOSED | `app/execution_core/durable_codec.py:208-213,248-280` enforces the relatively-prime rule after canonical component validation, including canonical zero as `0/1`. `tests/execution_core/test_durable_codec.py:580-659` covers ordinary construction, forged nested decode, noncanonical zero, and reduced controls. | Live construction and forged-decode probes rejected `2/4`, `-2/4`, `0/5`, and `15/10`. An exhaustive small-domain probe checked all 820 numerator/positive-denominator pairs against `gcd(abs(n), d) == 1` on Python 3.14 and 3.12. Weakening the decisive ratio check caused the new refusal test to fail. |
| P1-2 — frozen public API exported additional names | CLOSED | `app/execution_core/durable_codec.py:28-42,165` and `app/execution_core/profiles.py:32-45,323-436` make implementation imports/constants/helpers private and declare the exact approved `__all__` tuples. Exact-export tests are at `test_durable_codec.py:661-672` and `test_profiles.py:809-821`. | Fresh module inspection found exactly three public codec names and five public profile names, with no extras. Injecting an accidental public name into each live module caused its exact-export test to fail; removal restored the passing control. |
| P1-3 — frozen preparation inventory edited without checkpoint | CLOSED | The HEAD and accepted-base Git blob for `02-CURRENT-SOURCE-INVENTORY.md` are both `3ce9e519282837a5dda43b10e4213e3649500d23`; `git diff --exit-code` against `abcefca...` passed. The regeneration evidence remains in append-only `04-I1-ACTIVATION-CHECKPOINT.md:1-135`. | The frozen preparation file is byte-for-byte restored. The remediation record is appended to the existing post-baseline activation checkpoint and changes no authority boundary. |

## Exact review binding and scope

- Reviewed target: `3c85b17bc04fa587cac1995c8999155d6583006b`.
- Target tree: `eb283de534d4f97919a9aefa31cb73599f76f99d`.
- Target parent/re-review base: `66290630a0685facec328d4f7a53d50a2b24d068`.
- Branch: `codex/m2-i1-durable-codec-r1`; local and remote-tracking refs matched before review
  publication, and the candidate worktree was clean.
- The single remediation commit changes exactly six paths: both new source modules, both direct
  test modules, the restored `02` inventory, and append-only `04` checkpoint. The preserved
  REV-0070 `request.md` and `result.md` are unchanged.
- `git diff --check` passed. The cumulative WO-0165 scope checker passed.
- No source owner, package-root export, ADR, PKL, dependency, SQL/DDL, database, runtime, broker,
  credential, order, promotion, M2-I2+, or `master` surface changed.

## Fresh reproduced evidence

- Host CPython 3.14.5 focused value/import/codec/profile suite: `291 passed in 14.29s`.
- Supported CPython 3.12.13 full `tests/execution_core`: `1608 passed in 606.18s`; Grimp 3.15 was
  installed and the import-graph gate was included.
- Independent remediation probes passed under both CPython 3.14.5 and 3.12.13, including the
  ratio-rule and exact-export negative controls described above.
- Concrete exact-identity inventory: 29 classes; codec mapping: 29 classes; missing/extra: none.
  Total encoder entries remained 38 (six values, three composite keys, and 29 identities).
- Ruff 0.15.20 `check --no-cache .`: passed. Ruff format check: all four changed Python files
  already formatted.
- Mypy 2.2.0 `app/`: success, 89 source files.
- AI Project OS install, ledger, PKL, disposition, cumulative WO scope, and context-hygiene checks
  passed; hygiene retained eight pre-existing advisory size findings and zero violations.
- Both new source modules parsed under Python 3.11 grammar mode.

## Bottom-up disproof

- Re-ran the original `2/4` counterexample through ordinary construction and forged owner decode;
  both now fail closed before `Fraction` can normalize input.
- Tested every small numerator from -20 through 20 and denominator from 1 through 20 against the
  mathematical reduced-ratio rule; no false acceptance or refusal reproduced.
- Mutated the live decisive ratio predicate to accept every pair; the new refusal test failed for
  its intended reason.
- Injected an extra public API name into each module; both exact-export tests failed for their
  intended reason.
- Recounted every concrete identity mapping after the broad private-import rewrite; no route was
  lost or substituted, and the complete supported-Python suite remained green.
- Compared the frozen inventory by Git object identity rather than prose or a working-tree hash;
  it is the accepted-base blob.

## Unverified or intentionally not claimed

- A Python 3.11 interpreter was not available. Python 3.11 grammar parsing passed, and runtime
  behavior was reproduced on the work order's supported CPython 3.12 target.
- The broader repository suite was not run; WO-0165's bounded full execution-core suite remained
  the authorized validation boundary.
- No configured database, SQL/DDL, broker/network, credential, order, runtime, restore, soak,
  promotion, M2-I2, or merge operation was run or is represented as passing.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: Python 3.11 runtime and intentionally out-of-scope broader/runtime/database/broker checks.
