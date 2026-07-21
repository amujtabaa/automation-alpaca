---
type: Work Order
title: "R2 real paper-data backfill verification (H.1 step 7 / D5, pre-beta reliance gate)"
status: DRAFT
work_order_id: WO-0115
wave: post-R2 beta-prep
model_tier: strong
risk: high
disposition: []
owner: Ameen (supplies artifact + ratifies) / planning seat drafted 2026-07-20 / implementer TBD
created: 2026-07-20
gated_surface: real paper-data handling (read-only source); NO remediation authority
---

# Work Order: verify the R2 startup envelope-owner re-projection against real paper data

> **RATIFIED 2026-07-20 (Ameen):** D-BF-6 = yes-gated fixtures; D-BF-7 = report-only;
> D-BF-5 = **no artifact yet** — HOLD this WO until the D-HOST-1 hosting decision resolves
> (planning package §2): the verification doubles as the cutover gate for the DB's eventual
> migration to its host. **Hard gate unchanged:** without a real artifact, execution ends
> `NEEDS-INPUT` — synthetic fixtures cannot satisfy it (D5, `PARTB-COMPLETION-PLAN.md`).
> This WO verifies and reports; it authorizes ZERO repair, retro-sweep, migration, or
> app-code change. Independent of WO-0114; neither expands the other.

## Goal

Prove — or fail closed on — the claim that the existing startup re-projection
(`SqliteStateStore.initialize()`, `app/store/sqlite.py:502-638`) behaves per ADR-010/INV-090
against the actual shape of real pre-existing paper-trading data, producing a clear
`VERIFIED` or `BLOCKED/NEEDS-INPUT` pre-beta reliance verdict.

## Context packet

Read only these first:

- `CLAUDE.md` (safety core) + `work/queue/PD1-R2-PLANNING-PACKAGE.md` (runbook + evidence template)
- `docs/adr/ADR-010-execution-envelope.md` §3 (three predicates; close-time-only sweep)
- `docs/INVARIANTS.md` INV-090 (+ INV-087, INV-091)
- `work/review/CAMPAIGN-0002-claude/PARTB-COMPLETION-PLAN.md` (OBS-1..4, esp. OBS-3) + `DOWNSTREAM-STATUS.md` H.1-7
- `app/store/sqlite.py` `initialize()` write steps (`:502-638`), `_reconcile_envelope_owner_locked` (`:2661-2718`), `_migrate` (`:885-1017`)
- `app/store/core.py` `project_envelope_obligation` (`:1401`, predicates `:1873-1881`)
- `app/config.py` (`ALPACA_DB_PATH:25/86/295`, `STATE_STORE:24`, `BROKER_ADAPTER:41/316`)
- `tests/test_wo0036_r2_close_and_recovery_ownership.py:507-537` (restart-parity template) + `tests/test_wo0036_r2_hostile_closure.py`
- `tests/performance/r2_scaling_gate.py` (`_startup_metrics:351-359`, SELECT-trace + EXPLAIN-plan tooling)

## Allowed paths

```yaml
allowed_paths:
  - work/**                          # evidence tables, run log, verdict, close-out
  - tests/fixtures/**                # ONLY if D-BF-6 ratifies sanitized derived fixtures
```
All DB copies, hashes, and inventories live OUTSIDE the repo tree (operator-chosen workspace
per D-BF-5). Nothing under `data/` or any `*.db` is ever committed (`.gitignore:24-26` stays).

## Forbidden paths

```yaml
forbidden_paths:
  - app/**            # no code change of any kind in this WO
  - docs/adr/**       # findings may PROPOSE amendments; a new WO ships them
  - cockpit/**
  - .github/workflows/**
```

## Required behavior

- [ ] **Artifact intake (D-BF-5):** record path, size, SHA-256, schema fingerprint
      (`sqlite_master` dump hash + `PRAGMA table_info` per table), session date range, and how
      the operator supplied it. Missing artifact → stop, `NEEDS-INPUT`.
