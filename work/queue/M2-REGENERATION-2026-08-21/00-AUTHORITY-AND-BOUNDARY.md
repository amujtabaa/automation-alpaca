# Fresh M2 Gate-A authority and boundary record

Status: **CANDIDATE — REV-0069 REQUIRED — AUTHORITY GAIN NONE**

Work order: `WO-0164`

Branch: `codex/m2-regeneration-gate-a-r1`

## Purpose

This packet replaces the obsolete c9 planning candidate with a fresh, documentation-only M2
Gate-A candidate. It derives from accepted `master`, the accepted ADR/PKL authority, and the
human-ratified research overlay. It does not implement M2, authorize SQL/DDL or a database, select
a new provider, contact a broker, or permit a merge to `master`.

## Repository identity and ancestry

| Item | Exact value | Result |
| --- | --- | --- |
| Accepted base | `177ea5fcd959b9e7d7d5a3172070f90f89ece963` | Live local and remote `master` matched at activation |
| Accepted base tree | `99338a7832509645f17ed4f51c511e7dffb6c41f` | Matched |
| Activation commit | `d1380e0529a95ae04997c24c6d793d00ca765ec2` | Contains only WO-0164 and append-only ledger activation |
| Successor ancestry | `merge-base(successor, master) = 177ea5f...` | Accepted master is an ancestor |
| Obsolete checkpoint | `c9b27dca6236606b3792dfc75c6418fd735be6cb` | Non-authoritative comparison evidence only |
| c9 ancestry | `c9` is not an ancestor of the successor | Passed |
| Common base with c9 | `177ea5fcd959b9e7d7d5a3172070f90f89ece963` | No c9 commit imported |

The candidate commit and tree are recorded externally in the review request after the packet is
frozen, avoiding self-reference.

## Human research authority

The original aggregate decision form remains immutable at SHA-256
`0ff73c46b7fdf66d79d11d7ef493a73bc2a1d5415da8ac512dc86bca32614d8d`.
The completed post-freeze human overlay is separately bound at SHA-256
`32adab8c1e4e3d92610ef1e33628f1ef5e1664d873c91db190ab44b4aff39947`.
The old aggregate manifest was not rewritten and does not claim to cover the overlay.

The human decision:

- ratifies the research advisory as a basis for separately authorized planning;
- requests a later explicit exclusion/quarantine policy for non-trade financial facts;
- assigns numeric-risk policy preparation to Ameen Mujtabaa as project owner and sole human
  operator, without accepting any numeric limit now;
- selects `PKG-MIN`, then `PKG-HARD`, with `PKG-ADV` strictly conditional;
- selects no provider/vendor/platform/model comparison and no specialist engagement;
- authorizes this fresh M2 planning proposal and later exact obsolete-branch retirement only after
  its recorded gate; and
- preserves `NOT_READY / HOLD_ALL_PROMOTION` and grants no implementation or trading authority.

## Current accepted repository authority

The embedded proposed/draft text inside canonical ADR bodies is immutable provenance. Acceptance
comes from `ARCH-RESET-2026-07-RATIFICATION.md`; the old c9 contract's contrary label treatment is
not current authority.

| File | SHA-256 | Current treatment |
| --- | --- | --- |
| `AGENTS.md` | `163d9b36b654cea69530943d17b30e4ba7463ca8a7bc19ac2cd09934281444d3` | Controlling process and safety adapter |
| `CLAUDE.md` | `8bbc762fb29abc5cfb488e64b27b7a4c442e464c49fcf97e9463d3d61d7919fd` | Controlling safety core |
| `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` | `5a6a04bd975a8d0aae1a40670c228365f4fdc580442e2554235f7ddf950e0f98` | Acceptance and lineage index |
| `docs/adr/ADR-020-current-state-execution-kernel.md` | `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` | Accepted current-state/direct-lineage authority |
| `docs/adr/ADR-021-position-protection-liquidity-execution.md` | `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c` | Accepted protection/controller authority |
| `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md` | `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798` | Accepted beta/cutover/governance authority |
| `docs/adr/ADR-023-bounded-market-occurrence-authority.md` | `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf` | Accepted bounded market/cold-restart authority |
| `docs/adr/ADR-024-broker-roles-execution-connection-profile.md` | `93a3baecfbdd63efc722b6d9159e2d7f2c18e970be02145fee09a48a15011c13` | Accepted provider-neutral profile boundary; M2 implementation still inactive |
| `pkl/architecture/architecture-map.md` | `3671b0397ceec84d7bc2c605cdafb5acd597c17da30166b5ddc9c9ee7b1b4697` | High-authority current map |
| `pkl/architecture/testing-model.md` | `2f119a5cd8dcf3819729ed94c09acdfa8161a856cf5afcc02b97ecf07ef1a222` | High-authority determinism/test boundary |

