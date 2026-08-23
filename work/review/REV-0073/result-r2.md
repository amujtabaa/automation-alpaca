---
type: review-result
review_id: REV-0073
round: R2
work_order: WO-0167
review_seat: lead-fresh-independent
review_date: 2026-08-22
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
candidate_commit: 2ca0e3c35b51becda6d494ef903cd4de68839e26
candidate_tree: 13b803c1d15d929a4bc21fef241fc4fcce259507
documentation_head: 384d763a129f7c090d6e323769a6caac57179eac
verdict: BLOCK
p0_count: 5
p1_count: 2
p2_count: 0
---

# REV-0073 R2 Independent Review Result

## Verdict

**BLOCK**

Exact finding counts:

- **P0: 5**
- **P1: 2**
- **P2: 0**

The R2 implementation corrects the previously demonstrated production mechanisms, but the mandatory failure-capable gates remain bypassable in five materially distinct ways. Two production-semantic defects also remain: canonical duplicate classification is incomplete across the insert surface, and `load_current_proof` can hydrate relationally contradictory slices.

## Findings

### P0-1 — The exact-query gate does not verify bound key coordinates

- **Location:** `tests/execution_core/test_persistence_directness.py:571`
- **Related production location:** `app/execution_core/persistence/repository.py:2470`
- **Evidence level:** `reproduced-live`
- **Evidence:** A mutant changed the current-fact query parameter from `fact_head.fact_id` to `root_fill_key_id` without changing the SQL tail or query plan. It survived the round-trip, exact-query, execution-fact omission, missing-root, and stale-head tests. The fixtures assign `scope_id`, `root_fill_key_id`, and `fact_id` the same value, while the trace normalization at lines 571–575 erases literal values. In a fresh file-backed database with `root_fill_key_id=2` and `fact_id=1`, the unmutated implementation returned `FOUND`; the wrong-coordinate mutant returned `INTEGRITY_FAILURE`.
- **Impact:** A hydration query may use the wrong exact key while preserving the expected indexed SQL shape. The mandatory directness test therefore cannot fail for a class of incorrect proof hydration.
- **Resolution:** The gate must verify the ordered bound-coordinate values or use deliberately disjoint sentinel identifiers, and it must kill a wrong-bound-key mutant.

### P0-2 — Quoted and schema-qualified hidden domain scans evade the directness gate

- **Location:** `tests/execution_core/test_persistence_directness.py:562`
- **Evidence level:** `reproduced-live`
- **Evidence:** Mutants added hidden proof-path queries using both `FROM "execution_fact"` and `FROM main.execution_fact`. Each survived `test_total_proof_uses_only_fixed_direct_key_queries_under_history_stress`. The filter at lines 562–567 recognizes only literal `FROM {table}` fragments and excludes both quoted and schema-qualified references from the captured domain statements.
- **Impact:** A full or explanatory-history domain scan can ship while the mandatory fixed direct-key/O(1) gate remains green.
- **Resolution:** Domain-query accounting must recognize SQLite quoting and schema qualification and must fail on every unexpected proof-domain query. The quoted and schema-qualified scan mutants must be killed.

### P0-3 — Optional-member tests do not kill acceptance-evidence integrity swallowing

- **Location:** `tests/execution_core/test_persistence_directness.py:679`
- **Related production location:** `app/execution_core/persistence/repository.py:2585`
- **Evidence level:** `reproduced-live`
- **Evidence:** A mutant converted an `acceptance_evidence` `INTEGRITY_FAILURE` into optional absence while retaining the normal `ABSENT` behavior. It survived both the acceptance-evidence omission test and the exact-query test. With a fresh file-backed SQLite database and an authenticated `sqlite3.DatabaseError` injected only for the acceptance-evidence read, the mutant returned a partial `FOUND` proof with `acceptance_evidence=None`. The unmutated implementation correctly returned `INTEGRITY_FAILURE` with no record.
- **Impact:** The acceptance-evidence fail-closed behavior can regress to partial proof hydration without failing the R2 gate.
- **Resolution:** Optional-member coverage must distinguish `ABSENT` from authenticated SQLite read/decode failure for every optional proof member. An acceptance-evidence integrity-swallowing mutant must fail.

### P0-4 — Exact-scalar tests omit Python scalar subclasses

