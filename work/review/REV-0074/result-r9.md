# REV-0074 R9 — sound authenticated-proof amendment review result

## P1 — Review request pins a nonexistent R9 parent

- **Location:** `work/review/REV-0074/request-r9.md:14,17`
- **Mechanism:** The specified parent `f66383c5a0b8e7482eb3a929fe315e1d9c1d0e4d` does not exist. The candidate's actual parent is `f66383c561b6d09e0c85d516c627874a97a596ee`.
- **Impact:** The mandated amendment diff and its `git diff --check` cannot be reproduced as requested, weakening exact-range review provenance.
- **Smallest complete root correction:** Replace both parent/range references with the candidate's actual parent, then rerun the exact-range static review.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Unverified: The request-pinned diff/check could not run; no runtime, SQLite/DDL, composition, or tests were run as required.