## Frozen research bindings

| Artifact | SHA-256 | Use |
| --- | --- | --- |
| `CANONICAL_ARTIFACTS.sha256` | `91e74aaabfc20a0915fba27dba87758be6f41b71d4db4aa09e20b215394facc7` | Original aggregate boundary |
| `05_ARCHITECTURE_AND_INTERFACE_SYNTHESIS.md` | `b6019d86f3afb66d3658c3fb0161ba2523750da6aaf5b02dc947a834a45dd992` | Architecture hypothesis and interface obligations |
| `08_ROADMAP_BUILD_BUY_AND_SPECIALIST_RECOMMENDATIONS.md` | `d948c617acb4d2deede7c9ab21ef6a53f368759ce62070cdf03ce7af5df7ee9c` | Package sequencing and no-selection posture |
| `10_FINAL_RESEARCH_REVIEW.md` | `dbb14cee46febcaa8f00439ce0ce5b36e5183998700449756fe13e29223e375b` | Final blocking advisory and M2 regeneration rule |
| `REVIEW_RESULT.md` | `8edc6f27736ca10f0572e2d450bc907923cea73c76f41c3365c1529c6b17a224` | Independent aggregate `ACCEPT`, authority gain none |

All experiments remain `NOT_RUN`; R16 G0-G7 remain `NOT_EVALUATED`; exact lifecycle costs remain
`UNKNOWN`, never zero. Research acceptance does not close its P1/P2 findings or readiness holds.

## Quarantine and comparison boundary

The quarantined tar hashes to
`f163ac6cca5a1dbebdf17d585bb9dfa3e2bd4197f048fbbafa1364ac69ab4604`,
matching the exact independent binding in both handoff artifacts. Its input-manifest file hashes to
`abba3d37ace9bd1ad38582404d8e6e418eaace5d29def2b23bdfd7b56312a048`.

The manifest's tar-container row is retained negative evidence: its token is malformed at 63
hexadecimal characters (`...f048fbafa...`) and omits one `b` relative to the actual independently
bound digest (`...f048fbbafa...`). The external manifest is not rewritten. Container admission used
the two independent 64-character handoff bindings; every inner file was then verified against its
own valid 64-character manifest row. Details are in `01-FIVE-SURFACE-VERIFICATION.md`.

## Hard boundary

- This is schema-neutral planning. No SQL text, DDL execution, parser claim, migration, database,
  runtime composition, broker call, credential, order, or capital action is produced.
- Alpaca Paper remains the inherited M2-M8 execution profile; that is not a new provider selection.
- No Webull, IBKR, FIX, routing/failover, vendor/model comparison, or procurement work is scheduled.
- Historical SQL and c9 prose are evidence and disproof inputs only.
- Signal Seat remains disabled and unmounted.
- Only first-occurrence canonical `FILL` and valid predecessor-linked broker-authoritative
  `TRADE_CORRECT`/`TRADE_BUST` revisions change economics.
- One sequenced writer, claim-before-I/O, direct indexed current proof, acceptance-set closure, and
  source-authoritative cold restart remain mandatory.

## Terminal meaning

An independently accepted packet reaches
`READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`. That means only that the fresh M2 plan is
ready for a later human hash decision. It does not activate an implementation work order or merge.
