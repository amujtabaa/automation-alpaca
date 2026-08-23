# WO-0168c R3 exact SQL and storage-vector manifest

Status: **NORMATIVE PART OF R3 — STATIC ONLY; DO NOT EXECUTE BEFORE HUMAN DDL GATE**

## 1. Mechanical notation

`V(alias, VECTOR)` below means the literal comma-separated expansion `alias.column` in the exact
vector order in section 2. It is a documentation space-saver, not runtime choice. Implementation
uses module constants containing the fully expanded final SQL; the SQL-manifest test expands this
table independently and requires byte equality after the repository's existing whitespace
normalization. No identifier or vector comes from a caller.

All parameters are positional in written `?` order. `CAP` is literal `65536`; `SCOPE_CAP` is
literal `4097`. Every returned row is an exact tuple. Existing repository builders and the added
joined-vector slicers enforce tuple length, SQLite storage class, canonical identities, and the
null rules in section 4.

## 2. Exact flattened storage vectors

```text
APP = application_generation_id,selected_execution_profile_id,
      selected_market_source_profile_id,activation_ordinal
EXEC_PROFILE = connection_profile_id,application_generation,broker_provider,
      environment_class,account_identity,trade_command_origin,order_query_origin,
      order_event_origin,credential_handle_fingerprint,adapter_contract_version,
      capability_profile_sha256,deployment_identity,profile_commitment_sha256
MARKET_PROFILE = market_source_profile_id,provider,environment_or_feed,source_origin,
      entitlement_class,normalization_contract_version,data_capability_profile_sha256,
      source_profile_commitment_sha256
HEAD = application_generation_id,currentness_head_ordinal,checkpoint_sha256,
      checkpoint_version_ordinal
SCOPE = scope_id,application_generation_id,execution_profile_id,symbol_text
CONTROLLER = scope_id,application_generation_id,execution_profile_id,
      live_acquisition_generation_id,aggregate_quantity,integrity_state,
      currentness_head_ordinal,controller_version_ordinal,emergency_compatibility_sha256
PROTECTION = scope_id,authority_class,active_stream_generation_id,
      active_acquisition_generation_id,active_generation_mandate_commitment_sha256,
      active_source_profile_id,active_session_external,active_sequence_mode,
      expected_controller_head_ordinal,state_commitment_sha256,version_ordinal
GENERATION = acquisition_generation_id,scope_id,status,successor_ordinal,
      predecessor_generation_id,mandate_commitment_sha256,emergency_compatibility_sha256
GENERATION_CURRENT = acquisition_generation_id,scope_id,current_economics_head_ordinal,
      unresolved_effect_count,active_protection_count
EFFECT = effect_id,effect_external,scope_id,application_generation_id,execution_profile_id,
      acquisition_generation_id,generation_mandate_commitment_sha256,
      expected_controller_head_ordinal,expected_protection_version_ordinal,authority_class,
      request_occurrence_external,mandate_external,effect_kind,client_order_external,
      target_order_external,side,quantity,economic_scope,lifecycle_state,disposition,
      closure_proof_kind,closure_proof_digest,closure_proof_evidence_id,
      closure_proof_claim_id,created_ordinal
OWNER = scope_id,execution_profile_id,owner_external,observation_external,effect_id,
      root_fill_key_id,owner_generation_id,admitted_after_effect_closed
CLAIM = claim_id,effect_id,execution_profile_id,claim_occurrence_external,claim_ordinal
ACCEPTANCE = acceptance_set_id,effect_id
EVIDENCE = evidence_id,acceptance_set_id,effect_id,evidence_kind,proof_kind,evidence_digest,
      evidence_ordinal,contradiction_owner_external,contradiction_observation_external
CLOSURE = closure_id,scope_id,owner_external,ordinal,effect_id,closure_kind,
      predecessor_closure_id
ROUTE = root_fill_key_id,scope_id,application_generation_id,execution_profile_id,
      acquisition_generation_id,effect_id,owner_external,observation_external
ROOT = root_fill_key_id,scope_id,application_generation_id,execution_profile_id,
      owner_generation_id,root_fill_external,current_fact_id,current_kind,current_authority,
      current_side,current_quantity,price_present,price_units,scale_sign,scale_digits,
      scale_exponent,tick_units,tick_scale_sign,tick_scale_digits,tick_scale_exponent,
      economics_head_ordinal
FACT_HEAD = root_fill_key_id,fact_id,fact_ordinal
FACT = fact_id,scope_id,application_generation_id,execution_profile_id,root_fill_key_id,
      source_event_id,order_external,side,kind,authority,quantity,price_present,price_units,
      scale_sign,scale_digits,scale_exponent,tick_units,tick_scale_sign,tick_scale_digits,
      tick_scale_exponent,request_occurrence_external,claim_occurrence_external,
      prior_cumulative_quantity,resulting_cumulative_quantity,actor_external,reason_text,
      evidence_reference_external,predecessor_fact_id,fact_ordinal
STREAM = stream_generation_id,scope_id,application_generation_id,
      acquisition_generation_id,generation_mandate_commitment_sha256,source_profile_id,
      session_external,sequence_mode
CURSOR = stream_generation_id,scope_id,application_generation_id,
      acquisition_generation_id,generation_mandate_commitment_sha256,source_profile_id,
      session_external,sequence_mode,fixed_cursor_ordinal,published_head_ordinal
PAYLOAD = application_generation_id,execution_profile_id,market_source_profile_id,
      currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,payload_length,
      payload_sha256
```

