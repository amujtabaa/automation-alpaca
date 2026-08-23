# REV-0074 R9 rerun — sound authenticated-proof amendment review result

## P1 — Terminal-prefix nonmembership is unspecified

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:673-681`
- **Mechanism:** R9 defines nonmembership only as a terminal child tuple omitting the requested next byte. When the queried key is fully consumed at a node with `has_value=False` but that node has children (the queried key is a prefix of another key), there is no next byte. Although `has_value` is carried, the verifier is not required to handle this key-exhaustion case explicitly.
- **Impact:** The proof contract does not completely establish nonmembership for every key accepted by the existing generic radix map, leaving an undefined direct-proof route for an absent exact key at a populated prefix node.
- **Smallest complete root correction:** Specify two nonmembership cases: before key exhaustion, require the complete tuple to omit the queried next-byte label; after key exhaustion, require `has_value=False`. Require a negative-control test for the prefix-key case.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Unverified: Runtime composition, SQLite/DDL, implementation/tests, and broader suites were not run per the review boundary.
