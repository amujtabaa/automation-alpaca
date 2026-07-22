---
type: Review Request
rev_id: REV-0039
title: "WO-0134 — Signal Seat R4 model, planner, dual-store persistence, and replay"
status: STAGED
dispatch_state: HOLD_PENDING_OPERATOR_GATE_DECISIONS
reviewer_seat: Claude
targets: [WO-0134, ADR-009, signal-seat-r4]
human_gated_surfaces: [schema-DB-migration, event-log-truth, replay-read-model]
review_base_sha: 9d60b74dcc3ef5d5dcc2a09899dd7395dbf2a6dc
head_sha: b87d464cdf189e345b688a01cfbc9c18f8bc9d05
commit_range: 9d60b74dcc3ef5d5dcc2a09899dd7395dbf2a6dc..b87d464cdf189e345b688a01cfbc9c18f8bc9d05
branch: codex/signal-r4-store
created: 2026-07-22
---

# REV-0039 — independent review of Signal Seat R4

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
and the curated targets below. Re-derive behavior from the frozen semantic range and fresh,
failure-capable probes. Do not accept the author's evidence or schema approval as a correctness
verdict.

When this packet is dispatched, create only `work/review/REV-0039/result.md`. Do not edit this
request, either work order, source, tests, ADR/spec text, invariant text, ledger, or another
packet. Produce findings only. Each finding requires `file:line`, why it matters, and what
resolves it. End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, and list
anything not independently verified.

This request is staged on **HOLD** because two gate-contract decisions remain open: the mandated
staged tests are not Ruff-format-clean, and the kickoff's literal direct-script oracle invocation
is not import-safe. Staging this packet does not flip WO-0134 from ACTIVE to REVIEW and does not
authorize beta reliance.

## Frozen semantic range and approval boundary

Review the Signal Seat files in:

`9d60b74dcc3ef5d5dcc2a09899dd7395dbf2a6dc..b87d464cdf189e345b688a01cfbc9c18f8bc9d05`

The range also contains the disjoint WO-0135 activation/blocker record. Exclude commit `249f9be`
and `work/active/WO-0135-malformed-lineage-needs-review-record.md` from this semantic review.
The curated WO-0134 commits are:

- `7f918b4` — activate both work orders and establish the continuity record;
- `521be1f` — add the three authoritative staged RED tests byte-identically;
- `ba1594d` — add Signal model and execution-event vocabulary;
- `4d9779d` — add the pure planner, StateStore contract, memory integration, projector/replay,
  properties, and supporting tests;
- `f57525f` — record non-SQLite RED/GREEN and mutation evidence;
- `6947966` — record the operator's schema approval before any SQLite edit;
- `b87d464` — implement the approved SQLite DDL, migration guards, atomic store methods, and
  schema/rollback tests.

The operator approved exactly the presented `signal_records` DDL, two indexes, exact column-shape
guard, and `UNIQUE(producer_id, signal_id)` guard. The approval recorded before the SQLite commit
was:

> The DDL plus guard looks fine as far as I'm concerned. You may proceed.

Approval authorizes review of the gated change; it is not evidence that the implementation or DDL
is correct. Any deviation from the approved package is a P0.

## What changed

- `app/models.py:168,477,698` — additive `SignalStatus`, eight event types, and `SignalRecord`.
- `app/store/base.py:329,1315` — result type and the three typed StateStore signal methods.
- `app/store/core.py:5583,6013` — constants, sanitization, injective dedupe/hash semantics,
  persisted A-3 deadline planning, one-fact event construction, echo/conflict behavior, and
  caller-supplied server/cycle limits.
- `app/store/memory.py:245,533,5531` — signal state in `_atomic`, ingest/read/list methods, and
  event/record co-write.
- `app/store/sqlite.py:422,1041,7564,7606` — approved DDL/indexes, fail-closed startup guard,
  row mapping, and one-transaction ingest/read/list.
- `app/events/projectors.py:828` and `app/events/replay.py:149,175` — signal lifecycle fold,
  conflict exclusion, defaulted read-model field, replay registration, and parity diff.
- Three staged tests plus additive pure Hypothesis and SQLite schema/atomicity tests.

