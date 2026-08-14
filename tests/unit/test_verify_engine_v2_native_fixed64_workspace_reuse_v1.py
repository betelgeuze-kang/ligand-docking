from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_native_fixed64_workspace_reuse_v1 import (
    ContractError,
    DEFAULT_CONTRACT,
    DEFAULT_INTERNAL_HEADER,
    DEFAULT_NATIVE_TEST,
    DEFAULT_PIPELINE_SOURCE,
    DEFAULT_REFINEMENT_PIPELINE_SOURCE,
    DEFAULT_VENDOR_INTERNAL_HEADER,
    DEFAULT_VENDOR_PIPELINE_SOURCE,
    DEFAULT_VENDOR_REFINEMENT_PIPELINE_SOURCE,
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


def test_workspace_reuse_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["coordinate_buffer_count"] == 26
    assert result["public_abi"] == "1.21"
    assert result["same_shape_second_run_reallocates"] is False
    assert result["scientific_result_cached"] is False
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["abi"].update(public_abi_minor=22),
        lambda document: document["receipt_invariants"].update(
            candidate_denominator=63
        ),
        lambda document: document["receipt_invariants"].update(
            scientific_result_cached=True
        ),
        lambda document: document["workspace"].update(coordinate_buffer_count=25),
        lambda document: document["validation"].update(
            failed_preflight_mutates_workspace=True
        ),
    ),
)
def test_workspace_reuse_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


@pytest.mark.parametrize(
    ("source", "vendor", "needle", "argument"),
    (
        (
            DEFAULT_INTERNAL_HEADER,
            DEFAULT_VENDOR_INTERNAL_HEADER,
            "coordinate_capacity_growth_count",
            "vendor_internal_header_path",
        ),
        (
            DEFAULT_PIPELINE_SOURCE,
            DEFAULT_VENDOR_PIPELINE_SOURCE,
            "prepare_v2_workspace",
            "vendor_pipeline_source_path",
        ),
        (
            DEFAULT_REFINEMENT_PIPELINE_SOURCE,
            DEFAULT_VENDOR_REFINEMENT_PIPELINE_SOURCE,
            "validate_outputs_for_composition",
            "vendor_refinement_pipeline_source_path",
        ),
    ),
)
def test_workspace_reuse_contract_rejects_vendor_drift(
    tmp_path: Path,
    source: Path,
    vendor: Path,
    needle: str,
    argument: str,
) -> None:
    drifted = tmp_path / vendor.name
    raw = vendor.read_text(encoding="utf-8")
    assert needle in raw
    drifted.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")
    kwargs = {argument: drifted}

    with pytest.raises(ContractError, match="canonical and vendored"):
        verify(**kwargs)


def test_workspace_reuse_contract_rejects_native_test_drift(tmp_path: Path) -> None:
    drifted = tmp_path / DEFAULT_NATIVE_TEST.name
    raw = DEFAULT_NATIVE_TEST.read_text(encoding="utf-8")
    needle = "std::numeric_limits<double>::quiet_NaN()"
    assert needle in raw
    drifted.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")

    with pytest.raises(ContractError, match="missing frozen contract snippets"):
        verify(native_test_path=drifted)


def test_workspace_reuse_contract_rejects_duplicate_json_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)
