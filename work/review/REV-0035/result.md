---
rev_id: REV-0035
title: "WO-0114 — PD-1 needs_review reconciliation release valve (human-attested event-truth + operator control)"
reviewer: "Claude (independent; builder Codex)"
reviewer_seat: CLAUDE
status: COMPLETE
branch: codex/ultra-beta-batch
review_base_sha: 3b8c840   # origin/master
head_sha: 31d133d          # shipping branch HEAD (batch finalize)
commit_range: origin/master..31d133d
frozen_request_head: ffd818b6c8d86efed01a2b2924e59c23e535cb23
frozen_head_note: >
  The REV-0035 request froze head ffd818b. I reviewed the shipping HEAD 31d133d (more
  conservative). I verified every WO-0114 rail is byte-identical between ffd818b and 31d133d
  (canonical_recovery_fill_quantity, validate_recovery_attested_facts,
  validate_submit_recovery_identity, recovery_operator_execution_event, validate_recovery_fill_facts,
  recovery_fill_row_matches, and both reconcile_submit_recovery bodies — all SAME), so this review
  faithfully covers the frozen WO-0114 semantics. Later batch WOs (0124/0125/0126) did not touch
  WO-0114's rails.
date: 2026-07-21
verdict: ACCEPT-WITH-CHANGES
---

# REV-0035 — Independent review of WO-0114 (PD-1 release valve)

## Verdict: ACCEPT-WITH-CHANGES

The valve is architecturally sound and its load-bearing safety properties hold under adversarial
testing. The two-command design (separate canonical fill ingestion + pure attestation release) makes
"a status flip can never be a synthetic fill" **structural**, not procedural. I independently
reproduced position neutrality, parity fail-closed, multi-leg ambiguity, idempotency, SQLite-reopen
non-double-apply, and the typed boundary on **both** stores, and proved 3 of the 4 named rails go red
when mutated.

I found **no reproducible safety-invariant violation** and **no live economic-truth hole**. The
human-gated surface is **not** unapproved: Ameen's ratification of D-PD1-1..4 (2026-07-20, recorded in
`work/queue/PD1-R2-PLANNING-PACKAGE.md §2` and the WO banner) authorizes implementation, and the code
correctly gates *beta reliance* on ADR-012 acceptance + this packet. That means the AGENTS.md
P0 "human-gated surface without recorded approval" does **not** apply.

The verdict is ACCEPT-WITH-CHANGES rather than ACCEPT because of one **P1 inert-pin** of exactly the
REV-0029 P0-4 class: ADR-012 §4 / D-PD1-1(ii) assert that "every authority-gated consumer is
enumerated **and pinned** to treat `HUMAN_ATTESTED` as non-broker," but the `plan_append_fill`
overfill/negative-position rail for `HUMAN_ATTESTED` is **not** pinned — a mutation that makes
`HUMAN_ATTESTED` broker-authoritative survives the entire WO + fills + hardening corpus green. The
behavior in the shipping code is correct (the ingest command's redundant upstream guards protect
today), so this is a test-adequacy gap + an ADR overstatement, not a live defect. It must be closed
before beta reliance, alongside Ameen's ADR-012 acceptance (still Proposed).

---

## Findings

### P1-1 — `HUMAN_ATTESTED` non-broker fill rail is unpinned (inert-pin; ADR overstatement)
- **Where:** `app/store/core.py:586` (`broker_authoritative = authority is EventAuthority.BROKER_AUTHORITATIVE`), guarding the overfill-quarantine branch (`core.py:588-590`) and negative-position branch (`core.py:621`). Claimed pinned by ADR-012 §4 and `PD1-R2-PLANNING-PACKAGE.md` D-PD1-1(ii) ("overfill REJECTED, not quarantine-recorded … strict pre-append rails").
- **Failing sequence (reproduced):** In a throwaway worktree I mutated line 586 to
  `authority in (EventAuthority.BROKER_AUTHORITATIVE, EventAuthority.HUMAN_ATTESTED)` — i.e. treat human
  evidence as broker authority at the fill rail. Result: `tests/test_wo0114_pd1_release_valve.py` **104/104 still passed**, and `tests/test_fills_append_only.py` + `tests/test_review_hardening_gates.py` + `tests/test_wo0108_rev0029_remediation.py` **54/54 passed**. Nothing turned red.
