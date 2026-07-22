---
type: Review Request
rev_id: REV-0040
title: "WO-0135 — malformed-lineage recovery reuse blocker verification"
status: STAGED
packet_kind: BLOCKER_VERIFICATION
dispatch_state: READY_FOR_INDEPENDENT_REVIEW
reviewer_seat: Claude
targets: [WO-0135, ADR-012, malformed-lineage-recovery]
human_gated_surfaces: [event-log-truth, operator-recovery-release]
review_base_sha: 521be1f7a48ef4e05eb0228fcf438318156bee27
head_sha: 249f9be08bb6a7d7ac09022702ac41ccad1dc9c5
commit_range: 521be1f7a48ef4e05eb0228fcf438318156bee27..249f9be08bb6a7d7ac09022702ac41ccad1dc9c5
branch: codex/signal-r4-store
created: 2026-07-22
---

# REV-0040 — independent verification of the WO-0135 reuse blocker

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
the active WO, and the curated sources below. Reproduce the gate finding from current code; do not
accept the author's probe or the planning seat's pre-ratified reuse design as a verdict.

Create only `work/review/REV-0040/result.md`. Do not edit this request, the work order, code,
tests, ADR-012, invariant text, ledger, or another packet. Produce findings only. Each finding
requires `file:line`, why it matters, and what resolves it. End with exactly one verdict:
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, and state anything not independently verified.

This is a **blocker-verification packet**, not an implementation review. The WO's read-only GATE
fired before RED test or source work. No `app/monitoring.py`, `tests/**`, `app/store/**`, model,
event, schema, API, facade, cockpit, ADR, invariant, or ledger change was made for Lane B. A verdict
must not claim the requested durable record ships in this range.

The operator's continuation boundary is explicit:

```text
Keep WO-0135 BLOCKED. Do not weaken ADR-012 or implement a replacement mechanism in this session. Stage REV-0040 for Claude to verify the reuse blocker and assess, as a non-authoritative proposal, whether a purpose-built malformed-lineage operator-review record is the appropriate next design direction. Any exact schema, event vocabulary, lifecycle, operator command, new WO, or implementation requires subsequent planning and explicit human approval.
```

## Exact evidence range

Review:

`521be1f7a48ef4e05eb0228fcf438318156bee27..249f9be08bb6a7d7ac09022702ac41ccad1dc9c5`

That range contains one documentation/evidence commit, `249f9be`, modifying only:

- `work/active/WO-0135-malformed-lineage-needs-review-record.md`;
- the Lane B rows and NEEDS-INPUT section of `work/active/SIGNAL-R4-STATE.md`.

The active WO was moved from queue in the earlier activation commit `7f918b4`; read its complete
current body as the binding contract. No implementation diff exists.

## The contract to disprove or confirm

The pre-ratified design requires all of these to be simultaneously true:

1. `create_submit_recovery` accepts synthetic
   `(local_order_id="lineage:<envelope.id>", broker_order_id="")` with no local Order row,
   cleanup status `needs_review`, and stable immutable envelope scope.
2. Repeating that creation is idempotent on memory and SQLite: one recovery row, one
   `SUBMIT_RECOVERY_NEEDS_REVIEW` event, same record id, and `claim_occurrence is None`.
3. The record remains human-actionable and can resolve only through ADR-012's typed
   HUMAN_ATTESTED reconcile to `operator_reconciled`.
4. A later corrupt-lineage tick sees the terminal row and never re-creates or re-flags it.

The implementer found that items 1–2 hold but item 3 cannot: the typed attestation requires a
non-empty broker id, and both stores require the referenced real Order plus trustworthy
owner/envelope lineage and a durable submission-claim occurrence. The synthetic recovery has none
of them. Therefore the required post-reconcile pin in item 4 cannot be constructed through the
approved boundary.

## Curated code and authority

- Binding design/evidence: `work/active/WO-0135-malformed-lineage-needs-review-record.md`.
- Intended call site (read only): `app/monitoring.py`, malformed-lineage branch around the current
  `_converge_envelope_disposition_cancels` warning/return.
- Creation contract: `app/store/base.py:873`, `app/store/memory.py:4147`, and
  `app/store/sqlite.py:5836`.
- Typed identity: `app/models.py:1038` (`broker_order_id` min length) and
  `app/models.py:1047` (`SubmitRecoveryAttestation`).
- Human-release planner/guard: `app/store/core.py:2956-3153`, especially the fail-closed lineage
  check around `app/store/core.py:3000`.
- Store lineage resolution: `app/store/memory.py:4350-4367` and
  `app/store/sqlite.py:6092-6112`.
