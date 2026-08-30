"""M2-I2 inert SQLite schema contract and pure installer (human-gated).

This module is the exact M2-I2 schema-definition candidate. Importing it
performs no work: it contains only string constants, exception types, a
structural connection protocol, and pure functions. It imports neither
``sqlite3`` nor any I/O, clock, randomness, network, credential, or runtime
surface that opens a connection, discovers no database path, and never opens or inspects any
database by itself. ``install_schema`` acts only on an explicitly supplied
empty SQLite connection and refuses to act unless:

1. Ameen's application-owned execution authorization flag is exactly ``True``;
2. the reviewed expected digest and the caller's ``approved_ddl_sha256`` both
   equal the SHA-256 of these exact
   DDL bytes (EC-4: any byte drift returns to the human gate);
3. the supplied connection targets an empty database (zero ``sqlite_master``
   rows — EC-3: non-empty target refused before execution); and
4. ``PRAGMA foreign_keys`` and ``PRAGMA recursive_triggers`` verifiably report
   ``1`` on that connection (EC-3: disabled relational enforcement refused
   before execution).

``verify_schema_connection`` is the mandatory per-operation guard for later
repository work. SQLite enforcement pragmas are connection-local, so the
guard re-verifies them and the exact installed schema identity after every
open/reopen before durable authority may be read or written.

The schema enforces, database-natively: immutable generation/profile
bindings with exactly one selected profile pair per application generation;
one LIVE acquisition generation per exact scope; immutable predecessor-linked
facts whose revisions must follow their root's current head (no duplicate
roots, cross-root predecessors, branches, or out-of-order revisions); exact
effect-to-owner-to-closure bindings; canonical effect ownership of
OPEN|CLOSED|INVALIDATED with claim-before-CLOSED and terminal freeze;
append-only claims, owners, closures, facts, and acceptance evidence;
database-authenticated late-owner quarantine after apparent closure;
gap-free, branch-free, same-owner closure ordinals; version-coupled current
proof for checkpoint, controller, root economics, and protection authority;
and one current market cursor per stream-generation/source-profile binding.
"""

from __future__ import annotations as _annotations

from hashlib import sha256 as _sha256
from typing import Any as _Any
from typing import Final as _Final
from typing import Protocol as _Protocol
from typing import Sequence as _Sequence


SCHEMA_VERSION = 2

EXPECTED_EXECUTION_DDL_SHA256: _Final[str] = (
    "d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18"
)
DDL_EXECUTION_AUTHORIZED_BY_AMEEN: _Final[bool] = True