No ADR, spec, invariant, API, facade, config, launcher, cockpit, broker adapter, monitoring,
credential, live-mode, or ledger surface is changed. No `INV-*` definition was added or amended.

## Authority and behavior to verify

1. Re-derive every `SignalRecord` field, type, nullability rule, and enum/event value from
   ADR-009 plus `docs/spec/signal-seat/01-schema.md` and `02-lifecycle.md`. Validation quarantine
   may null only `issued_at`, `ttl_seconds`, and `expires_at`; `received_at` and raw offenders must
   remain durable.
2. Prove A-3 is exact: `expires_at = min(received_at + server_max_ttl_seconds, issued_at +
   ttl_seconds)`, with ttl `[30,86400]`, future skew `+30s`, stale skew `-24h`, inclusive boundary
   behavior, persisted deadline, and injected clock only. Rails/config defaults are not in R4.
3. Prove `(producer_id, signal_id)` encoding is injective and persistence uniqueness matches it.
   Identical content must be a write-free echo; a different payload hash must append exactly one
   conflict audit event without replacing or changing the original record/status.
4. Terminal-at-ingest cases emit one terminal event, not received-plus-terminal. Every attributable
   event carries the stable `record_id`, persisted `expires_at`, and caller-provided
   `cycle_budget_limit` required by downstream projection.
5. Compare memory `_atomic` and SQLite transaction ordering. Any event insert, row insert, mapper,
   constraint, or exception failure must roll back both sides; restart must preserve byte-equivalent
   records and event replay.
6. Compare committed SQLite DDL and `_migrate` guard byte-for-byte with the approval record and
   field-by-field with the accepted schema. Existing malformed shape or missing unique identity
   must refuse startup; the guard must not accept alternate affinity, nullability, PK, or index
   ordering.
7. Prove `project_signal_records` is identity-fail-fast, record-scoped, terminal-latching, and
   forward-compatible only where the spec permits. `SIGNAL_DUPLICATE_CONFLICT` must never enter the
   lifecycle fold.
8. Prove every aggregate replay path includes signals and reports divergence. The additive default
   must preserve legacy callers without allowing a persisted signal stream to disappear from
   parity comparison.
9. Reconfirm INV-1/INV-9: no `SIGNAL_*` or `PRODUCER_*` fact can alter positions. Drive fresh
   memory and SQLite ingests and require `list_positions()` and `PositionProjector` output to remain
   unchanged before and after replay.
10. Audit the complete diff for scope: especially accidental normalization of the three staged
    blobs, schema changes beyond approval, a hidden wall clock, or any R5/R6/R7 behavior.

## Mandatory fresh disproof probes

Do more than rerun the authored tests:

1. On each store, ingest the same identity with identical content, then conflicting content, then
   the original content again. Require one record, one birth/terminal event, one conflict event,
   stable original bytes/status, and no extra event on either echo; close/reopen SQLite between
   steps.
2. Exercise A-3 around all exact boundaries with a server cap smaller than the producer ttl,
   including deadline equal to `received_at`. Require the persisted deadline to survive replay and
   a later wall-clock change without re-derivation.
3. Inject a failure after SQLite event insertion and separately after record insertion; require
   zero partial truth after restart. Apply equivalent exceptions inside memory `_atomic` and
   require its snapshot to restore signal and event state.
4. Create legacy databases with one wrong column property at a time and with an alternate/reversed
   uniqueness definition. Require deterministic startup refusal before any mutation.
5. Feed projector streams with mismatched producer/signal/record identities, conflict-only birth,
   unknown future event types, and terminal-then-approved sequences. Distinguish required
   fail-closed cases from deliberate forward-compatible no-ops.
6. Delete signal registration from `project_read_models` temporarily. At least one parity test must
   fail. Restore it and report any aggregate path that remains blind.

## Required mutation pass

Apply each mutation temporarily and restore it without destructive checkout:

- replace A-3 `min` with `max`: the property corpus must falsify it;
- make the dedupe encoding separator-based/non-injective: a cross-producer or crafted-identity pin
  must turn red;
- treat a different hash as replay or replace the original row: conflict/audit-only tests must turn
  red on both stores;
