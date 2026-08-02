"""Entry-point level fail-closed tests for legacy product intake (P0-3).

``tests/unit/test_legacy_input_contract.py`` covers the contract primitives.
This module pins behaviour at the surfaces a customer request actually reaches:
the pose-generation contract preview, the structure-analysis route, the docking
submission passthrough, and the HTVS materializer's ligand-count resolution.
"""

from __future__ import annotations

import asyncio
import types
from typing import Any

import pytest

from api import product_docking
from api.product_docking import StructureAnalysisRequest
from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.docking_request import _pose_generation_contract
from betelgeuze_product.legacy_input_contract import (
    LEGACY_INPUT_CONTRACT_VERSION,
    REASON_INVALID_COORDINATE,
    REASON_INVALID_NUMERIC,
    LegacyInputPolicy,
)
from tools.product.materialize_docking_htvs_request import _estimate_expected_ligand_count

STRICT = LegacyInputPolicy()
COMPAT = LegacyInputPolicy(compatibility_mode=True)

RECEIPT_KEYS = ("legacy_input_contract_version", "fail_closed", "compatibility_mode")

# A compact CA-only grid, dense enough for pocket detection to report a pocket.
PDB_TEXT_CA_GRID = "".join(
    "ATOM  {index:5d}  CA  ALA A{resid:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n".format(
        index=i + 1,
        resid=i + 1,
        x=(i % 4) * 3.8,
        y=(i // 4) * 3.8,
        z=0.0,
    )
    for i in range(12)
)

# The same grid with one unparseable coordinate column appended.
PDB_TEXT_CA_GRID_MALFORMED = PDB_TEXT_CA_GRID + (
    "ATOM     13  CA  ALA A  13        nope   1.000   2.000  1.00  0.00           C\n"
)

PDB_TEXT_INVALID_COORDINATE = (
    "ATOM      1  N   GLY A   1      11.104  13.207  14.321  1.00 10.00           N\n"
    "ATOM      2  CA  GLY A   1       nope    13.207  14.321  1.00 10.00           C\n"
)


def test_pose_generation_contract_reports_pocket_for_well_formed_structure() -> None:
    contract = _pose_generation_contract(
        {"pdb_content": PDB_TEXT_CA_GRID}, {}, legacy_input_policy=STRICT
    )

    assert contract["legacy_input_blocked"] is False
    assert contract["legacy_input_reason_code"] == ""
    assert contract["pocket_detection_available"] is True
    assert contract["execution_enabled"] is False
    assert contract["docking_results_emitted"] is False


def test_pose_generation_contract_fails_closed_on_malformed_coordinate() -> None:
    contract = _pose_generation_contract(
        {"pdb_content": PDB_TEXT_CA_GRID_MALFORMED}, {}, legacy_input_policy=STRICT
    )

    assert contract["legacy_input_blocked"] is True
    assert contract["legacy_input_reason_code"] == REASON_INVALID_COORDINATE
    assert contract["legacy_input_reason"]
    # A refused parse must not read as "no pocket in an otherwise fine structure".
    assert contract["pocket_detection_available"] is False
    assert contract["pocket_method"] == ""


def test_pose_generation_contract_compatibility_mode_restores_lenient_parse() -> None:
    contract = _pose_generation_contract(
        {"pdb_content": PDB_TEXT_CA_GRID_MALFORMED}, {}, legacy_input_policy=COMPAT
    )

    assert contract["legacy_input_blocked"] is False
    assert contract["pocket_detection_available"] is True
    assert contract["compatibility_mode"] is True
    assert contract["fail_closed"] is False


@pytest.mark.parametrize("policy", [STRICT, COMPAT])
def test_pose_generation_contract_always_carries_policy_receipt(
    policy: LegacyInputPolicy,
) -> None:
    contract = _pose_generation_contract(
        {"pdb_content": PDB_TEXT_CA_GRID}, {}, legacy_input_policy=policy
    )

    for key in RECEIPT_KEYS:
        assert key in contract
    assert contract["legacy_input_contract_version"] == LEGACY_INPUT_CONTRACT_VERSION
    assert contract["fail_closed"] is policy.fail_closed
    assert contract["compatibility_mode"] is policy.compatibility_mode


def test_analyze_product_structure_blocks_malformed_coordinate_by_default() -> None:
    payload = StructureAnalysisRequest(pdb_content=PDB_TEXT_INVALID_COORDINATE)

    response = asyncio.run(product_docking.analyze_product_structure(payload))

    assert response["status"] == "blocked_structure_analysis"
    assert [blocker["code"] for blocker in response["blockers"]] == [REASON_INVALID_COORDINATE]
    assert response["fail_closed"] is True
    assert response["compatibility_mode"] is False
    assert response["atom_count"] == 0
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False


def test_analyze_product_structure_compatibility_mode_accepts_partial_parse() -> None:
    payload = StructureAnalysisRequest(
        pdb_content=PDB_TEXT_INVALID_COORDINATE, legacy_input_compatibility_mode=True
    )

    response = asyncio.run(product_docking.analyze_product_structure(payload))

    assert response["status"] == "structure_analysis_ready"
    assert response["compatibility_mode"] is True
    assert response["fail_closed"] is False
    # The malformed row is skipped, which is the pre-contract behaviour.
    assert response["atom_count"] == 1


def _stub_docking_submission(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Neutralize submission side effects and capture record-builder kwargs."""

    captured: dict[str, Any] = {}

    def fake_build_docking_job_record(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {
            "job_id": "job-test",
            "request_sha256": "sha-test",
            "status": "accepted_fail_closed",
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "",
            "customer_id": "",
            "user_id": "",
            "validation_status": "pass",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "claim_boundary": {},
        }

    monkeypatch.setattr(product_docking, "build_docking_job_record", fake_build_docking_job_record)
    monkeypatch.setattr(product_docking, "persist_docking_job_record", lambda *a, **k: None)
    monkeypatch.setattr(product_docking, "store_docking_request", lambda *a, **k: None)
    monkeypatch.setattr(product_docking, "configured_store", lambda *a, **k: None)
    monkeypatch.setattr(product_docking, "get_configured_job_store", lambda *a, **k: None)
    monkeypatch.setattr(product_docking, "dispatch_docking_job_if_eligible", lambda *a, **k: {})
    for name in (
        "docking_validation_summary",
        "docking_structure_summary",
        "docking_progress_summary",
        "docking_dispatch_summary",
        "docking_claim_summary",
        "docking_links",
    ):
        monkeypatch.setattr(product_docking, name, lambda *a, **k: {})
    return captured


@pytest.mark.parametrize("requested_mode", [True, None])
def test_submit_docking_job_passes_legacy_input_mode_through(
    monkeypatch: pytest.MonkeyPatch, requested_mode: bool | None
) -> None:
    captured = _stub_docking_submission(monkeypatch)
    payload = product_docking.DockingJobRequest(
        family="gpcr", legacy_input_compatibility_mode=requested_mode
    )
    request = types.SimpleNamespace(client=None)

    response = asyncio.run(product_docking.submit_docking_job(payload, request))

    assert captured["kwargs"]["legacy_input_compatibility_mode"] is requested_mode
    assert response["job_id"] == "job-test"
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False


def test_estimate_expected_ligand_count_prefers_declared_sources_in_order() -> None:
    assert (
        _estimate_expected_ligand_count(
            params={"ligand_count": 5},
            ledger={"ligand_count": 7},
            candidate_count=2,
            legacy_input_policy=STRICT,
        )
        == 5
    )
    assert (
        _estimate_expected_ligand_count(
            params={},
            ledger={"ligand_count": 7},
            candidate_count=2,
            legacy_input_policy=STRICT,
        )
        == 7
    )
    assert (
        _estimate_expected_ligand_count(
            params={},
            ledger={"intake_payload": {"ligand_count": 9}},
            candidate_count=2,
            legacy_input_policy=STRICT,
        )
        == 9
    )


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_estimate_expected_ligand_count_falls_back_when_undeclared(blank: Any) -> None:
    assert (
        _estimate_expected_ligand_count(
            params={"ligand_count": blank},
            ledger={},
            candidate_count=2,
            legacy_input_policy=STRICT,
        )
        == 2
    )


@pytest.mark.parametrize(
    ("params", "ledger"),
    [
        ({"ligand_count": "abc"}, {}),
        ({}, {"ligand_count": "abc"}),
        ({}, {"intake_payload": {"ligand_count": "abc"}}),
    ],
)
def test_estimate_expected_ligand_count_fails_closed_on_invalid_declaration(
    params: dict[str, Any], ledger: dict[str, Any]
) -> None:
    with pytest.raises(DockingMaterializationError) as excinfo:
        _estimate_expected_ligand_count(
            params=params,
            ledger=ledger,
            candidate_count=2,
            legacy_input_policy=STRICT,
        )

    assert excinfo.value.reason_code == REASON_INVALID_NUMERIC


def test_estimate_expected_ligand_count_compatibility_mode_skips_invalid_value() -> None:
    assert (
        _estimate_expected_ligand_count(
            params={"ligand_count": "abc"},
            ledger={},
            candidate_count=2,
            legacy_input_policy=COMPAT,
        )
        == 2
    )