SCHEMA_DDL = """
CREATE TABLE schema_meta (
    schema_version INTEGER PRIMARY KEY,
    approved_ddl_sha256 TEXT NOT NULL
        CHECK (length(approved_ddl_sha256) = 64 AND approved_ddl_sha256 NOT GLOB '*[^0-9a-f]*'),
    observed_catalog_sha256 TEXT NOT NULL
        CHECK (length(observed_catalog_sha256) = 64 AND observed_catalog_sha256 NOT GLOB '*[^0-9a-f]*')
);

CREATE TABLE execution_connection_profile (
    connection_profile_id TEXT PRIMARY KEY
        CHECK (length(connection_profile_id) = 64 AND connection_profile_id NOT GLOB '*[^0-9a-f]*'),
    application_generation TEXT NOT NULL
        CHECK (length(application_generation) BETWEEN 1 AND 256),
    broker_provider TEXT NOT NULL
        CHECK (
            length(broker_provider) BETWEEN 1 AND 32
            AND broker_provider = upper(broker_provider)
            AND broker_provider GLOB '[A-Z]*'
            AND broker_provider NOT GLOB '*[^A-Z0-9_]*'
        ),
    environment_class TEXT NOT NULL
        CHECK (
            length(environment_class) BETWEEN 1 AND 32
            AND environment_class = upper(environment_class)
            AND environment_class GLOB '[A-Z]*'
            AND environment_class NOT GLOB '*[^A-Z0-9_]*'
        ),
    account_identity TEXT NOT NULL
        CHECK (length(account_identity) = 64 AND account_identity NOT GLOB '*[^0-9a-f]*'),
    trade_command_origin TEXT NOT NULL
        CHECK (
            trade_command_origin GLOB 'https://*'
            AND length(trade_command_origin) >= 9
            AND length(trade_command_origin) <= 261
            AND substr(trade_command_origin, 9) NOT GLOB '*[^a-z0-9.:-]*'
            AND trade_command_origin NOT LIKE '%@%'
            AND substr(trade_command_origin, 9) NOT LIKE '%//%'
            AND trade_command_origin NOT LIKE '%:443'
            AND trade_command_origin NOT LIKE '%:%:'
        ),
    order_query_origin TEXT NOT NULL
        CHECK (
            order_query_origin GLOB 'https://*'
            AND length(order_query_origin) >= 9
            AND length(order_query_origin) <= 261
            AND substr(order_query_origin, 9) NOT GLOB '*[^a-z0-9.:-]*'
            AND order_query_origin NOT LIKE '%@%'
            AND substr(order_query_origin, 9) NOT LIKE '%//%'
            AND order_query_origin NOT LIKE '%:443'
            AND order_query_origin NOT LIKE '%:%:'
        ),
    order_event_origin TEXT NOT NULL
        CHECK (
            order_event_origin GLOB 'https://*'
            AND length(order_event_origin) >= 9
            AND length(order_event_origin) <= 261
            AND substr(order_event_origin, 9) NOT GLOB '*[^a-z0-9.:-]*'
            AND order_event_origin NOT LIKE '%@%'
            AND substr(order_event_origin, 9) NOT LIKE '%//%'
            AND order_event_origin NOT LIKE '%:443'
            AND order_event_origin NOT LIKE '%:%:'
        ),
    credential_handle_fingerprint TEXT NOT NULL
        CHECK (length(credential_handle_fingerprint) = 64 AND credential_handle_fingerprint NOT GLOB '*[^0-9a-f]*'),
    adapter_contract_version TEXT NOT NULL
        CHECK (
            adapter_contract_version NOT GLOB '*[^0-9.]*'
            AND adapter_contract_version GLOB '[0-9]*[.][0-9]*[.][0-9]*'
            AND adapter_contract_version NOT LIKE '%..%'
            AND adapter_contract_version NOT LIKE '.%'
            AND adapter_contract_version NOT LIKE '%.'
        ),
    capability_profile_sha256 TEXT NOT NULL
        CHECK (length(capability_profile_sha256) = 64 AND capability_profile_sha256 NOT GLOB '*[^0-9a-f]*'),
    deployment_identity TEXT NOT NULL
        CHECK (length(deployment_identity) = 64 AND deployment_identity NOT GLOB '*[^0-9a-f]*'),
    profile_commitment_sha256 TEXT NOT NULL UNIQUE
        CHECK (length(profile_commitment_sha256) = 64 AND profile_commitment_sha256 NOT GLOB '*[^0-9a-f]*'),
    UNIQUE (connection_profile_id, application_generation)
);

CREATE TABLE market_data_source_profile (
    market_source_profile_id TEXT PRIMARY KEY
        CHECK (length(market_source_profile_id) = 64 AND market_source_profile_id NOT GLOB '*[^0-9a-f]*'),
    provider TEXT NOT NULL
        CHECK (
            length(provider) BETWEEN 1 AND 32
            AND provider = upper(provider)
            AND provider GLOB '[A-Z]*'
            AND provider NOT GLOB '*[^A-Z0-9_]*'
        ),
    environment_or_feed TEXT NOT NULL CHECK (length(environment_or_feed) >= 1),
    source_origin TEXT NOT NULL
        CHECK (
            source_origin GLOB 'https://*'
            AND length(source_origin) >= 9
            AND length(source_origin) <= 261
            AND substr(source_origin, 9) NOT GLOB '*[^a-z0-9.:-]*'
            AND source_origin NOT LIKE '%@%'
            AND substr(source_origin, 9) NOT LIKE '%//%'
            AND source_origin NOT LIKE '%:443'
            AND source_origin NOT LIKE '%:%:'
        ),
    entitlement_class TEXT NOT NULL
        CHECK (
            length(entitlement_class) BETWEEN 1 AND 32
            AND entitlement_class = upper(entitlement_class)
            AND entitlement_class GLOB '[A-Z]*'
            AND entitlement_class NOT GLOB '*[^A-Z0-9_]*'
        ),
    normalization_contract_version TEXT NOT NULL
        CHECK (
            normalization_contract_version NOT GLOB '*[^0-9.]*'
            AND normalization_contract_version GLOB '[0-9]*[.][0-9]*[.][0-9]*'
            AND normalization_contract_version NOT LIKE '%..%'
            AND normalization_contract_version NOT LIKE '.%'
            AND normalization_contract_version NOT LIKE '%.'
        ),
    data_capability_profile_sha256 TEXT NOT NULL
        CHECK (length(data_capability_profile_sha256) = 64 AND data_capability_profile_sha256 NOT GLOB '*[^0-9a-f]*'),
    source_profile_commitment_sha256 TEXT NOT NULL UNIQUE
        CHECK (length(source_profile_commitment_sha256) = 64 AND source_profile_commitment_sha256 NOT GLOB '*[^0-9a-f]*')
);

CREATE TABLE application_generation (
    application_generation_id TEXT PRIMARY KEY
        CHECK (length(application_generation_id) BETWEEN 1 AND 256),
    selected_execution_profile_id TEXT NOT NULL UNIQUE,
    selected_market_source_profile_id TEXT NOT NULL
        REFERENCES market_data_source_profile (market_source_profile_id),
    activation_ordinal INTEGER NOT NULL UNIQUE CHECK (activation_ordinal >= 1),
    UNIQUE (application_generation_id, selected_execution_profile_id),
    UNIQUE (application_generation_id, selected_market_source_profile_id),
    FOREIGN KEY (selected_execution_profile_id, application_generation_id)
        REFERENCES execution_connection_profile (
            connection_profile_id, application_generation
        )
);

CREATE TABLE acquisition_scope (
    scope_id INTEGER PRIMARY KEY,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    symbol_text TEXT NOT NULL CHECK (length(symbol_text) >= 1),
    UNIQUE (application_generation_id, execution_profile_id, symbol_text),
    UNIQUE (scope_id, application_generation_id),
    UNIQUE (scope_id, application_generation_id, execution_profile_id),
    FOREIGN KEY (application_generation_id, execution_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_execution_profile_id
        )
);

CREATE INDEX ix_acquisition_scope_checkpoint
ON acquisition_scope (application_generation_id, execution_profile_id, scope_id);

CREATE TABLE acquisition_generation (
    acquisition_generation_id TEXT PRIMARY KEY
        CHECK (length(acquisition_generation_id) = 64 AND acquisition_generation_id NOT GLOB '*[^0-9a-f]*'),
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    status TEXT NOT NULL CHECK (status IN ('LIVE', 'RETIRED_UNSERVING')),
    successor_ordinal INTEGER NOT NULL CHECK (successor_ordinal >= 1),
    predecessor_generation_id TEXT
        REFERENCES acquisition_generation (acquisition_generation_id),
    mandate_commitment_sha256 TEXT NOT NULL
        CHECK (length(mandate_commitment_sha256) = 64 AND mandate_commitment_sha256 NOT GLOB '*[^0-9a-f]*'),
    emergency_compatibility_sha256 TEXT NOT NULL
        CHECK (length(emergency_compatibility_sha256) = 64 AND emergency_compatibility_sha256 NOT GLOB '*[^0-9a-f]*'),
    UNIQUE (scope_id, successor_ordinal),
    UNIQUE (acquisition_generation_id, scope_id),
    UNIQUE (
        acquisition_generation_id, scope_id, mandate_commitment_sha256
    ),
    CHECK ((predecessor_generation_id IS NULL) = (successor_ordinal = 1))
);

CREATE UNIQUE INDEX uq_one_live_acquisition_per_scope
    ON acquisition_generation (scope_id)
    WHERE status = 'LIVE';

CREATE TABLE acquisition_generation_current (
    acquisition_generation_id TEXT PRIMARY KEY,
    scope_id INTEGER NOT NULL,
    current_economics_head_ordinal INTEGER NOT NULL
        CHECK (current_economics_head_ordinal >= 0),
    unresolved_effect_count INTEGER NOT NULL
        CHECK (unresolved_effect_count >= 0),
    active_protection_count INTEGER NOT NULL
        CHECK (active_protection_count IN (0, 1)),
    UNIQUE (acquisition_generation_id, scope_id),
    FOREIGN KEY (acquisition_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id)
);

CREATE INDEX ix_acquisition_generation_current_checkpoint_effect
ON acquisition_generation_current (scope_id, acquisition_generation_id)
WHERE unresolved_effect_count > 0;

CREATE INDEX ix_acquisition_generation_current_checkpoint_protection
ON acquisition_generation_current (scope_id, acquisition_generation_id)
WHERE active_protection_count > 0;

CREATE TABLE kernel_checkpoint (
    application_generation_id TEXT PRIMARY KEY
        REFERENCES application_generation (application_generation_id),
    currentness_head_ordinal INTEGER NOT NULL CHECK (currentness_head_ordinal >= 0),
    checkpoint_sha256 TEXT NOT NULL
        CHECK (length(checkpoint_sha256) = 64 AND checkpoint_sha256 NOT GLOB '*[^0-9a-f]*'),
    checkpoint_version_ordinal INTEGER NOT NULL CHECK (checkpoint_version_ordinal >= 1)
);

CREATE TABLE symbol_controller (
    scope_id INTEGER PRIMARY KEY,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    live_acquisition_generation_id TEXT,

    aggregate_quantity INTEGER NOT NULL,
    integrity_state TEXT NOT NULL
        CHECK (
            integrity_state IN (
                'CONSISTENT',
                'NEGATIVE_POSITION_QUARANTINED',
                'UNMATCHED_LINEAGE_QUARANTINED',
                'UNRESOLVED_VENUE_QUARANTINED',
                'MIXED_GENERATION_RECOVERY'
            )
        ),
    currentness_head_ordinal INTEGER NOT NULL CHECK (currentness_head_ordinal >= 0),
    controller_version_ordinal INTEGER NOT NULL CHECK (controller_version_ordinal >= 1),
    emergency_compatibility_sha256 TEXT NOT NULL
        CHECK (length(emergency_compatibility_sha256) = 64 AND emergency_compatibility_sha256 NOT GLOB '*[^0-9a-f]*'),
    UNIQUE (scope_id, controller_version_ordinal),
    UNIQUE (scope_id, application_generation_id, execution_profile_id),
    FOREIGN KEY (scope_id, application_generation_id, execution_profile_id)
        REFERENCES acquisition_scope (
            scope_id, application_generation_id, execution_profile_id
        ),
    FOREIGN KEY (live_acquisition_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id)
);

CREATE TABLE root_fill (
    root_fill_key_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    owner_generation_id TEXT NOT NULL,

    root_fill_external TEXT NOT NULL CHECK (length(root_fill_external) >= 1),
    current_fact_id INTEGER,
    current_kind TEXT CHECK (current_kind IN ('FILL', 'TRADE_CORRECT', 'TRADE_BUST')),
    current_authority TEXT
        CHECK (current_authority IN ('BROKER_AUTHORITATIVE', 'HUMAN_ATTESTED')),
    current_side TEXT CHECK (current_side IN ('BUY', 'SELL')),
    current_quantity INTEGER CHECK (current_quantity >= 0),
    price_present INTEGER CHECK (price_present IN (0, 1)),
    price_units INTEGER,
    scale_sign INTEGER CHECK (scale_sign IN (0, 1)),
    scale_digits TEXT,
    scale_exponent INTEGER,
    tick_units INTEGER,
    tick_scale_sign INTEGER CHECK (tick_scale_sign IN (0, 1)),
    tick_scale_digits TEXT,
    tick_scale_exponent INTEGER,
    economics_head_ordinal INTEGER NOT NULL CHECK (economics_head_ordinal >= 0),
    UNIQUE (execution_profile_id, root_fill_external),
    UNIQUE (root_fill_key_id, scope_id),
    UNIQUE (root_fill_key_id, scope_id, owner_generation_id),
    UNIQUE (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id
    ),
    UNIQUE (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id, owner_generation_id
    ),
    CHECK (
        (
            current_fact_id IS NULL
            AND current_kind IS NULL
            AND current_authority IS NULL
            AND current_side IS NULL
            AND current_quantity IS NULL
            AND price_present IS NULL
            AND price_units IS NULL
            AND scale_sign IS NULL
            AND scale_digits IS NULL
            AND scale_exponent IS NULL
            AND tick_units IS NULL
            AND tick_scale_sign IS NULL
            AND tick_scale_digits IS NULL
            AND tick_scale_exponent IS NULL
            AND economics_head_ordinal = 0
        )
        OR
        (
            current_fact_id IS NOT NULL
            AND current_kind IS NOT NULL
            AND current_authority IS NOT NULL
            AND current_side IS NOT NULL
            AND current_quantity IS NOT NULL
            AND price_present IS NOT NULL
            AND price_units IS NOT NULL
            AND scale_sign IS NOT NULL
            AND scale_digits IS NOT NULL
            AND scale_exponent IS NOT NULL
            AND tick_units IS NOT NULL
            AND tick_scale_sign IS NOT NULL
            AND tick_scale_digits IS NOT NULL
            AND tick_scale_exponent IS NOT NULL
            AND economics_head_ordinal >= 1
        )
    ),
    FOREIGN KEY (scope_id, application_generation_id, execution_profile_id)
        REFERENCES acquisition_scope (
            scope_id, application_generation_id, execution_profile_id
        ),
    FOREIGN KEY (owner_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id),
    FOREIGN KEY (
        root_fill_key_id, current_fact_id, economics_head_ordinal,
        current_kind, current_authority, current_side, current_quantity,
        price_present, price_units, scale_sign, scale_digits, scale_exponent,
        tick_units, tick_scale_sign, tick_scale_digits, tick_scale_exponent
    ) REFERENCES execution_fact (
        root_fill_key_id, fact_id, fact_ordinal,
        kind, authority, side, quantity,
        price_present, price_units, scale_sign, scale_digits, scale_exponent,
        tick_units, tick_scale_sign, tick_scale_digits, tick_scale_exponent
    )
);

CREATE INDEX ix_root_fill_owner ON root_fill (owner_generation_id, root_fill_key_id);
CREATE INDEX ix_root_fill_scope_current_economics
    ON root_fill (
        scope_id, current_fact_id, current_side, current_quantity
    );

CREATE TABLE execution_fact (
    fact_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    root_fill_key_id INTEGER NOT NULL,
    source_event_id TEXT NOT NULL CHECK (length(source_event_id) >= 1),
    order_external TEXT NOT NULL CHECK (length(order_external) >= 1),
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    kind TEXT NOT NULL CHECK (kind IN ('FILL', 'TRADE_CORRECT', 'TRADE_BUST')),
    authority TEXT NOT NULL
        CHECK (authority IN ('BROKER_AUTHORITATIVE', 'HUMAN_ATTESTED')),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    price_present INTEGER NOT NULL CHECK (price_present IN (0, 1)),
    price_units INTEGER NOT NULL,
    scale_sign INTEGER NOT NULL CHECK (scale_sign IN (0, 1)),
    scale_digits TEXT NOT NULL
        CHECK (
            scale_digits <> ''
            AND scale_digits NOT GLOB '*[^0-9]*'
            AND (scale_digits = '0' OR substr(scale_digits, 1, 1) <> '0')
        ),
    scale_exponent INTEGER NOT NULL,
    tick_units INTEGER NOT NULL,
    tick_scale_sign INTEGER NOT NULL CHECK (tick_scale_sign IN (0, 1)),
    tick_scale_digits TEXT NOT NULL
        CHECK (
            tick_scale_digits <> ''
            AND tick_scale_digits NOT GLOB '*[^0-9]*'
            AND (
                tick_scale_digits = '0'
                OR substr(tick_scale_digits, 1, 1) <> '0'
            )
        ),
    tick_scale_exponent INTEGER NOT NULL,
    request_occurrence_external TEXT,
    claim_occurrence_external TEXT,
    prior_cumulative_quantity INTEGER CHECK (prior_cumulative_quantity >= 0),
    resulting_cumulative_quantity INTEGER CHECK (resulting_cumulative_quantity >= 0),
    actor_external TEXT,
    reason_text TEXT,
    evidence_reference_external TEXT,
    predecessor_fact_id INTEGER,
    fact_ordinal INTEGER NOT NULL UNIQUE CHECK (fact_ordinal >= 1),
    CHECK ((kind = 'FILL') = (predecessor_fact_id IS NULL)),
    CHECK (predecessor_fact_id IS NULL OR predecessor_fact_id <> fact_id),
    CHECK (
        (
            price_present = 0
            AND price_units = 0
            AND scale_sign = 0
            AND scale_digits = '0'
            AND scale_exponent = 0
            AND tick_units = 0
            AND tick_scale_sign = 0
            AND tick_scale_digits = '0'
            AND tick_scale_exponent = 0
        )
        OR
        (
            price_present = 1
            AND price_units > 0
            AND scale_sign = 0
            AND scale_digits <> '0'
            AND tick_units > 0
            AND tick_scale_sign = 0
            AND tick_scale_digits <> '0'
        )
    ),
    CHECK (
        (kind IN ('FILL', 'TRADE_CORRECT') AND quantity > 0 AND price_present = 1)
        OR (kind = 'TRADE_BUST' AND quantity = 0)
    ),
    CHECK (kind = 'FILL' OR authority = 'BROKER_AUTHORITATIVE'),
    CHECK (
        (authority = 'BROKER_AUTHORITATIVE')
        = (
            request_occurrence_external IS NULL
            AND claim_occurrence_external IS NULL
            AND prior_cumulative_quantity IS NULL
            AND resulting_cumulative_quantity IS NULL
            AND actor_external IS NULL
            AND reason_text IS NULL
            AND evidence_reference_external IS NULL
        )
    ),
    CHECK (
        authority <> 'HUMAN_ATTESTED'
        OR (
            kind = 'FILL'
            AND request_occurrence_external IS NOT NULL
            AND length(request_occurrence_external) >= 1
            AND claim_occurrence_external IS NOT NULL
            AND length(claim_occurrence_external) >= 1
            AND prior_cumulative_quantity IS NOT NULL
            AND resulting_cumulative_quantity IS NOT NULL
            AND actor_external IS NOT NULL
            AND length(actor_external) >= 1
            AND reason_text IS NOT NULL
            AND length(reason_text) >= 1
            AND evidence_reference_external IS NOT NULL
            AND length(evidence_reference_external) >= 1
        )
    ),
    FOREIGN KEY (scope_id, application_generation_id, execution_profile_id)
        REFERENCES acquisition_scope (
            scope_id, application_generation_id, execution_profile_id
        ),
    FOREIGN KEY (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id
    ) REFERENCES root_fill (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id
    ),
    FOREIGN KEY (root_fill_key_id, predecessor_fact_id)
        REFERENCES execution_fact (root_fill_key_id, fact_id)
);

CREATE UNIQUE INDEX uq_execution_fact_root_fact ON execution_fact (root_fill_key_id, fact_id);
CREATE UNIQUE INDEX uq_execution_fact_root_fact_ordinal
    ON execution_fact (root_fill_key_id, fact_id, fact_ordinal);
CREATE UNIQUE INDEX uq_execution_fact_exact_current_economics ON execution_fact (
    root_fill_key_id, fact_id, fact_ordinal,
    kind, authority, side, quantity,
    price_present, price_units, scale_sign, scale_digits, scale_exponent,
    tick_units, tick_scale_sign, tick_scale_digits, tick_scale_exponent
);
CREATE UNIQUE INDEX uq_execution_fact_one_fill_per_root
    ON execution_fact (root_fill_key_id)
    WHERE kind = 'FILL';
CREATE UNIQUE INDEX uq_execution_fact_m1_key ON execution_fact (
    execution_profile_id,
    source_event_id
);
CREATE INDEX ix_execution_fact_root_head ON execution_fact (root_fill_key_id, fact_ordinal DESC);

CREATE TABLE execution_fact_head (
    root_fill_key_id INTEGER PRIMARY KEY REFERENCES root_fill (root_fill_key_id),
    fact_id INTEGER NOT NULL UNIQUE,
    fact_ordinal INTEGER NOT NULL UNIQUE CHECK (fact_ordinal >= 1),
    UNIQUE (root_fill_key_id, fact_id, fact_ordinal),
    FOREIGN KEY (root_fill_key_id, fact_id, fact_ordinal)
        REFERENCES execution_fact (root_fill_key_id, fact_id, fact_ordinal)
);

CREATE TABLE venue_effect (
    effect_id INTEGER PRIMARY KEY,
    effect_external TEXT NOT NULL CHECK (length(effect_external) >= 1),
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    acquisition_generation_id TEXT NOT NULL,
    generation_mandate_commitment_sha256 TEXT NOT NULL
        CHECK (
            length(generation_mandate_commitment_sha256) = 64
            AND generation_mandate_commitment_sha256
                NOT GLOB '*[^0-9a-f]*'
        ),
    expected_controller_head_ordinal INTEGER NOT NULL
        CHECK (expected_controller_head_ordinal >= 0),
    expected_protection_version_ordinal INTEGER NOT NULL
        CHECK (expected_protection_version_ordinal >= 1),
    authority_class TEXT NOT NULL
        CHECK (authority_class IN ('NORMAL', 'HARD_BAIL')),
    request_occurrence_external TEXT NOT NULL
        CHECK (length(request_occurrence_external) >= 1),
    mandate_external TEXT NOT NULL CHECK (length(mandate_external) >= 1),
    effect_kind TEXT NOT NULL
        CHECK (effect_kind IN ('SUBMIT', 'CANCEL', 'REPLACE')),
    client_order_external TEXT,
    target_order_external TEXT,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    economic_scope BLOB NOT NULL CHECK (length(economic_scope) >= 1),
    lifecycle_state TEXT NOT NULL
        CHECK (
            lifecycle_state IN (
                'REQUESTED', 'CANCELED_BEFORE_DISPATCH', 'DISPATCH_CLAIMED',
                'ACKNOWLEDGED', 'REJECTED', 'OUTCOME_UNKNOWN',
                'NEEDS_REVIEW', 'OPERATOR_RECONCILED'
            )
        ),
    disposition TEXT NOT NULL CHECK (disposition IN ('OPEN', 'CLOSED', 'INVALIDATED')),
    closure_proof_kind TEXT
        CHECK (
            closure_proof_kind IS NULL
            OR closure_proof_kind IN (
                'NEVER_DISPATCHED',
                'CONTRACT_COMPLETE_RESPONSE',
                'COVERED_RECONCILIATION'
            )
        ),
    closure_proof_digest TEXT
        CHECK (
            closure_proof_digest IS NULL
            OR (
                length(closure_proof_digest) = 64
                AND closure_proof_digest NOT GLOB '*[^0-9a-f]*'
            )
        ),
    closure_proof_evidence_id INTEGER,
    closure_proof_claim_id INTEGER,
    created_ordinal INTEGER NOT NULL UNIQUE CHECK (created_ordinal >= 1),
    UNIQUE (execution_profile_id, effect_external),
    UNIQUE (execution_profile_id, request_occurrence_external),
    UNIQUE (execution_profile_id, client_order_external),
    UNIQUE (effect_id, scope_id),
    UNIQUE (effect_id, execution_profile_id),
    UNIQUE (effect_id, scope_id, execution_profile_id),
    UNIQUE (
        effect_id, scope_id, execution_profile_id,
        acquisition_generation_id
    ),
    UNIQUE (
        effect_id, scope_id, application_generation_id,
        execution_profile_id, acquisition_generation_id
    ),
    CHECK (
        (
            effect_kind = 'SUBMIT'
            AND client_order_external IS NOT NULL
            AND length(client_order_external) >= 1
            AND target_order_external IS NULL
        )
        OR (
            effect_kind = 'CANCEL'
            AND client_order_external IS NULL
            AND target_order_external IS NOT NULL
            AND length(target_order_external) >= 1
        )
        OR (
            effect_kind = 'REPLACE'
            AND client_order_external IS NOT NULL
            AND length(client_order_external) >= 1
            AND target_order_external IS NOT NULL
            AND length(target_order_external) >= 1
        )
    ),
    CHECK (
        authority_class = 'NORMAL'
        OR (
            authority_class = 'HARD_BAIL'
            AND effect_kind = 'SUBMIT'
            AND side = 'SELL'
        )
    ),
    CHECK (
        (
            disposition = 'OPEN'
            AND closure_proof_kind IS NULL
            AND closure_proof_digest IS NULL
            AND closure_proof_evidence_id IS NULL
            AND closure_proof_claim_id IS NULL
        )
        OR
        (
            disposition IN ('CLOSED', 'INVALIDATED')
            AND closure_proof_kind IS NOT NULL
            AND closure_proof_digest IS NOT NULL
            AND closure_proof_evidence_id IS NOT NULL
            AND (
                (
                    closure_proof_kind = 'NEVER_DISPATCHED'
                    AND closure_proof_claim_id IS NULL
                )
                OR
                (
                    closure_proof_kind <> 'NEVER_DISPATCHED'
                    AND closure_proof_claim_id IS NOT NULL
                )
            )
        )
    ),
    FOREIGN KEY (scope_id, application_generation_id, execution_profile_id)
        REFERENCES acquisition_scope (
            scope_id, application_generation_id, execution_profile_id
        ),
    FOREIGN KEY (
        acquisition_generation_id, scope_id,
        generation_mandate_commitment_sha256
    ) REFERENCES acquisition_generation (
        acquisition_generation_id, scope_id, mandate_commitment_sha256
    ),
    FOREIGN KEY (effect_id, closure_proof_claim_id)
        REFERENCES dispatch_claim (effect_id, claim_id),
    FOREIGN KEY (
        closure_proof_evidence_id, effect_id,
        closure_proof_digest, closure_proof_kind
    ) REFERENCES acceptance_evidence (
        evidence_id, effect_id, evidence_digest, proof_kind
    )
);

CREATE INDEX ix_venue_effect_scope_state ON venue_effect (scope_id, disposition, effect_id);

CREATE UNIQUE INDEX uq_one_hard_bail_effect_per_controller_head
    ON venue_effect (scope_id, expected_controller_head_ordinal)
    WHERE authority_class = 'HARD_BAIL';

CREATE TABLE venue_identity_owner (
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    execution_profile_id TEXT NOT NULL,
    owner_external TEXT NOT NULL CHECK (length(owner_external) >= 1),
    observation_external TEXT NOT NULL
        CHECK (length(observation_external) >= 1),
    effect_id INTEGER NOT NULL,
    root_fill_key_id INTEGER,
    owner_generation_id TEXT NOT NULL,
    admitted_after_effect_closed INTEGER NOT NULL
        CHECK (admitted_after_effect_closed IN (0, 1)),
    PRIMARY KEY (execution_profile_id, owner_external),
    UNIQUE (scope_id, owner_external, effect_id),
    UNIQUE (effect_id, owner_external, observation_external),
    UNIQUE (
        effect_id, owner_external, observation_external, scope_id,
        execution_profile_id, owner_generation_id
    ),
    UNIQUE (
        effect_id, owner_external, observation_external, root_fill_key_id,
        scope_id, execution_profile_id, owner_generation_id
    ),
    FOREIGN KEY (
        effect_id, scope_id, execution_profile_id, owner_generation_id
    ) REFERENCES venue_effect (
        effect_id, scope_id, execution_profile_id,
        acquisition_generation_id
    ),
    FOREIGN KEY (owner_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id),
    FOREIGN KEY (
        root_fill_key_id, scope_id, owner_generation_id
    ) REFERENCES root_fill (
        root_fill_key_id, scope_id, owner_generation_id
    )
);

CREATE INDEX ix_venue_identity_owner_effect
    ON venue_identity_owner (
        effect_id, admitted_after_effect_closed, scope_id,
        execution_profile_id, owner_external
    );

CREATE INDEX ix_venue_owner_checkpoint_late
ON venue_identity_owner (owner_generation_id, effect_id, owner_external)
WHERE admitted_after_effect_closed = 1;

CREATE INDEX ix_venue_effect_generation_disposition
    ON venue_effect (acquisition_generation_id, disposition, effect_id);

CREATE TABLE acquisition_root_route (
    root_fill_key_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    acquisition_generation_id TEXT NOT NULL,
    effect_id INTEGER NOT NULL,
    owner_external TEXT NOT NULL CHECK (length(owner_external) >= 1),
    observation_external TEXT NOT NULL
        CHECK (length(observation_external) >= 1),
    UNIQUE (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id
    ),
    UNIQUE (root_fill_key_id, acquisition_generation_id),
    UNIQUE (
        effect_id, owner_external, observation_external, scope_id,
        execution_profile_id, acquisition_generation_id
    ),
    FOREIGN KEY (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id, acquisition_generation_id
    ) REFERENCES root_fill (
        root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id, owner_generation_id
    ),
    FOREIGN KEY (
        effect_id, owner_external, observation_external, scope_id,
        execution_profile_id, acquisition_generation_id
    ) REFERENCES venue_identity_owner (
        effect_id, owner_external, observation_external, scope_id,
        execution_profile_id, owner_generation_id
    )
);

CREATE INDEX ix_acquisition_root_route_owner
    ON acquisition_root_route (
        effect_id, owner_external, observation_external,
        acquisition_generation_id, root_fill_key_id
    );

CREATE INDEX ix_acquisition_root_route_generation
    ON acquisition_root_route (
        acquisition_generation_id, root_fill_key_id
    );

CREATE INDEX ix_venue_owner_late_scope_evidence
    ON venue_identity_owner (
        scope_id, effect_id, owner_external, observation_external
    )
    WHERE admitted_after_effect_closed = 1;

CREATE TABLE dispatch_claim (
    claim_id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL UNIQUE,
    execution_profile_id TEXT NOT NULL,
    claim_occurrence_external TEXT NOT NULL
        CHECK (length(claim_occurrence_external) >= 1),
    claim_ordinal INTEGER NOT NULL UNIQUE CHECK (claim_ordinal >= 1),
    UNIQUE (effect_id, claim_id),
    UNIQUE (effect_id, claim_ordinal),
    UNIQUE (execution_profile_id, claim_occurrence_external),
    FOREIGN KEY (effect_id, execution_profile_id)
        REFERENCES venue_effect (effect_id, execution_profile_id)
);

CREATE INDEX ix_dispatch_claim_effect ON dispatch_claim (effect_id, claim_id);

CREATE TABLE acceptance_set (
    acceptance_set_id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL UNIQUE REFERENCES venue_effect (effect_id),
    UNIQUE (acceptance_set_id, effect_id)
);

CREATE TABLE acceptance_evidence (
    evidence_id INTEGER PRIMARY KEY CHECK (evidence_id >= 1),
    acceptance_set_id INTEGER NOT NULL,
    effect_id INTEGER NOT NULL,
    evidence_kind TEXT NOT NULL
        CHECK (evidence_kind IN ('OBSERVATION', 'CLOSURE_PROOF', 'INVALIDATION', 'RECONCILIATION_NOTE')),
    proof_kind TEXT
        CHECK (
            proof_kind IS NULL
            OR proof_kind IN (
                'NEVER_DISPATCHED',
                'CONTRACT_COMPLETE_RESPONSE',
                'COVERED_RECONCILIATION'
            )
        ),
    evidence_digest TEXT NOT NULL
        CHECK (length(evidence_digest) = 64 AND evidence_digest NOT GLOB '*[^0-9a-f]*'),
    evidence_ordinal INTEGER NOT NULL UNIQUE CHECK (evidence_ordinal >= 1),
    contradiction_owner_external TEXT,
    contradiction_observation_external TEXT,
    UNIQUE (evidence_id, effect_id, evidence_digest, proof_kind),
    CHECK ((evidence_kind = 'CLOSURE_PROOF') = (proof_kind IS NOT NULL)),
    CHECK (
        (
            evidence_kind = 'INVALIDATION'
            AND contradiction_owner_external IS NOT NULL
            AND length(contradiction_owner_external) >= 1
            AND contradiction_observation_external IS NOT NULL
            AND length(contradiction_observation_external) >= 1
        )
        OR (
            evidence_kind <> 'INVALIDATION'
            AND contradiction_owner_external IS NULL
            AND contradiction_observation_external IS NULL
        )
    ),
    FOREIGN KEY (acceptance_set_id, effect_id)
        REFERENCES acceptance_set (acceptance_set_id, effect_id),
    FOREIGN KEY (
        effect_id, contradiction_owner_external,
        contradiction_observation_external
    ) REFERENCES venue_identity_owner (
        effect_id, owner_external, observation_external
    )
);

CREATE INDEX ix_acceptance_evidence_set ON acceptance_evidence (acceptance_set_id, evidence_ordinal DESC);

CREATE UNIQUE INDEX uq_acceptance_invalidation_owner_observation
    ON acceptance_evidence (
        effect_id, contradiction_owner_external,
        contradiction_observation_external
    )
    WHERE evidence_kind = 'INVALIDATION';

CREATE TABLE closure_chain (
    closure_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    owner_external TEXT NOT NULL CHECK (length(owner_external) >= 1),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    effect_id INTEGER NOT NULL,
    closure_kind TEXT NOT NULL
        CHECK (closure_kind IN ('TERMINAL_LEG', 'ACCEPTANCE_CLOSED', 'INVALIDATED_TERMINAL')),
    predecessor_closure_id INTEGER,
    UNIQUE (scope_id, owner_external, closure_id),
    FOREIGN KEY (scope_id, owner_external, effect_id)
        REFERENCES venue_identity_owner (scope_id, owner_external, effect_id),
    FOREIGN KEY (scope_id, owner_external, predecessor_closure_id)
        REFERENCES closure_chain (scope_id, owner_external, closure_id),
    CHECK ((predecessor_closure_id IS NULL) = (ordinal = 1)),
    CHECK (
        (closure_kind = 'INVALIDATED_TERMINAL') = (closure_id < 0)
    )
);

CREATE UNIQUE INDEX uq_closure_single_successor
    ON closure_chain (scope_id, owner_external, predecessor_closure_id)
    WHERE predecessor_closure_id IS NOT NULL;

CREATE UNIQUE INDEX uq_closure_single_root
    ON closure_chain (scope_id, owner_external)
    WHERE predecessor_closure_id IS NULL;

CREATE INDEX ix_closure_chain_head ON closure_chain (scope_id, owner_external, ordinal DESC);

CREATE TABLE market_stream_authority (
    stream_generation_id TEXT NOT NULL
        CHECK (length(stream_generation_id) = 64 AND stream_generation_id NOT GLOB '*[^0-9a-f]*'),
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    acquisition_generation_id TEXT NOT NULL,
    generation_mandate_commitment_sha256 TEXT NOT NULL
        CHECK (
            length(generation_mandate_commitment_sha256) = 64
            AND generation_mandate_commitment_sha256
                NOT GLOB '*[^0-9a-f]*'
        ),
    source_profile_id TEXT NOT NULL,
    session_external TEXT NOT NULL CHECK (length(session_external) >= 1),
    sequence_mode TEXT NOT NULL CHECK (sequence_mode IN ('SEQUENCED', 'SOURCE_TIME')),
    PRIMARY KEY (stream_generation_id),
    UNIQUE (
        stream_generation_id, scope_id, application_generation_id,
        acquisition_generation_id, generation_mandate_commitment_sha256,
        source_profile_id, session_external, sequence_mode
    ),
    UNIQUE (
        stream_generation_id, scope_id, acquisition_generation_id,
        generation_mandate_commitment_sha256, source_profile_id,
        session_external, sequence_mode
    ),
    FOREIGN KEY (scope_id, application_generation_id)
        REFERENCES acquisition_scope (scope_id, application_generation_id),
    FOREIGN KEY (
        acquisition_generation_id, scope_id,
        generation_mandate_commitment_sha256
    ) REFERENCES acquisition_generation (
        acquisition_generation_id, scope_id, mandate_commitment_sha256
    ),
    FOREIGN KEY (application_generation_id, source_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_market_source_profile_id
        )
);

CREATE INDEX ix_market_stream_authority_checkpoint_generation
ON market_stream_authority (acquisition_generation_id, scope_id, stream_generation_id);

CREATE TABLE market_cursor (
    stream_generation_id TEXT PRIMARY KEY,
    scope_id INTEGER NOT NULL,
    application_generation_id TEXT NOT NULL,
    acquisition_generation_id TEXT NOT NULL,
    generation_mandate_commitment_sha256 TEXT NOT NULL,
    source_profile_id TEXT NOT NULL,
    session_external TEXT NOT NULL,
    sequence_mode TEXT NOT NULL,
    fixed_cursor_ordinal INTEGER NOT NULL CHECK (fixed_cursor_ordinal >= 0),
    published_head_ordinal INTEGER NOT NULL CHECK (published_head_ordinal >= 0),
    CHECK (fixed_cursor_ordinal <= published_head_ordinal),
    FOREIGN KEY (
        stream_generation_id, scope_id, application_generation_id,
        acquisition_generation_id, generation_mandate_commitment_sha256,
        source_profile_id, session_external, sequence_mode
    ) REFERENCES market_stream_authority (
        stream_generation_id, scope_id, application_generation_id,
        acquisition_generation_id, generation_mandate_commitment_sha256,
        source_profile_id, session_external, sequence_mode
    )
);

CREATE TABLE protection_authority (
    scope_id INTEGER PRIMARY KEY REFERENCES acquisition_scope (scope_id),
    authority_class TEXT NOT NULL
        CHECK (authority_class IN ('NORMAL', 'HARD_BAIL')),
    active_stream_generation_id TEXT,
    active_acquisition_generation_id TEXT,
    active_generation_mandate_commitment_sha256 TEXT,
    active_source_profile_id TEXT,
    active_session_external TEXT,
    active_sequence_mode TEXT,
    expected_controller_head_ordinal INTEGER NOT NULL
        CHECK (expected_controller_head_ordinal >= 0),
    state_commitment_sha256 TEXT NOT NULL
        CHECK (length(state_commitment_sha256) = 64 AND state_commitment_sha256 NOT GLOB '*[^0-9a-f]*'),
    version_ordinal INTEGER NOT NULL CHECK (version_ordinal >= 1),
    CHECK (
        (active_stream_generation_id IS NULL)
        = (active_acquisition_generation_id IS NULL)
        AND (active_stream_generation_id IS NULL)
        = (active_generation_mandate_commitment_sha256 IS NULL)
        AND (active_stream_generation_id IS NULL)
        = (active_source_profile_id IS NULL)
        AND (active_stream_generation_id IS NULL)
        = (active_session_external IS NULL)
        AND (active_stream_generation_id IS NULL)
        = (active_sequence_mode IS NULL)
    ),
    CHECK (
        authority_class = 'NORMAL'
        OR active_stream_generation_id IS NOT NULL
    ),
    FOREIGN KEY (
        active_stream_generation_id, scope_id,
        active_acquisition_generation_id,
        active_generation_mandate_commitment_sha256,
        active_source_profile_id,
        active_session_external, active_sequence_mode
    ) REFERENCES market_stream_authority (
        stream_generation_id, scope_id, acquisition_generation_id,
        generation_mandate_commitment_sha256, source_profile_id,
        session_external, sequence_mode
    )
);

CREATE INDEX ix_protection_authority_active_generation
    ON protection_authority (active_acquisition_generation_id, scope_id);

CREATE TRIGGER trg_schema_meta_immutable_update
    BEFORE UPDATE ON schema_meta
BEGIN
    SELECT RAISE (ABORT, 'schema_meta is immutable');
END;

CREATE TRIGGER trg_schema_meta_no_conflict_replace
    BEFORE INSERT ON schema_meta
    FOR EACH ROW
    WHEN EXISTS (SELECT 1 FROM schema_meta)
BEGIN
    SELECT RAISE (ABORT, 'schema metadata is already retained');
END;

CREATE TRIGGER trg_schema_meta_immutable_delete
    BEFORE DELETE ON schema_meta
BEGIN
    SELECT RAISE (ABORT, 'schema_meta is immutable');
END;

CREATE TRIGGER trg_acquisition_generation_no_conflict_replace
    BEFORE INSERT ON acquisition_generation
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acquisition_generation AS retained
             WHERE retained.acquisition_generation_id =
                    NEW.acquisition_generation_id
                OR (
                    retained.scope_id = NEW.scope_id
                    AND retained.successor_ordinal = NEW.successor_ordinal
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'acquisition generation identity is already retained');
END;

CREATE TRIGGER trg_execution_profile_no_conflict_replace
    BEFORE INSERT ON execution_connection_profile
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM execution_connection_profile AS retained
             WHERE retained.connection_profile_id = NEW.connection_profile_id
                OR retained.profile_commitment_sha256 =
                    NEW.profile_commitment_sha256
        )
BEGIN
    SELECT RAISE (ABORT, 'execution profile identity is already retained');
END;

CREATE TRIGGER trg_market_profile_no_conflict_replace
    BEFORE INSERT ON market_data_source_profile
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM market_data_source_profile AS retained
             WHERE retained.market_source_profile_id =
                    NEW.market_source_profile_id
                OR retained.source_profile_commitment_sha256 =
                    NEW.source_profile_commitment_sha256
        )
BEGIN
    SELECT RAISE (ABORT, 'market profile identity is already retained');
END;

CREATE TRIGGER trg_application_generation_no_conflict_replace
    BEFORE INSERT ON application_generation
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM application_generation AS retained
             WHERE retained.application_generation_id =
                    NEW.application_generation_id
                OR retained.selected_execution_profile_id =
                    NEW.selected_execution_profile_id
        )
BEGIN
    SELECT RAISE (ABORT, 'application generation identity is already retained');
END;

CREATE TRIGGER trg_acquisition_scope_no_conflict_replace
    BEFORE INSERT ON acquisition_scope
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM acquisition_scope AS retained
             WHERE retained.scope_id = NEW.scope_id
                OR (
                    retained.application_generation_id =
                        NEW.application_generation_id
                    AND retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.symbol_text = NEW.symbol_text
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'acquisition scope identity is already retained');
END;

CREATE TRIGGER trg_kernel_checkpoint_no_conflict_replace
    BEFORE INSERT ON kernel_checkpoint
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM kernel_checkpoint AS retained
             WHERE retained.application_generation_id =
                    NEW.application_generation_id
        )
BEGIN
    SELECT RAISE (ABORT, 'kernel checkpoint identity is already retained');
END;

CREATE TRIGGER trg_symbol_controller_no_conflict_replace
    BEFORE INSERT ON symbol_controller
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM symbol_controller AS retained
             WHERE retained.scope_id = NEW.scope_id
        )
BEGIN
    SELECT RAISE (ABORT, 'symbol controller identity is already retained');
END;

CREATE TRIGGER trg_root_fill_no_conflict_replace
    BEFORE INSERT ON root_fill
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM root_fill AS retained
             WHERE retained.root_fill_key_id = NEW.root_fill_key_id
                OR (
                    retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.root_fill_external = NEW.root_fill_external
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'root fill identity is already retained');
END;

CREATE TRIGGER trg_execution_fact_no_conflict_replace
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM execution_fact AS retained
             WHERE retained.fact_id = NEW.fact_id
                OR (
                    retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.source_event_id = NEW.source_event_id
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'execution fact identity is already retained');
END;

CREATE TRIGGER trg_execution_fact_head_no_conflict_replace
    BEFORE INSERT ON execution_fact_head
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM execution_fact_head AS retained
             WHERE retained.root_fill_key_id = NEW.root_fill_key_id
                OR retained.fact_id = NEW.fact_id
        )
BEGIN
    SELECT RAISE (ABORT, 'execution fact head identity is already retained');
END;

CREATE TRIGGER trg_venue_effect_no_conflict_replace
    BEFORE INSERT ON venue_effect
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM venue_effect AS retained
             WHERE retained.effect_id = NEW.effect_id
                OR (
                    retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.effect_external = NEW.effect_external
                )
                OR (
                    retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.request_occurrence_external =
                        NEW.request_occurrence_external
                )
                OR (
                    NEW.client_order_external IS NOT NULL
                    AND retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.client_order_external = NEW.client_order_external
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'venue effect identity is already retained');
END;

CREATE TRIGGER trg_venue_owner_no_conflict_replace
    BEFORE INSERT ON venue_identity_owner
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM venue_identity_owner AS retained
             WHERE retained.execution_profile_id = NEW.execution_profile_id
               AND retained.owner_external = NEW.owner_external
        )
BEGIN
    SELECT RAISE (ABORT, 'venue owner identity is already retained');
END;

CREATE TRIGGER trg_venue_owner_requires_exact_admission_phase
    BEFORE INSERT ON venue_identity_owner
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM venue_effect AS effect
             WHERE effect.effect_id = NEW.effect_id
               AND (
                    (
                        effect.disposition = 'OPEN'
                        AND NEW.admitted_after_effect_closed = 0
                    )
                    OR (
                        effect.disposition IN ('CLOSED', 'INVALIDATED')
                        AND NEW.admitted_after_effect_closed = 1
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'venue owner admission phase must match exact canonical effect state'
    );
END;

CREATE TRIGGER trg_acquisition_root_route_no_conflict_replace
    BEFORE INSERT ON acquisition_root_route
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acquisition_root_route AS retained
             WHERE retained.root_fill_key_id = NEW.root_fill_key_id
        )
BEGIN
    SELECT RAISE (ABORT, 'acquisition root route is already retained');
END;

CREATE TRIGGER trg_acquisition_root_route_owner_single_binding
    BEFORE INSERT ON acquisition_root_route
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acquisition_root_route AS retained
             WHERE retained.effect_id = NEW.effect_id
               AND retained.owner_external = NEW.owner_external
               AND retained.observation_external = NEW.observation_external
               AND retained.scope_id = NEW.scope_id
               AND retained.execution_profile_id = NEW.execution_profile_id
               AND retained.acquisition_generation_id =
                    NEW.acquisition_generation_id
        )
BEGIN
    SELECT RAISE (ABORT, 'acquisition route owner is already bound');
END;

CREATE TRIGGER trg_acquisition_root_route_requires_exact_owner_root
    BEFORE INSERT ON acquisition_root_route
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM venue_identity_owner AS owner
             WHERE owner.effect_id = NEW.effect_id
               AND owner.owner_external = NEW.owner_external
               AND owner.observation_external = NEW.observation_external
               AND owner.scope_id = NEW.scope_id
               AND owner.execution_profile_id = NEW.execution_profile_id
               AND owner.owner_generation_id = NEW.acquisition_generation_id
               AND (
                    owner.root_fill_key_id IS NULL
                    OR owner.root_fill_key_id = NEW.root_fill_key_id
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition route must match the retained owner root'
    );
END;

CREATE TRIGGER trg_acquisition_root_route_advances_generation_head
    AFTER INSERT ON acquisition_root_route
    FOR EACH ROW
BEGIN
    UPDATE acquisition_generation_current
       SET current_economics_head_ordinal = COALESCE(
            (
                SELECT MAX(root.economics_head_ordinal)
                  FROM acquisition_root_route AS route
                  JOIN root_fill AS root
                    ON root.root_fill_key_id = route.root_fill_key_id
                   AND root.scope_id = route.scope_id
                 WHERE route.acquisition_generation_id =
                        NEW.acquisition_generation_id
                   AND route.scope_id = NEW.scope_id
            ),
            0
       )
     WHERE acquisition_generation_id = NEW.acquisition_generation_id
       AND scope_id = NEW.scope_id;
END;

CREATE TRIGGER trg_dispatch_claim_no_conflict_replace
    BEFORE INSERT ON dispatch_claim
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM dispatch_claim AS retained
             WHERE retained.claim_id = NEW.claim_id
                OR retained.effect_id = NEW.effect_id
                OR (
                    retained.execution_profile_id = NEW.execution_profile_id
                    AND retained.claim_occurrence_external =
                        NEW.claim_occurrence_external
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'dispatch claim identity is already retained');
END;

CREATE TRIGGER trg_acceptance_set_no_conflict_replace
    BEFORE INSERT ON acceptance_set
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM acceptance_set AS retained
             WHERE retained.acceptance_set_id = NEW.acceptance_set_id
                OR retained.effect_id = NEW.effect_id
        )
BEGIN
    SELECT RAISE (ABORT, 'acceptance set identity is already retained');
END;

CREATE TRIGGER trg_acceptance_evidence_no_conflict_replace
    BEFORE INSERT ON acceptance_evidence
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM acceptance_evidence AS retained
             WHERE retained.evidence_id = NEW.evidence_id
                OR retained.evidence_ordinal = NEW.evidence_ordinal
                OR (
                    NEW.evidence_kind = 'INVALIDATION'
                    AND retained.evidence_kind = 'INVALIDATION'
                    AND retained.effect_id = NEW.effect_id
                    AND retained.contradiction_owner_external =
                        NEW.contradiction_owner_external
                    AND retained.contradiction_observation_external =
                        NEW.contradiction_observation_external
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'acceptance evidence identity is already retained');
END;

CREATE TRIGGER trg_acceptance_evidence_requires_exact_authority
    BEFORE INSERT ON acceptance_evidence
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM acceptance_set AS accepted
             WHERE accepted.acceptance_set_id = NEW.acceptance_set_id
               AND accepted.effect_id = NEW.effect_id
        )
       OR (
            NEW.evidence_kind = 'INVALIDATION'
            AND NOT EXISTS (
                SELECT 1
                  FROM venue_identity_owner AS owner
                 WHERE owner.effect_id = NEW.effect_id
                   AND owner.owner_external =
                        NEW.contradiction_owner_external
                   AND owner.observation_external =
                        NEW.contradiction_observation_external
            )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acceptance evidence requires exact retained authority'
    );
END;

CREATE TRIGGER trg_closure_chain_no_conflict_replace
    BEFORE INSERT ON closure_chain
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM closure_chain AS retained
             WHERE retained.closure_id = NEW.closure_id
                OR (
                    NEW.predecessor_closure_id IS NOT NULL
                    AND retained.scope_id = NEW.scope_id
                    AND retained.owner_external = NEW.owner_external
                    AND retained.predecessor_closure_id =
                        NEW.predecessor_closure_id
                )
                OR (
                    NEW.predecessor_closure_id IS NULL
                    AND retained.scope_id = NEW.scope_id
                    AND retained.owner_external = NEW.owner_external
                    AND retained.predecessor_closure_id IS NULL
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'closure identity is already retained');
END;

CREATE TRIGGER trg_market_stream_no_conflict_replace
    BEFORE INSERT ON market_stream_authority
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM market_stream_authority AS retained
             WHERE retained.stream_generation_id = NEW.stream_generation_id
        )
BEGIN
    SELECT RAISE (ABORT, 'market stream identity is already retained');
END;

CREATE TRIGGER trg_market_cursor_no_conflict_replace
    BEFORE INSERT ON market_cursor
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM market_cursor AS retained
             WHERE retained.stream_generation_id = NEW.stream_generation_id
        )
BEGIN
    SELECT RAISE (ABORT, 'market cursor identity is already retained');
END;

CREATE TRIGGER trg_execution_profile_canonical_insert
    BEFORE INSERT ON execution_connection_profile
    FOR EACH ROW
    WHEN EXISTS (
        WITH RECURSIVE
        origins(value) AS (
            VALUES
                (NEW.trade_command_origin),
                (NEW.order_query_origin),
                (NEW.order_event_origin)
        ),
        rests(value, rest) AS (
            SELECT value, substr(value, 9) FROM origins
        ),
        parsed(value, rest, host, port, colon_count) AS (
            SELECT
                value,
                rest,
                CASE
                    WHEN instr(rest, ':') = 0 THEN rest
                    ELSE substr(rest, 1, instr(rest, ':') - 1)
                END,
                CASE
                    WHEN instr(rest, ':') = 0 THEN NULL
                    ELSE substr(rest, instr(rest, ':') + 1)
                END,
                length(rest) - length(replace(rest, ':', ''))
              FROM rests
        ),
        labels(value, host, port, colon_count, label, tail) AS (
            SELECT
                value,
                host,
                port,
                colon_count,
                CASE
                    WHEN instr(host, '.') = 0 THEN host
                    ELSE substr(host, 1, instr(host, '.') - 1)
                END,
                CASE
                    WHEN instr(host, '.') = 0 THEN ''
                    ELSE substr(host, instr(host, '.') + 1)
                END
              FROM parsed
            UNION ALL
            SELECT
                value,
                host,
                port,
                colon_count,
                CASE
                    WHEN instr(tail, '.') = 0 THEN tail
                    ELSE substr(tail, 1, instr(tail, '.') - 1)
                END,
                CASE
                    WHEN instr(tail, '.') = 0 THEN ''
                    ELSE substr(tail, instr(tail, '.') + 1)
                END
              FROM labels
             WHERE tail <> ''
        )
        SELECT 1
          FROM labels
         WHERE value NOT GLOB 'https://*'
            OR length(host) NOT BETWEEN 1 AND 253
            OR substr(host, -1, 1) NOT GLOB '[a-z0-9]'
            OR colon_count > 1
            OR length(label) NOT BETWEEN 1 AND 63
            OR substr(label, 1, 1) NOT GLOB '[a-z]'
            OR substr(label, -1, 1) NOT GLOB '[a-z0-9]'
            OR label GLOB '*[^a-z0-9-]*'
            OR (
                port IS NOT NULL
                AND (
                    port = ''
                    OR port GLOB '*[^0-9]*'
                    OR (length(port) > 1 AND substr(port, 1, 1) = '0')
                    OR CAST(port AS INTEGER) NOT BETWEEN 1 AND 65535
                    OR CAST(port AS INTEGER) = 443
                )
            )
    )
BEGIN
    SELECT RAISE (ABORT, 'execution profile origin is noncanonical');
END;

CREATE TRIGGER trg_execution_profile_version_canonical_insert
    BEFORE INSERT ON execution_connection_profile
    FOR EACH ROW
    WHEN EXISTS (
        WITH
        versions(value) AS (VALUES (NEW.adapter_contract_version)),
        first(value, first_dot) AS (
            SELECT value, instr(value, '.') FROM versions
        ),
        parts(major, minor, patch) AS (
            SELECT
                substr(value, 1, first_dot - 1),
                substr(
                    substr(value, first_dot + 1),
                    1,
                    instr(substr(value, first_dot + 1), '.') - 1
                ),
                substr(
                    substr(value, first_dot + 1),
                    instr(substr(value, first_dot + 1), '.') + 1
                )
              FROM first
        )
        SELECT 1
          FROM parts
         WHERE major = '' OR minor = '' OR patch = ''
            OR major GLOB '*[^0-9]*'
            OR minor GLOB '*[^0-9]*'
            OR patch GLOB '*[^0-9]*'
            OR patch LIKE '%.%'
            OR (length(major) > 1 AND substr(major, 1, 1) = '0')
            OR (length(minor) > 1 AND substr(minor, 1, 1) = '0')
            OR (length(patch) > 1 AND substr(patch, 1, 1) = '0')
    )
BEGIN
    SELECT RAISE (ABORT, 'execution profile version is noncanonical');
END;

CREATE TRIGGER trg_market_profile_canonical_insert
    BEFORE INSERT ON market_data_source_profile
    FOR EACH ROW
    WHEN EXISTS (
        WITH RECURSIVE
        parsed(value, host, port, colon_count) AS (
            SELECT
                NEW.source_origin,
                CASE
                    WHEN instr(substr(NEW.source_origin, 9), ':') = 0
                        THEN substr(NEW.source_origin, 9)
                    ELSE substr(
                        substr(NEW.source_origin, 9),
                        1,
                        instr(substr(NEW.source_origin, 9), ':') - 1
                    )
                END,
                CASE
                    WHEN instr(substr(NEW.source_origin, 9), ':') = 0 THEN NULL
                    ELSE substr(
                        substr(NEW.source_origin, 9),
                        instr(substr(NEW.source_origin, 9), ':') + 1
                    )
                END,
                length(substr(NEW.source_origin, 9))
                    - length(replace(substr(NEW.source_origin, 9), ':', ''))
        ),
        labels(value, host, port, colon_count, label, tail) AS (
            SELECT
                value,
                host,
                port,
                colon_count,
                CASE
                    WHEN instr(host, '.') = 0 THEN host
                    ELSE substr(host, 1, instr(host, '.') - 1)
                END,
                CASE
                    WHEN instr(host, '.') = 0 THEN ''
                    ELSE substr(host, instr(host, '.') + 1)
                END
              FROM parsed
            UNION ALL
            SELECT
                value,
                host,
                port,
                colon_count,
                CASE
                    WHEN instr(tail, '.') = 0 THEN tail
                    ELSE substr(tail, 1, instr(tail, '.') - 1)
                END,
                CASE
                    WHEN instr(tail, '.') = 0 THEN ''
                    ELSE substr(tail, instr(tail, '.') + 1)
                END
              FROM labels
             WHERE tail <> ''
        )
        SELECT 1
          FROM labels
         WHERE value NOT GLOB 'https://*'
            OR length(host) NOT BETWEEN 1 AND 253
            OR substr(host, -1, 1) NOT GLOB '[a-z0-9]'
            OR colon_count > 1
            OR length(label) NOT BETWEEN 1 AND 63
            OR substr(label, 1, 1) NOT GLOB '[a-z]'
            OR substr(label, -1, 1) NOT GLOB '[a-z0-9]'
            OR label GLOB '*[^a-z0-9-]*'
            OR (
                port IS NOT NULL
                AND (
                    port = ''
                    OR port GLOB '*[^0-9]*'
                    OR (length(port) > 1 AND substr(port, 1, 1) = '0')
                    OR CAST(port AS INTEGER) NOT BETWEEN 1 AND 65535
                    OR CAST(port AS INTEGER) = 443
                )
            )
    )
    OR EXISTS (
        WITH
        version(value) AS (VALUES (NEW.normalization_contract_version)),
        first(value, first_dot) AS (
            SELECT value, instr(value, '.') FROM version
        ),
        parts(major, minor, patch) AS (
            SELECT
                substr(value, 1, first_dot - 1),
                substr(
                    substr(value, first_dot + 1),
                    1,
                    instr(substr(value, first_dot + 1), '.') - 1
                ),
                substr(
                    substr(value, first_dot + 1),
                    instr(substr(value, first_dot + 1), '.') + 1
                )
              FROM first
        )
        SELECT 1
          FROM parts
         WHERE major = '' OR minor = '' OR patch = ''
            OR major GLOB '*[^0-9]*'
            OR minor GLOB '*[^0-9]*'
            OR patch GLOB '*[^0-9]*'
            OR patch LIKE '%.%'
            OR (length(major) > 1 AND substr(major, 1, 1) = '0')
            OR (length(minor) > 1 AND substr(minor, 1, 1) = '0')
            OR (length(patch) > 1 AND substr(patch, 1, 1) = '0')
    )
BEGIN
    SELECT RAISE (ABORT, 'market profile origin or version is noncanonical');
END;

CREATE TRIGGER trg_execution_profile_no_update
    BEFORE UPDATE ON execution_connection_profile
BEGIN
    SELECT RAISE (ABORT, 'execution_connection_profile rows are immutable');
END;

CREATE TRIGGER trg_execution_profile_no_delete
    BEFORE DELETE ON execution_connection_profile
BEGIN
    SELECT RAISE (ABORT, 'execution_connection_profile rows are retained');
END;

CREATE TRIGGER trg_market_source_profile_no_update
    BEFORE UPDATE ON market_data_source_profile
BEGIN
    SELECT RAISE (ABORT, 'market_data_source_profile rows are immutable');
END;

CREATE TRIGGER trg_market_source_profile_no_delete
    BEFORE DELETE ON market_data_source_profile
BEGIN
    SELECT RAISE (ABORT, 'market_data_source_profile rows are retained');
END;

CREATE TRIGGER trg_application_generation_no_update
    BEFORE UPDATE ON application_generation
BEGIN
    SELECT RAISE (ABORT, 'application_generation bindings are immutable');
END;

CREATE TRIGGER trg_application_generation_no_delete
    BEFORE DELETE ON application_generation
BEGIN
    SELECT RAISE (ABORT, 'application_generation rows are retained');
END;

CREATE TRIGGER trg_acquisition_scope_no_update
    BEFORE UPDATE ON acquisition_scope
BEGIN
    SELECT RAISE (ABORT, 'acquisition_scope rows are immutable');
END;

CREATE TRIGGER trg_acquisition_scope_no_delete
    BEFORE DELETE ON acquisition_scope
BEGIN
    SELECT RAISE (ABORT, 'acquisition_scope rows are retained');
END;

CREATE TRIGGER trg_acquisition_generation_binding_immutable
    BEFORE UPDATE OF acquisition_generation_id, scope_id, successor_ordinal,
        predecessor_generation_id, mandate_commitment_sha256,
        emergency_compatibility_sha256 ON acquisition_generation
    FOR EACH ROW
    WHEN NEW.acquisition_generation_id IS NOT OLD.acquisition_generation_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.successor_ordinal IS NOT OLD.successor_ordinal
      OR NEW.predecessor_generation_id IS NOT OLD.predecessor_generation_id
      OR NEW.mandate_commitment_sha256 IS NOT OLD.mandate_commitment_sha256
      OR NEW.emergency_compatibility_sha256
            IS NOT OLD.emergency_compatibility_sha256
BEGIN
    SELECT RAISE (ABORT, 'acquisition_generation binding is immutable');
END;

CREATE TRIGGER trg_acquisition_generation_retire_only
    BEFORE UPDATE OF status ON acquisition_generation
    FOR EACH ROW
    WHEN NOT (
        OLD.status = 'LIVE' AND NEW.status = 'RETIRED_UNSERVING'
    )
BEGIN
    SELECT RAISE (ABORT, 'acquisition_generation may only retire in place');
END;

CREATE TRIGGER trg_acquisition_generation_not_retired_while_controller_live
    BEFORE UPDATE OF status ON acquisition_generation
    FOR EACH ROW
    WHEN OLD.status = 'LIVE'
     AND NEW.status = 'RETIRED_UNSERVING'
     AND EXISTS (
            SELECT 1
              FROM symbol_controller AS controller
             WHERE controller.live_acquisition_generation_id =
                    OLD.acquisition_generation_id
               AND controller.scope_id = OLD.scope_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition_generation remains LIVE while selected by its controller'
    );
END;

CREATE TRIGGER trg_acquisition_generation_retire_requires_closed_authority
    BEFORE UPDATE OF status ON acquisition_generation
    FOR EACH ROW
    WHEN OLD.status = 'LIVE'
     AND NEW.status = 'RETIRED_UNSERVING'
     AND NOT EXISTS (
            SELECT 1
              FROM acquisition_generation_current AS current
             WHERE current.acquisition_generation_id =
                    OLD.acquisition_generation_id
               AND current.scope_id = OLD.scope_id
               AND current.unresolved_effect_count = 0
               AND current.active_protection_count = 0
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition generation retirement requires closed effects and non-serving protection'
    );
END;

CREATE TRIGGER trg_acquisition_generation_predecessor_valid
    BEFORE INSERT ON acquisition_generation
    FOR EACH ROW
    WHEN NEW.predecessor_generation_id IS NOT NULL
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition predecessor must be retired and compatibility-equal at the immediate prior ordinal of the same scope'
    )
    WHERE NOT EXISTS (
            SELECT 1
              FROM acquisition_generation AS predecessor
              JOIN acquisition_generation_current AS current
                ON current.acquisition_generation_id =
                    predecessor.acquisition_generation_id
               AND current.scope_id = predecessor.scope_id
             WHERE predecessor.acquisition_generation_id =
                   NEW.predecessor_generation_id
               AND predecessor.scope_id = NEW.scope_id
               AND predecessor.successor_ordinal = NEW.successor_ordinal - 1
               AND predecessor.status = 'RETIRED_UNSERVING'
               AND predecessor.emergency_compatibility_sha256 =
                    NEW.emergency_compatibility_sha256
               AND current.unresolved_effect_count = 0
               AND current.active_protection_count = 0
        );
END;

CREATE TRIGGER trg_acquisition_generation_initializes_current
    AFTER INSERT ON acquisition_generation
    FOR EACH ROW
BEGIN
    INSERT INTO acquisition_generation_current (
        acquisition_generation_id, scope_id,
        current_economics_head_ordinal,
        unresolved_effect_count, active_protection_count
    ) VALUES (
        NEW.acquisition_generation_id, NEW.scope_id, 0, 0, 0
    );
END;

CREATE TRIGGER trg_acquisition_generation_current_no_conflict_replace
    BEFORE INSERT ON acquisition_generation_current
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acquisition_generation_current AS retained
             WHERE retained.acquisition_generation_id =
                    NEW.acquisition_generation_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition generation current proof is already retained'
    );
END;

CREATE TRIGGER trg_acquisition_generation_current_exact
    BEFORE UPDATE ON acquisition_generation_current
    FOR EACH ROW
    WHEN NEW.acquisition_generation_id IS NOT OLD.acquisition_generation_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.current_economics_head_ordinal <> COALESCE(
            (
                SELECT MAX(root.economics_head_ordinal)
                  FROM acquisition_root_route AS route
                  JOIN root_fill AS root
                    ON root.root_fill_key_id = route.root_fill_key_id
                   AND root.scope_id = route.scope_id
                 WHERE route.acquisition_generation_id =
                        NEW.acquisition_generation_id
                   AND route.scope_id = NEW.scope_id
            ),
            0
        )
      OR NEW.unresolved_effect_count <> (
            SELECT COUNT(*)
              FROM venue_effect AS effect
             WHERE effect.acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND effect.scope_id = NEW.scope_id
               AND (
                    effect.disposition <> 'CLOSED'
                    OR EXISTS (
                        SELECT 1
                          FROM venue_identity_owner AS owner
                         WHERE owner.effect_id = effect.effect_id
                           AND owner.admitted_after_effect_closed = 1
                    )
               )
        )
      OR NEW.active_protection_count <> (
            SELECT COUNT(*)
              FROM protection_authority AS protection
             WHERE protection.active_acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND protection.scope_id = NEW.scope_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition generation current proof must match direct authority'
    );
END;

CREATE TRIGGER trg_acquisition_generation_current_no_delete
    BEFORE DELETE ON acquisition_generation_current
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition_generation_current rows are retained'
    );
END;

CREATE TRIGGER trg_acquisition_generation_no_delete
    BEFORE DELETE ON acquisition_generation
BEGIN
    SELECT RAISE (ABORT, 'acquisition_generation rows are retained');
END;

CREATE TRIGGER trg_kernel_checkpoint_head_monotonic
    BEFORE UPDATE OF currentness_head_ordinal ON kernel_checkpoint
    FOR EACH ROW
    WHEN NEW.currentness_head_ordinal < OLD.currentness_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'kernel_checkpoint head may only advance');
END;

CREATE TRIGGER trg_kernel_checkpoint_identity_immutable
    BEFORE UPDATE OF application_generation_id ON kernel_checkpoint
    FOR EACH ROW
    WHEN NEW.application_generation_id IS NOT OLD.application_generation_id
BEGIN
    SELECT RAISE (ABORT, 'kernel_checkpoint identity is immutable');
END;

CREATE TRIGGER trg_kernel_checkpoint_versioned_replace
    BEFORE UPDATE ON kernel_checkpoint
    FOR EACH ROW
    WHEN NEW.checkpoint_version_ordinal < OLD.checkpoint_version_ordinal
      OR (
            (
                NEW.currentness_head_ordinal IS NOT OLD.currentness_head_ordinal
                OR NEW.checkpoint_sha256 IS NOT OLD.checkpoint_sha256
            )
            AND NEW.checkpoint_version_ordinal
                <= OLD.checkpoint_version_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'kernel checkpoint version must advance');
END;

CREATE TRIGGER trg_kernel_checkpoint_no_delete
    BEFORE DELETE ON kernel_checkpoint
BEGIN
    SELECT RAISE (ABORT, 'kernel_checkpoint rows are retained');
END;

CREATE TRIGGER trg_symbol_controller_head_monotonic
    BEFORE UPDATE OF currentness_head_ordinal ON symbol_controller
    FOR EACH ROW
    WHEN NEW.currentness_head_ordinal < OLD.currentness_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'symbol_controller head may only advance');
END;

CREATE TRIGGER trg_symbol_controller_identity_immutable
    BEFORE UPDATE OF scope_id, application_generation_id, execution_profile_id,
        emergency_compatibility_sha256 ON symbol_controller
    FOR EACH ROW
    WHEN NEW.scope_id IS NOT OLD.scope_id
      OR NEW.application_generation_id IS NOT OLD.application_generation_id
      OR NEW.execution_profile_id IS NOT OLD.execution_profile_id
      OR NEW.emergency_compatibility_sha256
            IS NOT OLD.emergency_compatibility_sha256
BEGIN
    SELECT RAISE (ABORT, 'symbol_controller identity is immutable');
END;

CREATE TRIGGER trg_symbol_controller_live_generation_valid_insert
    BEFORE INSERT ON symbol_controller
    FOR EACH ROW
    WHEN NEW.live_acquisition_generation_id IS NOT NULL
     AND NOT EXISTS (
            SELECT 1
              FROM acquisition_generation AS generation
             WHERE generation.acquisition_generation_id =
                    NEW.live_acquisition_generation_id
               AND generation.scope_id = NEW.scope_id
               AND generation.status = 'LIVE'
               AND generation.emergency_compatibility_sha256 =
                    NEW.emergency_compatibility_sha256
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'symbol_controller live generation must be LIVE, same-scope, and compatible'
    );
END;

CREATE TRIGGER trg_symbol_controller_live_generation_valid_update
    BEFORE UPDATE OF live_acquisition_generation_id,
        emergency_compatibility_sha256 ON symbol_controller
    FOR EACH ROW
    WHEN NEW.live_acquisition_generation_id IS NOT NULL
     AND NOT EXISTS (
            SELECT 1
              FROM acquisition_generation AS generation
             WHERE generation.acquisition_generation_id =
                    NEW.live_acquisition_generation_id
               AND generation.scope_id = NEW.scope_id
               AND generation.status = 'LIVE'
               AND generation.emergency_compatibility_sha256 =
                    NEW.emergency_compatibility_sha256
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'symbol_controller live generation must be LIVE, same-scope, and compatible'
    );
END;

CREATE TRIGGER trg_symbol_controller_generation_rebind_requires_flat_consistent
    BEFORE UPDATE OF live_acquisition_generation_id ON symbol_controller
    FOR EACH ROW
    WHEN NEW.live_acquisition_generation_id
            IS NOT OLD.live_acquisition_generation_id
     AND (
            OLD.aggregate_quantity <> 0
            OR NEW.aggregate_quantity <> 0
            OR OLD.integrity_state <> 'CONSISTENT'
            OR NEW.integrity_state <> 'CONSISTENT'
            OR (
                OLD.live_acquisition_generation_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                      FROM acquisition_generation_current AS current
                     WHERE current.acquisition_generation_id =
                            OLD.live_acquisition_generation_id
                       AND current.scope_id = OLD.scope_id
                       AND current.unresolved_effect_count = 0
                       AND current.active_protection_count = 0
                )
            )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition generation rebind requires flat consistent closed authority'
    );
END;

CREATE TRIGGER trg_symbol_controller_versioned_replace
    BEFORE UPDATE ON symbol_controller
    FOR EACH ROW
    WHEN NEW.controller_version_ordinal < OLD.controller_version_ordinal
      OR (
            (
                NEW.live_acquisition_generation_id
                    IS NOT OLD.live_acquisition_generation_id
                OR NEW.aggregate_quantity IS NOT OLD.aggregate_quantity
                OR NEW.integrity_state IS NOT OLD.integrity_state
                OR NEW.currentness_head_ordinal
                    IS NOT OLD.currentness_head_ordinal
            )
            AND NEW.controller_version_ordinal
                <= OLD.controller_version_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'symbol controller version must advance');
END;

CREATE TRIGGER trg_symbol_controller_payload_advances_head
    BEFORE UPDATE OF live_acquisition_generation_id, aggregate_quantity,
        integrity_state
        ON symbol_controller
    FOR EACH ROW
    WHEN (
            NEW.live_acquisition_generation_id
                IS NOT OLD.live_acquisition_generation_id
            OR NEW.aggregate_quantity IS NOT OLD.aggregate_quantity
            OR NEW.integrity_state IS NOT OLD.integrity_state
        )
      AND NEW.currentness_head_ordinal <= OLD.currentness_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'symbol controller head must advance');
END;

CREATE TRIGGER trg_symbol_controller_aggregate_exact_insert
    BEFORE INSERT ON symbol_controller
    FOR EACH ROW
    WHEN NEW.aggregate_quantity <> COALESCE(
            (
                SELECT SUM(
                    CASE root.current_side
                        WHEN 'BUY' THEN root.current_quantity
                        ELSE -root.current_quantity
                    END
                )
                  FROM root_fill AS root
                 WHERE root.scope_id = NEW.scope_id
                   AND root.current_fact_id IS NOT NULL
            ),
            0
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'symbol controller aggregate must equal canonical root economics'
    );
END;

CREATE TRIGGER trg_symbol_controller_aggregate_exact_update
    BEFORE UPDATE OF aggregate_quantity ON symbol_controller
    FOR EACH ROW
    WHEN NEW.aggregate_quantity <> COALESCE(
            (
                SELECT SUM(
                    CASE root.current_side
                        WHEN 'BUY' THEN root.current_quantity
                        ELSE -root.current_quantity
                    END
                )
                  FROM root_fill AS root
                 WHERE root.scope_id = NEW.scope_id
                   AND root.current_fact_id IS NOT NULL
            ),
            0
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'symbol controller aggregate must equal canonical root economics'
    );
END;

CREATE TRIGGER trg_symbol_controller_integrity_exact_insert
    BEFORE INSERT ON symbol_controller
    FOR EACH ROW
    WHEN NEW.integrity_state <> CASE
            WHEN NEW.aggregate_quantity < 0
                THEN 'NEGATIVE_POSITION_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM root_fill AS root
                     WHERE root.scope_id = NEW.scope_id
                       AND root.current_fact_id IS NOT NULL
                       AND NOT EXISTS (
                            SELECT 1
                              FROM acquisition_root_route AS route
                             WHERE route.root_fill_key_id =
                                    root.root_fill_key_id
                               AND route.scope_id = root.scope_id
                               AND route.application_generation_id =
                                    root.application_generation_id
                               AND route.execution_profile_id =
                                    root.execution_profile_id
                        )
                )
                THEN 'UNMATCHED_LINEAGE_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM venue_effect AS effect
                     WHERE effect.scope_id = NEW.scope_id
                       AND (
                            effect.disposition = 'INVALIDATED'
                            OR EXISTS (
                                SELECT 1
                                  FROM venue_identity_owner AS owner
                                 WHERE owner.effect_id = effect.effect_id
                                   AND owner.admitted_after_effect_closed = 1
                            )
                       )
                )
                THEN 'UNRESOLVED_VENUE_QUARANTINED'
            ELSE 'CONSISTENT'
        END
BEGIN
    SELECT RAISE (ABORT, 'symbol controller integrity must match economics');
END;

CREATE TRIGGER trg_symbol_controller_integrity_sticky_update
    BEFORE UPDATE OF aggregate_quantity, integrity_state ON symbol_controller
    FOR EACH ROW
    WHEN NEW.integrity_state <> CASE
            WHEN NEW.aggregate_quantity < 0
                THEN 'NEGATIVE_POSITION_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM root_fill AS root
                     WHERE root.scope_id = NEW.scope_id
                       AND root.current_fact_id IS NOT NULL
                       AND NOT EXISTS (
                            SELECT 1
                              FROM acquisition_root_route AS route
                             WHERE route.root_fill_key_id =
                                    root.root_fill_key_id
                               AND route.scope_id = root.scope_id
                               AND route.application_generation_id =
                                    root.application_generation_id
                               AND route.execution_profile_id =
                                    root.execution_profile_id
                        )
                )
                THEN 'UNMATCHED_LINEAGE_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM venue_effect AS effect
                     WHERE effect.scope_id = NEW.scope_id
                       AND (
                            effect.disposition = 'INVALIDATED'
                            OR EXISTS (
                                SELECT 1
                                  FROM venue_identity_owner AS owner
                                 WHERE owner.effect_id = effect.effect_id
                                   AND owner.admitted_after_effect_closed = 1
                            )
                       )
                )
                THEN 'UNRESOLVED_VENUE_QUARANTINED'
            WHEN OLD.integrity_state = 'MIXED_GENERATION_RECOVERY'
             AND NEW.aggregate_quantity = 0
             AND EXISTS (
                    SELECT 1
                      FROM execution_fact AS fact
                      JOIN root_fill AS root
                        ON root.root_fill_key_id = fact.root_fill_key_id
                       AND root.current_fact_id = fact.fact_id
                      JOIN acquisition_root_route AS route
                        ON route.root_fill_key_id = fact.root_fill_key_id
                       AND route.scope_id = fact.scope_id
                     WHERE fact.scope_id = NEW.scope_id
                       AND fact.fact_ordinal = (
                            SELECT MAX(candidate.fact_ordinal)
                              FROM execution_fact AS candidate
                        )
                       AND route.acquisition_generation_id =
                            NEW.live_acquisition_generation_id
                       AND (
                            fact.predecessor_fact_id IS NULL
                            OR NOT EXISTS (
                                SELECT 1
                                  FROM execution_fact AS predecessor
                                 WHERE predecessor.fact_id =
                                        fact.predecessor_fact_id
                                   AND predecessor.side IS fact.side
                                   AND predecessor.quantity IS fact.quantity
                                   AND predecessor.price_present
                                        IS fact.price_present
                                   AND predecessor.price_units IS fact.price_units
                                   AND predecessor.scale_sign IS fact.scale_sign
                                   AND predecessor.scale_digits
                                        IS fact.scale_digits
                                   AND predecessor.scale_exponent
                                        IS fact.scale_exponent
                                   AND predecessor.tick_units IS fact.tick_units
                                   AND predecessor.tick_scale_sign
                                        IS fact.tick_scale_sign
                                   AND predecessor.tick_scale_digits
                                        IS fact.tick_scale_digits
                                   AND predecessor.tick_scale_exponent
                                        IS fact.tick_scale_exponent
                            )
                        )
                )
                THEN 'CONSISTENT'
            WHEN OLD.integrity_state <> 'CONSISTENT'
                THEN OLD.integrity_state
            WHEN NEW.integrity_state = 'MIXED_GENERATION_RECOVERY'
             AND EXISTS (
                    SELECT 1
                      FROM root_fill AS root
                      JOIN acquisition_root_route AS route
                        ON route.root_fill_key_id = root.root_fill_key_id
                       AND route.scope_id = root.scope_id
                      JOIN acquisition_generation AS generation
                        ON generation.acquisition_generation_id =
                            route.acquisition_generation_id
                       AND generation.scope_id = route.scope_id
                     WHERE root.scope_id = NEW.scope_id
                       AND root.current_fact_id IS NOT NULL
                       AND generation.status = 'RETIRED_UNSERVING'
                )
                THEN 'MIXED_GENERATION_RECOVERY'
            ELSE 'CONSISTENT'
        END
BEGIN
    SELECT RAISE (
        ABORT,
        'controller integrity is exact and quarantine cannot clear in place'
    );
END;

CREATE TRIGGER trg_symbol_controller_no_delete
    BEFORE DELETE ON symbol_controller
BEGIN
    SELECT RAISE (ABORT, 'symbol_controller rows are retained');
END;

CREATE TRIGGER trg_root_fill_identity_immutable
    BEFORE UPDATE OF root_fill_key_id, scope_id, application_generation_id,
        execution_profile_id, owner_generation_id, root_fill_external ON root_fill
    FOR EACH ROW
    WHEN NEW.root_fill_key_id IS NOT OLD.root_fill_key_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.application_generation_id IS NOT OLD.application_generation_id
      OR NEW.execution_profile_id IS NOT OLD.execution_profile_id
      OR NEW.owner_generation_id IS NOT OLD.owner_generation_id
      OR NEW.root_fill_external IS NOT OLD.root_fill_external
BEGIN
    SELECT RAISE (ABORT, 'root_fill identity is immutable');
END;

CREATE TRIGGER trg_root_fill_economics_monotonic
    BEFORE UPDATE OF current_fact_id, current_kind, current_authority,
        current_side, current_quantity, price_present, price_units,
        scale_sign, scale_digits, scale_exponent, tick_units,
        tick_scale_sign, tick_scale_digits, tick_scale_exponent,
        economics_head_ordinal ON root_fill
    FOR EACH ROW
    WHEN NEW.economics_head_ordinal < OLD.economics_head_ordinal
      OR (
            NEW.current_fact_id IS NOT OLD.current_fact_id
            AND NEW.economics_head_ordinal <= OLD.economics_head_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'root_fill economics head must advance');
END;

CREATE TRIGGER trg_root_fill_no_delete
    BEFORE DELETE ON root_fill
BEGIN
    SELECT RAISE (ABORT, 'root_fill rows are retained');
END;

CREATE TRIGGER trg_root_fill_head_is_authenticated
    BEFORE UPDATE OF current_fact_id, current_kind, current_authority,
        current_side, current_quantity, price_present, price_units,
        scale_sign, scale_digits, scale_exponent, tick_units,
        tick_scale_sign, tick_scale_digits, tick_scale_exponent,
        economics_head_ordinal ON root_fill
    FOR EACH ROW
    WHEN (
            NEW.current_fact_id IS NOT OLD.current_fact_id
            OR NEW.current_kind IS NOT OLD.current_kind
            OR NEW.current_authority IS NOT OLD.current_authority
            OR NEW.current_side IS NOT OLD.current_side
            OR NEW.current_quantity IS NOT OLD.current_quantity
            OR NEW.price_present IS NOT OLD.price_present
            OR NEW.price_units IS NOT OLD.price_units
            OR NEW.scale_sign IS NOT OLD.scale_sign
            OR NEW.scale_digits IS NOT OLD.scale_digits
            OR NEW.scale_exponent IS NOT OLD.scale_exponent
            OR NEW.tick_units IS NOT OLD.tick_units
            OR NEW.tick_scale_sign IS NOT OLD.tick_scale_sign
            OR NEW.tick_scale_digits IS NOT OLD.tick_scale_digits
            OR NEW.tick_scale_exponent IS NOT OLD.tick_scale_exponent
            OR NEW.economics_head_ordinal IS NOT OLD.economics_head_ordinal
        )
     AND NOT EXISTS (
            SELECT 1
              FROM execution_fact_head AS head
              JOIN execution_fact AS fact
                ON fact.root_fill_key_id = head.root_fill_key_id
               AND fact.fact_id = head.fact_id
               AND fact.fact_ordinal = head.fact_ordinal
             WHERE head.root_fill_key_id = NEW.root_fill_key_id
               AND fact.fact_id = NEW.current_fact_id
               AND fact.fact_ordinal = NEW.economics_head_ordinal
               AND fact.kind = NEW.current_kind
               AND fact.authority = NEW.current_authority
               AND fact.side = NEW.current_side
               AND fact.quantity = NEW.current_quantity
               AND fact.price_present = NEW.price_present
               AND fact.price_units = NEW.price_units
               AND fact.scale_sign = NEW.scale_sign
               AND fact.scale_digits = NEW.scale_digits
               AND fact.scale_exponent = NEW.scale_exponent
               AND fact.tick_units = NEW.tick_units
               AND fact.tick_scale_sign = NEW.tick_scale_sign
               AND fact.tick_scale_digits = NEW.tick_scale_digits
               AND fact.tick_scale_exponent = NEW.tick_scale_exponent
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'root_fill economics must equal the exact current execution fact'
    );
END;

CREATE TRIGGER trg_execution_fact_scope_coordinates
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acquisition_scope AS scope
             WHERE scope.scope_id = NEW.scope_id
               AND (
                    scope.application_generation_id
                    <> NEW.application_generation_id
                 OR scope.execution_profile_id <> NEW.execution_profile_id
                )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'execution_fact profile coordinates must equal their scope coordinates'
    );
END;

CREATE TRIGGER trg_execution_fact_predecessor_exists_inside_root
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN NEW.predecessor_fact_id IS NOT NULL
     AND NEW.predecessor_fact_id <> NEW.fact_id
     AND NOT EXISTS (
            SELECT 1
              FROM execution_fact AS predecessor
             WHERE predecessor.fact_id = NEW.predecessor_fact_id
               AND predecessor.root_fill_key_id = NEW.root_fill_key_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'execution fact predecessor must exist inside the same root'
    );
END;

CREATE TRIGGER trg_execution_fact_predecessor_is_current_head
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN NEW.predecessor_fact_id IS NOT NULL
     AND EXISTS (
            SELECT 1
              FROM execution_fact AS predecessor
             WHERE predecessor.fact_id = NEW.predecessor_fact_id
               AND predecessor.root_fill_key_id = NEW.root_fill_key_id
        )
     AND NOT EXISTS (
            SELECT 1
              FROM execution_fact_head AS head
             WHERE head.root_fill_key_id = NEW.root_fill_key_id
               AND head.fact_id = NEW.predecessor_fact_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'execution fact predecessor must be the current root head'
    );
END;

CREATE TRIGGER trg_execution_fact_revision_exact_predecessor_scope
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN NEW.predecessor_fact_id IS NOT NULL
     AND NOT EXISTS (
            SELECT 1
              FROM execution_fact AS predecessor
             WHERE predecessor.fact_id = NEW.predecessor_fact_id
               AND predecessor.root_fill_key_id = NEW.root_fill_key_id
               AND predecessor.scope_id = NEW.scope_id
               AND predecessor.application_generation_id =
                    NEW.application_generation_id
               AND predecessor.execution_profile_id = NEW.execution_profile_id
               AND predecessor.order_external = NEW.order_external
               AND predecessor.side = NEW.side
               AND predecessor.authority = 'BROKER_AUTHORITATIVE'
               AND NEW.authority = 'BROKER_AUTHORITATIVE'
        )
BEGIN
    SELECT RAISE (ABORT, 'revision must preserve exact predecessor scope');
END;

CREATE TRIGGER trg_execution_fact_global_sequence_no_gap
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN NEW.fact_ordinal <> COALESCE(
            (SELECT MAX(fact.fact_ordinal) FROM execution_fact AS fact),
            0
        ) + 1
BEGIN
    SELECT RAISE (ABORT, 'fact ordinal must be next global execution sequence');
END;

CREATE TRIGGER trg_execution_fact_ordinal_advances
    BEFORE INSERT ON execution_fact
    FOR EACH ROW
    WHEN NEW.predecessor_fact_id IS NOT NULL
     AND EXISTS (
            SELECT 1
              FROM execution_fact AS predecessor
             WHERE predecessor.fact_id = NEW.predecessor_fact_id
               AND predecessor.root_fill_key_id = NEW.root_fill_key_id
               AND NEW.fact_ordinal <= predecessor.fact_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'execution fact ordinal must strictly advance');
END;

CREATE TRIGGER trg_execution_fact_append_only_update
    BEFORE UPDATE ON execution_fact
BEGIN
    SELECT RAISE (ABORT, 'execution_fact rows are append-only');
END;

CREATE TRIGGER trg_execution_fact_append_only_delete
    BEFORE DELETE ON execution_fact
BEGIN
    SELECT RAISE (ABORT, 'execution_fact rows are append-only');
END;

CREATE TRIGGER trg_execution_fact_maintains_direct_head
    AFTER INSERT ON execution_fact
    FOR EACH ROW
BEGIN
    INSERT INTO execution_fact_head (
        root_fill_key_id, fact_id, fact_ordinal
    )
    SELECT NEW.root_fill_key_id, NEW.fact_id, NEW.fact_ordinal
     WHERE NEW.predecessor_fact_id IS NULL;

    UPDATE execution_fact_head
       SET fact_id = NEW.fact_id,
           fact_ordinal = NEW.fact_ordinal
     WHERE NEW.predecessor_fact_id IS NOT NULL
       AND root_fill_key_id = NEW.root_fill_key_id
       AND fact_id = NEW.predecessor_fact_id;

    UPDATE root_fill
       SET current_fact_id = NEW.fact_id,
           current_kind = NEW.kind,
           current_authority = NEW.authority,
           current_side = NEW.side,
           current_quantity = NEW.quantity,
           price_present = NEW.price_present,
           price_units = NEW.price_units,
           scale_sign = NEW.scale_sign,
           scale_digits = NEW.scale_digits,
           scale_exponent = NEW.scale_exponent,
           tick_units = NEW.tick_units,
           tick_scale_sign = NEW.tick_scale_sign,
           tick_scale_digits = NEW.tick_scale_digits,
           tick_scale_exponent = NEW.tick_scale_exponent,
           economics_head_ordinal = NEW.fact_ordinal
     WHERE root_fill_key_id = NEW.root_fill_key_id;

    UPDATE symbol_controller
       SET aggregate_quantity = COALESCE(
                (
                    SELECT SUM(
                        CASE root.current_side
                            WHEN 'BUY' THEN root.current_quantity
                            ELSE -root.current_quantity
                        END
                    )
                      FROM root_fill AS root
                     WHERE root.scope_id = NEW.scope_id
                       AND root.current_fact_id IS NOT NULL
                ),
                0
           ),
           integrity_state = CASE
                WHEN COALESCE(
                        (
                            SELECT SUM(
                                CASE root.current_side
                                    WHEN 'BUY' THEN root.current_quantity
                                    ELSE -root.current_quantity
                                END
                            )
                              FROM root_fill AS root
                             WHERE root.scope_id = NEW.scope_id
                               AND root.current_fact_id IS NOT NULL
                        ),
                        0
                    ) < 0
                    THEN 'NEGATIVE_POSITION_QUARANTINED'
                WHEN EXISTS (
                        SELECT 1
                          FROM root_fill AS root
                         WHERE root.scope_id = NEW.scope_id
                           AND root.current_fact_id IS NOT NULL
                           AND NOT EXISTS (
                                SELECT 1
                                  FROM acquisition_root_route AS route
                                 WHERE route.root_fill_key_id =
                                        root.root_fill_key_id
                                   AND route.scope_id = root.scope_id
                                   AND route.application_generation_id =
                                        root.application_generation_id
                                   AND route.execution_profile_id =
                                        root.execution_profile_id
                            )
                    )
                    THEN 'UNMATCHED_LINEAGE_QUARANTINED'
                WHEN EXISTS (
                        SELECT 1
                          FROM venue_effect AS effect
                         WHERE effect.scope_id = NEW.scope_id
                           AND effect.disposition = 'INVALIDATED'
                    )
                    THEN 'UNRESOLVED_VENUE_QUARANTINED'
                WHEN integrity_state = 'MIXED_GENERATION_RECOVERY'
                 AND COALESCE(
                        (
                            SELECT SUM(
                                CASE root.current_side
                                    WHEN 'BUY' THEN root.current_quantity
                                    ELSE -root.current_quantity
                                END
                            )
                              FROM root_fill AS root
                             WHERE root.scope_id = NEW.scope_id
                               AND root.current_fact_id IS NOT NULL
                        ),
                        0
                    ) = 0
                 AND EXISTS (
                        SELECT 1
                          FROM acquisition_root_route AS route
                         WHERE route.root_fill_key_id = NEW.root_fill_key_id
                           AND route.scope_id = NEW.scope_id
                           AND route.acquisition_generation_id =
                                live_acquisition_generation_id
                           AND (
                                NEW.predecessor_fact_id IS NULL
                                OR NOT EXISTS (
                                    SELECT 1
                                      FROM execution_fact AS predecessor
                                     WHERE predecessor.fact_id =
                                            NEW.predecessor_fact_id
                                       AND predecessor.side IS NEW.side
                                       AND predecessor.quantity IS NEW.quantity
                                       AND predecessor.price_present
                                            IS NEW.price_present
                                       AND predecessor.price_units
                                            IS NEW.price_units
                                       AND predecessor.scale_sign
                                            IS NEW.scale_sign
                                       AND predecessor.scale_digits
                                            IS NEW.scale_digits
                                       AND predecessor.scale_exponent
                                            IS NEW.scale_exponent
                                       AND predecessor.tick_units
                                            IS NEW.tick_units
                                       AND predecessor.tick_scale_sign
                                            IS NEW.tick_scale_sign
                                       AND predecessor.tick_scale_digits
                                            IS NEW.tick_scale_digits
                                       AND predecessor.tick_scale_exponent
                                            IS NEW.tick_scale_exponent
                                )
                            )
                    )
                    THEN 'CONSISTENT'
                WHEN integrity_state <> 'CONSISTENT'
                    THEN integrity_state
                WHEN EXISTS (
                        SELECT 1
                          FROM acquisition_root_route AS route
                          JOIN acquisition_generation AS generation
                            ON generation.acquisition_generation_id =
                                route.acquisition_generation_id
                           AND generation.scope_id = route.scope_id
                         WHERE route.root_fill_key_id =
                                NEW.root_fill_key_id
                           AND generation.status = 'RETIRED_UNSERVING'
                    )
                 AND (
                        NEW.predecessor_fact_id IS NULL
                        OR EXISTS (
                            SELECT 1
                              FROM execution_fact AS predecessor
                             WHERE predecessor.fact_id =
                                    NEW.predecessor_fact_id
                               AND (
                                    predecessor.side IS NOT NEW.side
                                    OR predecessor.quantity IS NOT NEW.quantity
                                    OR predecessor.price_present
                                        IS NOT NEW.price_present
                                    OR predecessor.price_units
                                        IS NOT NEW.price_units
                                    OR predecessor.scale_sign
                                        IS NOT NEW.scale_sign
                                    OR predecessor.scale_digits
                                        IS NOT NEW.scale_digits
                                    OR predecessor.scale_exponent
                                        IS NOT NEW.scale_exponent
                                    OR predecessor.tick_units
                                        IS NOT NEW.tick_units
                                    OR predecessor.tick_scale_sign
                                        IS NOT NEW.tick_scale_sign
                                    OR predecessor.tick_scale_digits
                                        IS NOT NEW.tick_scale_digits
                                    OR predecessor.tick_scale_exponent
                                        IS NOT NEW.tick_scale_exponent
                                )
                        )
                    )
                    THEN 'MIXED_GENERATION_RECOVERY'
                ELSE 'CONSISTENT'
            END,
           currentness_head_ordinal = currentness_head_ordinal + CASE
                WHEN EXISTS (
                        SELECT 1
                          FROM execution_fact AS predecessor
                          JOIN acquisition_root_route AS route
                            ON route.root_fill_key_id =
                                NEW.root_fill_key_id
                          JOIN acquisition_generation AS generation
                            ON generation.acquisition_generation_id =
                                route.acquisition_generation_id
                           AND generation.scope_id = route.scope_id
                         WHERE predecessor.fact_id =
                                NEW.predecessor_fact_id
                           AND generation.status = 'RETIRED_UNSERVING'
                           AND predecessor.side IS NEW.side
                           AND predecessor.quantity IS NEW.quantity
                           AND predecessor.price_present
                                IS NEW.price_present
                           AND predecessor.price_units IS NEW.price_units
                           AND predecessor.scale_sign IS NEW.scale_sign
                           AND predecessor.scale_digits IS NEW.scale_digits
                           AND predecessor.scale_exponent
                                IS NEW.scale_exponent
                           AND predecessor.tick_units IS NEW.tick_units
                           AND predecessor.tick_scale_sign
                                IS NEW.tick_scale_sign
                           AND predecessor.tick_scale_digits
                                IS NEW.tick_scale_digits
                           AND predecessor.tick_scale_exponent
                                IS NEW.tick_scale_exponent
                    )
                    THEN 0
                ELSE 1
            END,
           controller_version_ordinal = controller_version_ordinal + CASE
                WHEN EXISTS (
                        SELECT 1
                          FROM execution_fact AS predecessor
                          JOIN acquisition_root_route AS route
                            ON route.root_fill_key_id =
                                NEW.root_fill_key_id
                          JOIN acquisition_generation AS generation
                            ON generation.acquisition_generation_id =
                                route.acquisition_generation_id
                           AND generation.scope_id = route.scope_id
                         WHERE predecessor.fact_id =
                                NEW.predecessor_fact_id
                           AND generation.status = 'RETIRED_UNSERVING'
                           AND predecessor.side IS NEW.side
                           AND predecessor.quantity IS NEW.quantity
                           AND predecessor.price_present
                                IS NEW.price_present
                           AND predecessor.price_units IS NEW.price_units
                           AND predecessor.scale_sign IS NEW.scale_sign
                           AND predecessor.scale_digits IS NEW.scale_digits
                           AND predecessor.scale_exponent
                                IS NEW.scale_exponent
                           AND predecessor.tick_units IS NEW.tick_units
                           AND predecessor.tick_scale_sign
                                IS NEW.tick_scale_sign
                           AND predecessor.tick_scale_digits
                                IS NEW.tick_scale_digits
                           AND predecessor.tick_scale_exponent
                                IS NEW.tick_scale_exponent
                    )
                    THEN 0
                ELSE 1
            END
     WHERE scope_id = NEW.scope_id;

    UPDATE acquisition_generation_current
       SET current_economics_head_ordinal = (
            SELECT MAX(root.economics_head_ordinal)
              FROM acquisition_root_route AS route
              JOIN root_fill AS root
                ON root.root_fill_key_id = route.root_fill_key_id
               AND root.scope_id = route.scope_id
             WHERE route.acquisition_generation_id =
                    acquisition_generation_current.acquisition_generation_id
               AND route.scope_id =
                    acquisition_generation_current.scope_id
       )
     WHERE EXISTS (
            SELECT 1
              FROM acquisition_root_route AS route
             WHERE route.root_fill_key_id = NEW.root_fill_key_id
               AND route.scope_id = NEW.scope_id
               AND route.acquisition_generation_id =
                    acquisition_generation_current.acquisition_generation_id
       );
END;

CREATE TRIGGER trg_execution_fact_head_first_fill_only
    BEFORE INSERT ON execution_fact_head
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM execution_fact AS fact
             WHERE fact.root_fill_key_id = NEW.root_fill_key_id
               AND fact.fact_id = NEW.fact_id
               AND fact.fact_ordinal = NEW.fact_ordinal
               AND fact.kind = 'FILL'
               AND fact.predecessor_fact_id IS NULL
        )
BEGIN
    SELECT RAISE (ABORT, 'execution fact head must begin at the root FILL');
END;

CREATE TRIGGER trg_execution_fact_head_immediate_successor_only
    BEFORE UPDATE ON execution_fact_head
    FOR EACH ROW
    WHEN NEW.root_fill_key_id IS NOT OLD.root_fill_key_id
      OR NOT EXISTS (
            SELECT 1
              FROM execution_fact AS fact
             WHERE fact.root_fill_key_id = OLD.root_fill_key_id
               AND fact.fact_id = NEW.fact_id
               AND fact.fact_ordinal = NEW.fact_ordinal
               AND fact.predecessor_fact_id = OLD.fact_id
               AND fact.fact_ordinal > OLD.fact_ordinal
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'execution fact head must advance to its immediate successor'
    );
END;

CREATE TRIGGER trg_execution_fact_head_no_delete
    BEFORE DELETE ON execution_fact_head
BEGIN
    SELECT RAISE (ABORT, 'execution_fact_head rows are retained');
END;

CREATE TRIGGER trg_venue_effect_starts_open
    BEFORE INSERT ON venue_effect
    FOR EACH ROW
    WHEN NEW.lifecycle_state <> 'REQUESTED'
      OR NEW.disposition <> 'OPEN'
      OR NEW.closure_proof_kind IS NOT NULL
      OR NEW.closure_proof_digest IS NOT NULL
      OR NEW.closure_proof_evidence_id IS NOT NULL
      OR NEW.closure_proof_claim_id IS NOT NULL
BEGIN
    SELECT RAISE (ABORT, 'venue_effect starts OPEN and REQUESTED without proof');
END;

CREATE TRIGGER trg_venue_effect_requires_current_controller
    BEFORE INSERT ON venue_effect
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM symbol_controller AS controller
             WHERE controller.scope_id = NEW.scope_id
               AND controller.application_generation_id =
                    NEW.application_generation_id
               AND controller.execution_profile_id =
                    NEW.execution_profile_id
               AND controller.live_acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND controller.currentness_head_ordinal =
                    NEW.expected_controller_head_ordinal
               AND (
                    (
                        controller.integrity_state = 'CONSISTENT'
                        AND NEW.authority_class = 'NORMAL'
                        AND EXISTS (
                            SELECT 1
                              FROM protection_authority AS protection
                             WHERE protection.scope_id = NEW.scope_id
                               AND protection.authority_class = 'NORMAL'
                               AND protection.expected_controller_head_ordinal =
                                    NEW.expected_controller_head_ordinal
                               AND protection.version_ordinal =
                                    NEW.expected_protection_version_ordinal
                               AND (
                                    (
                                        protection.active_stream_generation_id
                                            IS NOT NULL
                                        AND protection.active_acquisition_generation_id =
                                            NEW.acquisition_generation_id
                                        AND protection.active_generation_mandate_commitment_sha256 =
                                            NEW.generation_mandate_commitment_sha256
                                    )
                                    OR (
                                        controller.aggregate_quantity = 0
                                        AND protection.active_stream_generation_id
                                            IS NULL
                                        AND protection.active_acquisition_generation_id
                                            IS NULL
                                        AND protection.active_generation_mandate_commitment_sha256
                                            IS NULL
                                        AND protection.active_source_profile_id
                                            IS NULL
                                        AND protection.active_session_external
                                            IS NULL
                                        AND protection.active_sequence_mode
                                            IS NULL
                                    )
                               )
                        )
                    )
                    OR (
                        controller.integrity_state =
                            'MIXED_GENERATION_RECOVERY'
                        AND NEW.authority_class = 'HARD_BAIL'
                        AND controller.aggregate_quantity > 0
                        AND NEW.quantity <= controller.aggregate_quantity
                        AND EXISTS (
                            SELECT 1
                              FROM protection_authority AS protection
                             WHERE protection.scope_id = NEW.scope_id
                               AND protection.authority_class = 'HARD_BAIL'
                               AND protection.expected_controller_head_ordinal =
                                    NEW.expected_controller_head_ordinal
                               AND protection.version_ordinal =
                                    NEW.expected_protection_version_ordinal
                               AND protection.active_acquisition_generation_id =
                                    NEW.acquisition_generation_id
                        )
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'venue effect requires the exact current controller head'
    );
END;

CREATE TRIGGER trg_venue_effect_updates_generation_current_on_insert
    AFTER INSERT ON venue_effect
    FOR EACH ROW
BEGIN
    UPDATE acquisition_generation_current
       SET unresolved_effect_count = (
            SELECT COUNT(*)
              FROM venue_effect AS effect
             WHERE effect.acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND effect.scope_id = NEW.scope_id
               AND (
                    effect.disposition <> 'CLOSED'
                    OR EXISTS (
                        SELECT 1
                          FROM venue_identity_owner AS owner
                         WHERE owner.effect_id = effect.effect_id
                           AND owner.admitted_after_effect_closed = 1
                    )
               )
       )
     WHERE acquisition_generation_id = NEW.acquisition_generation_id
       AND scope_id = NEW.scope_id;
END;

CREATE TRIGGER trg_venue_effect_updates_generation_current_on_disposition
    AFTER UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN NEW.disposition IS NOT OLD.disposition
BEGIN
    UPDATE acquisition_generation_current
       SET unresolved_effect_count = (
            SELECT COUNT(*)
              FROM venue_effect AS effect
             WHERE effect.acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND effect.scope_id = NEW.scope_id
               AND (
                    effect.disposition <> 'CLOSED'
                    OR EXISTS (
                        SELECT 1
                          FROM venue_identity_owner AS owner
                         WHERE owner.effect_id = effect.effect_id
                           AND owner.admitted_after_effect_closed = 1
                    )
               )
       )
     WHERE acquisition_generation_id = NEW.acquisition_generation_id
       AND scope_id = NEW.scope_id;
END;

CREATE TRIGGER trg_venue_effect_acceptance_transition
    BEFORE UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN NOT (
        NEW.disposition = OLD.disposition
        OR (OLD.disposition = 'OPEN' AND NEW.disposition = 'CLOSED')
        OR (
            OLD.disposition = 'CLOSED'
            AND NEW.disposition = 'INVALIDATED'
            AND EXISTS (
                SELECT 1
                  FROM acceptance_evidence AS evidence
                 WHERE evidence.effect_id = NEW.effect_id
                   AND evidence.evidence_kind = 'INVALIDATION'
            )
        )
    )
BEGIN
    SELECT RAISE (ABORT, 'venue_effect acceptance transition is invalid');
END;

CREATE TRIGGER trg_venue_effect_lifecycle_transition
    BEFORE UPDATE OF lifecycle_state ON venue_effect
    FOR EACH ROW
    WHEN NOT (
        NEW.lifecycle_state = OLD.lifecycle_state
        OR (
            OLD.lifecycle_state = 'REQUESTED'
            AND NEW.lifecycle_state IN (
                'CANCELED_BEFORE_DISPATCH', 'DISPATCH_CLAIMED'
            )
        )
        OR (
            OLD.lifecycle_state = 'DISPATCH_CLAIMED'
            AND NEW.lifecycle_state IN (
                'ACKNOWLEDGED', 'REJECTED', 'OUTCOME_UNKNOWN'
            )
        )
        OR (
            OLD.lifecycle_state = 'OUTCOME_UNKNOWN'
            AND NEW.lifecycle_state IN (
                'ACKNOWLEDGED', 'REJECTED', 'NEEDS_REVIEW'
            )
        )
        OR (
            OLD.lifecycle_state = 'NEEDS_REVIEW'
            AND NEW.lifecycle_state = 'OPERATOR_RECONCILED'
        )
        OR (
            OLD.lifecycle_state = 'OPERATOR_RECONCILED'
            AND NEW.lifecycle_state = 'NEEDS_REVIEW'
        )
    )
BEGIN
    SELECT RAISE (ABORT, 'venue_effect lifecycle transition is invalid');
END;

CREATE TRIGGER trg_venue_effect_claimed_state_requires_claim
    BEFORE UPDATE OF lifecycle_state ON venue_effect
    FOR EACH ROW
    WHEN NEW.lifecycle_state IN (
            'DISPATCH_CLAIMED', 'ACKNOWLEDGED', 'REJECTED',
            'OUTCOME_UNKNOWN', 'NEEDS_REVIEW', 'OPERATOR_RECONCILED'
        )
     AND NOT EXISTS (
            SELECT 1
              FROM dispatch_claim AS claim
             WHERE claim.effect_id = NEW.effect_id
        )
BEGIN
    SELECT RAISE (ABORT, 'claimed-or-later lifecycle requires immutable claim');
END;

CREATE TRIGGER trg_venue_effect_identity_immutable
    BEFORE UPDATE OF effect_id, effect_external, scope_id,
        application_generation_id, execution_profile_id,
        acquisition_generation_id, generation_mandate_commitment_sha256,
        expected_controller_head_ordinal, authority_class,
        expected_protection_version_ordinal,
        request_occurrence_external, mandate_external, effect_kind,
        client_order_external, target_order_external, side, quantity,
        economic_scope, created_ordinal ON venue_effect
    FOR EACH ROW
    WHEN NEW.effect_id IS NOT OLD.effect_id
      OR NEW.effect_external IS NOT OLD.effect_external
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.application_generation_id IS NOT OLD.application_generation_id
      OR NEW.execution_profile_id IS NOT OLD.execution_profile_id
      OR NEW.acquisition_generation_id IS NOT OLD.acquisition_generation_id
      OR NEW.generation_mandate_commitment_sha256
            IS NOT OLD.generation_mandate_commitment_sha256
      OR NEW.expected_controller_head_ordinal
            IS NOT OLD.expected_controller_head_ordinal
      OR NEW.expected_protection_version_ordinal
            IS NOT OLD.expected_protection_version_ordinal
      OR NEW.authority_class IS NOT OLD.authority_class
      OR NEW.request_occurrence_external IS NOT OLD.request_occurrence_external
      OR NEW.mandate_external IS NOT OLD.mandate_external
      OR NEW.effect_kind IS NOT OLD.effect_kind
      OR NEW.client_order_external IS NOT OLD.client_order_external
      OR NEW.target_order_external IS NOT OLD.target_order_external
      OR NEW.side IS NOT OLD.side
      OR NEW.quantity IS NOT OLD.quantity
      OR NEW.economic_scope IS NOT OLD.economic_scope
      OR NEW.created_ordinal IS NOT OLD.created_ordinal
BEGIN
    SELECT RAISE (ABORT, 'venue_effect identity is immutable');
END;

CREATE TRIGGER trg_venue_effect_close_requires_proof
    BEFORE UPDATE OF disposition, closure_proof_kind, closure_proof_digest,
        closure_proof_evidence_id, closure_proof_claim_id ON venue_effect
    FOR EACH ROW
    WHEN NEW.disposition = 'CLOSED'
     AND OLD.disposition <> 'CLOSED'
     AND (
            NEW.closure_proof_kind IS NULL
            OR NEW.closure_proof_digest IS NULL
            OR NEW.closure_proof_evidence_id IS NULL
            OR NOT EXISTS (
                SELECT 1
                  FROM acceptance_evidence AS evidence
                 WHERE evidence.evidence_id = NEW.closure_proof_evidence_id
                   AND evidence.effect_id = NEW.effect_id
                   AND evidence.evidence_kind = 'CLOSURE_PROOF'
                   AND evidence.proof_kind = NEW.closure_proof_kind
                   AND evidence.evidence_digest = NEW.closure_proof_digest
            )
            OR (
                NEW.closure_proof_kind = 'NEVER_DISPATCHED'
                AND (
                    NEW.lifecycle_state <> 'CANCELED_BEFORE_DISPATCH'
                    OR NEW.closure_proof_claim_id IS NOT NULL
                    OR EXISTS (
                        SELECT 1
                          FROM dispatch_claim AS claim
                         WHERE claim.effect_id = NEW.effect_id
                    )
                )
            )
            OR (
                NEW.closure_proof_kind <> 'NEVER_DISPATCHED'
                AND (
                    NEW.lifecycle_state IN (
                        'REQUESTED', 'CANCELED_BEFORE_DISPATCH'
                    )
                    OR NEW.closure_proof_claim_id IS NULL
                    OR NOT EXISTS (
                        SELECT 1
                          FROM dispatch_claim AS claim
                         WHERE claim.effect_id = NEW.effect_id
                           AND claim.claim_id = NEW.closure_proof_claim_id
                    )
                )
            )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'venue_effect CLOSED requires exact proof; NEVER_DISPATCHED requires CANCELED_BEFORE_DISPATCH and no claim'
    );
END;

CREATE TRIGGER trg_venue_effect_proof_immutable
    BEFORE UPDATE OF closure_proof_kind, closure_proof_digest,
        closure_proof_evidence_id, closure_proof_claim_id ON venue_effect
    FOR EACH ROW
    WHEN OLD.closure_proof_kind IS NOT NULL
     AND (
            NEW.closure_proof_kind IS NOT OLD.closure_proof_kind
            OR NEW.closure_proof_digest IS NOT OLD.closure_proof_digest
            OR NEW.closure_proof_evidence_id IS NOT OLD.closure_proof_evidence_id
            OR NEW.closure_proof_claim_id IS NOT OLD.closure_proof_claim_id
        )
BEGIN
    SELECT RAISE (ABORT, 'venue_effect closure proof is immutable');
END;

CREATE TRIGGER trg_venue_effect_no_delete
    BEFORE DELETE ON venue_effect
BEGIN
    SELECT RAISE (ABORT, 'venue_effect rows are retained');
END;

CREATE TRIGGER trg_venue_identity_owner_late_admission_quarantines
    AFTER INSERT ON venue_identity_owner
    FOR EACH ROW
    WHEN NEW.admitted_after_effect_closed = 1
BEGIN
    UPDATE acquisition_generation_current
       SET unresolved_effect_count = (
            SELECT COUNT(*)
              FROM venue_effect AS effect
             WHERE effect.acquisition_generation_id =
                    NEW.owner_generation_id
               AND effect.scope_id = NEW.scope_id
               AND (
                    effect.disposition <> 'CLOSED'
                    OR EXISTS (
                        SELECT 1
                          FROM venue_identity_owner AS owner
                         WHERE owner.effect_id = effect.effect_id
                           AND owner.admitted_after_effect_closed = 1
                    )
               )
       )
     WHERE acquisition_generation_id = NEW.owner_generation_id
       AND scope_id = NEW.scope_id;

    UPDATE symbol_controller
       SET integrity_state = CASE
            WHEN aggregate_quantity < 0
                THEN 'NEGATIVE_POSITION_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM root_fill AS root
                     WHERE root.scope_id = symbol_controller.scope_id
                       AND root.current_fact_id IS NOT NULL
                       AND NOT EXISTS (
                            SELECT 1
                              FROM acquisition_root_route AS route
                             WHERE route.root_fill_key_id =
                                    root.root_fill_key_id
                               AND route.scope_id = root.scope_id
                               AND route.application_generation_id =
                                    root.application_generation_id
                               AND route.execution_profile_id =
                                    root.execution_profile_id
                        )
                )
                THEN 'UNMATCHED_LINEAGE_QUARANTINED'
            ELSE 'UNRESOLVED_VENUE_QUARANTINED'
        END,
           currentness_head_ordinal = currentness_head_ordinal + 1,
           controller_version_ordinal = controller_version_ordinal + 1
     WHERE scope_id = NEW.scope_id;
END;

CREATE TRIGGER trg_venue_identity_owner_no_update
    BEFORE UPDATE ON venue_identity_owner
BEGIN
    SELECT RAISE (ABORT, 'venue identity owner is immutable');
END;

CREATE TRIGGER trg_venue_identity_owner_no_delete
    BEFORE DELETE ON venue_identity_owner
BEGIN
    SELECT RAISE (ABORT, 'venue identity owner rows are retained');
END;

CREATE TRIGGER trg_acquisition_root_route_no_update
    BEFORE UPDATE ON acquisition_root_route
BEGIN
    SELECT RAISE (ABORT, 'acquisition root routes are immutable');
END;

CREATE TRIGGER trg_acquisition_root_route_no_delete
    BEFORE DELETE ON acquisition_root_route
BEGIN
    SELECT RAISE (ABORT, 'acquisition root routes are retained');
END;

CREATE TRIGGER trg_dispatch_claim_requires_open_effect
    BEFORE INSERT ON dispatch_claim
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM venue_effect AS effect
             WHERE effect.effect_id = NEW.effect_id
               AND effect.disposition = 'OPEN'
               AND effect.lifecycle_state = 'REQUESTED'
        )
BEGIN
    SELECT RAISE (ABORT, 'dispatch claim requires an OPEN REQUESTED venue effect');
END;

CREATE TRIGGER trg_dispatch_claim_requires_current_controller
    BEFORE INSERT ON dispatch_claim
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM venue_effect AS effect
              JOIN symbol_controller AS controller
                ON controller.scope_id = effect.scope_id
               AND controller.application_generation_id =
                    effect.application_generation_id
               AND controller.execution_profile_id =
                    effect.execution_profile_id
               AND controller.live_acquisition_generation_id =
                    effect.acquisition_generation_id
               AND controller.currentness_head_ordinal =
                    effect.expected_controller_head_ordinal
               AND (
                    (
                        controller.integrity_state = 'CONSISTENT'
                        AND effect.authority_class = 'NORMAL'
                        AND EXISTS (
                            SELECT 1
                              FROM protection_authority AS protection
                             WHERE protection.scope_id = effect.scope_id
                               AND protection.authority_class = 'NORMAL'
                               AND protection.expected_controller_head_ordinal =
                                    effect.expected_controller_head_ordinal
                               AND protection.version_ordinal =
                                    effect.expected_protection_version_ordinal
                               AND (
                                    (
                                        protection.active_stream_generation_id
                                            IS NOT NULL
                                        AND protection.active_acquisition_generation_id =
                                            effect.acquisition_generation_id
                                        AND protection.active_generation_mandate_commitment_sha256 =
                                            effect.generation_mandate_commitment_sha256
                                    )
                                    OR (
                                        controller.aggregate_quantity = 0
                                        AND protection.active_stream_generation_id
                                            IS NULL
                                        AND protection.active_acquisition_generation_id
                                            IS NULL
                                        AND protection.active_generation_mandate_commitment_sha256
                                            IS NULL
                                        AND protection.active_source_profile_id
                                            IS NULL
                                        AND protection.active_session_external
                                            IS NULL
                                        AND protection.active_sequence_mode
                                            IS NULL
                                    )
                               )
                        )
                    )
                    OR (
                        controller.integrity_state =
                            'MIXED_GENERATION_RECOVERY'
                        AND effect.authority_class = 'HARD_BAIL'
                        AND controller.aggregate_quantity > 0
                        AND effect.quantity <= controller.aggregate_quantity
                        AND EXISTS (
                            SELECT 1
                              FROM protection_authority AS protection
                             WHERE protection.scope_id = effect.scope_id
                               AND protection.authority_class = 'HARD_BAIL'
                               AND protection.expected_controller_head_ordinal =
                                    effect.expected_controller_head_ordinal
                               AND protection.version_ordinal =
                                    effect.expected_protection_version_ordinal
                               AND protection.active_acquisition_generation_id =
                                    effect.acquisition_generation_id
                        )
                    )
               )
             WHERE effect.effect_id = NEW.effect_id
               AND effect.execution_profile_id = NEW.execution_profile_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'dispatch claim requires the exact current controller head'
    );
END;

CREATE TRIGGER trg_dispatch_claim_advances_effect_state
    AFTER INSERT ON dispatch_claim
    FOR EACH ROW
BEGIN
    UPDATE venue_effect
       SET lifecycle_state = 'DISPATCH_CLAIMED'
     WHERE effect_id = NEW.effect_id;
END;

CREATE TRIGGER trg_dispatch_claim_no_update
    BEFORE UPDATE ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim rows are immutable');
END;

CREATE TRIGGER trg_dispatch_claim_no_delete
    BEFORE DELETE ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim rows are append-only');
END;

CREATE TRIGGER trg_acceptance_set_binding_immutable
    BEFORE UPDATE OF acceptance_set_id, effect_id ON acceptance_set
    FOR EACH ROW
    WHEN NEW.acceptance_set_id IS NOT OLD.acceptance_set_id
      OR NEW.effect_id IS NOT OLD.effect_id
BEGIN
    SELECT RAISE (ABORT, 'acceptance_set binding is immutable');
END;

CREATE TRIGGER trg_acceptance_set_no_delete
    BEFORE DELETE ON acceptance_set
BEGIN
    SELECT RAISE (ABORT, 'acceptance_set rows are retained');
END;

CREATE TRIGGER trg_acceptance_evidence_late_gate
    BEFORE INSERT ON acceptance_evidence
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM acceptance_set AS accepted
             JOIN venue_effect AS effect
                ON effect.effect_id = accepted.effect_id
             WHERE accepted.acceptance_set_id = NEW.acceptance_set_id
               AND effect.effect_id = NEW.effect_id
               AND effect.disposition IN ('CLOSED', 'INVALIDATED')
        )
     AND NEW.evidence_kind <> 'INVALIDATION'
BEGIN
    SELECT RAISE (ABORT, 'closed acceptance retains prior proof; only invalidation may append');
END;

CREATE TRIGGER trg_acceptance_invalidation_requires_closed_authority
    BEFORE INSERT ON acceptance_evidence
    FOR EACH ROW
    WHEN NEW.evidence_kind = 'INVALIDATION'
     AND NOT EXISTS (
            SELECT 1
                 FROM venue_effect AS effect
                 WHERE effect.effect_id = NEW.effect_id
                   AND effect.disposition IN ('CLOSED', 'INVALIDATED')
            )
BEGIN
    SELECT RAISE (
        ABORT,
        'invalidation evidence requires closed or invalidated acceptance'
    );
END;

CREATE TRIGGER trg_acceptance_invalidation_advances_effect
    AFTER INSERT ON acceptance_evidence
    FOR EACH ROW
    WHEN NEW.evidence_kind = 'INVALIDATION'
BEGIN
    UPDATE venue_effect
       SET disposition = 'INVALIDATED'
     WHERE effect_id = NEW.effect_id
       AND disposition = 'CLOSED';

    UPDATE symbol_controller
       SET integrity_state = CASE
            WHEN aggregate_quantity < 0
                THEN 'NEGATIVE_POSITION_QUARANTINED'
            WHEN EXISTS (
                    SELECT 1
                      FROM root_fill AS root
                     WHERE root.scope_id = symbol_controller.scope_id
                       AND root.current_fact_id IS NOT NULL
                       AND NOT EXISTS (
                            SELECT 1
                              FROM acquisition_root_route AS route
                             WHERE route.root_fill_key_id =
                                    root.root_fill_key_id
                               AND route.scope_id = root.scope_id
                               AND route.application_generation_id =
                                    root.application_generation_id
                               AND route.execution_profile_id =
                                    root.execution_profile_id
                        )
                )
                THEN 'UNMATCHED_LINEAGE_QUARANTINED'
            ELSE 'UNRESOLVED_VENUE_QUARANTINED'
        END,
           currentness_head_ordinal = currentness_head_ordinal + 1,
           controller_version_ordinal = controller_version_ordinal + 1
     WHERE scope_id = (
            SELECT effect.scope_id
              FROM venue_effect AS effect
             WHERE effect.effect_id = NEW.effect_id
        )
       AND (
            SELECT COUNT(*)
              FROM acceptance_evidence AS evidence
             WHERE evidence.effect_id = NEW.effect_id
               AND evidence.evidence_kind = 'INVALIDATION'
       ) = 1
       AND NOT EXISTS (
            SELECT 1
              FROM venue_identity_owner AS owner
             WHERE owner.effect_id = NEW.effect_id
               AND owner.owner_external =
                    NEW.contradiction_owner_external
               AND owner.observation_external =
                    NEW.contradiction_observation_external
               AND owner.admitted_after_effect_closed = 1
       );

    INSERT INTO closure_chain (
        closure_id, scope_id, owner_external, ordinal, effect_id,
        closure_kind, predecessor_closure_id
    )
    SELECT
        -NEW.evidence_id,
        owner.scope_id,
        NEW.contradiction_owner_external,
        COALESCE(
            (
                SELECT MAX(retained.ordinal)
                  FROM closure_chain AS retained
                 WHERE retained.scope_id = owner.scope_id
                   AND retained.owner_external =
                        NEW.contradiction_owner_external
            ),
            0
        ) + 1,
        NEW.effect_id,
        'INVALIDATED_TERMINAL',
        (
            SELECT retained.closure_id
              FROM closure_chain AS retained
             WHERE retained.scope_id = owner.scope_id
               AND retained.owner_external =
                    NEW.contradiction_owner_external
             ORDER BY retained.ordinal DESC
             LIMIT 1
        )
      FROM venue_identity_owner AS owner
     WHERE owner.effect_id = NEW.effect_id
       AND owner.owner_external = NEW.contradiction_owner_external
       AND owner.observation_external =
            NEW.contradiction_observation_external;
END;

CREATE TRIGGER trg_acceptance_evidence_append_only_update
    BEFORE UPDATE ON acceptance_evidence
BEGIN
    SELECT RAISE (ABORT, 'acceptance_evidence rows are append-only');
END;

CREATE TRIGGER trg_acceptance_evidence_append_only_delete
    BEFORE DELETE ON acceptance_evidence
BEGIN
    SELECT RAISE (ABORT, 'acceptance_evidence rows are append-only');
END;

CREATE TRIGGER trg_closure_chain_no_gap
    BEFORE INSERT ON closure_chain
    FOR EACH ROW
    WHEN NEW.predecessor_closure_id IS NOT NULL
BEGIN
    SELECT RAISE (ABORT, 'closure ordinals must be gap-free')
    WHERE NOT EXISTS (
            SELECT 1
              FROM closure_chain AS predecessor
             WHERE predecessor.closure_id = NEW.predecessor_closure_id
               AND predecessor.ordinal = NEW.ordinal - 1
        );
END;

CREATE TRIGGER trg_closure_chain_late_owner_requires_invalidation
    BEFORE INSERT ON closure_chain
    FOR EACH ROW
    WHEN NEW.closure_kind <> 'INVALIDATED_TERMINAL'
     AND EXISTS (
            SELECT 1
              FROM venue_identity_owner AS owner
             WHERE owner.scope_id = NEW.scope_id
               AND owner.owner_external = NEW.owner_external
               AND owner.effect_id = NEW.effect_id
               AND owner.admitted_after_effect_closed = 1
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'post-closure venue owner requires exact invalidation evidence'
    );
END;

CREATE TRIGGER trg_closure_chain_matches_effect_authority
    BEFORE INSERT ON closure_chain
    FOR EACH ROW
    WHEN (
            NEW.closure_kind = 'ACCEPTANCE_CLOSED'
            AND NOT EXISTS (
                SELECT 1
                 FROM venue_effect AS effect
                 WHERE effect.effect_id = NEW.effect_id
                   AND effect.disposition = 'CLOSED'
            )
        )
       OR (
            NEW.closure_kind = 'INVALIDATED_TERMINAL'
            AND (
                NOT EXISTS (
                    SELECT 1
                      FROM venue_effect AS effect
                     WHERE effect.effect_id = NEW.effect_id
                       AND effect.disposition = 'INVALIDATED'
                )
                OR NOT EXISTS (
                    SELECT 1
                      FROM acceptance_evidence AS evidence
                      JOIN venue_identity_owner AS owner
                        ON owner.effect_id = evidence.effect_id
                       AND owner.owner_external =
                            evidence.contradiction_owner_external
                       AND owner.observation_external =
                            evidence.contradiction_observation_external
                     WHERE evidence.evidence_id = -NEW.closure_id
                       AND evidence.effect_id = NEW.effect_id
                       AND evidence.evidence_kind = 'INVALIDATION'
                       AND owner.scope_id = NEW.scope_id
                       AND owner.owner_external = NEW.owner_external
                )
            )
        )
BEGIN
    SELECT RAISE (ABORT, 'closure kind must match canonical effect authority');
END;

CREATE TRIGGER trg_closure_chain_append_only_update
    BEFORE UPDATE ON closure_chain
BEGIN
    SELECT RAISE (ABORT, 'closure_chain rows are append-only');
END;

CREATE TRIGGER trg_closure_chain_append_only_delete
    BEFORE DELETE ON closure_chain
BEGIN
    SELECT RAISE (ABORT, 'closure_chain rows are append-only');
END;

CREATE TRIGGER trg_protection_authority_version_monotonic
    BEFORE UPDATE ON protection_authority
    FOR EACH ROW
    WHEN NEW.version_ordinal < OLD.version_ordinal
      OR (
            (
                NEW.authority_class IS NOT OLD.authority_class
                OR NEW.active_stream_generation_id
                    IS NOT OLD.active_stream_generation_id
                OR NEW.active_acquisition_generation_id
                    IS NOT OLD.active_acquisition_generation_id
                OR NEW.active_generation_mandate_commitment_sha256
                    IS NOT OLD.active_generation_mandate_commitment_sha256
                OR NEW.active_source_profile_id
                    IS NOT OLD.active_source_profile_id
                OR NEW.active_session_external
                    IS NOT OLD.active_session_external
                OR NEW.active_sequence_mode
                    IS NOT OLD.active_sequence_mode
                OR NEW.expected_controller_head_ordinal
                    IS NOT OLD.expected_controller_head_ordinal
                OR NEW.state_commitment_sha256
                    IS NOT OLD.state_commitment_sha256
            )
            AND NEW.version_ordinal <= OLD.version_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'protection version must advance');
END;

CREATE TRIGGER trg_protection_authority_no_nonflat_transfer
    BEFORE UPDATE OF active_stream_generation_id,
        active_acquisition_generation_id,
        active_generation_mandate_commitment_sha256,
        active_source_profile_id, active_session_external,
        active_sequence_mode ON protection_authority
    FOR EACH ROW
    WHEN (
            NEW.active_stream_generation_id
                IS NOT OLD.active_stream_generation_id
            OR NEW.active_acquisition_generation_id
                IS NOT OLD.active_acquisition_generation_id
            OR NEW.active_generation_mandate_commitment_sha256
                IS NOT OLD.active_generation_mandate_commitment_sha256
            OR NEW.active_source_profile_id
                IS NOT OLD.active_source_profile_id
            OR NEW.active_session_external
                IS NOT OLD.active_session_external
            OR NEW.active_sequence_mode IS NOT OLD.active_sequence_mode
        )
     AND EXISTS (
            SELECT 1
              FROM symbol_controller AS controller
             WHERE controller.scope_id = NEW.scope_id
               AND (
                    controller.aggregate_quantity <> 0
                    OR controller.integrity_state
                        <> 'CONSISTENT'
               )
               AND NOT (
                    OLD.authority_class = 'NORMAL'
                    AND NEW.authority_class = 'NORMAL'
                    AND OLD.active_stream_generation_id IS NULL
                    AND OLD.active_acquisition_generation_id IS NULL
                    AND OLD.active_generation_mandate_commitment_sha256
                        IS NULL
                    AND OLD.active_source_profile_id IS NULL
                    AND OLD.active_session_external IS NULL
                    AND OLD.active_sequence_mode IS NULL
                    AND NEW.active_stream_generation_id IS NOT NULL
                    AND NEW.active_acquisition_generation_id IS NOT NULL
                    AND NEW.active_generation_mandate_commitment_sha256
                        IS NOT NULL
                    AND NEW.active_source_profile_id IS NOT NULL
                    AND NEW.active_session_external IS NOT NULL
                    AND NEW.active_sequence_mode IS NOT NULL
                    AND controller.aggregate_quantity > 0
                    AND controller.integrity_state = 'CONSISTENT'
                    AND controller.live_acquisition_generation_id =
                        NEW.active_acquisition_generation_id
                    AND controller.currentness_head_ordinal =
                        NEW.expected_controller_head_ordinal
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'nonflat or quarantined protection authority cannot transfer'
    );
END;

CREATE TRIGGER trg_protection_authority_requires_consistent_controller
    BEFORE INSERT ON protection_authority
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
             FROM symbol_controller AS controller
             WHERE controller.scope_id = NEW.scope_id
               AND (
                    (
                        controller.integrity_state = 'CONSISTENT'
                        AND NEW.authority_class = 'NORMAL'
                    )
                    OR (
                        controller.integrity_state =
                            'MIXED_GENERATION_RECOVERY'
                        AND NEW.authority_class = 'HARD_BAIL'
                    )
               )
               AND controller.currentness_head_ordinal =
                    NEW.expected_controller_head_ordinal
               AND (
                    (
                        NEW.authority_class = 'NORMAL'
                        AND (
                            NEW.active_acquisition_generation_id IS NULL
                            OR controller.live_acquisition_generation_id =
                                NEW.active_acquisition_generation_id
                        )
                    )
                    OR (
                        NEW.authority_class = 'HARD_BAIL'
                        AND controller.live_acquisition_generation_id =
                            NEW.active_acquisition_generation_id
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'protection authority requires matching current controller authority'
    );
END;

CREATE TRIGGER trg_protection_authority_update_requires_current_controller
    BEFORE UPDATE ON protection_authority
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM symbol_controller AS controller
             WHERE controller.scope_id = NEW.scope_id
               AND (
                    (
                        controller.integrity_state = 'CONSISTENT'
                        AND NEW.authority_class = 'NORMAL'
                    )
                    OR (
                        controller.integrity_state =
                            'MIXED_GENERATION_RECOVERY'
                        AND NEW.authority_class = 'HARD_BAIL'
                    )
                    OR (
                        controller.integrity_state =
                            'UNRESOLVED_VENUE_QUARANTINED'
                        AND OLD.authority_class = 'NORMAL'
                        AND NEW.authority_class = 'NORMAL'
                        AND NEW.active_stream_generation_id
                            IS OLD.active_stream_generation_id
                        AND NEW.active_acquisition_generation_id
                            IS OLD.active_acquisition_generation_id
                        AND NEW.active_generation_mandate_commitment_sha256
                            IS OLD.active_generation_mandate_commitment_sha256
                        AND NEW.active_source_profile_id
                            IS OLD.active_source_profile_id
                        AND NEW.active_session_external
                            IS OLD.active_session_external
                        AND NEW.active_sequence_mode
                            IS OLD.active_sequence_mode
                        AND EXISTS (
                            SELECT 1
                              FROM venue_identity_owner AS owner
                              JOIN venue_effect AS effect
                                ON effect.effect_id = owner.effect_id
                               AND effect.scope_id = owner.scope_id
                              JOIN acceptance_evidence AS evidence
                                ON evidence.effect_id = owner.effect_id
                               AND evidence.evidence_kind = 'INVALIDATION'
                               AND evidence.contradiction_owner_external =
                                    owner.owner_external
                               AND evidence.contradiction_observation_external =
                                    owner.observation_external
                             WHERE owner.scope_id = NEW.scope_id
                               AND owner.admitted_after_effect_closed = 1
                               AND effect.disposition = 'INVALIDATED'
                        )
                        AND NOT EXISTS (
                            SELECT 1
                              FROM venue_identity_owner AS outstanding_owner
                              JOIN venue_effect AS outstanding_effect
                                ON outstanding_effect.effect_id =
                                    outstanding_owner.effect_id
                               AND outstanding_effect.scope_id =
                                    outstanding_owner.scope_id
                             WHERE outstanding_owner.scope_id = NEW.scope_id
                               AND outstanding_owner.admitted_after_effect_closed = 1
                               AND (
                                    outstanding_effect.disposition <>
                                        'INVALIDATED'
                                    OR NOT EXISTS (
                                        SELECT 1
                                          FROM acceptance_evidence AS evidence
                                         WHERE evidence.effect_id =
                                                outstanding_owner.effect_id
                                           AND evidence.evidence_kind =
                                                'INVALIDATION'
                                           AND evidence.contradiction_owner_external =
                                                outstanding_owner.owner_external
                                           AND evidence.contradiction_observation_external =
                                                outstanding_owner.observation_external
                                    )
                               )
                        )
                    )
               )
               AND controller.currentness_head_ordinal =
                    NEW.expected_controller_head_ordinal
               AND (
                    (
                        NEW.authority_class = 'NORMAL'
                        AND (
                            NEW.active_acquisition_generation_id IS NULL
                            OR controller.live_acquisition_generation_id =
                                NEW.active_acquisition_generation_id
                        )
                    )
                    OR (
                        NEW.authority_class = 'HARD_BAIL'
                        AND controller.live_acquisition_generation_id =
                            NEW.active_acquisition_generation_id
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'protection update requires matching current controller authority'
    );
END;

CREATE TRIGGER trg_protection_authority_updates_generation_current_on_insert
    AFTER INSERT ON protection_authority
    FOR EACH ROW
    WHEN NEW.active_acquisition_generation_id IS NOT NULL
BEGIN
    UPDATE acquisition_generation_current
       SET active_protection_count = (
            SELECT COUNT(*)
              FROM protection_authority AS protection
             WHERE protection.active_acquisition_generation_id =
                    NEW.active_acquisition_generation_id
               AND protection.scope_id = NEW.scope_id
       )
     WHERE acquisition_generation_id =
            NEW.active_acquisition_generation_id
       AND scope_id = NEW.scope_id;
END;

CREATE TRIGGER trg_protection_authority_updates_generation_current_on_update
    AFTER UPDATE OF active_acquisition_generation_id ON protection_authority
    FOR EACH ROW
    WHEN NEW.active_acquisition_generation_id
            IS NOT OLD.active_acquisition_generation_id
BEGIN
    UPDATE acquisition_generation_current
       SET active_protection_count = (
            SELECT COUNT(*)
              FROM protection_authority AS protection
             WHERE protection.active_acquisition_generation_id =
                    acquisition_generation_current.acquisition_generation_id
               AND protection.scope_id =
                    acquisition_generation_current.scope_id
       )
     WHERE scope_id = NEW.scope_id
       AND acquisition_generation_id IN (
            OLD.active_acquisition_generation_id,
            NEW.active_acquisition_generation_id
       );
END;

CREATE TRIGGER trg_market_stream_authority_no_update
    BEFORE UPDATE ON market_stream_authority
BEGIN
    SELECT RAISE (ABORT, 'market_stream_authority rows are immutable');
END;

CREATE TRIGGER trg_market_stream_authority_no_delete
    BEFORE DELETE ON market_stream_authority
BEGIN
    SELECT RAISE (ABORT, 'market_stream_authority rows are retained');
END;

CREATE TRIGGER trg_protection_authority_identity_immutable
    BEFORE UPDATE OF scope_id ON protection_authority
    FOR EACH ROW
    WHEN NEW.scope_id IS NOT OLD.scope_id
BEGIN
    SELECT RAISE (ABORT, 'protection_authority identity is immutable');
END;

CREATE TRIGGER trg_protection_authority_no_duplicate_insert
    BEFORE INSERT ON protection_authority
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM protection_authority AS retained
             WHERE retained.scope_id = NEW.scope_id
        )
BEGIN
    SELECT RAISE (ABORT, 'protection_authority identity is already retained');
END;

CREATE TRIGGER trg_protection_authority_no_delete
    BEFORE DELETE ON protection_authority
BEGIN
    SELECT RAISE (ABORT, 'protection_authority rows are retained');
END;

CREATE TRIGGER trg_market_cursor_ordinals_monotonic
    BEFORE UPDATE OF fixed_cursor_ordinal, published_head_ordinal ON market_cursor
    FOR EACH ROW
    WHEN NEW.fixed_cursor_ordinal < OLD.fixed_cursor_ordinal
      OR NEW.published_head_ordinal < OLD.published_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'market_cursor ordinals may only advance');
END;

CREATE TRIGGER trg_market_cursor_identity_immutable
    BEFORE UPDATE OF stream_generation_id, scope_id,
        application_generation_id, acquisition_generation_id,
        generation_mandate_commitment_sha256, source_profile_id,
        session_external, sequence_mode ON market_cursor
    FOR EACH ROW
    WHEN NEW.stream_generation_id IS NOT OLD.stream_generation_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.application_generation_id IS NOT OLD.application_generation_id
      OR NEW.acquisition_generation_id IS NOT OLD.acquisition_generation_id
      OR NEW.generation_mandate_commitment_sha256
            IS NOT OLD.generation_mandate_commitment_sha256
      OR NEW.source_profile_id IS NOT OLD.source_profile_id
      OR NEW.session_external IS NOT OLD.session_external
      OR NEW.sequence_mode IS NOT OLD.sequence_mode
BEGIN
    SELECT RAISE (ABORT, 'market_cursor identity is immutable');
END;

CREATE TRIGGER trg_market_cursor_no_delete
    BEFORE DELETE ON market_cursor
BEGIN
    SELECT RAISE (ABORT, 'market_cursor rows are retained');
END;

-- M2-I3.5 retains checkpoint payload history separately from the mutable
-- serving head.  The reverse-edge triggers below make a head unusable unless
-- the exact immutable bytes were staged first in the same caller-owned
-- transaction.
CREATE TABLE runtime_checkpoint_payload (
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    market_source_profile_id TEXT NOT NULL,
    currentness_head_ordinal INTEGER NOT NULL
        CHECK (currentness_head_ordinal >= 0),
    checkpoint_version_ordinal INTEGER NOT NULL
        CHECK (checkpoint_version_ordinal >= 1),
    payload_bytes BLOB NOT NULL
        CHECK (length(payload_bytes) >= 1),
    payload_length INTEGER NOT NULL
        CHECK (
            payload_length >= 1
            AND payload_length = length(payload_bytes)
        ),
    payload_sha256 TEXT NOT NULL
        CHECK (
            length(payload_sha256) = 64
            AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    PRIMARY KEY (application_generation_id, checkpoint_version_ordinal),
    UNIQUE (
        application_generation_id,
        currentness_head_ordinal,
        checkpoint_version_ordinal,
        payload_sha256
    ),
    FOREIGN KEY (application_generation_id, execution_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_execution_profile_id
        ),
    FOREIGN KEY (application_generation_id, market_source_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_market_source_profile_id
        )
);

CREATE TABLE durable_input (
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    scope_id INTEGER NOT NULL,
    input_domain TEXT NOT NULL
        CHECK (
            input_domain IN (
                'BROKER_EXECUTION',
                'VENUE_RECOVERY',
                'AUTHORITY',
                'BEGIN_ACQUISITION_GENERATION',
                'CREATE_ACQUISITION_EFFECT',
                'CLAIM_ACQUISITION_EFFECT',
                'BEGIN_ACQUISITION_PREEMPTION',
                'MARKET_OCCURRENCE'
            )
    ),
    session_external TEXT,
    acquisition_generation_id TEXT,
    market_source_profile_id TEXT,
    stream_generation_id TEXT,
    input_identity_sha256 TEXT NOT NULL
        CHECK (
            length(input_identity_sha256) = 64
            AND input_identity_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    operation_contract_version INTEGER NOT NULL
        CHECK (operation_contract_version = 1),
    canonical_payload_bytes BLOB NOT NULL
        CHECK (length(canonical_payload_bytes) >= 1),
    payload_sha256 TEXT NOT NULL
        CHECK (
            length(payload_sha256) = 64
            AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    technical_state TEXT NOT NULL
        CHECK (
            technical_state IN (
                'CLAIMED', 'TERMINAL', 'RECONCILIATION_PENDING'
            )
        ),
    created_ordinal INTEGER NOT NULL UNIQUE CHECK (created_ordinal >= 1),
    PRIMARY KEY (
        application_generation_id, input_domain, input_identity_sha256
    ),
    CHECK (
        (
            input_domain = 'MARKET_OCCURRENCE'
            AND session_external IS NOT NULL
            AND acquisition_generation_id IS NOT NULL
            AND market_source_profile_id IS NOT NULL
            AND stream_generation_id IS NOT NULL
        )
        OR (
            input_domain IN (
                'BEGIN_ACQUISITION_GENERATION',
                'CREATE_ACQUISITION_EFFECT',
                'CLAIM_ACQUISITION_EFFECT',
                'BEGIN_ACQUISITION_PREEMPTION'
            )
            AND session_external IS NOT NULL
            AND acquisition_generation_id IS NOT NULL
            AND market_source_profile_id IS NULL
            AND stream_generation_id IS NULL
        )
        OR (
            input_domain = 'VENUE_RECOVERY'
            AND acquisition_generation_id IS NULL
            AND market_source_profile_id IS NULL
            AND stream_generation_id IS NULL
        )
        OR (
            input_domain IN ('BROKER_EXECUTION', 'AUTHORITY')
            AND session_external IS NULL
            AND acquisition_generation_id IS NULL
            AND market_source_profile_id IS NULL
            AND stream_generation_id IS NULL
        )
    ),
    CHECK (session_external IS NULL OR length(session_external) >= 1),
    FOREIGN KEY (application_generation_id, execution_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_execution_profile_id
        ),
    FOREIGN KEY (scope_id, application_generation_id, execution_profile_id)
        REFERENCES acquisition_scope (
            scope_id, application_generation_id, execution_profile_id
        ),
    FOREIGN KEY (acquisition_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id),
    FOREIGN KEY (application_generation_id, market_source_profile_id)
        REFERENCES application_generation (
            application_generation_id, selected_market_source_profile_id
        ),
    FOREIGN KEY (stream_generation_id)
        REFERENCES market_stream_authority (stream_generation_id)
);

CREATE TABLE durable_input_semantic_key (
    key_kind TEXT NOT NULL
        CHECK (
            key_kind IN (
                'VENUE_COMMAND_V2',
                'VENUE_EXECUTION_FACT_V1',
                'VENUE_COVERAGE_ROOT_V1',
                'VENUE_COVERAGE_INTERVAL_V1',
                'VENUE_BROKER_FACT_V1',
                'AUTHORITY_QUERY_CLAIM_V1',
                'AUTHORITY_MANUAL_FLATTEN_V1',
                'AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1'
            )
        ),
    key_application_generation_id TEXT,
    execution_profile_id TEXT NOT NULL,
    key_scope_id INTEGER,
    canonical_key_bytes BLOB NOT NULL
        CHECK (length(canonical_key_bytes) >= 1),
    key_sha256 TEXT NOT NULL
        CHECK (
            length(key_sha256) = 64
            AND key_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    input_application_generation_id TEXT NOT NULL,
    input_domain TEXT NOT NULL
        CHECK (
            input_domain IN (
                'BROKER_EXECUTION',
                'VENUE_RECOVERY',
                'AUTHORITY',
                'BEGIN_ACQUISITION_GENERATION',
                'CREATE_ACQUISITION_EFFECT',
                'CLAIM_ACQUISITION_EFFECT',
                'BEGIN_ACQUISITION_PREEMPTION',
                'MARKET_OCCURRENCE'
            )
        ),
    input_identity_sha256 TEXT NOT NULL
        CHECK (
            length(input_identity_sha256) = 64
            AND input_identity_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    created_ordinal INTEGER NOT NULL UNIQUE CHECK (created_ordinal >= 1),
    UNIQUE (
        input_application_generation_id,
        input_domain,
        input_identity_sha256,
        key_kind,
        canonical_key_bytes
    ),
    CHECK (
        (
            key_kind IN (
                'VENUE_COMMAND_V2',
                'VENUE_EXECUTION_FACT_V1',
                'VENUE_COVERAGE_ROOT_V1',
                'VENUE_COVERAGE_INTERVAL_V1',
                'VENUE_BROKER_FACT_V1'
            )
            AND key_application_generation_id IS NULL
            AND key_scope_id IS NULL
        )
        OR (
            key_kind IN (
                'AUTHORITY_QUERY_CLAIM_V1',
                'AUTHORITY_MANUAL_FLATTEN_V1',
                'AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1'
            )
            AND key_application_generation_id IS NOT NULL
            AND key_scope_id IS NOT NULL
        )
    ),
    FOREIGN KEY (
        input_application_generation_id,
        input_domain,
        input_identity_sha256
    ) REFERENCES durable_input (
        application_generation_id, input_domain, input_identity_sha256
    ),
    FOREIGN KEY (
        key_scope_id, key_application_generation_id, execution_profile_id
    ) REFERENCES acquisition_scope (
        scope_id, application_generation_id, execution_profile_id
    )
);

CREATE UNIQUE INDEX uq_durable_input_semantic_key_venue
    ON durable_input_semantic_key (
        execution_profile_id, key_kind, canonical_key_bytes
    )
    WHERE key_kind IN (
        'VENUE_COMMAND_V2',
        'VENUE_EXECUTION_FACT_V1',
        'VENUE_COVERAGE_ROOT_V1',
        'VENUE_COVERAGE_INTERVAL_V1',
        'VENUE_BROKER_FACT_V1'
    );

CREATE UNIQUE INDEX uq_durable_input_semantic_key_authority
    ON durable_input_semantic_key (
        key_application_generation_id,
        execution_profile_id,
        key_scope_id,
        key_kind,
        canonical_key_bytes
    )
    WHERE key_kind IN (
        'AUTHORITY_QUERY_CLAIM_V1',
        'AUTHORITY_MANUAL_FLATTEN_V1',
        'AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1'
    );

CREATE TABLE decision_receipt (
    receipt_ordinal INTEGER PRIMARY KEY CHECK (receipt_ordinal >= 1),
    application_generation_id TEXT NOT NULL,
    input_domain TEXT NOT NULL,
    input_identity_sha256 TEXT NOT NULL
        CHECK (
            length(input_identity_sha256) = 64
            AND input_identity_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    owner_domain TEXT NOT NULL
        CHECK (
            owner_domain IN (
                'POSITION', 'VENUE_RECOVERY', 'AUTHORITY', 'ACQUISITION',
                'PROTECTION'
            )
        ),
    owner_disposition TEXT NOT NULL CHECK (length(owner_disposition) >= 1),
    terminal_technical_state TEXT NOT NULL
        CHECK (terminal_technical_state IN ('TERMINAL', 'RECONCILIATION_PENDING')),
    result_sha256 TEXT NOT NULL
        CHECK (
            length(result_sha256) = 64
            AND result_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    checkpoint_currentness_head_ordinal INTEGER,
    checkpoint_version_ordinal INTEGER,
    checkpoint_payload_sha256 TEXT
        CHECK (
            checkpoint_payload_sha256 IS NULL
            OR (
                length(checkpoint_payload_sha256) = 64
                AND checkpoint_payload_sha256 NOT GLOB '*[^0-9a-f]*'
            )
        ),
    canonical_receipt_bytes BLOB NOT NULL
        CHECK (length(canonical_receipt_bytes) >= 1),
    receipt_length INTEGER NOT NULL
        CHECK (
            receipt_length >= 1
            AND receipt_length = length(canonical_receipt_bytes)
        ),
    receipt_sha256 TEXT NOT NULL
        CHECK (
            length(receipt_sha256) = 64
            AND receipt_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    UNIQUE (application_generation_id, input_domain, input_identity_sha256),
    UNIQUE (
        application_generation_id,
        input_domain,
        input_identity_sha256,
        receipt_ordinal,
        receipt_sha256
    ),
    CHECK (
        (checkpoint_currentness_head_ordinal IS NULL)
        = (checkpoint_version_ordinal IS NULL)
        AND (checkpoint_version_ordinal IS NULL)
        = (checkpoint_payload_sha256 IS NULL)
    ),
    FOREIGN KEY (
        application_generation_id, input_domain, input_identity_sha256
    ) REFERENCES durable_input (
        application_generation_id, input_domain, input_identity_sha256
    ),
    FOREIGN KEY (
        application_generation_id,
        checkpoint_currentness_head_ordinal,
        checkpoint_version_ordinal,
        checkpoint_payload_sha256
    ) REFERENCES runtime_checkpoint_payload (
        application_generation_id,
        currentness_head_ordinal,
        checkpoint_version_ordinal,
        payload_sha256
    )
);

CREATE TABLE durable_input_outcome (
    application_generation_id TEXT NOT NULL,
    input_domain TEXT NOT NULL,
    input_identity_sha256 TEXT NOT NULL
        CHECK (
            length(input_identity_sha256) = 64
            AND input_identity_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    owner_domain TEXT NOT NULL
        CHECK (
            owner_domain IN (
                'POSITION', 'VENUE_RECOVERY', 'AUTHORITY', 'ACQUISITION',
                'PROTECTION'
            )
        ),
    owner_disposition TEXT NOT NULL CHECK (length(owner_disposition) >= 1),
    terminal_technical_state TEXT NOT NULL
        CHECK (terminal_technical_state IN ('TERMINAL', 'RECONCILIATION_PENDING')),
    result_sha256 TEXT NOT NULL
        CHECK (
            length(result_sha256) = 64
            AND result_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    checkpoint_currentness_head_ordinal INTEGER,
    checkpoint_version_ordinal INTEGER,
    checkpoint_payload_sha256 TEXT
        CHECK (
            checkpoint_payload_sha256 IS NULL
            OR (
                length(checkpoint_payload_sha256) = 64
                AND checkpoint_payload_sha256 NOT GLOB '*[^0-9a-f]*'
            )
        ),
    receipt_ordinal INTEGER NOT NULL,
    receipt_sha256 TEXT NOT NULL
        CHECK (
            length(receipt_sha256) = 64
            AND receipt_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    canonical_outcome_bytes BLOB NOT NULL
        CHECK (length(canonical_outcome_bytes) >= 1),
    outcome_length INTEGER NOT NULL
        CHECK (
            outcome_length >= 1
            AND outcome_length = length(canonical_outcome_bytes)
        ),
    outcome_sha256 TEXT NOT NULL
        CHECK (
            length(outcome_sha256) = 64
            AND outcome_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    PRIMARY KEY (
        application_generation_id, input_domain, input_identity_sha256
    ),
    CHECK (
        (checkpoint_currentness_head_ordinal IS NULL)
        = (checkpoint_version_ordinal IS NULL)
        AND (checkpoint_version_ordinal IS NULL)
        = (checkpoint_payload_sha256 IS NULL)
    ),
    FOREIGN KEY (
        application_generation_id, input_domain, input_identity_sha256
    ) REFERENCES durable_input (
        application_generation_id, input_domain, input_identity_sha256
    ),
    FOREIGN KEY (
        application_generation_id,
        input_domain,
        input_identity_sha256,
        receipt_ordinal,
        receipt_sha256
    ) REFERENCES decision_receipt (
        application_generation_id,
        input_domain,
        input_identity_sha256,
        receipt_ordinal,
        receipt_sha256
    ),
    FOREIGN KEY (
        application_generation_id,
        checkpoint_currentness_head_ordinal,
        checkpoint_version_ordinal,
        checkpoint_payload_sha256
    ) REFERENCES runtime_checkpoint_payload (
        application_generation_id,
        currentness_head_ordinal,
        checkpoint_version_ordinal,
        payload_sha256
    )
);

CREATE TABLE broker_outbox (
    outbox_sequence INTEGER PRIMARY KEY CHECK (outbox_sequence >= 1),
    application_generation_id TEXT NOT NULL,
    execution_profile_id TEXT NOT NULL,
    scope_id INTEGER NOT NULL,
    acquisition_generation_id TEXT NOT NULL,
    input_domain TEXT NOT NULL
        CHECK (input_domain IN ('AUTHORITY', 'CLAIM_ACQUISITION_EFFECT')),
    input_identity_sha256 TEXT NOT NULL
        CHECK (
            length(input_identity_sha256) = 64
            AND input_identity_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    effect_id INTEGER NOT NULL,
    claim_id INTEGER NOT NULL,
    canonical_payload_bytes BLOB NOT NULL
        CHECK (length(canonical_payload_bytes) >= 1),
    payload_length INTEGER NOT NULL
        CHECK (
            payload_length >= 1
            AND payload_length = length(canonical_payload_bytes)
        ),
    payload_sha256 TEXT NOT NULL
        CHECK (
            length(payload_sha256) = 64
            AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    UNIQUE (effect_id, claim_id),
    FOREIGN KEY (
        application_generation_id, input_domain, input_identity_sha256
    ) REFERENCES durable_input (
        application_generation_id, input_domain, input_identity_sha256
    ),
    FOREIGN KEY (
        effect_id,
        scope_id,
        application_generation_id,
        execution_profile_id,
        acquisition_generation_id
    ) REFERENCES venue_effect (
        effect_id,
        scope_id,
        application_generation_id,
        execution_profile_id,
        acquisition_generation_id
    ),
    FOREIGN KEY (effect_id, claim_id)
        REFERENCES dispatch_claim (effect_id, claim_id)
);

CREATE TRIGGER trg_runtime_checkpoint_payload_no_conflict_replace
    BEFORE INSERT ON runtime_checkpoint_payload
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM runtime_checkpoint_payload AS retained
             WHERE retained.application_generation_id =
                    NEW.application_generation_id
               AND retained.checkpoint_version_ordinal =
                    NEW.checkpoint_version_ordinal
        )
BEGIN
    SELECT RAISE (
        ABORT, 'runtime checkpoint payload identity is already retained'
    );
END;

CREATE TRIGGER trg_runtime_checkpoint_payload_immutable
    BEFORE UPDATE ON runtime_checkpoint_payload
BEGIN
    SELECT RAISE (ABORT, 'runtime checkpoint payload rows are immutable');
END;

CREATE TRIGGER trg_runtime_checkpoint_payload_no_delete
    BEFORE DELETE ON runtime_checkpoint_payload
BEGIN
    SELECT RAISE (ABORT, 'runtime checkpoint payload rows are retained');
END;

CREATE TRIGGER trg_kernel_checkpoint_payload_required_insert
    BEFORE INSERT ON kernel_checkpoint
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1 FROM runtime_checkpoint_payload AS payload
             WHERE payload.application_generation_id =
                    NEW.application_generation_id
               AND payload.currentness_head_ordinal =
                    NEW.currentness_head_ordinal
               AND payload.checkpoint_version_ordinal =
                    NEW.checkpoint_version_ordinal
               AND payload.payload_sha256 = NEW.checkpoint_sha256
        )
BEGIN
    SELECT RAISE (
        ABORT, 'kernel checkpoint requires an exact retained payload'
    );
END;

CREATE TRIGGER trg_kernel_checkpoint_payload_required_advance
    BEFORE UPDATE OF currentness_head_ordinal, checkpoint_sha256,
        checkpoint_version_ordinal ON kernel_checkpoint
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1 FROM runtime_checkpoint_payload AS payload
             WHERE payload.application_generation_id =
                    NEW.application_generation_id
               AND payload.currentness_head_ordinal =
                    NEW.currentness_head_ordinal
               AND payload.checkpoint_version_ordinal =
                    NEW.checkpoint_version_ordinal
               AND payload.payload_sha256 = NEW.checkpoint_sha256
        )
BEGIN
    SELECT RAISE (
        ABORT, 'kernel checkpoint requires an exact retained payload'
    );
END;

CREATE TRIGGER trg_durable_input_initial_state
    BEFORE INSERT ON durable_input
    FOR EACH ROW
    WHEN NEW.technical_state <> 'CLAIMED'
BEGIN
    SELECT RAISE (ABORT, 'durable input must initially be claimed');
END;

CREATE TRIGGER trg_durable_input_market_stream_exact_route
    BEFORE INSERT ON durable_input
    FOR EACH ROW
    WHEN NEW.input_domain = 'MARKET_OCCURRENCE'
     AND NOT EXISTS (
            SELECT 1
              FROM market_stream_authority AS stream
             WHERE stream.stream_generation_id = NEW.stream_generation_id
               AND stream.scope_id = NEW.scope_id
               AND stream.application_generation_id =
                    NEW.application_generation_id
               AND stream.acquisition_generation_id =
                    NEW.acquisition_generation_id
               AND stream.source_profile_id = NEW.market_source_profile_id
               AND stream.session_external = NEW.session_external
        )
BEGIN
    SELECT RAISE (
        ABORT, 'market occurrence input must bind its exact stream route'
    );
END;

CREATE TRIGGER trg_durable_input_immutable
    BEFORE UPDATE ON durable_input
    FOR EACH ROW
    WHEN NEW.application_generation_id IS NOT OLD.application_generation_id
      OR NEW.execution_profile_id IS NOT OLD.execution_profile_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.input_domain IS NOT OLD.input_domain
      OR NEW.session_external IS NOT OLD.session_external
      OR NEW.acquisition_generation_id IS NOT OLD.acquisition_generation_id
      OR NEW.market_source_profile_id IS NOT OLD.market_source_profile_id
      OR NEW.stream_generation_id IS NOT OLD.stream_generation_id
      OR NEW.input_identity_sha256 IS NOT OLD.input_identity_sha256
      OR NEW.operation_contract_version IS NOT OLD.operation_contract_version
      OR NEW.canonical_payload_bytes IS NOT OLD.canonical_payload_bytes
      OR NEW.payload_sha256 IS NOT OLD.payload_sha256
      OR NEW.created_ordinal IS NOT OLD.created_ordinal
BEGIN
    SELECT RAISE (ABORT, 'durable input identity is immutable');
END;

CREATE TRIGGER trg_durable_input_finalization_requires_outcome
    BEFORE UPDATE OF technical_state ON durable_input
    FOR EACH ROW
    WHEN NOT (
            OLD.technical_state = 'CLAIMED'
            AND NEW.technical_state IN ('TERMINAL', 'RECONCILIATION_PENDING')
            AND EXISTS (
                SELECT 1
                  FROM durable_input_outcome AS outcome
                  JOIN decision_receipt AS receipt
                    ON receipt.application_generation_id =
                           outcome.application_generation_id
                   AND receipt.input_domain = outcome.input_domain
                   AND receipt.input_identity_sha256 =
                           outcome.input_identity_sha256
                   AND receipt.receipt_ordinal = outcome.receipt_ordinal
                   AND receipt.receipt_sha256 = outcome.receipt_sha256
                 WHERE outcome.application_generation_id =
                           NEW.application_generation_id
                   AND outcome.input_domain = NEW.input_domain
                   AND outcome.input_identity_sha256 =
                           NEW.input_identity_sha256
                   AND outcome.terminal_technical_state = NEW.technical_state
                   AND receipt.owner_domain IS outcome.owner_domain
                   AND receipt.owner_disposition IS outcome.owner_disposition
                   AND receipt.terminal_technical_state IS
                           outcome.terminal_technical_state
                   AND receipt.result_sha256 IS outcome.result_sha256
                   AND receipt.checkpoint_currentness_head_ordinal IS
                           outcome.checkpoint_currentness_head_ordinal
                   AND receipt.checkpoint_version_ordinal IS
                           outcome.checkpoint_version_ordinal
                   AND receipt.checkpoint_payload_sha256 IS
                           outcome.checkpoint_payload_sha256
            )
        )
BEGIN
    SELECT RAISE (
        ABORT, 'durable input finalization requires one coherent outcome receipt'
    );
END;

CREATE TRIGGER trg_durable_input_no_delete
    BEFORE DELETE ON durable_input
BEGIN
    SELECT RAISE (ABORT, 'durable input rows are retained');
END;

CREATE TRIGGER trg_durable_input_semantic_key_binding
    BEFORE INSERT ON durable_input_semantic_key
    FOR EACH ROW
    WHEN NOT (
            (
                NEW.key_kind IN (
                    'VENUE_COMMAND_V2',
                    'VENUE_EXECUTION_FACT_V1',
                    'VENUE_COVERAGE_ROOT_V1',
                    'VENUE_COVERAGE_INTERVAL_V1',
                    'VENUE_BROKER_FACT_V1'
                )
                AND NEW.key_application_generation_id IS NULL
                AND NEW.key_scope_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM durable_input AS input
                     WHERE input.application_generation_id =
                            NEW.input_application_generation_id
                       AND input.input_domain = NEW.input_domain
                       AND input.input_identity_sha256 =
                            NEW.input_identity_sha256
                       AND input.execution_profile_id =
                            NEW.execution_profile_id
                       AND input.input_domain = 'VENUE_RECOVERY'
                )
            )
            OR (
                NEW.key_kind IN (
                    'AUTHORITY_QUERY_CLAIM_V1',
                    'AUTHORITY_MANUAL_FLATTEN_V1',
                    'AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1'
                )
                AND NEW.key_application_generation_id IS NOT NULL
                AND NEW.key_scope_id IS NOT NULL
                AND NEW.key_application_generation_id =
                        NEW.input_application_generation_id
                AND EXISTS (
                    SELECT 1 FROM durable_input AS input
                     WHERE input.application_generation_id =
                            NEW.input_application_generation_id
                       AND input.input_domain = NEW.input_domain
                       AND input.input_identity_sha256 =
                            NEW.input_identity_sha256
                       AND input.execution_profile_id =
                            NEW.execution_profile_id
                       AND input.scope_id = NEW.key_scope_id
                       AND input.input_domain = 'AUTHORITY'
                )
            )
        )
BEGIN
    SELECT RAISE (
        ABORT, 'durable input semantic key must bind its exact input domain'
    );
END;

CREATE TRIGGER trg_durable_input_semantic_key_immutable
    BEFORE UPDATE ON durable_input_semantic_key
BEGIN
    SELECT RAISE (ABORT, 'durable input semantic key rows are immutable');
END;

CREATE TRIGGER trg_durable_input_semantic_key_no_delete
    BEFORE DELETE ON durable_input_semantic_key
BEGIN
    SELECT RAISE (ABORT, 'durable input semantic key rows are retained');
END;

CREATE TRIGGER trg_decision_receipt_owner_binding
    BEFORE INSERT ON decision_receipt
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1 FROM durable_input AS input
             WHERE input.application_generation_id =
                    NEW.application_generation_id
               AND input.input_domain = NEW.input_domain
               AND input.input_identity_sha256 = NEW.input_identity_sha256
               AND (
                    (
                        input.input_domain = 'BROKER_EXECUTION'
                        AND NEW.owner_domain = 'POSITION'
                        AND NEW.owner_disposition IN (
                            'APPLIED', 'EXACT_REPLAY', 'FACT_CONFLICT',
                            'RECONCILIATION_REQUIRED'
                        )
                    )
                    OR (
                        input.input_domain = 'VENUE_RECOVERY'
                        AND NEW.owner_domain = 'VENUE_RECOVERY'
                        AND NEW.owner_disposition IN (
                            'APPLIED', 'EXACT_REPLAY', 'CONFLICT',
                            'RECONCILIATION_REQUIRED', 'REFUSED'
                        )
                    )
                    OR (
                        input.input_domain = 'AUTHORITY'
                        AND NEW.owner_domain = 'AUTHORITY'
                        AND NEW.owner_disposition IN (
                            'APPLIED', 'REFUSED', 'EXACT_REPLAY', 'CONFLICT'
                        )
                    )
                    OR (
                        input.input_domain IN (
                            'BEGIN_ACQUISITION_GENERATION',
                            'CREATE_ACQUISITION_EFFECT',
                            'CLAIM_ACQUISITION_EFFECT',
                            'BEGIN_ACQUISITION_PREEMPTION'
                        )
                        AND NEW.owner_domain = 'ACQUISITION'
                        AND NEW.owner_disposition IN (
                            'APPLIED', 'EXACT_REPLAY', 'REFUSED'
                        )
                    )
                    OR (
                        input.input_domain = 'MARKET_OCCURRENCE'
                        AND NEW.owner_domain = 'PROTECTION'
                        AND NEW.owner_disposition IN (
                            'APPLIED', 'EXACT_REPLAY', 'STALE', 'REFUSED'
                        )
                    )
               )
               AND (
                    (
                        NEW.owner_disposition = 'RECONCILIATION_REQUIRED'
                        AND NEW.terminal_technical_state =
                            'RECONCILIATION_PENDING'
                    )
                    OR (
                        NEW.owner_disposition <> 'RECONCILIATION_REQUIRED'
                        AND NEW.terminal_technical_state = 'TERMINAL'
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT, 'decision receipt must bind its input owner disposition'
    );
END;

CREATE TRIGGER trg_decision_receipt_no_conflict_replace
    BEFORE INSERT ON decision_receipt
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM decision_receipt AS retained
             WHERE retained.receipt_ordinal = NEW.receipt_ordinal
                OR (
                    retained.application_generation_id =
                        NEW.application_generation_id
                    AND retained.input_domain = NEW.input_domain
                    AND retained.input_identity_sha256 =
                        NEW.input_identity_sha256
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'decision receipt identity is already retained');
END;

CREATE TRIGGER trg_decision_receipt_immutable
    BEFORE UPDATE ON decision_receipt
BEGIN
    SELECT RAISE (ABORT, 'decision receipt rows are immutable');
END;

CREATE TRIGGER trg_decision_receipt_no_delete
    BEFORE DELETE ON decision_receipt
BEGIN
    SELECT RAISE (ABORT, 'decision receipt rows are retained');
END;

CREATE TRIGGER trg_durable_input_outcome_matches_receipt
    BEFORE INSERT ON durable_input_outcome
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1 FROM decision_receipt AS receipt
             WHERE receipt.application_generation_id =
                    NEW.application_generation_id
               AND receipt.input_domain = NEW.input_domain
               AND receipt.input_identity_sha256 = NEW.input_identity_sha256
               AND receipt.receipt_ordinal = NEW.receipt_ordinal
               AND receipt.receipt_sha256 = NEW.receipt_sha256
               AND receipt.owner_domain IS NEW.owner_domain
               AND receipt.owner_disposition IS NEW.owner_disposition
               AND receipt.terminal_technical_state IS
                    NEW.terminal_technical_state
               AND receipt.result_sha256 IS NEW.result_sha256
               AND receipt.checkpoint_currentness_head_ordinal IS
                    NEW.checkpoint_currentness_head_ordinal
               AND receipt.checkpoint_version_ordinal IS
                    NEW.checkpoint_version_ordinal
               AND receipt.checkpoint_payload_sha256 IS
                    NEW.checkpoint_payload_sha256
        )
BEGIN
    SELECT RAISE (
        ABORT, 'durable input outcome must exactly match its decision receipt'
    );
END;

CREATE TRIGGER trg_durable_input_outcome_immutable
    BEFORE UPDATE ON durable_input_outcome
BEGIN
    SELECT RAISE (ABORT, 'durable input outcome rows are immutable');
END;

CREATE TRIGGER trg_durable_input_outcome_no_delete
    BEFORE DELETE ON durable_input_outcome
BEGIN
    SELECT RAISE (ABORT, 'durable input outcome rows are retained');
END;

CREATE TRIGGER trg_broker_outbox_next_sequence
    BEFORE INSERT ON broker_outbox
    FOR EACH ROW
    WHEN NEW.outbox_sequence <> COALESCE(
            (SELECT MAX(outbox_sequence) + 1 FROM broker_outbox), 1
        )
BEGIN
    SELECT RAISE (ABORT, 'broker outbox sequence must be the next global ordinal');
END;

CREATE TRIGGER trg_broker_outbox_exact_input_route
    BEFORE INSERT ON broker_outbox
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM durable_input AS input
             WHERE input.application_generation_id =
                    NEW.application_generation_id
               AND input.input_domain = NEW.input_domain
               AND input.input_identity_sha256 = NEW.input_identity_sha256
               AND input.execution_profile_id = NEW.execution_profile_id
               AND input.scope_id = NEW.scope_id
               AND (
                    (
                        NEW.input_domain = 'AUTHORITY'
                        AND input.acquisition_generation_id IS NULL
                    )
                    OR (
                        NEW.input_domain = 'CLAIM_ACQUISITION_EFFECT'
                        AND input.acquisition_generation_id =
                            NEW.acquisition_generation_id
                    )
               )
        )
BEGIN
    SELECT RAISE (
        ABORT, 'broker outbox must bind its exact durable input route'
    );
END;

CREATE TRIGGER trg_broker_outbox_no_conflict_replace
    BEFORE INSERT ON broker_outbox
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1 FROM broker_outbox AS retained
             WHERE retained.outbox_sequence = NEW.outbox_sequence
                OR (
                    retained.effect_id = NEW.effect_id
                    AND retained.claim_id = NEW.claim_id
                )
        )
BEGIN
    SELECT RAISE (ABORT, 'broker outbox identity is already retained');
END;

CREATE TRIGGER trg_broker_outbox_immutable
    BEFORE UPDATE ON broker_outbox
BEGIN
    SELECT RAISE (ABORT, 'broker outbox rows are immutable');
END;

CREATE TRIGGER trg_broker_outbox_no_delete
    BEFORE DELETE ON broker_outbox
BEGIN
    SELECT RAISE (ABORT, 'broker outbox rows are retained');
END;
"""


