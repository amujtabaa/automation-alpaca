# Independent WO-0152 E3 implementation remediation 01 recheck

Review target: `codex/arch-reset-2026-07-r1` at base/HEAD
`ae626f56fb05c09b312a7383326ebbf9ba584cd3`, R1 candidate manifest SHA-256
`7761f179a0c7c0aefc1045d8d956ab791c76bf425e6117c91bdd0f6853405ee3`.
All 27 manifest rows matched their pinned SHA-256 values. Retained
`coverage-e3-final-r1.json` matched
`220e370e82d99b61962e0d4b7460fe711cd97ad2f430bce6b7c3c0484f0e36f2`.

## Findings

### [P1] The accepted exact setup/source authority remains bypassable

- Location: `tests/execution_core/test_acquisition_stateful.py:617`;
  `tests/execution_core/test_acquisition_stateful.py:3563`
- Requirement: The retained R2-R3 exact exception table and R2-R4/R2-R5
  source rules require failure-capable enforcement of the exact permitted
  helper owners, operation counts/shapes, loop flow, and prohibition of copy,
  patch, mutation, and early-exit constructs outside those limits.
- Evidence: `[reproduced-live]` The new controls correctly reject the five
  predecessor counterexamples, but four independent remaining mutations still
  return an empty violation tuple: a rogue `copy.copy` call; a rogue
  `patch.object` context; a bare `continue` in the schedule mint loop; and an
  eighth `object.__setattr__` in the serving setup helper. The checker does not
  enforce the retained exact copy/setter/private-reducer counts, globally own
  copy/patch exceptions, or reject `break`/`continue`/comprehension flow.
- Impact: Test code can again manufacture or mutate authority outside the
  accepted setup boundary, or alter the fixed mint schedule's control flow,
  while the named source-policy control remains green. The provenance and
  bounded test-privilege evidence is therefore still incomplete.
- Resolution: Encode the complete retained R2-R3 exception table and
  R2-R4/R2-R5 flow exclusions, including exact owner/count/shape checks for
  copy, setters, private reducer/hook, patch targets, and all prohibited loop
  flow, with isolated negative specimens for each family.

### [P1] AC-01 still inventories representative functions rather than every frozen E1/E2 requirement owner

- Location: `tests/execution_core/test_acquisition_stateful.py:391`;
  `tests/execution_core/test_acquisition_stateful.py:3530`
- Requirement: FR-01 / AC-01 requires the exact E1/E2
  requirement-to-failure-capable-test map and a stop if any base behavior lacks
  an owning-slice control.
- Evidence: `[static-reasoning]` The replacement lists nine locally named
  categories and verifies that nine functions exist with a minimum number of
  AST `assert` nodes. E1 alone contains FR-01 through FR-10 and AC-01 through
  AC-07; E2 contains FR-01 through FR-11 and AC-01 through AC-08. The table
  does not map those exact frozen requirement/control IDs, and two E1 plus
  seven E2 representative functions cannot mechanically establish ownership
  for every requirement. Assertion count is also not failure capability:
  replacing the predicates with `assert True` preserves the inventory result.
- Impact: A frozen base requirement can lose its owning semantic assertion
  while AC-01 remains green, allowing E3 to become the apparent proof for a
  behavior whose E1/E2 ownership has disappeared.
- Resolution: Map every controlling E1/E2 FR/AC identifier to its exact owning
  test and verify a semantic/frozen ownership predicate that fails when the
  decisive assertion is removed or made tautological; keep supplemental E3
  controls separate.

### [P1] AC-05 now consumes the oracle, but several required comparisons are labels only

- Location: `tests/execution_core/test_acquisition_stateful.py:447`;
  `tests/execution_core/test_acquisition_stateful.py:3513`;
  `tests/execution_core/test_acquisition_stateful.py:3877`
- Requirement: FR-06 / AC-05 requires omission mutants for identity-coordinate
  binding, direct lineage equality, genesis/successor head and ordinal,
  controller-head advance, one-LIVE uniqueness, aggregate exactly-once,
  compatibility, generation-local capacity, codec consistency, and bounded
  direct lookup.
- Evidence: `[static-reasoning]` The remediation correctly routes the omission
  mutants through the real long-sequence oracle, closing the detached-record
  defect. However, `head_ordinal` checks only that the ordinal equals 31 and
  never compares or advances `controller_head`; `capacity` checks only that two
  test collections have length 32 rather than generation-local capacity; and
  no comparison owns the complete authenticated identity-coordinate binding.
  Omitting those required semantic comparisons is therefore already the live
  baseline and cannot be killed by removing one of the eight dictionary keys.
- Impact: The mutation result can be green while core serial identity,
  currentness-head, or generation-local capacity checks are absent, so it still
  does not prove the assigned real behavior control detects every FR-06
  omission.
- Resolution: Add the missing concrete comparisons to the consumed behavior
  oracle and give each its own omission mutant; do not collapse head plus
  ordinal or schedule length plus generation-local capacity into one label.

## Closed predecessor finding and focused evidence

- `[reproduced-live]` The AC-04 boundedness P1 is closed. The control constructs
  all 32 public generations, executes current refresh/admission and rooted
  late-fact reduction under the exact sixteen history tripwires, then proves
  direct earliest/current registry lookup and retired-fact lineage routing.
- `[reproduced-live]` The three focused remediation controls passed. The
  coverage validator passed retained evidence at
  `24825 / 26530 = 93.573313%` lines and
  `8461 / 9920 = 85.292339%` branches.
- `[reproduced-live]` The tracked candidate delta contains no `app/**` path;
  the remediation itself is test-only plus authorized evidence/current-record
  updates. No M1 closeout or external-CI success is claimed.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 3
P2: 0
Unverified: the claimed complete E3-module and full-repository runs and
external exact-head Python 3.11/3.12 CI were not rerun in this focused seat.
