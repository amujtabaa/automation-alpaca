# WO-0168c → Codex review handoff

Prepared 2026-08-24 by the implementing seat (Claude) for Ameen to hand to Codex.

---

## 1. What to review

```text
Branch:      codex/claude-opus-m2-wo0168c-r1
             (mirrored to claude/m2-execution-continuation-vz91tk at the same commit)
Base:        344c32b   feat(checkpoint): R20 s4 venue HumanCoverages
Candidate:   see `git rev-parse HEAD` on that branch — 25 commits since base
Bound:       344c32b..HEAD
Work order:  work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
Contract:    R20, accepted by REV-0077 R13 at aa2f0225 with P0=0/P1=0/P2=0
```

The formal request is `work/review/REV-0078/request-r1.md` plus its Amendment 1. This handoff is
the orientation layer: what changed, what I already know is wrong, and where I most want to be
contradicted.

**REV-0077 already accepted the contract.** Re-opening contract questions is out of scope and is
how a review treadmill starts. The question here is whether the *implementation* matches it.

---

## 2. Scope completed

R20 §2 and §4 are done. The projector carries **no whole-family refusal anywhere**: all fifteen
venue families and every authority collection project from proof-selected direct keys.

Families added: `ClosureHeads`, `Reconciliations`, `ExecutionReconciliations`, `BootstrapTargets`
(venue); `AcquisitionDescriptors`, `AcquisitionSlots`, `EmergencyGrant` (authority). Nested forms
newly built for the bootstrap row: venue scope, execution binding, the 6-member inert transition
cursor, the 10-member symbol authority summary, and the 25-member inert transition proof.

Human-gated actions taken, each with recorded authorization:

| Surface | Authorization | Record |
| --- | --- | --- |
| Schema DDL: two `RAISE(ABORT,…)` messages joined to single literals | Ameen, 2026-08-24 | `35-WO-0168C-HUMAN-GATE-DDL.md` |
| `_SCHEMA_CATALOG_SHA256` re-pin | same | same |
| `_GATE_DIGEST` re-pin | ratified **after the fact** | same, Amendment 1 |
| Repository SQL: join order pinned with `CROSS JOIN` | Ameen, 2026-08-24 (Q9 first, then the rest) | this handoff, §4 |

---

## 3. Where I most want to be contradicted

Ranked. If review time is limited, spend it top-down.

### 3.1 Eight whole-map cardinality checks removed — **the highest-risk change in the diff**

I deleted eight refusals. Three I had added in this work order; five predate it. My argument:

- `_PersistentKeyMap` exposes `get` / `insert_new` / `replace_existing` / `size` and **no deletion
  of any kind** (`fills.py:577`), so every one of these indexes is monotonic.
- The repository selects `effect.disposition IN ('OPEN','INVALIDATED')` plus `CLOSED` effects
  carrying a late-admitted owner (`repository.py:4084`, `:4090`).
- Therefore one ordinary closed effect leaves a permanently unselected entry, and comparing map
  size against the reached count refused **every book from that point on**.

Maps affected: `_reconciliation_by_input`, `_execution_reconciliation_by_input`,
`_closure_head_by_leg`, `_owner_by_leg`, `_economic_high_water_by_leg`,
`_acquisition_correlation_by_root`, `_broker_coverage_by_root`, `_human_coverage_by_root`.

**What I want checked:** is a monotonic index with no deletion operation correctly classed as an
R16 §2 *permitted authenticated superset*? And is R15 §2's "requires exact current-map equality"
genuinely subordinate to the sentence three lines later — "rows not directly referenced by the
selected current subset are audit history and **are omitted**"? I read the second as governing. If
that reading is wrong, eight refusals need restoring and several tests are pinned backwards.

### 3.2 The replacement key relations

Removing a refusal is only safe if the relation it stood in for is actually proved. Each removal is
paired with one:

- **Coverage index→ledger.** Both coverage maps store a ledger *slot number*. They dereferenced it
  and emitted the row without proving it belonged to the indexing root — a spliced index could emit
  another root's effect, leg, and cumulative quantities, sealed as authentic. Now compares the
  reached fact's root, the broker head fact, and the human corroboration.
- **Reconciliation admission.** The derivations returned bare input tuples, so the consumer could
  only test *membership* in the selected set; a stale reconciliation on a different selected leg of
  the same scope satisfied that. Now carries the referencing row's identity (leg for fills, scope
  for registry outcomes) and requires equality.
- **Closure heads.** `selection.closure_heads` appeared **nowhere** in the codec — the only
  DB-selected venue family projected purely from in-memory state. Now bound on owner, ordinal,
  kind, and predecessor presence, refusing in all three directions.

**What I want checked:** are these sufficient to carry what the cardinality checks were wrongly
asked to carry? I believe they are strictly stronger, but I chose the fields.

### 3.3 Contract conformance of the large new rows

The 25-member `BootstrapTargetActive`, its nested 25-member transition proof, the 22-member
effect permit, the 16-member currentness row, and R2's 4-member `AcquisitionSlot` collapse of
contract-07's separate descriptor/active members. An in-process pass counted these member-by-member
and found them conformant; that pass was mine and is not independent.

---

## 4. Repository SQL — join order pinned

