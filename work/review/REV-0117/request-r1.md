# REV-0117 correction-only exact-head review r1

Return findings only. This is the sole correction round authorized by the original packet. Do not
reopen the whole architecture, edit files, run SQLite, create a database, install DDL, or execute
`tests_gated/**`. Review only the four accepted findings in `result.md` and regressions introduced
by their fixes.

## Exact binding

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Original static candidate: `f6f64207faa3ffa57224a5755536638d981fdfcb`.
- Preserved review-result commit / remediation base:
  `ca6e86cf53ea47f047db22f27a8dc81bd73e1029`.
- Correction candidate: `112d95115f2997ca613238b63eb161a12fbfc791`.
- Candidate tree: `137f7a7bd8d3bc4838cff905754c3394af07fef1`.
- Review correction diff exactly:
  `ca6e86cf53ea47f047db22f27a8dc81bd73e1029..112d95115f2997ca613238b63eb161a12fbfc791`.
- Correction size: 8 files, 312 insertions, 40 deletions.
- `startup.py` blob: `ee168dee89f51253af1930544b3c96b78b8f93ff`.
- `position.py` blob: `feb72be8ac4215d2fa8952109ea38b833cb194df`.
- Cold-recovery test blob: `144eca97f5cc401c827dec3df916dd7809450ce7`.
- Setup-boundary test blob: `79053886fd4a56482d2009c4e2f3d24d919f5b78`.
- Position test blob: `c2c0cc28d4eb0ccbab15d5915c39d2ae8cc93f7e`.
- SQLite-boundary test blob: `f2116d93c3a1bfc8e7d52728e08cd27e90a8dbdc`.
- Held proof remains blob `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Schema remains blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`, 190,705 DDL bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, with the human flag exact
  boolean `False`.

Read `result.md` unchanged, then `disposition.md`, then only the exact correction diff and directly
necessary accepted contract clauses.

## Correction questions

1. **P0-1:** Are all 19 predecessor-to-candidate Python paths Ruff-formatted? Is the original
   unqualified full-range `git diff --check` claim explicitly retracted? Confirm the only remaining
   full-range whitespace diagnostic is the immutable blank EOF in reviewer-owned
   `REV-0116/result.md`, that the full range excluding exactly that file is clean, and that the
   correction diff itself is clean. Do not require an author to rewrite reviewer-owned evidence.
2. **P1-1:** Does every datastore/source capability involved in the finding now have an exact owner
   check immediately before and after it, including post-baseline reread, each individual retained
   source-currentness call, and connection close before any later source call or serving
   publication? Do the three new negative controls actually fail if a later capability leaks?
3. **P1-2:** Do the scope amendment and exact two frozen inventories admit only the new held proof
   while retaining their canaries and central approved connection/setup routes?
4. **P1-3:** Is the first-layer self-authenticity oracle now correct for all three semantic-member
   mutant classes while the separate foreign-proof case still pins the second-layer direct-proof
   mismatch? Confirm no production validation was weakened.
5. Did any correction introduce a concrete safety, data-integrity, scope, or test-control
   regression?

## Fresh evidence at the exact candidate

- Complete ordinary suite: `2259 tests collected`; the exact run reached 100%, exit code 0.
- Focused four-file correction slice: 91 passed, zero failed.
- Ruff check passed the correction paths; Ruff format check passed all 19 Python paths in the full
  WO-0169 range.
- mypy passed all 99 application files.
- Work-order scope check and correction-range `git diff --check` passed.
- Full WO range excluding only `work/review/REV-0116/result.md` passed `git diff --check`; the
  unexcluded command reports exactly that preserved reviewer-owned blank EOF and nothing else.
- DDL/schema/expected digest/human flag and the held-test blob did not change.
- No SQLite/database/DDL/held-suite execution, configured path, migration, runtime composition,
  credentials, broker/network activity, orders, promotion, master merge, or M3 implementation
  occurred.

## Finite output

For a retained finding, give severity, exact `file:line`, concrete failing case, impact, and smallest
root correction. Disprove it before retaining it. Preferences, historical whitespace already
truthfully excluded, and new out-of-model concerns are nonblocking proposals.

End exactly:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1 and explicit closure of P0-1 and P1-1..P1-3. State that no
SQLite/database/held-suite execution occurred.
