# Independent WO-0151 R13 implementation acceptance result

## Verdict

**ACCEPT**

- P0: 0
- P1: 0
- P2: 0

This verdict accepts only the exact immutable candidate identified by
`WO-0151-R13-IMPLEMENTATION-CANDIDATE-MANIFEST.md`. It does not close WO-0151,
satisfy the pending paired 93% CI/coverage gate, or accept any excluded dirty-tree
path.

## Findings

No P0, P1, or P2 findings.

## Candidate and authority authentication

- `[reproduced-live]` Branch and review base were exact:
  `codex/arch-reset-2026-07-r1` at
  `2208119083632ce26e58f966f6d7c3f3775f4aa7`. The base resolved as a commit whose
  parent is the R13-R1 activation publication commit.
- `[reproduced-live]` The candidate manifest rehashed to the requested
  `b8fa0ab942ca32ec1a4aabb3c3f8d352ff33980437e72b456f26b5695ad11b8c`.
- `[reproduced-live]` The contract, clean semantic manifest, semantic acceptance,
  and activation acceptance pins rehashed exactly to, respectively,
  `240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90`,
  `c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222`,
  `71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5`,
  and `82627d88422374f0230e8f00926b397b06104b32042a993ea21f453fc9403c59`.
- `[reproduced-live]` Accepted ADR-020 R2, ADR-021 R2, and ADR-023 R1 rehashed
  exactly to `eab0c18c165cc457845658e1e5a2a7bb92250773755b3973b796e0b3aee1824a`,
  `b2527dc57d3544262625691003bc1374b6d72383802011927c4a1790ae13945d`, and
  `9a61d4f9541620b386bd6af49b8b9d8f42123c571807583154b7a87b01c4140b`.
- `[reproduced-live]` All eight candidate paths rehashed exactly:

  | Candidate path | SHA-256 |
  | --- | --- |
  | `app/execution_core/venue.py` | `b10e0a5e8c55dbbedbfdb7156a5a6f8d9bef83867212f12299575aa67bf7dedb` |
  | `app/execution_core/authority.py` | `6e028f3c80c0d27af5b5cb4a5ec6336a0bdff9c876d11ce670c6369c840e118a` |
  | `app/execution_core/acquisition.py` | `09cd9bb33fff2dcdcfadb68da837ea9afa108aac2fe75fface73b5121f07e0e0` |
  | `tests/execution_core/test_acquisition.py` | `ae86b23b8cbdc26f7c47930956a8b8b364bb76bae34c6f081ae5dc16968a8512` |
  | `tests/execution_core/test_import_boundary.py` | `1ffda4dd5655401c95ec1eee20e25e0e424929ea7dfdd007b37ac49881b7e0d0` |
  | `work/review/REV-0060/WO-0151-R13-IMPLEMENTATION-EVIDENCE.md` | `e837e776b335821086990130f8a1aeae0c2da4a72a6c8ad38ccd4bc515028b03` |
  | `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `4861058a508545d25e6283eac8918d89cb68a5e433497450b58da5eb1270da8a` |
  | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` | `f36d143f20323e2acc23898c47adbbc4c0953d2ba4a27a689e3a7f6f0abdec25` |

- `[reproduced-live]` The excluded frozen detector and its freeze record remained
  byte-exact at `c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`
  and `d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb`.
  The detector's pre-existing tracked delta is therefore separated from, and is
  not silently incorporated into, the eight-path R13 candidate.

## Independent semantic re-derivation

- `[static]` Venue owns the two private seams and the source-kind proof domain
  (`app/execution_core/venue.py:2754`, `:8155`, `:8185`). The rollover requires
  an exact scope, distinct predecessor/successor mandates, a consistent flat
  execution, the exact predecessor cursor and registration binding, and no live,
  pending, waiting, unknown, stand-downable, or cancellable owner. It changes
  only the scope cursor/proof ledger, carries zero raw/economic delta, and binds
  the resulting proof to the exact predecessor and successor.
- `[static]` Authority is the single importer and sole call site. Its registration
  path (`app/execution_core/authority.py:5943`, call at `:6131`) validates the
  authentic zero-delta transition and exact registration/proof commitment before
  constructing one next state containing both the rolled venue book and B
  currentness. Acquisition then requires exactly one transition and exact
  receipt binding for a completed successor, while requiring zero transitions
  and the unchanged venue object for an aborted successor
  (`app/execution_core/acquisition.py:2366`, `:4063`). Refusal paths return the
  predecessor components.
- `[static]` The central serving projection directly checks the scope cursor
  (`app/execution_core/authority.py:2920`, venue predicate at `:8155`). An old-A
  book combined with B currentness is non-serving, while the absence of
  currentness remains structurally usable; admission additionally requires the
  central serving result (`app/execution_core/authority.py:3161`). No generic or
  public input route exposes the private registration/rollover command.
- `[static]` B's first fill still passes through the ordinary strict projector and
  produces a fresh B `FLOOR_ONLY` cursor. Late retired-A fill/correct/bust facts
  retain A routing and advance A economics once while B remains the sole live
  generation; the protection result is `HARD_BAIL` and supplies no normal B
  capacity (`app/execution_core/acquisition.py:4348`).
- `[static]` The exact open/unknown-parent branch is recognized at
  `app/execution_core/authority.py:7499-7516`: it declines to invent cancellation
  authority and continues through currentness registration. The existing safe
  stand-down/cancellation predicates retain the atomic preemption path. The
  downstream frozen detector was inspected read-only and constructs the
  after-B-first-fill late-A case; it was not executed.
- `[static]` The diff introduces no public export/API, venue-to-authority import,
  history scan/controller history, runtime, persistence, database, network, or
  E3-source candidate edit. The only application/test edits are the five
  activation-authorized paths; the remaining three candidate paths are the
  evidence and bounded work-order records.

## Failure-capable controls and focused checks

- `[reproduced-live]` Nine exact non-stateful nodes completed with exit 0. They
  cover completed and aborted successors; wrong scope/mandate, nonflat and
  inconsistent execution, live ownership, wrong source binding, rebound ordinary
  proof, duplicate transition, serving-predicate mutation, B first fill, late
  retired-A fill/correct/bust, atomic successor preemption, and the private
  import/call/export boundary. The selected nodes were in
  `tests/execution_core/test_acquisition.py:1401,3793,3979,4079,4337,4421,4505,4699`
  and `tests/execution_core/test_import_boundary.py:8018`.
- `[reproduced-live]` Ruff check passed and Ruff format check reported all five
  candidate Python files already formatted.
- `[reproduced-live]` Mypy reported no issues for the three candidate application
  modules.
- `[reproduced-live]` `git diff --check` passed for all seven tracked candidate
  paths.
- `[reproduced-live]` Candidate, detector, and freeze-record hashes remained exact
  after these checks.

## Sequencing disclosure and evidence limits

- `[static]` The implementation evidence explicitly treats the premature frozen
  detector collection as a process error and negative diagnostic, not acceptance
  evidence. The freeze record and unchanged detector bytes corroborate that
  disclosure. Only the subsequent clean full pure-suite rerun is presented in
  the candidate evidence as support for local success.
- `[unverified]` In accordance with the request, this seat did not execute
  `tests/execution_core/test_acquisition_stateful.py`, the claimed full 1,382-test
  pure-suite rerun, database/SQL/DDL fixtures, broker/network activity, runtime
  wiring, external CI, or coverage. Consequently, the candidate evidence's final
  full-suite count and detector-pass transcript were not independently reproduced
  here. The disclosed pre-candidate external CI coverage miss also remains
  negative evidence, and the paired 93% candidate CI/coverage gate remains open.
