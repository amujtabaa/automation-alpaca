# Claude Opus continuation — finish WO-0168c, then serial M2 closeout

This is a self-contained continuation prompt. Treat repository files and exact Git objects as
authority; do not infer authority from prior chat.

## Mission and seat

You are the primary implementation and first-pass fresh-review seat. Finish WO-0168c from its
accepted R20 contract, then proceed serially through WO-0168 (called WO-0168b in coordination),
WO-0169, WO-0170, terminal M2 closeout, and documentation-only M3 preparation. Codex retains the
governor seat for changed-DDL validation, disputed high-risk findings, and terminal M2 review.

Root-cause corrections are required; avoid band-aids and avoid complexity that has no contract or
failure-capable test. Never claim a work order complete from prose or inherited evidence.

## Repository and exact continuation identities

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Source branch: `codex/m2-i3-5-checkpoint-closure-r1`
- Accepted R20 contract commit/tree:
  `a6bba249912d81dac0862030e294a2970a76ecf2` /
  `72c0fa4a576afa1f9e70ca544e89f6c67940282f`
- R20 SHA-256:
  `4bee617d48ee0f0dbcfc6b9109b6a4aaf73d9ce6c335573e7914793d83e6a40e`
- R20 exact-head review commit: `cd759c2` (`REV-0077/result-r20.md`, ACCEPT,
  P0=0/P1=0)
- Current implementation WIP commit/tree:
  `9284bd90497a470dcaa23c7f246735b73286fb42` /
  `b0581f92fc2b457d4e7a73e879c47d97ab7ff8c7`
- WIP file hashes:
  - `checkpoint_codec.py`:
    `33662bc5b8df6f9912e0e8eae5d7185401edaecfe4970f1cd7cc3cb573440c1a`
  - `test_persistence_runtime_checkpoint_pure.py`:
    `5c1948309ed7c7ab02d6a86fe83a36c6e3c02a9640fd682d1a3a441906764ab2`
  - `test_venue_checkpoint_hardening.py`:
    `00cfa22df3fae4d7ed3df4ae265a85f00017560b589b1e96571780c8c35db4ae`

The WIP commit is deliberately incomplete. Do not review or describe it as WO-0168c completion.
The continuation branch may contain later documentation-only handoff commits; verify they are
descendants and inspect their paths.

## Isolated worktree and branch

Use a new worktree, never `master`, the active Codex checkout, or Ox Alpha:

```powershell
git fetch origin
git worktree add -b codex/claude-opus-m2-wo0168c-r1 `
  G:\dev-hdd\automation-alpaca-worktrees\claude-opus-m2 `
  origin/codex/m2-i3-5-checkpoint-closure-r1
```

Verify source head/tree before work and record the actual branch base. For each successor work
order, reuse this worktree but create a fresh branch from the exact accepted predecessor:

```text
codex/claude-opus-m2-wo0168c-r1
  -> codex/claude-opus-m2-wo0168b-r1
  -> codex/claude-opus-m2-wo0169-r1
  -> codex/claude-opus-m2-wo0170-r1
  -> codex/claude-opus-m2-terminal-r1
```

Do not rebase, force-push, delete branches, merge to master, or start a successor before the exact
predecessor is independently accepted and closed.

## Read order

1. `AGENTS.md` and `CLAUDE.md` safety core.
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`.
3. R1, R5 plus SQL manifest, R6, R13, then amendments R15 and R17-R20 under
   `work/queue/M2-EXECUTION-2026-08-21/`.
4. `work/review/REV-0077/result-r20.md`; earlier R14-R19 results are failure history, not the
   winner.
5. WIP source/tests named above and held SQLite test
   `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`.
6. Before each successor, read its queued WO and the accepted predecessor closeout. The repo file
   `work/queue/WO-0168-m2-i4-atomic-unit-of-work-effects.md` is the coordinated WO-0168b step.

## WO-0168c current evidence and exact remaining work

Supported interpreter is `.venv\Scripts\python.exe`, CPython 3.12.13. Before WIP, 96 focused pure
tests passed. After WIP and correction of two defective RED pins, the focused pure suite has exactly
two deliberate failures; all other 114 checks pass:

- nonempty venue projection still depends on/rejects source order;
- nonempty authority projection is absent.

WIP already supplies dormant acquisition/protection union decoding, exact R18/R19 dormant rows,
distinct dormant source-projection commitments, basic dormant cross-binding, and active acquisition
groundwork. Re-review it; it is not trusted merely because it exists.

Finish all of these at the root:

1. Venue: direct proof-selected projection for all 15 frozen current families, dense proof-order
   checkpoint ordinals for effects/owners, no `_validate_full`, `_effect_order`, `_owner_order`,
   rank map, whole ledger, or unselected history. Wire commitment uses
   `execution-core/m2-venue/state/v1`; owner provenance uses distinct
   `execution-core/m2-venue/source-owner/v1`; Authority VenueRef consumes only wire commitment.
2. Authority: project selected current authorization/paired claim state and all selected-scope
   manual/currentness/descriptor/slot state. Collections use R20 canonical semantic-key ordering.
   The four permitted supersets never receive whole-map cardinality checks. Terminal IDs nested in
   a reached current manual are bounded owner semantics and do not require terminal effects to be
   repository-selected.
3. Active acquisition: encode and direct-validate every selected unresolved generation, stream,
   and REQUEST/EFFECT/OWNER/ROOT/FACT lineage route; do not traverse unrelated registry/history.
4. Complete selected-record equality, absence-evidence, active/dormant protection, execution,
   controller, profile, scope, and cross-family bindings. Every mutant must fail for the intended
   reason.
5. Strengthen tests with real nonempty behavioral fixtures; static source-string pins alone are not
   sufficient. Preserve all existing tests.

Pure verification before the database gate:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/execution_core/test_persistence_checkpoint_codec.py `
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py `
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py `
  tests/execution_core/test_venue_checkpoint_hardening.py
