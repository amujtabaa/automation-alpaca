# REV-0074 R8 — authenticated direct-proof amendment review result

## P1 — Radix witness does not yet prove membership

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:643-651`
- **Mechanism:** Existing radix nodes aggregate child edges with XOR (`app/execution_core/fills.py:340-364`). A path witness can substitute a queried child and compensate with an arbitrary sibling aggregate while preserving the committed XOR. The stated terminal 256-child absence witness addresses terminal absence, not membership at intermediate nodes.
- **Impact:** A stale or substituted direct row can remain indistinguishable from a committed member, so the REV-0075 R2 execution-proof defect is not closed.
- **Smallest complete root correction:** Freeze a sound authenticated-node proof: require complete canonical labelled sibling commitments at every traversed node, including exact ordering/count and value commitment, or replace XOR aggregation with an ordered 256-ary Merkle construction whose proof semantics establish membership and absence.

## P1 — `CurrentProofSlice` remains caller-forgeable and freshness-unbound

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:653-658`
- **Mechanism:** `CurrentProofSlice` is a publicly constructible frozen dataclass (`app/execution_core/persistence/records.py:300-323`), and `load_current_proof()` returns that ordinary carrier (`app/execution_core/persistence/repository.py:2374-2378,2770-2793`). Type-checking and internal coordinate comparisons cannot prove repository provenance, bind the requested envelope, or prevent replay of a stale but internally consistent slice.
- **Impact:** The checkpoint adapter can still seal caller-selected, stale, or mis-profiled authority rows, leaving the REV-0075 R2 protection-proof gap open.
- **Smallest complete root correction:** Make the slice an opaque repository-issued capability/sealed value bound to the exact `CurrentProofRequest`, envelope coordinates, and one verified currentness/read snapshot; the codec adapter must accept only that sealed value, never a public raw carrier.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 0

Unverified: R8 implementation and tests; SQLite/DDL, runtime composition, and broader suites were not run per instruction.