These vectors are byte-for-byte the current repository constants. `ROOT` is 21 columns and `FACT`
is 29; no logical dataclass field order substitutes for them.

## 3. Common CTEs

Q3, Q4a, Q4b, Q5, Q6a-c, Q7, Q8, and Q9 use `SELECTED_GENERATION`; Q5, Q6a-c,
Q7, and Q8 also use `QUALIFYING_EFFECT`.

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id = ?
      AND scope.execution_profile_id = ?
),
selected_generation(acquisition_generation_id,scope_id) AS MATERIALIZED (
    SELECT generation.acquisition_generation_id,generation.scope_id
    FROM selected_scope AS selected
    JOIN symbol_controller AS controller ON controller.scope_id = selected.scope_id
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id = controller.live_acquisition_generation_id
     AND generation.scope_id = selected.scope_id
     AND generation.status = 'LIVE'
    JOIN acquisition_generation_current AS current
      ON current.acquisition_generation_id = generation.acquisition_generation_id
     AND current.scope_id = generation.scope_id
    WHERE controller.live_acquisition_generation_id IS NOT NULL
    UNION
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_unresolved
      ON current.scope_id = selected.scope_id
     AND (current.unresolved_effect_count > 0 OR current.active_protection_count > 0)
    JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id = current.acquisition_generation_id
     AND generation.scope_id = current.scope_id
     AND generation.status = 'RETIRED_UNSERVING'
),
qualifying_effect(effect_id) AS MATERIALIZED (
    SELECT effect.effect_id
    FROM selected_generation AS selected
    JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
      ON effect.acquisition_generation_id = selected.acquisition_generation_id
     AND effect.disposition IN ('OPEN','INVALIDATED')
    UNION
    SELECT effect.effect_id
    FROM selected_generation AS selected
    JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
      ON owner.owner_generation_id = selected.acquisition_generation_id
     AND owner.admitted_after_effect_closed = 1
    JOIN venue_effect AS effect
      ON effect.effect_id = owner.effect_id
     AND effect.scope_id = selected.scope_id
     AND effect.acquisition_generation_id = selected.acquisition_generation_id
     AND effect.disposition = 'CLOSED'
)
```

The `QUALIFYING_EFFECT` CTE is not executed until Q4a and Q4b have independently established that
non-CLOSED effect rows and late-owner rows are each at most 65,535 and their unique effect union
equals the Q3 unresolved-counter sum. Its deduplication work is therefore bounded by two admitted
families, not retained history.

## 4. Twelve exact selection queries

Q1 parameters are `(application_id, execution_profile_id, market_profile_id)`:

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
  AND application.selected_execution_profile_id=?
  AND application.selected_market_source_profile_id=?
LIMIT 2
```

