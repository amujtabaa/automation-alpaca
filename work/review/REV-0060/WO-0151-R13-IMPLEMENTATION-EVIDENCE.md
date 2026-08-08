# WO-0151 R13 implementation evidence

Status: **fresh local candidate evidence -- independent acceptance pending**

Review base: `2208119083632ce26e58f966f6d7c3f3775f4aa7`
Branch: `codex/arch-reset-2026-07-r1`

## Root result

The completed-flat serial successor now advances the venue-owned protection
cursor from A to B in one private, zero-economic transition before authority
publishes B currentness. Authority installs the rolled venue and B currentness
atomically, binds the exact transition into the registration receipt, and
rejects a source-binding mismatch. Aborted successors retain the zero-transition
route.

The central acquisition-authority serving projection now rejects an old A book
paired with B currentness. B's first canonical BUY fill uses the unchanged
strict protection projector and creates fresh B `FLOOR_ONLY` protection.

The final compatibility correction preserves two distinct late-fact routes:

- a safely stand-downable or cancellable B BUY uses the existing atomic
  preemption receipt; and
- an exact open/unknown B parent remains owned and unresolved while the late A
  fact advances currentness and forces B-compatible `HARD_BAIL`, without
  fabricating cancellation authority or normal capacity.

No public API, export, authority command, protection API, runtime path,
persistence path, database path, history scan, or controller history was added.

## RED and remediation evidence

The initial focused RED command selected the completed-successor control, the
aborted A-to-B-to-C control, and the static private-boundary control. It ended
with two intended failures and one pass:

- completed successor returned zero rollover transitions instead of one;
- the two required private venue seams were absent; and
- the aborted successor remained green with zero transitions.

After the root implementation, the focused gate passed. Broader predecessor
execution then exposed and resolved four coupled compatibility controls:

1. acquisition refresh before a currentness entry must remain structurally
   current even when the target has non-acquisition venue history;
2. the central serving fence applies once acquisition currentness exists;
3. ordinary protection proof source identity must remain a fixed,
   mutation-testable domain-separated digest; and
4. post-rollover retired-fact preemption transitions owned by B use ordinary B
   protection reduction, while true cross-mandate catch-up keeps its existing
   reducer.

The first full pure-suite attempt also collected the frozen WO-0152 detector
before the contract's intended post-acceptance ordering. That sequencing error
is disclosed and is not treated as acceptance evidence. The run nevertheless
identified the exact open/unknown-parent waiting-resolution defect described
above. The detector remained byte-unchanged. After the bounded E2 correction,
its named failing case passed and the complete fresh pure suite was rerun.

## Fresh final local gates

| Gate | Result |
|---|---|
| Focused R13 completed/aborted/static RED controls | passed |
| R13 invalid-source, source-binding, receipt-count, ordinary-proof, and serving mutations | passed and restored |
| Complete allowed-path tests (`test_acquisition.py` + `test_import_boundary.py`) | passed |
| Unchanged WO-0152 B-first-fill and late-A-after-B detector | passed after bounded E2 correction |
| Full pure execution-core suite | 1,382 collected, exit 0 |
| Ruff check | exit 0 |
| Ruff exact-path format | clean |
| Mypy `app/execution_core` | exit 0; 10 source files clean |
| `git diff --check` | exit 0 |
| Work-order disposition, ledger, and PKL validators | exit 0 |

Frozen downstream pins after all runs:

- `tests/execution_core/test_acquisition_stateful.py` SHA-256
  `c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`;
- `work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md`
  SHA-256
  `d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb`.

The frozen detector is excluded from the R13 candidate and remains unstaged.

## External CI posture

The most recent exact-head GitHub Actions run inspected for this effort was PR
run #764, ID `31247505291`, at SHA
`051c758ce8b89985aa13cb1240e2fff64f5efac6`. Both Python 3.11 and 3.12 jobs
passed installation, Ruff, Mypy, import/governance checks, R2 conformance, and
all 5,947 tests. Both jobs failed only the unchanged 93% coverage gate at
91.32-91.33%. That run is retained negative coverage evidence and is not a
success claim for this candidate.

No threshold reduction, coverage exclusion, pragma, CI-workflow change, or
same-SHA rerun is proposed. Exact-head 3.11/3.12 success remains pending the
behavior-first WO-0152 E3 completion and paired E2/E3 93% closeout.

No database, SQL/DDL, credentials, broker/Alpaca/network activity, runtime
wiring, M2 work, merge, PR creation, deletion, cleanup, force-push, or rebase
was performed.
