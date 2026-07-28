# AUDIT-0003 — Assurance retrospective: structural findings across the review corpus

- **Date:** 2026-07-28
- **Trigger:** operator directive after the REV-0045 round-2 saga — "expand this inquiry
  into more of the prior REV and RESULT files… identify more structural findings and
  opportunities for improvement," broadened to any relevant artifact.
- **Method:** four parallel fresh-context analysts over partitioned corpora — REV-0001..0024;
  REV-0029..0045 + `SIGNAL-R6aR-STATE.md`; the FINDING/AUDIT/CAMPAIGN/PROC artifacts;
  the ledger + completed work orders — synthesized by the Claude seat. Every claim below
  carries its artifact ids; the per-analyst reports are preserved in the session record.
- **Status of this document:** findings and a prioritized queue. Items marked **LANDED**
  shipped with this audit under the 2026-07-28 operator ratification. Everything else is
  a proposal awaiting explicit ratification — nothing below self-executes.

## The one-sentence version

The repo has a **recurrence-amplified capability problem**: finite-context implementation
and review seats repeatedly lose universal-domain, sibling-lane, and causal-path obligations,
while duplicated representations and oversized semantic surfaces turn those limitations into
fresh P0/P1 defects. Durable prevention requires more than placing a rule in CI or a template:
the control must be machine-consumed, semantically complete, failure-capable, exercised by a
committed negative fixture, and current against the surface it guards.

## S-1 — One meta-root, diagnosed twice, cured locally, incompletely centralized

AUDIT-0001 (a full campaign ago): *"the same truth derived independently in two places,
then defended when the derivations disagree."* The early-corpus instances are confirmed:
the two working-order predicates that livelocked multi-leg
(FINDING-W3-multileg), per-symbol staleness computed but feed-wide staleness consumed
(REV-0012), and the envelope counter validated while real position went unread
(FINDING-W3-reduce-only).

The late-corpus instance is also confirmed, but this audit withdraws the exact count
**"seven independent implementations"** because no normalized seven-row census defined
what counted as an implementation rather than a parser, validator, caller, floor, seed,
or sink. REV-0045 nevertheless proves that several independently implemented limbs of
"what epoch sequence does this history prove?" diverged across tolerant high-water
bookkeeping, release-key decoding, memory/SQLite release floors, bounded-verification
seeds, heal checks, and the durable carrier domain. Fixing one limb did not establish
the others.

The sequence-carrier contribution is now centralized in
`contributed_epoch_sequence()`, but the larger producer-rail state machine remains
duplicated across the projector and both stores: boundary selection, state-conditioned
seed construction, field comparison, recovery classification, repair-and-refuse
behavior, and persistence choreography are not yet one semantic implementation.

**LANDED, NARROWLY:** `pkl/architecture/testing-model.md` states the single-source rule,
and `tests/test_derived_truth_single_source.py` is a useful AST tripwire. Its positive
import check is composed with CI's Ruff F401 gate, so a merely dead import would also
fail the build; however, the test still proves neither that every consumer calls the
helper nor that a second derivation cannot move to a new module or use an alias. Treat
the gate as a narrow regression control, not proof that S-1 is structurally impossible.

## S-2 — Sibling-lane blindness is a high-yield recurrent defect class

A repeatedly productive defect shape is a rail enforced on one path and absent on a
sibling. Confirmed instances include redrive bypassing fresh-path validation
(FINDING-W3-redrive-revalidation-bypass), reconciliation-inferred fills bypassing the
stream fill bridge and envelope accounting
(FINDING-W3-synthetic-fill-envelope-bypass), and two submission lanes omitting the same
known `needs_review` venue-exposure obligation (REV-0029 P0-3).

The earlier statement that **all eight findings across WO-0110/0111/0112 were symmetric
twins** is withdrawn. WO-0110 explicitly describes its three findings as twins.
WO-0111 and WO-0112 contain related omissions, but also a second-order retry/idempotence
wedge and a memory/SQLite terminal-cleanup parity defect; compressing all eight into one
shape loses material distinctions. The corpus supports "high-yield and recurrent," not
the unmeasured superlative "dominant."

Diff-scoped review is especially weak against unmodified sibling lanes. The durable
response is therefore not enumeration alone: every state or external-effect sink should
accept only a common authorization/plan type whose constructor owns the shared
obligations. Until that architecture exists, twin-lane enumeration remains a planning
aid rather than structural prevention.

## S-3 — The inert pin is the dominant review-machinery failure

