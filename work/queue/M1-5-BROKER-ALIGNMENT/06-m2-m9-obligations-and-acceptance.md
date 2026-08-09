# M2–M9 obligations and acceptance

| Milestone | Required profile-related proof | Must fail closed | Explicitly not authorized by M1.5 |
| --- | --- | --- | --- |
| M2 | Complete selected-profile binding, historical retention, one eligible profile, atomic old/new persistence, and startup/final-claim comparison. | Missing/unbound row; altered origin/account/credential/capability/deployment; two eligible profiles; cross-profile ID substitution; in-place change. | DDL now, database creation now, another provider, credentials, broker calls. |
| M3 | Deterministic replay/crash/cutover traces include profile commitment and preserve identity-scoped facts/effects/receipts. | Replay tries to rewrite profile history or split a profile change from a fact/effect transition. | A simulated topology becoming a runtime routing feature. |
| M4 | Measured Alpaca Paper capability profile and adapter normalization/correlation evidence under a separately approved credential gate. | Capability absent/expired/unproven; Paper/endpoint/fingerprint mismatch; incomplete coverage. | Live trading, Webull adapter, arbitrary capability claims. |
| M5–M8 | Paper-only operation retains the same selected profile; observed safety controls remain profile-scoped. | Any second authority, profile mismatch, or inferred market source. | Provider change, failover, routing, live promotion. |
| M9 | Official-document and empirical feasibility packet covers account/product access, session behavior, order/query/event semantics, correlation, correction/bust form, coverage/reconnect, limits, data entitlements, and paper/production difference. | Missing evidence leaves M9 non-serving and no adapter decision occurs. | Assuming suitability, using credentials, sending orders, or promoting live execution. |

## Minimum acceptance matrix for the future M2 work order

- **Profile uniqueness:** prove one immutable selected profile per application
  generation and reject a second mutation-eligible profile before I/O.
- **Binding completeness:** enumerate every capital-relevant relation and prove a
  missing, null, copied, or mismatched profile binding prevents serving.
- **External-account equality:** prove the one selected adapter extractor
  produces a valid provider-authoritative identifier whose
  `broker-account-identity/v1` commitment equals the profile; a different,
  absent, plural, alias, label, normalized, or reused raw value prevents
  preflight, mutation, final claim completion, and later broker requests.
- **Historical integrity:** prove exact historical profile retention through fact
  correction/bust, effect closure, restart, replay, and new-generation recutover.
- **Cutover:** prove an in-place provider/account/origin/credential/capability/
  adapter/deployment change fails; only a separately reviewed new generation can
  present a complete recutover proof.
- **Market separation:** prove a market stream has a committed market-data source
  and cannot acquire that authority from the execution profile.
- **Capability evidence:** prove stale, altered, incomplete, or non-evidence
  capability records deny the operation they would otherwise permit.

M1.5 accepts only this obligation contract. No test here is a substitute for
future M2 red/green, schema, crash, adapter, or operational proof.
