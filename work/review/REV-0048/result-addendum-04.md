---
type: Review Result Addendum
rev_id: REV-0048
addendum: 04
reviewer_model: Codex (GPT-5)
reviewed_target: 982d2137473a60e7052cae4d9cd88d9a384f001b
implementation_freeze: 5a8984133354ecfa0343d6fb4a7fdaef38d56dab
base: fe85336c962e13ba34a57c52856c65bda4fa83a7
verdict: ACCEPT
date: 2026-08-02
relationship: Independent successor review of the complete Python 3.11 compatibility repair; addendum-03 and every earlier request, result, evidence artifact, and blocked freeze remain preserved unchanged.
---

# REV-0048 Addendum 04 — independent review result

## Verdict

**ACCEPT.** I found no unresolved P0 or P1 in exact evidence target
`982d2137473a60e7052cae4d9cd88d9a384f001b` or implementation freeze
`5a8984133354ecfa0343d6fb4a7fdaef38d56dab`. The iterative projection closes addendum-03's
retained-leaf class and the later independently disclosed auxiliary-map bypass. It is
failure-capable against every pre-registered current graph surface, terminates under a hostile
cycle at a recursion limit of 700, distinguishes equality-omitted output state, and does not create
history- or identity-dependent divergence between independently equivalent graphs.

This verdict clears the independent implementation-review gate only. It does **not** satisfy the
mandatory unchanged exact-head Python 3.11/3.12 CI gate. WO-0146 therefore remains effectively
`REVIEW`, and WO-0147 remains inactive.

## Closure of the blocking chain

| Blocking class | Independent result |
|---|---|
| Addendum-03 retained `RootHead`, `SeenFact`, and sequence leaves could change while cached commitments stayed fixed | **CLOSED.** The projection at `tests/execution_core/test_fill_position_stateful.py:277` walks the actual dataclass/tuple graph and records every field, retained value, exact type, structural edge, and alias ordinal. Fresh reversible root-map and sequence-store probes changed the projection while their cached commitments remained fixed. |
| Freeze `1189d88` omitted `RootHeadIndex._broker_scope_counts` and `SeenFactIndex._prefix_commitments` | **CLOSED.** I substituted the incomplete predecessor oracle in memory. Both permanent parameters reproduced RED (`DID NOT RAISE`); restoring the complete projection made both GREEN. Fresh mutations of both auxiliary-map values were killed and restored exactly. |
| Ordinary `RootHeadIndex`/`SeenFactIndex` equality omits auxiliary state | **CLOSED for this oracle.** The complete transition projection runs before ordinary equality at `tests/execution_core/test_fill_position_stateful.py:245`. Fresh second-output prefix-cache corruption left ordinary transition equality true but made the complete projections differ. |
| Python 3.11 recursive rendering failure | **CLOSED locally and pending external version proof.** The complete stateful file passed 22/22 with the interpreter recursion limit reduced to 700. The projector uses an explicit work stack and reference ordinals; it never recursively renders a persistent container. Exact CPython 3.11 and 3.12 proof remains the successor CI gate. |

## Fresh adversarial probes

I built new objects and performed reversible mutations rather than relying only on the permanent
tests:

- **All six direct maps:** `_by_root`, `_broker_scope_counts`, `_by_key`, `_observed_roots`,
  `_overfill_scopes`, and `_prefix_commitments` each changed the complete projection when a retained
  value changed; restoration reproduced the original projection.
- **All three sequence stores:** the root order, effective-head order, and seen-fact order backing
  maps each changed the projection when their stored value changed. A sequence mutation integrated
  through `_apply` could not return successfully and restoration reproduced the original graph.
- **Cached metadata and aliases:** changing a radix node's cached `value_commitment`, replacing the
  required shared root sequence with an independently equal sequence, and replacing a shared
  binding were detected. The permanent alias and cached-node controls also passed in the complete
  stateful run.
- **Cycle:** replacing a radix root's children with a self-edge terminated twice with the same
  fingerprint, differed from the acyclic graph, and restored exactly. It did not approach the
  reduced recursion ceiling.
- **Sibling history and graph equivalence:** two persistent maps containing the same key/value pairs
  but built in opposite insertion orders were distinct objects with identical projections.
  Reversing the canonical sibling tuple then changed the projection.
- **Second-output divergence:** two independently produced transitions projected identically.
  Mutating only the second transition's equality-omitted prefix cache kept `first == second` true
  but made the complete projections differ, so the authoritative assertion killed it.
- **Leaf inventory:** the exercised graph contained only the execution enums/flags, `None`, exact
  booleans, bytes, integers, strings, `Decimal`, and `Fraction` outside dataclass/tuple containers;
  no list, dict, set, bytearray, memory view, or other mutable untraversed leaf was present.

The new projector also makes the output oracle stricter without creating a false divergence:
independently allocated but structurally and alias-topology-equivalent results receive the same
ordinal sequence because ordinals are assigned by deterministic structural encounter order, not by
embedding object IDs.

## Independent execution and static evidence

