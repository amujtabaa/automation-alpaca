# REV-0117 — Independent Correction Review Result r1

## Exact binding and review limits

- Published packet HEAD: `4f8823afdc22784d6ebec56ff90860f311630927`, tree `1f5d37d6ad6fa8405d048e8052e533bddf2b2d07`.
- Correction candidate: `112d95115f2997ca613238b63eb161a12fbfc791`, tree `137f7a7bd8d3bc4838cff905754c3394af07fef1`; its parent is the stated remediation base `ca6e86cf53ea47f047db22f27a8dc81bd73e1029`.
- Reviewed correction range: `ca6e86cf53ea47f047db22f27a8dc81bd73e1029..112d95115f2997ca613238b63eb161a12fbfc791` (8 files, 312 insertions, 40 deletions). The published packet-head change after the candidate is only `work/review/REV-0117/request-r1.md`; application, test, and active-work-order contents are identical.
- Mode: findings only and correction only. No SQLite/database was opened or created, no DDL was installed or executed, and no `tests_gated/**` test was executed.

## Correction findings

No P0, P1, or P2 findings retained.

### P0-1 closed — complete formatting and precise whitespace evidence

- `ruff format --check` over all 19 Python paths in `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51..112d95115f2997ca613238b63eb161a12fbfc791` reported `19 files already formatted`.
- `git diff --check ca6e86cf..112d951` is clean. The complete predecessor-to-candidate whitespace diagnostic reports exactly `work/review/REV-0116/result.md:32: new blank line at EOF`; excluding exactly that immutable reviewer-owned file is clean.
- `work/review/REV-0117/disposition.md` explicitly retracts the old unqualified full-range green claim. No author-owned historical whitespace was silently excluded or rewritten.

### P1-1 closed — owner fences cover each named capability boundary

- `app/execution_core/persistence/startup.py:933-961` checks the owner immediately before and after the post-baseline reread.
- `startup.py:419-440` applies the owner check, one source-currentness call, and immediate owner check to each retained subscription independently. The final two retained-currentness passes use that helper at `1022-1040`.
- `startup.py:999-1021` checks ownership before connection close and immediately after it before any later source call or `SERVING` publication.
- The three targeted negative controls are concrete and failure-capable: lease loss on the second reread leaves the source event sequence at subscribe/fence/baseline (`tests/execution_core/test_persistence_cold_recovery.py:680-716`); loss after the first retained-source call prevents the second (`719-747`); and loss in `close()` returns `OWNER_LOST` rather than serving (`750-777`). The focused ordinary file passed: 42 passed.

### P1-2 closed — scope and both frozen boundary inventories agree

- The correction adds exactly the three ordinary guard-test paths to both authoritative allowed-path inventories in `work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md:30-52,341-363`.
- The frozen setup-importer and SQLite-token inventories admit only `tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py` as the new held-proof boundary, preserving all existing entries and their mutation canaries (`tests/execution_core/test_persistence_write_capability.py:209-227`; `tests/execution_core/test_sqlite_boundary.py:28-54,280-283`). Both targeted ordinary controls passed.

### P1-3 closed — first and second authenticity layers remain distinct

- The production decoder recomputes the decoded state commitment and rejects a mismatch before the direct-proof seam (`app/execution_core/persistence/checkpoint_codec.py:5648-5666`); the correction did not weaken production validation.
- The ordinary oracle now correctly expects `execution state is not authentic` for raw-quantity, tail-fold-input, and integrity-order semantic-member mutants (`tests/execution_core/test_position.py:418-457`). The separate foreign-proof case still pins `direct proof state commitment does not match state` (`400-407`). Its targeted ordinary test passed.

## Disproof pass and executed evidence

- I attempted to retain each original finding by following its counterexample: removing the relevant reread, per-source, or post-close owner check would respectively introduce a source-currentness event, permit the second retained-source call, or return serving; the three controls distinguish those outcomes.
- I checked whether the boundary correction merely relaxed a detector: the inventories remain exact equality checks with their existing canaries, and the scope amendment names the guard tests. The added held proof is the only new inventory member.
- I checked whether P1-3 merely changed wording: the decoder's existing first-layer commitment comparison produces the asserted refusal for each of the three locally shaped semantic mutants, while a foreign proof still reaches the separate direct-proof mismatch.
- Executed ordinary, no-I/O checks: the cold-recovery control file (42 passed); checkpoint authenticity oracle, setup-importer inventory, and SQLite-token inventory (3 passed). No gated test or database-related command was run.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: complete 2259-test ordinary suite; held SQLite proof execution (packet-prohibited)
