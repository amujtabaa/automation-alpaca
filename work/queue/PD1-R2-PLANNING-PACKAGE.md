# PD-1 + R2 backfill verification — planning package (operator decision register)

> Planning-seat artifact, 2026-07-20. Anchor: `master` @ `88833e3d` (== PR #9 merge; no
> post-merge delta at planning time). Companion to `WO-0114` (PD-1 release valve) and
> `WO-0115` (real paper-data backfill verification), both `DRAFT` in `work/queue/`.
> **Nothing here is ratified.** Implementation of either WO stays blocked until Ameen answers
> the register below. This file is NOT a work order (no WO front matter) and carries no
> completion obligation of its own; it is dispositioned with whichever WO consumes it last.

## 1. State of play (planning-time verification)

- `origin/master` == `88833e3d` — VERIFIED (`git merge-base --is-ancestor` + `rev-parse`).
- REV-0033 dispositioned RESOLVED at `cdb7dd9` — VERIFIED (`work/review/REV-0033/disposition.md`).
- `needs_review` is a hard terminal sink: `RECOVERY_TRANSITIONS[RECOVERY_NEEDS_REVIEW] = frozenset()`
  (`app/models.py:905-909`); zero exit paths in `app/` (full-grep audit, WO-0114 context) — VERIFIED.
- The two REV-0029 P0-3 submission lanes are CLOSED on master (WO-0108/0109, Policy A), so PD-1
  is purely a *release* design — VERIFIED (`docs/adr/ADR-010-execution-envelope.md:127-147`).
- No honest human provenance exists: `EventSource` = engine/broker_stream/broker_rest/reconciliation;
  `EventAuthority` = broker_authoritative/local/synthetic (`app/models.py:488-513`) — VERIFIED.
