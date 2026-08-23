---
type: review-result
review_id: REV-0073
round: R4
work_order: WO-0167
review_seat: authoritative-fresh-independent-r4
review_date: 2026-08-22
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
r3_production_commit: 4ed0b4e0378a91940ca392dc40902959dc41ecff
blocked_predecessor: 17793433456b9ec9ae22fc4b59e8bf8b49ef5251
candidate_commit: 0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a
candidate_tree: 8bf5929e31f31ec970165611c333a2fc43b576f0
documentation_head: 6b2da7ce807ca93f0310e18fb1524f0edfcf2388
verdict: BLOCK
p0_count: 1
p1_count: 0
p2_count: 0
---

# REV-0073 R4 — WO-0167 authoritative independent review result

## Candidate identity and scope

The reviewed candidate is exact commit
`0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a`, tree
`8bf5929e31f31ec970165611c333a2fc43b576f0`, over accepted base
`0a7b5ae324c34be488da24478f95e2658a1bb894`. Accepted-base ancestry and
candidate-to-documentation-head ancestry were reproduced. Later head
`6b2da7ce807ca93f0310e18fb1524f0edfcf2388` changes only the WO, ledger,
REV-0073 disposition, and R4 request. The four production/test blobs and the accepted schema blob
at that head are identical to the candidate; schema blob
`5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd` is also identical to the accepted base.

R4 changes only `tests/execution_core/test_persistence_repository.py` and
`tests/execution_core/test_persistence_directness.py`. The full accepted-base-to-candidate
repository, records, and focused-test surface was inspected. No new production behavior, safety
invariant violation, human-gated surface, or out-of-scope runtime/DDL implementation was found.

## Finding

### P0-1 — A capability-gated raw cursor bypasses the exact proof-call recorder

- **Location:** `tests/execution_core/test_persistence_directness.py:619`,
  `tests/execution_core/test_persistence_directness.py:642`
- **Requirement:** `AGENTS.md` makes a completion test that cannot fail for its named defect P0.
  WO-0167 FR-5/AC-3 and REV-0073 R4 mandatory lens 2 require every prepared proof SQL call and
  bound parameter, after the exact schema-guard prefix, to appear in one ordered allowlist; every
  additional call must fail.
- **Evidence level:** `reproduced-live`
- **Evidence:** An in-process production mutant added this branch immediately after the schema
  guard without changing any repository file:

  ```python
  if hasattr(connection, "cursor"):
      connection.cursor().execute(
          "SELECT count(*) FROM execution_fact"
      ).fetchone()
  ```

  On a raw fresh file-backed SQLite connection, trace evidence observed exactly one hidden
  `execution_fact` read and the proof still returned `FOUND`. The complete focused
  repository/directness gate nevertheless remained green: **186 passed in 6.83s**. The bypass
  survives because `_ProofRecordingConnection` exposes only `execute`; it has no `cursor`
  capability, so the production branch is skipped only under the recorder while it runs on the
  real accepted connection.
- **Impact:** Production proof hydration can perform an unbounded or explanatory-history read on a
  real connection while the mandatory exact-call, bound-value, count, and plan gate records a
  different capability surface and remains green. The R4 evidence therefore does not establish
  FR-5/AC-3 for all accepted connection execution paths.
- **Resolution:** Make proof instrumentation capability-transparent and mediate every statement
  preparation path, including `cursor().execute` and related cursor execution methods, or use a
  raw-connection trace/authorizer boundary that cannot be capability-gated off. Add this exact
  `hasattr(connection, "cursor")` mutant and require the complete focused gate to fail for the
  additional prepared call.

## R3 mutant reproduction

All four exact R3 P0 mechanisms were injected in process without editing repository files and were
killed by their owning R4 controls on fresh file-backed `tmp_path` SQLite:

1. **Wrong acceptance-evidence bind — `reproduced-live`:** replacing
   `(acceptance.acceptance_set_id,)` with `(effect.effect_id,)` failed the disjoint effect proof;
   hydration returned `INTEGRITY_FAILURE` instead of `FOUND`.
2. **Parenthesized hidden read — `reproduced-live`:** adding
   `SELECT count(*) FROM (execution_fact)` failed exact call count with 16 proof calls against the
   15-call root allowlist.
