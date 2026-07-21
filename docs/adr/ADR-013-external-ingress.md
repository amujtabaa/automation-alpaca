# ADR-013: External Webhook Ingress Through a Public Receiver

**Status:** **Proposed — draft seed only; not approved for implementation**
**Date:** 2026-07-20
**Deciders:** Ameen (future human gate)
**Number:** ADR-013
**Prerequisites:** accepted D-HOST-1 deployment/auth ADR and independent acceptance review of this
ADR's final text.

> This seed records D-SIG-9 and the operator's intent to pursue TradingView/webhook producers
> relatively soon. It does not authorize a public endpoint, deployment, dependency, credential
> store, schema, or order path.

## Context

ADR-009's beta topology keeps the FastAPI trading API private: localhost by default and
`tailnet_serve` as the only remote configuration. Tailscale Funnel and every other public
exposure are forbidden. Third-party systems such as TradingView require an Internet-reachable
webhook target, but making the trading API itself public would erase the load-bearing private
boundary and expose all sensitive reads and human-gated commands.

## Proposed decision — Option C receiver architecture

Use a separate, thin public **Receiver** as the only Internet-facing component:

1. The Receiver accepts the vendor webhook on one narrowly scoped endpoint.
2. It authenticates before trust using a configured webhook secret/HMAC contract and rejects
   missing, invalid, malformed, oversized, or replay-invalid requests fail-closed.
3. It normalizes the authenticated vendor payload into ADR-009's `SignalProposal` contract.
4. It forwards the normalized proposal into the private Signal Seat path using its own
   ingestion-scoped producer key.
5. The private FastAPI trading API remains loopback/tailnet-only and is **never public**.
6. The Receiver holds zero order, fill, position, risk, approval, or execution state. It cannot
   approve, reject, release, submit, cancel, flatten, or operate the kill switch.
7. A proposal still carries zero execution authority and requires the ordinary ADR-009 L0
   per-signal operator approval.

The Receiver is a producer adapter at the trust boundary, not a second engine and not an execution
lane. Its only downstream capability is the same keyed `POST /api/signals` ingress available to
other producers.

## Security boundary

The final ADR must define, with executable acceptance criteria:

- exact webhook authentication and canonicalization rules (HMAC/secret handling, rotation,
  constant-time verification, replay window/idempotency);
- request-size, parsing, rate, observability, and secret-custody rails;
- Receiver-to-private-path transport and producer-key custody;
- failure/retry behavior that preserves ADR-009 dedupe and never blind-resubmits a distinct signal;
- deployment isolation, update/rollback, logging/redaction, and incident response;
- proof that no public route reaches the trading API or any operator credential.

## Prerequisite gates

Implementation cannot begin until all are true:

1. D-HOST-1 selects and accepts the deployment architecture and authentication boundary.
2. This ADR is completed with concrete deployment, threat, secret, replay, and failure contracts.
3. The completed ADR receives independent cross-model acceptance review and human disposition.
4. Any new dependency, schema, event vocabulary, or public deployment surface receives its own
   required gate.
5. ADR-009 itself has cleared REV-0034 and the Signal Seat private path exists behind its gates.

## Options recorded

- **A — make the trading API public:** rejected; it exposes sensitive reads and human-gated
  commands and contradicts D-SIG-3.
- **B — use Tailscale Funnel directly on FastAPI:** rejected; Funnel/public exposure is explicitly
  forbidden.
- **C — thin public Receiver forwarding privately as a keyed producer:** proposed.
- **D — vendor calls a tailnet-only endpoint:** unsuitable for an Internet webhook producer.

## Consequences if later accepted

The public attack surface is confined to a stateless normalization/authentication component, while
the deterministic single-writer spine and human approval boundary remain private and unchanged.
The cost is a separately deployed security boundary with its own secrets, monitoring, review, and
availability requirements.

## Out of scope for this seed

Implementation, hosting selection, a Receiver repository/package, concrete secrets, DDL/event
changes, TradingView-specific field mapping, L1/L2 automation, and any public exposure today.