- remove signal state from memory rollback or split SQLite event/record writes across commits: the
  injected atomicity controls must turn red;
- admit a malformed SQLite column or remove the unique-key check: schema guards must turn red;
- fold `SIGNAL_DUPLICATE_CONFLICT` or remove the terminal latch: projector tests must turn red;
- remove replay registration/diff comparison: aggregate parity must turn red.

If a relevant pin remains green, report an inert-test finding. Restore all mutations before
writing `result.md`.

## Curated authority and tests

- Contract/evidence: `work/active/WO-0134-signal-model-store-integration.md` and
  `work/active/SIGNAL-R4-STATE.md`.
- Accepted authority: `docs/adr/ADR-009-signal-seat-boundary.md`,
  `docs/spec/signal-seat/01-schema.md`, `docs/spec/signal-seat/02-lifecycle.md`.
- Implementation: the seven `app/` files listed above.
- Authoritative staged corpus: `tests/test_signal_seat_models.py`,
  `tests/test_signal_ingest_store.py`, `tests/test_signal_projector_forward_compat.py`.
- Additive hardening: `tests/test_signal_ingest_properties.py` and
  `tests/test_signal_sqlite_schema.py`.
- Adjacent replay/position checks: `tests/test_phase6b_readmodel_parity.py`,
  `tests/test_wo0125_envelope_replay_parity.py`, and `tests/r2_conformance_oracle.py`.

Forbidden/out of scope: R5 endpoint/auth/launcher/helper work; R6 rails; R7 conversion; API,
facade, config, main/server/launchers, cockpit, monitoring, adapters, ADR/spec/invariant edits,
staging-branch mutation, credentials, broker/live behavior, close-out, ledger, merge, or fixes by
the reviewer.

## Author evidence to reproduce skeptically

- RED collection: missing Signal model/projector imports; SQLite store abstract before the gated
  implementation; four new SQLite guard/atomicity tests red at the same boundary.
- Focused Signal suite: `66 passed` on memory and SQLite.
- Pure property suite: `9 passed`; deliberate A-3 `min`→`max` mutation was falsified at
  `issued_offset=0`, `ttl_seconds=30`, `server_max_ttl=1`.
- Three staged blob ids remain exact: `a4de2669e694e3608d53cde42765d73195c58404`,
  `9513d50eedce42c09ff1a2b6bfb4627c70121c34`,
  `a3ed1b5dc51b19ea94509d17da4447b7e9d476f6`.
- Full pytest: 4,275 collected nodes, exit 0, progress reached 100%.
- Ruff check, mypy (70 files), import-linter (6 kept/0 broken), canonical pytest R2 oracle
  (61 cases), and repair scaling (13 cases) passed.
- `ruff format --check .` is **not green**: it names the three exact staged blobs and seven files
  byte-identical to `origin/master`. All implementation-owned non-staged files pass.
- Literal `python tests/r2_conformance_oracle.py` is **not green**: direct execution cannot import
  top-level `app`; the unchanged canonical pytest invocation passes all 61 cases.

Treat every count as a claim to reproduce, not certification. Use OS temporary pytest scratch;
never create a repository-root basetemp.

## Questions to answer

1. Can any malformed, stale, future, expired, echo, or conflict path create two lifecycle outcomes,
   replace original truth, or omit required durable payload?
2. Can memory and SQLite disagree after rollback, conflict, restart, or replay?
3. Can the approved schema guard accept an unapproved shape or reject the exact approved shape?
4. Can a signal event mutate position or disappear from aggregate replay/parity?
5. Are the staged tests and additive properties failure-capable across planner, store, and projector
   mutations?
6. Did the frozen semantic range stay within the human approval and WO boundaries?
7. Independently confirm whether the two disclosed command/format conflicts are repository-contract
   blockers; do not silently waive them in the verdict.

## Expected output

After dispatch, write findings only to `work/review/REV-0039/result.md`, followed by one verdict.
`BLOCK` any unapproved DDL/migration deviation, safety-invariant breach, partial event/record truth,
non-injective dedupe, mutable conflict/echo behavior, replay/position bypass, inert decisive test,
or unreproducible completion claim.
