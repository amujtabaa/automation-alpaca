# REV-0050 independent production review result

Exact candidate: `34eb7f4aeea96c60522c4a8ca1b4575de41ffa39`  
Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## Findings

### P1 — A non-last sequence-less replay can regain corroboration authority and emit a false SELL goal

**Exact location:** `app/execution_core/protection.py:1401` (with the equal-time eligibility path at
`app/execution_core/protection.py:1430-1439` and evidence consumption at
`app/execution_core/protection.py:1539-1549` / `app/execution_core/protection.py:1627-1642`).

**Requirement:** WO-0148 lines 111-120 and accepted ADR-021 lines 121-126 require two distinct,
fresh, consecutive source occurrences; exact replay/restart delivery must be an evidence no-op, and
an old observation must not regain retroactive authority after an interruption/reset. The M1
roadmap likewise requires distinct, deduplicated, strictly advancing occurrences.

**Evidence (`reproduced-live` plus static trace):** `_reduce_market_occurrence` compares the incoming
identity and payload only with `state._last_occurrence_id` / `_last_occurrence_payload`. After any
intervening occurrence replaces that one retained identity, a sequence-less earlier occurrence can
be accepted again when source time is equal and local evaluation time advances. The current
deterministic and stateful replay controls replay only the immediately preceding occurrence, so
they do not exercise this history.

Two fresh control/exploit histories on the exact candidate reproduced the consequence:

1. Hard-bail history: sequence-less A (bid 92, below trigger, source time 100) was followed by B
   (bid 95, above trigger, the same source time), then exact replay A with only a newer local
   evaluation time, then distinct C (bid 91). Replay A returned `APPLIED` and changed state. C then
   returned `APPLIED / HARD_BAIL` with a SELL goal. The B-to-C control without replay A remained
   `FLOOR_ONLY` with no goal.
2. Trailing history: after activation with trail 102, sequence-less A (bid 101, below trail) was
   followed by B (bid 105, above trail), exact replay A, then C (bid 100). With replay A, C returned
   `EXIT_NORMAL` with a SELL goal; without replay A, C remained `TRAIL_ACTIVE` with no goal.

The same last-only guard also accepted a changed-payload reuse of A's identity after B as `APPLIED`
rather than refusing the equivocation. Immediate replay/equivocation tests pass because A is still
the last retained occurrence in those tests; they do not disprove the non-last case.

**Concrete impact:** one duplicated source fact can count twice after an intervening observation and
manufacture the second corroborator for either emergency hard-bail or normal trailing exit. The
slice is currently pure and unwired, so this does not itself dispatch a broker order, but it emits
an authoritative SELL goal that later integration would be expected to consume.

**Smallest complete resolution:** make replay/equivocation recognition reducer-owned and durable for
every occurrence that can still influence an evidence window, rather than retaining only the last
identity. An exact previously seen identity/payload must remain a complete no-op after intervening
occurrences and restart; the same identity with a different payload must be refused. Add
failure-capable A -> B -> replay(A) -> C controls for both hard-bail and trail branches, including
sequence-absent bid/trade forms, plus a restart/stateful form. Retention may be bounded by the
authoritative freshness/window rules, but it must cover the whole interval in which an old fact can
regain corroboration authority.

## Fresh verification summary

- Exact `HEAD`, candidate/base commit objects, and merge base were verified. The activation-base
  range passed the work-order scope checker and `git diff --check`; accepted ADR digests and all
  candidate source/test hashes matched the packet.
- The exact 35-case coverage-strength matrix passed. Its preserved mutant JUnit was parsed as one
  intended failure (`DID NOT RAISE`), and the restored control passed.
- Fresh focused protection/transition/stateful/import execution passed 487 tests; R2 passed 61; the
  complete execution-core suite passed 1,063.
- Ruff, changed-file format check, mypy over 86 source files, all six import contracts, and Python
  3.11 grammar parsing of all nine changed Python files passed on local Python 3.12.13.
- Preserved JUnit/coverage artifacts were independently parsed: the final artifact records 5,651
  tests, zero failures/errors, 12 skips, and raw combined coverage `93.13120099909804`; recorded
  hashes matched. This artifact check is not treated as functional acceptance.
- No accepted ADR body, runtime, persistence, broker, credential, configuration, or closeout-only
  surface changed in the candidate range. The narrow authority amendment was tuple plumbing only;
  no separate admission, mode/kill/fence, budget, grant, final-claim, or manual-flatten decision
  change was found.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: actual Python 3.11 and exact-head dual-version CI; a fresh full-repository rerun (the preserved final JUnit and raw coverage were parsed instead); broker/network/persistent-database behavior excluded by scope
