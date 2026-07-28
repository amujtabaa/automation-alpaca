# Sequencing proposal — one ordered build plan to live capital

- **Status:** PROPOSAL, unratified. Nothing self-executes.
- **Reconciles:** this war-game's findings with the standing ratified plan
  (`work/queue/SIGNAL-SEAT-R5b-TO-D2a-SEQUENCING-PLAN.md`), the AUDIT-0003 queue (P-1…P-14) and its
  addendum (Q-14, Q-A, Q-B).
- **Does not disturb the critical path.** REV-0045 round 3 is Codex-owned and BLOCK; R-1/R-2 open, D-2a
  OFF, R6b blocked. Everything below is planning or work on surfaces the R6a producer-rail remediation
  does not touch. Collision analysis is in §5.

## 1. The ordering principle this war-game produced

The seed map's implied principle was *"build the kernel before the surface that needs it."* **The
war-game refuted it on tense.** The six order-effect authorities
(`app/store/base.py:665,731,814,876,1550,1573`) all **predate** R7; R7 is a seventh consumer, not the
first. So sequencing WO-E "before R7" would deliver a permit type that R7 honours and the five existing
lanes do not — which is precisely the sibling-lane failure the permit exists to prevent, manufactured by
its own sequencing.

The principle that replaces it, and that orders everything below:

> **Buy failure-capability first, and buy it where it is cheapest.** A control that costs one line and
> converts an already-written but inert check into a build failure outranks a subsystem that costs a
> quarter and produces a document. Order by *(defects structurally prevented) ÷ (cost)*, and treat any
> control that cannot fail as costing infinity.

Under that principle the two highest-ranked items in the entire roadmap are a one-line
`.importlinter` edit and a one-line `pyproject.toml` edit.

## 2. Wave 0 — free wins (no prerequisites, all S-cost, all failure-capable)

Every item is independently valuable, none blocks another, and none requires a decision. This is the
de-dicing wave: each converts an obligation that currently lives in prose or memory into something a
mediocre run cannot skip.

| id | Work | Why first | Anchor |
|---|---|---|---|
| **W0.1** | Add `app.store` to `.importlinter` Contract 3; add the INV-052 no-`await`-on-adapter-under-lock AST check + committed negative fixture | Contract 3's `source_modules` omits `app.store`, so nothing prevents a broker call under the store lock — the M4a N5 outcome is one careless edit away and every control that should stop it is inert. `lint-imports` is already a CI step | `.importlinter:70-81`; `docs/INVARIANTS.md:420-422` |
| **W0.2** | Set pytest to collect `.ai-os/scripts/tests/`; wire `check_fable_done.py`, `check_work_order_scope.py`, `check_mcp_spec.py` into CI | ~30 committed red/green pairs proving six checkers can fail are excluded from every pytest invocation in the repo. The control plane's own S-3 | `pyproject.toml:5`; `.github/workflows/ci.yml` |
| **W0.3** | Close the two fail-open broker branches: the 422 duplicate/terminal collision, and the 404⟹never-landed inference | Both are capital-critical and need no venue access. A duplicate rejection worded without the magic substrings classifies a **live order as never-submitted**; a 404 on an aged-out filled order marks it `REJECTED`, stranding real shares with no protective sell | `app/broker/alpaca_paper.py:741-743` vs `:804-808`; `:1171-1172` → `app/monitoring.py:2937-2946` |
| **W0.4** | Dedupe `ORDER_SUBMISSION_BLOCKED` on `(order_id, reason)` | An order held for any earlier reason records **no event** when the kill switch later holds it. The event log cannot answer the first question a live incident review asks | `app/monitoring.py:2406-2421`; `app/policy.py:895,929-930` |
| **W0.5** | Holdout-ownership enforcement: CODEOWNERS on the holdout path + a CI check that an implementation commit does not touch it | AUDIT-0003's S-8 cure ("the implementation seat may not amend the holdout") is currently prose in an audit file — S-4 by that audit's own meta-law. This is a CODEOWNERS line and a five-line check | AUDIT-0003 S-8 §Control |
| **W0.6** | Add kill-switch `@invariant()`s to the existing `RuleBasedStateMachine` | The generator already has `crash_after_claim`, `divergent_fill_and_reconcile` and `set_kill_switch` as rules; `kill_switch` appears in **none** of its ten invariants. The composition M4a N7 feared is already generatable — only the assertion is missing | `tests/test_lifecycle_state_machine.py:127,256,297,503` |

**Wave 0 is the single highest-value recommendation in this war-game.** It is roughly one session of
work and it closes: one live fail-open path to duplicate orders, one to stranded positions, one
unguarded route to whole-process lock starvation, six checkers whose failure-proofs never run, the
event-log gap that would blind a post-incident review, and the S-8 cure's own missing enforcement.