- Complete stateful file at recursion limit 700: **22/22 passed** in 106.2 seconds with
  `BROKER_ADAPTER=mock` and a fresh workspace-local base temp.
- Complete pure `tests/execution_core`: **536/536 passed** in 188.3 seconds with
  `BROKER_ADAPTER=mock` and a second fresh workspace-local base temp.
- Ruff check and Ruff format-check: pass over all 17 execution-core source/test files.
- mypy: pass over all seven execution-core source modules.
- Import Linter: six contracts kept, zero broken.
- AI-OS install, version, ledger, PKL, and work-order-disposition checks: pass.
- Exact `fe85336..5a89841` and cumulative `4b9b47d..5a89841` scope checks: pass.
- Exact and cumulative `git diff --check`: pass.
- A separate evidence-audit seat freshly collected **5,124** repository cases and passed all
  **61/61** R2 conformance cases under `BROKER_ADAPTER=mock`. I did not rerun the database-bearing
  repository coverage suite in this seat.

Static AST inspection found no production comparison of whole `RootHeadIndex` or `SeenFactIndex`
objects. Production paths compare exact commitments, counts, scopes, binding identity, required
sequence aliases, or explicit materialized values. The equality omissions therefore do not leave a
production P1, and no production behavior was changed to close this test-oracle defect.

## Exact object, scope, and evidence identity

- Target `982d2137473a60e7052cae4d9cd88d9a384f001b` is the direct child of implementation freeze
  `5a8984133354ecfa0343d6fb4a7fdaef38d56dab` and adds exactly the addendum-04 request and evidence.
- The implementation delta `fe85336..5a89841` changes exactly the stateful test and WO FIX record.
  The cumulative recovery delta `4b9b47d..5a89841` contains exactly five allowed paths: those two
  files plus the preserved addendum-03 request, evidence, and reviewer result. Including the exact
  evidence target adds only the two addendum-04 author-owned files, for seven paths total.
- `app/execution_core` is byte-identical at tree
  `09f93d1577dd2c0e1499acf56cf4688cac8be665`; complete `app` is byte-identical at tree
  `b144102e4c99c9e889cd7e22591c884630187188` across the failed candidate and final repair.
- Final stateful test: 46,443 bytes, SHA-256
  `c3d0a4111eb53bf4fb242e80391148eb34d383b4f6bd2c87d8066bf2bf1c1551`.
- Addendum-04 implementation evidence: 6,512 bytes, SHA-256
  `6a82934e90f74e0ecf1596113aed390e9b63d640881a2165aef8fc2f123d337b`.
- Addendum-04 request: 2,514 bytes, SHA-256
  `c291ab723f36992146fe872a20008fbea104ce5e181d925ea346d40b4084e074`.
- Preserved addendum-03 result: 3,159 bytes, SHA-256
  `b85c224c92750b6abcb605c96f60b9c6c51c3e860a552051d6d56f51aba11536`.
- Binary coverage artifact: 1,765,376 bytes, SHA-256
  `7cd7642ff617c37405f208ed8ab037240391bbf58c34bb34e3590c0a5308c02a`.
- JSON coverage artifact: 1,739,722 bytes, SHA-256
  `768c86f13505eb2fb606fc1542420ba1ed9cf0504c8b1835b3b94951a68964ec`.
  Its totals are 17,537/18,503 lines and 6,080/6,890 branches: 23,617/25,393, exactly
  `93.00594652069468%`.

The binary artifact is byte-identical to the earlier full-run artifact because the repair changes
tests and WO prose only; the JSON production totals are likewise unchanged. The recorded
5,112-passed/11-skipped/1-xfailed repository distribution and duration remain hash-addressed
implementation-seat evidence until external exact-head CI reproduces the unchanged workflow.

## Non-blocking limitations and exclusions

- A hostile mutation of a shared sequence leaf is detected but can make ordinary index equality at
  `tests/execution_core/test_fill_position_stateful.py:248` raise
  `RuntimeError: root index order references a missing head` before the final mutation-specific
  assertion at line 249. This is less diagnostic than the intended assertion, but it cannot pass
  silently, the independent projection itself changes, and the graph restores exactly; it is not a
  P1 assertion bypass.
- Completeness currently relies on all behavior-bearing containers being dataclasses or exact
  tuples (`tests/execution_core/test_fill_position_stateful.py:285-314`). The fresh runtime inventory
  found no unsupported mutable leaf. A future production representation that adds another mutable
  container kind must extend this test-only projector and its inventory pin; that hypothetical
  maintenance obligation is outside this exact unchanged production tree.
- I did not use SQL/DDL, a database engine or fixture, credentials, broker/Paper activity, network,
  persistent application state, runtime wiring, PR/merge, branch/worktree retirement, deletion, or
  cleanup. The prohibited R1 DDL result supplied no evidence.
- No WO-0147 work-order file exists. PKL and the WO retain the effective `REVIEW` posture. An
  immutable successor must pass unchanged exact-head Python 3.11 and Python 3.12 CI before the
  closeout becomes effective or WO-0147 can activate.

**ACCEPT**
