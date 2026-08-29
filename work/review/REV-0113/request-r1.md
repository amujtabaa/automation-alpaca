# REV-0113 R1 — correction-only exact-head preflight

## Exact target

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168-atomic-uow-r1`
- Original contract candidate: `9485256811e633578c0059afe15b160c4555d8b6`
- Accepted finding-preservation parent: `cb30fa4eeab193597936c79022e61ab5813b3427`
- Correction candidate: `088b8bc5ea0bf37c7a40a266c8941fd3ccf907b2`
- Correction tree: `949dba2d3892486020071f4be9dda9c6d843b259`
- Corrected work-order SHA-256: `223157502b228ea25224f507340e9c3b11fbb5d0791f0db508f9498880885a63`
- Original result: `work/review/REV-0113/result.md`, SHA-256
  `838ee22d61707e1eeb6f35af247778052729c7d2d1a172fc2f3b0f92c35d7413`

Verify every identity. The packet-hosting commit after `088b8bc5` is not contract substance. Review
the exact correction diff `cb30fa4eeab193597936c79022e61ab5813b3427..088b8bc5ea0bf37c7a40a266c8941fd3ccf907b2` together with the original P1 only.

## Bounded question

Determine only whether REV-0113 P1 is resolved at the executable-contract level:

1. Does the corrected contract require one exact operation-keyed owner proof before any reducer can
   read a deliberately omitted checkpoint member?
2. For manual operations, does the three-case partition bind the targeted manual identity to the
   active checkpoint row, retained semantic/input/outcome evidence, or proven absence?
3. Does the shared-kernel requirement prevent unbound `_manual_by_id` noise from changing either
   the public-owner route or UOW route while preserving one decision engine?
4. Are the two payload-equal counterexamples now mandatory RED controls?
5. Does the correction avoid historical-map serialization, generic callbacks/write plans, DDL
   changes, or a second reducer engine?

Do not reopen unrelated design questions or seek new taste findings. A finding is blocking only if
the correction leaves the original reproduced behavior implementable under the contract or creates
a concrete contradiction with accepted authority.

## Authority and output

This is findings-only, fresh-context, static correction verification. Do not edit implementation,
the original `request.md`, or `result.md`. Create only
`work/review/REV-0113/result-r1.md`. Do not use SQLite, create/access a database, execute DDL or
held suites, load credentials, call a broker/network, place orders, or implement WO-0168.

End with exactly:

```text
Verdict: ACCEPT | BLOCK
P0: <count>
P1: <count>
P2: <count>
Unverified: <concise limits>
```

Implementation may start only if this correction review returns zero open P0/P1.
