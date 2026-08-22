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
facts whose revisions must stay inside their own root (no duplicate roots,
no cross-root/cross-owner predecessors, no gaps); canonical effect ownership
of OPEN|CLOSED|INVALIDATED with claim-before-CLOSED and terminal freeze;
append-only claims, closures, facts, and acceptance evidence; gap-free,
branch-free, same-owner closure ordinals via composite foreign keys plus a
single-successor uniqueness rule; monotonic current heads for checkpoint,
controller, root economics, protection version, and market cursor; and one
current market cursor per stream-generation/source-profile binding.
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
CREATE UNIQUE INDEX uq_execution_fact_m1_key ON execution_fact (
    broker_text,
    environment_text,
    account_text,
    source_event_id
);
CREATE INDEX ix_execution_fact_root_head ON execution_fact (root_fill_key_id, fact_ordinal DESC);

CREATE TABLE venue_effect (
    effect_id INTEGER PRIMARY KEY,
    scope_id INTEGER NOT NULL REFERENCES acquisition_scope (scope_id),
    root_fill_key_id INTEGER NOT NULL,

    order_external TEXT NOT NULL CHECK (length(order_external) >= 1),
    disposition TEXT NOT NULL CHECK (disposition IN ('OPEN', 'CLOSED', 'INVALIDATED')),
    created_ordinal INTEGER NOT NULL UNIQUE CHECK (created_ordinal >= 1),
    UNIQUE (scope_id, order_external),
    UNIQUE (effect_id, scope_id),
    FOREIGN KEY (root_fill_key_id, scope_id)
        REFERENCES root_fill (root_fill_key_id, scope_id)
);

CREATE INDEX ix_venue_effect_scope_state ON venue_effect (scope_id, disposition, effect_id);

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

CREATE TABLE acceptance_set (
    acceptance_set_id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL UNIQUE REFERENCES venue_effect (effect_id),
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'CLOSED', 'INVALIDATED'))
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
    FOREIGN KEY (scope_id, effect_id)
        REFERENCES venue_effect (scope_id, effect_id),
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

CREATE TRIGGER trg_acquisition_generation_retire_only
    BEFORE UPDATE OF status, successor_ordinal, predecessor_generation_id, mandate_commitment_sha256, emergency_compatibility_sha256, scope_id, acquisition_generation_id
    ON acquisition_generation
    FOR EACH ROW
    WHEN NOT (
        OLD.status = 'LIVE'
        AND NEW.status = 'RETIRED_UNSERVING'
    )
BEGIN
    SELECT RAISE (ABORT, 'acquisition_generation may only retire in place');
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

CREATE TRIGGER trg_symbol_controller_no_delete
    BEFORE DELETE ON symbol_controller
BEGIN
    SELECT RAISE (ABORT, 'symbol_controller rows are retained');
END;

CREATE TRIGGER trg_root_fill_identity_immutable
    BEFORE UPDATE OF scope_id, owner_generation_id, root_fill_external ON root_fill
BEGIN
    SELECT RAISE (ABORT, 'root_fill identity is immutable');
END;

CREATE TRIGGER trg_root_fill_economics_monotonic
    BEFORE UPDATE OF economics_head_ordinal ON root_fill
    FOR EACH ROW
    WHEN NEW.economics_head_ordinal < OLD.economics_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'root_fill economics head may only advance');
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

CREATE TRIGGER trg_venue_effect_terminal_freeze
    BEFORE UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN OLD.disposition <> 'OPEN' AND NEW.disposition <> 'INVALIDATED'
BEGIN
    SELECT RAISE (ABORT, 'venue_effect disposition may not leave a terminal state');
END;

CREATE TRIGGER trg_venue_effect_close_requires_claim
    BEFORE UPDATE OF disposition ON venue_effect
    FOR EACH ROW
    WHEN NEW.disposition = 'CLOSED'
     AND OLD.disposition <> 'CLOSED'
     AND NOT EXISTS (
            SELECT 1
              FROM dispatch_claim AS claim
             WHERE claim.effect_id = NEW.effect_id
        )
BEGIN
    SELECT RAISE (ABORT, 'venue_effect CLOSED requires a committed dispatch claim');
END;

CREATE TRIGGER trg_venue_effect_no_delete
    BEFORE DELETE ON venue_effect
BEGIN
    SELECT RAISE (ABORT, 'venue_effect rows are retained');
END;

CREATE TRIGGER trg_dispatch_claim_resolution_once
    BEFORE UPDATE OF resolved_kind ON dispatch_claim
    FOR EACH ROW
    WHEN OLD.resolved_kind IS NOT NULL OR NEW.resolved_kind IS NULL
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim resolves at most once');
END;

CREATE TRIGGER trg_dispatch_claim_append_only_columns
    BEFORE UPDATE OF effect_id, claim_ordinal ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim binding columns are immutable');
END;

CREATE TRIGGER trg_dispatch_claim_no_delete
    BEFORE DELETE ON dispatch_claim
BEGIN
    SELECT RAISE (ABORT, 'dispatch_claim rows are append-only');
END;

CREATE TRIGGER trg_acceptance_set_forward_only
    BEFORE UPDATE OF state ON acceptance_set
    FOR EACH ROW
    WHEN NOT (
        (OLD.state = 'OPEN' AND NEW.state IN ('CLOSED', 'INVALIDATED'))
        OR (OLD.state = 'CLOSED' AND NEW.state = 'INVALIDATED')
    )
BEGIN
    SELECT RAISE (ABORT, 'acceptance_set state machine violated');
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
             WHERE accepted.acceptance_set_id = NEW.acceptance_set_id
               AND accepted.state = 'CLOSED'
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

CREATE TRIGGER trg_protection_authority_version_monotonic
    BEFORE UPDATE OF version_ordinal ON protection_authority
    FOR EACH ROW
    WHEN NEW.version_ordinal < OLD.version_ordinal
BEGIN
    SELECT RAISE (ABORT, 'protection_authority version may only advance');
END;

CREATE TRIGGER trg_market_cursor_ordinals_monotonic
    BEFORE UPDATE OF fixed_cursor_ordinal, published_head_ordinal ON market_cursor
    FOR EACH ROW
    WHEN NEW.fixed_cursor_ordinal < OLD.fixed_cursor_ordinal
      OR NEW.published_head_ordinal < OLD.published_head_ordinal
BEGIN
    SELECT RAISE (ABORT, 'market_cursor ordinals may only advance');
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