## 3. Wave 1 — operator decisions (no code, but they gate later waves)

These are blocking in the strict sense: proceeding under an assumption would make the downstream work
wrong rather than merely delayed.

| id | Decision | Gates | Why it cannot be defaulted |
|---|---|---|---|
| **P-0** | Amend `pkl/project/goals.md` and the CLAUDE.md safety core to admit a live-capital destination | ADR-016…019 | The active goals page says **paper-only** and the safety core says no live trading in beta. The roadmap's terminal state contradicts the repo's highest-authority statement of intent |
| **D-1** | May any credentialed live-paper probe run in this program? | the XA register's `verified` column; ADR-018 F1 | If no, the column becomes `unverifiable-in-beta` and those rows stay `ASSUMED` permanently. A legitimate answer — but it changes what the beta→shadow gate can honestly claim |
| **D-2** | Calendar source: `GetCalendarRequest` (a new external call inside the adapter boundary, making a currently pure IO-free layer network-dependent) vs a committed static table with an expiry date | Row 3's generator; ADR-019 G2 | The generator cannot be specified until this lands, and a generator built without it re-certifies the half-day misclassification |
| **D-3** | Is max-daily-loss a **beta** requirement or a **pre-live** requirement? | Row 5 cost (M vs L); ADR-018 F3 | No P&L control exists anywhere in `app/`. Pre-live ⇒ a `NO-CONTROL` sentinel row suffices now. Beta ⇒ a real P&L subsystem, and Row 5 becomes L |
| **D-4** | **What are "WO-A/B/C kernel program" and "WO-E permits"?** | Wave 3 scoping | These appear **only** in the kickoff — nowhere else in the repo. Per the governing principle, the planning seat will not reconstruct their content from inference. Marked `ASSUMED` → **NEEDS-INPUT** |
| **D-5** | Does `LIVE_CONTROLLED`→`LIVE_PROD` share ADR-019 with `LIVE_MICRO`→`LIVE_CONTROLLED`, or split? | ADR-019 | The ratified ladder has four transitions; the kickoff named three gates |

## 4. Waves 2–5

### Wave 2 — registries and coverage (after Wave 0; D-1/D-2/D-3 gate parts)

| id | Work | Depends on |
|---|---|---|
| W2.1 | The XA register as a keyed, machine-joined artifact + its CI checker + negative fixture; plus the mock/sim "behaviours deliberately not modelled" list joined by the same checker | W0.3; `verified` column needs D-1 |
| W2.2 | Bidirectional capital-limit ↔ INV coverage checker with `NO-CONTROL` sentinel rows | D-3 |
| W2.3 | `session_date` UTC-vs-Eastern decision + full consumer enumeration + AST tripwire on bare `utcnow().date()` | — (needs no calendar source) |
| W2.4 | **The shared lane registry** — one mechanism serving P-2's twin-lane table, P-7's cross-cutting-concern registry, Row 1's permit lanes, Row 5's INV quantifier upgrade, and Row 12's compensation registry | W0.5 |
| W2.5 | `fold_fills` property test vs a `Decimal` reference | — |
| W2.6 | Store I/O-failure semantics: `OperationalError` fault injection, assert fail-closed | W0.6 (same test surface) |

**W2.4 is the consolidation finding.** Five separately queued items — two of them AUDIT-0003 P-items —
all need the same artifact: a machine-readable enumeration of the lanes that reach a given effect. Buying
it once is the difference between a registry and five registries.

### Wave 3 — the R7 program, re-cut

| id | Work | Note |
|---|---|---|
| W3.1 | **WO-E1** — unify `_same_symbol_exit_may_execute` into one `core.py` pure function | Pays down a live S-1 whether or not R7 ships. **Must precede R7**, or R7's agreement pin has no fixed reference and will "prove" agreement against whichever twin the test happens to run |
| W3.2 | **WO-E2** — the permit type with a mypy-narrowed sink signature + no-permit negative fixture, **migrating all six existing authorities**. The migration is the deliverable, not the type | Scoped as a migration program per §1. Blocked on D-4 for naming/intent |
| W3.3 | **R7 re-cut by gated surface** — split the R4 correlation-schema surface into its own WO | The standing plan already splits R7 into R7a/R7b **by side**; this adds a cut **by gated surface**. Amending a ratified plan — needs operator ratification |
| W3.4 | Author `project_committed_sell_exposure` (currently zero occurrences in `app/`) + its reviewer-owned holdout, authored before implementation | W3.1, W0.5 |

### Wave 4 — `LIVE_SHADOW`

