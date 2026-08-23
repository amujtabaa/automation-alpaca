"""Pure API and boundary tests for the M2 checkpoint-codec seam."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.execution_core.persistence import checkpoint_codec, records, repository


def test_checkpoint_codec_is_inert_and_exposes_only_nonserving_checkpoint_surface() -> (
    None
):
    assert checkpoint_codec.__all__ == (
        "InertRuntimeCheckpointComponent",
        "RuntimeCheckpointEnvelope",
        "RuntimeCheckpointScopeCandidate",
        "encode_runtime_checkpoint",
    )

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


def test_wo0168c_exposes_only_the_frozen_nonserving_checkpoint_surface() -> None:
    assert hasattr(checkpoint_codec, "RuntimeCheckpointEnvelope")
    assert "RuntimeCheckpointPayloadRecord" in records.__all__
    assert hasattr(records, "RuntimeCheckpointPayloadRecord")
    assert "store_runtime_checkpoint_payload" not in repository.__all__
    assert "load_runtime_checkpoint_payload" not in repository.__all__
    assert not hasattr(repository, "store_runtime_checkpoint_payload")
    assert not hasattr(repository, "load_runtime_checkpoint_payload")
    assert "store_kernel_checkpoint" not in repository.__all__
    assert "advance_kernel_checkpoint" not in repository.__all__
    assert "load_kernel_checkpoint" not in repository.__all__
    assert not hasattr(repository, "store_kernel_checkpoint")
    assert not hasattr(repository, "advance_kernel_checkpoint")
    assert not hasattr(repository, "load_kernel_checkpoint")


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
