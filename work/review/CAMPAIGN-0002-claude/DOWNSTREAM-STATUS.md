# Part B downstream status — reconciled against the current trunk (`d031a99`)

> Living tracker for the §H.1/§H.3 downstream pieces, reconciled against the **code on the
> trunk** (not the Part A report, which was written against the pre-R2 base + the two attempts).
> "Code is evidence of behavior" (CLAUDE.md conflict rule) — several pieces the report lists as
> to-do were already satisfied by intervening work (notably the Sol mechanism port, `74a7a4c`).
> **No human-gated code landed to produce this file — it is a read-only audit.**

## §H.1 build order

| Step | Piece | Status | Evidence |
|---|---|---|---|
| 1 | Port Sol's projection core + reconcile write-back | ✅ DONE | `74a7a4c` (Part B step 1a) |
| 2 | Indexed/memoized per-symbol projection | ✅ DONE | `c11bd44`, `b46fa31` (step 1b/1c) |
| 3 | Sol's monitoring/reconciliation rework + §E.3.2 fail-closed logging | ✅ DONE | `688d2c1` (R6 fix); Sol port in `74a7a4c` |
| 4 | **F.2 grafts** (masked-predecessor pins · `spared_sell_intents` counter · granular audit reasons) | ⏳ **OPEN** (partial) | see below |
| 5 | **Theme D** — `broker_order_id` write-once | ✅ **DONE** (already on trunk) | guard `core.py:2546-2562` + AIR-001 `2526-2544` (both stores, shared planner), added in `74a7a4c`, absent at base `22617f4`. Test: `test_wo0036_r2_hostile_closure.py::test_broker_order_id_is_write_once_with_zero_mutation_on_retarget` (both stores: submit → no-op reaffirm → retarget `InvalidOrderError "immutable once set"` → zero mutation). Verified green. |
| 6 | Merge R2 test files (Sol hostile corpus primary; oracle + lifecycle pins retained) | ⏳ OPEN (files coexist; consolidation TBD) | |
| 7 | Pre-cutover backfill verification vs real paper data | ⏳ OPEN (production migration) | |

### Step 4 — F.2 grafts, detailed
- **masked-predecessor**: the *property* is pinned — `test_r2_conformance_oracle_claude.py::test_masked_predecessor_keeps_intent_owned` (my oracle) + predecessor handling in `monitoring.py` (~1169/1406/1409). **Open item:** confirm the Claude attempt's *additional* hostile pins for the masked-predecessor class are represented (or provably covered) — a verification task, maybe not a code graft.
- **`spared_sell_intents` counter**: ⏳ OPEN — no occurrence in `app/` (a session-close observability counter; the graft that makes the sparing decision auditable/measurable).
- **granular audit reason**: ⏳ OPEN — trunk emits Sol's reused `deferred_to_live_protection` (`core.py:2028`); the graft is Claude's distinct `deferred_to_live_envelope_child` for audit legibility. **Note:** this touches the flatten deferral audit payload — adjacent to the Option B / REV-0024 flatten surface, so sequence it *after* the REV-0024 flatten gate clears to avoid churning a surface under review.

## §H.3 governance to produce

| Piece | Status | Note |
|---|---|---|
| One ADR-010 R2 amendment | ⏳ OPEN | no WO-0036/R2 amendment text in `docs/adr/ADR-010-execution-envelope.md`. Convention: inline dated "Amended … (WO-0036 R2)" paragraphs (Sol's style), content freshly written for the *synthesized* mechanism. Doc, but ADR amendment ⇒ independent-review gate. |
| One canonical INV-090 | ⏳ OPEN | absent from `docs/INVARIANTS.md`. Synthesize from both texts; name the indexed projection + grafts. |
| WO-0036 close-out (credit Sol) | ⏳ OPEN | **0** ledger rows mention WO-0036 on this trunk — the close-out writes the status flip + disposition + ledger entry crediting Sol's contribution (Sol shipped zero `work/` artifacts, §C.2.5/§G.2). |
| `close_session` docstring gap (§G.3) | ⏳ OPEN | pre-existing under-description; fix with the close-out. |
| REV-0029 (consolidated gated-change review) | ⏳ OPEN | supersede/close the dangling REV-0028. |
| Re-verify INV-032/036/080/081/087 vs final code | ⏳ OPEN | read-only audit against the synthesized code. |

## Gating + sequencing notes
- F.2 grafts touch order-intent/event-log surfaces (human-gated) → each needs its own scoped WO +
  review, like Option B (WO-0107). Not auto-approved.
- The granular-audit-reason graft is flatten-deferral-adjacent → hold until REV-0024 (Option B) clears.
- ADR-010 amendment + INV-090 describe the *synthesized* mechanism including the grafts, so they
  land **after** step 4, not before.
- WO-0036 close-out + REV-0029 come **last** (they record the *finished* consolidation).