- [ ] **Source is immutable:** the source file is NEVER opened through `SqliteStateStore`
      (there is no read-only open — `initialize()` always migrates/backfills/re-projects,
      `app/store/sqlite.py:502-601`). Inventory the source only via `sqlite3` URI
      `mode=ro&immutable=1`. Re-hash the source after every phase; any hash change = STOP,
      report, verdict void.
- [ ] **Zero broker surface:** no Alpaca calls, credentials, or order submit/cancel/replace.
      The store is opened directly as an object (no adapter is constructed at all —
      `initialize()` takes no broker argument; `app/main.py` is not run). Defense-in-depth:
      unset `ALPACA_PAPER_API_KEY/SECRET`, set `BROKER_ADAPTER=mock`; network egress observed
      nil during the run.
- [ ] **Pre-mutation inventory (read-only, source):** row counts + status histograms for
      `sessions`, `sell_intents`, `execution_envelopes`, `orders`, `submit_recoveries`,
      `fills`, `events`, `execution_events`, `candidates`, `watchlist`, `position_snapshots`;
      envelope-owner shapes (per `sell_intent_id`: envelope statuses × intent status),
      delegating/terminal splits, bare-`APPROVED` envelopes whose session is closed (OBS-3
      candidates), open `unresolved`/`needs_review` recoveries, `envelope_action`-typed
      `execution_events`, malformed identities (dangling `sell_intent_id`/`envelope_id`/
      `order_id` references), duplicate owners per symbol, pre-R2 orphan patterns. Confirm
      actual table/column names against `SCHEMA` (`app/store/sqlite.py:210-449`) — there is no
      `owner_bindings` table; owner state IS `sell_intents.status`.
- [ ] **Working copy + snapshots:** byte copy; SHA-256 recorded; full logical dump (before);
      run `initialize()` on the copy with the store clock pinned inside the source's last
      session day (freeze pattern per `_freeze_store_clocks`) so `_ensure_current_session_locked`
      (`sqlite.py:1306-1327`) cannot mint a confounding new session — or, if allowed to fire,
      its writes are classified to that named mechanism; full logical dump (after).
- [ ] **Classify every write** by named current mechanism, from the exact ordered write-step
      list (planning package §runbook): (1) idempotent DDL, (2) `_migrate` column/rebuild
      migrations, (3) index (re)creation, (4) `_backfill_fill_events_locked`,
      (5) `_backfill_trading_state_events_locked` (+`sessions.trading_state`),
      (6) `_backfill_order_status_events_locked`, (7) R2 owner re-projection
      (`sell_intents.status` UPDATEs + `events` rows with reasons
      `envelope_delegation_linked|restored|released|conflict` ONLY),
      (8) `_ensure_current_session_locked`. **Any row-level change not attributed to exactly
      one mechanism = unexplained write = STOP + `BLOCKED`.**
- [ ] **Second-open idempotency:** reopen the migrated copy (same pinned day):
      zero new `events`/`execution_events`, zero owner churn, zero semantic delta between
      pass-1-after and pass-2-after dumps (allowing only nondeterministic ingest clocks per
      the WO-0109 Cluster D comparator rules).
- [ ] **Economic truth unchanged:** positions projected from FILL events identical
      before/after on every symbol; no order quantity/status/broker-id mutation; no new
      `fills` rows; new `execution_events` limited to the named backfills (4)-(6) with
      deterministic dedupe keys; ADR-001 quarantine set unchanged.
- [ ] **OBS-3 characterization (report-only):** count and list (sanitized) legacy
      bare-`APPROVED`-envelope shapes from pre-P2-closed sessions, and the re-projection's
      actual behavior on them — expected per current code: strict retention includes
      pre-activation `APPROVED` (`core.py:1116-1118,1874`), so startup may PROMOTE or RESTORE
      (`EXPIRED→APPROVED`, `sqlite.py:2691-2699`) such owners; the across-close sweep is
      close-time only (ADR-010 §3). Report observed counts of `envelope_delegation_restored`
      on real rows. A retro-sweep or any repair is OUT OF SCOPE → separately approved
      remediation WO (D-BF-7).
