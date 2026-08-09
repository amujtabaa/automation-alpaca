# M1.5 authority and conflict audit

Status: **TASK A CANDIDATE — NOT ACCEPTED AUTHORITY**
Task A base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`

## Controlling baseline

- The safety core keeps the beta paper-only and Alpaca-only, makes the backend the source of truth,
  and permits quantity changes only from canonical execution facts.
- ADR-020 R2 freezes the pure, bounded execution kernel and makes
  `ApplicationGenerationId` the deployment/cutover and broker-authority fence.
- ADR-021 R2 keeps one aggregate position, one composite authority path, and one active broker
  authority while assigning persistence and adapter proof to later milestones.
- ADR-022 selects Alpaca Paper/live-shadow for beta and currently expresses the cutover fence and
  several durable bindings with literal Alpaca/Paper/origin/account coordinates.
- ADR-023 independently governs market occurrence authority, but its
  `MarketStreamGenerationId` does not yet bind an explicit market-source profile commitment.
- The WO-0152 M1-to-M2 handoff freezes the public M1 transition and requires M2 to persist the
  composite transition atomically. It grants no M2, DDL, runtime, broker, or credential authority.

## Conflicts and required reconciliation

| Existing clause | Classification | M1.5 treatment |
|---|---|---|
| ADR-020 §§1–6 pure reducer, canonical facts, bounded state, atomic M2 transition | Preserve | No M1 interface, state, reducer, or proof changes. |
| ADR-020 application generation as broker-authority fence | Preserve and refine | The generation binds exactly one immutable execution-connection profile commitment. |
| ADR-021 one active broker authority and composite path | Preserve | Portability never means concurrent authority, routing, or failover. |
| ADR-022 beta boundary: Alpaca Paper/live-shadow only | Preserve | Alpaca Paper remains the sole M2–M8 mutation-eligible provider. |
| ADR-022 cutover fence names literal `ALPACA`, `PAPER`, origins, account, and credential fingerprint | Narrowly supersede | These remain required beta profile values, but the durable relationship binds a profile identity/commitment rather than permanently limiting the provider domain. |
| ADR-022 rows bind directly to singleton generation and literal coordinates | Narrowly supersede | Capital-relevant rows bind the exact profile identity or commitment, which itself is immutable and generation-bound. |
| ADR-022 exact final-claim comparison and live endpoint refusal | Preserve | Compare the committed profile fields; any mismatch or non-Paper beta value fails closed before I/O. |
| ADR-023 stream generation and evidence policy | Preserve and refine | A later separately reviewed change must bind each stream generation to one market-source commitment; execution provider must not be inferred. |
| Existing exact schema/table/constraint language | Block pending M2 reconciliation | No provider-literal DDL may be implemented until it conforms to the overlay; exact DDL remains an M2 decision. |

There is no conflict requiring an M1 code change. The correction is prospective: it changes the
identity to which M2 persistence must bind while retaining every selected beta value and fail-closed
condition. The proposed overlay cannot become authority without independent review and human
approval of exact hashes.

## Security and public-repository boundary

The profile may persist opaque credential-handle identity, version, and a non-reversible
fingerprint only. It must never contain a secret, token, account credential, private broker
document, entitlement artifact, or recoverable credential material. This candidate performed no
network or broker activity and introduces none.
