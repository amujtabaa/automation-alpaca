"""Static directness controls for the non-serving runtime-checkpoint boundary."""

from __future__ import annotations

import ast
import hashlib
import inspect
import re

from app.execution_core.persistence import records, repository, unit_of_work


_QUERY_SHA256 = (
    "48cfa92f658d370ea402934d3a8f80af2fb39002292365fef62b63247f7e79bf",
    "79cd0a08e4d64780d4dbdeca2351aa109534f2b7629963ee25672508f062cb11",
    "cf152cb66b8dab1801305de267abead4b9c4d3b4e32e7346d7c2b42f496d26f9",
    "2056ba5dbe2a6ffc304fdd52e2f15492cf47c27545eec2f0c71367b97fc9c4d6",
    "18e762935e10fd3baba1c0930e1b2ab43626fcd3aca20aaed274d4df2c37b4dd",
    "678fa0303c0d7a8b59af808a9c1c321e78c9e8ba57e55115909fcb1cf5c8deb1",
    "189214cec5232f162fa9521f6eefd831b7c74f14e16aa150ff609e4231d9114b",
    "dbf8a97e2e767bf587c745a4aa5091d9fac369deaec75594ccbad05572a04427",
    "9c2c3fc8c4825b8bd3b8ccf6f5bf1f7320c12034589eb8a77139e200025ffd8a",
    "ca2929f6f651b60b30f628086d8e886230c82ef89ba57b36e7d37d645dfc8951",
    "a86d2d4f0b5994f2d5ac49314003a171510acd7d5b11bb82c9ccc9a8fc9c9a61",
    "f1a326d518c662891cb4316872203465c9c038b372b6e9b435bae449c340e3bc",
    "6303e3efd04ae60ad565c8b068f4d27a1d31612dce325ba43ba53ac3c86dce70",
)
_VECTOR_SHA256 = (
    ("APP", "1fdf27aaa6776e10aeb44e011daec766d22e362bec41e6fab00a43f707a1bee6"),
    (
        "EXEC_PROFILE",
        "63a42303462e7cc076b3de47cefb1f2bdcde91be18e597469770d19d25884cc6",
    ),
    (
        "MARKET_PROFILE",
        "f9cfc1a0a2b57509986a64f516c227cf359020e89ebd33652b4939ab5a43cfe9",
    ),
    ("HEAD", "bfeceaa1dbd804c6cbfd962f7608a60793bff8fec5201d574a9f7ac56891814b"),
    ("SCOPE", "7953cc5b7827baa580f0f88f6c2bafee6a97f9c698b7b94c96c71428410a3136"),
    ("CONTROLLER", "7a7473c1910b7c4923199a093d61c83210d5c40f6c897bce89c8b34f0e2812d7"),
    ("PROTECTION", "042b2ad9beed2e07b92ffba31097a1b3a198b4e8e1eedb0506d3acc48ea19e65"),
    ("GENERATION", "fd39be2bf5a3a145914beec81696862d728e7aa863bc3bc65a15dc42779b02a8"),
    (
        "GENERATION_CURRENT",
        "3a8442e504ec872b3ff9abc1e49081b5b204d60ec5f3a49cb5d0100a0b9982b1",
    ),
    ("EFFECT", "d03ed10a80397b133d539ef47f1c3d97a32cbb637b5ff2ee373e1636ffad858c"),
    ("OWNER", "854be860578d324cb7a45e182a74df1c2266a6113a7ed6690b5f8a41cb3b47b5"),
    ("CLAIM", "be242bf7a070e3cb935a3084404cc20265ac1ec2c664863b9b32d34570a9fd32"),
    ("ACCEPTANCE", "77f410a5142861c27fd37958fb6f65b1b6ccab3662304ce8f7dfe92eef07f23b"),
    ("EVIDENCE", "33cb047c4e9df118b78431d5dd273d9f9e5a885be27c44f8a0d224cfa228fbb8"),
    ("CLOSURE", "8a345627ca0516ac2cb7bcf7b28fb7e7845d91f66f73c02eb4b87eb12b323f9d"),
    ("ROUTE", "fbf59d2dae4c81b5bece97f771a5e026e84f541b981f43847fab6f1725c6dee4"),
    ("ROOT", "9f51000d622764831a6528ebaaa0b60c3d63651fdd47028b315fc87d02d8d721"),
    ("FACT_HEAD", "97f640472b12a7a7f05e6ac9f7ed2ec47f2f5b3e134c91dd56babebf4148c65c"),
    ("FACT", "22f573282d44374a4bb7a1cb082ef695fa878b898d2deea3a326a929d0696a02"),
    ("STREAM", "1483db88d433faf53c9d7355905cfafc649a5ddc3f200fb872c63a52ddba924f"),
    ("CURSOR", "80f8a39b85b63fa9374225a329af624c01b397a44b9280233ce774b188f6da2b"),
    ("PAYLOAD", "425d3a2f947fe20631d8a47016d87794610a45f18ee7e209335947a8d001a381"),
)


