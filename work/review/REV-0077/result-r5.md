# REV-0077 R5 reconciled result

Date: 2026-08-23

Candidate: `2a096f100644191764b9d12403f3eb5fee823e39`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=8`, `P2=0`)

Three fresh-context reviewers verified the candidate and reconciled these findings:

1. R5 normatively references R4 contract/SQL objects that are absent from its closed
   `commit:path` authority table.
2. The authority top still needs explicit VenueRef, effect-authorization/current-effect, and manual
   wrapper/row imports rather than excluded transitive references.
3. Projected/loaded envelope formulas do not explicitly frame scope-owner rows, provenance, every
   public field/component, and public-bytes coherence.
4. The vector inventory is 22, not 20.
5. `EFFECT.economic_scope` is BLOB and was omitted from FIELD_BYTES classification.
6. Existing runtime capabilities have no transaction-generation lease, so a token from T1 can
   survive into T2 on the same connection; the new boundary and successor obligation must freeze
   issuance/invalidation.
7. W00 omits missing, subclassed, out-of-transaction, SQL-before-auth, and setup-support scope
   cases.
8. The fault matrix omits payload-INSERT raises; CAS-zero needs a reachable parameter/source mutant
   separate from stale reselection; and F00 requires transaction call-count evidence because its
   durable state is unchanged either way.

No SQLite, query-plan, changed-DDL, transaction, fault, source, or runtime test ran.
