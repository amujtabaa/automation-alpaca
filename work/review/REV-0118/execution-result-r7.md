# REV-0118 R7 — corrected boundedness fresh-file result

Status: **PASSED**

- Canonical source: `106fa7c4be39adc974af038264ed74d4349f19c7`, tree
  `782fcbe39ec2df524bce1012b2d818979c670bd8`
- Flag-only proof branch: `codex/m2-wo0170-rev0118-correction-sqlite-r2`
- Unlock commit: `94ca21f2cf0a786ac92e0ef15c8cb3966e0de1a8`, tree
  `ac046cc8590aa668e7e324f3d8c06f24d6cc2633`
- Branch publication: local equals `origin`
- Exact result: seven passed, zero failed
- Database boundary: fresh pytest-owned files under
  `.codex-ddl-gate-run/wo0170-rev0118-r7/pytest`; no `:memory:` or configured path

The proof includes both pre/post startup COMMIT-fault cases; dedicated dispatch-claim erasure,
acceptance-set omission, closure-chain omission, and independent fixed/published cursor-regression
cases; and one target/stress boundedness case. The latter creates a canonical checkpoint and
measures the actual load, decode, and compact restoration path at 1,000 and 10,000 unrelated rows,
including SELECT-count/elapsed growth, peak projection memory, and all selection/load plans at
both coordinates.

The proof branch differs from its canonical source only by the exact authorization flag. The DDL
remained 190,705 UTF-8 bytes at SHA-256
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; `schema.py` on
canonical remains blob `164de10ad9fef6ce37324840aff59b5b68c07d2a` with exact boolean `False`.

The proof branch and generated databases remain quarantined evidence and are not implementation
predecessors. No migration, runtime composition, credential, broker/network activity, order,
promotion, master merge, or M3 implementation occurred.

