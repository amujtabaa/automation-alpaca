# REV-0098 result — WO-0168c exact root-cause static-boundary review

Date: 2026-08-25
Candidate reviewed: `ec1fbf8f94a2e10f08a33ef5d3476f336d37ce13`
Candidate tree reviewed: `7974e3718ab1977d7eb640eea75f28e1f908607c`
Review branch: `codex/m2-wo0168c-remediation-r1`

## Recording note

This artifact consolidates two independent fresh-context `gpt-5.6-sol`
review seats. Neither seat edited implementation, opened SQLite, created a
database, executed a held SQLite-bearing test, or accessed network,
credential, broker, or order paths.

## Verdict

**BLOCK**

Counts after deduplicating the returned findings: **P0=5, P1=2, P2=0**.

## Findings

### P0-1 — governed module values can leave the owned operation boundary

`tests/execution_core/test_persistence_write_capability.py:1077`

The finite grammar accepted the schema, builtins, or sys module value when it
was passed to an arbitrary local function, retained in a container, mutated
through `vars(schema).update(...)`, or recovered through
`sys.__class__.__getattribute__(...)`. Those values could subsequently alter
the installer, import machinery, or module registry outside the operation the
audit believed it owned.

Evidence: reproduced-static by independent review seats.

Required root resolution: make governed-module ownership value-centered for
every modeled expression and allow only operations the grammar itself proves.

### P0-2 — repository helper provenance is lost through canonical primitives

`tests/execution_core/test_persistence_write_capability.py:2966`

The topology pass missed imported or aliased `importlib.import_module`,
`operator.getitem(vars(helper), ...)`, `builtins.getattr`, and a helper-module
relay alias. It could therefore accept a consumer that recovered the real
installer or approval accessor from a local helper.

Evidence: reproduced-static by independent review seats.

Required root resolution: use one lexical provenance model for canonical
import, lookup, namespace, mapping, and relay forms instead of matching only
their surface spellings.

### P0-3 — the source inventory omits nested Python files

`tests/execution_core/test_persistence_write_capability.py:850`

The claimed repository-wide source proof used non-recursive `glob("*.py")`.
A future nested module under either execution-core tree could contain a
connection or capability route while remaining outside the audit.

Evidence: reproduced-static by independent review seats.

Required root resolution: derive one recursive, deterministic inventory for
both `app/execution_core/**` and `tests/execution_core/**`, with a control that
fails if nested files are omitted.

### P0-4 — the claimed whole-source proof was red at the frozen candidate

`tests/execution_core/test_protection.py:2705`

The audit classified an existing dynamic builtins inspection helper as a gate
violation even though that source owns no SQLite or approval surface. Thus the
author's source-wide GREEN claim was not reproducible at the exact candidate.

Evidence: reproduced-live by independent review seats.

Required root resolution: distinguish ordinary introspection from governed
capability recovery by resolved provenance and local gate ownership.

### P0-5 — the new helper proof had a false exact-count expectation

`tests/execution_core/test_persistence_write_capability.py:3432`

The reviewer control expected exactly two findings but the candidate emitted
five for the same synthetic helper graph. The proof asserted incidental
diagnostic multiplicity rather than each required refusal behavior, so its
reported completion evidence was false and brittle.

Evidence: reproduced-live by an independent review seat.

Required root resolution: assert each required behavior independently and do
not freeze duplicate diagnostic counts as contract semantics.

### P1-1 — the exact approval module still permits builtin rebinding

`tests/execution_core/test_persistence_write_capability.py:169`

The structural checker pinned the accessor body but allowed extra module-level
executable statements. Rebinding `str`, `type`, `len`, or `any` could change the
meaning of its apparently exact validation.

Evidence: reproduced-static by an independent review seat.

Required root resolution: pin the complete executable module shape while
retaining the one authorized future change from literal `None` to one literal
lowercase SHA-256 string.

### P1-2 — spelling-based topology rules reject ordinary local behavior

`tests/execution_core/test_persistence_write_capability.py:2966`

A parameter shadowing a helper name and custom objects exposing methods named
`getattr` or `import_module` could be classified as privileged operations.
This makes the finite check fragile and encourages broad exceptions.

Evidence: reproduced-static by independent review seats.

Required root resolution: resolve lexical bindings first; only a binding
proven to be a canonical primitive may carry privileged provenance.

## Independently checked boundary facts

- The DDL remained source-static and the approval literal remained `None`.
- No changed-DDL installation, SQLite test, database creation, or human-gate
  release was claimed by either reviewer.

## Unverified by the review seats

The reviewers did not independently complete the full author matrix, style,
type, import-architecture, or governance checks.
