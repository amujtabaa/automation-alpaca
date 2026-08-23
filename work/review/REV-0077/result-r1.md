# REV-0077 R1 reconciled result

Date: 2026-08-23

Candidate: `6faf61aa9419234ee953ab881d1bef550699400c`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=11`, `P2=0`)

Three fresh-context read-only reviewers independently verified the candidate identity and reviewed
authority/serialization, persistence/query/DDL, and specification/test exactness without running
SQLite. Duplicate findings are reconciled below; each is accepted.

## P1 findings

1. `09-...R1.md:48-59` — canonical ordering and limit grammar is incomplete: literal type octets,
   composite framing, enum-owner spellings, size boundaries, and witness grammar are not frozen.
2. `09-...R1.md:70,241-263` — envelope/proof/record/API types lack exact fields, signatures, seal
   domains, module/export ownership, outcomes, and exceptions. Exact type alone does not prevent
   `object.__new__` forgery; the envelope needs authenticated issuance binding.
3. `09-...R1.md:84` — current component decoders return authentic execution/protection types; exact
   inert carriers and bytes-only decoders are absent.
4. `09-...R1.md:127-136` — bootstrap imports neither its exact row nor the nested transition proof,
   cursor, and authority-summary bytes; current source has no such inert proof codec.
5. `09-...R1.md:173-180` — deleting the authority descriptor collection loses the current
   descriptor-by-effect map, especially inactive predecessor permit semantics.
6. `09-...R1.md:115-143` — effect/owner/contradiction source ordinals have no authoritative
   derivation, density rule, tie refusal, or reconstruction rule.
7. `09-...R1.md:270-299` — Q1-Q7 are categories rather than literal parameterized SQL with closed
   result schemas, predicates, cardinalities, order, overflow sentinels, absence vectors, and
   per-table plan expectations.
8. `09-...R1.md:278-299` — proposed indexes cannot discover unresolved retired generations from
   application/scope coordinates without history-shaped work; a bounded discovery root is missing.
9. `09-...R1.md:279-282` — Q3 omits CLOSED effects made unresolved by late owners, leaving a
   selected owner without its required effect record.
10. `09-...R1.md:250-263` — payload/head advance does not consume the selection proof in an exact
    predecessor compare-and-swap; the asserted existing primitive does not exist.
11. `09-...R1.md:305-317` — the test contract lacks a finite named mutation/negative-control matrix
    with independent oracles and RED methods.

## Unverified

No SQLite command, query plan, SQLite-bearing test, runtime test, or dynamic index proof ran. R1 is
documentation-only and grants no source or database authority.
