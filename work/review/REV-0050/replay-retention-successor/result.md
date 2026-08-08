# REV-0050 occurrence-receipt successor independent review result

Exact candidate: `488ce0e7cb954d7b1d19c2bc0127a925e069ea58`  
Candidate predecessor: `34eb7f4aeea96c60522c4a8ca1b4575de41ffa39`  
Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## Findings

### P1 — The aggregate-lifetime receipt map makes incremental market state unbounded

- **Location:** `app/execution_core/protection.py:1088-1090` and
  `app/execution_core/protection.py:1479-1484`.
- **Requirement:** Accepted ADR-020 at `docs/adr/ADR-020-current-state-execution-kernel.md:165-166`
  requires both that live work not scale with audit-history length and that incremental market
  state be bounded. Repository instructions also require an accepted ADR for an architecture
  change. The successor must close the non-last replay/equivocation defect without replacing
  bounded current market state with retained market history.
- **Evidence (`reproduced-live` plus static trace):** `_new_state_from_projection` retains the same
  `_seen_occurrence_receipts` map through every projection and lifecycle reset. Every unseen,
  well-routed occurrence is then inserted before freshness, sequence/time, halt, quote/tick, step,
  formula, or policy eligibility. There is no eviction, cardinality limit, epoch compaction, or
  fail-closed overflow path anywhere in the candidate. A fresh exact-candidate probe delivered
  1,000 distinct well-routed but stale occurrences to one state; the retained map grew from
  `size=0` to `size=1000` (`delta=1000`). `_PersistentKeyMap` gives history-independent lookup
  depth, but `PositionProtectionState` retains its full radix root and all inserted values, so
  constant path work does not bound current-state storage. The changed tests assert that each
  ineligible occurrence increments the map but contain no cap/scaling or overflow control. The
  candidate's implementation note calling for aggregate-lifetime retention cannot override the
  accepted ADR, and no ADR amendment is present.
- **Impact:** Once wired in a later slice, ordinary high-rate market traffic—including stale,
  crossed, step-invalid, halted, or otherwise unusable facts—would grow the capital-relevant
  checkpoint for the lifetime of the aggregate. Memory, hydration, and eventual SQLite
  serialization cost therefore grow with market-history length, contradicting the reset kernel's
  bounded live-state/startup design. This slice is pure and unwired, so the defect is not presently
  a broker-effect or safety-invariant P0.
- **Smallest complete resolution:** Re-gate the owning retention rule against ADR-020 and define a
  finite authenticated receipt window plus deterministic compaction/overflow behavior that still
  keeps every identity capable of affecting corroboration from regaining authority. Keep
  full-lifetime audit receipts outside live protection state. Add a long-history bound test,
  restart/compaction replay and equivocation controls, and a mutation that removes the bound. If
  exact aggregate-lifetime payload refusal is instead required, obtain explicit human approval for
  an ADR amendment before implementation; a work-order evidence paragraph is not sufficient
  architecture authority.

## Fresh verification

- Exact `HEAD` and commit objects were verified at the requested candidate. The tracked tree was
  unchanged; pre-existing untracked review/evidence artifacts were not treated as candidate
  contents. The activation-base range passed the work-order scope checker and `git diff --check`.
- Fresh local execution with `BROKER_ADAPTER=mock` passed all 495 affected authority, protection,
  stateful, and import-boundary tests. This independently confirmed that the first review's
  non-last hard-bail/trailing replay and changed-payload cases are closed by the candidate.
- All five preserved mutation groups were independently parsed. Their mutant/restored results were
  respectively `4 failed / 4 passed`, `3 failed / 3 passed`, `3 failed / 3 passed`,
  `6 failed / 6 passed`, and `1 failed / 1 passed`; every artifact hash matched the mutation
  record. The point-in-time stateful restoration hash is explicitly distinguished from, and differs
  from, the final successor-freeze hash.
- Candidate SHA-256 and Git-blob hashes for `protection.py`, `test_protection.py`, and
  `test_protection_stateful.py` matched the successor record. ADR-020/021/022 hashes matched the
  ratification index.
- Ruff lint and changed-file format checks passed; mypy passed across 86 application files; Python
  3.11 grammar parsing passed for all nine candidate-range Python files; and all six import
  contracts were kept.
- Preserved JUnit/coverage artifacts were independently parsed and hash-checked: affected
  `495/495`, predecessor `745/745`, R2 `61/61`, execution core `1,071/1,071`, and full repository
  `5,659` tests with zero failures/errors and 12 skipped; raw combined coverage was
  `93.14745457067555%`. Artifact parsing is not treated as a fresh functional rerun.
- No runtime, broker, network, credentials, Alpaca, persistent application database, SQL/DDL,
  configuration, accepted ADR body, or later-slice authority was exercised or introduced.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: actual Python 3.11/3.12 exact-head CI; fresh predecessor, R2, complete execution-core, and full-repository reruns (their preserved artifacts were parsed and hash-checked); broker/network/persistent-database behavior excluded by scope
