# Roadmap and milestone reconciliation

This overlay adds M1.5 between a closed M1 and inactive M2. It preserves the
existing dependency order and the selected Alpaca Paper beta path.

```text
M1    Pure execution kernel — CLOSED and unchanged
M1.5  Broker-role and provider-neutral persistence-boundary alignment
M2    SQLite and crash semantics — inactive; selected Alpaca Paper profile only
M3    Simulator and semantic replay — profile-scoped refusal/replay proof
M4    Alpaca Paper conformance adapter — measured selected-profile capabilities
M5    SELL protection beta — Alpaca Paper path
M6    BUY acquisition — Alpaca Paper path
M7    Cockpit and handoff — Alpaca Paper path
M8    Paper soak and acceptance — Alpaca Paper path
M9    Webull feasibility and possible adapter — separate future wave
```

## Reconciliation rules

1. M1's exact source, tests, public surface, and proof remain frozen. The M1-to-
   M2 handoff remains evidence of the atomic boundary, not persistence authority.
2. M2 does not begin because ADR-024 exists. A separately activated M2 work order
   must reconcile the profile contract with its reviewed schema and refusal tests.
3. M3 treats profile commitment as part of replay/cutover coordinates. It cannot
   simulate or infer an unapproved second broker authority.
4. M4 remains the first opportunity to establish selected Alpaca Paper adapter
   capability evidence, and still requires the existing credential/outbound-call
   human gate.
5. M5–M8 do not change provider. Any live promotion remains separately planned,
   externally verified, and human-gated.
6. M9 begins with official documents plus empirical feasibility against a
   separately approved non-live scope. It does not assume that a Webull adapter
   will be built or accepted.

## Backlink intent after ratification

Current authority records should point to ADR-024 as the narrow resolution of
provider-literal persistence representation. They should continue to point to
ADR-022 for the selected Alpaca Paper fence and to ADR-020/021/023 for execution,
protection, and market-source safety semantics. The digest-pinned historical
roadmap packet remains preserved; current PKL and ADR backlinks carry the new
overlay.