- Handoff correction: the invariants-rationale PKL page is `pkl/safety/invariants-rationale.md`
  (the handoff's `pkl/architecture/` path does not exist) — VERIFIED on disk.
- OBS-3 sharpening (planning finding, feeds WO-0115): startup owner reconciliation keys on the
  STRICT predicate, which counts bare pre-activation `APPROVED` envelopes as delegating
  (`app/store/core.py:1116-1118,1874`). Opening a legacy pre-P2-closed DB can therefore
  PROMOTE or **RESTORE (`EXPIRED→APPROVED`)** an owner beside a bare-APPROVED envelope
  (`app/store/sqlite.py:2682-2699`); the across-close sweep is close-time only (ADR-010 §3).
  Real-data verification must count these restorations, not just "spared rows" — VERIFIED.
- Retained branch `consolidate/r2-canonical` carries one ledger-only commit `b8d5dbb` (CI 492
  green) not on master — INFERRED from handoff; no planning action required, noted for hygiene.

## 2. Operator decision register

Numbering follows the handoff (1-7). Format: **Default (recommended)** / Alternatives /
Consequences. Answers materially change semantics, data handling, or authorization — nothing
below is answerable from current code alone.

### D-PD1-1 — Human-attestation provenance vocabulary (handoff #1)

**Default: hybrid-honest.**
(i) The valve's status-transition `ExecutionEvent` + audit `Event` follow the existing
ADR-008/ADR-010 §6 convention — `source=ENGINE, authority=LOCAL`, commanding actor + reason +
evidence ref in the audit payload — exactly like `envelope_approved` and
`emergency_reduce_override` (`app/store/sqlite.py:7253-7285`). No vocabulary change for the
transition itself: the engine is recording an operator command, which is what ENGINE/LOCAL
already means here.
(ii) IFF D-PD1-4 permits operator-supplied fill facts, add `EventSource.OPERATOR = "operator"`
and `EventAuthority.HUMAN_ATTESTED = "human_attested"`, used ONLY for those FILL events.
Every authority-gated consumer is then enumerated and pinned to treat HUMAN_ATTESTED as
non-broker: strict pre-append rails; overfill REJECTED, not quarantine-recorded
(`app/store/core.py:576-588, 4291-4338`); negative-crossing projector guards unchanged
(`core.py:1317,1647`); HUMAN_ATTESTED never satisfies any broker-terminal requirement.
- *Alternative A — full new vocabulary for all valve events.* Cleaner queryability (one
  `authority='human_attested'` filter finds everything), but diverges from the established
  lifecycle-event convention and widens the consumer audit; larger ADR-008 amendment.
- *Alternative B — pure bridge, no new enum values, no fill path through PD-1.* Zero vocabulary
  change, but a record whose fills are missing from event truth can never reach parity → stays
  latched forever; PD-1 becomes a partial valve. Honest but weaker.
- *Forbidden either way:* labeling human evidence `BROKER_AUTHORITATIVE` (REV-0029), or
  `SYNTHETIC` (defined as deterministic reconciliation-inferred, `app/models.py:507-508`).
- *Consequence of default:* enum widening touches event-log truth vocabulary → explicitly named
  in ADR-012 + ADR-008 amendment; additive values, no `EXECUTION_EVENT_SCHEMA_VERSION` bump
  (version marks incompatible shape changes, ADR-010 §6), stated in the ADR, review-gated.

### D-PD1-2 — Cleanup-status name and exact semantics (handoff #2)

**Default: new terminal status `RECOVERY_OPERATOR_RECONCILED = "operator_reconciled"`.**
Semantics: terminal (empty outgoing set); the ONLY new edge is
`needs_review → operator_reconciled`, reachable exclusively via the valve command; excluded
from `RECOVERY_OPEN_STATUSES` (that exclusion IS the release); the recovery loop still selects
only `{RECOVERY_UNRESOLVED}` (`app/monitoring.py:2869`) and can never touch the record; the
status itself carries zero position semantics. Name candidates if the default string reads
wrong: `"reconciled_by_operator"`, `"resolved_operator_reconciled"`. The sketch name
`reconciled` alone is NOT ratified — bare "reconciled" collides with reconciliation-engine
activity, which explicitly refuses to do this (`app/reconciliation.py:19-32`).
- *Alternative — annotation fields (reconciled_at/by) with status left `needs_review`.* Two
  sources of truth for openness; breaks the AIR-004 closed-set design; every
  `RECOVERY_OPEN_STATUSES` consumer needs a second condition. Rejected.
- *Alternative — reuse `RECOVERY_RESOLVED` (`"resolved_canceled"`).* Falsifies history (the
  record exists BECAUSE it had fills; nothing was cleanly cancelled). Rejected.
- *Consequence of default:* app-level closed sets + `recovery_status_event` +
  `require_recovery_status` widen; NO SQLite DDL (`cleanup_status` is unconstrained TEXT,
  `app/store/sqlite.py:353-369`); T1.1 enum-total hardening gates must be extended, which is a
  feature — they force total handling of the new value.

### D-PD1-3 — First surface: API-only vs API + cockpit control (handoff #3)

**Default: API-only.** Typed facade command + `POST /api/order-recoveries/{id}/reconcile`
(actor via `X-Actor`, `FacadeError`→404/409/422). The cockpit already lists open recoveries
read-only (`GET /api/order-recoveries`, `app/api/routes_trading.py:186-197`) and keeps doing
so; the released record simply leaves the open view. A cockpit action button is a follow-up WO
after the semantics survive independent review.
- *Alternative — cockpit control in the same WO.* One less operator hop for a rare event, but a
  larger human-gated review surface in one packet. Either way Streamlit calls only the typed
  API (invariants 4-6); the store/broker are unreachable from the UI.

### D-PD1-4 — Discovered fills: same atomic command or separate ingestion (handoff #4)

**Default: separate commands.**
(1) An operator broker-evidence **fill-ingestion command** (used only when the record's venue
fills are missing from event truth) appends canonical deduplicated FILL events
(`plan_append_fill`, dedupe `fill:{order_id}:{source_fill_id}`) with D-PD1-1(ii) provenance.
Position legitimately moves — that is INV "only fills change quantity" working as designed —
and the quarantine stays latched meanwhile.
(2) The **valve command** is pure attestation + transition: it requires cumulative-fill parity
to already hold at execution time and writes NO fill, ever.
- *Why:* "a status flip can never act as a synthetic fill" becomes structural, not procedural;
  the intermediate state (fills ingested, record still latched) is fail-closed and safe; each
  command is independently idempotent and testable; retry semantics stay simple.
- *Alternative — one atomic command doing both.* No intermediate state, but the valve becomes a
  fill writer — the exact shape REV-0029's PD-1 assessment warned against — and the single
  atomic unit compounds dedupe + parity + transition failure modes.
- *Sub-decision under the default:* ingestion command ships in WO-0114 (same review packet,
  separate command + tests) — recommended — or as its own WO (slower, second packet).

### D-BF-5 — Real paper-data artifact: location and handling (handoff #5)

**Default:** the operator quiesces the app, then copies the paper DB
(`%ALPACA_DB_PATH%`, default `.\data\app.db`, `app/config.py:25,86,295`) to a workspace
OUTSIDE the repo tree, e.g. `C:\Users\amujt\dev\r2-verify\source\app.db`, and records its
SHA-256 at copy time. That file is the immutable source; all working copies live beside it
under `...\r2-verify\work\`. Nothing under `data/` or `*.db` is ever committed
(`.gitignore:24-26`). Date range and schema fingerprint recorded at intake.
- *Alternative — sanitized snapshot instead of the raw copy.* Acceptable, but the reliance
  verdict then attaches to the snapshot; the sanitization rules must be stated and the verdict
  notes the gap.
- *Consequence of no artifact:* WO-0115 ends `NEEDS-INPUT`; beta reliance on the re-projection
  stays ungated (D5 blocks reliance, not the merge).

### D-BF-6 — May sanitized derived fixtures be committed? (handoff #6)

**Default: yes, gated.** Minimal fixtures derived from real *shape classes* (not rows) found
during verification — fake symbols/ids/prices wherever economics don't matter — committed
separately under `tests/fixtures/` with a provenance note, reviewable in isolation. Never
account identifiers, credentials, raw paper rows, or secrets.
- *Alternative — report-only, no fixtures.* Smaller privacy surface; regression protection for
  real shapes then depends on later hand-written reproductions.

### D-BF-7 — Anomalies found during verification: report-only or remediation? (handoff #7)

**Default (per handoff): report-only + stop beta reliance.** Every anomaly class becomes a
proposed, separately named and separately authorized remediation WO. The already-visible
candidate: an OBS-3 retroactive close sweep for legacy bare-APPROVED shapes (would be a new
semantic on real data — a separately named future WO, id assigned at creation; NOT created,
  NOT authorized. (WO-0116/0117 were later consumed by the hygiene sweep and audit charter.)
- *Alternative — pre-authorize narrow mechanical remediations.* Faster, but each remediation is
  a new semantic against real economic records; rejected as default.

## 3. Dependency and sequencing note

The WOs are **independent by construction** and must stay so:

- **Disjoint surfaces.** WO-0114 changes app code (vocabulary, store command, facade, route)
  and ships an ADR; WO-0115 changes NO app code (allowed paths: `work/**` + optional
  `tests/fixtures/**`). Zero file overlap.
- **No semantic coupling.** The valve is command-driven, never a startup writer, so WO-0114
  adds nothing to the `initialize()` write-step list WO-0115 classifies; a WO-0115 verdict
  survives a later PD-1 merge unchanged. Conversely WO-0115 writes no code PD-1 depends on.
- **Order:** either order or parallel is safe. **Recommended: WO-0115 first** — it needs only
  the D-BF answers (data handling, no new engine semantics), it gates beta reliance that is
  already deferred (D5), and its inventory of real open `needs_review` rows is free, concrete
  test-shape intelligence for WO-0114. WO-0114 additionally waits on the D-PD1 semantic
  ratifications and an independent review slot.
- **Leak guards.** WO-0115 findings never widen into repairs (D-BF-7); WO-0114 never touches
  backfill/startup behavior; a third semantic need (e.g. OBS-3 retro-sweep, an ADR-001-latch
  release) is always a NEW work order or `NEEDS-INPUT`.

## 4. Verification matrices

### WO-0114 (PD-1) — every row red-first, BOTH stores; (R) = SQLite reopen/restart parity

| Property | Guard type | Stop-on-fail |
|---|---|---|
| Deny: no/malformed evidence, empty actor/reason | unit + route 422/409 | yes |
| Deny: wrong recovery/order/broker-id/symbol/side/envelope/owner identity | unit, exhaustive per field | yes |
| Deny: non-terminal broker state; cumulative contradiction | unit (R) | yes |
| Accept: zero-fill terminal / partial / fully-accounted parity | unit (R) | yes |
| Discovered fills: canonical dedupe under retry AND replay; one position move | integration (R) + mutation | yes |
| Valve moves no position (byte-identical projection) | integration (R) + mutation | yes |
| Atomic CAS-loss vs concurrent monitor/recovery tick; zero partial writes | concurrency | yes |
| Idempotent repeat; 409 on conflicting re-attestation | unit (R) | yes |
| Contribution-only release: sibling obligation keeps all rails closed | integration on WO-0108/0109 rails (R) | yes |
| ADR-001 latch unaffected | unit | yes |
| Zero venue calls (adapter spy) | integration | yes |
| Actor/reason/evidence durably auditable; open-view drop | integration (R) | yes |
| Enum-total + producer/consumer hardening gates extended | `test_review_hardening_gates.py` | yes |
| Full gates: ruff/mypy/lint-imports/pytest + both oracles | CI-form | yes |
| Independent cross-model review packet → ACCEPT/AWC + disposition | governance | yes (blocks reliance) |

### WO-0115 (backfill verification) — evidence-gated, no code

| Gate | Evidence | Stop-on-fail |
|---|---|---|
| Source SHA-256 unchanged (intake / post-run / end) | hash log ×3 | yes — verdict void |
| Source never opened via store initializer | runbook audit (ro/immutable URI only) | yes |
| Zero broker/network contact; no credentials present | env audit + egress observation | yes |
| Pre-mutation inventory complete (all 11 tables + shape classes) | evidence table | yes |
| Every working-copy write classified to one of the 8 named mechanisms | before/after dump diff | yes — unexplained write = BLOCKED |
| Second open semantically idempotent (comparator rules per WO-0109 D) | dump diff pass1 vs pass2 | yes |
| Economic truth unchanged (positions/orders/fills/broker-ids) | projection + table diff | yes |
| OBS-3 population characterized incl. `envelope_delegation_restored` count | report section | no — report-only |
| Deterministic duplicate/unlinked-owner resolution; INV-087 index holds | diff + index creation | violation = BLOCKED (legitimate abort) |
| Startup SELECT count / runtime bounded at real cardinality | scaling-gate tracer output | gross growth = BLOCKED |
| Verdict recorded VERIFIED or BLOCKED/NEEDS-INPUT | fable_done | n/a |

## 5. WO-0115 PowerShell runbook (operator-safe; DO NOT EXECUTE during planning)

To be dry-run-reviewed at activation. The Python driver script it references is authored
inside WO-0115 execution (test-first) and pinned to the anchor tree.

```powershell
# 0) QUIESCE: stop the FastAPI app + any monitoring loop. Confirm no process holds app.db.
# 1) INTAKE (source becomes immutable from here)
$V   = "C:\Users\amujt\dev\r2-verify"; mkdir $V\source,$V\work,$V\evidence -Force
Copy-Item $env:ALPACA_DB_PATH -ErrorAction Stop $V\source\app.db   # or the explicit path
Get-FileHash $V\source\app.db -Algorithm SHA256 | Tee-Object $V\evidence\hash-intake.txt
# 2) READ-ONLY INVENTORY (immutable URI — never the app store)
python inventory.py "file:$($V -replace '\\','/')/source/app.db?mode=ro&immutable=1" `
  | Tee-Object $V\evidence\inventory-before.json
# 3) WORKING COPY + BEFORE DUMP
Copy-Item $V\source\app.db $V\work\copy1.db
python dump.py $V\work\copy1.db | Out-File $V\evidence\dump-before.jsonl
# 4) RUN 1: SqliteStateStore(copy1).initialize() under a pinned clock (driver: run_init.py
#    — pins store clock inside the source's last session day; traces SELECTs; mock-only env)
$env:BROKER_ADAPTER="mock"; Remove-Item Env:ALPACA_PAPER_API_KEY,Env:ALPACA_PAPER_API_SECRET -ErrorAction SilentlyContinue
python run_init.py $V\work\copy1.db | Tee-Object $V\evidence\run1.log
python dump.py $V\work\copy1.db | Out-File $V\evidence\dump-after1.jsonl
# 5) CLASSIFY: every row-level delta -> exactly one of the 8 named mechanisms
python classify.py $V\evidence\dump-before.jsonl $V\evidence\dump-after1.jsonl `
  | Tee-Object $V\evidence\classification.md          # any UNEXPLAINED row => STOP (BLOCKED)
# 6) RUN 2 (idempotency): reopen same copy, same pinned day
python run_init.py $V\work\copy1.db | Tee-Object $V\evidence\run2.log
python dump.py $V\work\copy1.db | Out-File $V\evidence\dump-after2.jsonl
python classify.py $V\evidence\dump-after1.jsonl $V\evidence\dump-after2.jsonl   # expect: zero semantic delta
# 7) SOURCE INTEGRITY RE-PROOF
Get-FileHash $V\source\app.db -Algorithm SHA256 | Tee-Object $V\evidence\hash-final.txt
# 8) ROLLBACK = Remove-Item $V\work\* ; the source is untouched by construction.
```

### Evidence-table template (one row per gate, fresh pasted output only)

| Gate | Command | Expected | Pasted output (fresh) | VERIFIED/BLOCKED |
|---|---|---|---|---|
| Source hash stable | `Get-FileHash …` ×3 | 3 identical digests | | |
| … | | | | |

## 6. NEEDS-INPUT register (blocking; batched for one operator pass)

1. **D-PD1-1** provenance vocabulary — WO-0114 blocked.
2. **D-PD1-2** cleanup-status name/semantics — WO-0114 blocked.
3. **D-PD1-3** API-only vs cockpit — WO-0114 blocked.
4. **D-PD1-4** fill-ingestion split (+ sub-decision same-WO vs own WO) — WO-0114 blocked.
5. **D-BF-5** artifact supply/location — WO-0115 blocked; no artifact ⇒ WO-0115 ends NEEDS-INPUT.
6. **D-BF-6** sanitized fixtures policy — WO-0115 partially blocked (fixture step only).
7. **D-BF-7** anomaly policy — WO-0115 blocked (default report-only recommended).
8. Non-decision note: handoff's PKL path corrected to `pkl/safety/invariants-rationale.md`.

Everything else in both WOs is answerable from code/artifacts and is deliberately NOT queued
for the operator.
