# WO-0151 exact-head coverage remediation 02 candidate manifest

Status: **FROZEN LOCAL FOCUSED-RECHECK CANDIDATE**

Tracked parent and branch HEAD:
`ec69b0d80a073d981d583a9193b181d5f4cb2255`.

GitHub Actions run `31174280408` (#739) executed that exact SHA on unchanged
Python 3.11 and 3.12 jobs. Both jobs passed all 5,929 tests, Ruff, mypy,
import-boundary, governance, and R2 controls, then failed only the repository
93% branch-coverage ratchet at 90.46%. This candidate corrects that exact
evidence gap without reopening WO-0151 architecture or behavior policy.

## Exact candidate

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/authority.py` | `eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19` |
| `app/execution_core/protection.py` | `1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e` |
| `tests/execution_core/test_acquisition.py` | `2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb` |

The tracked delta is exactly those three authorized WO-0151 paths: 499
insertions and no deletions. The other frozen WO-0151 implementation paths and
all accepted contracts remain unchanged.

## Root corrections

1. `PositionProtectionState` and `ProtectionVenueProjection` now require all
   retained boolean coordinates to be exact `bool` values. Previously their
   commitments normalized by truthiness, so a forged truthy non-boolean could
   retain the same commitment.
2. `AcquisitionEffectTerms` now has one canonical owner authenticator that
   reconstructs its economic leaf and compares the derived commitment.
   `AcquisitionEffectPermit` authenticity uses it, so quantity or price cannot
   diverge from the sealed BUY economics through a stale cached digest.

## Failure-capable controls

The candidate adds one deterministic field-mutation harness and five compact
owner-boundary tests. They cover:

- acquisition mandate, generation, registry, lineage, route, controller, and
  controller-state coordinates;
- authority currentness, refresh, admission, effect terms/permit/descriptor,
  active/inactive slots, claim/exit permits, fact preemption, claim receipt,
  all three currentness-registration sources, and their sealed commands;
- protection compatibility, state, contexts, semantic rebase, venue
  projection, transition, preemption intent, and protection-exit intent;
- venue acquisition context/projection/relation, protection-transition proof,
  and active/consumed bootstrap records;
- direct construction and subclassing refusal for every named owner-minted
  acquisition boundary.

Each retained field receives a type-faithful mutation and a wrong-type
mutation where its owner seal is authoritative. Raw cross-owner source
carriers use the complete serving matcher or a type-only mutation so the tests
preserve the ratified layered-authentication boundary rather than inventing a
new recursive trust model.

The controls found and pinned both root defects above. One attempted direct
predecessor-venue revalidation was disproved by the ratified sibling-refresh
path and removed; no over-strict semantic change remains.

## Fresh evidence

- Pure execution-core suite before the final test-only headroom additions:
  1,358/1,358 passed, exit 0.
- Every test modified by the final headroom additions passed in focused runs.
- Pure branch coverage increased from 86.54% to 89.51% (display 90%); the
  repository-wide exact result remains delegated to unchanged exact-head CI.
- Ruff check and exact-path Ruff format: passed.
- Mypy `app`: no issues in 87 source files.
- Import Linter: six contracts kept, zero broken.
- Static import-boundary suite: 31/31 passed.
- `git diff --check`: passed.

No database-capable fixture, SQL/DDL, database engine, credential, broker,
Alpaca, network, runtime wiring, persistence, M2, merge, PR, deletion, cleanup,
force-push, or rebase was used.

This manifest does not itself satisfy exact-head CI, effectively close
WO-0151, or activate WO-0152.
