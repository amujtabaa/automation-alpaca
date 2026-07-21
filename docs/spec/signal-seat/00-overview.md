
# Signal Seat — Contract Specification (WO-0101)

**Authority:** accepted implementation contract for ADR-009 as amended by WO-0127. REV-0034
returned ACCEPT-WITH-CHANGES, WO-0133 resolved its required citation corrections, and Ameen
accepted the final ADR text at `385cc7d` on 2026-07-21. Where this spec and ADR-009 disagree,
ADR-009 wins and the disagreement is a defect in this spec.
**Status:** architecture accepted 2026-07-21; implementation has not begun. WO-0102..0104 remain
draft and retain their activation, sequencing, implementation-review, and joint-enablement gates.
The fresh `signal_records` DDL approval remains deliberately deferred to WO-R4.
**Tree basis:** `origin/master@3b8c840` plus the ULTRA batch continuity commit; current-tree anchors
were refreshed during WO-0127.

> **Archive provenance convention.** References to archive REV-0024/0025 below mean records at
> `origin/archive/claude-wo-0001-install-checks-2x5ys8`; those packet ids are never ported to
> master and did not clear the fresh REV-0034 gate.

## Document map

| Doc | Contents |
|---|---|
| `01-schema.md` | `SignalProposal` wire schema, `SignalRecord` entity, the approval payload, dedupe/idempotency semantics, validation rules |
| `02-lifecycle.md` | Signal state machine, event-log vocabulary additions, TTL/staleness rules, replay/reconstruction contract |
| `03-rails.md` | Rate limits, the non-refilling invalid/conflict budget, enablement gated on full rails, producer quarantine + release, flood backpressure |
| `04-auth-and-api.md` | Producer/operator credential model, endpoint definitions (OpenAPI fragment), feature flag + mount rules |
| `05-conversion.md` | Approval → order-intent conversion per direction, the risk-reducing classification, TradingState/kill-switch interaction table, signal→order correlation |
| `06-invariants.md` | Preservation notes: CLAUDE.md invariants 1–11 and spine §5 INV-1..9, each mapped to the concrete mechanism in this spec |

## Roles and vocabulary

- **Producer** — an out-of-process, untrusted advisor (exemplar: HKUDS Vibe-Trading) holding an
  ingestion-scoped API key. Producers can do exactly one thing: `POST /api/signals`.
- **Operator** — the human (browser-first, via the cockpit) holding the operator credential.
  Only operators approve, reject, or release.
- **Signal** — a proposal, identified by `(producer_id, signal_id)`. It carries **zero execution
  authority** at every trust level in this spec (L0 only; L1/L2 need superseding ADRs).
- **Conversion** — the atomic act, triggered only by operator approval, that turns an approved
  signal into a standard order intent through the existing candidate/sell-intent pipeline.

## Feature flag

`Settings.signal_seat_enabled: bool = False` (env `SIGNAL_SEAT_ENABLED`). Flag off ⇒ the signal
routers are **not mounted** in `create_app` (`app/main.py`) — endpoints 404, no auth surface, no
storage writes possible. Flag on ⇒ routers mounted **and** operator-credential enforcement on
**every sensitive route — reads included** — is active (the two flip together; see the fail-closed
mounted-route matrix in `04-auth-and-api.md §1a` and `§4`). Read exposure is exposure: a producer
with HTTP reach must learn nothing about positions, orders, sessions, or other producers' theses,
so the enforcement is **not** narrowed to mutating command routes (ADR-009 A-1.3; archive REV-0024-F-003).
**Enablement is gated on full rails (ADR-009 A-4; not a deployment discipline but a startup guard):**
with the flag on, startup **fails fast** unless the full per-producer rails are wired — refilling
rate bucket, non-refilling invalid/conflict budget, producer-quarantine epoch, and human release
path (parallel to the credential-presence guard). There is **no interim ceiling** and no window in
which an enabled endpoint is unrailed; the former audit-free interim ceiling was withdrawn after
archive REV-0024. Live enablement is therefore the **joint WO-0102 + WO-0103 + WO-0104 milestone** — ingest
endpoint, the WO-0103 atomic approval→conversion (an enabled seat that cannot atomically convert
re-opens F-002), and the rails (`03-rails.md §2`). V1 producer topology is localhost-only
(`loopback`); `tailnet_serve` is the only configured remote transport. Tailscale Funnel and all
other public exposure are forbidden and negatively tested.

## Out of scope (log, don't build)

L1/L2 trust levels; any producer code in-repo; reference producer shim; backtest/data sharing;
multi-operator RBAC (beta has one operator credential).
