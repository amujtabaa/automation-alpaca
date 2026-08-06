# WO-0149 post-activation bootstrap adjudication result

Review mode: independent static re-derivation. The reviewer did not run application code, tests,
SQL/DDL, database tooling, broker/Alpaca activity, network activity, or Git mutation.

## Findings

### [P1] The frozen public contract has no legal post-genesis M1E bootstrap

- Requirement: WO-0149 requires a new mandate for a new entry after terminal acquisition
  lifecycle state (FR-02, lines 136-142), while the domain specification makes single-flight
  symbol-scoped rather than mandate-scoped (03-domain-specification.md:443-445).
- Evidence: `VenueScope` is account-level. `project_acquisition_venue` permits a book source only
  through exact empty-book genesis (`venue.py:5844-5868`); transition projection rejects an old
  dual-mandate binding for a new one (`venue.py:5917-5926`). `CreateAcquisitionEffect` requires a
  pre-registered currentness (`authority.py:1102-1122`, `1485-1516`). Registration of an existing
  symbol requires a predecessor head (`authority.py:891-915`) and retains the original issued BUY
  slot; a later sealed BUY therefore remains stale. Public venue application rejects caller-built
  authority-changing inputs, so it cannot be used to manufacture a neutral bootstrap.
- Concrete effect: after the first account history exists, neither a second same-symbol mandate
  after terminal closure nor a first mandate for another flat symbol has a contract-compliant
  public bootstrap. The result is fail-closed, so this is not P0, but it prevents FR-02/FR-06
  conformance and blocks WO-0149 acceptance.
- Smallest complete resolution: ratify a bounded WO amendment that adds a scoped bootstrap source
  for a current canonical book/execution and an exact-flat rollover of a terminal same-symbol
  M1E state. It must preserve generic BUY refusal, use no audit scan or private input, and reset
  the retired slot only atomically after exact closure. The proposed shape is recorded separately
  in `PROPOSED-WO-0149-R1-BOOTSTRAP-AMENDMENT.md`; it is not active authority.

Verdict: BLOCK
P0: 0
P1: 1
P2: 0
Unverified: Runtime behavior and external CI were outside this static adjudication.
