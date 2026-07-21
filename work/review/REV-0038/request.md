---
type: Review Request
rev_id: REV-0038
title: "WO-0131 — fail-closed envelope replay FSM legality"
status: STAGED
reviewer_seat: Claude
targets: [WO-0131, envelope-replay, read-model-projection]
human_gated_surfaces: [event-log-truth, replay-read-model-interpretation]
review_base_sha: cf50f115c55b04d2111a17ec9207b004dd4b8b7e
head_sha: b99d8c03ca56fbba66f21ce958da2b0364c72df6
commit_range: cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
branch: codex/ultra-beta-batch
created: 2026-07-21
---

# REV-0038 — independent review of envelope replay FSM legality

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
and the curated targets below. Re-derive the behavior from the frozen range and fresh probes; do
not accept the author's evidence as a verdict.

Create only `work/review/REV-0038/result.md`. Do not edit this request, the work order, source,
tests, ADRs, invariants, ledger, or another packet. Produce findings only. Each finding requires
`file:line`, why it matters, and what resolves it. End with exactly one verdict: `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`, and state anything you could not independently verify.

## Gate and frozen semantic range

This changes how persisted envelope lifecycle truth is interpreted during replay/read-model
reconstruction. The operator authorized this exact WO-0131 remediation, but it is not relied upon
until this independent packet returns and is dispositioned. Paper only: no live mode, credential,
broker call, schema/DDL, migration, store write, position/fill rule, facade, API, cockpit, or
monitoring change is in scope.

Review the frozen semantic/test range:

`cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6`

- `d0665b3` — red-first exhaustive transition matrix and correction of the old synthetic
  `ACTIVE → CANCELLED` positive fixture to canonical `FROZEN → CANCELLED`.
- `b99d8c0` — consume `ENVELOPE_TRANSITIONS` in the projector and add the aggregate read-model
  fail-closed pin.

The activation commit `cf50f11` is the exclusive base. The later request/status staging commit is
deliberately outside the range so the packet never reviews itself.

```powershell
git rev-parse cf50f115c55b04d2111a17ec9207b004dd4b8b7e
git rev-parse b99d8c03ca56fbba66f21ce958da2b0364c72df6
git diff --stat cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
git diff --name-status cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
git diff --check cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
git diff cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
```

The range changes exactly:

- `app/events/projectors.py` — imports the canonical `ENVELOPE_TRANSITIONS` graph and refuses an
  event target absent from the projected current state's outgoing set.
- `tests/test_wo0125_envelope_replay_parity.py` — exhaustive representable edge matrix, explicit
  vocabulary coverage, legal terminal fixture correction, direct replay pin, and aggregate
  `project_read_models` pin.

No invariant or ADR text is added or amended, so this packet has no new-`INV-*` fresh-probe debt.

## Authority and behavior to verify

1. `app/transitions.py::ENVELOPE_TRANSITIONS` remains the sole canonical graph; the projector
   consumes it without copying, widening, or changing it. The import must not create a cycle or
   violate an architecture contract.
2. Replay still validates persisted `from == projected current` and `to == event-type target`, then
   additionally requires that target in `ENVELOPE_TRANSITIONS[current]`. Payload text must never
   choose the graph node independently.
3. An illegal edge raises `ProjectionError` before status/supersession mutation. In particular,
   `PENDING → COMPLETED`, `ACTIVE → CANCELLED`, `FROZEN → COMPLETED`, every terminal-state outgoing
   edge, and self-transitions must fail closed.
4. Every canonical legal edge still projects, including pre-activation escape edges,
   `ACTIVE ↔ FROZEN`, `FROZEN → CANCELLED`, and `FROZEN → BREACHED`. The deliberate absence of
   `FROZEN → COMPLETED` must remain observable.
5. `PENDING` is the creation snapshot state and has no lifecycle target event. Verify the explicit
   test mapping covers every other `EnvelopeStatus`, and the legal/illegal sets cover the full
   `10 source states × 9 representable targets` cross-product without duplicates or omissions.
6. The changed terminal fixture is not weakened: `FROZEN → CANCELLED` remains positively tested,
   while `ACTIVE → CANCELLED` is now explicitly in the forbidden matrix.
7. `project_read_models` propagates the same `ProjectionError`; there is no alternate replay path
   that bypasses `project_envelopes` or swallows the exception.
8. Legitimate memory and SQLite event producers emit only edges in the canonical graph. If any real
   producer stream is rejected, return a finding rather than weakening legality enforcement.

## Mandatory fresh disproof probes

Do not satisfy these only by rerunning the author's matrix:

1. Build a fresh event stream with a valid creation snapshot followed by `PENDING → COMPLETED`;
   require both `project_envelopes` and `project_read_models` to raise `ProjectionError`.
