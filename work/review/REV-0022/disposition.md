---
type: Review Disposition
rev_id: REV-0022
verdict_received: BLOCK
disposition_status: REMEDIATION_OPEN
date: 2026-07-14
---

# Disposition — REV-0022 (ADR-009 Signal Seat acceptance review)

**Verdict: BLOCK** (GPT-5/Codex, formal packet run by Ameen on frozen commit `25590a7`,
result dated 2026-07-11 — `result.md`). Four P1 findings, none yet remediated:

- **F-001** — the credential boundary is incomplete: read routes (pending-signal list, existing
  position/order/session queries) stay unauthenticated, and transport/key-lifecycle (TLS or
  loopback-only, storage, rotation, constant-time compare) is unspecified. Live probe: an
  unauthenticated request flipped the kill switch.
- **F-002** — approval→intent conversion is not required to be one atomic operation; a live
  crash-injection probe consumed a candidate approval without creating its order. The
  human-gated boundary needs a dual-store atomic command (or durable outbox), with
  crash/interleaving tests across expiry/quarantine/TradingState races.
- **F-003** — freshness/classification bounds must live in the ADR, not be deferred: server-max
  TTL, `expires_at = min(received_at + server_max_ttl, issued_at + bounded_ttl)`, skew limits,
  restart behavior, and an executable risk-reducing predicate over fresh derived position +
  outstanding sell exposure.
- **F-004** — "coalesced periodic audit" still grows without bound over indefinite hostility;
  bound must be per-quarantine-epoch (one event per epoch + summary on release), with
  auth/rate-limit before body parse and request-size caps.

## Rescind record (governance history, kept honest)

1. 2026-07-12: with no packet result visible in the repo, Ameen chose option 1 (treat the PR #5
   seven-pass Codex record as the review) and accepted ADR-009; a constructed
   ACCEPT-WITH-CHANGES result was filed (commit `15a4db1`).
2. 2026-07-14: the formal packet result (run locally 2026-07-11, pushed 2026-07-14) surfaced with
   verdict **BLOCK** — the constructed record is **superseded**
   (`result-pr5-record-SUPERSEDED.md`, kept as a catalogue of the 16 PR-round findings, several of
   which the formal review credits as fixed).
3. Same change: **ADR-009 acceptance RESCINDED** (status back to Proposed), WO-0102..0104
   re-gated, WO-0101's spec re-marked as draft input to remediation.

## Remediation status

- 2026-07-14: **Amendments A-1..A-4 drafted** into ADR-009 (one per finding), with the spec
  (`docs/spec/signal-seat/`) and WO-0102..0104 reconciled to them, and Option E (signal-inbox +
  conversion-outbox) considered and recorded per the reviewer's ask. PROPOSED — awaiting Ameen's
  approval of the amendment text, then the re-review.

## Path to clearing the gate

Remediate F-001..F-004 as ADR-009 text amendments + WO tightening (human-approved), then
re-review (new packet or REV-0022 re-run at Ameen's discretion, mirroring the REV-0001→REV-0003
pattern). The gate clears only on an ACCEPT/ACCEPT-WITH-CHANGES disposition of that re-review.
