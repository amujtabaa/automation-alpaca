# M2 terminal closeout and M3 entry checkpoint

Status: **ACCEPTED — M2 COMPLETE; M3 PREPARED, NOT ACTIVATED**

Date: 2026-08-29

This is the compact terminal record for the serial M2 persistence milestone and the
documentation-only preparation of M3. It binds accepted repository evidence; it does not merge,
promote, activate M3, compose a runtime, access a configured database, contact a broker, or
authorize an order.

REV-0119 independently accepted exact terminal candidate
`8499845f668c0e0b71100e2420d000b0657606a6`, tree
`79382c952ceacf5e777c13a7a44f4e3ccddb32f7`, with P0=0/P1=0/P2=0 and
`Unverified: NONE`. Reviewer result SHA-256:
`0ec9364bec497a7b7d24e35a0b3bb5a6db492955a4c954d5c9c9af709707415c`.

## Repository and terminal candidate

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- WO-0170 lifecycle closeout: commit
  `6edd8fbae0cd0eb7868826cfd0450860c63df70e`, tree
  `8c918f3a1cf46333ed0eef79d3ef51d0503de88a`
- Final WO-0170 implementation/test source:
  `c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree
  `2d5c662f569ec3ee792216863fe46213551773a8`
- REV-0118 accepted candidate: `2051afe2bbc21918fac6b69875e0a536fe722e49`, tree
  `2d3fef0011412ec432fd26f43f526be6946ad00c`
- REV-0118 final result: `ACCEPT`, P0=0, P1=0, P2=0, `Unverified: NONE`; result SHA-256
  `14ebde3fb24498b0b9d2272c486eda7efef5a7524f9b84431cfd7741cd9a2a23`
- Closeout manifest: `harness/m2/M2-CLOSEOUT-MANIFEST.md`, SHA-256
  `a72f5e92820415c48bf404063fe6a4d1dbe6397c02f5439424a43b7cc823eb66`, blob
  `e708e782f980d4eecd79ba148a11e5a3a884e304`
- Canonical DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; schema blob
  `164de10ad9fef6ce37324840aff59b5b68c07d2a`; execution authorization flag exact `False`

## Accepted serial M2 chain

| Order | Accepted implementation source | Lifecycle closeout | Independent review |
| --- | --- | --- | --- |
| WO-0165 / M2-I1 | `3c85b17bc04fa587cac1995c8999155d6583006b` | `2e47702c926515bf587aa71de987a3fb879e4d75` / tree `e8d2b0d4a8f734934252b8719cb0241574d03654` | REV-0070, zero open P0/P1 |
| WO-0166 / M2-I2 | `b00c2dec5fab7f87fd30aecc130a29bec600bf39` | `0a7b5ae324c34be488da24478f95e2658a1bb894` / tree `9e76edce54a661b5685f5837a53371ae5e1d858b` | REV-0071, zero open P0/P1 |
| WO-0167 / M2-I3 | `3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043` | `0777fab62598f85ce189f40eb1a69319791282c2` / tree `1db6fe831fc7d7785d032c224072b131cd5643e9` | REV-0073, zero open P0/P1 |
| WO-0168 / M2-I4 | `f637295e42be8430edb14be03c0dd23d24bef394` | `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51` / tree `de844054db45d03c73889d986185cab651cbc386` | REV-0115, zero open P0/P1 |
| WO-0169 / M2-I5 | `ae6277b38fb8e9e9823e512373a8c2d19938c7e9` | `0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130` / tree `b5f1042247804ad9fde4347c8729d5bde29a172d` | REV-0117, zero open P0/P1 |
| WO-0170 / M2-I6 | `c7e394f52782a9b398ed89bfdc55b45bc09499b4` | `6edd8fbae0cd0eb7868826cfd0450860c63df70e` / tree `8c918f3a1cf46333ed0eef79d3ef51d0503de88a` | REV-0118, zero open P0/P1 |

Every implementation source and closeout above is an ancestor of the terminal candidate. Earlier
failed or flag-true proof branches remain quarantined evidence and are not predecessors.

## M2 completion argument

The definition in `01-M2-M3-EXECUTION-MAP.md` is satisfied at the implementation-evidence
boundary:

| Required property | Accepted evidence |
| --- | --- |
| One sequenced writer and pure semantic owner | WO-0168's authenticated eight-operation unit of work; repository writes remain subordinate and caller-transaction-owned |
| Direct bounded current proof | WO-0167 direct repository hydration plus WO-0170 target/stress plans and actual checkpoint load/decode/compact restoration |
| Atomic fact/state/effect/claim/receipt boundary | WO-0168 unit-of-work contract and WO-0170 pre/post-COMMIT old-or-new-complete fault comparisons |
| No blind resend after ambiguity/restart | Immutable claim/effect evidence, startup reconciliation, and fault/replay equality in WO-0168 through WO-0170 |
| Fail-closed lock/startup/recovery | WO-0169 owner lock, phase ladder, current checkpoint restoration, unknown-effect reconciliation, and ADR-023 cold recovery |
| Exact profile-scoped Paper authority | Durable profiles/schema and startup bindings retain Alpaca Paper as the sole M2-M8 mutation profile; no broker access occurred |
| Fresh fault/restore/boundedness proof | R4 259 fresh-file cases, R8 seven correction cases, 2,310 ordinary cases, 61 R2 cases, static/import/governance gates |
| Honest unpassed surfaces | 24-hour soak remains `NOT_RUN`; the former R16 G0-G7 label is retired as untraceable under `40-R16-G0-G7-LABEL-DISPOSITION.md`; operational/promotion surfaces remain unauthorized |

This is a persistence/startup milestone, not a production-readiness or trading-readiness claim.

## REV-0119-reviewed M3 preparation artifacts

| Artifact | Exact candidate identity | Purpose |
| --- | --- | --- |
| `01-M2-M3-EXECUTION-MAP.md` | blob `09ea6d572caefe9301f0c820a6b6e2ca1a7e1e33`; SHA-256 `685eebf48efb8c668fa7372674064e494fc88d9f77f777fa45d1d720e9d87f41` | Current serial status and terminal gates |
| `WO-0171-m3-p1-deterministic-simulator-tape-clock.md` | blob `e0b337ee41624353a3baf0022009680fc06e7aa7`; SHA-256 `99e938998fba25f87512940faef42713d26b81b87f287e3190c20c56ccd099c5` | Deterministic offline simulator, tape, and clock through the accepted M2 seam |
| `WO-0172-m3-p2-semantic-replay-regression-corpus.md` | blob `cb21a523c209fc846c9be0bd44e65dd3ca809e8a`; SHA-256 `7206b6f2a9954b47509db09dbf730683f84330e2e17bda933e5109c2150951d8` | Semantic comparator, mutant obligations, minimizer, and permanent corpus |

Those hashes identify the exact reviewed candidate. The post-acceptance lifecycle commit changes
only candidate/pending labels to accepted/ready-blocked labels and records REV-0119's result and
disposition; it changes no M2 or M3 contract requirement.

The M3 entry checkpoint freezes the existing public M2 operation, unit-of-work, startup, and inert
checkpoint-codec surfaces by exact source blobs in WO-0171. Simulator and comparator code remain
outside direct repository/schema/current-state mutation authority. A needed M2 seam change must be
proposed and independently reviewed; it cannot be smuggled into M3 as test infrastructure.

The eight roadmap histories are mapped to typed simulator observations. AR-02 through AR-09 are
mapped to exact semantic distinctions and failure-capable mutant obligations. M3-P1 owns input
representability and deterministic transport behavior; M3-P2 owns semantic verdicts, trace
comparison, minimization, and corpus retention. This separation avoids a second engine without
creating a new framework merely for planning.

## M3 activation gates

Neither M3 order is active. After REV-0119 acceptance:

1. WO-0171 still requires a separate human M3-P1 activation from the exact accepted terminal head,
   a fresh `codex/` branch, exact allowed paths, and a fresh review identity.
2. WO-0172 still requires accepted WO-0171, replacement of its predecessor placeholder with that
   exact head/tree, and a separate human M3-P2 activation on another fresh branch.
3. One worktree may be reused serially, but each order starts from its exact accepted predecessor.
4. No activation grants credentials, configured-database access, broker/network calls, orders,
   runtime composition, promotion, `master` merge, M4 work, or live/shadow authority.

## Honest residuals and forbidden inferences

- The 24-hour soak is `NOT_RUN`; the successful short driver smoke is not a substitute.
- The former `R16 G0-G7` label is retired as untraceable under
  `40-R16-G0-G7-LABEL-DISPOSITION.md`; it is not an unresolved implementation or readiness gate.
  The concrete R16 contract and ratified manual rule remain unchanged.
- No configured or in-memory database was used for this terminal documentation step.
- No DDL byte, authorization flag, application source, test source, or accepted execution result is
  changed by M3 preparation.
- No Paper account was observed; no credential, SDK, network, broker, or order path ran.
- No merge, promotion, runtime composition, or M3 implementation is implied by terminal acceptance.

## Minimal read order for a later M3 activation

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. This terminal checkpoint and `harness/m2/M2-CLOSEOUT-MANIFEST.md`.
3. `01-M2-M3-EXECUTION-MAP.md`.
4. The exact M3 work order being activated; WO-0171 before WO-0172.
5. Accepted ADR-020 through ADR-024 and only the roadmap/war-game clauses linked by that work order.
6. The frozen public M2 source surfaces and directly necessary tests named by the activated order.

## Terminal review disposition

REV-0119 completed one fresh, finite documentation/governance review and returned `ACCEPT` with no
findings. It verified exact identities, the M2 completion argument, M3 seam/scenario completeness,
honest residuals, and absence of accidental M3 or operational authority. It ran no SQLite, held
suite, configured/in-memory database, broker/network path, or M3 code. No correction round was
needed.
