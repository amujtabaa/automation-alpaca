# Independent WO-0152 E3 implementation remediation 02 recheck

Review target: `codex/arch-reset-2026-07-r1` at base/HEAD
`ae626f56fb05c09b312a7383326ebbf9ba584cd3`, R2 candidate manifest SHA-256
`15d9bf169e895cc3927f5ce40b7ad73d4bec626f4bce980ae9bfcd6ff5a3b4aa`.
All 31 manifest rows matched their pinned SHA-256 values. Retained
`coverage-e3-final-r3.json` matched
`331b6886b8aa55bc1dd512074e67e5faa4578df8f701a1d33efd177966ae06bc`.

## Findings

### [P1] The exact setup/source authority still has unowned lexical routes

- Location: `tests/execution_core/test_acquisition_stateful.py:699`;
  `tests/execution_core/test_acquisition_stateful.py:3815`
- Requirement: The retained R2-R3 exception table and R2-R4/R2-R5 source
  rules require every allowed private/copy/patch/mutation site and schedule
  control-flow exception to be lexically exact and failure-pinned.
- Evidence: `[reproduced-live]` The four new rogue copy, `patch.object`, setter,
  and `continue` specimens now fail. Three independent residual mutations still
  return an empty violation tuple: a rogue direct `patch(...)` call, a list
  comprehension inside the fixed schedule fixture, and a second
  `venue._apply_venue_input(...)` call in the terminal-certification helper.
  The checker inventories only `patch.object`, omits comprehension nodes from
  the schedule flow ban, and authorizes the private reducer by owner without
  enforcing its exact one-site limit.
- Impact: An additional production patch/private transition or nonliteral
  schedule iteration can enter the test proof while its privilege-boundary
  control remains green, invalidating the exact provenance and bounded setup
  evidence.
- Resolution: Inventory direct `patch` as forbidden, reject all comprehension
  forms in the schedule helper, and pin the exact count/shape of the private
  venue reducer and certification hook, with isolated negative specimens.

### [P1] The fifteen-row AC-01 table maps E1 AC-01 to a non-owning primitive test

- Location: `tests/execution_core/test_acquisition_stateful.py:391`;
  `tests/execution_core/test_acquisition.py:5029`;
  `tests/execution_core/test_acquisition.py:5514`
- Requirement: FR-01 / AC-01 requires every frozen E1/E2 acceptance criterion
  to map to its exact failure-capable owning test and semantic predicates.
- Evidence: `[static-reasoning]` The remediation now enumerates all seven E1
  and eight E2 AC labels and its assertion-erasure mutant works. However,
  `E1-AC-01/FR-01-FR-02` is assigned to
  `test_wo0151_e2_identity_primitives_are_exact_and_input_validated`, whose
  assertions only validate the two E2 wrapper value types. It does not prove
  E1's deterministic/replay-stable generation identity or coordinate
  sensitivity. The actual frozen known-answer/replay/coordinate owning control
  is `test_identity_known_answers_replay_and_well_formed_variants_are_data_only`
  at line 5514. Erasing assertions from the incorrectly selected test cannot
  establish ownership of the E1 criterion.
- Impact: The inventory can report all fifteen ACs owned even while the core E1
  identity derivation proof is absent from its map, allowing E3 to rely on a
  base-semantic proof it did not mechanically verify.
- Resolution: Map E1 AC-01 to the actual known-answer/replay/coordinate owner
  and pin its decisive identity and coordinate predicates; recheck the other
  rows against their frozen AC descriptions rather than test-name proximity.

### [P1] AC-05 still omits public coordinates from its claimed full identity proof

- Location: `app/execution_core/acquisition.py:248`;
  `tests/execution_core/test_acquisition_stateful.py:4193`
- Requirement: FR-06 / AC-05 and the focused request require the real oracle
  and omission mutants to consume the full authenticated generation identity
  coordinates, alongside head progression, ordinal, one-LIVE, capacity, and
  binding evidence.
- Evidence: `[static-reasoning]` Head uniqueness/progression, terminal ordinal,
  one-LIVE, mandate capacity, dual-mandate binding, and application/scope/
  ordinal coordinates are now consumed by the real oracle. But the public
  `GenerationBindingView` also exposes
  `predecessor_or_genesis_head_commitment`,
  `emergency_recovery_compatibility_commitment`, and `binding_commitment`.
  The `identity_coordinates` conclusion checks none of those fields. The
  separate compatibility conclusion checks only the input mandates' shared
  compatibility value, not each generation record's sealed identity
  coordinate. Their omission is therefore the live baseline and no omission
  mutant can kill it.
- Impact: A record can carry the wrong predecessor/genesis head or compatibility
  coordinate while the claimed full-identity oracle remains green, weakening
  the serial lineage/currentness provenance the E3 proof is intended to lock.
- Resolution: Compare every record's predecessor/genesis head, emergency
  compatibility, and aggregate binding commitment to the expected public
  coordinates for its ordinal, and give each decisive comparison an omission
  mutant consumed by the real oracle.

## Focused evidence and scope

- `[reproduced-live]` The AC-01, source-policy/omission-mutation, and long-
  sequence controls passed. Eleven coverage-ratchet tests passed.
- `[reproduced-live]` The retained JSON passed the validator at
  `24826 / 26530 = 93.577083%` lines and
  `8462 / 9920 = 85.302419%` branches.
- `[reproduced-live]` Mypy passed across the exact 90-source command comprising
  `app/**` plus the validator and two changed test modules. Candidate diff
  inventory contains no `app/**` production change.
- `[static-reasoning]` Evidence correctly retains the 5,977-pass full local
  run as author-produced exact-candidate evidence and claims neither M1
  closeout nor external exact-head CI success.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 3
P2: 0
Unverified: the complete E3 module and full repository suite were not rerun in
this focused seat; external exact-head Python 3.11/3.12 CI remains pending.
