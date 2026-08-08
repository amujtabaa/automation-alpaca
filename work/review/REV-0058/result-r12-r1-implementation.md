# Independent WO-0151 R12-R1 implementation acceptance result

Review posture: fresh, read-first independent acceptance of the exact local
candidate. Author conclusions and historical green prose were not used as
acceptance evidence. The only review write is this result.

## Exact target and integrity

- Branch: `codex/arch-reset-2026-07-r1`.
- Required base, `HEAD`, and merge-base:
  `f25505cb59afde42e312a3933b85e44e6ad44c41`.
- Candidate manifest SHA-256:
  `abe0df5d723df536263e99a72d1b612ffcf39032de71753aaee9a6304e8166f0`.
- The index was empty. The tracked worktree delta was exactly the six
  manifest-listed candidate paths; every other tracked or untracked path was
  excluded from the candidate.
- Every candidate path was independently rehashed after verification and
  matched its manifest pin:

| Path | Recomputed SHA-256 |
|---|---|
| `app/execution_core/fills.py` | `6d9f5dcf0c9bc6b04304f3eab4f5822560a8f1f0a2afededb3f5530f4e5f6e4c` |
| `app/execution_core/acquisition.py` | `d94db238acaa586fcce0dcb931b12043ab2ec43ebe6b91074510da08bb3473a3` |
| `tests/execution_core/test_fill_position.py` | `fd56c921b66c3238393f25e37490bf2e85c09ed4a983a376b3e273a8eb57ef96` |
| `tests/execution_core/test_acquisition.py` | `799129974b9facecba3fe576fe89c7a56e0ce0b195e8f939397821b14a54bc14` |
| `tests/execution_core/test_protection.py` | `0d7cf12e220f02485e72566d8a5119f50c8b3f66ad60da01956042dddfb43872` |
| `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `8d89aa676e49dfbefa0c69d2e254cb8aefbc9f540af757d15a85bee55365ee65` |

- The governing R12-R1 contract, semantic result, and accepted activation R2
  result matched their authority pins respectively:
  `9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25`,
  `5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b`,
  and
  `ef5ba3af97bc76b2e1f77fa4bab0fc9d4677f5dfc7f8eb740c2e5c9dad688444`.
- ADR-020 R2 and ADR-021 R2 matched the retained WO-0151 pins
  `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653`
  and
  `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c`.
- The frozen WO-0152 detector and evidence remained unchanged at
  `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`
  and
  `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`.
  Neither was executed.

## Findings

No P0, P1, or P2 finding was identified.

## Independent re-derivation and disproof

Evidence: `reproduced-live` plus `static-reasoning`.

- `_PersistentKeyMap._lookup` follows the same one exact-key radix path and
  returns `(False, None)` only for physical absence. A retained `None` returns
  `(True, None)`. Legacy `get` delegates without changing its public behavior,
  while insert and replace now decide from presence rather than value
  (`app/execution_core/fills.py:433-469`).
- The market-stream relation is one private reducer-constructed sealed value
  in one private persistent map. The registry seal binds both direct-map
  commitments, retains the exact empty identity, and uses the nonempty v3
  domain. The only production consumer is one fixed-key `_lookup`; no iterator,
  collection reader, history walk, controller-retired collection, or
  authority-side duplicate index was introduced
  (`app/execution_core/acquisition.py:312-659`).
- The stream reader distinguishes absence from every malformed present value,
  authenticates the exact key/stream/binding/record relation, and accepts
  immutable value-equivalent route copies. Current-route resolution is part of
  controller-state authenticity. Candidate resolution occurs only after that
  authenticity gate and before successor authority registration
  (`app/execution_core/acquisition.py:488-518,2118-2175,4043-4290`).
- Consequently, malformed current state is rejected as invalid input when the
  refusal constructor re-authenticates it. A malformed or already-retained
  candidate route returns the ordinary exact nonmutating `REFUSED` transition
  with no receipt, effect, or claim. Only a physically absent candidate route
  can continue to registration.
- Generation-record/economics replacement retains the identical stream-route
  map and reseals against it. Successor insertion directly adds exactly one
  route after a duplicate lookup; serial A -> B -> C with distinct streams
  remains valid, while an A stream reused after A -> B is refused without a
  scan.
- The five test surfaces are failure-capable: map presence/insert/replace;
  distinct-stream serial success and nonadjacent reuse refusal; malformed
  candidate versus malformed current disposition plus immutable copy;
  replacement retention/pollution; and the moved bounded-map provenance owner.
  The provenance negative control now seals `_lookup`'s dependency closure and
  still proves `get` delegates through the moved traversal
  (`tests/execution_core/test_fill_position.py:5127`,
  `tests/execution_core/test_acquisition.py:1401-1878,3788-3907`,
  `tests/execution_core/test_protection.py:8835-8871`).
- Disproof mutations that bypass the early candidate lookup, pollute a retained
  route during record replacement, or rebind the radix dependency produce the
  intended failure and restore cleanly. Wrong-key routes, wrong runtime values,
  present `None`, and value-equivalent copies are distinguished by the focused
  controls.

## Fresh verification

Environment: Python `3.12.13`; pytest `9.1.1`.

- Focused R12/R12-R1/map/provenance gate: 18 selected cases passed, exit 0.
- Complete directly touched semantic pair:
  `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_fill_position.py tests/execution_core/test_acquisition.py`
  completed at 100%, exit 0.
- `.venv\Scripts\ruff.exe check` on the five changed Python paths: exit 0,
  `All checks passed!`.
- `.venv\Scripts\ruff.exe format --check` on the same paths: exit 0,
  `5 files already formatted`.
- `.venv\Scripts\python.exe -m mypy --no-incremental app/execution_core`:
  exit 0, `Success: no issues found in 10 source files`.
- `git diff --check` over the exact six candidate paths: exit 0 with no
  diagnostics.
- Final candidate, frozen-exclusion, branch, base, scope, and index checks were
  repeated after execution; no drift was found.

## Evidence limits

The full `tests/execution_core` suite was not rerun and is not an acceptance
basis for this result. The WO-0152 E3 detector, database/SQL/DDL, database
fixtures, broker/network activity, runtime wiring, external CI, Python 3.11,
cleanup, and paired 93% exact-head coverage gate were not run. The frozen E3
confirmation and paired external-coverage condition remain deferred exactly as
required; this result does not claim either work order effectively closed.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: frozen WO-0152 E3 rerun; full pure execution-core suite; external
Python 3.11/3.12 CI and paired 93% exact-head coverage gate; all explicitly
excluded runtime, persistence, database, broker, and network surfaces.