Q2 parameters are `(application_id, execution_profile_id)`:

```sql
SELECT V(scope,SCOPE),V(controller,CONTROLLER),V(protection,PROTECTION)
FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
JOIN symbol_controller AS controller ON controller.scope_id=scope.scope_id
 AND controller.application_generation_id=scope.application_generation_id
 AND controller.execution_profile_id=scope.execution_profile_id
JOIN protection_authority AS protection ON protection.scope_id=scope.scope_id
WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
ORDER BY scope.scope_id
LIMIT 4097
```

Q3 prepends `SELECTED_GENERATION`, takes the same two parameters, and ends:

```sql
SELECT V(generation,GENERATION),V(current,GENERATION_CURRENT)
FROM selected_generation AS selected
JOIN acquisition_generation AS generation
  ON generation.acquisition_generation_id=selected.acquisition_generation_id
 AND generation.scope_id=selected.scope_id
JOIN acquisition_generation_current AS current
  ON current.acquisition_generation_id=generation.acquisition_generation_id
 AND current.scope_id=generation.scope_id
ORDER BY generation.scope_id,generation.successor_ordinal,
         generation.acquisition_generation_id
LIMIT 65536
```

Q4a prepends `SELECTED_GENERATION` and returns non-CLOSED effects:

```sql
SELECT V(effect,EFFECT)
FROM selected_generation AS selected
JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
  ON effect.acquisition_generation_id=selected.acquisition_generation_id
 AND effect.disposition IN ('OPEN','INVALIDATED')
ORDER BY effect.created_ordinal,effect.effect_id
LIMIT 65536
```

Q4b prepends `SELECTED_GENERATION` and returns each late owner with its required CLOSED effect:

```sql
SELECT V(owner,OWNER),V(effect,EFFECT)
FROM selected_generation AS selected
JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
  ON owner.owner_generation_id=selected.acquisition_generation_id
 AND owner.admitted_after_effect_closed=1
JOIN venue_effect AS effect ON effect.effect_id=owner.effect_id
 AND effect.scope_id=selected.scope_id
 AND effect.acquisition_generation_id=selected.acquisition_generation_id
 AND effect.disposition='CLOSED'
ORDER BY owner.owner_generation_id,owner.effect_id,owner.owner_external
LIMIT 65536
```

Q5 prepends both common CTEs and returns all found owners:

```sql
SELECT V(owner,OWNER)
FROM qualifying_effect AS selected
JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
  ON owner.effect_id=selected.effect_id
ORDER BY owner.effect_id,owner.owner_external,owner.observation_external
LIMIT 65536
```

Q6a, Q6b, and Q6c prepend both CTEs and are respectively:

```sql
SELECT V(claim,CLAIM)
FROM qualifying_effect AS selected
JOIN dispatch_claim AS claim INDEXED BY ix_dispatch_claim_effect
  ON claim.effect_id=selected.effect_id
ORDER BY claim.effect_id,claim.claim_id
LIMIT 65536
```

```sql
SELECT V(acceptance,ACCEPTANCE)
FROM qualifying_effect AS selected
JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
ORDER BY acceptance.effect_id,acceptance.acceptance_set_id
LIMIT 65536
```

```sql
SELECT V(evidence,EVIDENCE)
FROM qualifying_effect AS selected
JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
JOIN acceptance_evidence AS evidence INDEXED BY ix_acceptance_evidence_set
  ON evidence.acceptance_set_id=acceptance.acceptance_set_id
ORDER BY evidence.effect_id,evidence.evidence_ordinal,evidence.evidence_id
LIMIT 65536
```

Q7 prepends both CTEs and selects one current closure head per found owner:

```sql
SELECT V(closure,CLOSURE)
FROM qualifying_effect AS selected
JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
  ON owner.effect_id=selected.effect_id
JOIN closure_chain AS closure ON closure.closure_id=(
    SELECT candidate.closure_id
    FROM closure_chain AS candidate INDEXED BY ix_closure_chain_head
    WHERE candidate.scope_id=owner.scope_id
      AND candidate.owner_external=owner.owner_external
    ORDER BY candidate.ordinal DESC
    LIMIT 1)
ORDER BY closure.effect_id,closure.owner_external,closure.ordinal
LIMIT 65536
```