A verification artifact that cannot fail, recorded as if it could: mocks pinning a
nonexistent SDK method (REV-0002, recurring as X-002 in FINDING-W3-test-integrity
*after* INVARIANTS.md named it); a parity verifier structurally blind to order-status
divergence (REV-0007); `assert x or True` surviving 410 green tests (REV-0023); then an
unbroken late-corpus chain — REV-0029 P0-4/NEW-P0-1, REV-0031 (×2), REV-0035
(explicitly "the REV-0029 class"), REV-0038, REV-0039, REV-0041, REV-0043, REV-0045
P0-2 **twice** (the original expired silently; the replacement was epoch-1-only and a
generated-shape mutant survived 161 tests). Two mechanisms:

- **Proof expiry:** a mutation check is evidence about the code as it stood that day;
  both REV-0045 P0-2 rounds were proofs invalidated by later commits to the guarded path.
- **Fallback shadowing:** redundant recovery re-derives the correct final state, so
  outcome assertions pass on the wrong path (Option-A reclassification, REV-0041 C-1).

**PARTIALLY LANDED:** the expiry rule and path-assertion rule are recorded in
`testing-model.md`, and ADR-015 plus the nightly workflow establish the intended
generated-mutation mechanism. At this anchor the workflow is **REPORT-ONLY, NOT A
RATCHET**: `MAX_SURVIVORS` remains the permissive sentinel `999`, `mutmut run` is followed
by `|| true`, and ADR-015 itself says the first recorded baseline is still owed. It may
report useful evidence, but it does not yet prevent a regression. A real gate must
distinguish complete runs, survivors, no-mutant/empty-scope runs, baseline test failure,
tool error, timeout/partial results, and cache invalidation before comparing a frozen
baseline.

## S-4 — Lessons die with their file

PROC-0001's own through-line, and this audit's most repeated observation: the incident
carry-forward field was added to W3-STATE.md and vanished when that file retired; the
conformance oracle was prescribed as a gate and never entered CI (AUDIT-0002 AUD2-C002,
explicitly "the cheapest high-value fix in the batch"); AUDIT-0001's R6 root
(cancel-convergence) remained prescribed-and-open across three artifacts; X-002 was
documented in INVARIANTS.md and then reproduced. The repo's knowledge system records lessons durably, but placement in CI or a template
is only a necessary condition. This commit contains counterexamples: the mutation job is
in CI but is still report-only; the round-budget rule depends on `round:` and `surface:`
frontmatter absent from the result template; and the Fable checker recognizes marker
substrings rather than validating the declared evidence grammar.

**Corrected meta-law:** a mandatory rule is durable only when it is
(1) machine-consumed, (2) semantically complete for the claim it makes,
(3) failure-capable, (4) exercised by a committed negative fixture, and
(5) current against the guarded surface. A template field without schema enforcement,
or a CI step without a failing canary, is placement—not control.

**PARTIALLY LANDED:** the conformance oracle is now invoked by CI, but it is invoked
twice in the same job and its semantic independence remains a separate S-8 question.

## S-5 — Evidence decays between the moment it is made and the moment it is read

