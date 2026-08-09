# REV-0063 - independent remediation-02 re-review result

## Reviewed identity

- Branch: `codex/m1-5-broker-alignment-local-r1`
- Base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`
- Candidate: `e2843c38eda506762e6e6b0318e1c4cce8b43d57`
- Candidate manifest SHA-256 actually reviewed:
  `7b2945e887ba2b183ae7b22c6e69195870f646659805f066a83217cb47107a48`
- Proposed ADR SHA-256 actually reviewed:
  `f997ffcae2011300f13d4844ab8064c73c58f641a04772d0f5e673901254131f`
- Accepted authority SHA-256 values actually reviewed:
  - ADR-020 R2: `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653`
  - ADR-021 R2: `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c`
  - ADR-022: `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798`
  - ADR-023 R1: `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf`

## P0 findings

No P0 findings.

## P1 findings

### P1-1 - Origin host canonicalization remains implementation-selected

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md:96-98`
- Requirement: remediation-02 requires exact, independently constructible origin bytes and no
  valid value that silently changes under library URL normalization.
- Evidence: `[reproduced-live]` The new rule fixes scheme, host case, path/query/fragment absence,
  and default-port treatment, but never defines the grammar or canonical form of `host`. The
  strings `https://127.1`, `https://[0:0:0:0:0:0:0:1]`, and
  `https://%65xample.com` satisfy every enumerated ASCII/case/path/port condition; only the
  undefined adjective "canonical" could reject them. Node.js v24.16.0's WHATWG URL
  implementation reserialized them respectively as `https://127.0.0.1/`, `https://[::1]/`, and
  `https://example.com/`. An RFC-3986-style validator can instead treat at least the first and
  third spellings as registry-name forms. The line-108 prohibition on library reserialization
  prevents one consumer behavior but supplies no failure-capable rule by which independent M2
  validators decide whether these input spellings are valid.
- Impact: two conforming implementations can accept different origin domains or hash different
  bytes for the same endpoint. Startup/final-claim profile comparison can therefore depend on an
  unratified URL parser or host-normalization choice at the exact Paper/live refusal boundary.
- Resolution: define the v1 host language and canonical validation completely. The smallest beta
  rule is lowercase ASCII DNS labels only, with exact label/total lengths, no percent encoding,
  trailing dot, legacy IPv4 form, or IP literal, plus an explicit port range; require rejection
  unless the supplied string is already in that form. If IPv4/IPv6 are required, define their one
  accepted textual forms explicitly rather than delegating them to a URL library.

### P1-2 - Exact-hash ratification still points to the immutable negative result

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/07-human-ratification-request.md:18-20` and
  `work/queue/M1-5-BROKER-ALIGNMENT/README.md:13-18`
- Requirement: human ratification must bind the exact independently accepted review result and
  every semantic candidate change; immutable prior negative results must remain evidence rather
  than be presented as the accepting verdict.
- Evidence: `[reproduced-live]` The ratification template hardcodes
  `work/review/REV-0063/result.md` while immediately asserting `Verdict: ACCEPT`. That immutable
  file has SHA-256
  `74bfd435770045d24aedd4a83b1c4d9aa058fa2dcf00a0382511fcd9c0995d97` and actually ends
  `ACCEPT-WITH-CHANGES`, P1=2. The also-immutable remediation-01 result has SHA-256
  `a9623907f5e0c0c4fc5f9bc89a4f7ed1b9f995c4452b1d577780027bfa609183` and ends
  `ACCEPT-WITH-CHANGES`, P1=1. Any possible final `ACCEPT` belongs to
  `result-remediation-02.md`, but the ratification contract and README exclusion/provenance text
  name only `result.md`; the manifest comments likewise describe only that original result. The
  human therefore cannot execute the required template truthfully and bind the final independent
  verdict hash without inventing an unreviewed routing amendment.
- Impact: the exact-hash gate can either hash negative evidence while claiming it is an acceptance,
  or substitute an unlisted addendum path. Either route defeats the packet's drift-prevention
  claim at the gate that authorizes ADR landing and authority reconciliation.
- Resolution: make the ratification contract name and hash the current terminal accepting result
  addendum, while retaining the original and remediation-01 results as immutable negative
  provenance; reconcile the README and manifest exclusion language with all request/result
  addenda. Because those are semantic candidate edits, regenerate the manifest and obtain a fresh
  focused independent review before ratification.

## P2 findings

No P2 findings.

## Executed verification

- `[reproduced-live]` `HEAD` and the named branch resolved to the exact candidate; the named base
  and candidate objects exist, and the worktree was clean before this reviewer-owned result was
  created.
- `[reproduced-live]` All 12 manifest-covered files matched their recorded lowercase SHA-256
  values. The self-excluded manifest and proposed ADR hashes are recorded above.
- `[reproduced-live]` The canonical ADR-020 through ADR-023 file hashes matched the controlling
  values in `ARCH-RESET-2026-07-RATIFICATION.md`.
- `[reproduced-live]` A reviewer-only Python 3.14.5 constructor, using no production helper,
  independently encoded every listed non-output field. The execution example terminated at 12
  parts/416 bytes with SHA-256
  `ee194c99f0fa651a196a36850eef60fa54b187572749293669d6f254deadc601`; the market-source
  example terminated at 7 parts/205 bytes with SHA-256
  `26e6329bb53a968e5e439626774d04f6f43212234085d54c4d4bcd0504114544`. Domain and per-part
  length framing, order, NFC UTF-8 text, decoded identity/digest bytes, output exclusion, and
  lowercase output are otherwise constructible and non-self-referential.
- `[reproduced-live]` The base-to-candidate scope check passed against `WO-0157`; `git diff
  --check`, `check_ledger.py`, and `check_pkl.py pkl` passed. The semantic correction changes no
  application, test, DDL, database, runtime, credential, dependency, workflow, or broker file.
- `[static-reasoning]` Apart from the ratification-routing defect above, the correction preserves
  Alpaca Paper as the sole M2-M8 mutation provider, M1 closure and M2 inactivity, one
  mutation-eligible profile, market-source separation, evidence-before-eligibility, the M4 human
  credential/outbound-call gate, and the prohibitions on live trading, routing, failover,
  cross-provider inventory, and second-writer authority.

## Unverified

- Full pytest, Ruff, mypy, import-boundary, coverage-ratchet, R2-oracle, and exact-head Python
  3.11/3.12 CI were not run. This candidate is documentation-only; none of those post-ratification
  gates is used as acceptance evidence here.
- No M2 schema/runtime implementation, SQL/DDL, database, credential, broker/network call,
  external CI, or abandoned Cloud PR #12 material was inspected or used.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