- **Location:** `tests/execution_core/test_persistence_repository.py:1033`
- **Additional location:** `tests/execution_core/test_persistence_repository.py:1069`
- **Related production locations:** `app/execution_core/persistence/repository.py:215`, `app/execution_core/persistence/repository.py:227`, `app/execution_core/persistence/repository.py:245`
- **Evidence level:** `reproduced-live`
- **Evidence:** The current implementation correctly rejects `IntEnum`, a custom `int` subclass, and a custom `str` subclass as `INTEGRITY_FAILURE`. I weakened `_exact_int`, `_exact_text`, and `_query_parameters` to accept subclasses while continuing to reject the aliases presently parameterized by the tests (`True`, `1.0`, `"1"`, `"01"`, `"+1"`, and `"1.0"`). Both existing alias test families survived, while the three subclass values hydrated as `FOUND`.
- **Impact:** A future refactor can reintroduce non-exact Python scalar coordinates that SQLite aliases to canonical integer or text keys, while all mandatory scalar tests remain green.
- **Resolution:** The gate must include `IntEnum`, custom `int` subclasses, and custom `str` subclasses across the applicable loader/query surfaces and must kill a subclass-accepting mutant.

### P0-5 — Transaction-ownership gates miss indirect commit calls and dynamically assembled COMMIT SQL

- **Location:** `tests/execution_core/test_persistence_repository.py:764`
- **Additional location:** `tests/execution_core/test_persistence_repository.py:1203`
- **Evidence level:** `reproduced-live` for gate survival; `specialist-reproduced` for completed post-rollback impact
- **Evidence:** Two proof-path mutants survived the static transaction scan, the existing runtime no-commit test, and the proof directness test:
  1. an aliased commit method obtained through a dynamically assembled attribute name; and
  2. `connection.execute` receiving dynamically assembled `COMMIT` SQL.

  The AST check detects only direct `.commit`/`.rollback`/`.executescript` attributes and complete forbidden string constants. The runtime test at lines 1203–1214 exercises only `_foundation`; it does not cover `load_current_proof` or every exported repository operation. The specialist seat completed the caller-rollback reproduction and observed the committed state survive rollback.
- **Impact:** Repository code can take transaction ownership from its caller while all R2 transaction gates remain green.
- **Resolution:** Runtime transaction-ownership evidence must cover every public repository operation, including proof hydration, and detect both method and SQL transaction controls independent of spelling or assembly. Both indirect-commit mutants must be killed.

### P1-1 — Canonical duplicate classification is incomplete across the insert surface

- **Location:** `app/execution_core/persistence/repository.py:102`
- **Representative callers:** `app/execution_core/persistence/repository.py:513`, `app/execution_core/persistence/repository.py:1054`, `app/execution_core/persistence/repository.py:2048`
- **Inadequate test location:** `tests/execution_core/test_persistence_repository.py:920`
- **Evidence level:** `reproduced-live`, `source-confirmed`, and independently reconciled with specialist evidence
- **Evidence:** Only two of nineteen insert-owned record families provide a canonical conflict probe to `_insert`: execution facts and dispatch claims. In a fresh file-backed matrix, canonical mismatches in fourteen unprobed families returned `CONFLICT`, including execution profile, market profile, application generation, scope, acquisition generation, kernel checkpoint, root fill, venue owner, acquisition-root route, acceptance set, acceptance evidence, market stream, market cursor, and protection authority. Three other families happened to return `INTEGRITY_FAILURE` only because of current trigger ordering. The specialist seat additionally reproduced contradictory fact-identity collision paths returning `CONFLICT`, demonstrating that even a probed family is not necessarily covered across every unique identity.
- **Impact:** Contradictory retained authority can be reported as retryable contention instead of durable integrity failure. The result depends on trigger ordering and which uniqueness constraint fires rather than canonical record equality.
- **Resolution:** Every insert family and every colliding unique identity must distinguish an exact canonical duplicate from a canonical mismatch. Exact equality may return `CONFLICT`; any mismatched canonical field must return `INTEGRITY_FAILURE`. The test matrix must cover mismatches for all nineteen families and alternate unique identities.

### P1-2 — `load_current_proof` does not validate all canonical relationships among hydrated records

- **Location:** `app/execution_core/persistence/repository.py:2411`
- **Additional locations:** `app/execution_core/persistence/repository.py:2478`, `app/execution_core/persistence/repository.py:2514`, `app/execution_core/persistence/repository.py:2558`, `app/execution_core/persistence/repository.py:2595`
- **Evidence level:** `reproduced-live`
- **Evidence:** Using a fresh file-backed SQLite database and a connection wrapper that delegated the real schema guard and reads but altered one decoded scalar coordinate, `load_current_proof` returned `FOUND` for nine contradictory slices:
  - a partially populated protection active-stream tuple;
  - protection source-profile mismatch;
  - market-cursor acquisition-mandate mismatch;
  - venue-effect mandate mismatch;
  - current execution-fact scope mismatch;
  - current execution-fact application-generation mismatch;
  - current execution-fact execution-profile mismatch;
  - venue-owner execution-profile mismatch; and
  - acceptance-set effect mismatch.
