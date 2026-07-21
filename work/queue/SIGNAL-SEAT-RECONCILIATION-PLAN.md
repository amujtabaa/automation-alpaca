# Signal Seat Reconciliation Plan

**Repo:** automation-alpaca (master, bdb7221/89f0f6e era) · **Archive:** `origin/archive/claude-wo-0001-install-checks-2x5ys8` (tip fc81951, forked from 80250e0, 2026-07-13)
**Status of this document:** DRAFT for operator (Ameen) review. No repo files were modified. All verdicts below reflect the adversarial verify pass; **zero verify-stage downgrades occurred** — all 60 mapped verdicts were CONFIRMED, with three verify amendments folded into the table and WO ladder (import-boundary allowlist co-port; repo-primer frontmatter citation; README stale-claim fix).

---

## 1. Executive summary

Most of the archived Signal Seat survives. Of 60 archive files audited, **32 port as KEEP** (near-verbatim, anchors refreshed), **15 are REWRITE** (the design survives but the code/text must be rebuilt against master's post-fork seams), **12 are RECORD-ONLY** (the branch's review packets and ledger entries — provenance, never portable), and **1 is DROP** (byte-identical duplicate). The design itself is in unusually good shape: it was hardened through three adversarial review rounds after the REV-0022 BLOCK, and two of the four P1 findings (F-002 atomic conversion, F-003 server-owned freshness) were independently confirmed CLOSED. The rebuild burden concentrates in three places: the store trio (`app/store/core.py`/`memory.py`/`sqlite.py`, which roughly tripled since the fork), the three facade/API files, and the sell-direction half of the conversion spec. The three biggest risks: **(1) governance import** — the archive shows ADR-009 "ACCEPTED 2026-07-14", but that acceptance was a human spec-lock after two further BLOCKs, never the ACCEPT/ACCEPT-WITH-CHANGES verdict master's G1 gate requires, so resurrecting it wholesale would import an un-cleared review gate and colliding REV-0024/0025 packet ids; **(2) sell-side invariant drift** — the archive's committed-sell-exposure formula and the locked multi-exit decision predate INV-087/INV-090/INV-091 and are now exactly the "neighboring exposure definition" INV-090 forbids (`app/store/core.py:1401`); **(3) auth-posture drift** — the archive's generic `tls_proxy` transport mode is broader than the topology the operator ratified on 2026-07-20 (tailnet-serve only, Funnel forbidden, VPS gated on an auth ADR). The clean path: amend ADR-009 on master using the archive text as the basis, dispatch one fresh re-review, clear G1 properly, then rebuild in bounded WOs behind it.

---

## 2. What the archive's review chain established, and the id collision

### The chain (all archive-branch except REV-0022)

| Packet | Verdict | What it established |
|---|---|---|
| **REV-0022** (master, frozen 25590a7, GPT-5 Codex, 2026-07-11) | **BLOCK** | Four P1s: F-001 credential/transport, F-002 non-atomic approval→intent, F-003 freshness deferred out of ADR, F-004 unbounded rejected-count appends. Master disposition still **REMEDIATION_OPEN** (`work/review/REV-0022/disposition.md`). |
| **REV-0024** (archive, frozen 413da38) | **BLOCK** | Closure scorecard: **F-002/A-2 and F-003/A-3 CONFIRMED CLOSED**; F-001/F-004 NOT closed. Four new P1s incl. the ASGI-seam bind-guard unenforceability and the paced-hostility hole (10,080 events over 7 days at 1 req/min without breaching the refill bucket). Produced Ameen's backend-owned-launcher and non-refilling-budget decisions. |
| **REV-0025** (archive, frozen 209496d) | **BLOCK** | Seven P1s (reachable-503 listener, non-mutation-sensitive launch proof, non-linearizable/non-durable budget, joint-enablement contradiction, A-4 propagation contradictions, session-close missing from the auth matrix); explicitly **no A-2/A-3 regression**. Ameen then decided D-1 (construction-time bind refusal) and D-2 (release/deployment conversion gate), folded all findings, **LOCKED the spec, ACCEPTED ADR-009 (2026-07-14)** — disposition candidly recorded as `RESOLVED_BY_LOCK`. |
| **REV-0026** (archive) | **WITHDRAWN** | Never dispatched ("no fifth spec-only round"). Retained for provenance. |
| **REV-0027** (archive) | **ACCEPT-WITH-CHANGES** | First **code** review of the branch WO-0102 implementation (cc346b1..5a93f73): no P0/P1; one P2 (operator-middleware prefix-skip of `/api/signals*`) + two P3, folded at 11832f0. Disposition `FINDINGS_FOLDED_AWAITING_HUMAN_RATIFICATION` — WO-0102 never closed even on the branch, and the archive tip carries 8 further auto-review fix rounds after the reviewed commit. |

