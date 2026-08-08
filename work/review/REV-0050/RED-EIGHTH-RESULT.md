# WO-0148 eighth RED exact-commit independent review

Exact candidate reviewed: `7beda3f61e4d44f035143e883d7efa35a424f661`
Activation base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## P1 findings

### P1-1 — Restart replay can still advance retained evidence state

**Location:** `tests/execution_core/test_protection.py:6806`

**Authority:** ADR-021 requires an exact source-occurrence replay, including one redelivered after
restart with a new local receive time, to be an evidence no-op. The accepted packet domain
specification states the same rule at
`work/queue/ARCH-RESET-2026-07/03-domain-specification.md:182`, and WO-0148 clause 11 requires
replay/restart delivery to be an evidence no-op.

**Concrete disproof:** The test redelivers `duplicate-bid` with only `evaluation_time` changed from
105 to 109, but its assertions at lines 6825-6828 check only that policy remains `FLOOR_ONLY` and
that no goal is emitted. They do not require `ProtectionDisposition.EXACT_REPLAY`, byte-for-byte
unchanged state, or an unchanged commitment. A reducer may therefore accept the replay, advance
its retained evaluation-time watermark/commitment to 109, and still pass this test. A subsequent
distinct below-trigger occurrence with source sequence 8, source time 106, and evaluation time 107
is eligible relative to the original 105 watermark and would complete the two-bid branch, but the
replay-mutated watermark rejects it as a regression. The replay has acquired negative evidence
authority despite every present assertion passing.

**What resolves it:** Require the changed-delivery-context replay to return exact
`EXACT_REPLAY`, preserve the complete prior state and commitment, and emit neither goal nor alert.
Continue the history with a distinct otherwise-eligible occurrence whose evaluation time lies
between the original and replay delivery times; it must still be accepted and complete the
corroboration branch. This is the failure-capable mutant control for replay watermark advancement.

### P1-2 — The claimed no-I/O gate permits direct runtime output

**Location:** `tests/execution_core/test_import_boundary.py:57`

**Authority:** ADR-020 at line 30 requires the pure reducer to perform no I/O or logging. WO-0148
declares this slice pure and deterministic and specifically requires the import/public-surface pins
to fail if protection gains I/O (`work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:201`).

**Concrete disproof:** `_FORBIDDEN_CALL_NAMES` rejects `__import__`, `compile`, `eval`, `exec`, and
`open`, but not `print`. The call scanner at lines 386-404 therefore accepts a direct
`print("protection transition")` in any public reducer or private helper. No import is needed; the
public-entrypoint provenance oracle accepts source and bytecode that both contain the call; the
behavioral helper invokes each reducer twice but never asserts that stdout/stderr stayed untouched.
The future protection implementation can consequently perform observable runtime I/O while every
RED boundary assertion passes. `sys.stdout.write` is an equivalent bypass because `sys` is allowed
by the general stdlib rule and `write` is not a forbidden call attribute.

**What resolves it:** Make the protection-module purity gate allowlist-based, or otherwise reject
direct output builtins and `sys` stream capabilities as both imports and calls. Add synthetic
failure controls for at least `print(...)` and `sys.stdout.write(...)`, plus a runtime stdout/stderr
tripwire around each public entry point, so this no-I/O claim can fail independently of production
behavior assertions.

## Reproduced evidence

- `HEAD` is the exact requested candidate; both candidate and activation-base objects exist.
- Before this reviewer artifact was created, there were no tracked or staged worktree changes.
  `RED-EIGHTH-REQUEST.md` and retained older evidence were untracked and preserved.
- The activation-base diff changes only six allowed-path files: the three RED test files, the
  active WO, and two non-authoritative REV-0050 comparator documents. It adds no production module,
  deletion, broker/runtime/persistence surface, or human-gated effect.
- Complete focused collection reproduced 282 tests: 265 deterministic protection, four stateful,
  and 13 import-boundary tests.
- Exact RED execution reproduced `227 failed, 55 passed`: `test_protection.py` was 220/45,
  `test_protection_stateful.py` was 3/1, and `test_import_boundary.py` was 4/9. The 224 failures
  caused directly by the deliberately absent protection module and the three remaining required
  inventory/export deltas are the expected RED classes; no oracle helper failed.
- Eight selected provenance, lifecycle, no-access, leaf-walker, and bounded-map meta-oracles passed.
- Ruff check and format-check passed for all three RED files. Python 3.11 grammar parsing passed,
  `git diff --check` passed, the activation-base scope checker reported `SCOPE CHECK PASSED`, and
  all three accepted ADR digests matched the ratification index.
- The predecessor execution-core corpus collected 698 tests and passed all 698 in 191.4 seconds
  with the three deliberate RED files excluded.

## Unverified items

- No Python 3.11 interpreter is installed locally; only its grammar target was checked. Actual
  Python 3.11 execution remains an exact-head CI obligation.
- Production `app/execution_core/protection.py` is deliberately absent. Domain behavior and the
  required production mutation-kill/restoration evidence therefore cannot yet be executed.
- Network/CI state, broker behavior, credentials, database/persistence behavior, and runtime wiring
  were not exercised, consistent with the review boundary.
- Repository-wide tests outside the 698-test execution-core predecessor corpus were not run; they
  are later implementation-gate evidence and include surfaces prohibited for this RED review.

## Verdict

**BLOCK**

P0: **0**
P1: **2**

Two unresolved P1 test-contract gaps remain. Production implementation must remain barred until
both are repaired at the owning oracle, the affected gates are rerun, and a fresh immutable RED
candidate receives independent zero-P0/P1 acceptance. This verdict governs only permission to
begin WO-0148 production implementation; it does not close the work order or replace the later
implementation review.
