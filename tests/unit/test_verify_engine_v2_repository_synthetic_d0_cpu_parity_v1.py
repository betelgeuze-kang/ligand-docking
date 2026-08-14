from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_repository_synthetic_d0_cpu_parity_v1 import (
    ContractError,
    DEFAULT_CLI_SOURCE,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_NATIVE_WORKFLOW,
    DEFAULT_PYTHON_SOURCE,
    DEFAULT_RELEASE_WORKFLOW,
    DEFAULT_RUNTIME_EXPORT,
    DEFAULT_RUNTIME_SOURCE,
    DEFAULT_RUST_SOURCE,
    DEFAULT_SESSION_CONTRACT,
    DEFAULT_SOURCE_CONTRACT,
    DEFAULT_TEST_SOURCE,
    verify,
)


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


def test_repository_synthetic_d0_cpu_parity_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["compared_f64_count"] == 16_896
    assert result["absolute_tolerance"] == 1e-11
    assert result["relative_tolerance"] == 4e-12
    assert result["performance_measurement_allowed"] is False
    assert result["qualification_rerun_authorized"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(molecular_execution_authorized=True),
        lambda document: document["authority"].update(qualification_rerun_authorized=True),
        lambda document: document["comparison"].update(absolute_tolerance=1e-8),
        lambda document: document["comparison"].update(all_scorer_v1_terms_compared=False),
        lambda document: document["comparison"].update(exact_source_and_allocation_identity_parity_required=False),
        lambda document: document["expected"].update(candidate_denominator=63),
        lambda document: document["expected"].update(compared_f64_count=16_895),
        lambda document: document["expected"].update(scientific_decision_sha256="0" * 64),
        lambda document: document["expected"].update(top_k_slot_indices=[9, 23, 10, 29, 16]),
        lambda document: document["restrictions"].update(performance_measurement_allowed=True),
        lambda document: document["runtime"].update(
            entrypoint="native_fixed64_prepare_repository_synthetic_d0_session_v1"
        ),
        lambda document: document["runtime"].update(no_caller_science_input=False),
    ),
)
def test_repository_synthetic_d0_cpu_parity_rejects_policy_drift(tmp_path: Path, mutation) -> None:
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
            "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
        ),
        (
            DEFAULT_RUNTIME_SOURCE,
            "runtime_source_path",
            "pub fn compare_fixed64_scientific_numeric_parity(",
        ),
        (
            DEFAULT_RUNTIME_EXPORT,
            "runtime_export_path",
            "compare_fixed64_scientific_numeric_parity",
        ),
        (
            DEFAULT_PYTHON_SOURCE,
            "python_source_path",
            "def _rederive_receipt_sha256(",
        ),
        (
            DEFAULT_CLI_SOURCE,
            "cli_source_path",
            '"--repository-native-d0-cpu-parity"',
        ),
        (
            DEFAULT_TEST_SOURCE,
            "test_source_path",
            "test_repository_d0_cpu_parity_is_native_complete_and_non_authoritative",
        ),
        (
            DEFAULT_DOCUMENTATION,
            "documentation_path",
            "all 16,896 binary64 values",
        ),
        (
            DEFAULT_RELEASE_WORKFLOW,
            "release_workflow_path",
            "tools/verify_engine_v2_repository_synthetic_d0_cpu_parity_v1.py",
        ),
        (
            DEFAULT_NATIVE_WORKFLOW,
            "native_workflow_path",
            "tools/verify_engine_v2_repository_synthetic_d0_cpu_parity_v1.py",
        ),
    ),
)
def test_repository_synthetic_d0_cpu_parity_rejects_source_binding_drift(
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


@pytest.mark.parametrize(
    ("source", "argument", "message"),
    (
        (
            DEFAULT_SOURCE_CONTRACT,
            "source_contract_path",
            "cross-wired to its source contract",
        ),
        (
            DEFAULT_SESSION_CONTRACT,
            "session_contract_path",
            "cross-wired to its source session contract",
        ),
    ),
)
def test_repository_synthetic_d0_cpu_parity_rejects_contract_cross_wiring(
    tmp_path: Path,
    source: Path,
    argument: str,
    message: str,
) -> None:
    document = json.loads(source.read_text(encoding="ascii"))
    document["schema_id"] = "drifted"
    drifted = tmp_path / source.name
    _write_json(drifted, document)

    with pytest.raises(ContractError, match=message):
        verify(**{argument: drifted})


def test_repository_synthetic_d0_cpu_parity_rejects_duplicate_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n',
        encoding="ascii",
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
