# Independent WO-0152 E3 implementation acceptance

Review target: `codex/arch-reset-2026-07-r1` at base/HEAD
`ae626f56fb05c09b312a7383326ebbf9ba584cd3`, candidate manifest SHA-256
`5bb2c37a1405f19882d9a95a1b8eb219b7f888340327b2b56afd5a9c74dcdd53`.
All 23 manifest rows matched their pinned SHA-256 values. Retained
`coverage-e3-final.json` matched
`02941f1052a912a9484736f478e44495fc3ed08d4a4f719d90ba7eb168c638e0`.

## Findings

### [P1] The R2-R5 construction boundary is not failure-pinned by the source control

- Location: `tests/execution_core/test_acquisition_stateful.py:558`;
  `tests/execution_core/test_acquisition_stateful.py:3283`
- Requirement: Accepted R2-R4 section 4 and R2-R5 section 5 require the
  self-source control and isolated negative specimens to own the exact fixture
  signatures, direct loop/call shapes, literal probe provenance, schedule/probe
  separation, and pre-genesis invocation boundary.
- Evidence: `[reproduced-live]` The checker currently owns private-call owner
  names, the tripwire target set/shapes, and only the positive schedule's
  cardinality/uniqueness/literal-stream shape. Five independent in-memory
  source mutations all returned an empty violation tuple: parameterizing the
  schedule helper; parameterizing the probe helper; placing the probe mint
  under a branch; deriving the probe stream by indexing schedule A; and
  returning the probe in the positive schedule tuple. The seven existing
  specimens do not exercise the accepted R2-R4/R2-R5 negative matrix.
- Impact: Caller-shaped authority, derived sealed-stream provenance, a
  conditional private mint, or contamination of the 32-generation positive
  chain can enter while the named source-policy control remains green. This
  defeats the test-only privilege boundary that makes the E3 evidence safe to
  rely on.
- Resolution: Extend the AST control to prove every retained R2-R4/R2-R5
  signature, literal-provenance, call-placement, invocation-order, and
  schedule/probe-isolation rule, and add the separately required negative
  specimens so each prohibited construction fails for its own reason.

### [P1] The boundedness tripwire never exercises a long serial generation history

- Location: `tests/execution_core/test_acquisition_stateful.py:1978`;
  `tests/execution_core/test_acquisition_stateful.py:3438`
- Requirement: FR-05 / AC-04 and accepted R2-R3 section 3 require a long serial
  run that preserves direct earliest/current routing while the exact sixteen
  history materializers fail on live refresh, admission, and reduction.
- Evidence: `[static-reasoning]` The 32-generation aborted-chain control does
  not run live decisions under the history tripwire. The separately named long-
  sequence control constructs only the rooted A-to-B path, yielding one retired
  generation and one live generation, then applies one late-A fill inside the
  tripwire. It never combines the long serial history with earliest-generation
  fact routing under the traps.
- Impact: Work proportional to a large retired-generation set, including a
  regression to predecessor/history traversal, is not distinguished from the
  current bounded direct-map implementation. The strongest capital/lifecycle
  boundedness claim therefore lacks its required failure-capable evidence.
- Resolution: Construct the fixed long public serial trace, then exercise the
  required current and earliest-generation live decisions inside the exact
  tripwire and prove direct earliest/current routing through the allowed
  bounded readers after restoration.

### [P1] AC-01 inventories labels, not the frozen E1/E2 owning controls

- Location: `tests/execution_core/test_acquisition_stateful.py:391`;
  `tests/execution_core/test_acquisition_stateful.py:3268`
- Requirement: FR-01 / AC-01 requires an exact E1/E2 requirement-to-test map
  and a stop when any base behavior lacks a failure-capable owning-slice
  control; E3 may not become the first or only proof of base semantics.
- Evidence: `[static-reasoning]` `_E3_REQUIREMENT_CONTROL_INVENTORY` maps only
  the seven E3 acceptance labels to seven strings. Its test asserts the
  hard-coded label sequence and uniqueness of those strings. It neither names
  the frozen E1/E2 requirements and owning tests nor proves the referenced
  controls exist or are failure-capable; removing the body of a referenced
  E3 control would not fail this inventory test.
- Impact: A base identity, admission, economics, routing, protection, or
  currentness control can disappear while AC-01 remains green, allowing E3 to
  mask a missing lower-level proof rather than consume it.
- Resolution: Record the exact frozen E1/E2 requirement-to-owning-test map and
  make the inventory fail on a missing, duplicate, unresolved, or non-owning
  control, while retaining the E3 controls as supplemental evidence.

### [P1] The observer mutations do not mutate the behavior oracles they claim to protect

- Location: `tests/execution_core/test_acquisition_stateful.py:3239`;
  `tests/execution_core/test_acquisition_stateful.py:3283`
- Requirement: FR-06 / AC-05 requires each decisive comparison omission to
  make its assigned behavior control fail, including lineage, head/ordinal,
  one-LIVE, exactly-once economics, compatibility, capacity, codec, and bounded
  direct lookup.
- Evidence: `[static-reasoning]` The control replaces fields on one detached
  `_E3PublicObserver` value and proves `_e3_observer_mismatches` reports that
  field. No seeded, replay, economics, or boundedness behavior control calls
  this comparator. Removing a decisive assertion from those controls therefore
  leaves the mutation test green, and several comparisons explicitly required
  by FR-06 have no corresponding mutant at all.
- Impact: The packet's killed-mutation claim does not show that its public
  behavior oracles can detect loss of the core serial-generation invariants.
- Resolution: Implement named test-owned oracle/trace mutants that omit each
  required decisive comparison in turn and prove the assigned real behavior
  control fails for that reason, without patching production conditions.

## Reproduced evidence and scope

- `[reproduced-live]` The focused E3 module completed successfully with all 18
  tests passing. This confirms the current behavior examples, but does not
  disprove the failure-capability gaps above.
- `[reproduced-live]` Branch, HEAD, all manifest rows, retained coverage JSON,
  and the coverage-ratchet R1 `ACCEPT` pins matched exactly. The tracked delta
  contains no `app/**` path; noncandidate status entries are the declared temp
  trees, earlier coverage reports, and retained historical raw artifacts.
- `[static-reasoning]` The candidate adds no production application, broker,
  database, runtime, credential, M2, coverage-exclusion, or threshold change.
  The retained JSON arithmetic is `24826 / 26530 = 93.577083%` lines and
  `8462 / 9920 = 85.302419%` branches, above the unchanged independent
  `93.00%` / `85.25%` ratchets.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 4
P2: 0
Unverified: the full repository suite and external exact-head Python 3.11/3.12
CI were not rerun in this bounded seat; retained full-run JSON was used only
for identity and arithmetic.
