# REV-0099 result — WO-0168c exact finite-provenance review

Date: 2026-08-25
Review target: `ce9c2b482605ff25144b193ab6783960530922c6`
Target tree: `43e7ff04b10e6025ad7b53e1c2d5f82123a88b20`
Review seats: two fresh-context GPT-5.6 Sol Max reviewers; findings reconciled by the Codex orchestrator without changing the frozen target.

## Findings

### P0-1 — governed module ownership depends on unrelated gate syntax

`tests/execution_core/test_persistence_write_capability.py:2576`

The single-file audit owns a governed module value only while
`has_gate_surface` is true. A helper with no local gate spelling can therefore
pass `schema`, `builtins`, or `sys` through an arbitrary call or container, or
reach module-class mutation, without a violation. The safety property belongs
to the value's provenance, not to whether the same file also imports the gate.
Resolve by enforcing finite governed-value ownership in every scanned file and
retaining accepted direct read-only operations explicitly.

### P0-2 — import identity is not closed over package and relative forms

`tests/execution_core/test_persistence_write_capability.py:1170`
`tests/execution_core/test_persistence_write_capability.py:3586`

The scanners key important imports by one absolute spelling and resolve dynamic
imports from literal arguments only. Equivalent wildcard, relative, package-
qualified, statically aliased, and `import_module(..., package=...)` routes can
therefore lose schema/approval/helper identity. Resolve with one package-aware
absolute-name resolver, lexical static-string resolution, and explicit refusal
of noncanonical approval and schema wildcard identities.

### P0-3 — a protected helper module can escape before member recovery

`tests/execution_core/test_persistence_write_capability.py:3441`
`tests/execution_core/test_persistence_write_capability.py:3671`

The topology proof follows selected protected members but does not own the
helper module value itself. Container relays, ordinary-call relays, dynamic
`__getattribute__`/`attrgetter`, and `ModuleType` descriptor recovery can move
or recover the capability without producing a protected kind. Resolve by
rejecting a protected helper module outside a finite set of modeled reflection
operations and by tracking module-type maps, getters, and mutators as one
descriptor family.

### P0-4 — dynamic getters discard governed provenance

`tests/execution_core/test_persistence_write_capability.py:2199`

A non-static member passed to `getattr(sys, name)` or
`getattr(builtins, name)` becomes an empty/unknown ordinary result. The returned
module registry or builtins map can then be mutated without attribution.
Resolve by carrying a fail-closed governed-unknown kind through member, map,
call, and escape analysis.

### P1-1 — flow-insensitive binding union rejects a definite ordinary rebind

`tests/execution_core/test_persistence_write_capability.py:3572`

Every binding ever seen for a name is unioned. A protected import remains
attributed after an unconditional same-scope ordinary rebind, creating a false
positive and encouraging filename waivers. Resolve with source-ordered definite
binding replacement, conservative conditional unions, and deferred-function
parent-state handling.

### P2-1 — review packet misstates approval-file provenance

`work/review/REV-0099/request.md:30`

The request says `approved_schema_digest.py` was first introduced after
baseline `b8709110`; the file already existed there as blob
`bd4f4f22b0de7db660a8770356205c8f6f1511cd` and was modified to blob
`8306ea294075fe76b314724ad6c49e514621f7b1` by the reviewed boundary. Correct
the next packet; do not rewrite this frozen request.

## Evidence and limits

- One independent seat reproduced the recorded 279 held-safe pure/static tests.
- The second seat's CPython 3.14 reproduction was blocked by a reviewer
  temporary-directory permission error; this is environment evidence, not a
  candidate failure.
- Both seats independently returned `BLOCK` on the exact target.
- No reviewer imported SQLite, opened a connection, installed DDL, or ran a
  held suite.

## Verdict

`BLOCK` — P0=4, P1=1, P2=1.

The candidate cannot enter the changed-DDL HUMAN-GATE until a fresh exact-head
review verifies the root corrections with P0=0 and P1=0.
