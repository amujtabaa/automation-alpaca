---
type: Review Result
rev_id: REV-0040
reviewer: "Claude (independent seat; implementer Codex)"
packet_kind: BLOCKER_VERIFICATION
commit_range: 521be1f7a48ef4e05eb0228fcf438318156bee27..249f9be08bb6a7d7ac09022702ac41ccad1dc9c5
branch: codex/signal-r4-store (reviewed at 58b4296)
verdict: ACCEPT
date: 2026-07-22
---

# REV-0040 — independent verification of the WO-0135 reuse blocker

Environment: isolated git worktree detached at `58b4296` (tip of `codex/signal-r4-store`;
the packet head `249f9be` is an ancestor), pinned repo venv
`/home/user/automation-alpaca/.venv` (Python 3.12.3), cloud Linux container. All probes were
throwaway scripts in an OS-scratch directory (deleted before this write); SQLite state in
OS-temp only; zero repo files touched except this result. I verified the Lane B recovery
surfaces are **line-identical** between the packet head `249f9be` and my checkout `58b4296`
(the intervening commits are Lane A signal-store work plus `work/` docs: hunk-level diff of
`app/store/{core,memory,sqlite,base}.py`/`app/models.py` shows only signal additions;
`app/monitoring.py`, `app/facade/store_backed.py`, `app/api/routes_trading.py` unchanged), so
probing at `58b4296` validly reproduces the packet-range claims. The author's probe outputs
were treated as claims and regenerated, never trusted.

## Contract items 1–2 (claimed MET) — reproduced on both stores

Fresh probe, the exact pre-ratified D-ML scope (`local_order_id="lineage:<uuid>"`,
`broker_order_id=""`, `client_order_id=<envelope id>`, immutable qty, `needs_review`,
`SUBMIT_RECOVERY_NEEDS_REVIEW`), created **three times** per store:

```text
[P1 memory] same_id=True rows=1 events=1 status='needs_review' claim_occurrence_payload=[(False, None)]
[P1 sqlite] same_id=True rows=1 events=1 status='needs_review' claim_occurrence_payload=[(False, None)]
[P1 sqlite-restart] re-create same_id=True   (after close + reopen of the same DB file)
```

One record, one audit event, identical id across all three calls, `claim_occurrence` absent
from the creation payload (i.e. `None` — `app/store/memory.py:4263-4265` pops it and only
re-adds a non-None value; SQLite path identical). Stores agree; SQLite dedup survives
restart. Items 1–2 **CONFIRMED MET**, matching the author's `fable_done` evidence lines
verbatim.

## Contract item 3 (claimed BLOCKED) — reproduced, all rejection layers regenerated

**Layer 1 — typed identity.** Constructing `SubmitRecoveryAttestation` normally with the
record's own durable `broker_order_id=""`:

```text
[P2 memory] typed rejection loc=('broker_order_id',) msg='String should have at least 1 character' type='string_too_short'
[P2 sqlite] identical
```

Source: `app/models.py:1038` (`SubmitRecoveryIdentity.broker_order_id: Field(min_length=1)`),
inherited by `SubmitRecoveryAttestation` (`app/models.py:1047`). This typed model is the
**only** shape accepted at every approved entry: FastAPI route
`app/api/routes_trading.py:242-244` and facade `app/facade/store_backed.py:721-733`. The
author's decisive string ("String should have at least 1 character") regenerated exactly.

**Layer 2 — store lineage guard.** Bypassing pydantic via `model_construct` (probe-only, per
the request) while preserving the exact empty-id/synthetic values, then calling
`reconcile_submit_recovery` on each store:

```text
[P3 memory] RecoveryTransitionError: recovery lineage is not trustworthy: referenced local order is missing
[P3 sqlite] identical; rejection persists after SQLite close/reopen
```

Guard code, cited from current source: the lineage resolvers return the error string
(`app/store/memory.py:4365-4367`; `app/store/sqlite.py:6108-6112` — `order_row is None →
"referenced local order is missing"`), and the shared fail-closed validator raises it first,
before any echo comparison (`app/store/core.py:2998-3001` inside
`validate_submit_recovery_identity`, called at `app/store/memory.py:4624-4632` /
`app/store/sqlite.py:6389-6397`). The author's decisive string regenerated exactly, both
stores.

