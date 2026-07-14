# Signal Seat — Contract Specification (WO-0101)

**Authority:** implements ADR-009 (Accepted 2026-07-12) exactly; where this spec and ADR-009
disagree, ADR-009 wins and the disagreement is a defect in this spec.
**Status:** complete spec, design-only — no code ships with this document set.
**Implementer contract:** WO-0102 (ingestion), WO-0103 (approval surface + conversion), WO-0104
(rails) must be implementable from these documents alone, against the as-built tree at `c4271d8`+.

## Document map

| Doc | Contents |
|---|---|
| `01-schema.md` | `SignalProposal` wire schema, `SignalRecord` entity, the approval payload, dedupe/idempotency semantics, validation rules |
| `02-lifecycle.md` | Signal state machine, event-log vocabulary additions, TTL/staleness rules, replay/reconstruction contract |
| `03-rails.md` | Rate limits, the WO-0102 interim ingest ceiling, producer quarantine + release, flood backpressure |
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
storage writes possible. Flag on ⇒ routers mounted **and** operator-credential enforcement on all
mutating command routes is active (the two flip together; see `04-auth-and-api.md §4`).
**Deployment gate (ADR-009 rails):** the flag must not be enabled in any environment before
WO-0104's full rails land — but the code does not rely on that discipline: WO-0102 ships the
interim hard ceiling (`03-rails.md §2`) so an enabled endpoint is never unrailed.

## Out of scope (log, don't build)

L1/L2 trust levels; any producer code in-repo; reference producer shim; backtest/data sharing;
multi-operator RBAC (beta has one operator credential).
