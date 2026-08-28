# FINDING — the schema approval gate approves itself

- **Status:** RESOLVED 2026-08-27 by WO-0168d and REV-0108.
- **Severity:** **P2 today, P0 on the day `execution_core` is wired in.** No runtime path exists
  yet, so nothing is currently at risk; the severity is entirely about what happens when one does.
- **Owner:** resolved by the Codex implementation seat under Ameen's bounded authority.
- **Blocks:** wiring `execution_core` persistence into the app, and any beta that installs this
  schema against a real database.

## What

`install_schema(connection, approved_ddl_sha256=...)` (`app/execution_core/persistence/schema.py`)
refuses to install DDL whose SHA-256 does not match the caller's approved value. The intent is a
human gate: someone reads the DDL, transcribes its digest, and the installer refuses anything else.

Every caller but one supplies the digest **computed from the DDL it is approving**:

```python
install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
```

- `tests/execution_core/test_persistence_repository.py:49`
- `tests/execution_core/test_persistence_directness.py:30`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

`schema_ddl_digest()` is `sha256(SCHEMA_DDL)`. Passing it back as the approval token makes the
comparison `sha256(x) == sha256(x)` — a tautology. The check cannot fail, and no human is involved.

`tests/execution_core/test_persistence_schema._GATE_DIGEST` was the sole constant not derived that
way. On 2026-08-24 it was re-pinned to `schema_ddl_digest()` as well (ratified after the fact in
`work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`, Amendment 1). So there is now
**no caller anywhere whose approval token is independent of the artifact it approves.**

## Why it matters

Today: nothing. Verified by inspection —

```text
install_schema callers            tests only -- zero in app/, cockpit/, harness/
SCHEMA_DDL consumers              none outside app/execution_core/persistence/
execution_core wired into the app not at all
```

No running code creates this schema and no database carries it.

On the day that changes, the gate becomes a deploy-time guard on the durable store for orders,
fills, positions, and checkpoints — and it will be a guard that has never once refused anything.
A change to a trigger predicate, a `CHECK`, or a `UNIQUE` would install exactly as readily as a
change to an error-message string. The 2026-08-24 episode is the demonstration: an agent altered
DDL, recomputed the digest, re-pinned it, and every gate passed. That the change was inert was a
property of the change, not of the gate.

This is also why CLAUDE.md classes schema/DB migration as human-gated. The mechanism intended to
implement that classification does not currently do so.

## What resolves it

1. **Separate the approval token from the artifact.** The approved digest must come from
   somewhere a human writes and a machine does not derive — a checked-in constant updated by a
   deliberate commit, an environment value, or a signed manifest. `schema_ddl_digest()` may verify
   what a caller *has*; it must never be what a caller *approves with*.
2. **Forbid the tautology structurally.** A control that refuses any call where
   `approved_ddl_sha256` is the return of `schema_ddl_digest()` in the same expression would have
   caught every site above. Cheap, and it fails loudly.
3. **Decide the test posture deliberately.** Tests legitimately need to install the schema
   constantly; a per-test human transcription is not workable. The honest split is a single
   test-suite constant (what `_GATE_DIGEST` was meant to be) that every test fixture reads, so
   changing the DDL is exactly one deliberate edit — not one automatic recomputation per fixture.
4. **Re-pin `_GATE_DIGEST` by transcription** once (3) is in place, so its value is a human act.

## Evidence

```text
$ grep -rn "install_schema" --include=*.py app/ cockpit/ harness/ audit_harness/
(no matches -- the only definition is app/execution_core/persistence/schema.py)

$ grep -rn "approved_ddl_sha256=schema_ddl_digest()" --include=*.py tests/
tests/execution_core/test_persistence_repository.py:49
tests/execution_core/test_persistence_directness.py:30
tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py:73
```

## Related

- `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md` — Amendment 1 records the
  `_GATE_DIGEST` re-pin and its ratification.
- `work/review/REV-0078/in-process-adversarial-pass-r1.md` — the pass that surfaced this.

## Resolution

Application commit `a5c95ca271c99f79ecfd045468072274107f6ead` moved the still-False human
authorization and expected identity to the application installer, which now refuses before supplied-
connection access. Successor `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, tree
`f5ee0646d74047d373ce6b09728177453bd45c82`, centralizes held-suite opening behind an exact
gate-then-connect helper and closes ordinary public `sqlite3`/`sqlite3.*` direct, alias, submodule,
and wildcard import forms without a general Python analyzer.

Independent REV-0108 returned ACCEPT with P0=0/P1=0/P2=0; result SHA-256 is
`920a93295573159e9b46148f03248cc8fd70c43e7c69533299e05b7b7d70a894`. The DDL remains
178,755 bytes at SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`,
the authorization flag remains False, and no held suite, database, DDL, or migration executed.
