# REV-0077 R0 author disposition

Date: 2026-08-23

Verdict: `ACCEPT-WITH-CHANGES`, accepted in full.

## Root disposition

The initial unified contract still crossed the integrity/authority boundary. It made checkpoint
encoding depend on a future persisted payload, let a sealed historical bundle outlive currentness,
left execution/protection witness issuance implicit, imported a contradictory bootstrap grammar,
claimed history-shaped owner commitments could survive bounded projection, and asserted index
sufficiency before freezing the queries.

R1 will not patch those clauses individually. It will narrow WO-0168c to a complete but explicitly
**non-serving** checkpoint candidate:

1. a repository-issued pre-persistence selection proof drives exact bounded projection;
2. payload storage precedes kernel-head advance in the caller-owned transaction;
3. a distinct post-persistence load proof authenticates exact bytes and current direct rows;
4. decode returns only a non-serving restored candidate and never existing owner/proof types;
5. WO-0169 alone may convert that candidate to serving state after owner-lock and fresh head
   revalidation;
6. existing history-shaped commitments are retained as source evidence but are not claimed to be
   reproducible from bounded bytes; payload-only commitments are separately domain-bound; and
7. the exact query/predicate/index matrix, bootstrap/cursor rows, APIs, and mutation plan must be
   frozen before implementation authority.

The late-owner query will be designed from the exact current-generation key and a partial index,
not a scan of closed history. Any DDL byte change remains static-only and returns to Ameen's exact
human gate before installation or SQLite-bearing tests.

No source, test, DDL, or SQLite action is authorized by this disposition.