Net: all four REV-0022 P1s were remediated to human-approved locked spec text (two Codex-verified closed, two human-decided and in-process-verified only); one of three implementation WOs was built and code-reviewed on the branch; WO-0103/0104 were never built. **No packet in the chain ever carried ACCEPT or ACCEPT-WITH-CHANGES on the spec** — the gate was closed by human lock, which does not satisfy master's G1 condition as written (`work/review/REV-0022/disposition.md` "Path to clearing the gate"; CLAUDE.md Review section).

### Id collision handling (mandatory)

- Master reassigned **REV-0024** to the WO-0107 Option B atomic-flatten packet (`work/review/REV-0024/SUPERSEDED.md`, subsumed into REV-0029) and its numbering has advanced through **REV-0033**.
- Therefore: **all archive packets (REV-0024/0025/0026/0027) stay RECORD-ONLY at their archive refs.** Nothing under those ids is ever ported to master. Any revived review gets a **fresh master id (≥ REV-0034)** citing the archive ref as provenance.
- Every in-code and in-doc citation of "REV-0024-F-001", "REV-0025-F-002", etc. (in `app/launch_guard.py`, `app/server.py`, `app/main.py` module tail, README callout, spec headers, WO texts) must be **renumbered or converted to archive-ref citations** at port time.
- Fresh ledger entries at fresh ids; the archive's six post-fork ledger lines (`REV-0024`, `REV-0025`, `SIGNAL-SEAT-SPEC-LOCK`, `ADR-009-ACCEPTED`, `WO-0102-SCHEMA-APPROVAL`, `REV-0027`) never port — the `ADR-009-ACCEPTED` entry in particular contradicts master's own ADR file (`docs/adr/ADR-009-signal-seat-boundary.md:3`).

---

## 3. ADR-009: path to Accepted

Master state: **Proposed** (acceptance of 2026-07-12 rescinded 2026-07-14); REV-0022 disposition **REMEDIATION_OPEN**; WO-0101..0104 re-gated. G1 clears **only** on an ACCEPT/ACCEPT-WITH-CHANGES disposition of a re-review of the final master-side text.

### Finding-by-finding status

