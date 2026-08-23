# REV-0075 R12 — fixture-capability root-correction review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition, credentials,
network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R11-reviewed candidate: `5289f3a55544141763177b17c92bf1b88e8155c2`, tree
  `bb90cfbcbecccd9d14d5c847341eb85ad0de2d29`
- Exact corrective candidate: `a7fb8e0aea4dfde96bb180be3382d81fac0e46d3`, tree
  `fff0dd0c544436acf3636a39928610ba7fe4da18`
- Review diff: `5289f3a55544141763177b17c92bf1b88e8155c2..a7fb8e0aea4dfde96bb180be3382d81fac0e46d3`

`result-r11.md` is findings input only. This is a fresh acceptance review of the correction, not a
request to trust the earlier result or author claim.

## Required read order

1. `AGENTS.md`, `CLAUDE.md` safety core, active WO-0168a, frozen contract R13/R13-R1,
   `request-r11.md`, and `result-r11.md`.
2. This request, exact diff, and
   `tests/execution_core/test_persistence_write_capability.py` at the corrective candidate.
3. Reproduce only the named pure test command if useful. SQLite activity is forbidden even for
   temporary files.

## Required adversarial checks

1. Confirm the fixture AST control detects a direct repository alias, callable alias, imported
   mutator alias, and a dynamic `getattr(repository, "store_*")` route when any uses no capability,
   an arbitrary object, or a capability issued for a different syntactic connection.
2. Confirm that the only accepted direct token expression is the named setup wrapper bound to the
   same connection expression, and that the one allowed higher-order fixture writer has an exact
   issuer-to-`operation` shape.
3. Attack the alias resolver and helper-shape test for a false-green route, including alias chains,
   forged tokens, default arguments, proxy values, and an unrelated callable. Distinguish a concrete
   bypass from a theoretical unexecuted construction.
4. Assess whether the test-only AST surface is proportionate to its finite fixture grammar; identify
   needless abstraction or a false claim of runtime enforcement if present.
5. Confirm the correction does not alter runtime capability issuance, DDL bytes, SQLite execution,
   or any safety boundary.

## Author evidence to reproduce or challenge

```text
.\\.venv\\Scripts\\python.exe -m pytest -q \\
  tests\\execution_core\\test_persistence_operations.py \\
  tests\\execution_core\\test_persistence_checkpoint_codec.py \\
  tests\\execution_core\\test_persistence_input_receipt.py \\
  tests\\execution_core\\test_persistence_write_capability.py
```

The command passed (78 tests). Ruff check/format and `git diff --check` passed. No SQLite-bearing
test has run.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, smallest complete root correction, and
evidence tag. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`) and counts. State
unverified checks. This review does not close WO-0168a or authorize DDL execution, SQLite activity,
runtime composition, external I/O, promotion, merge, or release.