27 base-table joins inside CTE bodies changed `JOIN` → `CROSS JOIN`. In SQLite that is
syntactically identical with an `ON` clause; its only effect is to disable the join-order
optimizer, keeping the bounded CTE as the outer loop.

Measured against the corrected bounded-plan rule: **12 unbounded base-table scans → 0.** No query
lost a `SEARCH`, and none gained a base-table automatic index.

The control that found this was itself wrong twice, and both corrections matter:

1. It first excused every `USING INDEX` scan, on the reasoning that an index bounds the pass. A
   **full** index has one entry per table row, so scanning it is the same unbounded pass.
2. It then excused every **partial** index. `ix_venue_owner_checkpoint_late` is partial on
   `admitted_after_effect_closed = 1`, which never clears, on a table with a no-delete trigger.

Only a predicate that *clears as work completes* bounds a scan. The two qualifying indexes are now
named explicitly with an assertion that they really are partial.

**Worth an independent look:** plans are measured on a near-empty database with no `ANALYZE`.
`CROSS JOIN` removes the planner's freedom permanently, which is right if the CTE is always the
smaller side — and it is, by construction — but that is my reasoning, not a measurement at scale.

---

## 5. What I got wrong, disclosed

The in-process adversarial pass (three fresh-context agents, `in-process-adversarial-pass-r1.md`)
found P0-class defects in my own work. Treat this list as evidence of where my judgment failed,
and probe those areas harder:

| I claimed | Actually |
| --- | --- |
| Reconciliation maps are exact current indexes needing size equality | They are append-only supersets; the check refused every reconciliation-required book — the quarantine state a checkpoint exists to preserve |
| `trg_kernel_checkpoint_versioned_replace` is "unreachable through this path" | Reachable; it loses SQLite's BEFORE-trigger order race. My change left it with zero coverage repo-wide |
| Partial index ⇒ bounded scan | False for a predicate that never clears |
| Repository SQL carries no digest pin | It does — a per-query SHA-256 manifest. I broke Q9's pin and the full-suite run found it, not my verification |
| "4 failures, otherwise green" (full suite) | Counted only `^FAILED` through a `tail` pipe; missed setup `ERROR`s entirely |

Every item above is fixed. I list them because a reviewer should weight my other confident claims
accordingly.

---

## 6. Evidence

```text
tests/execution_core/test_persistence_runtime_checkpoint_pure.py    all pass
tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py  55 failures -> 0
tests/execution_core/test_persistence_schema.py                     77 failures -> 0
tests/execution_core/test_persistence_repository.py       27 ERROR + 1 FAILED -> 0
tests/execution_core/test_persistence_directness.py      152 ERROR + 1 FAILED -> 0
tests/test_import_boundaries.py                                     all pass
tests/r2_conformance_oracle.py                                      exit 0
tests/test_wo0113_repair_scaling.py                                 13 passed
ruff check · ruff format (changed paths) · mypy app/ · lint-imports  clean
```

Every new refusal is mutation-checked; the mutants are named in the commit messages. Two initially
survived and I added the missing controls rather than claim coverage I did not have.

**Suite floor — 3 failures, all reproduced at base `344c32b`**, recorded in
`work/review/FINDING-preexisting-suite-floor-2026-08-24.md`: two fill-position scaling assertions
and one production-boundary violation where `checkpoint_codec` annotates a private acceptance
closure seam.

**NOT_RUN:** the five hypothesis state-machine files (37 tests). `deadline=None` lets one example
run unbounded; a full 6,793-test run reached ~1% then advanced at roughly six tests per minute.
Tracked in `FINDING-protection-stateful-replay-disposition.md`, which also records that
`test_protection_stateful.py` is red at base for an unrelated reason.

---

## 7. Open items the reviewer should NOT treat as oversights

| Item | Status |
| --- | --- |
| `FINDING-schema-approval-gate-is-self-approving.md` | P2 now, P0 the day `execution_core` is wired in. Every `install_schema` caller passes the digest computed from the artifact it approves, so the check is `sha256(x) == sha256(x)`. **Blocks going live.** |
| `FINDING-protection-stateful-replay-disposition.md` | P1, predates WO-0168c, proven outside its import graph |
| `FINDING-preexisting-suite-floor-2026-08-24.md` | The three remaining failures, attributed |
| R15 §3 / R16 §2 conflict on `_manual_by_id` | **Ratified by Ameen 2026-08-24** — R16's reachable-current rule governs; R15 §3's cardinality sentences superseded. See `work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md`. Verify the enforcement table there rather than re-weighing the conflict |
| Pre-existing tautologies at `pure:1551`, `:1554`, `:2258` | Predate this diff; recorded, not fixed |

---

## 8. Requested verdict

`BLOCK` / `ACCEPT-WITH-CHANGES` / `ACCEPT` with exact P0/P1/P2 findings, per
`.ai-os/core/15_CROSS_MODEL_REVIEW.md`. The reviewer owns `result.md`; I will not write it, and
per P-1 any correction from me goes in a separate disclosed addendum.

**Do not accept on the strength of the in-process pass.** It was run by the party being reviewed,
on lenses that party chose, against contracts that party selected as authority. It is a first-pass
filter and nothing more.