3. **Comment-prefixed dynamically assembled `COMMIT` — `reproduced-live`:** the exact
   `getattr(connection, "in_transaction", False)` plus
   `"-- transaction\n" + "".join(("COM", "MIT"))` mutant failed with
   `repository attempted transaction SQL COMMIT`.
4. **Removed active-stream all-or-none rule — `reproduced-live`:** clearing the first coordinate,
   `active_stream_generation_id`, returned `FOUND` under the mutant and failed the owning
   contradiction test. The unmodified focused gate retains the all-null positive proof.

The unmodified focused gate passed **186 tests in 6.92s** on CPython 3.12.13. Every database fixture
used an explicit fresh file-backed pytest temporary database with foreign keys and recursive
triggers enabled.

## Additional-call disproof matrix

On fresh file-backed main and attached `aux` SQLite databases, injected additional proof calls using
quoted tables, parenthesized tables, comma joins, arbitrary schema qualification, a CTE, a subquery,
and a non-domain `SELECT` were each rejected by the ordered call-count gate (`reproduced-live`).
Those syntax classes disprove the four R3 parser-specific bypasses, but they do not disprove P0-1:
all seven probes used the recorder's visible `connection.execute` path, while P0-1 changes the
capability path itself.

## Prior-finding reconciliation

- The original REV-0073 codec/direct-key/totality P0 and two production P1 findings remain corrected
  in the reviewed production surface.
- R1's indexed-range/history-fold P0 and optional-claim/exact-scalar P1 findings remain corrected.
- R2's five gate classes and two production-semantic P1 findings remain corrected for their exact
  recorded mechanisms.
- R3's four exact mutants are killed as listed above. R4 cannot accept because the stronger raw
  cursor capability mutant survives the complete focused gate.
- Exact exports/import inertness, canonical duplicate classification, scalar exactness, proof
  totality, visible direct-query plans, schema-source immutability, caller transaction ownership for
  the exact R3 mutant, and accepted scope showed no additional P1/P2 defect in this bounded pass.

## Critic-candidate reconciliation and disproof pass

- **Cursor-based hidden query:** independently reproduced and promoted to P0-1. The strongest
  counterargument—that every extra statement is caught regardless of SQL syntax—fails because the
  recorder itself changes the connection capability surface.
- **Cursor-based dynamic `COMMIT` then `BEGIN`:** `reasoned-only` and **not counted as a second
  finding**. Static inspection confirms both prerequisites: `_TransactionTripwireConnection`
  delegates unknown attributes, including `cursor`, to the raw connection, and the per-operation
  test checks only `in_transaction` before rollback rather than operation-specific persisted state
  after rollback. The exact live mutant/rollback observation was not executed before the human's
  finalization stop, so this candidate remains unverified rather than being promoted on inherited
  critic reasoning. P0-1's capability-transparent remediation should also close this adjacent path,
  but that is not accepted as proof.
- P0-1 was challenged against the normal 186-case gate and a raw-connection trace. Both conditions
  required for the finding held: the prohibited read was reachable and observed, while the complete
  mandatory gate remained green. The finding stands.

## Unverified items and boundaries

- The cursor-based dynamic `COMMIT`-then-`BEGIN` rollback-persistence candidate was not reproduced
  live and is not included in the counts.
- The claimed 559-case integration selection, 61-case R2 oracle, 1,876-case full execution-core
  suite, Ruff, mypy, Import Linter, governance gates, Python 3.11, and external CI were not rerun.
  The ten-minute full suite was intentionally not widened into this bounded R4 review.
- The recorded DDL SHA-256 value was not independently recomputed; exact schema blob immutability
  from accepted base through candidate and later documentation head was verified.
- No configured/existing or in-memory database, network service, broker, credentials, order,
  migration, runtime composition, M2-I4 work, push, PR, promotion, or merge was used.

## Final counts and disposition

- **P0: 1**
- **P1: 0**
- **P2: 0**
- **Verdict: BLOCK**

WO-0167 cannot clear independent review because the mandatory exact proof-call gate remains
non-failure-capable on a real accepted cursor execution path. This result does not activate M2-I4
or authorize merge.
