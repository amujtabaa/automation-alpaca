# Five-surface acquisition and verification

Status: **VERIFIED FOR BOUNDED COMPARISON — AUTHORITY GAIN NONE**

## Container gate and exact file set

The quarantined tar was not listed or extracted until the human research decision and active
`WO-0164` gates passed. The tar was extracted once into an isolated system-temporary directory.
No extracted byte was copied into the repository or treated as accepted authority.

Container evidence:

| Check | Result |
| --- | --- |
| Actual tar SHA-256 | `f163ac6cca5a1dbebdf17d585bb9dfa3e2bd4197f048fbbafa1364ac69ab4604` |
| Independent binding in handoff 01 | Match |
| Independent binding in fresh-session prompt 03 | Match |
| Input-manifest file SHA-256 | `abba3d37ace9bd1ad38582404d8e6e418eaace5d29def2b23bdfd7b56312a048` |
| Tar row in input manifest | **Malformed 63-character token; retained as negative evidence** |
| Inner manifest rows | 6 valid lowercase 64-character rows |
| Extracted regular files | Exactly 6; no extra file |
| Inner hash matches | 6 of 6 |

The manifest defect is not waived: the invalid container row fails a strict SHA-256 parser. The
container was admitted only because two separately frozen handoff artifacts record the same correct
64-character digest and the actual tar matches it. Every inner file then matched its valid row.

## Exact surface hashes

| Surface | Exact extracted path | Bytes | SHA-256 | Verification |
| --- | --- | ---: | --- | --- |
| WO-0158b | `work/active/WO-0158b-m2a3-governing-authority-audit.md` | 10,852 | `fe33af020f110a57f2913098d15c9eb5fe938fba1a204336f13f91226025e07b` | Matches manifest |
| Frozen authority inventory | `work/queue/M2-PERSISTENCE-CRASH/00-frozen-authority-and-owner-inventory.md` | 4,963 | `9196050f251772ee5276fc698443a05b79a60de3d9ab578dad837625e5ffdb2a` | Matches manifest |
| Cold-restart/authority contract | `work/queue/M2-PERSISTENCE-CRASH/06-governing-authority-and-cold-restart-contract.md` | 65,671 | `1fda8cc3614ccd7b85a9962e9cfea89767c99e28f2a5641707a5e7f63d229842` | Matches manifest |
| ADR-023 | `docs/adr/ADR-023-bounded-market-occurrence-authority.md` | 33,302 | `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf` | Matches manifest and current accepted repo byte-for-byte |
| ADR-024 | `docs/adr/ADR-024-broker-roles-execution-connection-profile.md` | 17,728 | `93a3baecfbdd63efc722b6d9159e2d7f2c18e970be02145fee09a48a15011c13` | Matches manifest and current accepted repo byte-for-byte |

The sixth inner file, `AUTHORITY-MANIFEST.sha256`, is supporting comparison evidence at SHA-256
`4cd8b8062dd8575334e63364e2fed62b1387821cbcb9a9aaca96a533069a8b08`.

## Independent 89-row reproduction

The contract contains 90 lines beginning with `G|`: one grammar header plus 89 canonical rows. The
header is excluded exactly as the contract states. The 89 rows were joined in printed order with
one LF after every row and encoded as UTF-8.

| Measure | Reproduced value | Expected | Result |
| --- | ---: | ---: | --- |
| All `G|` lines | 90 | 90 including grammar header | Match |
| Excluded grammar header | 1 | 1 | Match |
| Canonical rows | 89 | 89 | Match |
| Canonical payload bytes | 12,724 | Independently derived | Recorded |
| Canonical SHA-256 | `95e826f2ce22aa3125ce258a457ea22ea9f7dc529be2d7386b11c324d3cda5ed` | Same | Match |

First canonical row:

`G|AGENTS.md|3-17|AI-OS scope, source priority, and smallest packet|CONTROLLING|follow active WO, fresh evidence, and smallest context packet`

Last canonical row:

`G|work/queue/ARCH-RESET-2026-07/04-persistence-and-cutover.md|1146-1154|retention|PRESERVED|read only history and no raw feed promise`

## Surface findings

### WO-0158b

The work order is useful lifecycle provenance but remains `ACTIVE`, pre-review, and tied to the
obsolete branch, old Gate-A decisions, and forbidden `REV-0067`. It cannot be resumed or closed as
the successor. Its semantic objective is re-derived here under `WO-0164`.

### Frozen inventory

The 17-row inventory accurately freezes c9 source/ADR bytes and old audit routing. It is not a
member-complete implementation contract and its application-file hashes are not implementation
authority. A future post-Gate-B implementation order must freeze the then-current exact source
surface rather than reuse these hashes.

### Cold-restart/authority contract

The contract preserves valuable A01-A13 current-state rules, C01-C12 cold-restart rules, CR-01
through CR-19 negative controls, and H01-H08 transaction/startup/cutover rules. It is not accepted:

- it routes canonical ADR bodies through old Gate-A provenance instead of the current ratification
  index;
- it incorrectly classifies accepted ADR-024 as a conditional Gate-B proposal;
- it carries obsolete D2-A/D4-A/Stage-3/ADR-025 and REV-0067 paths;
- its source universe predates the frozen R01-R20/S01-S04 aggregate and completed human overlay;
- its candidate hashes and old work-order graph are invalidated; and
- its historical SQL vocabulary remains evidence only.

These defects require a fresh candidate rather than acceptance of the old contract.

### ADR-023 and ADR-024

Both exact tar bytes match current repository bytes. Their semantics are retained from current
accepted authority. The candidate reads their acceptance from
`ARCH-RESET-2026-07-RATIFICATION.md`, not from the deliberately unchanged proposed/draft text inside
the ADR bodies.

## Scope proof

- No c9 commit, source file, test, schema, SQL, runtime file, or old candidate hash was imported.
- No configured database, parser, application, broker, credential, or network path was used.
- The extraction directory is temporary comparison state, not a new archive or authority source.
- The exact obsolete branch remains untouched pending independent acceptance and the complete
  retirement gate.
