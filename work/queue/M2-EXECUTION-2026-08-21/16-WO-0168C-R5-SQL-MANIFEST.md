# WO-0168c R5 exact SQL and boundedness manifest

Status: **NORMATIVE PART OF R5 — STATIC ONLY; DO NOT EXECUTE BEFORE HUMAN DDL GATE**

Date: 2026-08-23

## 1. Fixed vectors, count, and DDL

The twenty flattened vectors are exactly the R3 SQL manifest section 2 at the full coordinate in
R5 section 1. There are exactly thirteen selection statements: Q1, Q2, Q3a, Q3b, Q4a, Q4b, Q5,
Q6a, Q6b, Q6c, Q7, Q8, Q9. `CAP=65536`; `SCOPE_CAP=4097`; parameters are positional in written
order. `V(alias,VECTOR)` is expanded from one private literal vector constant. The final SQL is
assembled only from the exact private fragments in this manifest at module import; no caller value
can supply SQL text or an identifier. Q01 independently expands and byte-compares every final
normalized statement.

Static DDL replaces
`checkpoint_version_ordinal INTEGER NOT NULL UNIQUE CHECK (checkpoint_version_ordinal >= 1)` with
`checkpoint_version_ordinal INTEGER NOT NULL CHECK (checkpoint_version_ordinal >= 1)`, deletes
R3's combined unresolved partial index, and adds exactly:

```sql
CREATE INDEX ix_acquisition_scope_checkpoint
ON acquisition_scope (application_generation_id, execution_profile_id, scope_id);

CREATE INDEX ix_acquisition_generation_current_checkpoint_effect
ON acquisition_generation_current (scope_id, acquisition_generation_id)
WHERE unresolved_effect_count > 0;

CREATE INDEX ix_acquisition_generation_current_checkpoint_protection
ON acquisition_generation_current (scope_id, acquisition_generation_id)
WHERE active_protection_count > 0;

CREATE INDEX ix_venue_owner_checkpoint_late
ON venue_identity_owner (owner_generation_id, effect_id, owner_external)
WHERE admitted_after_effect_closed = 1;

CREATE INDEX ix_market_stream_authority_checkpoint_generation
ON market_stream_authority (acquisition_generation_id, scope_id, stream_generation_id);
```

No other DDL changes. These bytes remain static until the exact human gate.

## 2. Q1 and Q2

Q1 parameters are only `(application_id,)`:

```sql
SELECT V(application,APP),V(execution_profile,EXEC_PROFILE),V(market_profile,MARKET_PROFILE),
       CASE WHEN checkpoint.application_generation_id IS NULL THEN 0 ELSE 1 END,
       V(checkpoint,HEAD)
FROM application_generation AS application
JOIN execution_connection_profile AS execution_profile
  ON execution_profile.connection_profile_id=application.selected_execution_profile_id
 AND execution_profile.application_generation=application.application_generation_id
JOIN market_data_source_profile AS market_profile
  ON market_profile.market_source_profile_id=application.selected_market_source_profile_id
LEFT JOIN kernel_checkpoint AS checkpoint
  ON checkpoint.application_generation_id=application.application_generation_id
WHERE application.application_generation_id=?
LIMIT 2
```

Zero rows is `ABSENT`. One row whose selected profile IDs differ from the request is `CONFLICT`.
Otherwise its exact optional HEAD must equal the expected checkpoint or selection is `CONFLICT`.

Q2 is R4 Q2. Missing joined row requires its entire vector NULL. A present CONTROLLER requires all
columns non-null except `live_acquisition_generation_id`, which may be NULL. A present PROTECTION
requires non-null `scope_id`, `authority_class`, `expected_controller_head_ordinal`,
`state_commitment_sha256`, and `version_ordinal`; its six active fields are either all NULL or all
non-null. `HARD_BAIL` additionally requires them present. Both joined rows are mandatory for every
scope; missing or malformed vectors are `INTEGRITY_FAILURE`.

## 3. Q3a and Q3b

`SELECTED_SCOPE` is exactly R4 section 3. Q3a is exactly R4 Q3a and includes both GENERATION and
GENERATION_CURRENT. Every non-null controller LIVE ID must occur exactly once in Q3a.

