# REV-0074 R10 — complete radix nonmembership amendment review result

## P1 — Prefix negative control can pass without enforcing terminal nonmembership

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:715`
- **Mechanism:** A longer-key-only map proves the prefix is absent even if the verifier omits the required terminal `has_value=False` check. A mutated terminal witness may still be refused solely because its node commitment no longer matches, not because the terminal-membership rule is enforced.
- **Impact:** The required negative control does not necessarily fail when the terminal-prefix nonmembership condition is weakened, so the precise R9b omission can regress undetected.
- **Smallest complete root correction:** Require a second authenticated control with both the prefix key and a descendant retained: submitting that valid `has_value=True` prefix terminal as a nonmembership witness must be refused specifically by the terminal-membership rule. Retain the longer-key-only prefix-absence case.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Unverified: No source/tests, SQLite/DDL, runtime composition, external activity, or test execution was performed, per the review boundary.