def test_runtime_checkpoint_repository_has_one_static_thirteen_query_manifest() -> None:
    queries = repository._RUNTIME_CHECKPOINT_SELECTION_SQL

    assert type(queries) is tuple
    assert len(queries) == 13
    assert all(type(query) is str and "LIMIT" in query for query in queries)
    assert tuple(hashlib.sha256(query.encode()).hexdigest() for query in queries) == (
        _QUERY_SHA256
    )
    assert tuple(query.count("?") for query in queries) == (1, *([2] * 12))
    assert repository._RUNTIME_CHECKPOINT_CAP == 65_536
    assert repository._RUNTIME_CHECKPOINT_SCOPE_CAP == 4_097
    assert "ix_acquisition_scope_checkpoint" in queries[1]
    assert "ix_acquisition_generation_current_checkpoint_effect" in queries[3]
    assert "ix_acquisition_generation_current_checkpoint_protection" in queries[3]
    assert "ix_venue_owner_checkpoint_late" in queries[5]
    assert "ix_market_stream_authority_checkpoint_generation" in queries[12]
    assert all("?" in query for query in queries)
    assert all(
        query.startswith(repository._RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL)
        for query in queries[4:]
    )
    assert (
        tuple(
            (name, hashlib.sha256(columns.encode()).hexdigest())
            for name, columns in repository._RUNTIME_CHECKPOINT_STORAGE_VECTORS
        )
        == _VECTOR_SHA256
    )


def test_runtime_checkpoint_plan_access_manifest_is_complete_and_explicit() -> None:
    """Plan proof names every source beside the frozen SQL, with no SQL parser.

    A source parser had to guess whether tokens such as RIGHT, NATURAL, USING, or
    a comma were aliases.  This contract instead makes a query addition a reviewable
    metadata addition: each access says which base table it is, what EXPLAIN calls
    it, and whether a named hard index is mandatory.
    """

    queries = repository._RUNTIME_CHECKPOINT_SELECTION_SQL
    accesses = repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS

    assert len(accesses) == len(queries) == 13
    assert all(access for access in accesses)
    assert all(
        type(table) is str
        and table
        and type(plan_name) is str
        and plan_name
        and (required_index is None or (type(required_index) is str and required_index))
        for query_accesses in accesses
        for table, plan_name, required_index in query_accesses
    )

    named_accesses = tuple(
        access for query_accesses in accesses for access in query_accesses
    )
    expected_tables = {
        "acceptance_evidence",
        "acceptance_set",
        "acquisition_generation",
        "acquisition_generation_current",
        "acquisition_root_route",
        "acquisition_scope",
        "application_generation",
        "closure_chain",
        "dispatch_claim",
        "execution_connection_profile",
        "execution_fact",
        "execution_fact_head",
        "kernel_checkpoint",
        "market_cursor",
        "market_data_source_profile",
        "market_stream_authority",
        "protection_authority",
        "root_fill",
        "symbol_controller",
        "venue_effect",
        "venue_identity_owner",
    }
    assert {table for table, _, _ in named_accesses} == expected_tables

    all_sql = "\n".join(queries)
    for index in {
        required_index
        for _, _, required_index in named_accesses
        if required_index is not None
    }:
        expected_count = sum(
            required_index == index for _, _, required_index in named_accesses
        )
        assert all_sql.count(f"INDEXED BY {index}") == expected_count, index

    assert repository._RUNTIME_CHECKPOINT_LOAD_PLAN_ACCESS == (
        (("kernel_checkpoint", "kernel_checkpoint", None),),
        (("runtime_checkpoint_payload", "runtime_checkpoint_payload", None),),
    )


