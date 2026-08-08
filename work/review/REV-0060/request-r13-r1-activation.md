# REV-0060 R13-R1 clean records-only activation review request

Status: **INDEPENDENT REVIEW REQUIRED -- RECORDS ONLY**

Review only the exact candidate frozen by
`WO-0151-R13-R1-ACTIVATION-DELTA-MANIFEST.md`. Re-derive the result from the
listed files. Do not rely on conversation history or the author's conclusion.

Write only `result-r13-r1-activation.md` in this directory. Do not edit source,
tests, ADR bodies, work orders, PKL, ledger, ratification, candidate files, or
retained evidence. Do not run application tests, coverage, runtime, database,
SQL/DDL, broker, network, or CI work.

## Required checks

1. Verify the exact branch/base, empty index, every manifest hash, and absence
   of the future reviewer result before writing it.
2. Verify the unchanged R13 contract, clean R13-R1 semantic manifest, and
   independent semantic result match the exact user-ratified SHA-256 values.
3. Confirm the current-record delta records ratification but does not claim
   R13 activation, source/test authority, detector success, coverage success,
   external CI success, WO-0151 closure, or M1 completion.
4. Confirm both original format-blocked R13 manifests remain byte-stable,
   untracked, excluded from the publication set, and are not normalized or
   staged.
5. Confirm the planned first publication commit is records/documentation only,
   contains no `app/`, `tests/`, `.github/`, ADR-body, runtime, database, or
   operational path, and has a clean exact allowlist.
6. Confirm the second commit is limited to exact publication-SHA substitution
   and activation of the ratified five-path R13 source/test scope; source/test
   work remains forbidden before that reconciliation.
7. Confirm WO-0152 remains ACTIVE/PAUSED, the frozen detector stays unchanged
   and unstaged, the unchanged 93% paired gate remains mandatory, and all
   safety exclusions survive.
8. Run ordinary, cached, and untracked-safe whitespace checks. Ordinary Git
   checks do not cover untracked candidate files, so inspect every new clean
   activation artifact directly for trailing whitespace.
9. Run the static work-order scope, disposition, ledger, and PKL validators
   against the documentation-only candidate without staging it.

End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` and exact P0/P1/P2
counts. `ACCEPT` requires P0=0/P1=0/P2=0 and must explicitly state that it
authorizes only the two-step records-only activation sequence, not R13
implementation by itself.
