# REV-0063 remediation-03 independent review

Review target: `codex/m1-5-broker-alignment-local-r1` at
`f7b955be591c31ddc7cb211a8b9e1141eb01896e`, against
`5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`.

This is a findings-only clean-room review. Earlier `result*.md` artifacts were
preserved as negative audit provenance and were not used as acceptance evidence.

## Verified evidence

- `git branch --show-current` and `git rev-parse` matched the requested branch,
  base, and target. The target diff adds only the M1.5 documentation/review
  packet; it changes no `app/`, `tests/`, migration, dependency, or CI path.
- Every one of the 13 manifest-covered paths rehashed to its recorded SHA-256.
  The separately rehashed manifest is
  `1da5d1631c01e837df8572135cb3e53b9eedca5b64e0779dff01de2b96eb4755`.
  The proposed ADR body is
  `d3bd94f1784196a67877cfc4ab8906b12cbe357265acaf8de6b801a42e121d91`.
- `git diff --check <base> <target>`, `check_work_order_scope.py`,
  `check_ledger.py`, and `check_pkl.py pkl` passed.
- A parser-free origin probe implemented the stated DNS-label and port grammar.
  It rejected `https://127.1`, `https://[0:0:0:0:0:0:0:1]`,
  `https://%65xample.com`, malformed labels, explicit `:443`, and invalid
  retained ports; it accepted lower-ASCII DNS origins with no port and with
  `:8443` (12/12 expected outcomes).
- Independent literal framing probes produced an execution-profile payload of
  391 bytes with SHA-256
  `17c9f761fc547f5ca9591fb504b887bca6033c96d9679eaa2b16ebc15f84a58e`,
  and a market-source payload of 196 bytes with SHA-256
  `84cbe34282eaf6144357d3fdc1bcc1d2308a704fa81d700fc4a84d11d7f9bc14`.
  Adding the execution digest as a framed field changed its result, confirming
  the specified self-output exclusion is material.
- The candidate names only
  `work/review/REV-0063/result-remediation-03.md` as the terminal accepting
  result and expressly prevents prior results from substituting for its hash or
  zero-P0/zero-P1 verdict. The earlier result files remain present. No secret
  value was found in the candidate packet.
- The candidate preserves ADR-022's Alpaca Paper M2--M8 selection and exact
  mismatch-denial posture, leaves M1 closed and M2 inactive, retains separate
  market-source authority, and excludes live trading, runtime/DDL/credential
  work, routing, failover, and deferred broker integrations.

### [P1] The committed account coordinate cannot prove the selected broker account

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md:89`
- Requirement: ADR-022 requires the supervisor-owned fence to name the exact
  Paper account and requires startup and every final claim to compare every
  fence field, refusing any mismatch before broker I/O
  (`docs/adr/ADR-022-reset-beta-scope-cutover-governance.md:45-51`).
- Evidence: static-reasoning. The proposed canonical encoding classifies
  `account_identity` as an opaque 32-byte lowercase-hex value and says it is
  activation-minted and never digest-derived (lines 89-92). It supplies no
  immutable, non-secret mapping or equality rule from that local value to the
  provider-returned account identity, although it later requires the exact
  Paper account to remain a profile coordinate (line 125). The M2 contract
  consequently says to re-derive and compare an account without defining what
  external value can satisfy the profile coordinate.
- Impact: an M2 implementation has no failure-capable, provider-neutral rule
  for rejecting a different broker account. It can either compare only the
  local opaque alias, which does not establish the ADR-022 external-account
  fence, or introduce an uncommitted representation of the broker account.
- Resolution: define one immutable, non-secret, profile-committed binding from
  `account_identity` to the exact broker-returned account identity, including
  byte grammar, equality/re-derivation, and refusal behavior; alternatively
  make the canonical external-account assertion a distinct committed coordinate.
  Preserve the local opaque ID if desired, but do not use it as an unspecified
  substitute for the external account comparison.

## Unverified

- Full repository pytest and Python 3.11/3.12 exact-head CI were not completed
  in this environment: the documented `.venv\\Scripts\\python.exe` is absent,
  and the available interpreter is Python 3.14.5. The candidate changes no
  executable code.
- Human exact-hash ratification, future M2 persistence/refusal controls, M4
  credential-gated capability evidence, and M9 feasibility evidence remain
  intentionally unperformed and are not implied by this review.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
