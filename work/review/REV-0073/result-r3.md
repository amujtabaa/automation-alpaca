---
type: review-result
review_id: REV-0073
round: R3
work_order: WO-0167
review_seat: authoritative-independent-r3
review_date: 2026-08-22
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
blocked_predecessor: 2ca0e3c35b51becda6d494ef903cd4de68839e26
candidate_commit: 4ed0b4e0378a91940ca392dc40902959dc41ecff
candidate_tree: 0b5c8104c726ce009b6e82b961dc4c9d78a61355
documentation_head: b1ef4ff30831f46d49e1d7ca4fffabda1c612bca
verdict: BLOCK
p0_count: 4
p1_count: 0
p2_count: 0
---

# REV-0073 R3 — WO-0167 authoritative independent review result

## Candidate identity

The reviewed implementation is exact commit
`4ed0b4e0378a91940ca392dc40902959dc41ecff`, tree
`0b5c8104c726ce009b6e82b961dc4c9d78a61355`, over accepted base
`0a7b5ae324c34be488da24478f95e2658a1bb894` and blocked R2 predecessor
`2ca0e3c35b51becda6d494ef903cd4de68839e26`. Later head
`b1ef4ff30831f46d49e1d7ca4fffabda1c612bca` changes only WO, ledger, disposition, and R3 request
documentation. The accepted schema blob remains
`5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`; fresh DDL SHA-256 was
`2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`.

## Findings

### P0-1 — The effect-proof bound-value gate aliases distinct authority keys

- **Location:** `tests/execution_core/test_persistence_directness.py:36`, `tests/execution_core/test_persistence_directness.py:105`, `tests/execution_core/test_persistence_directness.py:739`; related production query `app/execution_core/persistence/repository.py:2736`
- **Requirement:** `AGENTS.md` classifies a test that cannot fail for its claimed defect as P0. WO-0167 FR-3/FR-5 and AC-3 plus the R3 request require exact ordered proof-query values; one wrong key must fail.
- **Evidence level:** `reproduced-live`
- **Evidence:** On an exported exact-candidate snapshot, replacing the acceptance-evidence bind `(acceptance.acceptance_set_id,)` with the wrong `(effect.effect_id,)` left the complete focused repository/directness gate green: 177 tests passed using fresh file-backed `tmp_path` SQLite. The effect fixture constructs evidence with `evidence_id == acceptance_set_id == effect_id`, and the seeded acceptance row is `AcceptanceSetRecord(2, 2)`. The new disjoint-key test separates only root and execution-fact identifiers, so it cannot distinguish this effect-path substitution.
- **Impact:** A wrong exact proof key can ship while the mandatory bound-value gate remains green, defeating the total direct-proof claim when acceptance-set and effect identities differ.
- **Resolution:** Seed deliberately distinct effect, acceptance-set, and evidence identifiers; assert the complete ordered bound-value vector for every root/effect proof query; and require this exact substitution mutant to fail.

### P0-2 — Hidden-domain accounting misses valid parenthesized and attached-schema reads

- **Location:** `tests/execution_core/test_persistence_directness.py:584`, `tests/execution_core/test_persistence_directness.py:603`
- **Requirement:** WO-0167 FR-5/AC-3 and the R3 request require every additional proof-domain read, including quoted and schema-qualified forms, to fail the exact query-count/shape gate.
- **Evidence level:** `reproduced-live`
- **Evidence:** Adding `SELECT count(*) FROM (execution_fact)` to `load_current_proof` left all 177 focused tests green on fresh file-backed SQLite. Separately, a fresh accepted main database with a fresh attached `aux` database passed `verify_schema_connection` (`guard=1`), and `SELECT count(*) FROM aux.execution_fact` executed, while `_statement_domain_tables(...)` returned no domain table. The helper strips only `main`/`temp` qualification and recognizes only a table name immediately following `FROM` or `JOIN`.
- **Impact:** Parenthesized, comma-joined, or custom attached-schema proof-history reads can evade domain-query accounting, so an extra scan can ship with unchanged expected counts and plans.
- **Resolution:** Enforce the exact ordered production statement set with SQLite-aware parsing or authorizer/trace accounting that resolves every table reference and arbitrary schema qualification. Add parenthesized, comma-join, and custom attached-schema mutants.

### P0-3 — Transaction ownership gates miss comment-prefixed dynamic SQL on real connections

