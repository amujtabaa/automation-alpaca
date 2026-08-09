# M1.5 roadmap reconciliation and M2–M9 obligations

Status: **TASK A CANDIDATE — NO MILESTONE ACTIVATION**

| Milestone | Obligation after proposed ADR-024 |
|---|---|
| M1 | Closed and unchanged; no public kernel or proof edits. |
| M1.5 | Independently review and human-ratify exact overlay hashes; land accepted knowledge only. |
| M2 | Design SQLite/crash semantics around one immutable provider-neutral active connection profile; keep M2 inactive until separately authorized. |
| M3 | Prove replay/hydration cannot cross profile or market-source commitments and preserves the atomic M1 transition. |
| M4 | Implement only an Alpaca Paper conformance adapter after authority; prove an evidence-backed capability profile and correlation to the immutable connection profile. |
| M5 | Exercise SELL protection beta only through the M4-proven Alpaca Paper profile. |
| M6 | Exercise BUY acquisition with the same single profile and existing approval/safety authority. |
| M7 | Expose handoff/cockpit observations without making the UI a broker caller or execution-state owner. |
| M8 | Soak and accept the paper MVP on the exact profile/capability evidence; do not infer live readiness. |
| M9 | Separately research and empirically assess Webull; propose an adapter/new-generation recutover only through a new accepted decision. |

IBKR Pro remains an optional later measured execution-quality comparator. FIX/QuickFIX requires an
authorized session and evidence of operational benefit. Robinhood Agentic/MCP and Tradier remain
outside the near-term safety-critical path. None is an M1.5 implementation target.

M9 must use then-current official documentation and controlled empirical evidence for account,
session, extended-hours, order, query, event, correction, partial-fill, rate-limit, entitlement,
sandbox/production, and identity behavior. Marketing claims are not capability evidence. M9 must
not use credentials in this public repository or weaken the human-approval model for cloud tests.
