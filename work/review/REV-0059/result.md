# WO-0152 E3 RED-contract independent preflight result

Review base: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`  
Frozen candidate manifest SHA-256:
`ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe`  
Review mode: independent static and file-level inspection only

## Exact-candidate verification

- The manifest hash matched the value above.
- Every tracked, non-self untracked, frozen source/test, and ADR hash listed in
  the manifest matched its file.
- `HEAD` matched the frozen base. The tracked delta was exactly the eight
  listed documentation paths; the six untracked candidate files were the
  manifest itself plus its five listed non-self packet records.
- No E3 test module or prior `result.md` existed at review start, and
  `git diff --check` passed.
- The documentation consistently classifies run #741 / ID `31185454392` as
  functional/static success and coverage-only negative evidence at 91.34%
  against the unchanged 93% gate. It consistently leaves WO-0151 effectively
  `REVIEW`, WO-0152 DRAFT/preflight-only, and both effective closeouts plus M1
  completion dependent on paired exact-head Python 3.11/3.12 success.

## Finding

### [P1] The public-only boundary cannot construct the required acquisition mandates

- Location: `work/review/REV-0059/WO-0152-RED-CONTRACT.md:53-97`;
  `app/execution_core/acquisition.py:1147-1226`;
  `app/execution_core/acquisition.py:1329-1367`;
  `tests/execution_core/test_acquisition.py:221-248`.
- Requirement: The sole fixture exception may alter only the six serving-
  environment coordinates. After it, every bootstrap/controller action must
  use declared public contracts, with no private production name, existing
  test helper, or construction of an opaque/sealed value. E3-01 through E3-06
  require an authentic initial mandate and distinct authentic successor
  mandates for A, B, and C.
- Evidence: `static-reasoning`. `AcquisitionMandate` is publicly exported but
  requires an authentic `DualMandateBinding`. `DualMandateBinding.__init__`
  always raises because the value is reducer-constructed only. The only
  constructor in the frozen implementation is the deliberately private
  `_mint_dual_mandate_binding`; no public transition can return a binding
  before `initialize_acquisition_controller` already receives a complete
  mandate. The retained E2 test creates mandates by calling that private
  minter. I also attempted to disprove the issue by tracing the package-root
  exports and the public authority, venue, registry, lineage, and controller
  outputs: none supplies the missing initial or successor dual binding.
- Impact: No positive genesis, A-to-B-to-C, stateful, replay, late-fact, or
  32-generation trace can be written under the frozen contract. Activation
  would force either an unauthorized private call/sealed-value forgery or a
  suite containing only refusal paths, so the RED contract is not yet
  constructible.
- Smallest complete resolution: Add one exact test-only configuration-input
  exception for constructing fixed approved A/B/C mandates with
  `_mint_dual_mandate_binding`, confined to one named pre-bootstrap helper and
  whitelisted only at that exact call site by the source control. The helper
  must return complete immutable `AcquisitionMandate` inputs and grant no
  acquisition, controller, effect, claim, or broker authority. Keep every
  other private import/access forbidden. If that bounded fixture is not
  acceptable, the alternative is a separately approved public configuration-
  boundary factory, which is a production/API change outside WO-0152.

## Reconciled non-findings

- The serving-environment fixture is otherwise necessary and narrowly
  bounded: deny-only genesis exposes no public runtime/configuration transition,
  and the six allowed coordinates grant no acquisition authority.
- The trace-codec design is explicitly test-owned replay from genesis, not a
  persistence, hydration, database, crash, adapter, or broker-recovery claim.
- The serial, late-fact, exactness, currentness, claim, boundedness, and
  test-owned sensitivity requirements are behavior-directed rather than
  coverage-denominator padding. The two-batch rule stops an open-ended review
  or coverage loop.
- No production, API, persistence, runtime, CI-workflow, coverage-threshold,
  database, broker, credential, M2, merge, deletion, or cleanup change is in
  the frozen candidate.

Verdict: ACCEPT-WITH-CHANGES  
P0: 0  
P1: 1  
P2: 0  
Unverified: GitHub Actions run #741 was not re-queried because network and CI
access were prohibited; its exact retained records and internal classification
were verified statically. No tests or application code were executed.