- **Location:** `tests/execution_core/test_persistence_repository.py:777`, `tests/execution_core/test_persistence_directness.py:263`, `tests/execution_core/test_persistence_directness.py:285`
- **Requirement:** WO-0167 FR-1/FR-6/EC-3 and the R3 request require every public operation to leave transaction ownership with its caller; indirect methods and dynamically assembled transaction SQL must fail.
- **Evidence level:** `reproduced-live`
- **Evidence:** This proof-path mutant left all 177 focused tests green:

  ```python
  if getattr(connection, "in_transaction", False):
      connection.execute("-- transaction\n" + "".join(("COM", "MIT")))
  ```

  The static constant folder does not recognize it. The runtime proxy does not transparently expose `in_transaction`, so the branch is skipped there, while its SQL tokenizer would see `--` rather than `COMMIT`. On a raw fresh file-backed connection, a rollback probe observed `in_transaction=True` before the operation, `False` afterward, and one application-generation row still retained after caller rollback.
- **Impact:** Repository code can commit caller-owned work while every R3 transaction gate remains green.
- **Resolution:** Exercise every public operation through a transparent connection proxy or raw connection inside a caller transaction, then rollback and verify operation-specific writes disappear. Normalize leading SQL comments and verify transaction/savepoint state independently of transaction spelling.

### P0-4 — The active-stream totality test targets a redundantly checked coordinate

- **Location:** `tests/execution_core/test_persistence_directness.py:1034`, `tests/execution_core/test_persistence_directness.py:1045`; related production rule `app/execution_core/persistence/repository.py:2502`
- **Requirement:** WO-0167 FR-3/AC-1 and the R3 request require the total proof to reject every partial active-stream coordinate tuple, with a failure-capable test for the recorded contradiction.
- **Evidence level:** `reproduced-live`
- **Evidence:** Disabling the six-coordinate all-or-none check left the full 177-test gate green. The existing case clears `active_acquisition_generation_id`, but another comparison against the live acquisition generation already rejects that value, so the test does not depend on the owning all-or-none rule. Under the disabled-rule mutant, clearing `active_stream_generation_id` instead returned `FOUND`, with `market_stream_authority=None` while the other active-stream coordinates remained populated.
- **Impact:** The owning totality rule can be removed while its named R3 gate remains green; a different partial tuple then escapes as a supposedly total proof.
- **Resolution:** Independently clear each of the six active-stream coordinates, require all six partial tuples to fail, retain an all-null positive case, and require a removed-all-or-none-rule mutant to fail.

## Independent-seat reconciliation

Goodall's two P0 reports overlap the finding classes above and are treated as independent
corroboration, not additional owning defects. They therefore do not increase the count beyond four.
The closed seat did not deposit a readable result artifact, so no Goodall-only factual assertion is
used as authority in this result.

## Disproof pass

The unmodified exact candidate passed the 177 focused repository/directness tests on fresh
file-backed `tmp_path` SQLite. Current production uses the correct acceptance-set key, contains the
active-stream all-or-none check, contains no observed transaction control, and contains no observed
hidden proof-domain scan. The four findings therefore remain scoped to mandatory failure-capability
defects, not allegations that those mutants are present in the candidate.

Counterevidence was also applied: acceptance-evidence read/decode swallowing, custom
`int`/`IntEnum`/`str` aliases, a direct dynamically aliased `commit`, the direct-conflict probe
bypass, and eight other recorded cross-row comparison removals failed their intended selected
tests. Those mechanisms were removed as findings. The four surviving stronger mutants above could
not be disproved and remain blocking under the repository's P0 rule.

## Unverified items

- The claimed full 1,867-test `tests/execution_core` run was not rerun.
- The remaining 373-case integration selection produced 372 passes in the read-only worktree; its sole failure was Grimp attempting to write `.grimp_cache`. The exact graph assertion passed from the writable exported snapshot.
- The SQLite/file-backed half of `tests/r2_conformance_oracle.py` passed 30 cases. The in-memory half was not executed under the explicit database boundary.
- Python 3.11, Ruff, mypy, the complete governance suite, external CI, and external review state were not rerun.
- No configured/existing database, in-memory database, network service, broker, credentials, order, migration, runtime composition, or DDL change was used.

## Final counts and disposition

- **P0: 4**
- **P1: 0**
- **P2: 0**
- **Verdict: BLOCK**

WO-0167 cannot clear review at this candidate because four mandatory R3 controls remain
non-failure-capable. This result does not activate M2-I4 or authorize merge.