class SchemaInstallError(Exception):
    """Base typed failure for the pure schema installer."""


class SchemaDigestMismatchError(SchemaInstallError):
    """The caller's approved digest does not match these exact DDL bytes."""


class SchemaTargetNotEmptyError(SchemaInstallError):
    """The supplied connection does not target an empty database."""


class SchemaForeignKeysDisabledError(SchemaInstallError):
    """PRAGMA foreign_keys did not verifiably report enabled on the connection."""


def _require_human_authorized_schema_install(actual_ddl_sha256: str) -> None:
    """Refuse before connection access unless Ameen unlocked these exact bytes."""

    if DDL_EXECUTION_AUTHORIZED_BY_AMEEN is not True:
        raise SchemaInstallError(
            "HUMAN-GATE pending: changed DDL execution is not authorized by Ameen"
        )
    if EXPECTED_EXECUTION_DDL_SHA256 != actual_ddl_sha256:
        raise SchemaDigestMismatchError(
            "expected execution DDL identity does not match the exact schema bytes; "
            "returning to the human gate"
        )


class SQLiteConnectionProtocol(_Protocol):
    """Structural subset of sqlite3.Connection used by the installer."""

    def execute(
        self, sql: str, parameters: _Sequence[_Any] = ()
    ) -> _Any: ...  # pragma: no cover - structural protocol