| Finding | Location in ADR-009 | Archive remediation | Verification status | Master action |
|---|---|---|---|---|
| **F-001** (transport/credential boundary; reads unauthenticated) | Contract §1 (master line 47) | **Amendment A-1**: transport policy (loopback default / proxy mode, fail-fast), env-injected keys + `compare_digest` + N-key rotation + revocation, fail-closed mounted-route auth matrix **reads included** with unclassified-route CI failure, credential-presence startup guard, docs routes gated, backend-owned launcher + construction-time one-shot capability (bare `uvicorn app.main:app` opens **no listener**). | **Substantively addressed, never review-verified** — REV-0024 judged it NOT closed; the decisive clause-6 text (D-1a) postdates REV-0025's BLOCK; REV-0026 withdrawn. | Adopt A-1 text; **narrow `tls_proxy` → `tailnet_serve`** per D-SIG-3 (G3); extend the route matrix to post-fork envelope routes (`app/api/routes_trading.py:289,299,318`) and `POST /api/session/close` (archive REV-0025 F-007); refresh anchors; **re-review owed**. |
| **F-002** (approval→intent not atomic) | Contract §3 (master line 49) + Options | **Amendment A-2**: dedicated atomic dual-store conversion command; split-await facade composition forbidden; no-await between checks and durable writes; failure → nothing persisted; full crash/interleaving matrix required of WO-0103; **Option E considered and recorded** (rejected for beta with honest scope note). | **CONFIRMED CLOSED** (REV-0024 scorecard) with no regression at REV-0025. Strongest of the four. | Adopt near-verbatim; re-baseline code anchors only (the forbidden pattern now sits at `app/facade/store_backed.py:786-789`; candidate build at `app/store/core.py:981-998`, not the cited `core.py:641+`). |
| **F-003** (freshness/classification deferred) | Contract §5 TTL bullet (line 54) + INV-7 row (line 78) | **Amendment A-3**: `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)` with server_max_ttl default 3600s / hard cap 86400s; ttl range [30, 86400]; skew quarantines (`issued_at_future` at +30s, `issued_at_stale` at −24h); injected clock; persisted-never-re-derived deadline; atomic re-check inside the A-2 command; executable risk-reducing predicate; stable reason codes. | **CONFIRMED CLOSED** (REV-0024) — but two post-review refinements (local-SELL CREATED/ORDERED exposure counting; the multi-exit/single-flight relaxation) were **locked, not reviewed**. | Adopt formula/skew/restart/atomic-recheck verbatim. **REWRITE the exposure/risk-reducing predicate**: it must consume `project_envelope_obligation` (`app/store/core.py:1401`, INV-090 sole predicate source), `RECOVERY_OPEN_STATUSES` (`app/models.py:893`, WO-0108), and INV-091 acceptance exposure (`docs/INVARIANTS.md:978`) — the hand-rolled sum is now a forbidden parallel derivation. **Re-put multi-exit to Ameen** (collides with INV-087, `docs/INVARIANTS.md:829`). Flag both locked clauses explicitly to the re-reviewer. |
| **F-004** (unbounded rejected-count; no auth/size-cap before parse) | Contract §5 backpressure bullet (line 56) | **Amendment A-4** (two remediation rounds deep): authenticate → rails → 64 KiB capped read → parse; thesis ≤ 4000 chars, provenance ≤ 20×500; exactly one `PRODUCER_QUARANTINED` per epoch with zero-budget co-open; saturating out-of-log counter; one `PRODUCER_RELEASED` summary resetting both rails; **non-refilling per-producer invalid budget** (default 50, hard cap 1000), linearizable check-reserve-debit, restart-durable; interim ceiling WITHDRAWN, replaced by permanent rails-presence startup guard; D-2a joint enablement (WO-0102+0103+0104). The offending "periodic rejected-count" sentence deleted and disavowed. | **Substantively addressed, never review-verified** — REV-0024 judged NOT closed; the re-remediated form got REV-0025's BLOCK; post-REV-0025 fixes were locked, never re-reviewed. | Adopt verbatim; renumber REV citations; **re-review owed**. |

### Acceptance sequence (the only path that satisfies G1)

1. Land the four amendments on master as human-approved ADR text (WO-R1 below), **keeping Status: Proposed** ("Proposed — remediation drafted").
2. Dispatch **one fresh re-review packet (≥ REV-0034)** against the final master text, explicitly flagging the never-reviewed items: A-1 clause 6 (D-1a construction capability), A-4 final form (zero-budget co-open, linearizable/durable budget, rails-guard permanence, D-2a), and the two locked A-3 clauses.
3. G1 clears **only** on ACCEPT/ACCEPT-WITH-CHANGES of that packet; only then does Ameen flip Proposed→Accepted and unfreeze WO-0102..0104.

---

## 4. The auth decision (must precede the ingestion endpoint)

D-013b as ratified 2026-07-20 (D-HOST-1, `work/queue/PD1-R2-PLANNING-PACKAGE.md:199-206`; `docs/00_START_HERE.md:1086`): FastAPI bound 127.0.0.1 only; remote access only via `tailscale serve`; **Funnel/public exposure forbidden until an auth ADR exists**; interim ratified as zero repo changes. The archive's mechanism (per-producer `X-Producer-Key` + flag-gated `X-Operator-Key` on every sensitive route, over a construction-time-enforced loopback bind) **meets or exceeds D-013b's minimum** but is jurisdictionally broader than the ratified topology.

**Option A — Localhost-only producer (recommended).** The first producer is a process Ameen runs on the same host, POSTing to 127.0.0.1. No new network exposure; D-013b trivially satisfied; producer keys retained purely for identity binding/attribution. Decidable today; smallest surface for the re-review.

**Option B — Tailnet producer.** Producer on another tailnet node, reached via `tailscale serve`. Lawful under the ratified interim, **but**: flag-on operator-key enforcement (all reads included) must be live **before** serve fronts the API, with cockpit `X-Operator-Key` plumbing in the same change (no lockout window — invariant 11); `X-Producer-Key` remains the producer identity (tailnet node identity is transport-auth only). Decidable today if Ameen wants a remote producer at beta.

**Option C — Internet/third-party producer (e.g. TradingView webhook).** **Not decidable now.** Requires the D-HOST-1 auth ADR + deployment ADR first; the archive's static-key model becomes an input to that ADR, not a substitute.

