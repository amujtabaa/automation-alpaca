# WO-0168c R4 exact SQL correction manifest

Status: **NORMATIVE PART OF R4 — STATIC ONLY; DO NOT EXECUTE BEFORE HUMAN DDL GATE**

Date: 2026-08-23

## 1. Closed base and query count

The exact flattened storage vectors and Q1/Q4b/Q5/Q6a/Q6b/Q6c/Q7/Q8/Q9 are imported from
`12-WO-0168C-R3-SQL-MANIFEST.md` at SHA-256
`f1cae0c9af8a6b906497864e03311158ecdfae2ff37a7f7cd23c59c542bbd069`. This file replaces its
common CTE, Q2, Q3, Q4a, result/count, load-count, and plan clauses. There are exactly thirteen
selection queries: Q1, Q2, Q3a, Q3b, Q4a, Q4b, Q5, Q6a, Q6b, Q6c, Q7, Q8, Q9.

All parameters are positional in written order. `V(alias,VECTOR)`, `CAP=65536`, and
`SCOPE_CAP=4097` retain the R3 manifest's exact mechanical meaning.

## 2. Q2 — total scope discovery with presence vectors

Parameters are `(application_id, execution_profile_id)`:

```sql
SELECT V(scope,SCOPE),
       CASE WHEN controller.scope_id IS NULL THEN 0 ELSE 1 END,V(controller,CONTROLLER),
       CASE WHEN protection.scope_id IS NULL THEN 0 ELSE 1 END,V(protection,PROTECTION)
FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
LEFT JOIN symbol_controller AS controller ON controller.scope_id=scope.scope_id
 AND controller.application_generation_id=scope.application_generation_id
 AND controller.execution_profile_id=scope.execution_profile_id
LEFT JOIN protection_authority AS protection ON protection.scope_id=scope.scope_id
WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
ORDER BY scope.scope_id
LIMIT 4097
```

Controller presence 0 requires all CONTROLLER columns NULL; presence 1 requires all present and
scope/application/profile equal. Protection presence 0 requires all PROTECTION columns NULL;
presence 1 requires all present and scope equal. Every selected scope must have both presence bits
1; otherwise selection is `INTEGRITY_FAILURE`. Q2 therefore cannot silently omit an incomplete
scope.

## 3. Q3a/Q3b — separately bounded generation discovery

Both queries begin with the exact selected-scope CTE:

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id = ?
      AND scope.execution_profile_id = ?
)
```

Q3a appends and selects LIVE generations:

```sql
SELECT V(generation,GENERATION),V(current,GENERATION_CURRENT)
FROM selected_scope AS selected
JOIN symbol_controller AS controller ON controller.scope_id=selected.scope_id
JOIN acquisition_generation AS generation
  ON generation.acquisition_generation_id=controller.live_acquisition_generation_id
 AND generation.scope_id=selected.scope_id
 AND generation.status='LIVE'
JOIN acquisition_generation_current AS current
  ON current.acquisition_generation_id=generation.acquisition_generation_id
 AND current.scope_id=generation.scope_id
WHERE controller.live_acquisition_generation_id IS NOT NULL
ORDER BY generation.scope_id,generation.successor_ordinal,
         generation.acquisition_generation_id
LIMIT 65536
```

Q3b independently appends and selects unresolved retired-unserving generations:

```sql
SELECT V(generation,GENERATION),V(current,GENERATION_CURRENT)
FROM selected_scope AS selected
JOIN acquisition_generation_current AS current
  INDEXED BY ix_acquisition_generation_current_checkpoint_unresolved
  ON current.scope_id=selected.scope_id
 AND (current.unresolved_effect_count>0 OR current.active_protection_count>0)
JOIN acquisition_generation AS generation
  ON generation.acquisition_generation_id=current.acquisition_generation_id
 AND generation.scope_id=current.scope_id
 AND generation.status='RETIRED_UNSERVING'
ORDER BY generation.scope_id,generation.successor_ordinal,
         generation.acquisition_generation_id
