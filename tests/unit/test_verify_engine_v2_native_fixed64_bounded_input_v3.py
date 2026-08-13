from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_native_fixed64_bounded_input_v3 import (
    ContractError,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_PYTHON_CONSUMER,
    DEFAULT_RUST_SOURCE,
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


def test_bounded_input_v3_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["canonical_entrypoint"] == "native_fixed64_complete_pipeline_v3"
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["limits"].update(ligand_atom_count=513),
        lambda document: document["receipt_domains"].update(
            consumer_identity_in_prepared_projection=True
        ),
        lambda document: document.update(
            canonical_entrypoint="native_fixed64_complete_pipeline_v2"
        ),
    ),
)
def test_bounded_input_v3_contract_rejects_policy_drift(
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
        ("rust", "bounded_prepared_input_preflight(input)"),
        ("python", 'name = "native_fixed64_complete_pipeline_v3"'),
        ("documentation", "External authority must reach blocker zero"),
    ),
)
def test_bounded_input_v3_contract_rejects_source_binding_drift(
    tmp_path: Path, source_kind: str, needle: str
) -> None:
    paths = {
        "rust": DEFAULT_RUST_SOURCE,
        "python": DEFAULT_PYTHON_CONSUMER,
        "documentation": DEFAULT_DOCUMENTATION,
    }
    drifted = tmp_path / paths[source_kind].name
    source = paths[source_kind].read_text(encoding="utf-8")
    assert needle in source
    drifted.write_text(source.replace(needle, "DRIFTED", 1), encoding="utf-8")
    kwargs = {
        "contract_path": DEFAULT_CONTRACT,
        "rust_source_path": DEFAULT_RUST_SOURCE,
        "python_consumer_path": DEFAULT_PYTHON_CONSUMER,
        "documentation_path": DEFAULT_DOCUMENTATION,
    }
    argument = {
        "rust": "rust_source_path",
        "python": "python_consumer_path",
        "documentation": "documentation_path",
    }[source_kind]
    kwargs[argument] = drifted

    with pytest.raises(ContractError, match="missing frozen contract snippets"):
        verify(**kwargs)


def test_bounded_input_v3_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
