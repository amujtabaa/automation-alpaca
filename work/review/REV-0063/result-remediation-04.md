# REV-0063 remediation-04 independent review

Review target: `codex/m1-5-broker-alignment-local-r1` at
`34eba03265410783f0c5c7a35f2fd2e303a06d7b`, against
`5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`.

This is a findings-only clean-room review. I re-derived the candidate from the
repository authority and exact review request. Earlier `result*.md` artifacts
were read only as immutable negative provenance and were not used as
acceptance evidence.

## Reviewed identity and hashes

- The checked-out branch and `HEAD` matched the requested branch and target;
  the base and target are commit objects, and their merge base is the supplied
  base. The range contains six commits. The worktree was clean before this
  reviewer-owned result was created.
- Candidate manifest SHA-256 actually reviewed:
  `9f77a39faa6fe8b9f8772efc7a3c6495e80f2b754652831343f7be9b936e352d`.
- Proposed ADR SHA-256 actually reviewed:
  `93a3baecfbdd63efc722b6d9159e2d7f2c18e970be02145fee09a48a15011c13`.
- Accepted authority SHA-256 values actually reviewed:
  - ADR-020 R2:
    `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653`;
  - ADR-021 R2:
    `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c`;
  - ADR-022:
    `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798`;
  - ADR-023 R1:
    `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf`.

## Findings

No P0, P1, or P2 findings.

## Executed verification and disproof evidence

- `[reproduced-live]` All 14 manifest-covered paths rehashed from exact bytes
  to their recorded lowercase SHA-256 values. The manifest remained correctly
  self-excluded and every prior reviewer result remained outside candidate
  meaning. Git history showed each prior result added once with no subsequent
  edit in the reviewed range.
- `[reproduced-live]` The base-to-target diff changes only the allowed M1.5
  documentation/review packet. It changes no application, test, migration,
  dependency, workflow, database, credential, or runtime path. `git diff
  --check`, `check_work_order_scope.py`, `check_ledger.py`, and `check_pkl.py
  pkl` passed.
- `[reproduced-live]` An independent literal account-assertion constructor used
  domain `broker-account-identity/v1`, four-byte big-endian domain framing,
  eight-byte big-endian part framing, and the exact four-part order. For
  `ALPACA`, `PAPER`, adapter contract `1.2.3`, and the non-secret test scalar
  `acct-É-42`, it produced 88 bytes and SHA-256
  `c1a456a9bedb668769c52c8bb0a72cc1b882533a7cbdbae13d11b3867a54d88c`.
  A different account, label, leading/trailing-space form, case-changed form,
  and percent-encoded form all produced unequal digests. The decomposed
  non-NFC spelling was rejected; normalizing it would have recreated the valid
  digest, confirming that reject-before-normalize is load-bearing.
- `[reproduced-live]` A parser-free extraction validator passed 10/10 boundary
  cases: one valid scalar and 256 supplementary-plane scalars were admitted;
  missing, plural, non-string, empty, non-NFC, ASCII-control, and 257-scalar
  values were refused. The selected versioned adapter contract normatively
  names one provider-authoritative extractor; labels, aliases, and substituted
  extractors are not alternative equality authorities. The extractor and its
  returned exact bytes are mutation pins, and changing the selected extractor
  is independently classified as a material new-generation recutover change.
- `[reproduced-live]` The account digest was inserted as decoded 32 bytes into
  an independently framed 12-part execution-profile example. The result was
  414 bytes with SHA-256
  `b75ce0afb735da9f50afdd5b89db172b64070adb90753a6dea83f8a46b63aed7`.
  A separate seven-part market-source example was 209 bytes with SHA-256
  `9da8e18ef3380e1624911db07c4206cccce546b80cf369b9d3aa0381ada7394b`.
  Both profile outputs terminate outside their own preimages; all listed
  non-output fields are bound, and opaque profile/deployment/fingerprint
  identities remain activation-minted rather than digest-derived.
- `[reproduced-live]` A parser-free origin validator produced the stated unique
  answer for 17/17 cases. It accepted lowercase DNS origins with default 443 or
  retained `:8443`; it rejected legacy IPv4, IPv6 literal, percent encoding,
  malformed/empty/trailing-dot labels, explicit `:443`, leading-zero/out-of-
  range ports, uppercase host, path, and non-`https` scheme. No URL-library
  normalization was needed.
- `[reproduced-live]` No account-ID-shaped raw value was found in the changed
  packet, and manual review found no selected external account instance in the
  profile, candidate, manifest, ledger/ratification material, or public review
  artifacts. The only concrete account scalar above is reviewer-local test
  data recorded in this result, not a selected provider account.
- `[static-reasoning]` ADR-022's exact provider/environment/account/origin/
  credential fence survives. The profile remains exactly `ALPACA`/`PAPER` for
  M2--M8; account commitment mismatch refuses preflight, the first provider-
  authoritative session assertion, mutation eligibility, final claim, and
  later broker requests. Every other profile coordinate remains mandatory at
  startup and final claim, and any material profile or extractor change routes
  only through a separately reviewed new application generation and recutover.
- `[static-reasoning]` The candidate retains one immutable selected profile per
  application generation and at most one mutation-eligible profile, with no
  hot swap, standby, routing, failover, simultaneous provider, cross-provider
  inventory, second writer, or historical-authority revival. Execution and
  market-source profiles remain separate; capability requirements are frozen
  before append-only evidence, and complete matching M4 evidence is required
  before `PAPER_MUTATION_ELIGIBLE`.
- `[static-reasoning]` M1 remains closed and unchanged, M2 remains inactive,
  and no DDL, database, serialization, runtime, credential, broker/network,
  live-trading, Webull/FIX/IBKR/Robinhood/Tradier implementation, or merge
  authority is introduced. First-occurrence canonical execution truth and the
  single-writer/final-claim rules are unchanged.
- `[reproduced-live]` The current README, work order, remediation-04 request,
  and ratification contract route acceptance only through
  `work/review/REV-0063/result-remediation-04.md`; prior negative results remain
  present and cannot supply or substitute for the terminal result hash.

## Unverified

- Human exact-hash ratification is intentionally pending and is not implied by
  this review.
- Future M2 DDL/schema, implementation, known-answer/mutation controls,
  crash/replay behavior, startup/final-claim enforcement, and exact
  provider-response extractor integration do not yet exist and therefore were
  not runtime-verified.
- M4 credential-gated Alpaca Paper capability evidence, the actual selected
  Paper account/origin values, broker/network behavior, and M9 feasibility
  evidence were intentionally not obtained.
- Full pytest, Ruff, mypy, import-boundary, R2-oracle, coverage-ratchet, and
  Python 3.11/3.12 exact-head CI were not run. The documented local virtual-
  environment interpreter is absent; the available Python 3.14.5 interpreter
  was used only for the AI-OS static checks. The candidate changes no
  executable code, and those broader gates remain post-ratification/exact-head
  obligations.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