LIMIT 65536
```

The repository consumes and validates Q3a completely before executing Q3b, and Q3b completely
before any later common CTE. A 65,536th row in either query refuses before combined
materialization. Each returned record pair is unique and coordinate-equal. The canonical union is
deduplicated by `(acquisition_generation_id,scope_id)` only after both gates; an overlap must have
byte/value-equal GENERATION and GENERATION_CURRENT vectors.

## 4. Bounded later common CTEs

Selection, store reselection, and composed load require one caller-owned stable-read transaction;
the repository verifies `connection.in_transaction` and never starts or ends it. After Q3a and Q3b
are admitted, Q4a/Q4b/Q5/Q6a/Q6b/Q6c/Q7/Q8/Q9 repeat discovery through this exact bounded common
CTE. Each arm is independently materialized and capped before the canonical union. A mutation that
removes either inner LIMIT is killed by Q03.

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id = ?
      AND scope.execution_profile_id = ?
),
live_generation(acquisition_generation_id,scope_id) AS MATERIALIZED (
    SELECT generation.acquisition_generation_id,generation.scope_id
    FROM selected_scope AS selected
    JOIN symbol_controller AS controller ON controller.scope_id=selected.scope_id
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=controller.live_acquisition_generation_id
     AND generation.scope_id=selected.scope_id
     AND generation.status='LIVE'
    WHERE controller.live_acquisition_generation_id IS NOT NULL
    LIMIT 65536
),
unresolved_generation(acquisition_generation_id,scope_id) AS MATERIALIZED (
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_unresolved
      ON current.scope_id=selected.scope_id
     AND (current.unresolved_effect_count>0 OR current.active_protection_count>0)
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id
     AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
selected_generation(acquisition_generation_id,scope_id) AS MATERIALIZED (
    SELECT acquisition_generation_id,scope_id FROM live_generation
    UNION
    SELECT acquisition_generation_id,scope_id FROM unresolved_generation
)
```

Because the transaction snapshot is stable, these arms equal the already admitted Q3a/Q3b
coordinates. Tests compare the CTE coordinate set to their canonical union. A mismatch is
`INTEGRITY_FAILURE` before child records are issued.

`qualifying_effect` for Q5-Q8 is the exact R3 CTE except its `selected_generation` input is the
already admitted coordinate relation. It is not executed until Q4a and Q4b are each capped and
their unique effect union equals the admitted unresolved-counter sum.

## 5. Q4a — bounded sort is explicit

Q4a uses the admitted selected-generation relation:

```sql
SELECT V(effect,EFFECT)
FROM selected_generation AS selected
JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
  ON effect.acquisition_generation_id=selected.acquisition_generation_id
 AND effect.disposition IN ('OPEN','INVALIDATED')
ORDER BY effect.created_ordinal,effect.effect_id
LIMIT 65536
```

The existing forced index bounds base access by selected generation/disposition. SQLite may use a
temporary B-tree for the `created_ordinal,effect_id` order; this is permitted because the result is
capped and generation discovery was already gated. No new wide index is added merely to avoid
that bounded sort.

## 6. Result, load, and write counts

Q1 is zero/one; two is integrity failure. Q2 and every later family use the exact R4 presence,
coordinate, cap, equality, and absence rules. Q3a and Q3b each contribute one query count, making
thirteen counts in the selection binding. Store-time reselection executes exactly thirteen
selection queries.

Successful composed load executes exactly sixteen SELECTs: initial head, payload, thirteen
selection queries, final head. Payload lookup and initial/final head SQL are exact R3 section 6.
Payload INSERT and head CAS are exact R4 contract section 7.

## 7. Plan assertions and reachable negative controls

With at least 10,000 unrelated rows per populated base family, every base access named in R3
section 7 must report `SEARCH`, never `SCAN`. Temporary B-tree use is allowed for Q3a/Q3b/Q4a/Q4b/
Q7/Q9 ordering and admitted-set UNION/deduplication. It is forbidden when paired with an unrelated-
history base scan.

Hard-index tests remove/recreate each added R4 index around the statement that names it and require
the statement to become unpreparable or violate its named plan assertion. The Q4a reachable
negative control does not delete the hard `INDEXED BY` target. Instead it executes a test-only SQL
mutant that replaces `INDEXED BY ix_venue_effect_generation_disposition` with
`NOT INDEXED`; under unrelated history the mutant must expose a `SCAN` and fail the same plan
predicate. Equivalent named `NOT INDEXED` mutants prove scope/current/owner/stream directness.

No plan test accepts generic `SEARCH` text alone: it matches the expected base alias/table and
required index name where `INDEXED BY` is normative.