**Recommendation:** ratify **Option A** now, and write the amended ADR-009 so Option B is a pure config change later: replace the archive's generic `tls_proxy` value with an explicit `tailnet_serve` transport policy, keep `loopback` default, and encode "Funnel/public exposure forbidden" as a spec-level negative test (D-SIG-3). Revive the construction-time bind guard regardless of topology (D-SIG-4) — it converts the ratified interim's operational promise into an enforced invariant. Under any option, confirm D-SIG-5 (flag-on makes **all** sensitive reads operator-key-gated — this changes the operator's own daily workflow) and D-SIG-6 (env-injected static keys with overlap rotation as interim custody).

---

## 5. Classification table (verify-stage final; zero downgrades applied because zero occurred)

### engine-store

| File | Verdict | Reason |
|---|---|---|
| `app/models.py` | **KEEP** | Purely additive signal vocabulary (SignalStatus, SIGNAL_* constants, 8 event types, SignalRecord); zero name collisions; no exhaustiveness gate breaks; only insertion anchors moved (re-anchor after `EMERGENCY_REDUCE_OVERRIDE_RESOLVED`, models.py:454). |
| `app/store/base.py` | **KEEP** | Additive ABC methods + `SignalIngestResult` match master's envelope-lift pattern; fix docstring (constants live in `app.models`, not `app.store.core`); re-check `cycle_budget_limit` kwarg against remediated F-004 text. |
| `app/store/core.py` | **REWRITE** | Design (pure planner, injective dedupe key, sanitizers) survives intact, but core.py tripled to 4,894 lines — rebuild at the new EOF seam after the envelope planners (:3745-4894); re-derive F-003/F-004 constants from remediated ADR. |
| `app/store/memory.py` | **REWRITE** | Method bodies port nearly verbatim; `_atomic` was rebuilt (O(1) length-snapshot + truncate + index rebuild, memory.py:480-541) — the archive's snapshot patch must be reconstructed into it. |
| `app/store/sqlite.py` | **REWRITE** | Table/mapper/methods still fit (`_insert_execution_event` contract identical, sqlite.py:6868), but `_SCHEMA`/`_migrate` reorganized by R2, and **the archived schema approval (78d8f57) is stale — fresh human-gated approval required**. |
| `app/events/projectors.py` | **KEEP** | `project_signal_records` appends cleanly after PositionProjector (:437-488); companion change: register the fold in `app/events/replay.py` read-model parity harness. |

### api-facade

| File | Verdict | Reason |
|---|---|---|
| `app/api/deps.py` | **REWRITE** | Credential matrix/`check_signal_rails` logic worth preserving, but Settings fields and middleware wiring are absent on master, and the flag-ON `get_actor` fallback is **not fail-closed** (silent downgrade) — fix at rebuild; gated on ADR-009 re-acceptance. |
| `app/api/routes_signals.py` | **REWRITE** | Review-hardened contract (body-blind ordering, quarantine totality, 64 KiB cap) survives, but every import target is absent on master and the store seam was rewritten; add to import-linter contract 5 (.importlinter:139-147) in the same change. |
| `app/api/schemas.py` | **KEEP** | `SignalProposal` block applies cleanly (file byte-unchanged since fork); only unresolved import is `SQLITE_MAX_SIGNED_INT` (models lane); re-verify against the master-ratified 01-schema text. |
| `app/facade/signal_rails.py` | **KEEP** | Pure stdlib seam (Protocol + `is_conforming_rails`); zero master collisions; inert until wiring + WO-0104 provider exist. |
| `app/facade/signals.py` | **REWRITE** | Concept (typed facade, lazy expiry on every echo, injected clock) must survive, but every store symbol it imports is absent and `store_backed.py` conventions moved (+215/−44); rebuild against `app/store/base.py:425` and `app/facade/protocols.py:20-29`. |
| `cockpit/api_client.py` | **KEEP** | Small `_operator_headers` patch, byte-safe under flag-off; **sequencing is load-bearing**: must land in the same change as the enforcement flip (lockout risk, invariant 11). |

### runtime-config

| File | Verdict | Reason |
|---|---|---|
| `app/__main__.py` | **KEEP** | 16-line delegator; ports verbatim, but only as one unit with server.py/launch_guard.py/main.py wiring, behind the ADR gate. |
| `app/config.py` | **KEEP** | +263 purely additive lines; all anchors intact (master drift is ruff-format + one comment); credential/transport settings are F-001 territory → review-gated. |
| `app/launch_guard.py` | **KEEP** | New leaf module, auto-covered by contract 1; renumber REV-0024/0025 citations (master's REV-0024 is a different packet). |
| `app/main.py` | **KEEP** | Master main.py byte-identical to fork — archive diff applies cleanly; conditional on same-change co-ports (deps.py auth helpers, routes_signals, rails seam, cockpit plumbing); WO-0102 scope ("router mount only", WO-0102:42) must be re-scoped first. |
| `app/server.py` | **KEEP** | Backend-owned launcher; uvicorn already pinned (requirements.txt:12); ports as one unit with the trio; renumber REV citations. |
| `README.md` | **KEEP** | 12-line callout applies cleanly; **mandatory edit**: the "app is None" claim is stale — correct to the leave-name-UNDEFINED mechanism (archive REV-0025 F-002 lesson). |
| `.importlinter` | **KEEP** | One-line contract-5 addition at :145; master's own WO-0102 requires exactly this line (WO-0102:50). |
| `.claude/rules/repo-primer.md` | **KEEP** (conditional) | Opus-routing preference applies cleanly but is an **operator directive requiring Ameen's explicit re-ratification**; strip the archive-only `recommended_model` frontmatter citation (verify amendment B); downgrade to RECORD-ONLY if declined. |

### specs-adr

| File | Verdict | Reason |
|---|---|---|
| `docs/adr/ADR-009-signal-seat-boundary.md` | **REWRITE** | A-1..A-4 are the remediation basis, but the ACCEPTED status is archive-local governance, A-3's exposure formula collides with INV-090/091, and anchors are stale — see §3. |
| `docs/spec/signal-seat/00-overview.md` | **KEEP** | Post-lock superset of master's draft; fix the false "ACCEPTED/UNFROZEN" header, move the tree pin to current master, drop archive REV-0024/0025 citations. |
| `docs/spec/signal-seat/01-schema.md` | **KEEP** | Self-contained wire/entity/dedupe design; point the exposure cross-reference at the rewritten 05 §3a. |
| `docs/spec/signal-seat/02-lifecycle.md` | **KEEP** | State machine + event vocabulary collision-free (EventSource/EventAuthority members verified); confirm member names at port time. |
| `docs/spec/signal-seat/03-rails.md` | **KEEP** | The dual-rail hardened design — the file where the archive most decisively supersedes master's draft (which still specs the withdrawn interim ceiling). |
| `docs/spec/signal-seat/04-auth-and-api.md` | **KEEP** | Router set identical fork→master (main.py diff empty); enumerate the three envelope routes in the §1a matrix; add a contract-6 (sellside purity) note. |
| `docs/spec/signal-seat/05-conversion.md` | **REWRITE** | Buy branch nearly intact; the entire sell-direction half is written against a sell side that no longer exists (ADR-010 envelopes, INV-090 projection, WO-0108 rails, INV-091) — including the undesigned signal-sell-vs-envelope question. |
| `docs/spec/signal-seat/06-invariants.md` | **REWRITE** | The archive delta is exactly the stale INV-4 exposure row; must gain INV-090/INV-091 preservation rows (and audit INV-034/085/087). |
| `pkl/architecture/signal-seat.md` | **REWRITE** | Rules distillation is accurate, but frontmatter asserts archive-local acceptance; keep draft/medium until the master-side flip. |

### tests

| File | Verdict | Reason |
|---|---|---|
| `tests/signal_seat_helpers.py` | **KEEP** | Test-only construction seam; rebases cleanly once `create_app` grows the settings/capability/rails params. |
| `tests/test_cockpit_operator_header.py` | **KEEP** | Red-first today (2 of 4 tests fail red; 2 pass vacuously); goes green with the header plumbing. |
| `tests/test_import_boundaries.py` | **REWRITE** (hunk-only) | Never port the file (master drifted); cherry-pick the 5-line `_SANCTIONED_ALPACA_REACHERS` hunk (:45-49) **in the same change as** server.py/`__main__.py` — CI fails otherwise (verify amendment A). |
| `tests/test_phase6_facade_foundations.py` | **REWRITE** (hunk-only) | Cherry-pick only the two request-aware `get_actor` tests; whole-file port would revert master formatting. |
| `tests/test_signal_facade_reads.py` | **KEEP** | Lazy-expiry read corpus; all fixtures/seams survive (`any_store` conftest.py:28, `InvalidInputError` errors.py:83). |
| `tests/test_signal_ingest_store.py` | **KEEP** | Most portable store regression corpus; every seam signature-compatible on master; tests port verbatim, store code rebuilds. |
| `tests/test_signal_malformed_input_matrix.py` | **KEEP** | Quarantine-boundary class tests; pure HTTP-level via the helper seam; no pre-R2 store assumptions. |
| `tests/test_signal_projector_forward_compat.py` | **KEEP** | Synthetic-event fold tests; ExecutionEvent gained only nullable `envelope_id` since fork. |
| `tests/test_signal_quarantine_totality.py` | **KEEP** | The totality invariant that ended the finding-per-round treadmill; `_SYMBOL_RE` byte-identical at base.py:71. |
| `tests/test_signal_routes.py` | **KEEP** | 1,021-line WO-0102 acceptance corpus — highest-value red-first asset; all HTTP seams zero-drift since fork. |
| `tests/test_signal_seat_config.py` | **KEEP** | Env-parsing/validation corpus; `load_settings` drifted only +18 lines. |
| `tests/test_signal_seat_launch_guard.py` | **KEEP** | Construction-time guard corpus; encodes the remediated design → ships with/after the ADR gate. |
| `tests/test_signal_seat_launcher.py` | **KEEP** | Socket-level never-accepts proof; preserve the deferred positive-control note (pending WO-0104 real rails). |
| `tests/test_signal_seat_models.py` | **KEEP** | Model-kernel spec incl. the INV-1 FILL-only guard; zero enum name collisions. |

### governance

| File | Verdict | Reason |
|---|---|---|
| `work/ledger.jsonl` (6 archive entries) | **RECORD-ONLY** | Branch-truth decisions; `ADR-009-ACCEPTED` contradicts master's ADR file; fresh entries at fresh ids on revival. |
| `work/queue/WO-0102-signal-ingestion-endpoint.md` | **REWRITE** | The remediated contract text is the portable asset; revert status to gated/draft; re-confirm the schema approval (branch-only ledger cite); rebuild against 6-contract import-linter and current seams. |
| `work/queue/WO-0103-signal-approval-surface.md` | **REWRITE** | Keep the A-2 atomic-command contract; **escalate the multi-exit relaxation** (collides with INV-087/090); rebuild exposure text against the projection. |
| `work/queue/WO-0104-signal-rails.md` | **REWRITE** | Keep rails semantics verbatim (three review rounds of hardening); rebuild allowed_paths/wiring; new event fields now bind to review-hardening producer/consumer tables. |
| `work/review/DISPATCH.md` | **KEEP** | Archive-only dispatch mechanics doc; cross-reference `15_CROSS_MODEL_REVIEW.md`; drop/re-land the Opus-routing paragraph with the repo-primer decision. |
| `work/review/REV-0022/disposition.md` (archive rewrite) | **RECORD-ONLY** | The SUPERSEDED banner would falsely close master's open BLOCK gate; master's version is authoritative. |
| `work/review/REV-0023/result.md` | **DROP** | Byte-identical to master's copy; nothing to port. |
| `work/review/REV-0024/{request,result,disposition}.md` | **RECORD-ONLY** | Id collision (master REV-0024 = Option B flatten); content = proof that F-002/F-003 closed. |
| `work/review/REV-0025/{request,result,disposition}.md` | **RECORD-ONLY** | Id namespace claimed by master's history; content = highest-density hardening record + the `RESOLVED_BY_LOCK` fact. |
| `work/review/REV-0026/request.md` | **RECORD-ONLY** | Self-declared WITHDRAWN; never dispatch. |
| `work/review/REV-0027/{request,result,disposition}.md` | **RECORD-ONLY** | Certifies branch-only code; its three findings + certified-properties list become the rebuild checklist for the new code-review packet. |

---

## 6. Proposed WO ladder

Ids below are placeholders; assign next-free master ids at draft time (WO namespace ≥ WO-0117; REV namespace ≥ REV-0034). Venue rule applied: **gated/perilous surfaces (ADR text, auth/transport, schema, conversion) run locally on the strongest model; mechanical/read-heavy porting may run cloud.** All WOs close out per the repo rule (disposition + ledger + file-move in the closing commit).

### Step 1 — WO-R1: ADR-009 remediation amendment + spec reconciliation (LOCAL, strongest model)
- **Scope:** Port A-1..A-4 onto master's ADR-009 as the F-001..F-004 remediation, with: `tls_proxy` → `tailnet_serve` narrowing + Funnel-prohibition negative-test clause (D-SIG-3); A-3 exposure predicate rewritten onto `project_envelope_obligation`/`RECOVERY_OPEN_STATUSES`/INV-091; envelope + session-close routes added to the §1a matrix; all anchors refreshed; all archive REV citations converted to archive-ref provenance. Port spec files 00–04 with their mechanical fixes; rewrite 05 (sell branch + §3a, incl. the signal-sell-vs-envelope design answer), 06 (INV-090/091 rows), and the pkl page (status stays draft/medium). Re-scope WO-0102/0103/0104 queue files (status gated/draft; launcher trio added to WO-0102 allowed_paths; main.py scope widened beyond router-mount-only). Port DISPATCH.md with fixes.
- **Allowed paths:** `docs/adr/ADR-009-signal-seat-boundary.md`, `docs/spec/signal-seat/*`, `pkl/architecture/signal-seat.md`, `docs/INVARIANTS.md` (cross-refs only), `work/queue/WO-0102..0104*.md`, `work/review/DISPATCH.md`.
- **Gates:** Human approval of the amendment text (ADR change = human-gated). Status stays **Proposed**. Consumes NEEDS-INPUT items 1–6 (§8).

### Step 2 — WO-R2: Re-review dispatch + disposition (external reviewer; packet authored LOCAL)
- **Scope:** Stage one fresh packet (≥ REV-0034) against the final ADR + spec text; explicitly flag the never-reviewed items (A-1 clause 6 / D-1a; final A-4; A-3's two locked clauses; the multi-exit re-decision). Mirror the REV-0001→REV-0003 pattern.
- **Gates:** **G1 clears only on ACCEPT/ACCEPT-WITH-CHANGES**; then Ameen flips Proposed→Accepted and unfreezes the implementation WOs. Hard stop for everything below except Step 3 prep.

### Step 3 — WO-R3: Red-first test-corpus port (CLOUD-capable; branch-staged)
- **Scope:** Rebase the 12 KEEP test files + `signal_seat_helpers.py` + the two hunk cherry-picks onto master on a staging branch; re-baseline constants/citations against the amended ADR. Tests stay red on the branch; each slice merges only with its green implementation WO (CI cannot carry red tests on master).
- **Allowed paths:** `tests/signal_seat_helpers.py`, `tests/test_signal_*.py`, `tests/test_cockpit_operator_header.py`, hunks into `tests/test_import_boundaries.py` + `tests/test_phase6_facade_foundations.py`.
- **Gates:** None beyond G1 for merge; prep may start once WO-R1's text stabilizes. Never weaken a ported test to fit rebuilt code.

### Step 4 — WO-R4: Model + store integration (LOCAL for the schema-gated portion; after Lane P)
- **Scope:** `app/models.py` vocabulary; `app/store/base.py` ABC; rebuild planner block in `core.py` (post-envelope EOF seam), `memory.py` (`_atomic` integration at :480-541), `sqlite.py` (DDL re-anchored); port `projectors.py` fold + register in `app/events/replay.py` parity harness. Merge the store-slice tests green.
- **Gates:** G1 cleared; **fresh human schema-migration approval for `signal_records`** (archive approval 78d8f57 is stale — human-gated surface); dual-store test rule; T1.3-style producer/consumer pins for any new safety field; **sequenced after Lane P (WO-0114)**.

### Step 5 — WO-R5: Endpoint + auth + launcher (rebuilt WO-0102) (LOCAL, strongest model)
- **Scope:** `routes_signals.py`, `deps.py` rework (fail-closed `get_actor` fix), `schemas.py` block, `facade/signals.py` + `signal_rails.py`, `config.py` fields, `main.py` guards/middleware/mount, launcher trio (`server.py`, `launch_guard.py`, `__main__.py`), `.importlinter` contract-5 line, **same-change**: import-boundary allowlist hunk + cockpit `X-Operator-Key` plumbing + README callout (with the UNDEFINED-not-None correction). Merge the HTTP/config/launcher test slices green.
- **Gates:** G1 cleared; human-gated auth surface; **fresh code-review packet** (new id; REV-0027's F-1/F-2/F-3 + certified-properties list as the checklist); no partial landing of the enforcement flip without cockpit plumbing (invariant 11).

### Step 6 — WO-R6: Rails provider (rebuilt WO-0104) (LOCAL)
- **Scope:** Real dual-rail provider (refilling bucket + non-refilling durable budget, atomic debit+append, epoch co-open, both-rails release), durable rail state in both stores, release route via facade, rails-presence guard satisfaction.
- **Gates:** G1; review-hardening producer/consumer tables for new event fields; dual-store + restart-durability tests; after WO-R4/R5.

### Step 7 — WO-R7: Approval→conversion surface (rebuilt WO-0103) (LOCAL, strongest model)
- **Scope:** A-2 atomic conversion command in both stores; exposure ceiling via the INV-090 projection; exit-preemption epoch respect (`docs/INVARIANTS.md:686-691`); `rejected_by` field + projector alias under its own schema approval; crash/interleaving matrix.
- **Gates:** G1; the **fresh multi-exit human decision** (NEEDS-INPUT 7) and the signal-sell-vs-envelope design answer from WO-R1; enablement is the **joint WO-R5+R6+R7 milestone with the D-2a release gate + joint mounted-app test** — the flag never turns on before all three close.

---

## 7. Sequencing constraints

- **After Lane P (WO-0114):** WO-R4, R6, R7 (and R5's store-adjacent edges) touch `app/store/*` event-log truth; O-3 sequences implementation after Lane P, which is still queued and will move the store seams again. Plan one re-baselining pass of the engine-store REWRITE notes when Lane P lands.
- **May run earlier (before/parallel to Lane P):** WO-R1 (docs/specs/queue only), WO-R2 (review dispatch), WO-R3 branch prep (tests are read-only against production seams until merge), DISPATCH.md port, and the batched operator decisions in §8.
- **Hard orderings inside the ladder:** R2 blocks R4–R7 (G1); fresh schema approval blocks R4's sqlite slice; R5's enforcement flip, cockpit plumbing, import-boundary hunk, and launcher trio are one atomic change; R6+R7 join R5 in the D-2a enablement milestone; the repo-primer bullet lands only on explicit re-ratification.
- **Concurrency per operator preference:** R3 (cloud) may run alongside R1/R2; R4 and R5 may overlap only where file sets are disjoint (store trio vs API/launcher), sequencing the shared `models.py`/`base.py` foundation first.

---

## 8. NEEDS-INPUT (batched for one operator pass)

1. **D-SIG-1 — Producer topology:** Option A (localhost-only, recommended), B (tailnet), or C (internet — blocked until the D-HOST-1 auth ADR). Sizes everything else.
2. **D-SIG-2 — ADR-009 re-review path:** confirm one fresh packet (≥ REV-0034) against the final locked text; reviewer choice at your discretion (non-negotiable process gate per CLAUDE.md).
3. **D-SIG-3 — Transport vocabulary:** accept `loopback` default + `tailnet_serve` replacing `tls_proxy`, with Funnel prohibition as a spec-level negative test. (Strong default — accept/decline.)
4. **D-SIG-4 — Bind-guard revival:** re-implement the construction-time one-shot capability + `python -m app` launcher regardless of topology. (Strong default — accept/decline.)
5. **D-SIG-5 — Flag-on read enforcement:** confirm that enabling the seat makes ALL sensitive reads operator-key-gated — this changes your own daily workflow (every client needs the key).
6. **D-SIG-6 — Interim key custody:** env-injected static keys with multi-key overlap rotation + restart, on the home PC, until the VPS-era secret store. (Strong default — accept/decline.)
7. **Multi-exit / single-flight relaxation:** your 2026-07-14 lock (concurrent signal exits, single-flight relaxed) predates INV-087/INV-090 and collides with both — needs a fresh decision; cannot carry forward silently under the conflict rule.
8. **Signal-sell vs envelope relationship:** must a signal-driven sell mint/join an execution envelope, or ride a legacy-lane intent? Undesigned question the 05-conversion rewrite must answer; your steer wanted before WO-R1 finalizes.
9. **Fresh `signal_records` schema approval:** the archived approval (78d8f57) was given against a pre-R2 schema under branch-only governance — re-approve at WO-R4.
10. **Repo-primer Opus-routing bullet:** re-ratify (with refreshed model currency and the `recommended_model` frontmatter convention either re-established or stripped) or leave RECORD-ONLY in the archive.
11. **WO-0102 scope refresh:** approve widening allowed_paths to include the launcher trio and `app/main.py` beyond router-mount-only (current text at `work/queue/WO-0102-signal-ingestion-endpoint.md:42` is narrower than the A-1 remediation requires).
