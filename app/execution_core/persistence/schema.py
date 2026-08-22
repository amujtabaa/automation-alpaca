"""M2-I2 inert SQLite schema contract and pure installer (human-gated).

This module is the exact M2-I2 schema-definition candidate. Importing it
performs no work: it contains only string constants, exception types, a
structural connection protocol, and pure functions. It imports neither
``sqlite3`` nor any I/O, clock, randomness, network, credential, or runtime
surface, discovers no database path, and never opens or inspects any
database by itself. ``install_schema`` acts only on an explicitly supplied
empty SQLite connection and refuses to act unless:

1. the caller's ``approved_ddl_sha256`` equals the SHA-256 of these exact
   DDL bytes (EC-4: any byte drift returns to the human gate);
2. the supplied connection targets an empty database (zero ``sqlite_master``
   rows — EC-3: non-empty target refused before execution); and
3. ``PRAGMA foreign_keys`` verifiably reports ``1`` on that connection
   (EC-3: disabled foreign keys refused before execution).

The schema enforces, database-natively: immutable generation/profile
bindings with exactly one selected profile pair per application generation;
one LIVE acquisition generation per exact scope; immutable predecessor-linked
facts whose revisions must follow their root's current head (no duplicate
roots, cross-root predecessors, branches, or out-of-order revisions); exact
effect-to-owner-to-closure bindings; canonical effect ownership of
OPEN|CLOSED|INVALIDATED with claim-before-CLOSED and terminal freeze;
append-only claims, owners, closures, facts, and acceptance evidence;
gap-free, branch-free, same-owner closure ordinals; version-coupled current
proof for checkpoint, controller, root economics, and protection authority;
and one current market cursor per stream-generation/source-profile binding.
"""

from __future__ import annotations as _annotations

from hashlib import sha256 as _sha256
from typing import Any as _Any
from typing import Protocol as _Protocol
from typing import Sequence as _Sequence


SCHEMA_VERSION = 1