**Write-free after failure** (request probe 3): before/after counts around the failed
reconcile — rows=1, status still `needs_review`, needs_review events=1, reconciled events=0,
fills=0, positions=0, `unchanged=True` on both stores, and identical after SQLite restart.
The guard fires before the atomic commit block (`app/store/memory.py:4681`;
`app/store/sqlite.py:6376` `_tx` rolls back), so zero truth writes.

**Fabricated non-empty broker id** (request probe 4): same missing synthetic order —

```text
[P4 memory/sqlite] recovery lineage is not trustworthy: referenced local order is missing
```

and with an Order row seeded (isolation below), the echo guard takes over:

```text
[L2 fabricated-id] recovery identity mismatch for broker_order_id: echoed 'fabricated-broker-1', durable ''
```

(`app/store/core.py:3017-3023`). This is a **pincer**: the typed layer requires a non-empty
id while the durable echo requires exactly the record's `""` — so no attestation, honest or
fabricated, can ever satisfy both for an empty-sentinel record. The blocker is not merely
"missing data"; it is structurally closed from both sides.

**Guard-chain isolation cascade** (memory store; fake internal-state injection impossible
through any approved boundary):

| Seeded state | Rejection |
|---|---|
| L0 nothing | `recovery lineage is not trustworthy: referenced local order is missing` |
| L1 Order row only | `recovery lineage is not trustworthy: sell-intent owner is missing` |
| L2 Order + owner row | `recovery cannot be bound to a durable submission claim occurrence` (`app/store/memory.py:4635-4638`; `app/store/sqlite.py:6400-6404`) |
| L3 Order + owner + pre-dated fake `SUBMIT_PENDING` claim event | **SUCCEEDED → operator_reconciled** |

Two side-findings from the cascade: (a) the `Order` model itself refuses an ownerless row
("order must have exactly one origin: candidate_id XOR sell_intent_id") — a synthetic
lineage order cannot even be *modeled* without fabricating an owner; (b) L3 succeeding only
after **three** internal fabrications plus a pydantic bypass proves the minimum authority set
ADR-012 requires is exactly: a real Order row with matching scope, an existing origin owner
(and unambiguous envelope lineage), a durable `SUBMIT_PENDING` claim occurrence predating the
record, a non-empty broker id surviving the typed layer, plus terminal-state/fill parity.
The synthetic record structurally lacks the first three and can never acquire them: a
`SUBMIT_PENDING` event for order_id `lineage:<uuid>` can only be minted by
`claim_order_for_submission` on a real `CREATED` order (single-writer,
`app/store/base.py:830-869`), which a non-order key can never be. This answers boundary
question 2: `claim_occurrence is None` is not a benign determinism artifact — it makes
release **permanently** impossible under the hardened occurrence-scoped lifecycle.

Item 3 **CONFIRMED BLOCKED**.

## Contract item 4 — I agree it falls with item 3

The WO's post-reconcile pin requires a record in `RECOVERY_OPERATOR_RECONCILED`. The only
edge into that status is `needs_review → operator_reconciled`
(`app/models.py:979-984` — `RECOVERY_TRANSITIONS`), and the only writer is
`reconcile_submit_recovery` (blocked above). Alternate-path search (request probe 5), all
regenerated:

- `update_submit_recovery` hard-rejects the edge on both stores — probe output:
  `operator_reconciled requires the evidence-bearing operator attestation command`
  (`app/store/memory.py:4732-4736`; `app/store/sqlite.py:6508-6512`).
- Generic transitions go through `recovery_status_event` which enforces the closed graph
  (`app/store/core.py:2944-2960`); `needs_review` has no edge to `resolved_canceled`, so the
  record cannot even be laundered sideways.
