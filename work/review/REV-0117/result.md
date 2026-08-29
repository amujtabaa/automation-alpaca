# REV-0117 — Independent Review Result

## Review binding

- Exact range: `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51..f6f64207faa3ffa57224a5755536638d981fdfcb`
- Candidate tree: `ca677a9fe854e5c3cd34646eabf9ce340894f7d7`
- Published packet HEAD: `c5a0c37691c771d08a334e387177019d51d7f107`; its only candidate-relative change is `work/review/REV-0117/request.md`.
- Mode: findings only. No SQLite connection or database was opened or created; no DDL was installed or executed; and no `tests_gated/**` test was executed.

## Retained findings

### P0-1 — The exact candidate does not reproduce its published static-green evidence

**Evidence level:** `reproduced-live`

**Locations:** `work/review/REV-0117/request.md:88-90`; `work/review/REV-0116/result.md:32`; `app/execution_core/position.py:1` (file-level Ruff format gate)

**Violated clause / failing case:** The packet says Ruff check and format check passed all changed Python files and `git diff --check` passed. Against the exact frozen range, `git diff --check c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51..f6f64207faa3ffa57224a5755536638d981fdfcb` exits 1 with `work/review/REV-0116/result.md:32: new blank line at EOF`. Ruff lint passes, but Ruff format check over the range's 16 changed Python files exits 1 with `Would reformat: app\execution_core\position.py`. This is the AGENTS.md P0 class for a published green claim that cannot be reproduced from the frozen candidate.

**Impact:** The review packet's static evidence is not bound to the exact candidate and the required static/full-governance completion evidence is red. The candidate cannot be accepted on the supplied evidence even though both defects are mechanically small.

**Disproof pass:** I reran the checks against the candidate commit rather than packet HEAD and confirmed the packet-only commit is not the cause. The scope checker separately passes, so this finding does not overstate the request's combined scope/diff-check sentence.

**Root correction:** Correct the blank EOF and Ruff formatting defect, then rerun both checks over the complete exact base-to-candidate range and publish their exact outputs. Do not describe a hand-selected five-file subset as all changed Python files.

### P1-1 — Owner loss after the post-baseline reread permits another external capability call

**Evidence level:** `reproduced-live`

**Locations:** `app/execution_core/persistence/startup.py:866`; `app/execution_core/persistence/startup.py:903`; `app/execution_core/persistence/startup.py:910`; `app/execution_core/persistence/startup.py:928`; `app/execution_core/persistence/startup.py:936`

**Violated clause / failing case:** WO-0169 requires owner evidence to be revalidated before and after every external-capability step, and CR-03 requires lease loss after database access begins to fail closed before the next capability step. After `_m2_reread_cold_context(...)` returns at line 866, startup calls the source's `is_current(...)` at line 903 before the next owner check at line 910. A pure injected counterexample that lost the lease as the reread returned produced this ordered tail: `reread-2 -> LEASE-LOST -> SOURCE-IS-CURRENT -> owner-current-12`, followed by `NON_SERVING / OWNER_LOST`. The final retained-subscription loops likewise place one owner check after a potentially multi-source `all(...)`, so loss during one source call can permit another source call before detection.

**Impact:** A process that no longer holds the single-owner lease may still invoke a source capability. Returning non-serving afterward prevents publication but does not satisfy the contract's before-the-next-capability fence or its single-owner boundary.

**Disproof pass:** The counterexample does not obtain serving state, mutation eligibility, or dispatch eligibility; the later owner check correctly refuses startup. That limits this to P1 rather than a demonstrated P0 safety escape, but it does not erase the intervening source call.

**Root correction:** Fence every datastore/source capability as owner-check, capability call, immediate owner-check, including the post-baseline reread and connection close. Check ownership around each retained subscription's currentness call rather than once around the whole loop. Add negative controls that lose ownership on reread return and during the first of multiple currentness checks and assert that no later capability is called.

### P1-2 — The held proof widens two frozen test-capability boundaries without updating their guards