- **Root cause:** The two WO-0114 pins that *look* like they cover this (`test_operator_fill_over_order_capacity_is_rejected` asserting `match="cumulative"`, and the `sell_below_zero` guard asserting `match="negative position"`) actually exercise the **ingest command's own upstream guards** — `validate_recovery_fill_facts`'s `cumulative > record.quantity` check (`core.py:3203-3206`) and the ingest pre-check (`memory.py:4545-4549` / `sqlite.py:6189-6193`) — not the `plan_append_fill` rail. Because those upstream guards reject first, `plan_append_fill`'s `HUMAN_ATTESTED` branch is never reached with overfill/negative conditions, so it is unreachable-to-fail through the only producer and therefore unpinnable via the ingest command. The hardening gate never references `HUMAN_ATTESTED`/`broker_authoritative` at all (it pins only the recovery status enum + the `SUBMIT_RECOVERY_OPERATOR_RECONCILED` lifecycle event).
- **Why it matters:** This is the REV-0029 P0-4 "inert pin" class the WO was told to guard against. If a future change removed the ingest upstream guards ("plan_append_fill already protects us") or widened `broker_authoritative`, a `HUMAN_ATTESTED` fill could silently take the ADR-001 broker-overfill exception or cross a position below zero — a `submitted≠filled` / overfill-latch regression — with a fully green suite. The ADR's "enumerated and pinned" claim is not met at this consumer.
- **Resolution:** Add a direct unit pin on `plan_append_fill` (or `append_fill`) with `authority=EventAuthority.HUMAN_ATTESTED` proving (a) order-level cumulative overfill → `FILL_REJECT` (not `fill_overfill_quarantined`), and (b) a SELL crossing flat → `fill_rejected_negative_position`. Both stores. Then re-run the mutation above and confirm it turns exactly those nodes red. (Optionally amend ADR-012 §4 to name the pin.)

### P2-1 — Release-event consumers over-clear when `claim_occurrence` is absent (latent, unreachable today)
- **Where:** `app/store/core.py:1332-1339` (`direct_sell_order_may_execute`) and `app/store/core.py:1957-1965` (`project_envelope_obligation`). When a `SUBMIT_RECOVERY_OPERATOR_RECONCILED` event resolves no occurrence, both fall into `claim_open.clear(); venue_open.clear()` — closing **every** claim/venue interval for the order, i.e. making the order look *more* releasable than the single-occurrence contract intends.
- **Failing sequence:** Not reachable via the valve: both stores compute `claim_occurrence` and **fail closed** (`RecoveryTransitionError`, zero writes) if it can't be bound (`memory.py:4622-4625` / `sqlite.py:6264-6269`), and always stamp `payload["claim_occurrence"]` before writing the release event; `_child_lifecycle_provenance_is_valid` further requires this event be `ENGINE/LOCAL`. So no legitimately-written release event lacks an occurrence.
- **Why it matters:** It is a defense-in-depth asymmetry — the None-branch is *less* conservative than the concrete branch, the opposite of fail-closed. If any future path ever emitted this event without an occurrence, contribution-only isolation would silently degrade to order-wide clearing.
- **Resolution:** Make the None-branch conservative (e.g. leave intervals open / mark invalid), or assert `occurrence is not None` for this event type. Low priority given current unreachability.