- Grep over `app/` for writers of `RECOVERY_OPERATOR_RECONCILED`: only the two store
  `reconcile_submit_recovery` methods; the one facade method
  (`app/facade/store_backed.py:721`) and one route (`app/api/routes_trading.py:238-261`)
  both take the typed attestation; cockpit reaches it only through the typed API client.
  `ingest_submit_recovery_fill` never changes `cleanup_status`. **No bypass exists** — which
  is correct; a path that released the synthetic record without the identity/lineage/claim
  evidence would be a safety bypass, not a solution.

Therefore the post-reconcile pin is unconstructible through the approved boundary, and the
WO's acceptance criteria cannot be satisfied honestly. **Item 4 CONFIRMED.**

## Operator visibility (request probe 6) — confirmed

```text
[P6 memory] operator_open_visible=True auto_loop_selected=0
[P6 sqlite]  operator_open_visible=True auto_loop_selected=0
```

The record appears via `list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES)` and is never
selected by the automatic loop's `{RECOVERY_UNRESOLVED}` filter (`app/monitoring.py:3556`;
guard comment :3550). Visibility holds — but visibility without a reachable disposition does
not satisfy a lifecycle that promises operator resolution (boundary question 3: **yes**, the
reuse design strands permanently open records the stated operator surface cannot
disposition).

## Scope / stop-condition compliance (contract item on the range)

`git log 521be1f..249f9be` = exactly one commit, `249f9be` "Record WO-0135 reuse gate
blocker"; `git diff --stat` = `work/active/WO-0135-malformed-lineage-needs-review-record.md`
(+41) and `work/active/SIGNAL-R4-STATE.md` (+24/−8, Lane B rows + NEEDS-INPUT section) only.
**Zero** production, test, store, model, event, schema, vocabulary, ADR, or ledger changes.
The WO's forbidden paths were respected; the STOP condition ("reuse proves unsound → STOP and
escalate; do NOT patch `app/store/**` or add a new event type") was obeyed exactly. Boundary
question 6: **yes**.

## Findings

### F1 (new, corroborating — strengthens the blocker): the synthetic record permanently poisons symbol-level SELL-exposure rails
- **Where:** `app/store/memory.py:2966-3000` (`_open_direct_sell_recovery_ids_unlocked`
  matches any open recovery by declared symbol+SELL even with no order row), feeding
  `app/store/memory.py:3003-3022` (dispatch/claim exposure set),
  `app/store/memory.py:3030-3041` (same-symbol exit-vs-BUY preempt), and
  `app/store/memory.py:3303-3329` (flatten gate); SQLite analogues
  `app/store/sqlite.py:4412`, `:4468`, `:4799`.
- **What (probe-verified, both stores):** with nothing else in the store, one synthetic
  lineage record makes `flatten_position("AAPL")` raise
  `FlattenBlockedError: manual flatten of AAPL blocked: unresolved direct SELL exposure
  cannot be safely deduplicated (lineage:<uuid>)`, registers as a same-symbol exit that "may
  execute" (blocking crossing BUYs per the P0-2 rail), and enters the direct-SELL exposure
  ids.
- **Why it matters:** because the record is unreleasable (item 3), these blocks are
  **permanent**. Manual flatten is precisely the operator's remedy for the stranded-SELL
  scenario this WO exists to surface — the pre-ratified reuse design would irreversibly
  disable the remedy for the affected symbol. This is a second, independent unsoundness the
  WO's war-game (Hazards 1–6) did not enumerate; the implementer's blocker is, if anything,
  understated.
- **Resolves:** planning input only — any successor design must either live outside the
  submit-recovery ledger or carry a reachable terminal state; nothing to change in this
  doc-only range.

### F2 (P3 — vocabulary nuance for the next design round): "HUMAN_ATTESTED reconcile" is imprecise
- **Where:** WO-0135 Goal/§Required behavior; REV-0040 request "contract" item 3; vs
  `app/store/core.py:3152-3155` and ADR-012 §4.
- **What:** the release lifecycle event carries `ENGINE`/`LOCAL` provenance;
  `HUMAN_ATTESTED` authority attaches only to the separate operator **fill** command. The
  unreachability conclusion is unaffected.
- **Why it matters:** the successor design will be drafted from these texts; imprecise
  authority vocabulary on an event-truth surface invites exactly the kind of pre-ratified
  assumption that failed here.
