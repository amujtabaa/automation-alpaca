# REV-0078 request — canonical, frozen post-remediation candidate

Date: 2026-08-24 · Author: implementing seat (Claude)
Supersedes: `request-r1.md` and its amendment (mutable bounds — REV-0078 P1-7)

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**, fresh exact-head
review after the R1 BLOCK remediation. If it reaches P0=0/P1=0, this same document is the DDL
gate packet returned to Ameen for the separately recorded fresh-file execution approval.

## Frozen identity — immutable, no `HEAD` authority

```text
Candidate:  ce5cb38d5b2fe38d957252df21d5f0a0889801fc
Tree:       5d2f7d2925c4f2d855fd1ae7161588420a600ec0
Base:       344c32b
Range:      344c32b..ce5cb38d5b2fe38d957252df21d5f0a0889801fc
Branch:     codex/claude-opus-m2-wo0168c-r1 (identity is the commit, not the ref)
```

## DDL gate identities (for Ameen's execution approval, after P0=0/P1=0)

```text
SCHEMA_DDL sha256:   2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL bytes:    178755 (UTF-8)
Catalog digest pin:  c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
Approval literal:    tests/execution_core/approved_schema_digest.py (single transcribed source)
Q-manifest:          13 queries, per-query SHA-256 pinned in
                     tests/execution_core/test_persistence_runtime_checkpoint_directness.py
Approved commands (fresh tmp_path files only; no :memory:, no configured DB):
  pytest tests/execution_core/test_persistence_schema.py -p no:randomly
  pytest tests/execution_core/test_persistence_repository.py -p no:randomly
  pytest tests/execution_core/test_persistence_directness.py -p no:randomly
  pytest tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py -p no:randomly
```

Per gate bundle Amendment 2, all earlier database runs are noncompliant and their results are
`NOT_RUN` for gate purposes; none has run since the R1 verdict.

## Commits in range (29)

```text
ce5cb38 fix(rev-0078): disposition the BLOCK verdict -- splice bindings, gate hygiene, corrected arms
5bfec3a Merge remote-tracking branch 'origin/codex/rev-0078-result-r1' into codex/claude-opus-m2-wo0168c-r1
c725dfb docs(wo-0168c): record Ameen's ratification of the R16 manual rule, pin its last refusal
1dbcc96 review: block REV-0078 checkpoint candidate
5d3df2b fix(repository): pin join order across the remaining selection queries
7bee810 docs: record the suite floor and the stateful runtime cost
f0dc2f1 test(directness): close the last of the debt the DDL gate was hiding
7acf328 test: move Q9's pin in the static query manifest
657ab17 docs(rev-0078): move the acted-on findings to a closed table
ae00985 docs(rev-0078): extend the review bound past the corrected candidate
2082e4e fix(checkpoint): bind closure heads to their selected records
8998db9 fix(checkpoint): replace monotonic-map cardinality checks with real key relations
fff2dc3 docs: ratify the third DDL digest and open the self-approving gate finding
04cc8e8 docs(rev-0078): record the in-process adversarial pass and its dispositions
083dc11 fix(checkpoint): act on the adversarial review's P0 and P1 findings
b86115b test(repository): close the WO-0168c debt the DDL gate had been hiding
a87235f fix(repository): pin Q9's join order, and correct the bounded-plan rule
49dd271 docs(rev-0078): author the WO-0168c implementation review request
2cfbce0 test: clear the three remaining WO-0168c verification gaps
0e1c835 fix(checkpoint): drive the SQLite proof through the production projector
aab4130 fix(schema): make the DDL installable and re-pin both approval digests
9447dd4 docs(wo-0168c): HUMAN-GATE checkpoint bundle for the schema DDL
faa964e test: prove the projected venue and authority wires pass their own validators
720d390 feat(checkpoint): project the authority emergency grant row
1597152 feat(checkpoint): R20 s2 authority AcquisitionDescriptors and AcquisitionSlots
8e81cbe feat(checkpoint): R20 s4 venue ExecutionReconciliations
0d16933 feat(checkpoint): R20 s4 venue BootstrapTargets
ab67de4 feat(checkpoint): R20 s4 venue Reconciliations
d22bf0e feat(checkpoint): R20 s4 venue ClosureHeads
```

## Changed paths (22)

```text
app/execution_core/persistence/checkpoint_codec.py
app/execution_core/persistence/repository.py
app/execution_core/persistence/schema.py
tests/execution_core/approved_schema_digest.py
tests/execution_core/test_persistence_directness.py
tests/execution_core/test_persistence_repository.py
tests/execution_core/test_persistence_runtime_checkpoint_directness.py
tests/execution_core/test_persistence_runtime_checkpoint_pure.py
tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py
tests/execution_core/test_persistence_schema.py
tests/execution_core/test_persistence_write_capability.py
work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md
work/review/FINDING-preexisting-suite-floor-2026-08-24.md
work/review/FINDING-protection-stateful-replay-disposition.md
work/review/FINDING-schema-approval-gate-is-self-approving.md
work/review/REV-0078/HANDOFF.md
work/review/REV-0078/disposition-r1.md
work/review/REV-0078/in-process-adversarial-pass-r1.md
work/review/REV-0078/request-r1.md
work/review/REV-0078/result.md
```

## What changed since the reviewed `5d3df2b`

`result.md` (merged unmodified at `5bfec3a`) and `disposition-r1.md` carry the finding-by-finding
record. In brief: P1-1/P1-2 splice bindings landed with nine caught mutants; P1-3's parser got a
negative lookahead plus a six-case pure control; P1-4's duplicate guards are tested and its two
absent-row arms were **removed as wrong with evidence** (`recovery.py:963`; the initial bootstrap
checkpoint input) — the one point where this seat disputes a finding's arm rather than
implementing it, argued in the disposition for this review to judge; P1-5 released-paths
amendment; P1-6 was ratified by Ameen at `c725dfb` adopting the reviewer's own recommended text;
P0-1's static component (transcribed literal, AST anti-tautology control, Amendment 2) is in;
P2-1/2/3 corrected.

## Author evidence at the frozen candidate (pure/static only)

```text
pytest tests/execution_core/test_persistence_runtime_checkpoint_pure.py      114 passed
pytest tests/execution_core/test_persistence_write_capability.py               8 passed
pytest tests/test_import_boundaries.py                                         6 passed
pytest ...checkpoint_sqlite.py -k resolves_indexed_by (string parsing only)    1 passed
PYTHONPATH=. python tests/r2_conformance_oracle.py                             exit 0
ruff check · mypy app/ (95 files) · lint-imports (6 kept)                      clean
git diff --check 344c32b..ce5cb38d5                                       clean
```

## Known limitations, stated

- Every SQLite-bearing suite is `NOT_RUN` at this candidate — deliberately, per the R1 gate
  disposition. The edited fixtures (approval literal) are verified statically only: the literal
  equals the DDL text hash, and the AST control refuses the self-derived spelling.
- The EXPLAIN-based unbounded-plan negative control (P1-3) is authored into the bounded-plan test
  but exercises only at the approved gate run.
- The suite floor (3 pre-existing failures) and the three tracked FINDING files stand unchanged.
- The 24-hour soak remains WO-0170's `NOT_RUN`.

**READ ONLY for the reviewer:** no edits, no result authored by this seat, no database activity
on this seat's behalf.