- **Impact:** The supposedly total, internally consistent current proof can contain records that disagree about scope, application generation, execution profile, mandate, effect identity, or active-stream authority.
- **Resolution:** Proof hydration must compare every canonical relationship represented by the loaded rows, enforce all-or-none grouped coordinates such as the active-stream tuple, and return `INTEGRITY_FAILURE` with no partial record for every contradiction.

## Prior-finding reconciliation

| Prior negative evidence | R2 reconciliation |
|---|---|
| Indexed checkpoint-range proof query | **Resolved in the current implementation and tested mutant.** The indexed-range mutant was killed. P0-2 shows that equivalent hidden queries remain undetectable when quoted or schema-qualified. |
| Keyed execution-fact history fold | **Resolved in the current implementation and tested mutant.** The keyed-history-fold mutant was killed. P0-1 shows that the retained exact query can still bind the wrong coordinate without failing tests. |
| Optional dispatch-claim integrity swallowing | **Resolved in production.** Fresh authenticated SQLite failure injection returned `INTEGRITY_FAILURE`. P0-3 identifies the same unguarded test class for acceptance evidence. |
| Primitive numeric coercion and text/non-text aliases | **Resolved in production for the prior aliases.** The coercing-integer mutant was killed and the listed primitive aliases are rejected. P0-4 shows that subclass aliases remain absent from the failure-capable gate. |
| Conflict probe executed only under selected failure text | **Resolved for configured probes.** The prior gating mutant was killed. P1-1 remains because only two insert families configure probes and alternate unique identities are incomplete. |
| Literal SQL `END` escaped the transaction scan | **Resolved for literal `END`.** The literal mutant was killed. P0-5 shows that indirect commit methods and dynamically assembled SQL remain outside the gate. |
| Contradictory immutable authority during advances | **Resolved in the reviewed R2 surface.** Focused advance tests passed. |
| Execution-fact alternate-root/next-ordinal conflict handling | **Resolved for the focused prior case.** The direct focused test passed. This does not disprove the broader collision-classification defect in P1-1. |
| Partial current-proof member failures | **Partially resolved.** Fresh failure injection across eleven proof members returned `INTEGRITY_FAILURE` in current code, but P0-3 demonstrates a surviving acceptance-evidence regression and P1-2 demonstrates omitted relational comparisons. |

## WO-0167 and mandatory-lens disposition

| Requirement or lens | Result |
|---|---|
| Exact candidate identity and semantic surface | **Verified.** Base, candidate commit, candidate tree, documentation-only HEAD, ancestry, and path surface matched the packet. |
| Complete repository/record export surface | **Verified.** The implementation exposes 56 repository operations and 23 record models pinned by tests. |
| Schema authority and no DDL change | **Verified.** Schema blob is unchanged from base and the fresh DDL digest was `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`. |
| Schema guard before repository work | **Verified for reviewed code and normal gates.** |
| Exact scalar decoding and query coordinates | **Production implementation passes prior aliases; gate fails P0-1 and P0-4.** |
| Fixed direct-key current proof | **Current visible queries pass; gate fails P0-1 and P0-2.** |
| Total fail-closed proof hydration | **Fails P0-3 and P1-2.** |
| Exact duplicate versus canonical mismatch semantics | **Fails P1-1.** |
| Caller-owned transactions | **Current source contains no observed transaction control; mandatory gate fails P0-5.** |
| SQLite-only persistence boundary | **Verified by source and import checks.** |
| Architecture/import contracts | **Verified by six kept import-linter contracts and a cache-disabled Grimp equivalent.** |
| Human-gated surfaces and safety invariants | **No schema migration, event-truth change, live trading, UI-to-broker call, or other listed gated surface was introduced.** |
| Scope control | **Verified.** Implementation/test blobs at documentation HEAD match the candidate, and candidate-to-HEAD changes are documentation/governance only. |

## Fresh evidence

### Identity and surface

- Worktree branch matched `codex/m2-i3-sqlite-repository-hydration-r1`.
- Candidate commit matched `2ca0e3c35b51becda6d494ef903cd4de68839e26`.
- Candidate tree matched `13b803c1d15d929a4bc21fef241fc4fcce259507`.
- Accepted base was an ancestor of the candidate.
- Documentation-only HEAD was `384d763a129f7c090d6e323769a6caac57179eac`.
- The four implementation/test blobs were identical at candidate and documentation HEAD.
- No repository file was intentionally edited or created during this review.

