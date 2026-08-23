"""Static directness controls for the non-serving runtime-checkpoint boundary."""

from __future__ import annotations

import ast
import hashlib
import inspect
import re

from app.execution_core.persistence import records, repository


_QUERY_SHA256 = (
    "48cfa92f658d370ea402934d3a8f80af2fb39002292365fef62b63247f7e79bf",
    "79cd0a08e4d64780d4dbdeca2351aa109534f2b7629963ee25672508f062cb11",
    "cf152cb66b8dab1801305de267abead4b9c4d3b4e32e7346d7c2b42f496d26f9",
    "fededb93e1c6f8a20027051cfe0fcdc9013e9c6359d593af5b1079b6f7492585",
    "91202fbda506657de2242dc184fb3cb1c850b223d520a12c6c33eba04a73c6f2",
    "cfef75830aca3e2da2d9badf8db86bacb515312e86b5c069923118ad391379f1",
    "1cd3183474299a03d2a73b558896cf51f7d28f4994fa87de9cd7ed0b49488c0a",
    "21d7552bdc966e559d4543c6e631928ba2b01e60e8e80641181c2183ebf4ca7b",
    "a2f32ed485edde2a7e51014bfe2416bdfb4e0884a38996c1a4231960b97974d0",
    "97bbe0367b57cb460e66d19854bda8b8c51b4b7f500dc68440addeec66e97727",
    "1c034577ce7eaadc7aaaa63eb392df8b32ecdb6c7e45a8608adf38874147693c",
    "d7a326e623de948ad93840f3965e60977993d0f9862e302283d8dc79be5d649a",
    "6731c3b17fb5ed258f36c97bda4cf22e73718f697c547bda743edb2941c0f834",
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
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_classify_runtime_checkpoint_sqlite_failure" in definitions
    assert source.count("def _classify_runtime_checkpoint_sqlite_failure(") == 1
    assert source.count("def _issue_runtime_checkpoint_write_receipt(") == 1
    assert "_activate_runtime_write_lease" not in source
    assert "_retire_runtime_write_lease" not in source
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
