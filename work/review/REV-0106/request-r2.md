---
type: Review Request
rev_id: REV-0106
title: Round two — installer-owned authorization and boundary remediations
status: AWAITING_REVIEW
targets: [WO-0168d, ADR-026, REV-0106-F1, REV-0106-F2, REV-0106-F3]
human_gated_surfaces: [application-side schema installer authorization]
commit_range: f20eddd4d060f7506bbbe563761bbf964731275f..a5c95ca271c99f79ecfd045468072274107f6ead
created: 2026-08-27
---

# REV-0106 round two — fresh exact-head remediation review

## Role and immutable ownership

You are a new independent findings-only seat. Do not inherit the author's reasoning or the first
reviewer's conclusions; re-derive the mechanisms. Follow `AGENTS.md` and
`.ai-os/core/15_CROSS_MODEL_REVIEW.md`. Do not edit implementation, governance, `request.md`,
`request-r2.md`, or the prior reviewer-owned `result.md`. Create only
`work/review/REV-0106/result-r2.md`; do not commit or push.

## Exact identities

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Original review base: `d0887585fdb479e83a74909e6d14f3375e0a0850`
- Original candidate: `f20eddd4d060f7506bbbe563761bbf964731275f`
- Round-two remediation candidate: `a5c95ca271c99f79ecfd045468072274107f6ead`
- Round-two candidate tree: `fdbdbe0934a08e97d542945d28b937bdc67708ea`
- Remediation range: `f20eddd4d060f7506bbbe563761bbf964731275f..a5c95ca271c99f79ecfd045468072274107f6ead`
- Request-document commits after `a5c95ca` are documentation-only; the candidate above remains
  authoritative.

Verify these before reviewing. Stop on an identity mismatch.

## Required read order

1. `AGENTS.md` and `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.
2. `work/review/REV-0106/result.md` and `disposition.md`.
3. `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`.
4. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
5. Amendment 9 in
   `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.
6. The exact remediation diff above, especially:
   `app/execution_core/persistence/schema.py`,
   `tests/execution_core/approved_schema_digest.py`, and
   `tests/execution_core/test_sqlite_boundary.py`.

## Human authority and exclusions

Ameen authorized only the bounded F1 root remediation: the application-side installer must enforce
the human authorization flag before connection access, with supporting tests/governance. No DDL-
byte change, held-suite execution, database creation, migration, later work-order implementation,
unlock, or merge is authorized. The flag must remain `False` in this candidate.

## Findings to reconcile

Round one returned `BLOCK`, P0=1/P1=2/P2=0:

- **F1/P0:** known matching digest could reach connection access because `install_schema` did not
  consume the authorization fact.
- **F2/P1:** direct-connection AST detection missed ordinary SQLite import aliases.
- **F3/P1:** whole-file lexical exemptions admitted added production token occurrences.

The author claims F2/F3 are resolved at `d22c236` and F1 at `a5c95ca`. Try to disprove each.

## Required lenses and probes

1. **Installer-owned authorization:** with the source flag False, an ordinary direct public
   `install_schema` call supplied the known expected digest must fail before any method/property of
   a no-I/O stand-in connection is touched. Verify source order is actual digest, application-owned
   authorization/expected-identity check, caller-digest check, then connection inspection.
2. **Single authority fact:** the pre-open fixture accessor must read the same application-owned
   expected identity and flag; it must not maintain a second independently drifting authorization
   flag. Expected identity alone must remain insufficient.
3. **Unlock auditability:** the later source-recorded unlock must still be one flag-only change from
   the exact accepted parent. The current candidate must not be unlocked.
4. **DDL immutability:** statically prove the DDL byte count and SHA below without importing or
   executing the module; check that the DDL literal is byte-identical to the original candidate.
5. **F2 regression:** test ordinary `import sqlite3 as db`, `from sqlite3 import connect`, and
   ordinary aliased gate-first forms. Avoid reflection/deliberate dynamic evasion outside ADR-026.
6. **F3 regression:** an added token occurrence under an already justified production path must
   fail; exact manifests must not hide a new occurrence.
7. **API/governance regression:** check the installer signature and frozen `__all__` remain
   compatible, the schema module import remains inert, scope is exact, and ADR/gate/work-order text
   does not weaken the separate human execution gate.

Any evidence-backed contract, scope, remediation-regression, safety, data-integrity, or governance
finding remains allowed. Core 20 cannot constrain findings about its own text. Deliberate mutation
of the in-process flag or hostile host ownership is an out-of-model threat proposal unless it also
demonstrates an in-scope defect.

## Command safety boundary

Permitted: read-only source/Git inspection; static AST/hash checks; no-I/O stand-ins; focused
`tests/execution_core/test_sqlite_boundary.py` and
`test_persistence_write_capability.py`; all ordinary `tests/execution_core` tests if desired; Ruff,
mypy, lint-imports, and non-database governance checks.

Forbidden: importing/collecting/running any `tests_gated` test; executing or installing DDL;
creating a file or in-memory database; running the database-creating conformance oracle or broader
repository tests; setting or monkeypatching the authorization flag True; migrations; credentials;
network/broker calls; orders; promotion; merge; force-push; or edits outside `result-r2.md`.

## Frozen identities and author evidence

- Candidate schema Git blob: `ef332a0b97d28e0535ac53ea0e4d4e091991abad`
- `SCHEMA_DDL`: `178755` UTF-8 bytes
- `SCHEMA_DDL` SHA-256 and expected identity:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- Authorization flag, statically extracted: `False`
- Installed catalog digest remains:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4/R5 SQL-manifest identities remain
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39` /
  `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`.

File SHA-256 values:

- schema.py: `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
- approved_schema_digest.py:
  `68338cde85bd0467728f6cb318bd083c34c0a131459534a585c88947edff0d20`
- test_sqlite_boundary.py:
  `211b44139b6ba445abfa8602d0bbeaa6d826826c9ea944b885d89ce9190e6b7a`
- ADR-026: `4db26a999efd4c2f751c7c6a15b25423e94ae61df034cec15fa01c3603109ea0`
- WO-0168d: `624ad8656923c2b7cab09ebf1ab3ee5eb426fdd8be68d1e67e408b631b589f73`

Author evidence at `a5c95ca`:

- RED before source fix: focused collection failed because the application module did not own the
  expected identity.
- Focused GREEN: `18 passed` with no SQLite/DDL/database.
- Complete ordinary `tests/execution_core`: exit 0, 100%, no gated collection.
- Ruff check/format: all 11 changed Python paths clean.
- mypy: success, 95 app source files.
- lint-imports: 6 contracts kept, 0 broken.
- AI-OS install/version (`v0.9.2`)/ledger/PKL/disposition/scope: pass.
- Boundary plus gate: 385 nonblank/non-comment SLOC, below 400.
- Full repository pytest and conformance oracle: `NOT_RUN` because Ameen's remediation authority
  forbids database creation; both create ordinary SQLite files. The original candidate had two
  independent full ordinary-suite passes before this isolated three-file remediation.

Added/amended INV entries: none; fresh-probe obligation: N/A.

## Finite stop and response contract

This is the one permitted remediation review round. The cap never forces acceptance: any valid
open P0/P1 remains an exact blocker for re-diagnosis or human disposition. `ACCEPT-WITH-CHANGES`
may close only with zero open P0/P1; P2 or explicit out-of-model proposals may remain.

Create `result-r2.md` with verified identities, verdict, findings and P0/P1/P2 counts, separate
threat proposals, commands/not-verified, and a disproof pass for F1/F2/F3 plus remediation
regressions. Use `[DONE] STATUS: VERIFIED` only if the review work is complete.
