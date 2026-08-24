# REV-0078 R1 request — WO-0168c implementation review

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

- Candidate: **superseded — see the amendment at the end of this request.**
- Branch: `codex/claude-opus-m2-wo0168c-r1`
- Base for this review: `344c32b` (last independently unreviewed head; R20 §4 partial)
- Governing contract: R20 (`work/queue/M2-EXECUTION-2026-08-21/31-...-R20.md`), accepted by
  REV-0077 R13 at `aa2f0225a0d0d85a41e5cfc5f6c8e530ed7c1a83` with P0=0/P1=0/P2=0.

## Scope — bounded deliberately

Review **only the diff `344c32b..2cfbce0`**. REV-0077 already accepted the contract; re-opening
contract questions is out of scope for this packet. Eleven commits, 8 files:

```text
d22bf0e feat(checkpoint): R20 s4 venue ClosureHeads
ab67de4 feat(checkpoint): R20 s4 venue Reconciliations
0d16933 feat(checkpoint): R20 s4 venue BootstrapTargets
8e81cbe feat(checkpoint): R20 s4 venue ExecutionReconciliations
1597152 feat(checkpoint): R20 s2 authority AcquisitionDescriptors and AcquisitionSlots
720d390 feat(checkpoint): project the authority emergency grant row
faa964e test: prove the projected wires pass their own validators
9447dd4 docs(wo-0168c): HUMAN-GATE checkpoint bundle for the schema DDL
aab4130 fix(schema): make the DDL installable and re-pin both approval digests
0e1c835 fix(checkpoint): drive the SQLite proof through the production projector
2cfbce0 test: clear the three remaining WO-0168c verification gaps
```

## What changed

R20 §2 and §4 projection are complete. The projector carries **no whole-family refusal
anywhere**: all fifteen venue families and every authority collection project from proof-selected
direct keys.

