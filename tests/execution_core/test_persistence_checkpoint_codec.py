"""Pure API and boundary tests for the M2 checkpoint-codec seam."""

from __future__ import annotations

import ast
from hashlib import sha256
import inspect
from pathlib import Path

import pytest

from app.execution_core.persistence import checkpoint_codec, records
from app.execution_core.identity import ApplicationGenerationId


def test_checkpoint_codec_is_inert_and_exposes_only_the_envelope_type() -> None:
    assert checkpoint_codec.__all__ == ("RuntimeCheckpointEnvelope",)
    with pytest.raises(TypeError, match="codec-issued"):
        checkpoint_codec.RuntimeCheckpointEnvelope()

    tree = ast.parse(inspect.getsource(checkpoint_codec))
    imported_modules = {
        alias.name
        for statement in tree.body
        if isinstance(statement, ast.Import)
        for alias in statement.names
    }
    assert "sqlite3" not in imported_modules


def test_checkpoint_codec_refuses_a_forged_current_proof_before_adaptation() -> None:
    forged = object.__new__(records.CurrentProofSlice)

    assert not records.CurrentProofSlice._is_authentic(forged)


def test_runtime_checkpoint_payload_record_binds_exact_bytes_and_coordinates() -> None:
    payload = b"execution-core/m2-document/v1\n\x02\x00\x00\x00\x00\x00\x00\x00\x02[]"
    record = records.RuntimeCheckpointPayloadRecord(
        ApplicationGenerationId("checkpoint-payload-app"),
        "ab" * 32,
        "cd" * 32,
        4,
        2,
        payload,
        len(payload),
        sha256(payload).hexdigest(),
    )

    assert record.payload_bytes == payload
    assert record.payload_length == len(payload)
    assert record.payload_sha256 == sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="payload length"):
        records.RuntimeCheckpointPayloadRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.market_source_profile_id,
            record.currentness_head_ordinal,
            record.checkpoint_version_ordinal,
            payload,
            len(payload) + 1,
            record.payload_sha256,
        )
    with pytest.raises(ValueError, match="payload SHA-256"):
        records.RuntimeCheckpointPayloadRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.market_source_profile_id,
            record.currentness_head_ordinal,
            record.checkpoint_version_ordinal,
            payload,
            len(payload),
            "00" * 32,
        )
    with pytest.raises(TypeError, match="head ordinal"):
        records.RuntimeCheckpointPayloadRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.market_source_profile_id,
            True,
            record.checkpoint_version_ordinal,
            payload,
            len(payload),
            record.payload_sha256,
        )


def test_current_proof_and_protection_issuers_have_one_production_route() -> None:
    app_root = Path(checkpoint_codec.__file__).resolve().parents[1]
    sources = {
        path.relative_to(app_root).as_posix(): path.read_text(encoding="utf-8")
        for path in app_root.rglob("*.py")
    }

    current_proof_issuer_users = {
        path for path, source in sources.items() if "_CURRENT_PROOF_ISSUER" in source
    }
    current_proof_factory_users = {
        path
        for path, source in sources.items()
        if "_issue_current_proof_slice" in source
    }
    protection_proof_factory_users = {
        path
        for path, source in sources.items()
        if "_m2_issue_protection_authority_proof" in source
    }

    assert current_proof_issuer_users == {
        "persistence/records.py",
        "persistence/repository.py",
    }
    assert current_proof_factory_users == {
        "persistence/records.py",
        "persistence/repository.py",
    }
    assert protection_proof_factory_users == {
        "persistence/checkpoint_codec.py",
        "protection.py",
    }
