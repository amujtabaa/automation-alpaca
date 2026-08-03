# WO-0148 eighth RED exact-commit review request

Status: **INDEPENDENT PRE-PRODUCTION TEST-CONTRACT REVIEW**

Review exact commit `7beda3f61e4d44f035143e883d7efa35a424f661` against activation base
`d75806b1a79d1769db25ae962c0977cd9388a886`. This is the immutable eighth RED
candidate. Production `app/execution_core/protection.py` is deliberately absent and remains barred.

Read `AGENTS.md`, the `CLAUDE.md` safety core, the complete active WO-0148, its linked accepted
authority, and the exact diff. Re-derive the test contract from those sources. Do not inherit the
implementation seat's reasoning or count an in-process pre-flight as independent evidence.

Hostile review objectives:

1. Attempt to disprove every normative WO clause and required mutation control represented by the
   RED contract, including all nine P1 repairs recorded in the active WO.
2. Require a concrete reachable bypass, counterexample, contract contradiction, or failure-capable
   missing control for P0/P1. Classify speculative hardening, style, and preference as P2/advisory.
3. Verify that new meta-oracles can fail, reject attacker-controlled payloads before execution, do
   not overfit irrelevant CPython details, and do not weaken predecessor guarantees.
4. Verify exact RED failure classification, static/format/grammar/scope integrity, production
   absence, and preservation of the always-on safety and authority boundaries.

No `INV-*` entry is added or amended by this test-only candidate, so no new-invariant probe is due.
Do not implement production, edit tests or the WO, use credentials, call Alpaca, execute SQL/DDL,
initialize a database, alter runtime/persistence, or perform cleanup/deletion.

Write findings only to `work/review/REV-0050/RED-EIGHTH-RESULT.md`. For each finding include exact
file/line, why it matters, the concrete disproof, and what resolves it. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`, explicitly state unverified items, and report whether any P0/P1
remains. This verdict governs only permission to begin WO-0148 production implementation; it does
not replace the later final implementation review or close the work order.
