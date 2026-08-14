from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_native_fixed64_prepared_session_v1 import (
    ContractError,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_PYTHON_SOURCE,
    DEFAULT_RUST_SOURCE,
    DEFAULT_TEST_SOURCE,
    verify,
)


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


def test_prepared_session_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["persistent_context_reuse"] is True
    assert result["scientific_result_cached"] is False
    assert result["native_entrypoint"] == "native_fixed64_prepare_session_v1"
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["lifecycle"].update(
            context_created_once_per_session=False
        ),
        lambda document: document["lifecycle"].update(
            native_pipeline_destroyed_before_owned_input=False
        ),
        lambda document: document["lifecycle"].update(scientific_result_cached=True),
        lambda document: document["scope"].update(candidate_denominator=63),
        lambda document: document["api"].update(
            native_entrypoint="native_fixed64_complete_pipeline_v3"
        ),
    ),
)
def test_prepared_session_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


@pytest.mark.parametrize(
    ("source_kind", "needle"),
    (
        ("rust", '#[pyclass(unsendable, name = "NativeFixed64PreparedSessionV1")]'),
        ("python", "def prepare_native_fixed64_session("),
        (
            "test",
            "test_prepared_session_reuses_one_native_context_without_caching_science",
        ),
        ("documentation", "External authority must reach blocker zero"),
    ),
)
def test_prepared_session_contract_rejects_source_binding_drift(
    tmp_path: Path, source_kind: str, needle: str
) -> None:
    paths = {
        "rust": DEFAULT_RUST_SOURCE,
        "python": DEFAULT_PYTHON_SOURCE,
        "test": DEFAULT_TEST_SOURCE,
        "documentation": DEFAULT_DOCUMENTATION,
    }
    drifted = tmp_path / paths[source_kind].name
    source = paths[source_kind].read_text(encoding="utf-8")
    assert needle in source
    drifted.write_text(source.replace(needle, "DRIFTED", 1), encoding="utf-8")
    kwargs = {
        "contract_path": DEFAULT_CONTRACT,
        "rust_source_path": DEFAULT_RUST_SOURCE,
        "python_source_path": DEFAULT_PYTHON_SOURCE,
        "test_source_path": DEFAULT_TEST_SOURCE,
        "documentation_path": DEFAULT_DOCUMENTATION,
    }
    argument = {
        "rust": "rust_source_path",
        "python": "python_source_path",
        "test": "test_source_path",
        "documentation": "documentation_path",
    }[source_kind]
    kwargs[argument] = drifted

    with pytest.raises(ContractError, match="missing frozen contract snippets"):
        verify(**kwargs)


def test_prepared_session_contract_rejects_duplicate_json_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