def test_runtime_checkpoint_write_sql_is_exact_and_transaction_free() -> None:
    assert repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL == (
        "INSERT INTO runtime_checkpoint_payload("
        "application_generation_id,execution_profile_id,market_source_profile_id,"
        "currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,"
        "payload_length,payload_sha256) VALUES (?,?,?,?,?,?,?,?)"
    )
    assert repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL == (
        "INSERT INTO kernel_checkpoint(application_generation_id,currentness_head_ordinal,"
        "checkpoint_sha256,checkpoint_version_ordinal) SELECT ?,?,?,? WHERE NOT EXISTS ("
        "SELECT 1 FROM kernel_checkpoint WHERE application_generation_id=?)"
    )
    assert repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL == (
        "UPDATE kernel_checkpoint SET currentness_head_ordinal=?,checkpoint_sha256=?,"
        "checkpoint_version_ordinal=? WHERE application_generation_id=? "
        "AND currentness_head_ordinal=? AND checkpoint_sha256=? "
        "AND checkpoint_version_ordinal=?"
    )
    checkpoint_sql = "\n".join(
        (
            *repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
            repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL,
        )
    ).upper()
    assert re.search(r"(?m)^\s*(BEGIN|COMMIT|ROLLBACK)\b", checkpoint_sql) is None
    assert "REPLACE" not in checkpoint_sql
    assert "UPSERT" not in checkpoint_sql


def test_runtime_checkpoint_classifier_and_issuers_have_one_source_route() -> None:
    source = inspect.getsource(repository)
    unit_source = inspect.getsource(unit_of_work)
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_classify_runtime_checkpoint_sqlite_failure" in definitions
    assert source.count("def _classify_runtime_checkpoint_sqlite_failure(") == 1
    assert source.count("def _issue_runtime_checkpoint_write_receipt(") == 1
    assert source.count("def _activate_runtime_write_lease(") == 1
    assert source.count("def _retire_runtime_write_lease(") == 1
    assert "_activate_runtime_write_lease" not in repository.__all__
    assert "_retire_runtime_write_lease" not in repository.__all__
    assert unit_source.count("_repository._activate_runtime_write_lease(") == 1
    assert unit_source.count("_repository._retire_runtime_write_lease(") == 2
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sqlite3" not in imported


def test_runtime_checkpoint_public_repository_surface_is_exactly_added() -> None:
    expected = {
        "select_runtime_checkpoint",
        "store_runtime_checkpoint",
        "load_runtime_checkpoint_payload",
        "load_runtime_checkpoint",
    }

    assert expected <= set(repository.__all__)
    assert "store_runtime_checkpoint_payload" not in repository.__all__
    assert "load_kernel_checkpoint" not in repository.__all__
    assert "store_kernel_checkpoint" not in repository.__all__


def test_runtime_checkpoint_records_integration_routes_and_boolean_domains_exist() -> (
    None
):
    assert callable(records._runtime_checkpoint_selection_proof_is_authentic)
    assert callable(records._issue_runtime_checkpoint_load_proof_binding)
    absent_fact_price = records._runtime_checkpoint_price_columns(
        None, absent_is_null=False
    )
    absent_root_price = records._runtime_checkpoint_price_columns(
        None, absent_is_null=True
    )

    assert absent_fact_price[0] is False
    assert absent_root_price[0] is None
    assert records._runtime_checkpoint_storage_field_binding(False) != (
        records._runtime_checkpoint_storage_field_binding(0)
    )