Q8 prepends both CTEs and returns found routes/roots plus optional exact current fact:

```sql
SELECT V(route,ROUTE),V(root,ROOT),
       CASE WHEN head.fact_id IS NULL THEN 0 ELSE 1 END,V(head,FACT_HEAD),V(fact,FACT)
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
ORDER BY route.effect_id,route.owner_external,route.root_fill_key_id
LIMIT 65536
```

Q9 prepends `SELECTED_GENERATION` and returns found streams plus optional cursor:

```sql
SELECT V(stream,STREAM),
       CASE WHEN cursor.stream_generation_id IS NULL THEN 0 ELSE 1 END,V(cursor,CURSOR)
FROM selected_generation AS selected
JOIN market_stream_authority AS stream
  INDEXED BY ix_market_stream_authority_checkpoint_generation
  ON stream.acquisition_generation_id=selected.acquisition_generation_id
 AND stream.scope_id=selected.scope_id
LEFT JOIN market_cursor AS cursor ON cursor.stream_generation_id=stream.stream_generation_id
ORDER BY stream.acquisition_generation_id,stream.stream_generation_id
LIMIT 65536
```

Counting Q6a-c separately gives exactly twelve queries: Q1, Q2, Q3, Q4a, Q4b, Q5, Q6a, Q6b,
Q6c, Q7, Q8, Q9.

## 5. Result and absence rules

Q1 is zero or one; two is integrity failure. Its head vector is exactly `(0,NULL,NULL,NULL,NULL)`
or `(1,HEAD)` and must equal request.expected_checkpoint. Q2 scope IDs are unique and each
controller/protection pair agrees on scope and currentness. Q3 generation IDs are unique; each
scope has at most one LIVE row matching its controller.

Q4a and Q4b are independently capped. Q4b may repeat a CLOSED effect for distinct owners; unique
effect records must be byte/value-equal. Their unique union count equals the Q3 unresolved-counter
sum. Q5-Q9 are each independently capped.

Absence is the canonical-key-sorted complement of complete parents and found children:
`owner/effect`, `claim/effect`, `acceptance/effect`, `evidence/acceptance`, `closure/owner`,
`route/owner`, `fact-head/root`, `current-fact/root`, `stream/generation`, `cursor/stream`. Found and
absence sets are disjoint and their union equals the parent set. Q8's presence 0 requires all three
FACT_HEAD columns and all 29 FACT columns null; presence 1 requires both complete and equal to the
root's current economics. Q9's presence bit controls all ten cursor columns.

## 6. Load and write SQL

Initial/final head lookup is:

```sql
SELECT application_generation_id,currentness_head_ordinal,checkpoint_sha256,
       checkpoint_version_ordinal
FROM kernel_checkpoint WHERE application_generation_id=? LIMIT 2
```

Payload lookup is:

```sql
SELECT application_generation_id,execution_profile_id,market_source_profile_id,
       currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,payload_length,
       payload_sha256
FROM runtime_checkpoint_payload
WHERE application_generation_id=? AND currentness_head_ordinal=?
  AND checkpoint_version_ordinal=? AND payload_sha256=?
LIMIT 2
```

Payload INSERT and absent/found head CAS are exactly R2 section 9. Store-time reselection reruns all
twelve selection queries. Successful load is initial head + payload + twelve queries + final head,
exactly fifteen SELECTs.

## 7. Required plan assertions

Under at least 10,000 unrelated historical rows per populated base family, `EXPLAIN QUERY PLAN`
must contain `SEARCH` (never `SCAN`) for acquisition scope, unresolved generation-current,
generation, non-CLOSED effect, late owner, effect-owner, claim, acceptance, evidence, closure head,
root route, root, fact head, fact, stream, cursor, profile, application, head, and payload access.
Temporary B-tree use is permitted only for bounded Q3/Q4b/Q7/Q9 ordering or UNION deduplication;
it is forbidden over an unrelated-history base scan. Tests remove each R3 index one at a time and
must fail the named plan assertion.