The schema DDL was changed under Ameen's explicit 2026-08-24 authorization at the human gate;
that gate bundle is `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.

## Lenses requested

1. **Contract conformance.** Do the new rows match R20/R2/contract-07 member counts, order, and
   tags exactly? Especially: the 25-member bootstrap active row and its nested 25-member inert
   transition proof, the 4-member R2 `AcquisitionSlot` collapse of contract-07's separate
   descriptor/active members, and the 16-member currentness row.

2. **R16 §2 map taxonomy.** Each family must sit in the right category. Confirm that
   `_acquisition_descriptor_by_effect` correctly gets **no** whole-map cardinality check (permitted
   superset), that the three acquisition scope maps are each compared against **their own** reached
   count rather than the slot count, and that the reconciliation indexes are exact-current.

3. **R17/R20 ordering.** Venue families must use proof order and never re-sort; authority families
   must use canonical semantic-key order. Check that no Python comparison, repr, or digest
   surrogate substitutes for contract §2.4 canonical ordering anywhere.

4. **Reachability.** R15 §2 admits a reconciliation row only when its input ID is directly
   referenced by a selected current row. Is the referenced set I derived correct and complete —
   closure/coverage for fill reconciliations, bootstrap targets for execution reconciliations?

5. **The gated change.** Are the two `RAISE(ABORT, ...)` literal joins byte-identical in message
   text, and are both re-pinned digests correct for the resulting DDL?

6. **Test integrity.** Do the new controls fail for the right reason? Three specific places where
   I changed an expectation rather than the code — each is argued in the commit message and I want
   them checked adversarially:
   - `_require_write_capability` now reads its sealed slots via `getattr(..., None)`.
   - The W00b assertion now targets the first *checkpoint* statement, not the first statement.
   - `test_current_proof_payloads_require_fresh_heads_or_versions` now expects the payload
     refusal because a same-version replacement can have no retained payload.

## Known open items — please confirm my classification, do not re-find

- **Q9 bounded-plan violation.** `acceptance_set AS acceptance` is joined on a UNIQUE column but
  the planner reverses the join and passes over the whole table. Stable across ANALYZE. Pinned by
  exact equality in `test_all_thirteen_selection_queries_have_bounded_indexed_plans`. The fix is a
  repository SQL change behind the human gate. **Is pinning the right disposition, or is this a
  P0/P1 that must block?**
- **Import-direction control.** Its allow-list is now exact rather than a subset; the stale
  `test_persistence_schema.py` entitlement was dropped and the real consumer added. Authorized
  2026-08-24. **Does the tightening hold, and does the enumeration still mean what it should?**
- **24-hour soak** — `NOT_RUN`, belongs to WO-0170.

## Evidence

```text
tests/execution_core/test_persistence_runtime_checkpoint_pure.py   105 passed
tests/execution_core/test_persistence_schema.py                     77 failures -> 0
tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py  55 failures -> 0
tests/execution_core/test_persistence_write_capability.py            7 passed
tests/test_import_boundaries.py                                      6 passed
tests/test_wo0113_repair_scaling.py                                 13 passed
tests/r2_conformance_oracle.py                                      exit 0
ruff check / ruff format (changed paths) / mypy app/ / lint-imports  clean
```

Mutation evidence for the new controls is recorded in the commit messages; re-run any of it.

**READ ONLY:** no edits, no `result.md` authored by me, no SQLite or database activity on my behalf.

---

# Amendment 1 — bound extended past the original candidate

Date: 2026-08-24

The request above named `2cfbce0`. Nine further commits have landed, several of them
**correcting defects in the reviewed artifact itself**, so reviewing `2cfbce0` would review
code that is known-wrong. The bound is extended:

```text
Candidate: 2082e4ed130259ae1bf1a1565e5b0d4e5c5d499c
Tree:      d4d3ddd41a6c2aa0be4545c4297dd43d9a5d9890
Bound:     344c32b..2082e4ed130259ae1bf1a1565e5b0d4e5c5d499c
```

## What changed since `2cfbce0`, and why

An in-process adversarial pass (three fresh-context agents; **not** independent review — see
`in-process-adversarial-pass-r1.md`) found P0-class defects in the original candidate. Reviewing
the old head would waste the reviewer's effort on findings already dispositioned.

1. **Eight whole-map cardinality checks removed** — three added in this work order, five
   pre-existing. `_PersistentKeyMap` has no deletion of any kind, so those indexes are monotonic,
   while the repository selects only `disposition IN ('OPEN','INVALIDATED')` plus late-admitted
   owners. One ordinary closed effect left a permanently unselected entry and every later
   checkpoint refused. **The reviewer should still rule on this**: it removes refusals on a
   safety surface, and the argument, though verified against the code, was reached in-process.
2. **Each removal replaced by the relation it was standing in for** — coverage index-to-ledger
   root binding, reconciliation admission by equality with the referencing row rather than
   membership in the selected set, and closure heads bound against `selection.closure_heads`,
   which the codec had never consulted.
3. **Bootstrap records now pass their authenticity check** before reaching the wire.
4. **The bounded-plan control corrected twice** — first because it excused all indexed scans,
   then because "partial index" does not imply bounded. Pinned violations went 1 → 5 → 12.
5. **Q9 `CROSS JOIN`** — repository SQL, authorized by Ameen on 2026-08-24.
6. **DDL and three digest re-pins** — authorized, with the third ratified retroactively in
   Amendment 1 of the gate bundle. Tracked forward as
   `work/review/FINDING-schema-approval-gate-is-self-approving.md`.

## What the reviewer should weigh most

The eight removed cardinality checks and the five replacement relations. Everything else is
either mechanical or already dispositioned. The specific question: **is a monotonic index with no
deletion operation correctly classed as an R16 §2 permitted superset, and are the replacement
key relations sufficient to carry what the cardinality checks were wrongly asked to carry?**
