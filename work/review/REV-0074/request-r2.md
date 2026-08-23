# REV-0074 R2 — fresh alternate-authority preflight review

Independent findings-only review. Write only `result-r2.md`; do not edit any other file.

Verify exact identities:

- accepted authority base: `0777fab62598f85ce189f40eb1a69319791282c2`, tree
  `1db6fe831fc7d7785d032c224072b131cd5643e9`;
- R1 result publication: `8157978cb1ccec39651c6a0319fa970da7e14b33`;
- exact R2 remediation candidate: `23e43a6a371e600dbbe490a0390ae265ea6e3a84`;
- candidate tree: `58c16250a28ffc7f9a5a48fd1a047d7fa1edc173`;
- remediation range: `8157978cb1ccec39651c6a0319fa970da7e14b33..23e43a6a371e600dbbe490a0390ae265ea6e3a84`.

Read `AGENTS.md`, `CLAUDE.md` safety core, `request-r1.md`, immutable `result-r1.md`,
`disposition-r1.md`, WO-0168a, and the complete frozen contract. Reproduce R1's query/grant
counterexamples and try adjacent alternate-key aliases in venue, manual flatten, facts, coverage,
claims, effects, acquisition routes, and market identity.

Required decision: does the amended contract now freeze exact canonical key bytes/domains,
uniqueness/immutability, record/repository lookup, checkpoint hydration, owner-visible match proof,
and the correct conditional insertion point, without consuming an identity on refusal or inventing
generic semantics? Also recheck the original finite-matrix/state/path requirement and DDL/source
stop boundaries. Try to identify two materially different authority behaviors still permitted.

Documentation/static read-only review only: no SQLite, source edit, configured DB, network, broker,
credentials, orders, migration, or implementation. End `result-r2.md` with verdict and P0/P1/P2
counts. Source activation requires P0=0/P1=0 for this exact candidate.
