from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_repository_synthetic_d0_native_session_v1 import (
    ContractError,
    DEFAULT_CLI_SOURCE,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_NATIVE_WORKFLOW,
    DEFAULT_PYTHON_SOURCE,
    DEFAULT_RELEASE_WORKFLOW,
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


def test_repository_d0_native_session_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["complete_scorer_v1_weighted_term_count"] == 8
    assert result["cpp_rust_decision_parity_required"] is True
    assert result["contact_policy_sha256"] == (
        "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
    )
    assert result["scientific_decision_sha256"] == (
        "8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"
    )
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["api"].update(
            native_entrypoint="native_fixed64_prepare_session_v1"
        ),
        lambda document: document["fixed_input"].update(candidate_denominator=63),
        lambda document: document["fixed_input"].update(ready_slot_count=55),
        lambda document: document["frozen_decision"].update(
            scientific_decision_sha256="0" * 64
        ),
        lambda document: document["frozen_decision"].update(
            top_k_slot_indices=[9, 23, 10, 29, 16]
        ),
        lambda document: document["runtime_evidence"].update(
            qualification_runner_called=True
        ),
        lambda document: document["runtime_evidence"].update(
            complete_scorer_v1_weighted_term_count=7
        ),
        lambda document: document["build_binding_policy"].update(
            required_attested_wrapper_control="direct_cargo_unattested"
        ),
        lambda document: document["scientific_context_receipts"].update(
            contact_policy_sha256="0" * 64
        ),
        lambda document: document["policy_receipts"]["refinement_policy"].update(
            rigid_max_steps=21
        ),
        lambda document: document["policy_receipts"]["post_admission_policy"].update(
            post_rejection_deleted=True
        ),
    ),
)
def test_repository_d0_native_session_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


@pytest.mark.parametrize(
    ("source", "argument", "needle"),
    (
        (
            DEFAULT_RUST_SOURCE,
            "rust_source_path",
            "repository_d0_scoring_features(",
        ),
        (
            DEFAULT_PYTHON_SOURCE,
            "python_source_path",
            "def _repository_d0_backend_binding_digest(",
        ),
        (
            DEFAULT_CLI_SOURCE,
            "cli_source_path",
            '"--repository-native-d0-backend"',
        ),
        (
            DEFAULT_TEST_SOURCE,
            "test_source_path",
            "test_repository_d0_native_session_uses_one_source_bound_core_across_surfaces",
        ),
        (
            DEFAULT_DOCUMENTATION,
            "documentation_path",
            "External authority must reach blocker zero",
        ),
        (
            DEFAULT_RELEASE_WORKFLOW,
            "release_workflow_path",
            "config/engine_v2_repository_synthetic_d0_native_session_v1.json",
        ),
        (
            DEFAULT_NATIVE_WORKFLOW,
            "native_workflow_path",
            "config/engine_v2_repository_synthetic_d0_native_session_v1.json",
        ),
    ),
)
def test_repository_d0_native_session_contract_rejects_source_binding_drift(
    tmp_path: Path,
    source: Path,
    argument: str,
    needle: str,
) -> None:
    raw = source.read_text(encoding="utf-8")
    assert needle in raw
    drifted = tmp_path / source.name
    drifted.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")

    with pytest.raises(ContractError, match="missing frozen snippets"):
        verify(**{argument: drifted})


def test_repository_d0_native_session_rejects_source_contract_cross_wiring(
    tmp_path: Path,
) -> None:
    from tools.verify_engine_v2_repository_synthetic_d0_native_session_v1 import (
        DEFAULT_SOURCE_CONTRACT,
    )

    document = json.loads(DEFAULT_SOURCE_CONTRACT.read_text(encoding="ascii"))
    document["receipt_identities"]["allocation_receipt_sha256"] = "0" * 64
    source_contract = tmp_path / "source-contract.json"
    _write_json(source_contract, document)

    with pytest.raises(ContractError, match="cross-wired to its source contract"):
        verify(source_contract_path=source_contract)


def test_repository_d0_native_session_rejects_duplicate_json_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
