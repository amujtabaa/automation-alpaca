# REV-0095 result — WO-0168c registry-ownership review

Date: 2026-08-24
Candidate reviewed: `4dd24b5e3235cfff160923c31eee5922c6ed95fe`
Candidate tree reviewed: `6311752ec66cea80a0331ceb6918a0dc1172c584`
Review branch: `codex/m2-wo0168c-remediation-r1`

## Recording note

This result faithfully consolidates the two independent `gpt-5.6-sol` review
seats' returned findings without downgrading them. The reviewers did not modify
the repository. Their review messages are the source record; this artifact
preserves the exact review disposition for the work-order chain.

## Verdict

**BLOCK**

Counts after deduplicating overlapping findings: **P0=3, P1=2, P2=1**.

## Findings

### P0-1 — lexically proven registry mutations remain outside the guard

`tests/execution_core/test_persistence_write_capability.py` did not reject
known mutation forms whose receiver is proven to be `sys.modules`: `operator`
`setitem`/`delitem`/`ior`, escaped `dict.__setitem__`, `dict.__init__`, and
`|=` through a direct or aliased registry value. These routes can replace or
remove the human-controlled approval module while the source audit is green.

Evidence: reproduced-static by both independent review seats.

Required root resolution: own mutation by the proven registry value across the
finite set of known builtin-dict/operator mutation primitives, their lexical
aliases, direct stores/deletes, and augmented assignment; retain local-shadow
precision.

### P0-2 — the distinct sys namespace map is mutable around `modules`

The candidate correctly kept `sys.__dict__`/`vars(sys)` distinct from
`sys.modules` for reads, but did not refuse mutation through that namespace:
direct/imported namespace `update` and `vars(sys).pop('modules')` passed.
Those forms can replace or remove the route used to reach the approval module.

Evidence: reproduced-static by one independent review seat.

Required root resolution: give the proven sys namespace map its own finite
mutation ownership rule, without conflating ordinary sys attributes with the
registry.

### P0-3 — the canonical approval accessor can be rewritten in place

The direct canonical import remained nominally intact after assigning a forged
function's `__code__` to `require_approved_ddl_execution`; the source audit
returned no violation. This defeats the human-gated token while preserving the
expected spelling.

Evidence: reproduced-static by both independent review seats.

Required root resolution: treat the lexically proven approval accessor as an
immutable, unescapable capability; reject direct attribute writes/deletes,
known mutator/reflection paths, and behavior-changing escape routes.

### P1-1 — a shadowed local `dict` is still treated as builtin `dict`

The `dict.get`/`dict.__getitem__` static lookup branch checked the spelling of
the name rather than its resolved lexical capability. A function parameter
named `dict` could therefore be treated as the builtin map primitive.

Evidence: reproduced-static by one independent review seat.

Required root resolution: require the resolved `builtin-dict` capability for
that special lookup grammar and prove local-shadow controls remain accepted.

### P1-2 — harmless registry reads are inconsistent by spelling

In otherwise valid gate-first source, direct `sys.modules.get('json')` was
rejected as an approval-registry route while the equivalent imported
`modules.get('json')` passed. This contradicts the declared read-only registry
contract and creates an avoidable false positive.

Evidence: reproduced-static by one independent review seat.

Required root resolution: permit proven read-only registry lookup, propagate
known module provenance from its result, and reject mutation/escape at the
actual sensitive value.

### P2-1 — REV-0095's documented range was not a one-file range

`970bf511..4dd24b5` included the intervening active-work-order and REV-0094
documentation changes, although the request described it as limited to the
source test file. The candidate tip itself was one-file source-only.

Evidence: reproduced-static by one independent review seat.

Required root resolution: name all paths in a full range or name the exact
one-file source range separately in the successor packet.

## Independently checked boundary facts

- `SCHEMA_DDL` was reported unchanged at SHA-256
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`,
  178755 UTF-8 bytes.
- The approval literal remained `None`.
- No reviewer opened SQLite, created a database, accessed credentials/network,
  broker, or order paths.

## Unverified by the review seats

The reviewers did not independently complete the full author test matrix,
Ruff, mypy, catalog/manifest recomputation, or any SQLite/fresh-file gate.
Those SQLite activities remain intentionally NOT_RUN.