**Evidence level:** `reproduced-live`

**Locations:** `tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py:8`; `tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py:25`; `tests/execution_core/test_persistence_write_capability.py:220`; `tests/execution_core/test_sqlite_boundary.py:279`

**Violated clause / failing case:** Two ordinary static boundary tests fail on the new held file. `test_setup_support_importers_have_the_frozen_direction` reports `tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py` as an extra setup-support importer. `test_sqlite_tokens_exist_only_at_justified_boundaries` reports the same file as an unallowlisted `sqlite3` token boundary. The exact two targets reproduce as failures without running the held suite or opening SQLite.

**Impact:** The new privileged test seam is not represented in the repository's explicit frozen boundary inventories, leaving ordinary governance tests red and preventing the work order's full-governance completion evidence.

**Disproof pass:** Static inspection shows the held proof routes connection creation through the central approved helper and the work order expressly authorizes this held file. I found no direct runtime SQLite escape, so this is not a P0 DDL/database-authority violation. It remains P1 because the candidate widens guarded capability surfaces without reconciling the guards.

**Root correction:** Either remove the new boundary uses or amend the work-order scope before changing the two currently out-of-scope guard tests, then explicitly add the held path to the justified setup-support and SQLite-token inventories while preserving their mutation-killing assertions.

### P1-3 — Checkpoint decoding changes an accepted exact rejection contract and leaves the ordinary suite red

**Evidence level:** `reproduced-live`

**Locations:** `app/execution_core/persistence/checkpoint_codec.py:5652-5653`; `tests/execution_core/test_position.py:430-434`

**Violated clause / failing case:** `test_m2_execution_checkpoint_component_round_trips_canonically` expects semantic-member mutants retaining the original state commitment to reach the direct-proof comparison and raise `direct proof state commitment does not match state`. The new decoder first compares the retained commitment with the reconstructed state and raises `execution state is not authentic`. The isolated ordinary test fails on that exact mismatch.

**Impact:** The implementation changes observable validation precedence without reconciling the pre-existing exact-message contract, so the ordinary execution-core suite is not green. `tests/execution_core/test_position.py` is not an activated WO-0169 path, preventing an unreviewed oracle rewrite as a nominal fix.

**Disproof pass:** Both semantic mutants are still rejected, and the retained-commitment comparison remains fail-closed; I found no authenticity bypass. This is therefore a P1 compatibility/test-contract regression, not a P0 checkpoint-integrity failure.

**Root correction:** Preserve the accepted proof-mismatch precedence in the in-scope decoder, or obtain a work-order scope amendment and explicit contract justification before changing the exact test oracle. In either case, retain mutation controls proving that raw quantity and tail-fold input both affect the state commitment.

## Evidence summary and finite disproof

- Six targeted ordinary pure/import-boundary files collected 524 tests and passed all 524.
- The three newly reported ordinary failures were independently reproduced as three isolated pure/static targets; no broad suite was started.
- Work-order scope check passed. Ruff lint passed; Ruff format check and `git diff --check` failed as described in P0-1.
- Static schema verification found `DDL_EXECUTION_AUTHORIZED_BY_AMEEN is False` and the expected DDL digest equal to the current digest. The schema file is outside the candidate diff.
- Static tracing of the held proof found assertions capable of distinguishing the C0-to-C1 advance, persisted `ACKNOWLEDGED` outcome, payload growth, first-start query, and second-start zero-query exact replay. Execution remains deliberately unverified under the packet gate.
- I attempted to disprove each retained item by separating eventual non-serving from capability ordering, authorized held-test access from frozen-boundary accounting, and semantic rejection from exact diagnostic precedence. Those checks reduced severity where appropriate but did not eliminate the findings.

Verdict: BLOCK
P0: 1
P1: 3
P2: 0
Unverified: held fresh-file SQLite proof execution (packet-prohibited); complete `tests/execution_core` run count (user supplied exactly 3 failures, all 3 failing targets independently reproduced)
