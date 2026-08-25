# REV-0096 result — WO-0168c exact sensitive-value ownership review

Date: 2026-08-24
Candidate reviewed: `d00903f9321b124723f6dad3d74f68b3214eb240`
Candidate tree reviewed: `be49d44033451513949ac338e7f502fa9ac2f135`
Review branch: `codex/m2-wo0168c-remediation-r1`

## Recording note

This artifact faithfully consolidates the two independent fresh-context
`gpt-5.6-sol` review seats' returned findings. Neither review seat edited the
repository, opened SQLite, or ran database-bearing tests. Their review messages
are the source record; this artifact preserves the disposition without
downgrading it.

## Verdict

**BLOCK**

Counts after deduplicating overlapping findings: **P0=6, P1=0, P2=1**.

## Findings

### P0-1 — sensitive registry values and mutation capabilities can escape

`tests/execution_core/test_persistence_write_capability.py` allowed
`sys.modules` to be returned from a helper or passed as an argument, and allowed
known mutation capabilities to be stored in object attributes, defaults, and
unpacked containers. A later consumer can mutate the approval-module registry
while the source audit remains green.

Evidence: reproduced-static by an independent review seat.

Required root resolution: define the finite allowed uses of sensitive mappings
and known mutator capabilities; reject unsupported argument, return, attribute,
container, default, and destructuring escapes rather than trying to enumerate
their eventual mutations.

### P0-2 — dynamic sys namespace-map writes are not owned by the map value

Dynamic-key mutations through `sys.__dict__`/`vars(sys)` were accepted, including
stores, deletes, nested writes, and `|=`. A dynamic key resolving to `modules`
can replace or corrupt the route to the approval module.

Evidence: reproduced-static by an independent review seat.

Required root resolution: reject writes/deletes/augmented writes by the proven
sensitive map itself and reject dynamic lookup that can expose its mutable
contents; do not depend on resolving the eventual key spelling.

### P0-3 — conditional aliases discard a known mutator provenance

When a known mapping mutator was first bound and then conditionally rebound,
the analyzer selected the later ordinary binding and accepted a call that can
still invoke the known mutator on `sys.modules`.

Evidence: reproduced-static by an independent review seat.

Required root resolution: retain conservative capability provenance across
reachable conditional bindings or reject the unsupported alias escape at its
first use.

### P0-4 — later module/class shadows incorrectly suppress builtin `dict`

An earlier `dict.__setitem__(sys.modules, ...)` can execute with builtin `dict`
before a later module or class binding of `dict` exists at runtime. The analyzer
treated that future ordinary binding as already active and missed the registry
mutation.

Evidence: reproduced-static by an independent review seat.

Required root resolution: preserve Python timing: function-local bindings are
whole-body lexical, while module/class bodies use bindings available at the
executed source position. Where builtin capability remains possible, fail
closed.

### P0-5 — recovered approval accessors escape the canonical-call rule

The no-escape rule applied only to a direct name. Module- or registry-recovered
approval accessors could be passed to `object.__setattr__` or used to recover
`__globals__`, enabling behavior or token mutation.

Evidence: reproduced-static by an independent review seat.

Required root resolution: apply the direct-call-only rule to every expression
whose provenance is the approval accessor, not merely to `ast.Name` nodes.

### P0-6 — descriptor and namespace routes recover known mapping mutators

Known `dict`/`operator` mutation capabilities could be recovered through
`__call__`, `__get__`, `vars(dict)`, and `vars(operator)` before mutating the
registry.

Evidence: reproduced-static by an independent review seat.

Required root resolution: retain proven capability through the recognized
namespace/member routes and reject a mutator capability unless it is its direct,
supported call form.

### P2-1 — the request misidentified its one-file range

`4dd24b5..d00903f` included the active work-order and REV-0095 request
documentation paths. The direct parent range
`556511200eac7c74895d8446d1676e0457c89efc..d00903f9321b124723f6dad3d74f68b3214eb240`
was the actual one-file code range.

Evidence: reproduced-static by both independent review seats.

Required root resolution: use the exact parent code range in the successor
packet or enumerate every path in any broader range.

## Independently checked boundary facts

- The DDL remained locked; the review performed no SQLite/database activity.
- The review seats reported `SCHEMA_DDL` as unchanged at SHA-256
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`,
  178755 UTF-8 bytes, with approval literal `None`.
- No reviewer accessed credentials, network, broker, order, promotion, or merge
  surfaces.

## Unverified by the review seats

The review seats did not independently complete the full author test matrix,
Ruff/mypy checks, catalog/manifest recomputation, or any held SQLite/fresh-file
test. Those activities remain intentionally NOT_RUN.