def schema_ddl() -> str:
    """Return the exact proposed schema bytes."""

    return SCHEMA_DDL


def schema_ddl_digest() -> str:
    """Return the lowercase SHA-256 of the exact UTF-8 DDL bytes."""

    return _sha256(SCHEMA_DDL.encode("utf-8")).hexdigest()


def _schema_catalog_digest(connection: SQLiteConnectionProtocol) -> str:
    """Hash the complete installed application-owned SQLite catalog."""

    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    digest = _sha256()
    for row in rows:
        for value in row:
            encoded = ("" if value is None else str(value)).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def _verify_connection_pragmas(connection: SQLiteConnectionProtocol) -> None:
    """Refuse a connection that cannot enforce the schema's relational rules."""

    foreign_keys_row = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys_row is None or int(foreign_keys_row[0]) != 1:
        raise SchemaForeignKeysDisabledError(
            "foreign keys must verifiably be enabled on every schema connection"
        )
    recursive_triggers_row = connection.execute("PRAGMA recursive_triggers").fetchone()
    if recursive_triggers_row is None or int(recursive_triggers_row[0]) != 1:
        raise SchemaInstallError(
            "recursive triggers must verifiably be enabled on every schema connection"
        )


def verify_schema_connection(connection: SQLiteConnectionProtocol) -> int:
    """Verify per-connection enforcement and the exact installed schema identity.

    SQLite enforcement pragmas are connection-local and reset when a database is
    reopened. Every future repository operation must call this guard before it
    reads or writes schema authority; direct SQL on an unverified connection is
    outside the persistence contract.
    """

    _verify_connection_pragmas(connection)
    meta_row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'"
    ).fetchone()
    if meta_row is None:
        raise SchemaInstallError(
            "connection does not expose the exact installed schema identity"
        )
    identity_rows = connection.execute(
        "SELECT schema_version, approved_ddl_sha256, observed_catalog_sha256"
        " FROM schema_meta"
    ).fetchall()
    current_ddl_sha256 = schema_ddl_digest()
    if EXPECTED_EXECUTION_DDL_SHA256 != current_ddl_sha256:
        raise SchemaInstallError(
            "current schema bytes do not match the expected execution DDL identity"
        )
    expected = (SCHEMA_VERSION, EXPECTED_EXECUTION_DDL_SHA256)
    if len(identity_rows) != 1:
        raise SchemaInstallError(
            "connection does not expose the exact installed schema identity"
        )
    retained_identity = tuple(identity_rows[0])
    if len(retained_identity) != 3 or retained_identity[:2] != expected:
        raise SchemaInstallError(
            "connection does not expose the exact installed schema identity"
        )
    observed_catalog_sha256 = retained_identity[2]
    if (
        type(observed_catalog_sha256) is not str
        or len(observed_catalog_sha256) != 64
        or any(
            character not in "0123456789abcdef" for character in observed_catalog_sha256
        )
    ):
        raise SchemaInstallError(
            "connection does not expose the exact installed schema identity"
        )
    if _schema_catalog_digest(connection) != observed_catalog_sha256:
        raise SchemaInstallError(
            "connection does not expose the exact installed schema catalog"
        )
    return SCHEMA_VERSION


