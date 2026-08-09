# Human ratification request contract

This document defines the required request; it intentionally contains no
precomputed hash so a later candidate change cannot be mistaken for approval.
After independent `ACCEPT` with P0=0/P1=0, the delivery seat must present the
current values below in the same session:

```text
READY FOR HUMAN M1.5 RATIFICATION

Current master/base SHA: <base>
Branch: <branch>
Candidate commit: <commit>
Proposed ADR number/title/path: ADR-024 — Broker roles, single active execution-connection identity, and provider-neutral M2 persistence boundary — work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md
Proposed ADR body SHA-256: <hash>
Candidate manifest path: work/queue/M1-5-BROKER-ALIGNMENT/AUTHORITY-MANIFEST.sha256
Candidate manifest SHA-256: <hash>
Independent review result path: work/review/REV-0063/result-remediation-04.md
Independent review result SHA-256: <hash>
Verdict: ACCEPT
P0: 0
P1: 0
P2: <count>
Exact candidate files: <manifest-covered paths>
Explicitly preserved: Alpaca Paper M2–M8; one active execution authority; M1 closure; first-occurrence execution truth; market-source separation; all existing no-live/credential/runtime gates.
Explicitly excluded: M2 implementation/DDL/database/runtime/broker activity; Webull/FIX/IBKR/Robinhood/Tradier integration; routing/failover; live trading; M1 source/tests; merge.
```

Required approval text:

```text
I approve the exact M1.5 candidate identified by:

- Proposed ADR body SHA-256: <hash>
- Candidate manifest SHA-256: <hash>
- Independent review result SHA-256: <hash>
- Verdict: ACCEPT, P0=0, P1=0

This authorizes only the unchanged documentation/architecture landing,
ratification provenance, PKL/roadmap/ledger reconciliation, lifecycle closeout,
normal branch push, PR update, and unchanged validation. It does not authorize
M2 implementation, DDL, database creation, runtime wiring, broker/network
activity, credentials, Webull integration, FIX, routing, or live trading.
```

Any semantic candidate change after review creates new hashes and requires a
fresh independent review and exact new approval.

`result.md` and `result-remediation-01.md` through
`result-remediation-03.md` are immutable negative review provenance. They must
remain available for audit but must not be substituted for the terminal
`result-remediation-04.md` hash or its required `ACCEPT`, P0=0, P1=0 verdict.
If that terminal result is not an `ACCEPT`, no ratification request may be
presented; the next correction must name a new terminal accepting result path,
regenerate the manifest, and obtain a fresh independent review.
