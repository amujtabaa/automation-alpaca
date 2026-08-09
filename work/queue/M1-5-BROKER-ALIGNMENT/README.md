# M1.5 broker-role and persistence-boundary alignment

Status: **candidate only — documentation-only — M2 inactive**

This packet re-derives one narrow architecture overlay from `master` at
`5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`. It is governed by active
`WO-0157`, reviewed in `REV-0063`, and proposes **ADR-024**. It is not a
runtime plan, DDL, database schema, broker integration, credential record, or
authority to trade.

## Semantic candidate boundary

The semantic candidate consists exactly of this README, numbered documents
`01` through `07`, active `WO-0157`, and every exact `REV-0063` request path
listed in `AUTHORITY-MANIFEST.sha256`. The manifest lists every included path
and SHA-256 digest; it excludes itself to avoid a self-referential digest
cycle. Reviewer-owned `result.md` and each `result-remediation-*.md` addendum
are deliberately outside the semantic candidate and retain their own hashes.
At human ratification, only the named terminal
`result-remediation-03.md` may supply the required `ACCEPT`, P0=0, P1=0
review verdict; earlier negative results remain immutable provenance.

## Binding outcome

- M1 remains closed and unchanged.
- M2 through M8 retain **Alpaca Paper** as the sole mutation-capable beta
  execution provider.
- One immutable, provider-neutral `ExecutionConnectionProfile` is selected for
  each application generation; exactly one profile can be mutation-eligible.
- Webull is a separate future M9 feasibility/adapter candidate, IBKR Pro is a
  benchmark only, and FIX/QuickFIX, Robinhood, Tradier, routing, failover, and
  live trading remain deferred.
- Execution-provider identity and market-data-source identity are distinct.

No human approval is inferred from this packet. A separate exact-hash approval
is mandatory before copying the proposed ADR unchanged to `docs/adr/` or
reconciling current authority records.
