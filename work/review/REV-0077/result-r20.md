# REV-0077 R20 exact-head preflight review

Reviewed exact commit `a6bba249912d81dac0862030e294a2970a76ecf2`, tree
`72c0fa4a576afa1f9e70ca544e89f6c67940282f`, and R20 SHA-256
`4bee617d48ee0f0dbcfc6b9109b6a4aaf73d9ce6c335573e7914793d83e6a40e`.

No material P0 or P1 findings.

R20 closes the three identified implementability gaps exactly. Venue wire integrity and source
projection now use distinct, literal domains over the same canonical row; `VenueRef` consumes the
wire commitment while the owner preimage separately binds the source commitment and repository
selection proof. Authority rows retain semantic-key ordering rather than inheriting repository
proof-family order. Terminal manual effect IDs are bounded, canonical payload-owned semantics
reached through the current scope-to-manual indexes; only IDs also present in the selected effect
family require selected-record agreement, while omitted terminal history cannot mint a current
venue row or serving authority.

The retained direct-key source surfaces can implement those rules without a new query, SQL
predicate, row family, DDL byte, public export, serving type, or serving authority. The full P0/P1
disproof pass found no remaining circular commitment, authority-order conflict, unbounded
enumeration requirement, selected/direct-proof weakening, or human-gated database expansion.

Verdict: ACCEPT
P0: 0
P1: 0
Unverified: No SQLite, database, DDL, schema-install, runtime-composition, serving-path, or
executable test was run. Review was static against AGENTS.md, active WO-0168c, R17-R20,
`result-r19.md`, and current source solely as implementability evidence. Pre-existing worktree
changes were not treated as part of the exact committed review target.
