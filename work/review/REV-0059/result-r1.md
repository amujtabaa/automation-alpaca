# WO-0152 E3 R1 RED-contract independent preflight result

Review base: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`
Branch: `codex/arch-reset-2026-07-r1`
Frozen R1 manifest SHA-256:
`86ba85d531186567d289f761fca7ba1f5e658768ff1818ea4d978329b9e48888`
Review mode: independent static and file-level inspection only

## Exact-candidate verification

- Evidence: `reproduced-live`. `HEAD` and branch matched the manifest. The
  index was empty, `git diff --check` exited 0, and no production or existing
  test path was present in the tracked or untracked delta.
- Every manifest-listed path hash matched. The core R1 candidate hashes were:
  remediation disposition
  `3b99a1f5dc177003279b9c32690bfdc50213a01d03da80fd05e12a1e2f5b3fa5`,
  RED contract
  `3b2ba052df61f8e128f82b4ee408568774ff8cdd62a815e4387a821ab6f9709b`,
  request
  `a830a1aa75a790c4d54db008c483abe72c363fb3a9f2a16579ae1209b69a1098`,
  and WO-0152
  `0fbdcf87f5f5e71df8a14f5e780f17b5fba3ddcf4b09c00c51808d773e955d86`.
- The retained R0 contract, manifest, request, and independent result matched
  `ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4`,
  `ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe`,
  `1a31a21820e9152f4da7bd494607ae4711e75d8c164ad48c956a6039a7e4ee5e`,
  and
  `ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57`
  respectively. The retained `result.md` was not edited.
- The tracked delta was exactly the eight manifest-listed documentation/
  governance paths. The untracked delta was exactly the three manifest-listed
  REV-0058 records plus the retained four-file R0 packet and four-file R1
  packet in REV-0059. Before this reviewer-owned artifact was created,
  `tests/execution_core/test_acquisition_stateful.py` and
  `work/review/REV-0059/result-r1.md` were both absent.
- The records consistently retain run #741 as functional/static positive
  evidence and coverage-only negative evidence at 91.34% versus 93%, keep
  WO-0151 effectively `REVIEW`, keep WO-0152 `DRAFT`, and retain the paired
  E2/E3 93% exact-head Python 3.11/3.12 gate before effective closure or M1
  completion.

## Findings

### [P1] The exact AST allowlist omits the write needed to return the copied authority

- Location: `work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md:168-189`;
  `work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md:195-214`;
  `app/execution_core/authority.py:634-674`;
  `app/execution_core/authority.py:5828-5840`.
- Requirement: The terminal fixture must install only the resulting venue book
  into a copied authority state, while the self-source AST control rejects
  every `object.__setattr__` occurrence except its exact fixture-owned expected
  set. The user authorization permits the copied `authority.venue` replacement
  and no other authority coordinate change.
- Evidence: `static-reasoning`. `ExecutionAuthorityState` is frozen and opaque;
  its constructor always raises, and the production copy-with-changes helper is
  private. A Python 3.11/3.12 test therefore needs a shallow copy plus an exact
  `object.__setattr__(copied_authority, "venue", transition.book)` occurrence
  to produce the required state. Section 3.5 explicitly lists `copy.copy` and
  `object.__setattr__` only for the environmental fixture's six fields. The
  terminal row names private proof/reducer/patch exceptions and says
  `copied authority.venue only` only as a static limit; it does not include the
  copy or setter in the exact exception set that the same section requires.
  I attempted to disprove this via the public authority surface and the
  package exports: neither exposes a public state replacement constructor.
- Impact: A literal exact-set AST implementation either rejects the only
  constructible terminal fixture or must silently broaden/interpret the
  allowlist. Without the copied authority carrying the closed venue book, the
  public refresh/admission/successor path cannot consume the certified setup.
- Smallest complete resolution: Add exactly one terminal-fixture-owned
  `copy.copy(authority)` occurrence and exactly one
  `object.__setattr__(copied_authority, "venue", applied.book)` occurrence to
  the table's exact exception set, after APPLIED/CLOSED validation. Require
  negative source specimens for an original-state write, any other field, a
  second setter/copy site, and a shared or dynamically selected setter.

### [P1] Clear effect reconciliation is required before closure but has no allowed bounded proof

- Location: `work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md:149-178`;
  `work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md:243-251`;
  `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md:291-311`;
  `app/execution_core/venue.py:4378-4392`;
  `app/execution_core/venue.py:7467-7471`;
  `app/execution_core/venue.py:11530-11615`.
- Requirement: The authorized private closure may run only after clear
  reconciliation has been independently checked. The fixture may use bounded
  public direct readers, but may not scan reconciliation history or read/call
  another private production member. Invalid preconditions must refuse before
  the private transition.
- Evidence: `static-reasoning`. The allowed public `effect`, `owner`,
  `active_attempt`, and `closure_head` readers do not expose effect-level
  reconciliation clearance. The only public reconciliation views materialize
  retained reconciliation histories, which this contract expressly forbids;
  the bounded current predicate is the private
  `_has_effect_reconciliation`. Moreover, `_close_acceptance_set` checks OPEN,
  exact scope/claim, no active leg, and the patched certificate, then changes
  the acceptance set to CLOSED without checking effect reconciliation.
  `_maybe_finalize_effect` checks reconciliation only after closure and simply
  declines finalization, so APPLIED plus CLOSED is not a precondition proof.
  Counterexample: a claimed OPEN effect with the exact terminal owner/closure,
  no active attempt, flat consistent execution, and retained effect-level
  reconciliation satisfies every enumerated allowed direct check; the private
  reducer can close it while leaving it non-final. The contract also does not
  pin an exact public effect state or exact no-interleaving APPLIED transition
  chain that could serve as a source-proven substitute.
- Impact: The required reconciliation-negative control is not constructible
  within the frozen allowlist. Implementing it requires either a prohibited
  history scan/private read or permits the test-only certification route to
  close a parent outside the user's exact preconditions. A later public
  successor refusal does not cure that earlier unauthorized closure call.
- Smallest complete resolution: Freeze a source-proven public precondition that
  actually excludes effect reconciliation before the hook is patched: bind the
  helper to the exact local, no-interleaving chain of APPLIED claim, discovery,
  and terminal outputs; pin the exact pre-close public effect state and
  `CONTRACT_COMPLETE_RESPONSE` proof kind; and add a reconciliation-injection
  control proving the hook/private reducer is not reached. If the frozen public
  state cannot prove that condition, stop and obtain explicit human approval
  for one exact bounded reconciliation-clear reader; do not infer clearance
  from CLOSED or scan the reconciliation ledger.

## Evidence limits and activation disposition

No tests, fixtures, database/SQL/DDL, network, broker, credential, runtime,
CI, or coverage command was run. GitHub Actions run #741 was not queried; only
its frozen, internally consistent records were inspected. No source, existing
test, work-order, PKL, ledger, manifest, request, or retained result was
modified.

Activation disposition: **STOP — WO-0152 remains DRAFT and no E3 test creation
or execution is permitted.**

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
Unverified: external GitHub Actions provenance for run #741; dynamic behavior
of the future absent E3 module, because this gate prohibited its creation and
all execution.