def _ddl_statements() -> tuple[str, ...]:
    """Split fixed DDL without importing or acquiring a database capability.

    The checked-in DDL emits one ordinary statement at each semicolon-terminated
    line. Trigger bodies are the sole exception: their internal statements are
    retained until the top-level, unindented ``END;`` terminator. Installation
    tests execute every returned statement against SQLite, so unsupported DDL
    formatting fails at the bounded proof boundary.
    """

    statements: list[str] = []
    pending: list[str] = []
    is_trigger = False
    for line in SCHEMA_DDL.splitlines():
        if not pending and not line.strip():
            continue
        if not pending:
            is_trigger = line.startswith("CREATE TRIGGER ")
        pending.append(line)
        complete = line == "END;" if is_trigger else line.rstrip().endswith(";")
        if complete:
            statements.append("\n".join(pending).strip())
            pending = []
            is_trigger = False
    if pending:
        raise RuntimeError("SCHEMA_DDL ended with an incomplete SQLite statement")
    return tuple(statements)


def _require_exact_approved_ddl_digest(
    approved_ddl_sha256: str,
    actual_ddl_sha256: str,
) -> None:
    """Refuse a stale approval before a connection can be inspected or changed."""

    if approved_ddl_sha256 != actual_ddl_sha256:
        raise SchemaDigestMismatchError(
            "approved_ddl_sha256 does not match the exact schema bytes; "
            "returning to the human gate"
        )


