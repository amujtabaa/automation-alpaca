# WO-0168c frozen non-serving checkpoint contract — R14 bounded owner projection

Status: **PREFLIGHT AMENDMENT — DOCUMENTATION ONLY; NO NEW DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R14 incorporates the exact accepted R13 object at
`aa2f0225a0d0d85a41e5cfc5f6c8e530ed7c1a83:work/queue/M2-EXECUTION-2026-08-21/24-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R13.md`,
SHA-256 `f7503f3b9c5cc71b464f97d35f0ba8b325299678f2e353a96b5f9abab597245b`,
including its recursive graph. R14 changes only the owner-projection access rule below.

## Root correction

The projector must accept every authentic bounded state selected by the repository contract; an
empty-map-only implementation is not conforming. Projection remains handwritten and closed. It
may obtain values only through:

1. exact direct owner-map lookups whose keys are derived from the authenticated selection proof;
2. the venue owner's named semantic orders or audit materializers for effects, claims, owners,
   current closure heads, execution bindings, coverage, reconciliation, and execution
   reconciliation; and
3. acquisition's exact direct registry and lineage lookups for selected live/unresolved generation,
   stream, effect, owner, root, and fact identities.

Before touching a named owner sequence, the projector checks its retained count against the frozen
family cap. It then filters to the proof-selected application/profile/scopes and selected durable
identity set. It refuses missing, extra, duplicate, stale, cross-scope, cross-profile, or
non-canonically ordered values. Current-map equality is checked where a materializer originates in
an append-only ledger. Unrelated terminal history never enters bytes.

The projector must not walk `_PersistentKeyMap._root`, inspect radix nodes, use reflection or a
generic serializer, infer a map's contents from a commitment, or weaken the repository selection
proof. Authority manual rows are reachable only through selected effect authorizations; acquisition
descriptors and slots are reachable only through selected effect/scope coordinates; the emergency
grant is the one explicit owner singleton. An authentic retained value that is required by the
closed checkpoint grammar but cannot be reached by these rules is an integrity refusal, not an
empty default.

## Failure-capable controls

Pure tests include at least one authentic nonempty representative for venue, authority, unresolved
acquisition registry, and each lineage family, plus missing/extra/spliced/order/cap mutants. Empty
controls remain but cannot stand in for nonempty coverage. Static controls reject generic radix
traversal and reflection in the projector.

R14 changes no wire tag, member count, commitment domain, SQL, DDL byte, transaction rule, serving
authority, public export, or human-gated surface. REV-0077 must return exact R14 `ACCEPT` with
`P0=0/P1=0` before the implementation relies on this clarified access rule.