51 of 119 ledger rows record `"commit": "HEAD"` (unverifiable; WO-0116 had to re-prove
ancestry externally). SHAs cited in packets stopped resolving after rebases (REV-0034
F-B, REV-0036). REV-0030 has a result but no disposition; REV-0044's result is absent
from the working branch while downstream artifacts rely on its verdict. Wave-1 reviews
ran on broken environments and still emitted verdict tokens (REV-0004's "ACCEPT
(non-gating, environment-limited)"). Summary sentences overclaim what per-finding text
states accurately — slice 9's withdrawn "all 7 fixed at root cause," the implementer
launch prompt's unpushed-work claim, REV-0041's `red_green_verified: true`. The pattern:
**the evidence layer is append-mostly prose with no resolver**, so truth drifts the
moment the tree moves.

**P-6 STATUS — PARTIALLY LANDED:** `check_ledger.py` now rejects non-hex commit strings
only for rows dated after the cutoff, but it does not resolve the SHA, prove ancestry,
or validate same-day and grandfathered evidence. `check_work_order_disposition.py`
detects a disposition artifact with no `result*.md`, but it does not enforce result
before disposition by commit order, disposition before work-order close, verdict
agreement, or packet-to-work-order linkage. The queue and shipped summary must not call
the full P-6 contract closed.

## S-6 — Semantic coupling is associated with the treadmill; line count is not established

The original line-count claim lacked an enumerated denominator and conflated work-order
length, novelty, risk, and review intensity. A follow-up audit enumerated 62 delivered or
queued implementation/assurance records and selected 33 product work orders whose review
outcomes could be attributed with useful confidence. It coded a descriptive scope score:

`state machines + effect sinks + human-gated surfaces + one paired-store limb`

The paired memory/SQLite limb records required dual-store coupling; it is never a reason
to split the stores.

| Scope bucket | N | ≥1 attributed material finding | Exposed to BLOCK | Multi-round chain |
|---|---:|---:|---:|---:|
| bounded, score 0–2 | 5 | 2 | 0 | 0 |
| coupled, score 3–6 | 14 | 6 | 1 | 1 |
| umbrella, score ≥7 | 14 | 13 | 5 | 8 |

Descriptively, umbrella work was about 2.2× as likely as non-umbrella work to have a
material finding, 6.8× as likely to be exposed to a BLOCK, and 10.9× as likely to enter
a multi-round chain. These are screening ratios, not causal estimates: several rows share
campaign packets, high-risk work receives deeper review, and historical metadata is
inconsistent.

**Conclusion:** retract “work-order line count predicts the treadmill.” The supported
claim is narrower and more useful: multiple state machines, independent effect
authorities, truth owners, or human-gated surfaces in one delivery are strongly
associated with review churn. P-3 should become a semantic scope budget, not a
`>400 lines` rule.

## S-7a — Environment non-reproducibility weakens evidence

A reviewer running a different interpreter, operating system, dependency closure,
working directory, or unavailable service may be unable to reproduce a claimed gate.
That is an evidence limitation, not automatically a product defect and not a basis for
an unqualified verdict token. The result artifact must record a structured
`INCONCLUSIVE` limitation with the exact environment difference.

The Windows/POSIX path comparison in REV-0045 P0-1 is not merely false review signal; it
is a real portability defect in a purportedly cross-platform test/probe. Wrapper
exit-code masking belongs primarily to S-3/S-5 because it makes evidence inert or
misreported.

## S-7b — Tool and framing friction consume review capacity

The two content-filter stalls are operator-attested session evidence rather than
repository artifacts. They are operationally relevant because they delayed review, but
they do not establish a product-correctness class. ADR-014's neutral vocabulary can
reduce that friction. Runbook constraints and prompt framing should be treated as
tool-access controls, not as substitutes for executable correctness controls.

## S-8 — Oracle capture: the system proves the wrong or incomplete property correctly

S-8 differs from an inert pin. Under S-3, a check cannot fail when its intended property
is violated. Under S-8, the check is active but the code, tests, ADR/spec text, work order,
and reviewers share the same incomplete premise.

Live candidates include:

- `tests/r2_conformance_oracle.py` claims independence from implementation helpers, yet
  its owner oracle calls the production `active_sell_intent_for()` query and checks the
  production intent status rather than comparing against a separate raw-fact model.
- The same oracle's `_seed_long()` always terminalizes the establishing BUY, excluding
  the cross-side interleavings that generated several later defects.
- `project_read_models()` deliberately delegates to the same projectors used by the
  stores; memory/SQLite equality can therefore certify a common semantic error.
- The comparator meta-test perturbs only five of eight `ReadModelProjection` fields, and
  the live-vs-replay test compares only three fields.
- `docs/spec/signal-seat/06-invariants.md` says `docs/INVARIANTS.md` remains the
  independent oracle, while the registry adds only a non-normative Signal Seat
  cross-reference and no independent producer-rail invariant.
- REV-0040 proved the case-study shape: creation and dedupe were coherent, but release
  preconditions and downstream control-loop membership were omitted.

**Control:** before ratification, at least one reviewer-owned holdout property or
metamorphic relation must be derived independently of the production query/projector
being checked. The implementation seat may not amend that holdout in the same work order.
Stateful generators should exercise operation sequences and compare both stores with a
small independent model. Review packets must disclose shared dependencies between the
system under test and its oracle.

## Prioritized ratification queue

Ordered by (defects prevented per unit of mechanism), dedup of ~30 candidates from the
four analysts. None of these self-execute; each needs an operator yes.

| # | Change | Kills | Evidence anchor |
|---|---|---|---|
| P-1 | **LANDED 2026-07-28** — **Treadmill tripwire:** after 2 consecutive BLOCK/P0 rounds on one surface, the next artifact must be an AUDIT-0001-style root audit (symptom-vs-root grading + same-class sweep), not another remediation WO | S-6 | AUDIT-0001 worked; REV-0029 and REV-0045 chains show its absence |
| P-2 | **PARTIALLY LANDED 2026-07-28** — **Twin-lane enumeration:** retain the mandatory table as a planning aid, but do not claim structural closure until lanes and effect sinks are machine-registered and the sink accepts only a shared authorization/plan type | S-2 | WO-0110's three explicit twins; REV-0029 P0-3; REV-0045 carrier/floor siblings |
| P-3 | **Semantic scope budget:** split or record an operator-approved coupling waiver when one delivery owns >1 state machine, >1 independent effect authority, >1 human-gated surface, >1 truth owner/event family, or scores ≥7 on the audited scope dimensions. Memory+SQLite are one required paired limb and may not be split | S-6 | 33-WO attributable cohort: umbrella bucket 13/14 material findings, 5/14 BLOCK exposure, 8/14 multi-round |
| P-4 | **LANDED 2026-07-28** — **Review-round budget:** 2 rounds on one delivery ⇒ re-cut or seat change (formalizes what WO-0113 and the R6aR swap did late) | S-6 | PR #9 chain |
| P-5 | **Mutation-currency registry:** map each decisive pin to its guarded span; CI flags span changes without recorded re-verification | S-3 | REV-0045 P0-2; REV-0038 F4; REV-0041 C-3 |
| P-6 | **PARTIALLY LANDED 2026-07-28** — **Ledger/provenance hardening:** hex-format and disposition-without-result checks exist; SHA resolution/ancestry, commit-order validation, disposition-before-close, verdict agreement, and durable negative fixtures remain open | S-5 | 51/119 rows; checker implementation at this anchor |
| P-7 | **Cross-cutting-concern registry + contract test:** every mutating facade command enumerated once; parametrized test asserts actor/clock threading per command | S-2 | dropped-actor ×3; dropped-clock REV-0032 |
| P-8 | **Parity-verifier completeness meta-test:** `ReadModelProjection` field set must cover every projector output | S-3 | REV-0007 F001 |
| P-9 | **Autospec rule:** broker-SDK mocks require `create_autospec`/`spec_set` (lint or fixture) | S-3 | X-002 ×2 |
| P-10 | **Dual-store parametrization check:** tests touching store seams must carry both store params | S-2 | R6aR SQLite-only heal pins; REV-0039 F2 |
| P-11 | **Replay-coverage gate:** a new durable event type ships with projector/replay/parity coverage in the same WO | S-4 | CC-04; 13 uncovered event types |
| P-12 | **State-file template carries `toolchain-incidents`** (re-lands PROC-0001 #1 structurally) + inverse staleness check for DRAFT WOs untouched N days | S-4 | PROC-0001; WO-0102/0103/0104 DRAFT 17 days |
| P-13 | **Result-template linter:** frozen SHA + interpreter stanza + pasted probe or explicit could-not-verify + numeric counts; ban bare "Exit code: 0"; add `INCONCLUSIVE-ENV` verdict token | S-5, S-7 | REV-0004/0009..0014/0019..0021 |
| P-14 | **INV↔probe linkage checker:** every INV names ≥1 enforcing test; INV text amendments must touch their named enforcement in the same commit | S-4 | INV-050/074/085 overclaims; ADR-008 ×3 rounds |

## Shipped with this audit (operator ratification 2026-07-28)

Second ratification round (same day): P-1 + P-4 were placed in
`.ai-os/core/15_CROSS_MODEL_REVIEW.md` (+ a CLAUDE.md pointer); P-2 was placed in the
work-order template and review checklist. P-6 is **partially landed**: the two hygiene
scripts enforce narrower predicates than the queue row promised. The operator attests
that planted violations produced RED and restore produced GREEN; committed negative
fixtures are being added so that this evidence no longer depends on session attestation.

ADR-014 landed as a vocabulary-only change. ADR-015, the nightly mutmut workflow, and
`requirements-mutation.txt` are present, but the mutation job is **REPORT-ONLY pending
its first valid baseline and a failure-state taxonomy**. The single-source AST test is a
narrow tripwire composed with Ruff F401, not proof of a single state-machine
implementation. The conformance oracle is wired into CI twice; one duplicate invocation
should be removed without weakening collection.

## What this audit deliberately does not conclude

No verdict on any open gate (REV-0045 remains Codex-owned; R-1/R-2 open; D-2a OFF; R6b
blocked). No claim that the queue is complete — P-items were selected for mechanism per
defect; the four analyst reports contain the full candidate set and dissenting detail.