- **Resolves:** use exact provenance terms in the next planning artifact.

### F3 (P3 — process observation, not against the implementer): the contradiction was derivable pre-ratification
- **Where:** ADR-012 §2 ("a recovery that cannot be bound to its durable submission-claim
  occurrence fails closed") + `app/models.py:1038`, both predating WO-0135; the WO's own
  context packet cites both files.
- **What:** D-ML-5 ("resolved only by the operator's … reconcile") was ratified without
  tracing the release path's preconditions against the synthetic identity.
- **Why it matters / resolves:** the next design's GATE should walk the full lifecycle
  end-to-end (birth → dedup → **release** → post-release pin) before ratification; the
  implementer's read-only GATE doing exactly that is what caught this.

## Boundary questions (request §Boundary)

1. **Real on both stores.** No existing typed, authorized route reconciles the synthetic
   pair; the only near-miss requires triple internal-state fabrication plus a pydantic
   bypass (L3), i.e. it does not exist through any boundary.
2. **Release intentionally impossible**, not merely deterministic (cascade + single-writer
   argument above).
3. **Yes — permanent stranding**, and worse than "open records": F1 shows permanent
   symbol-rail blocking.
4. **No monitoring-only change can satisfy D-ML-1..5.** Creation/dedup/visibility are
   achievable (items 1–2), but D-ML-5's operator resolution and the WO's own post-reconcile
   acceptance pin are unreachable without new durable vocabulary/lifecycle or revised
   ADR authority — all outside monitoring-only scope and outside this session's boundary.
5. **Weakening any guard is a P0 bypass, demonstrated:** L3 proves the guards are the only
   thing separating a fabricated attestation from a terminal event-log write. Relaxing
   `min_length=1` would also hit **real** recoveries — `""` is the legitimate unknown-id
   sentinel on real incident rows (`app/store/base.py:99-109`, `:918-920`), so empty-id
   release would let a real unknown-leg recovery be released without naming a venue leg,
   degrading the leg-scoped fill-parity check keyed on `record.broker_order_id`
   (`app/store/core.py:3110-3141`).
6. **Yes — STOP obeyed** (doc-only range verified above).

## NON-AUTHORITATIVE PROPOSAL ASSESSMENT

*Advisory input to planning only. Per the operator's continuation boundary quoted in the
request and WO: nothing here decides or authorizes any schema, event vocabulary, lifecycle,
operator command, new work order, or implementation.*

- **Purpose-built malformed-lineage operator-review record (the proposed direction):**
  directionally right, in my assessment. The blocker is evidence that the submit-recovery
  ledger is the wrong vessel, not that durable operator review is the wrong goal. A
  submit-recovery row *means* "a possibly-live venue leg with identity/claim/fill semantics"
  — every hardened guard (real order, owner lineage, claim occurrence, broker-id identity,
  fill parity) and every symbol-rail consumer (F1) follows from that meaning. A malformed
  lineage is a different fact class: an envelope-scoped projection-integrity fault with no
  venue leg of its own. A purpose-built record can carry an honest lifecycle
  (open → operator-acknowledged) whose release preconditions match what an operator can
  actually attest about a corrupt lineage, without touching ADR-012's guards. Cost: it is
  the full gated surface (new `ExecutionEventType`, projector fold, table/read model, typed
  operator command, ADR) — correctly a separate, larger WO.
- **Widening ADR-012 attestation to synthetic identities: reject.** This is the P0 of
  boundary question 5 — the guards are load-bearing for real recoveries sharing the same
  code path and the same `""` sentinel; special-casing a `lineage:` string prefix inside the
  release valve would turn a naming convention into a security boundary.
- **Envelope-scoped needs_review surface:** plausible middle ground (the envelope *is* the
  faulty entity), but it grafts an integrity-fault state onto the execution FSM that
  WO-0131/REV-0038 just finished hardening as a closed graph — vocabulary/lifecycle cost is
  similar to the purpose-built record with worse separation of concerns.
- **Cockpit-surfaced projection ambiguity without an event-log write:** underrated as an
  interim. The malformed-lineage set is deterministically re-derivable from existing durable
  truth on every tick — a query-facade/read-model surface (list of corrupt envelope ids +
  ambiguity sets) is durable-in-effect (survives restart by recomputation), deduped by
  construction, needs no gate on event-log truth, and strands nothing. What it cannot do is
  record *that the operator reviewed it* — no attestable disposition without a durable
  write. Given the exposure is already fail-closed (zero venue calls, no guessed target) and
  REV-0037 rated it P2 advisory, read-model surfacing now + the purpose-built record as the
  planned end-state is a defensible sequence.
- **Recommendation (input, deciding nothing):** pursue the purpose-built record as the
  design direction; consider the read-model surface as a low-risk interim; do not widen
  ADR-012.

## Ran vs read

**Ran** (pinned 3.12.3 venv, worktree at `58b4296`, OS-temp state, scripts deleted after):
triple-create dedup probe (memory, SQLite, SQLite-after-restart); typed attestation
rejection (both stores); bypassed-attestation store rejection + write-free verification +
restart persistence (both stores); fabricated-broker-id probe (both stores); L0–L3
guard-chain isolation cascade (memory); `update_submit_recovery` edge rejection (both
stores); open-status visibility + auto-loop filter (both stores); F1 blast-radius probe —
`flatten_position` FlattenBlockedError + exposure/exit-rail membership (both stores);
`git log`/`diff --stat` over the packet range and over `249f9be..58b4296` (Lane B surface
identity check).

**Read:** CLAUDE.md safety core; `.ai-os/core/15_CROSS_MODEL_REVIEW.md`; REV-0040 request
(full); WO-0135 complete body incl. fable_gate/fable_done; ADR-012;
`work/review/REV-0037/result.md` §P2-1; `app/store/base.py:99-109,830-929,984`;
`app/models.py:954-1073,1102-1159`; `app/store/core.py:1219-1274,2936-3160`;
`app/store/memory.py:4147-4780,2920-3030,3278-3330`;
`app/store/sqlite.py:5836-6540,4403-4470,4757-4800`; `app/monitoring.py:1352-1520,
2620-2660,3540-3560,4000-4040`; `app/facade/store_backed.py:700-733`;
`app/api/routes_trading.py:230-262`; the `249f9be` commit diff in full.

## Not independently verified

1. The L3 cascade (and therefore the exact completeness of the minimum-authority-set
   enumeration at the commit layer) ran on the memory store only; SQLite shares the
   identical shared-core guards and reproduced L0/L2-fabricated layers directly, but the
   L3 "succeeds after triple fabrication" step was not replicated at the SQL level.
2. The full gate battery (`ruff`/`mypy`/`lint-imports`/full `pytest`/oracles) was not run —
   there is no code diff in the range to gate; nothing in this packet certifies suite
   health at `249f9be` or `58b4296`.
3. The authenticity of the operator's continuation-boundary text as a verbatim human
   statement (consistent across WO and request, but not independently witnessable).
4. The activation-commit provenance claim (`7f918b4` moved the WO from queue) — outside the
   evidence range; taken as stated.
5. Windows/PowerShell behavior; this review ran on Linux.

## Verdict

**ACCEPT.** The implementer correctly identified a real blocker and responded exactly per
contract. Items 1–2 of the pre-ratified reuse contract independently reproduce as MET on
both stores; item 3 independently reproduces as BLOCKED at two regenerated layers (typed
`broker_order_id` min-length, `app/models.py:1038`; store lineage guard "recovery lineage is
not trustworthy: referenced local order is missing", `app/store/core.py:2998-3001` via
`memory.py:4367`/`sqlite.py:6112`) plus a third structural layer the author also named
(claim-occurrence binding, permanently `None` for a synthetic key), with an
identity-echo/typed-layer pincer closing the fabrication route; item 4 follows. My F1 probe
shows the reuse design is additionally unsound in a way the ratified war-game missed
(permanent symbol-rail stranding), reinforcing the STOP. No Lane B production/test diff
exists in the range; the stop condition and forbidden paths were honored; no completion is
claimed anywhere. The design-direction assessment above is advisory only and authorizes
nothing.
