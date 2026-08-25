from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_repository_synthetic_d0_native_source_v1 import (
    ContractError,
    DEFAULT_CONTRACT,
    DEFAULT_CPU_PARITY_CONTRACT,
    DEFAULT_FIXTURE_MANIFEST,
    DEFAULT_NATIVE_WORKFLOW,
    DEFAULT_RELEASE_WORKFLOW,
    DEFAULT_RUST_LIBRARY,
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


def _write_compact_json(path: Path, document: object) -> None:
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


def test_native_repository_d0_source_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["ready_slot_count"] == 54
    assert result["typed_failure_count"] == 10
    assert result["bitwise_current_v7_coordinate_identity_count"] == 28
    assert result["cpp_cpu_parity_bound"] is True
    assert result["cpp_cpu_parity_compared_f64_count"] == 16_896
    assert len(result["cpp_cpu_parity_policy_sha256"]) == 64
    assert result["consumer_activation_authorized"] is False
    assert result["molecular_execution_authorized"] is False
    assert result["reservation_authorized"] is False
    assert result["hip_device_execution_authorized"] is False
    assert result["verification_blockers"] == []
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda document: document["runtime"].update(
                source_contract_sha256="0" * 64
            ),
            "not bound to this source policy",
        ),
        (
            lambda document: document["authority"].update(
                molecular_execution_authorized=True
            ),
            "acquired execution authority",
        ),
        (
            lambda document: document["expected"].update(
                native_source_bundle_receipt_sha256="0" * 64
            ),
            "cross-wired from source",
        ),
    ),
)
def test_native_repository_d0_source_rejects_cpu_parity_cross_wiring(
    tmp_path: Path, mutation, message: str
) -> None:
    document = json.loads(DEFAULT_CPU_PARITY_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "parity.json"
    _write_compact_json(contract, document)

    with pytest.raises(ContractError, match=message):
        verify(cpu_parity_contract_path=contract)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["consumer_binding"].update(
            standalone_activation_authorized=True
        ),
        lambda document: document["fixture"].update(candidate_denominator=63),
        lambda document: document["feature_inventory"].update(ready_slot_count=55),
        lambda document: document["source_generation"].update(
            result_dependent_retry_allowed=True
        ),
        lambda document: document["source_generation"].update(
            uniform_upstream_source_indices=list(range(16))
        ),
        lambda document: document["source_generation"].update(
            legacy_ulp_correction_count=20
        ),
        lambda document: document["receipt_identities"].update(
            allocation_receipt_sha256="0" * 64
        ),
        lambda document: document["scope"].update(
            hip_disposition="device_execution_allowed"
        ),
    ),
)
def test_native_repository_d0_source_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


def test_native_repository_d0_source_rejects_materializer_drift(
    tmp_path: Path,
) -> None:
    drifted = tmp_path / DEFAULT_RUST_SOURCE.name
    raw = DEFAULT_RUST_SOURCE.read_text(encoding="utf-8")
    needle = "Fixed64Allocation::build(inventory)"
    assert needle in raw
    drifted.write_text(raw.replace(needle, "DRIFTED", 1), encoding="utf-8")

    with pytest.raises(ContractError, match="missing frozen contract snippets"):
        verify(rust_source_path=drifted)


def test_native_repository_d0_source_rejects_legacy_identity_manifest_drift(
    tmp_path: Path,
) -> None:
    drifted = tmp_path / DEFAULT_RUST_SOURCE.name
    raw = DEFAULT_RUST_SOURCE.read_text(encoding="utf-8")
    needle = "9b39f3d5b4d6b4d8da17abfc5ce717bc45e271ab18a01dd9113068cb79300d0e"
    assert needle in raw
    drifted.write_text(raw.replace(needle, "0" * 64, 1), encoding="utf-8")

    with pytest.raises(ContractError, match="identity manifest changed"):
        verify(rust_source_path=drifted)


def test_native_repository_d0_source_rejects_caller_input(
    tmp_path: Path,
) -> None:
    drifted = tmp_path / DEFAULT_RUST_SOURCE.name
    raw = DEFAULT_RUST_SOURCE.read_text(encoding="utf-8")
    needle = "pub fn materialize_repository_synthetic_d0_sources(\n)"
    assert needle in raw
    drifted.write_text(
        raw.replace(
            needle,
            "pub fn materialize_repository_synthetic_d0_sources(\n    caller: u64,\n)",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="zero-input"):
        verify(rust_source_path=drifted)


def test_native_repository_d0_source_rejects_export_drift(tmp_path: Path) -> None:
    drifted = tmp_path / DEFAULT_RUST_LIBRARY.name
    raw = DEFAULT_RUST_LIBRARY.read_text(encoding="utf-8")
    needle = "materialize_repository_synthetic_d0_sources"
    assert needle in raw
    drifted.write_text(raw.replace(needle, "DRIFTED", 1), encoding="utf-8")

    with pytest.raises(ContractError, match="Rust library export"):
        verify(rust_library_path=drifted)


def test_native_repository_d0_source_rejects_fixture_manifest_drift(
    tmp_path: Path,
) -> None:
    drifted = tmp_path / DEFAULT_FIXTURE_MANIFEST.name
    drifted.write_bytes(DEFAULT_FIXTURE_MANIFEST.read_bytes() + b"\n")

    with pytest.raises(ContractError, match="manifest identity"):
        verify(fixture_manifest_path=drifted)


@pytest.mark.parametrize(
    ("source", "argument", "label"),
    (
        (DEFAULT_NATIVE_WORKFLOW, "native_workflow_path", "native workflow"),
        (DEFAULT_RELEASE_WORKFLOW, "release_workflow_path", "release workflow"),
    ),
)
def test_native_repository_d0_source_rejects_ci_drift(
    tmp_path: Path,
    source: Path,
    argument: str,
    label: str,
) -> None:
    drifted = tmp_path / source.name
    raw = source.read_text(encoding="utf-8")
    needle = "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
    assert needle in raw
    drifted.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")

    with pytest.raises(ContractError, match=label):
        verify(**{argument: drifted})


def test_native_repository_d0_source_rejects_duplicate_json_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