SCHEMA_DDL = """
CREATE TABLE schema_meta (
    schema_version INTEGER PRIMARY KEY,
    approved_ddl_sha256 TEXT NOT NULL
        CHECK (length(approved_ddl_sha256) = 64 AND approved_ddl_sha256 NOT GLOB '*[^0-9a-f]*')
);

CREATE TABLE execution_connection_profile (
    connection_profile_id TEXT PRIMARY KEY
        CHECK (length(connection_profile_id) = 64 AND connection_profile_id NOT GLOB '*[^0-9a-f]*'),
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
        CHECK (length(profile_commitment_sha256) = 64 AND profile_commitment_sha256 NOT GLOB '*[^0-9a-f]*')
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
        CHECK (length(application_generation_id) = 64 AND application_generation_id NOT GLOB '*[^0-9a-f]*'),
    selected_execution_profile_id TEXT NOT NULL
        REFERENCES execution_connection_profile (connection_profile_id),
    selected_market_source_profile_id TEXT NOT NULL
        REFERENCES market_data_source_profile (market_source_profile_id),
    activation_ordinal INTEGER NOT NULL UNIQUE CHECK (activation_ordinal >= 1)
);

CREATE TABLE acquisition_scope (
    scope_id INTEGER PRIMARY KEY,
    application_generation_id TEXT NOT NULL
        REFERENCES application_generation (application_generation_id),
    broker_text TEXT NOT NULL CHECK (length(broker_text) >= 1),
    environment_text TEXT NOT NULL CHECK (length(environment_text) >= 1),
    account_text TEXT NOT NULL CHECK (length(account_text) >= 1),
    symbol_text TEXT NOT NULL CHECK (length(symbol_text) >= 1),
    UNIQUE (application_generation_id, broker_text, environment_text, account_text, symbol_text)
);

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
    CHECK ((predecessor_generation_id IS NULL) = (successor_ordinal = 1))
);

CREATE UNIQUE INDEX uq_one_live_acquisition_per_scope
    ON acquisition_generation (scope_id)
    WHERE status = 'LIVE';

CREATE TABLE kernel_checkpoint (
    application_generation_id TEXT PRIMARY KEY
        REFERENCES application_generation (application_generation_id),
    currentness_head_ordinal INTEGER NOT NULL CHECK (currentness_head_ordinal >= 0),
    checkpoint_sha256 TEXT NOT NULL
        CHECK (length(checkpoint_sha256) = 64 AND checkpoint_sha256 NOT GLOB '*[^0-9a-f]*'),
    checkpoint_version_ordinal INTEGER NOT NULL UNIQUE CHECK (checkpoint_version_ordinal >= 1)
);

CREATE TABLE symbol_controller (
    scope_id INTEGER PRIMARY KEY REFERENCES acquisition_scope (scope_id),
    live_acquisition_generation_id TEXT,

    aggregate_quantity INTEGER NOT NULL CHECK (aggregate_quantity >= 0),
    basis_numerator INTEGER NOT NULL CHECK (basis_numerator >= 0),
    basis_denominator INTEGER NOT NULL CHECK (basis_denominator >= 1),
    currentness_head_ordinal INTEGER NOT NULL CHECK (currentness_head_ordinal >= 0),
    controller_version_ordinal INTEGER NOT NULL UNIQUE CHECK (controller_version_ordinal >= 1),
    emergency_compatibility_sha256 TEXT NOT NULL
        CHECK (length(emergency_compatibility_sha256) = 64 AND emergency_compatibility_sha256 NOT GLOB '*[^0-9a-f]*'),
    FOREIGN KEY (live_acquisition_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id)
);

CREATE TABLE root_fill (
    root_fill_key_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    owner_generation_id TEXT NOT NULL,

    root_fill_external TEXT NOT NULL CHECK (length(root_fill_external) >= 1),
    current_quantity INTEGER NOT NULL CHECK (current_quantity >= 0),
    price_units INTEGER NOT NULL,
    scale_sign INTEGER NOT NULL CHECK (scale_sign IN (0, 1)),
    scale_digits TEXT NOT NULL
        CHECK (
            scale_digits <> ''
            AND scale_digits NOT GLOB '*[^0-9]*'
            AND (scale_digits = '0' OR substr(scale_digits, 1, 1) <> '0')
        ),
    scale_exponent INTEGER NOT NULL,
    economics_head_ordinal INTEGER NOT NULL CHECK (economics_head_ordinal >= 0),
    UNIQUE (scope_id, root_fill_external),
    UNIQUE (root_fill_key_id, scope_id),
    UNIQUE (root_fill_key_id, scope_id, owner_generation_id),
    FOREIGN KEY (owner_generation_id, scope_id)
        REFERENCES acquisition_generation (acquisition_generation_id, scope_id)
);

CREATE INDEX ix_root_fill_owner ON root_fill (owner_generation_id, root_fill_key_id);

CREATE TABLE execution_fact (
    fact_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    application_generation_id TEXT NOT NULL
        REFERENCES application_generation (application_generation_id),
    broker_text TEXT NOT NULL CHECK (length(broker_text) >= 1),
    environment_text TEXT NOT NULL CHECK (length(environment_text) >= 1),
    account_text TEXT NOT NULL CHECK (length(account_text) >= 1),
    root_fill_key_id INTEGER NOT NULL,
    source_event_id TEXT NOT NULL CHECK (length(source_event_id) >= 1),
    kind TEXT NOT NULL CHECK (kind IN ('FILL', 'TRADE_CORRECT', 'TRADE_BUST')),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    price_units INTEGER,
    scale_sign INTEGER CHECK (scale_sign IN (0, 1)),
    scale_digits TEXT
        CHECK (
            scale_digits IS NULL
            OR (
                scale_digits <> ''
                AND scale_digits NOT GLOB '*[^0-9]*'
                AND (scale_digits = '0' OR substr(scale_digits, 1, 1) <> '0')
            )
        ),
    scale_exponent INTEGER,
    predecessor_fact_id INTEGER,
    fact_ordinal INTEGER NOT NULL UNIQUE CHECK (fact_ordinal >= 1),
    CHECK ((kind = 'FILL') = (predecessor_fact_id IS NULL)),
    CHECK (predecessor_fact_id IS NULL OR predecessor_fact_id <> fact_id),
    CHECK ((price_units IS NULL) = (scale_sign IS NULL)),
    CHECK ((scale_sign IS NULL) = (scale_digits IS NULL)),
    CHECK ((scale_digits IS NULL) = (scale_exponent IS NULL)),
    CHECK (kind <> 'FILL' OR quantity > 0),
    FOREIGN KEY (root_fill_key_id, scope_id)
        REFERENCES root_fill (root_fill_key_id, scope_id),
    FOREIGN KEY (root_fill_key_id, predecessor_fact_id)
        REFERENCES execution_fact (root_fill_key_id, fact_id)
);

CREATE UNIQUE INDEX uq_execution_fact_root_fact ON execution_fact (root_fill_key_id, fact_id);
CREATE UNIQUE INDEX uq_execution_fact_root_fact_ordinal
    ON execution_fact (root_fill_key_id, fact_id, fact_ordinal);
CREATE UNIQUE INDEX uq_execution_fact_one_fill_per_root
    ON execution_fact (root_fill_key_id)
    WHERE kind = 'FILL';
CREATE UNIQUE INDEX uq_execution_fact_m1_key ON execution_fact (
    broker_text,
    environment_text,
    account_text,
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
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    root_fill_key_id INTEGER NOT NULL,

    order_external TEXT NOT NULL CHECK (length(order_external) >= 1),
    disposition TEXT NOT NULL CHECK (disposition IN ('OPEN', 'CLOSED', 'INVALIDATED')),
    created_ordinal INTEGER NOT NULL UNIQUE CHECK (created_ordinal >= 1),
    UNIQUE (scope_id, order_external),
    UNIQUE (effect_id, scope_id),
    UNIQUE (effect_id, scope_id, root_fill_key_id),
    FOREIGN KEY (root_fill_key_id, scope_id)
        REFERENCES root_fill (root_fill_key_id, scope_id)
);

CREATE INDEX ix_venue_effect_scope_state ON venue_effect (scope_id, disposition, effect_id);

CREATE TABLE venue_identity_owner (
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    owner_external TEXT NOT NULL CHECK (length(owner_external) >= 1),
    effect_id INTEGER NOT NULL,
    root_fill_key_id INTEGER NOT NULL,
    owner_generation_id TEXT NOT NULL,
    PRIMARY KEY (scope_id, owner_external),
    UNIQUE (scope_id, owner_external, effect_id),
    FOREIGN KEY (effect_id, scope_id, root_fill_key_id)
        REFERENCES venue_effect (effect_id, scope_id, root_fill_key_id),
    FOREIGN KEY (root_fill_key_id, scope_id, owner_generation_id)
        REFERENCES root_fill (root_fill_key_id, scope_id, owner_generation_id)
);

CREATE INDEX ix_venue_identity_owner_effect
    ON venue_identity_owner (effect_id, scope_id, owner_external);

CREATE TABLE dispatch_claim (
    claim_id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL REFERENCES venue_effect (effect_id),
    claim_ordinal INTEGER NOT NULL UNIQUE CHECK (claim_ordinal >= 1),
    resolved_kind TEXT CHECK (resolved_kind IN ('DISPATCHED', 'TIMEOUT_QUARANTINE')),
    UNIQUE (effect_id, claim_ordinal)
);

CREATE UNIQUE INDEX uq_one_open_claim_per_effect
    ON dispatch_claim (effect_id)
    WHERE resolved_kind IS NULL;

CREATE TABLE effect_closure_proof (
    effect_id INTEGER PRIMARY KEY REFERENCES venue_effect (effect_id),
    proof_kind TEXT NOT NULL
        CHECK (proof_kind IN ('CLAIMED_TERMINAL', 'ADAPTER_COMPLETE', 'TARGETED_QUERY_COMPLETE', 'NEVER_DISPATCHED')),
    proof_digest TEXT NOT NULL
        CHECK (length(proof_digest) = 64 AND proof_digest NOT GLOB '*[^0-9a-f]*')
);

CREATE TABLE acceptance_set (
    acceptance_set_id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL UNIQUE REFERENCES venue_effect (effect_id)
);

CREATE TABLE acceptance_evidence (
    evidence_id INTEGER PRIMARY KEY,
    acceptance_set_id INTEGER NOT NULL REFERENCES acceptance_set (acceptance_set_id),
    evidence_kind TEXT NOT NULL
        CHECK (evidence_kind IN ('OBSERVATION', 'CLOSURE_PROOF', 'INVALIDATION', 'RECONCILIATION_NOTE')),
    evidence_digest TEXT NOT NULL
        CHECK (length(evidence_digest) = 64 AND evidence_digest NOT GLOB '*[^0-9a-f]*'),
    evidence_ordinal INTEGER NOT NULL UNIQUE CHECK (evidence_ordinal >= 1)
);

CREATE INDEX ix_acceptance_evidence_set ON acceptance_evidence (acceptance_set_id, evidence_ordinal DESC);

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
    CHECK ((predecessor_closure_id IS NULL) = (ordinal = 1))
);

CREATE UNIQUE INDEX uq_closure_single_successor
    ON closure_chain (scope_id, owner_external, predecessor_closure_id)
    WHERE predecessor_closure_id IS NOT NULL;

CREATE UNIQUE INDEX uq_closure_single_root
    ON closure_chain (scope_id, owner_external)
    WHERE predecessor_closure_id IS NULL;

CREATE INDEX ix_closure_chain_head ON closure_chain (scope_id, owner_external, ordinal DESC);

CREATE TABLE protection_authority (
    scope_id INTEGER PRIMARY KEY REFERENCES acquisition_scope (scope_id),
    active_stream_generation_id TEXT
        CHECK (
            active_stream_generation_id IS NULL
            OR (
                length(active_stream_generation_id) = 64
                AND active_stream_generation_id NOT GLOB '*[^0-9a-f]*'
            )
        ),
    state_commitment_sha256 TEXT NOT NULL
        CHECK (length(state_commitment_sha256) = 64 AND state_commitment_sha256 NOT GLOB '*[^0-9a-f]*'),
    version_ordinal INTEGER NOT NULL UNIQUE CHECK (version_ordinal >= 1)
);

CREATE TABLE market_cursor (
    stream_generation_id TEXT NOT NULL
        CHECK (length(stream_generation_id) = 64 AND stream_generation_id NOT GLOB '*[^0-9a-f]*'),
    source_profile_id TEXT NOT NULL
        REFERENCES market_data_source_profile (market_source_profile_id),
    fixed_cursor_ordinal INTEGER NOT NULL CHECK (fixed_cursor_ordinal >= 0),
    published_head_ordinal INTEGER NOT NULL CHECK (published_head_ordinal >= 0),
    PRIMARY KEY (stream_generation_id, source_profile_id)
);

CREATE TRIGGER trg_schema_meta_immutable_update
    BEFORE UPDATE ON schema_meta
BEGIN
    SELECT RAISE (ABORT, 'schema_meta is immutable');
END;

CREATE TRIGGER trg_schema_meta_immutable_delete
    BEFORE DELETE ON schema_meta
BEGIN
    SELECT RAISE (ABORT, 'schema_meta is immutable');
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

CREATE TRIGGER trg_acquisition_generation_predecessor_valid
    BEFORE INSERT ON acquisition_generation
    FOR EACH ROW
    WHEN NEW.predecessor_generation_id IS NOT NULL
BEGIN
    SELECT RAISE (
        ABORT,
        'acquisition predecessor must be the immediate prior ordinal of '
            || 'the same scope'
    )
    WHERE NOT EXISTS (
            SELECT 1
              FROM acquisition_generation AS predecessor
             WHERE predecessor.acquisition_generation_id =
                   NEW.predecessor_generation_id
               AND predecessor.scope_id = NEW.scope_id
               AND predecessor.successor_ordinal = NEW.successor_ordinal - 1
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
    BEFORE UPDATE OF scope_id, emergency_compatibility_sha256 ON symbol_controller
    FOR EACH ROW
    WHEN NEW.scope_id IS NOT OLD.scope_id
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

CREATE TRIGGER trg_symbol_controller_versioned_replace
    BEFORE UPDATE ON symbol_controller
    FOR EACH ROW
    WHEN NEW.controller_version_ordinal < OLD.controller_version_ordinal
      OR (
            (
                NEW.live_acquisition_generation_id
                    IS NOT OLD.live_acquisition_generation_id
                OR NEW.aggregate_quantity IS NOT OLD.aggregate_quantity
                OR NEW.basis_numerator IS NOT OLD.basis_numerator
                OR NEW.basis_denominator IS NOT OLD.basis_denominator
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
        basis_numerator, basis_denominator ON symbol_controller
    FOR EACH ROW
    WHEN (
            NEW.live_acquisition_generation_id
                IS NOT OLD.live_acquisition_generation_id
            OR NEW.aggregate_quantity IS NOT OLD.aggregate_quantity
            OR NEW.basis_numerator IS NOT OLD.basis_numerator
            OR NEW.basis_denominator IS NOT OLD.basis_denominator
        )
      AND NEW.currentness_head_ordinal <= OLD.currentness_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'symbol controller head must advance');
END;

CREATE TRIGGER trg_symbol_controller_no_delete
    BEFORE DELETE ON symbol_controller
BEGIN
    SELECT RAISE (ABORT, 'symbol_controller rows are retained');
END;

CREATE TRIGGER trg_root_fill_identity_immutable
    BEFORE UPDATE OF root_fill_key_id, scope_id, owner_generation_id,
        root_fill_external ON root_fill
    FOR EACH ROW
    WHEN NEW.root_fill_key_id IS NOT OLD.root_fill_key_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.owner_generation_id IS NOT OLD.owner_generation_id
      OR NEW.root_fill_external IS NOT OLD.root_fill_external
BEGIN
    SELECT RAISE (ABORT, 'root_fill identity is immutable');
END;

CREATE TRIGGER trg_root_fill_economics_monotonic
    BEFORE UPDATE OF current_quantity, price_units, scale_sign, scale_digits,
        scale_exponent, economics_head_ordinal ON root_fill
    FOR EACH ROW
    WHEN NEW.economics_head_ordinal < OLD.economics_head_ordinal
      OR (
            (
                NEW.current_quantity IS NOT OLD.current_quantity
                OR NEW.price_units IS NOT OLD.price_units
                OR NEW.scale_sign IS NOT OLD.scale_sign
                OR NEW.scale_digits IS NOT OLD.scale_digits
                OR NEW.scale_exponent IS NOT OLD.scale_exponent
            )
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
    BEFORE UPDATE OF current_quantity, price_units, scale_sign, scale_digits,
        scale_exponent, economics_head_ordinal ON root_fill
    FOR EACH ROW
    WHEN (
            NEW.current_quantity IS NOT OLD.current_quantity
            OR NEW.price_units IS NOT OLD.price_units
            OR NEW.scale_sign IS NOT OLD.scale_sign
            OR NEW.scale_digits IS NOT OLD.scale_digits
            OR NEW.scale_exponent IS NOT OLD.scale_exponent
            OR NEW.economics_head_ordinal IS NOT OLD.economics_head_ordinal
        )
     AND NOT EXISTS (
            SELECT 1
              FROM execution_fact_head AS head
             WHERE head.root_fill_key_id = NEW.root_fill_key_id
               AND head.fact_ordinal = NEW.economics_head_ordinal
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'root_fill economics head must reference the current execution fact head'
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
                 OR scope.broker_text <> NEW.broker_text
                 OR scope.environment_text <> NEW.environment_text
                 OR scope.account_text <> NEW.account_text
                )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'execution_fact coordinates must equal their scope coordinates'
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

CREATE TRIGGER trg_venue_effect_terminal_freeze
    BEFORE UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN OLD.disposition <> 'OPEN' AND NEW.disposition <> 'INVALIDATED'
BEGIN
    SELECT RAISE (ABORT, 'venue_effect disposition may not leave a terminal state');
END;

CREATE TRIGGER trg_venue_effect_identity_immutable
    BEFORE UPDATE OF effect_id, scope_id, root_fill_key_id, order_external,
        created_ordinal ON venue_effect
    FOR EACH ROW
    WHEN NEW.effect_id IS NOT OLD.effect_id
      OR NEW.scope_id IS NOT OLD.scope_id
      OR NEW.root_fill_key_id IS NOT OLD.root_fill_key_id
      OR NEW.order_external IS NOT OLD.order_external
      OR NEW.created_ordinal IS NOT OLD.created_ordinal
BEGIN
    SELECT RAISE (ABORT, 'venue_effect identity is immutable');
END;

CREATE TRIGGER trg_venue_effect_close_requires_proof
    BEFORE UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN NEW.disposition = 'CLOSED'
     AND OLD.disposition <> 'CLOSED'
     AND (
            NOT EXISTS (
                SELECT 1
                  FROM effect_closure_proof AS proof
                 WHERE proof.effect_id = NEW.effect_id
            )
            OR EXISTS (
                SELECT 1
                  FROM effect_closure_proof AS proof
                 WHERE proof.effect_id = NEW.effect_id
                   AND proof.proof_kind = 'NEVER_DISPATCHED'
                   AND EXISTS (
                        SELECT 1
                          FROM dispatch_claim AS claim
                         WHERE claim.effect_id = NEW.effect_id
                   )
            )
            OR EXISTS (
                SELECT 1
                  FROM effect_closure_proof AS proof
                 WHERE proof.effect_id = NEW.effect_id
                   AND proof.proof_kind <> 'NEVER_DISPATCHED'
                   AND NOT EXISTS (
                        SELECT 1
                          FROM dispatch_claim AS claim
                         WHERE claim.effect_id = NEW.effect_id
                   )
            )
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'venue_effect CLOSED requires compatible immutable closure proof'
    );
END;

CREATE TRIGGER trg_venue_effect_no_delete
    BEFORE DELETE ON venue_effect
BEGIN
    SELECT RAISE (ABORT, 'venue_effect rows are retained');
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

CREATE TRIGGER trg_dispatch_claim_resolution_once
    BEFORE UPDATE OF resolved_kind ON dispatch_claim
    FOR EACH ROW
    WHEN OLD.resolved_kind IS NOT NULL OR NEW.resolved_kind IS NULL
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim resolves at most once');
END;

CREATE TRIGGER trg_dispatch_claim_refuses_never_dispatched_proof
    BEFORE INSERT ON dispatch_claim
    FOR EACH ROW
    WHEN EXISTS (
            SELECT 1
              FROM effect_closure_proof AS proof
             WHERE proof.effect_id = NEW.effect_id
               AND proof.proof_kind = 'NEVER_DISPATCHED'
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'dispatch claim contradicts NEVER_DISPATCHED closure proof'
    );
END;

CREATE TRIGGER trg_dispatch_claim_requires_open_effect
    BEFORE INSERT ON dispatch_claim
    FOR EACH ROW
    WHEN NOT EXISTS (
            SELECT 1
              FROM venue_effect AS effect
             WHERE effect.effect_id = NEW.effect_id
               AND effect.disposition = 'OPEN'
        )
BEGIN
    SELECT RAISE (ABORT, 'dispatch claim requires an OPEN venue effect');
END;

CREATE TRIGGER trg_dispatch_claim_append_only_columns
    BEFORE UPDATE OF claim_id, effect_id, claim_ordinal ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim binding columns are immutable');
END;

CREATE TRIGGER trg_dispatch_claim_no_delete
    BEFORE DELETE ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim rows are append-only');
END;

CREATE TRIGGER trg_effect_closure_proof_never_dispatched
    BEFORE INSERT ON effect_closure_proof
    FOR EACH ROW
    WHEN NEW.proof_kind = 'NEVER_DISPATCHED'
     AND EXISTS (
            SELECT 1
              FROM dispatch_claim AS claim
             WHERE claim.effect_id = NEW.effect_id
        )
BEGIN
    SELECT RAISE (
        ABORT,
        'NEVER_DISPATCHED proof is impossible after a dispatch claim'
    );
END;

CREATE TRIGGER trg_effect_closure_proof_no_update
    BEFORE UPDATE ON effect_closure_proof
BEGIN
    SELECT RAISE (ABORT, 'effect_closure_proof rows are immutable');
END;

CREATE TRIGGER trg_effect_closure_proof_no_delete
    BEFORE DELETE ON effect_closure_proof
BEGIN
    SELECT RAISE (ABORT, 'effect_closure_proof rows are retained');
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
               AND effect.disposition = 'CLOSED'
        )
     AND NEW.evidence_kind <> 'INVALIDATION'
BEGIN
    SELECT RAISE (ABORT, 'closed acceptance retains prior proof; only invalidation may append');
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
                NEW.active_stream_generation_id
                    IS NOT OLD.active_stream_generation_id
                OR NEW.state_commitment_sha256
                    IS NOT OLD.state_commitment_sha256
            )
            AND NEW.version_ordinal <= OLD.version_ordinal
        )
BEGIN
    SELECT RAISE (ABORT, 'protection version must advance');
END;

CREATE TRIGGER trg_protection_authority_identity_immutable
    BEFORE UPDATE OF scope_id ON protection_authority
    FOR EACH ROW
    WHEN NEW.scope_id IS NOT OLD.scope_id
BEGIN
    SELECT RAISE (ABORT, 'protection_authority identity is immutable');
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
    BEFORE UPDATE OF stream_generation_id, source_profile_id ON market_cursor
    FOR EACH ROW
    WHEN NEW.stream_generation_id IS NOT OLD.stream_generation_id
      OR NEW.source_profile_id IS NOT OLD.source_profile_id
BEGIN
    SELECT RAISE (ABORT, 'market_cursor identity is immutable');
END;

CREATE TRIGGER trg_market_cursor_no_delete
    BEFORE DELETE ON market_cursor
BEGIN
    SELECT RAISE (ABORT, 'market_cursor rows are retained');
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


class SQLiteConnectionProtocol(_Protocol):
    """Structural subset of sqlite3.Connection used by the installer."""

    def execute(
        self, sql: str, parameters: _Sequence[_Any] = ()
    ) -> _Any: ...  # pragma: no cover - structural protocol

    def executescript(
        self, sql: str
    ) -> _Any: ...  # pragma: no cover - structural protocol


def schema_ddl() -> str:
    """Return the exact proposed schema bytes."""

    return SCHEMA_DDL


def schema_ddl_digest() -> str:
    """Return the lowercase SHA-256 of the exact UTF-8 DDL bytes."""

    return _sha256(SCHEMA_DDL.encode("utf-8")).hexdigest()


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
    if approved_ddl_sha256 != actual_digest:
        raise SchemaDigestMismatchError(
            "approved_ddl_sha256 does not match the exact schema bytes; "
            "returning to the human gate"
        )
    master_row = connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    if master_row is None or int(master_row[0]) != 0:
        raise SchemaTargetNotEmptyError(
            "schema installer requires an explicitly supplied empty database"
        )
    foreign_keys_row = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys_row is None or int(foreign_keys_row[0]) != 1:
        raise SchemaForeignKeysDisabledError(
            "foreign keys must verifiably be enabled before installation"
        )
    connection.executescript(SCHEMA_DDL)
    connection.execute(
        "INSERT INTO schema_meta (schema_version, approved_ddl_sha256) VALUES (?, ?)",
        (SCHEMA_VERSION, actual_digest),
    )
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
)
