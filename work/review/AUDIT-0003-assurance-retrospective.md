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

The repo does not have a defect problem; it has a **recurrence** problem — the same five
structural classes generate nearly every P0, each class has been correctly diagnosed at
least once, and the diagnosis kept dying with the file it was written in.

## S-1 — One meta-root, diagnosed twice, cured locally three times, never enforced

AUDIT-0001 (a full campaign ago): *"the same truth derived independently in two places,
then defended when the derivations disagree."* The early-corpus instances: the two
working-order predicates that livelocked multi-leg (FINDING-W3-multileg), per-symbol
staleness computed but feed-wide staleness consumed (REV-0012), envelope counter
validated while real position went unread (FINDING-W3-reduce-only). The late-corpus
instance: "what epoch sequence does this history prove?" had **seven** independent
implementations, which is why REV-0045's per-instance fixes produced round-2 P0s
(addendum-02) — fixing one implementation said nothing about the other six.

Every successful closure of this class used the same cure: one shared function consumed
everywhere (WO-0109's projector; `contributed_epoch_sequence()`). The cure was never
promoted from instance to rule.

**LANDED:** the rule ("derived truth is single-sourced or it is a defect") in
`pkl/architecture/testing-model.md`, mechanically enforced by
`tests/test_derived_truth_single_source.py` (AST gate, mutation-verified, collected by
normal CI). Queue item P-2 extends the register beyond the sequence kernel.

## S-2 — Sibling-lane blindness is the dominant defect generator

The single most productive defect shape in the corpus: a rail enforced on the primary
path and absent on a sibling. Redrive bypassed ingest rails
(FINDING-W3-redrive-revalidation-bypass); reconciliation-inferred fills bypassed the
envelope ceiling (FINDING-W3-synthetic-fill-envelope-bypass); two submission lanes
bypassed the needs-review quarantine (REV-0029 P0-3 — falsifying a parked decision's
premise); stage lacked protection's guard (REV-0032); **all eight findings across
WO-0110/0111/0112 were symmetric twins of already-fixed sites** (their own frontmatter
says so); the dropped-actor class needed three separate remediation rounds at three
sibling commands (REV-0002 → REV-0004 → REV-0013); REV-0045 P0-3's payload carrier was
the sibling of the dedupe-key carrier fixed one round earlier. Diff-scoped review
structurally cannot see the un-diffed twin — this class must be killed at fix time, not
review time.

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

**LANDED:** the expiry rule and the path-assertion rule in `testing-model.md`;
ADR-015's nightly generated-mutation ratchet (`mutmut` over the derived-truth kernel) as
the backstop for mutants nobody hand-picked. Queue items P-5/P-10 mechanize the rest.

## S-4 — Lessons die with their file

PROC-0001's own through-line, and this audit's most repeated observation: the incident
carry-forward field was added to W3-STATE.md and vanished when that file retired; the
conformance oracle was prescribed as a gate and never entered CI (AUDIT-0002 AUD2-C002,
explicitly "the cheapest high-value fix in the batch"); AUDIT-0001's R6 root
(cancel-convergence) remained prescribed-and-open across three artifacts; X-002 was
documented in INVARIANTS.md and then reproduced. The repo's knowledge system records
lessons durably but only *enforces* the ones that reach CI or a template.

**LANDED:** the oracle now runs in CI (`ci.yml`, with the REV-0045 round-2 invocation
correction — direct script invocation never resolved `app`). Queue items P-6/P-12
re-land the carry-forward field structurally.

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

## S-6 — Work-order shape predicts the treadmill

WO-0113 (1,067 lines) and WO-0104a (87 KB) anchor the two worst chains (six remediation
WOs + five packets for PR #9; the R6a saga). The WO-0029 umbrella was superseded and its
re-cut singles all closed clean; the planned splits (0007a/b, 0019a) closed clean;
~20 of ~50 implementation WOs closed first-round clean and they share a profile — one
primary rail, explicit allowed paths, red-first pins, dual-store parity in the same
change, low declared risk. Meanwhile both sagas continued in-PR patching for rounds
after the signal was clear; AUDIT-0001's tripwire (stop remediating, audit roots) was
the intervention that actually worked, applied late both times.

## S-7 — Environment and framing friction produce false review signal

Interpreter drift (3.11 vs pinned 3.12, four consecutive packets), wrapper exit codes
masking failures (the coverage ratchet; REV-0043's near-false-green at 9% progress),
Windows/POSIX separator divergence (REV-0045 P0-1), and content-filter stalls on
security-flavored vocabulary in two review sessions (REV-0029's word-normalization note;
the REV-0045 round-2 stall). **LANDED:** ADR-014 renames the vocabulary at the source
(`InvalidProjectionMarker` et al.) so packets stop needing per-prompt defusing; the
runbook rules (marker-line reading, PS 5.1 constraints) are recorded in the state file
and repo primer.

## Prioritized ratification queue

Ordered by (defects prevented per unit of mechanism), dedup of ~30 candidates from the
four analysts. None of these self-execute; each needs an operator yes.

| # | Change | Kills | Evidence anchor |
|---|---|---|---|
| P-1 | **Treadmill tripwire:** after 2 consecutive BLOCK/P0 rounds on one surface, the next artifact must be an AUDIT-0001-style root audit (symptom-vs-root grading + same-class sweep), not another remediation WO | S-6 | AUDIT-0001 worked; REV-0029 and REV-0045 chains show its absence |
| P-2 | **Twin-lane enumeration, mandatory in every FIX block and WO template:** list every lane reaching the same state/venue effect (fresh/redrive/reconcile/restart/supersede/manual; memory+sqlite; stage/protection/flatten) with "covered / N-A because…" per lane | S-2 | WO-0110..0112 (8/8 twins); REV-0029 P0-3; REV-0045 P0-3 |
| P-3 | **WO size cap:** >1 gated surface or >~400 lines ⇒ split before ratification | S-6 | WO-0113/WO-0104a vs the clean-close profile |
| P-4 | **Review-round budget:** 2 rounds on one delivery ⇒ re-cut or seat change (formalizes what WO-0113 and the R6aR swap did late) | S-6 | PR #9 chain |
| P-5 | **Mutation-currency registry:** map each decisive pin to its guarded span; CI flags span changes without recorded re-verification | S-3 | REV-0045 P0-2; REV-0038 F4; REV-0041 C-3 |
| P-6 | **Ledger/provenance hardening:** reject `"commit": "HEAD"`; CI resolver for cited SHAs; REV completeness gate (result before disposition; disposition before WO close) | S-5 | 51/119 rows; REV-0030/0034/0036/0044 |
| P-7 | **Cross-cutting-concern registry + contract test:** every mutating facade command enumerated once; parametrized test asserts actor/clock threading per command | S-2 | dropped-actor ×3; dropped-clock REV-0032 |
| P-8 | **Parity-verifier completeness meta-test:** `ReadModelProjection` field set must cover every projector output | S-3 | REV-0007 F001 |
| P-9 | **Autospec rule:** broker-SDK mocks require `create_autospec`/`spec_set` (lint or fixture) | S-3 | X-002 ×2 |
| P-10 | **Dual-store parametrization check:** tests touching store seams must carry both store params | S-2 | R6aR SQLite-only heal pins; REV-0039 F2 |
| P-11 | **Replay-coverage gate:** a new durable event type ships with projector/replay/parity coverage in the same WO | S-4 | CC-04; 13 uncovered event types |
| P-12 | **State-file template carries `toolchain-incidents`** (re-lands PROC-0001 #1 structurally) + inverse staleness check for DRAFT WOs untouched N days | S-4 | PROC-0001; WO-0102/0103/0104 DRAFT 17 days |
| P-13 | **Result-template linter:** frozen SHA + interpreter stanza + pasted probe or explicit could-not-verify + numeric counts; ban bare "Exit code: 0"; add `INCONCLUSIVE-ENV` verdict token | S-5, S-7 | REV-0004/0009..0014/0019..0021 |
| P-14 | **INV↔probe linkage checker:** every INV names ≥1 enforcing test; INV text amendments must touch their named enforcement in the same commit | S-4 | INV-050/074/085 overclaims; ADR-008 ×3 rounds |

## Shipped with this audit (operator ratification 2026-07-28)

ADR-014 (vocabulary rename, zero behavior change, battery-gated); ADR-015 + nightly
mutmut workflow + `requirements-mutation.txt`; `tests/test_derived_truth_single_source.py`
(S-1's gate, mutation-verified); three standing rules in
`pkl/architecture/testing-model.md`; conformance oracle wired into CI (AUD2-C002
closed); repo-primer oracle-invocation correction.

## What this audit deliberately does not conclude

No verdict on any open gate (REV-0045 remains Codex-owned; R-1/R-2 open; D-2a OFF; R6b
blocked). No claim that the queue is complete — P-items were selected for mechanism per
defect; the four analyst reports contain the full candidate set and dissenting detail.