### P2-2 — Verification environment mismatch (Python 3.11 vs pinned 3.12); full CI-form suite not reproduced
- The review environment ran Python **3.11.15**; the repo pins **3.12** (CLAUDE.md, `pyproject.toml`). All gates I ran are green under 3.11, but the pinned-toolchain full run (author's 4,003-test / 93.13% branch-coverage CI-form suite, ~400 s) was **not** reproduced here (see could-not-verify). Not a code defect; a verification limit worth recording on a human-gated surface.

---

## The 10 load-bearing properties

| # | Property | Verdict | Evidence |
|---|----------|---------|----------|
| 1 | Valve writes NO fill, moves NO position; status flip ≠ synthetic fill; position byte-identical across a successful reconcile with fully-accounted fills | **VERIFIED** | `reconcile_submit_recovery` writes only status + audit `Event` + `SUBMIT_RECOVERY_OPERATOR_RECONCILED` ExecutionEvent (no `quantity`, `core.py:3138-3159`) + owner reconcile, all in one unit. Authored pin `test_zero_fill_release_is_atomic_visible_and_position_neutral` asserts byte-identical position JSON. **My independent probe:** MEM+SQL "position byte-identical across release" + "no fill added" PASS. |
| 2 | Discovered fills enter truth ONLY as canonical deduped FILL (`fill:{order_id}:{source_fill_id}`) via the SEPARATE ingestion command; one movement under retry AND replay | **VERIFIED** | Ingest routes through `append_fill`/`record_envelope_fill` (the sole remaining-qty writer) with shared dedupe key; INV-5 dedupe. **My independent probe2:** MEM+SQL retry → position moved exactly once, one fill row, one canonical FILL event, status `duplicate`; **SQL replay-after-reopen** → still one movement/one FILL. |
| 3 | Cumulative-fill parity = sum of canonical FILLs for exact `(local_order_id, broker_order_id)`; contradiction fails closed zero writes; zero-fill terminal matches zero; multi-leg unscoped → ambiguity | **VERIFIED** | `validate_recovery_attested_facts` (`core.py:3062-3096`) + `canonical_recovery_fill_quantity` (`core.py:3098-3136`), fed **all** concrete legs via `_recovery_known_broker_ids_*`. Zero-fill CANCELED matches zero. **Mutation:** neutralizing the parity comparison → exactly `test_attestation_mismatch_...[memory/sqlite-cumulative_filled_quantity-1]` red (2 nodes). **My probe:** MEM+SQL multi-leg unscoped fill → release blocked with "ambiguous", no optimistic allocation. |
| 4 | Provenance honesty (D-PD1-1): human evidence never `BROKER_AUTHORITATIVE`/`SYNTHETIC`; every authority-gated consumer treats `HUMAN_ATTESTED` as non-broker (overfill REJECTED; no broker-terminal satisfied) | **VERIFIED (behavior) / PARTIAL (pin)** | Release event is `ENGINE/LOCAL` (`core.py:3149-3151`; probe asserts). Fill event is `OPERATOR/HUMAN_ATTESTED` (probe asserts). `plan_append_fill` gates `broker_authoritative` strictly on `BROKER_AUTHORITATIVE` (`core.py:586`), so `HUMAN_ATTESTED` overfill→REJECT, SELL-cross→REJECT (`core.py:588-635`). **Caveat:** this rail is not independently pinned — see **P1-1** (mutation survives green). |
| 5 | Atomicity/concurrency: all checks + status + audit + execution event under ONE lock/tx; concurrent transition loses cleanly (`RecoveryTransitionError`), zero partial writes; lock-serialized read-validate-write is the mechanism (no CAS) | **VERIFIED** | Memory `_recovery_truth_lock`+`_lock`+`_atomic()` (`memory.py:4587-4686`); SQLite `_recovery_truth_lock`+`_lock`+single `_tx` (`sqlite.py:6231-6360`). Fresh read inside the boundary; ingest and release share `_recovery_truth_lock`. Authored `test_interleaved_conflicting_attestations_exactly_one_applies` passes; execution-event identity re-check rolls back on conflict. |
| 6 | Idempotency: exact repeat = success no-writes; different attestation on released record = 409-class refusal; SQLite reopen never double-applies | **VERIFIED** | `if cleanup_status==OPERATOR_RECONCILED: prior_audit.payload==payload → return (no writes) else raise` (both stores). **My probe:** MEM+SQL exact repeat write-free + conflicting re-attestation `RecoveryTransitionError`; **SQL reopen** exact re-release write-free, record stays terminal. Facade maps `RecoveryTransitionError→409`, `UnknownEntityError→404` (`store_backed.py:134-183`, `http_mapping.py`). |
| 7 | Contribution-only release: release leaves `needs_review_child_order_ids`/`_order_needs_review_*`/`RECOVERY_OPEN_STATUSES` scans; symbol quarantine lifts only if no other predicate holds; ADR-001 latch UNAFFECTED | **VERIFIED** | Both consumers close only the named occurrence (`core.py:1331-1339`, `1953-1965`). `operator_reconciled ∉ RECOVERY_OPEN_STATUSES`. **Mutation:** dropping the direct-SELL reconcile consumer → `test_direct_sell_recovery_blocks_fresh_owner_until_release[memory/sqlite]` red. Authored `test_second_needs_review_predicate_keeps_envelope_paused`, `test_release_of_last_predicate_lifts_flatten_quarantine`, `test_adr001_overfill_latch_survives_operator_release` all green (in the 121). Reconcile path never touches quarantine facts. |
| 8 | Recovery loop selects only `{RECOVERY_UNRESOLVED}`; a released record can never be re-touched | **VERIFIED** | Driver at `monitoring.py:3556` selects `{RECOVERY_UNRESOLVED}`; open views (`689`, `2634`) use `RECOVERY_OPEN_STATUSES` (excludes reconciled). **My probe:** MEM+SQL (and SQL-reopen) released id absent from `{UNRESOLVED}` and open view, present in full history. |
| 9 | Boundary: cockpit calls ONLY typed API (no store/broker/alpaca import); routes never touch store/broker | **VERIFIED** | `cockpit/app.py` + `cockpit/api_client.py` grep for `store\|broker\|alpaca\|app.` imports = **empty**; api_client is HTTP-only with `X-Actor`. Routes use `Depends(get_command_facade)` + required `X-Actor` header + path/echo id-match + `FacadeError→facade_error_to_http` (`routes_trading.py:209-260`). import-linter: **6 kept / 0 broken** ("engine never imports Alpaca", "API reaches store/engine/broker only through facade"). |
| 10 | Red-first integrity: mutate ≥2-3 named pins, prove they go red (hunt inert pins) | **VERIFIED (3 pins) / REFUTED (1 rail)** | Parity → 2 nodes red; echoed-symbol identity → `test_attestation_mismatch_...[symbol-MSFT]` 2 nodes red; direct-SELL reconcile consumer → `test_direct_sell_recovery_blocks_fresh_owner_until_release` 2 nodes red. **INERT:** `HUMAN_ATTESTED`-as-broker mutation survives 104+54 green → **P1-1**. |

Also independently verified: single write path to `operator_reconciled` (only the two `reconcile_submit_recovery` methods; `update_submit_recovery` refuses it, pinned by `test_generic_update_cannot_bypass_operator_attestation`); forbidden paths `app/adapters/**` and `app/reconciliation.py` untouched across the whole branch; vocabulary additive with no schema-version bump / no SQLite DDL (`cleanup_status` unconstrained TEXT).

---

## What I ran vs. what I read

**Ran (throwaway worktree at `31d133d` in scratchpad; basetemp in scratchpad, never repo-root):**
- `pytest tests/test_wo0114_pd1_release_valve.py tests/test_wo0114_cockpit_release.py tests/test_review_hardening_gates.py` → **121 passed** (104+3+14).
- `pytest tests/r2_conformance_oracle.py tests/test_r2_conformance_oracle_claude.py` → **83 passed, 6 skipped**.
- `ruff check` (WO paths) → clean; `mypy app/` → **Success, 70 files**; `lint-imports` → **6 kept / 0 broken**; `python .ai-os/scripts/check_work_order_disposition.py` → **DISPOSITION CHECK PASSED**.
- **Mutation battery** (apply → run → `git checkout` restore): parity-comparison neutralized (2 red), echoed-symbol comparison skipped (2 red), direct-SELL reconcile consumer dropped (2 red), `HUMAN_ATTESTED`→broker-authoritative (0 red — **P1-1**).
- **Independent probe harness** (my own scenarios, both stores; not a rerun): 21 checks incl. position byte-identical across release, driver/open-view exclusion + history retention, exact-repeat write-free + conflicting-re-attestation 409, **multi-leg unscoped-fill ambiguity**, SQLite reopen (terminal persists, still excluded, exact re-release write-free) → **21/21**.
- **Independent fill probe:** retry + replay-after-reopen dedupe, provenance `OPERATOR/HUMAN_ATTESTED` → **11/11**.

**Read:** WO-0114 contract, REV-0035 request, AGENTS.md review rubric, CLAUDE.md safety core, `PD1-R2-PLANNING-PACKAGE.md §2` (D-PD1-1..4), ADR-012, INV-096, and the full diffs of `app/models.py`, `app/store/{core,base,memory,sqlite}.py`, `app/facade/{commands,dtos,store_backed,http_mapping}.py`, `app/api/routes_trading.py`, `cockpit/{app,api_client}.py`, plus the projector consumers and `monitoring.py` recovery selectors.

---

## Could not verify (explicit)

1. **Full CI-form suite / 93.13% branch coverage** (author's 4,003 passed / 11 skipped / 1 xfailed, `--cov=app --cov-branch`, ~400 s): not reproduced here. I ran the WO-focused corpus (121), conformance (89), hardening (14), all static gates, and 32 independent probe checks instead — all green.
2. **Python version:** verified under **3.11.15**; repo pins **3.12**. All gates pass, but this differs from the pinned toolchain (P2-2).
3. **Repo-wide `ruff format --check .`** (6 pre-existing out-of-lane blockers named in the WO): not independently reproduced; WO-scoped ruff check is green.
4. **Zero-venue-call adapter spy** and the concurrency `asyncio.gather` race: relied on authored pins `test_facade_release_makes_zero_venue_calls` and `test_interleaved_conflicting_attestations_exactly_one_applies` (green in the 121) plus code trace / my conflicting-re-attestation probe; did not build a separate broker-spy harness.
5. **Surrounding batch (WO-0124/0125/0126)** that integrated on top of the frozen WO-0114 head: out of REV-0035 scope. I confirmed only that they leave WO-0114's rails byte-identical (`ffd818b`≡`31d133d` for the WO-0114 functions).

## Gating status (informational; not authorized by this review)
ADR-012 remains **Proposed** and requires Ameen's acceptance; per the WO's own acceptance criteria and this request, **no** disposition/ledger/close-out/merge is authorized until (a) this packet is dispositioned ACCEPT/ACCEPT-WITH-CHANGES, (b) **P1-1** is resolved (add the missing fill-rail pin), and (c) Ameen accepts ADR-012. Recommended: apply the P1-1 fix, then this verdict stands as **ACCEPT-WITH-CHANGES**.
