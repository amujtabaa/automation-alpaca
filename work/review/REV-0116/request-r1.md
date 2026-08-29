---
type: Review
review_id: REV-0116
work_order_id: WO-0169
review_mode: correction-only static pre-implementation architecture re-review
status: REVIEW
authoritative_candidate: 9867e45fe53540c06cd821760f27e2e844be716a
---

# REV-0116 R1 — verify the three accepted WO-0169 preflight corrections

Return to the same fresh review seat. Verify only the three accepted P1 findings from
`result.md`, their direct regressions, and whether the added scope is necessary and minimal. Do not
restart broad design review, invent optional features, edit files, commit, push, open SQLite,
create a database, install DDL, run held suites, or implement source.

## Exact binding

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Original activation candidate: `974198587791454f7fc3ea5dbe0a8d640d22c9ce`, tree
  `e83ff0caeb84c6dfdd7310af7558467e19ec71fb`.
- Corrected candidate: `9867e45fe53540c06cd821760f27e2e844be716a`, tree
  `8c2e237aca44928ea04ec10cfd122f869535cb97`.
- Corrected active-WO blob: `7078a3364c778c0ba70e74690f0eb67653aa4b98`; file SHA-256
  `37ac07f51ca414fa7ea03d0827d4a14d77094d6e7bc5e888dc28dfb742e41bbd`.
- Original result raw SHA-256:
  `5cf497c636a66efee779f75935f80e8e65762a2b163a48ccd1745466cc7ac98c`; blob
  `d1c42097ffccc7097adc4cac98529eb66d026070`.
- DDL remains inherited and unchanged at 190,705 bytes / SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Minimal read order

1. `work/review/REV-0116/result.md` and `disposition.md`.
2. The complete corrected active WO.
3. Only the exact seams cited by the original findings in `checkpoint_codec.py`,
   `repository.py`, and `unit_of_work.py`.
4. ADR-023 only if needed to disprove one of these corrections.

## Finite verification

1. Confirm `StartupRequest` now carries immutable application/profile selection coordinates,
   owner acquisition precedes hydration, private owner restoration requires current repository
   proof plus byte-identical reprojection, non-serving returns leak no context, and retry reloads
   the latest committed checkpoint rather than caller-retained C0.
2. Confirm reconciliation completeness comes from the authenticated current-unresolved union in
   the checkpoint selection proof, including qualifying OPEN, INVALIDATED, and closed-late-owner
   rows, while only exact claimed identities are queried and no effect is resent.
3. Confirm exact subscription-currentness is bound to acknowledgement, fence, source profile,
   stream generation, and sequence mode and is checked after baseline commit and immediately before
   `SERVING`.
4. Confirm the added checkpoint-codec/owner/test paths are required for that proof-bound cold
   hydration and do not introduce a public owner API, generic framework, DDL change, new durable
   input domain, or unrelated implementation scope.

Report only a demonstrated incomplete/bypassable correction or regression caused by these exact
changes. End:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. Deposit the findings-only response as `result-r1.md`; do not
modify prior review artifacts.