.\.venv\Scripts\python.exe -m ruff check <changed paths>
.\.venv\Scripts\python.exe -m ruff format --check <changed paths>
.\.venv\Scripts\python.exe -m mypy app/
git diff --check
```

## Changed-DDL gate — still binding

Current static `SCHEMA_DDL` is exactly 178,791 UTF-8 bytes, SHA-256
`73dce64aa76172a9123a51819b668013d13850b86d40d7f19c678bb3171e9c88`.
`_GATE_DIGEST` remains intentionally unchanged. No changed schema has been installed or executed.

Before any SQLite-bearing test or changed-DDL install, stop and return to Ameen/Codex:

- exact candidate commit and tree;
- exact DDL byte count and SHA-256;
- changed-DDL summary;
- exact fresh-`tmp_path` file database commands, including held runtime-checkpoint and schema tests.

Every DDL byte change requires a new exact candidate and approval. Never use a configured database
or `:memory:`. After approval, run only the approved fresh-file gate first, collect RED/GREEN, then
broaden verification.

## Review and lifecycle protocol

At each work order:

1. freeze exact contract/allowed paths and obtain preflight review if design changes;
2. implement with RED/GREEN evidence;
3. use fresh-context review agents that did not author the patch;
4. require exact-head `ACCEPT`, P0=0/P1=0; reconcile P0/P1 at the contract/root level and re-review
   a new exact head;
5. update WO disposition, append-only ledger, lifecycle move, evidence, and review packet atomically;
6. commit, push, verify clean worktree except known user-owned temp directories, and verify
   local branch equals origin;
7. create the successor branch from that exact accepted predecessor.

Claude performs implementation and first-pass fresh-context reviews. Reserve Codex for exact DDL
validation, disputed critical findings, and terminal M2 review.

## Remaining serial chain

- WO-0168c: finish non-serving checkpoint, DDL gate, REV-0078, close/publish.
- WO-0168b / repo WO-0168: transaction-generation lease, one atomic unit of work, outbox/claim/
  receipt boundary; independent acceptance.
- WO-0169: startup owner lock, reconciliation, cold market recovery, owner-locked conversion of the
  inert checkpoint to serving authority; fake capabilities only.
- WO-0170: crash/restore/fault/boundedness closeout. A mandatory 24-hour soak that cannot complete
  remains honestly `NOT_RUN`; do not fabricate completion.
- Terminal M2: combined exact-head review and self-contained closeout manifest.
- M3 preparation only: reconcile queued WO-0171/WO-0172 entry contracts and dependencies against
  accepted M2. Do not implement M3.

## Allowed and forbidden authority

Allowed: ordinary reversible work inside the active WO, root-cause fixes, tests, governance,
normal commits/pushes, and fresh review agents. In-flight relevant issues may be resolved without
re-asking unless they alter a human-gated surface.

Forbidden without a new exact gate: changed-DDL execution, configured/existing DB access,
`:memory:` DB, migration, credentials, broker/network calls, orders, production runtime
composition, promotion, master merge, M3 implementation, rebase/force-push/history rewrite, branch
deletion, or weakening a test/contract to obtain green.

Start by verifying all identities and reproducing the exact two RED guards. Then finish WO-0168c;
do not start WO-0168b while WO-0168c has an unresolved design or review finding.
