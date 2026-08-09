# REV-0063 - independent clean-room review result

## Reviewed identity

- Branch: `codex/m1-5-broker-alignment-local-r1`
- Base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`
- Candidate: `fb9ecb23c52c8c15545613974ea49cdd56dce260`
- Candidate manifest SHA-256 actually reviewed:
  `3230c9f30cc6144b9f87606776fb5aebd3e59264c2c4928d9ca65489574f7130`
- Proposed ADR SHA-256 actually reviewed:
  `6251344e5d5de7afcffdaedd6629b8fc4a99943524130caa2695a7778cf50c49`

## P0 findings

No P0 findings.

## P1 findings

### P1-1 - The execution-profile commitment is self-referential

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md:59`
- Requirement: the selected immutable profile and its commitment must be
  constructible, independently verifiable, and usable for total durable binding
  and fail-closed mismatch checks.
- Evidence: `[static-reasoning]` `profile_commitment_sha256` is itself a listed
  profile coordinate at line 59, while lines 63-64 require that digest to commit
  a complete preimage containing "every listed coordinate." That definition
  therefore includes the digest being calculated in its own preimage. Unlike the
  packet manifest, which explicitly excludes its own digest to prevent the same
  cycle, ADR-024 states no exclusion or other terminating construction.
- Why it matters: M2 cannot deterministically create or independently recompute
  the profile commitment on which row binding, startup refusal, final-claim
  refusal, historical retention, and cross-profile identity checks depend. An
  implementation would have to invent an unratified encoding/exclusion rule.
- Smallest resolution: define a versioned, domain-separated canonical preimage
  with an exact field order that explicitly excludes
  `profile_commitment_sha256`, then define the digest as the SHA-256 of those
  bytes. Apply the same non-self-referential construction to
  `source_profile_commitment_sha256`, and ensure no profile identifier is itself
  derived in a way that recreates the cycle.

### P1-2 - Capability evidence is frozen before the milestone that can produce it

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md:57`
- Requirement: capability profiles must be evidence-gated, M2 must remain
  inactive and credential-free, and M4 must preserve its separate human gate
  before credential use or outbound Alpaca Paper calls.
- Evidence: `[static-reasoning]` the immutable execution profile contains
  `capability_profile_sha256` at line 57; lines 109-112 make a change to that
  digest material and require a new application generation plus recutover.
  Lines 142-150 require the hashed capability profile to contain tested, dated
  evidence for submit/cancel/replace, targeted query and coverage, reconnect,
  corrections/busts, and partial fills. The companion M2 contract says its
  activation record creates the immutable selected profile
  (`04-m2-persistence-contract-amendment.md:7`), while M4 is explicitly the first
  opportunity to establish that evidence
  (`05-roadmap-and-milestone-reconciliation.md:27`). The proposed ADR then says
  M4 must measure the profile before any credential or outbound API authority is
  used at lines 200-201, whereas the packet's own M4 obligation correctly places
  measurement under a separately approved credential gate
  (`06-m2-m9-obligations-and-acceptance.md:7`). The accepted roadmap likewise
  requires that human gate before credentials or outbound calls.
- Why it matters: the lifecycle has no satisfiable first path. M2 cannot freeze a
  complete evidence digest before M4 performs the credential-gated measurements;
  an absent or placeholder digest must fail closed, but adding the M4 evidence
  later changes a material immutable coordinate and triggers the recutover rule.
  The literal "before any credential or outbound API authority" clause also
  bars the calls needed to obtain the named empirical evidence.
- Smallest resolution: state one non-circular lifecycle explicitly. For example,
  let M2 implement and test the schema/refusal contract without creating the
  operational selected profile; let separately human-authorized M4 conformance
  calls produce and freeze the evidence-backed capability digest; then create
  the immutable selected profile and permit `PAPER_MUTATION_ELIGIBLE` only after
  all remaining cutover gates pass. If an earlier profile must exist, separate
  its immutable required-capability contract from the later append-only measured
  evidence authority and define exactly how the latter can become current
  without an in-place profile rewrite or an unintended recutover.

## P2 findings

No P2 findings.

## Executed verification

- `[reproduced-live]` The checked-out `HEAD` and named branch both resolved to
  the exact candidate; the base and candidate objects exist.
- `[reproduced-live]` All ten manifest-covered files matched their recorded
  SHA-256 values.
- `[reproduced-live]` The base-to-candidate diff contained exactly those ten
  semantic files plus the self-excluded manifest: 11 expected paths, 11 actual
  paths, with no omissions or extras.
- `[reproduced-live]` `git diff --check` passed for the exact review range.
- `[reproduced-live]` `check_ledger.py` and `check_pkl.py pkl` passed under
  Python 3.14.5.
- `[reproduced-live]` `check_work_order_scope.py` passed when supplied the exact
  work order and base-to-candidate changed-file list.

## Unverified

- Full pytest, Ruff, mypy, import-boundary, coverage-ratchet, R2-oracle, and
  Python 3.11/3.12 exact-head CI were not run. They are post-ratification gates
  for this documentation-only candidate and are not used as acceptance evidence
  here. The work-order command's local `.venv\\Scripts\\python.exe` was absent;
  the applicable AI-OS static checks above were rerun with available Python
  3.14.5.
- No broker, network, credential, database, SQL/DDL, runtime, PR #12, or external
  CI check was used.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