def install_schema(
    connection: SQLiteConnectionProtocol,
    *,
    approved_ddl_sha256: str,
) -> int:
    """Install the human-approved schema onto an explicitly supplied empty DB.

    Refuses before executing anything unless the approved digest matches
    these exact bytes, the target is empty, and foreign keys verifiably
    report enabled. Returns the installed schema version on success.
    """

    actual_digest = schema_ddl_digest()
    _require_human_authorized_schema_install(actual_digest)
    _require_exact_approved_ddl_digest(approved_ddl_sha256, actual_digest)
    _verify_connection_pragmas(connection)

    connection.execute("BEGIN IMMEDIATE")
    try:
        master_row = connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        if master_row is None or int(master_row[0]) != 0:
            raise SchemaTargetNotEmptyError(
                "schema installer requires an explicitly supplied empty database"
            )
        for statement in _ddl_statements():
            connection.execute(statement)
        observed_catalog_sha256 = _schema_catalog_digest(connection)
        connection.execute(
            "INSERT INTO schema_meta (schema_version, approved_ddl_sha256,"
            " observed_catalog_sha256) VALUES (?, ?, ?)",
            (SCHEMA_VERSION, actual_digest, observed_catalog_sha256),
        )
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    return SCHEMA_VERSION


__all__ = (
    "SCHEMA_DDL",
    "SCHEMA_VERSION",
    "SchemaDigestMismatchError",
    "SchemaForeignKeysDisabledError",
    "SchemaInstallError",
    "SchemaTargetNotEmptyError",
    "SQLiteConnectionProtocol",
    "install_schema",
    "schema_ddl",
    "schema_ddl_digest",
    "verify_schema_connection",
)