- [ ] **Determinism + bounds:** duplicate/unlinked pre-R2 owner shapes resolve
      deterministically (`_reconcile_envelope_symbol_conflicts_locked`, one retained
      delegation); startup SELECT count and wall-clock at real cardinality recorded via the
      scaling-gate tracer (`r2_scaling_gate.py` `_startup_metrics` + `EXPLAIN QUERY PLAN`, no
      unrelated full scans). An INV-087 partial-unique-index violation on real data is a
      legitimate fail-closed startup abort — record as `BLOCKED`, do not work around.
- [ ] **Evidence:** the planning-package evidence table filled with fresh pasted output for
      every gate; PowerShell runbook followed verbatim (operator machine) or reproduced
      command-for-command on the executing platform.

## Stop conditions

STOP (verdict `BLOCKED`, source untouched, copy retained for forensics): corruption or
`PRAGMA integrity_check` failure; ambiguous lineage the projection cannot resolve without
guessing; any unexplained write; second-pass semantic delta; schema drift vs current `SCHEMA`;
runtime/SELECT growth grossly out of line with the scaling gate's structural expectations; any
observed broker/network attempt; source hash change. Rollback = delete working copies; the
source artifact is never modified by design.

## Required tests / gates

- [ ] Source SHA-256 unchanged across the entire run (hashed ≥3 times: intake, post-run-1, end).
- [ ] All working-copy changes classified; **zero unexplained writes**.
- [ ] Second initialization semantically idempotent.
- [ ] Projection/owner/envelope outcomes conform to ADR-010 §3 + INV-090 (three predicates,
      hold-vs-resurrect, conflict sweep) — each observed transition mapped to its predicate.
- [ ] OBS-3 population characterized and reported (report-only).
- [ ] If later remediation is authorized: existing conformance
      (`tests/r2_conformance_oracle.py`, `tests/test_r2_conformance_oracle_claude.py`),
      hostile-closure, parity, and scaling gates must be green on that WO — pre-registered
      here, not run as part of this verification.
- [ ] Final verdict recorded: `VERIFIED` (re-projection safe for beta reliance on this data)
      or `BLOCKED`/`NEEDS-INPUT` with the exact failing gate. Synthetic evidence cannot
      upgrade the verdict.

## Required commands

```bash
# executed on the WORKING COPY only; source opened read-only via sqlite3 URI mode=ro
python - <<'EOF'   # store-open motion (template: r2_scaling_gate._startup_metrics)
# SqliteStateStore(copy_path) -> await initialize() under a pinned clock; see runbook
EOF
sha256sum <source>          # (PowerShell: Get-FileHash -Algorithm SHA256) at intake/mid/end
```

## Acceptance criteria

- [ ] Every required behavior satisfied with pasted evidence, or an explicit STOP verdict.
- [ ] Scope respected: no app/docs code touched; no source mutation; no broker contact.
- [ ] Fable DONE block: `VERIFIED` / `BLOCKED` / `NEEDS-INPUT` only.
- [ ] Findings needing new semantics filed as proposed follow-up WOs (default report-only,
      D-BF-7); none executed here.
- [ ] Close-out ships with the work: status flip, disposition, ledger; DOWNSTREAM-STATUS
      H.1-7 row updated with the verdict.

## Model-tier rationale

`strong` — adversarial data-forensics judgment on real economic records; misclassifying one
write would silently bless an unsafe migration path for beta.

## Notes

- Anchor: master `88833e3d`; re-projection semantics as amended through WO-0113/REV-0033.
- The source DB location default is `./data/app.db` on the operator machine
  (`ALPACA_DB_PATH`, `app/config.py:86`); actual artifact + transfer rules are D-BF-5.
- Privacy: no account identifiers, credentials, or raw paper data enter the repo; sanitized
  minimal fixtures only if D-BF-6 ratifies (separate commit, reviewable in isolation).

## Completion disposition

Complete after closure per template; expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`
(+ `ADR_CREATED` only if findings force an accepted-ADR correction via follow-up).