### Normal gates

- Focused repository/directness tests: **61 passed**.
- Seven-file integration selection: **433 passed**; one Grimp test failed only because it attempted to create `.grimp_cache` in the read-only worktree. The same graph assertion passed with Grimp caching disabled.
- Full `tests/execution_core` run with that single cache-writing Grimp test deselected: **exit 0, reached 100%**.
- SQLite half of `tests/r2_conformance_oracle.py`: **30 passed** using fresh file-backed `tmp_path` databases.
- Ruff check with cache disabled: **passed**.
- Ruff format check for the four changed Python files: **passed**.
- Mypy with an external cache: **passed, 93 source files**.
- Import linter with cache disabled: **6 kept, 0 broken**.
- Installation, version, ledger, PKL, disposition, exact-scope, and `git diff --check` gates: **passed**.

### Fresh killed mutants and failure matrices

- Indexed checkpoint-range mutant: **killed**.
- Keyed execution-fact-history fold mutant: **killed**.
- Prior optional-claim swallowing mutant: **killed**.
- Coercing-integer mutant: **killed**.
- Conditional conflict-probe mutant: **killed**.
- Literal SQL `END` transaction mutant: **killed**.
- Authenticated SQLite failure injection across market stream, cursor, root, route, fact head, fact, effect, claim, owner, acceptance set, acceptance evidence, and closure: current implementation returned `INTEGRITY_FAILURE` with no record in every case.
- Primitive numeric aliases `True`, `1.0`, `"1"`, `"01"`, `"+1"`, and `"1.0"` were rejected across the nineteen numeric loader/proof entry points.
- The five plain-text loader surfaces rejected non-text integer aliases.

### Fresh surviving mutants

- Wrong-bound execution-fact key: **survived**.
- Hidden quoted domain query: **survived**.
- Hidden schema-qualified domain query: **survived**.
- Acceptance-evidence integrity swallowing: **survived**.
- `IntEnum`/`int`-subclass/`str`-subclass acceptance: **survived**.
- Indirect aliased commit method: **survived**.
- Dynamically assembled `COMMIT` SQL: **survived**.

## Disproof pass

- **Duplicate semantics:** I attempted to disprove P1-1 by relying on schema triggers to classify contradictions as integrity failures. Three families did so under current trigger ordering, but fourteen returned `CONFLICT`, and source inspection confirmed that only two families provide canonical probes. The finding stands.
- **Aggregate consistency:** Foreign keys prevent several contradictions through ordinary accepted inserts. That does not discharge the repository’s fail-closed hydration contract: the repository accepts delegated SQLite connection-protocol reads, already defends against malformed decoded rows, and returned `FOUND` for nine exact-typed relational contradictions. The finding stands.
- **Directness findings:** The reviewed production source currently uses the correct fact identifier and contains no observed hidden domain scan. P0-1 and P0-2 are specifically failure-capability defects in mandatory acceptance evidence, not allegations that those two mutants are present in the candidate.
- **Optional-member finding:** Current acceptance-evidence handling correctly propagates the injected SQLite failure. P0-3 stands because the required omission test cannot distinguish absence from integrity failure.
- **Subclass finding:** Current exact-type guards reject all three tested subclasses. P0-4 stands because a subclass-accepting regression survived the mandatory alias suites.
- **Transaction finding:** No transaction-control call was found in the candidate source. P0-5 stands because both independent mutants survived the static, runtime, and directness gates, and the specialist seat reproduced lost caller rollback ownership.

## Unverified items and review boundaries

- The in-memory half of the 61-case R2 conformance oracle was not executed because this review expressly prohibited configured or in-memory databases. Thirty SQLite/file-backed cases were executed.
- The exact Grimp test was not executable unchanged under the read-only worktree because it writes `.grimp_cache`; its cache-disabled semantic equivalent passed.
- The full-suite terminal stream reached 100% with exit code 0, but its final numerical pytest summary was not retained in the terminal chunk.
- Python 3.11 was not separately exercised; fresh evidence used CPython 3.12.13.
- External CI state was not verified.
- I independently confirmed that both transaction mutants survive the relevant gates. The completed post-rollback persistence observation is attributed to the specialist seat because the lead-seat duplicate runtime observation was stopped before its final state assertion.
- No configured durable database, network service, broker, or in-memory database was used.

## Final counts and disposition

- **P0: 5**
- **P1: 2**
- **P2: 0**
- **Verdict: BLOCK**

The R2 implementation must not be accepted on the present evidence because five mandatory tests remain non-failure-capable and two production-semantic requirements remain unsatisfied.