Q3b is one statement with two independently bounded, predicate-matched arms:

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
),
effect_unresolved AS MATERIALIZED (
    SELECT V(generation,GENERATION),V(current,GENERATION_CURRENT)
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_effect
      ON current.scope_id=selected.scope_id AND current.unresolved_effect_count>0
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id
     AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
protection_active AS MATERIALIZED (
    SELECT V(generation,GENERATION),V(current,GENERATION_CURRENT)
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_protection
      ON current.scope_id=selected.scope_id AND current.active_protection_count>0
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id
     AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
combined AS (
    SELECT * FROM effect_unresolved
    UNION
    SELECT * FROM protection_active
)
SELECT * FROM combined
LIMIT 65536
```

A 65,536th row in either arm or combined Q3b result refuses. Equal generation coordinates must
have equal complete vectors. The canonical Q3a/Q3b coordinate union is then independently capped
at 65,535 in repository code. Q3a is fully consumed before Q3b; Q3b and the combined union are
fully validated before Q4. Bounded rows are canonical-sorted only after these gates.

## 4. Exact later selected-generation CTE

Q4a-Q9 prepend one exact CTE whose LIVE arm is semantically identical to Q3a, including the
generation-current join. Its two retired arms are identical to Q3b. Each arm has `LIMIT 65536`;
their union has `LIMIT 65536` and projects only `(acquisition_generation_id,scope_id)` after full
row validation by Q3a/Q3b. All statements run in one caller-owned stable transaction, so identical
predicates observe the same snapshot. There is no separate runtime equality query. A static test
requires literal predicate/join parity; every Q4-Q9 child coordinate must belong to the canonical
Q3a/Q3b union, which detects any implementation splice.

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id FROM acquisition_scope AS scope
      INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
),
live_generation AS MATERIALIZED (
    SELECT generation.acquisition_generation_id,generation.scope_id
    FROM selected_scope AS selected
    JOIN symbol_controller AS controller ON controller.scope_id=selected.scope_id
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=controller.live_acquisition_generation_id
     AND generation.scope_id=selected.scope_id AND generation.status='LIVE'
    JOIN acquisition_generation_current AS current
      ON current.acquisition_generation_id=generation.acquisition_generation_id
     AND current.scope_id=generation.scope_id
    WHERE controller.live_acquisition_generation_id IS NOT NULL
    LIMIT 65536
),
effect_unresolved AS MATERIALIZED (
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_effect
      ON current.scope_id=selected.scope_id AND current.unresolved_effect_count>0
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
protection_active AS MATERIALIZED (
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_protection
      ON current.scope_id=selected.scope_id AND current.active_protection_count>0
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
selected_generation AS MATERIALIZED (
    SELECT * FROM (
      SELECT * FROM live_generation
      UNION SELECT * FROM effect_unresolved
      UNION SELECT * FROM protection_active)
    LIMIT 65536
)
```

## 5. Admission before canonical ordering

`SG` means the exact section-4 CTE through `selected_generation`; it is a literal private SQL
fragment. `QE` extends `SG` with exactly:

```sql
, qualifying_effect(effect_id) AS MATERIALIZED (
    SELECT effect.effect_id
    FROM selected_generation AS selected
    JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
      ON effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition IN ('OPEN','INVALIDATED')
    UNION
    SELECT effect.effect_id
    FROM selected_generation AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
      ON owner.owner_generation_id=selected.acquisition_generation_id
     AND owner.admitted_after_effect_closed=1
    JOIN venue_effect AS effect ON effect.effect_id=owner.effect_id
     AND effect.scope_id=selected.scope_id
     AND effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition='CLOSED'
)
```

The exact final bodies are below. Each `, admitted` literally extends SG or QE. Q4a is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(effect,EFFECT)
    FROM selected_generation AS selected
    JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
      ON effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition IN ('OPEN','INVALIDATED')
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 25,1
```

Q4b is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(owner,OWNER),V(effect,EFFECT)
    FROM selected_generation AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
      ON owner.owner_generation_id=selected.acquisition_generation_id
     AND owner.admitted_after_effect_closed=1
    JOIN venue_effect AS effect ON effect.effect_id=owner.effect_id
     AND effect.scope_id=selected.scope_id
     AND effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition='CLOSED'
    LIMIT 65536
)
SELECT * FROM admitted
ORDER BY 7,5,3
```

Q5 is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(owner,OWNER)
    FROM qualifying_effect AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted
ORDER BY 5,3,4
```

Q6a is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(claim,CLAIM)
    FROM qualifying_effect AS selected
    JOIN dispatch_claim AS claim INDEXED BY ix_dispatch_claim_effect
      ON claim.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 2,1
```

Q6b is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(acceptance,ACCEPTANCE)
    FROM qualifying_effect AS selected
    JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 2,1
```

Q6c is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(evidence,EVIDENCE)
    FROM qualifying_effect AS selected
    JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
    JOIN acceptance_evidence AS evidence INDEXED BY ix_acceptance_evidence_set
      ON evidence.acceptance_set_id=acceptance.acceptance_set_id
    LIMIT 65536
)
SELECT * FROM admitted
ORDER BY 3,7,1
```

Q7 is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(closure,CLOSURE)
    FROM qualifying_effect AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    JOIN closure_chain AS closure ON closure.closure_id=(
        SELECT candidate.closure_id
        FROM closure_chain AS candidate INDEXED BY ix_closure_chain_head
        WHERE candidate.scope_id=owner.scope_id
          AND candidate.owner_external=owner.owner_external
        ORDER BY candidate.ordinal DESC LIMIT 1)
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 5,3,4
```

Q8 is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(route,ROUTE),V(root,ROOT),
           CASE WHEN head.fact_id IS NULL THEN 0 ELSE 1 END,
           V(head,FACT_HEAD),V(fact,FACT)
    FROM qualifying_effect AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    JOIN acquisition_root_route AS route INDEXED BY ix_acquisition_root_route_owner
      ON route.effect_id=owner.effect_id
     AND route.owner_external=owner.owner_external
     AND route.observation_external=owner.observation_external
    JOIN root_fill AS root ON root.root_fill_key_id=route.root_fill_key_id
     AND root.scope_id=route.scope_id
     AND root.owner_generation_id=route.acquisition_generation_id
    LEFT JOIN execution_fact_head AS head ON head.root_fill_key_id=root.root_fill_key_id
    LEFT JOIN execution_fact AS fact ON fact.root_fill_key_id=head.root_fill_key_id
     AND fact.fact_id=head.fact_id AND fact.fact_ordinal=head.fact_ordinal
    LIMIT 65536
)
SELECT * FROM admitted
ORDER BY 6,7,1
```

Q9 is:

```sql
, admitted AS MATERIALIZED (
    SELECT V(stream,STREAM),
           CASE WHEN cursor.stream_generation_id IS NULL THEN 0 ELSE 1 END,V(cursor,CURSOR)
    FROM selected_generation AS selected
    JOIN market_stream_authority AS stream
      INDEXED BY ix_market_stream_authority_checkpoint_generation
      ON stream.acquisition_generation_id=selected.acquisition_generation_id
     AND stream.scope_id=selected.scope_id
    LEFT JOIN market_cursor AS cursor ON cursor.stream_generation_id=stream.stream_generation_id
    LIMIT 65536
)
SELECT * FROM admitted
ORDER BY 4,1
```

The positional ORDER BY terms above refer to the exact imported vector positions and avoid
duplicate joined-column-name ambiguity. A 65,536-row admitted result refuses before record construction. The SQL sort itself receives at
most 65,536 admitted rows. Q4a/Q4b run and validate before QE is ever executed; their exact unique
effect union must equal the admitted unresolved counter sum. Under the stable snapshot QE is the
same proven-bounded set. At most 65,536 selected-parent rows plus bounded parent CTE work can feed
any temporary B-tree.

## 6. Counts, plans, load, and writes

Each statement contributes one exact row count, including Q3b as one count. Store reselection is
thirteen statements. Successful composed load is initial head + payload + thirteen selection
statements + final head = sixteen SELECTs. Head/payload lookup and R4 payload INSERT/CAS SQL and
parameter order remain exact.

Under 10,000 unrelated rows and separate selected-parent 65,535/65,536 fixtures, every named base
access is `SEARCH`, never unrelated-history `SCAN`. Temporary B-trees are permitted only over an
already admitted CTE. Each forced partial index is tested with its exact predicate. Hard-index
removal must make preparation fail; reachable `NOT INDEXED` mutants must expose the expected base
SCAN. Plan assertions identify alias/table and required index, not generic `SEARCH` text.