ADR-016 (architecture + producer independence + divergence schema/taxonomy) → the build (L: adapter
lane, store schema with dual-store parity, event type with projector/replay coverage per P-11,
comparator, CI reader, cockpit surface).

### Wave 5 — the gates

ADR-017 → soak → ADR-018 → ADR-019, each ratified only as its evidence table goes green.

## 5. Interleaving with the standing plan, and collision risk

The signal-seat track is unchanged and runs on its own line:

```
R6a (BLOCKED: REV-0045 round 3, Codex-owned)  →  R6b  →  R7a  →  R7b  →  D-2a
```

**Wave 0 does not touch the R6a producer-rail surface.** W0.1 edits `.importlinter` and adds a checker;
W0.2 edits `pyproject.toml` and `ci.yml`; W0.3 edits `app/broker/alpaca_paper.py`; W0.4 edits
`app/monitoring.py`; W0.5 adds CODEOWNERS + a CI check; W0.6 edits
`tests/test_lifecycle_state_machine.py`. None modifies `app/store/` producer-rail code, the release-key
parser, or the epoch-sequence helper under review.

**Two real collision risks, both manageable:**

1. **`work/ledger.jsonl` append conflicts.** Any Wave 0 close-out appends a line. Per the repo primer,
   serialize close-outs and preserve both lines on conflict — never resolve by dropping one.
2. **W0.3 touches `app/broker/alpaca_paper.py`**, which REV-0045 does not, but which the eventual
   REV-0011-successor packet will. Cheap to sequence: land W0.3 before any venue-truth review opens.

**Recommendation: Wave 0 runs now, in parallel with the Codex round-3 critical path.** It is the only
wave for which that is true, and holding it until the gate clears would leave two live fail-open paths
open for the duration.

## 6. Reconciliation with the AUDIT-0003 queue

Verified placement status: **P-1 and P-4 landed** (`.ai-os/core/15_CROSS_MODEL_REVIEW.md:74-85`);
**P-2 landed** in the work-order template (`:46-75`); **P-6 partial**. **P-3, P-5, P-13 and P-14 have
zero placement** in `.ai-os/core/`, `.ai-os/templates/`, or either CI workflow — they exist only as
prose rows in AUDIT-0003, which is the exact S-4 shape that audit diagnoses.

| Item | Disposition proposed here |
|---|---|
| **P-3** semantic scope budget | **Sharpen and ratify.** This war-game supplies its first real test case: R7 scores ≥2 human-gated surfaces before counting effect authorities, so P-3 would flag it today. Fold into W3.3 |
| **P-5** mutation-currency registry | **RATIFY-AFTER** the mutation ratchet has a baseline. Mandating currency certificates while `MAX_SURVIVORS=999` mandates an artifact that structurally cannot fail — S-3 on purpose. Sequence into Wave 2 after ADR-015's baseline |
| **P-7** cross-cutting-concern registry | **Merge into W2.4.** Do not build separately |
| **P-11** replay coverage for new event types | **Promote.** ADR-016's divergence record and R7's correlation fields both need it; it is a precondition for two waves, not a queue item |
| **P-13** result-template linter | **Ratify with Q-A folded in** (the C1/C2/C4 protocol contradictions). Wave 2 |
| **P-14** INV↔probe linkage | **Ratify with the quantifier upgrade.** W-1 priced landing debt at near zero, but this war-game found P-14 as written **would not catch INV-060** — a universal claim ("every new order-intent path") pinned by three tests covering two of six lanes passes a checker that counts to one. Ratify P-14 *and* the upgrade, which depends on W2.4 |
| **Q-B** spec-refresh WO | Unchanged; independent |

## 7. What this proposal does not claim

- **It does not price Wave 4.** `LIVE_SHADOW` is L and its central design question — what independently
  produces the second side of the comparison, given that Alpaca sells no live-shadow product — is
  unanswered. ADR-016 must answer it; this proposal only establishes that it must be answered *before*
  any gate binds.
- **It does not resolve D-4.** The kickoff's "WO-A/B/C kernel program" and "WO-E permits" have no repo
  artifact. Wave 3 is scoped from the hazard analysis, not from those names, and may be wrong about
  their intent.
- **It assumes the R6a track clears.** If REV-0045 round 3 forces an AUDIT-0001-style root audit under
  the P-1 tripwire (two consecutive BLOCK/P0 rounds on one surface — a condition the R6a chain has
  already met), that audit precedes Wave 3 and probably reorders it.
- **No wave here has been costed against operator time**, only against work-order units. The critical
  constraint on this repo has consistently been review capacity, not implementation capacity, and
  nothing in this proposal measures that.