- Store release methods: `app/store/memory.py:4598` and `app/store/sqlite.py:6366`.
- Accepted authority: `docs/adr/ADR-012-submit-recovery-operator-release.md`.
- Existing typed/recovery tests: `tests/test_wo0114_pd1_release_valve.py`,
  `tests/test_wave0_submission_claim.py`, `tests/test_wo0113_store_parity.py`, and adjacent
  recovery/convergence tests discoverable from the named methods.

No `INV-*` definition was added or amended, so there is no new-invariant probe debt.

## Mandatory fresh disproof probes

Use OS-temporary pytest/probe state and both store implementations. Do not persist a harness in the
repository.

1. Create the exact synthetic recovery three times with the WO's immutable scope. Record ids,
   total rows, total matching audit events, cleanup status, and payload `claim_occurrence`. Confirm
   whether memory and SQLite agree.
2. Construct `SubmitRecoveryAttestation` normally with the recovery's exact echoed fields and
   `broker_order_id=""`. Record the typed validation result; do not silently substitute a fake
   non-empty broker id.
3. Only to isolate the deeper store guard, use a non-persisted test object that bypasses Pydantic
   construction while preserving the exact empty-id/synthetic-order values, then call each store's
   `reconcile_submit_recovery`. Require the precise failure layer and prove zero status/event/fill/
   position writes after failure and SQLite restart.
4. Repeat with a fabricated non-empty broker id but the same missing synthetic Order. Determine
   whether the real-order/lineage guard still rejects it. Then seed only an Order row, only owner
   lineage, and only a claim occurrence in isolation; identify the complete minimum authority set
   ADR-012 requires. These are disproof probes, not proposed production work.
5. Search every public operator route/facade/store entry for an alternate legitimate terminal
   transition. Report any path that can reconcile the synthetic record without the same exact
   identity/lineage/claim evidence; that may be a safety bypass rather than a solution.
6. Confirm `needs_review` remains visible through the operator open-status query and absent from the
   automatic unresolved-recovery loop. Visibility alone does not satisfy a lifecycle that promises
   operator disposition.

## Boundary questions

1. Is the author's contradiction real on both stores, or is there an existing typed, authorized
   ADR-012 route that can reconcile this synthetic pair without weakening identity?
2. Does `claim_occurrence is None` merely make creation deterministic, or does it make release
   intentionally impossible under the hardened occurrence-scoped lifecycle?
3. Would accepting the current reuse design strand permanent open records that the stated operator
   surface cannot disposition?
4. Can any monitoring-only change satisfy D-ML-1..5, or would every viable solution require a new
   durable vocabulary/table, store lifecycle, typed operator command, or revised ADR authority?
5. Would weakening broker-id, real-order, owner-lineage, or claim-occurrence guards create a bypass
   for ordinary submit-recovery release? Treat such weakening as a P0, not a convenient fix.
6. Did the implementer obey the STOP condition by avoiding all production/test/store/model/event
   edits after reuse proved unsound?

## Expected resolution boundary

If the contradiction reproduces, the current mechanism cannot be implemented honestly under
WO-0135. Assess, strictly as a **non-authoritative proposal**, whether a purpose-built
malformed-lineage operator-review record is the appropriate next design direction. Do not define
or authorize its exact schema, event vocabulary, lifecycle, operator command, new work order, or
implementation; every such surface requires subsequent planning and explicit human approval. Do
not prescribe weakening ADR-012's submit-recovery identity, lineage, claim, fill, or position
safeguards.

## Author evidence to reproduce skeptically

- Memory: three creates returned one id; one row; one event; `claim_occurrence=None`.
- SQLite: the same one-id/one-row/one-event result; `claim_occurrence=None`.
- Normal typed attestation: rejected `broker_order_id=""` because the string requires at least one
  character.
- Deeper memory and SQLite probes: both rejected with
  `recovery lineage is not trustworthy: referenced local order is missing`.
- No Lane B production/test edit, venue call, guessed target, schema, vocabulary, or ledger change.

Treat these as claims to reproduce. If the lifecycle is actually reachable, provide the exact
typed call path and fresh dual-store evidence in the finding; do not infer reachability from the
status transition graph alone.

## Expected output

Write findings only to `work/review/REV-0040/result.md`, then one verdict. `BLOCK` any claim that
WO-0135 is implemented, any unreachable promised operator lifecycle, any proposed weakening of
ADR-012 authority, any production change outside the pre-ratified monitoring-only scope, or any
unreproducible gate evidence. Any design-direction assessment is advisory only and must not be
written as approved architecture or implementation authority.