2. Build a legal `ACTIVE → FROZEN → ACTIVE` stream and a legal `ACTIVE → FROZEN → BREACHED` stream;
   require exact final status and no false rejection.
3. For each terminal state, construct it through a legal prefix, then append at least one correctly
   shaped status event. Require fail-closed behavior without relying on malformed `from`, `to`,
   identity, or supersession payload.
4. Drive real memory and SQLite stores through representative pre-activation, active, frozen, and
   terminal edges, then replay their persisted logs. Require replay status to match each store's
   read model and report any producer/graph disagreement.

## Required mutation pass

Apply each mutation temporarily, run the narrow decisive nodes, and restore without destructive
checkout:

- disable or invert the graph-membership check: direct replay and aggregate read-model illegal-edge
  pins must turn red;
- check membership against the event payload `from`/`to` instead of the projected/current enum:
  mismatch and illegal-edge pins must turn red;
- skip validation for one terminal source or for `ENVELOPE_COMPLETED`: the exhaustive matrix must
  turn red;
- reject one known legal edge in the projector only: its legal-edge node and at least one real-store
  replay/parity path must turn red.

If a relevant pin stays green, report an inert-test finding. Restore every mutation before writing
`result.md`.

## Curated targets

- Contract: `work/active/WO-0131-replay-fsm-transition-legality.md`
- Projector: `app/events/projectors.py::project_envelopes`
- Canonical graph (read only): `app/transitions.py::ENVELOPE_TRANSITIONS`
- State-machine record (read only): `docs/adr/ADR-010-execution-envelope.md` §3
- Tests: `tests/test_wo0125_envelope_replay_parity.py`
- Adjacent aggregate path: `app/events/replay.py::project_read_models`
- Existing parity/conformance corpus: `tests/test_phase6b_readmodel_parity.py`,
  `tests/test_wo0007a_stage4_dual_store_parity.py`,
  `tests/test_wo0036_r2_parity_adversarial.py`,
  `tests/test_wo0036_r2_projection_scope_parity.py`, `tests/test_wo0113_store_parity.py`, and both
  R2 conformance oracles.

Forbidden/out of scope: editing `app/transitions.py`; changing the FSM; store/monitoring/facade/API/
cockpit behavior; event vocabulary or schema; DDL/migration; tests weakened or deleted; ADR/INV
text changes; credentials, broker calls, or live mode; close-out, disposition, ledger, merge, or
reviewing unrelated remediation WOs.

## Author evidence to reproduce skeptically

- Untouched focused baseline: `14 passed`.
- Direct pre-fix probe: `ILLEGAL_EDGE_ACCEPTED=completed` for synthetic `PENDING → COMPLETED`.
- RED node: `DID NOT RAISE ProjectionError` for `pending-to-completed`.
- Pre-fix positive controls: 15 legal edges + six terminal folds + vocabulary accounting,
  `22 passed`.
- Post-fix full WO-0125 replay file: `106 passed`.
- Membership-check mutation: direct replay and aggregate read-model pins both failed; restored
  full file green.
- Existing replay/parity/conformance corpus: `282` collected nodes, exit `0` (six documented
  conformance skips).
- Full repository suite on `b99d8c0`: `4205` collected nodes; exit `0` after `395.6s`; `11 skipped`,
  `1 xfailed`.
- Static/architecture: Ruff clean; mypy clean across 70 source files; import-linter 6 contracts
  kept, 0 broken; frozen-range diff check clean.

Treat every green count as a claim to reproduce, not certification. Pytest scratch must use an
OS-temporary basetemp; do not create repo-root scratch directories.

## Questions to answer

1. Can any correctly shaped but FSM-illegal status event still mutate replay or read-model state?
2. Can any legal producer edge be rejected because event-type mapping, frozen resume semantics, or
   supersession payload handling diverges from the graph?
3. Does the exhaustive matrix truly cover all 90 representable source/target pairs, including all
   terminal states and the deliberate `FROZEN → COMPLETED` non-edge?
4. Is the test expectation independent enough to kill a removed projector check, or does deriving
   case labels from the canonical graph create an inert pin?
5. Does any alternate replay/parity path bypass or swallow the fail-closed exception?
6. Did the frozen range stay within authorization and avoid any store-write, schema, vocabulary,
   ADR/INV, broker/live, or unrelated behavior change?

## Expected output

Write only `work/review/REV-0038/result.md`, findings first and then one verdict. `BLOCK` any
legitimate producer/FSM disagreement, bypassable replay path, non-failing illegal-edge pin,
unreproducible green claim, or unapproved gated/schema/live-surface change.
