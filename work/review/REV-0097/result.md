# REV-0097 result — WO-0168c final static approval-boundary review

Date: 2026-08-24
Candidate reviewed: `b8709110d7e634b92d1af6262c28332fc25b5b93`
Candidate tree reviewed: `a0092cac597b1d10bbdeab94e9a23fe7b1b31d7a`
Review branch: `codex/m2-wo0168c-remediation-r1`

## Recording note

This artifact faithfully consolidates two independent fresh-context
`gpt-5.6-sol` review seats. Neither seat edited the repository, opened SQLite,
created a database, executed a held SQLite-bearing test, or accessed network,
credential, broker, or order paths.

## Verdict

**BLOCK**

Counts after deduplicating the returned findings: **P0=5, P1=1, P2=0**.

## Findings

### P0-1 — reflective recovery of `sys.modules` escapes the finite model

`tests/execution_core/test_persistence_write_capability.py` did not classify
`sys.__getattribute__('modules')` or
`object.__getattribute__(sys, 'modules')` as the governed module registry.
The recovered mapping can replace the approval module before a later source
uses it.

Evidence: reproduced-static by an independent review seat.

Required root resolution: preserve/refuse capability provenance across the
recognized direct reflection routes; do not treat the recovered mapping as an
ordinary value.

### P0-2 — the schema installer module can be replaced before canonical use

The candidate accepted `setattr(schema, 'install_schema', replacement)`, its
bound `__setattr__` form, and an `object.__setattr__` form. A subsequent
canonical-looking `schema.install_schema` spelling can therefore call forged
code.

Evidence: reproduced-static by an independent review seat.

Required root resolution: make the schema module and installer immutable within
the finite governed capability grammar, including recognized mutator and
reflection forms.

### P0-3 — builtins import machinery can be mutated or escaped

`builtins.__import__`, the builtins namespace map, and an alias of the importer
were not uniformly owned. A source can replace import machinery and then make a
canonical import spelling resolve to forged code.

Evidence: reproduced-static by an independent review seat.

Required root resolution: keep the importer and builtins namespace under the
same direct-call-only/mutation-refusal rule as other governed capabilities.

### P0-4 — sensitive capabilities can be laundered through another source file

A helper can import the canonical installer and approval accessor, then a
consumer can import them from that helper. The candidate analyzes each file in
isolation, so the consumer appears ordinary even though it receives the real
privileged values.

Evidence: reproduced-static by an independent review seat.

Required root resolution: add a repository-level provenance topology check (or
an equivalently complete no-re-export rule) for the finite sensitive surface.

### P0-5 — function-global capability lookup used source-body time

For a function defined before a module-level governed import, the candidate
resolved the function body's global lookup as though the later import did not
exist. If the function runs after that import, the actual runtime lookup can
acquire SQLite, registry, or approval capability state missed by the audit.

Evidence: reproduced-static by an independent review seat.

Required root resolution: conservatively model later governed module bindings
for function-global/free-name lookup, while retaining Python's lexical handling
of function-local bindings.

### P1-1 — the private approval validator is not behaviorally pinned

The public accessor was checked only for delegating to a named private helper.
Changing the helper's body could weaken validation while leaving the public
accessor's structure unchanged.

Evidence: reasoned-static by an independent review seat.

Required root resolution: eliminate the independently callable validator or
structurally pin the full validation behavior, not only the delegation shape.

## Independently checked boundary facts

- The DDL remained source-static and the approval literal remained `None`.
- No review seat claimed a changed-DDL installation, SQLite test, database
  creation, or human-gate release.

## Unverified by the review seats

The reviewers did not independently complete the author test matrix, style/type
checks, or any held SQLite/fresh-file command.
