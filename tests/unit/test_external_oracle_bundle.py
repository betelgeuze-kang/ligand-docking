"""Offline Vina/GNINA/Smina oracle recorded as a common bundle (P1-9)."""

from __future__ import annotations

import pytest

from betelgeuze_product.docking_result_bundle import (
    REQUIRED_BUNDLE_SECTIONS,
    validate_bundle_payload,
)
from betelgeuze_product.engine_adapters import (
    LEGACY_BUDGET,
    run_engine_v2_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.external_oracle_bundle import (
    EXTERNAL_ORACLE_BUNDLE_SCHEMA_VERSION,
    ORACLE_SCORE_TERM_ID,
    build_external_oracle_run,
    record_external_oracle_bundle,
)
from betelgeuze_product.preparation_packet import ENGINE_SURFACE_EXTERNAL_ORACLE
from betelgeuze_product.preparation_service import build_preparation_packet
from betelgeuze_product.shadow_execution import build_shadow_execution_record

pytest.importorskip("rdkit")


def _receptor_pdb(atom_count: int = 40) -> str:
    return "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (index, index, float(index % 9), float(index % 5), float(index % 3))
        for index in range(1, atom_count + 1)
    )


def _receipt(**overrides):
    row = {
        "baseline_engine": "vina",
        "engine_version": "1.2.5",
        "score_artifact_path": "runs/oracle/vina_case1.log",
        "score_artifact_sha256": "a" * 64,
        "prep_policy_sha256": "b" * 64,
        "operator_id": "operator_1",
        "reviewed_at_utc": "2026-07-27T00:00:00Z",
        "license_ok": True,
        "method": "vina --score_only on the prepared packet",
    }
    row.update(overrides)
    return row


def _poses(count: int = 3):
    return [
        {
            "pose_id": f"oracle_pose_{index}",
            "rank": index,
            "score": -8.0 + index,
            "geometric_valid": True,
            "chemistry_valid": True,
        }
        for index in range(1, count + 1)
    ]


@pytest.fixture(scope="module")
def packet():
    return build_preparation_packet(
        receptor_payload={"pdb_content": _receptor_pdb(), "target_id": "T1"},
        ligand_smiles="CCCCCCO",
        target_id="T1",
        ligand_id="L1",
        max_conformers=6,
        seed=7,
    )


@pytest.fixture(scope="module")
def macrocycle_packet():
    return build_preparation_packet(
        receptor_payload={"pdb_content": _receptor_pdb(), "target_id": "T1"},
        ligand_smiles="C1CCCCCCCCCCCC1",
        ligand_id="macro",
    )


def _bundle(packet, *, receipt=None, poses=None, budget: int | None = None):
    run = build_external_oracle_run(
        receipt=receipt if receipt is not None else _receipt(),
        poses=_poses() if poses is None else poses,
    )
    return record_external_oracle_bundle(
        packet,
        run,
        candidate_budget=LEGACY_BUDGET.candidate_budget if budget is None else budget,
    )


def test_oracle_bundle_satisfies_the_common_result_schema(packet) -> None:
    payload = _bundle(packet).to_dict()

    assert payload["status"] == "docking_result_bundle_ready"
    assert payload["engine_surface"] == ENGINE_SURFACE_EXTERNAL_ORACLE
    assert payload["engine_version"] == "vina:1.2.5"
    assert validate_bundle_payload(payload) == []
    for section in REQUIRED_BUNDLE_SECTIONS:
        assert section in payload


def test_oracle_bundle_binds_to_the_canonical_prepared_input(packet) -> None:
    bundle = _bundle(packet)

    assert bundle.prepared_input_hash == packet.prepared_input_hash
    assert bundle.receptor_input_hash == packet.receptor.input_hash
    assert bundle.ligand_input_hash == packet.ligand.input_hash
    assert bundle.pocket_identity == packet.receptor.pocket.as_dict()


def test_oracle_score_is_kept_out_of_internal_score_terms(packet) -> None:
    payload = _bundle(packet).to_dict()

    for terms in payload["per_term_score"].values():
        assert list(terms) == [ORACLE_SCORE_TERM_ID]


def test_oracle_records_that_it_did_not_execute_in_process(packet) -> None:
    receipts = _bundle(packet).evidence_receipts

    assert receipts["bundle_schema_version"] == EXTERNAL_ORACLE_BUNDLE_SCHEMA_VERSION
    assert receipts["executed_in_process"] is False
    assert receipts["execution_locus"] == "offline_operator_host"
    assert receipts["claim_promotion_allowed"] is False
    assert receipts["oracle_receipt"]["operator_id"] == "operator_1"


def test_oracle_poses_are_reranked_contiguously(packet) -> None:
    poses = _bundle(packet, poses=list(reversed(_poses(3)))).poses

    assert [pose.rank for pose in poses] == [1, 2, 3]
    assert [pose.pose_id for pose in poses] == [
        "oracle_pose_1",
        "oracle_pose_2",
        "oracle_pose_3",
    ]


def test_unconfirmed_license_blocks_the_oracle_record(packet) -> None:
    bundle = _bundle(packet, receipt=_receipt(license_ok=False))

    assert "baseline_license_not_confirmed" in bundle.blockers
    assert bundle.poses == ()
    assert bundle.failure_denominator.failed_case_count == 1
    assert validate_bundle_payload(bundle.to_dict()) == []


def test_missing_provenance_blocks_the_oracle_record(packet) -> None:
    bundle = _bundle(packet, receipt=_receipt(score_artifact_sha256="", operator_id=""))

    assert "oracle_receipt_field_missing:score_artifact_sha256" in bundle.blockers
    assert "oracle_receipt_field_missing:operator_id" in bundle.blockers


def test_unsupported_baseline_engine_is_rejected(packet) -> None:
    bundle = _bundle(packet, receipt=_receipt(baseline_engine="some_other_docker"))

    assert "unsupported_baseline_engine:some_other_docker" in bundle.blockers


def test_pending_score_value_blocks_instead_of_reading_as_zero(packet) -> None:
    rows = _poses(1)
    rows[0]["score"] = ""
    bundle = _bundle(packet, poses=rows)

    assert "oracle_pose_score_pending:oracle_pose_1" in bundle.blockers
    assert bundle.poses == ()


def test_no_reported_pose_blocks_the_oracle_record(packet) -> None:
    bundle = _bundle(packet, poses=[])

    assert "oracle_reported_no_pose" in bundle.blockers


def test_unrecorded_candidate_budget_blocks_the_oracle_record(packet) -> None:
    bundle = _bundle(packet, budget=0)

    assert "oracle_candidate_budget_not_recorded" in bundle.blockers


def test_blocked_packet_yields_a_counted_oracle_failure(macrocycle_packet) -> None:
    bundle = _bundle(macrocycle_packet)

    assert macrocycle_packet.ready is False
    assert "prepared_input_not_ready" in bundle.blockers
    assert bundle.failure_denominator.accounted is True
    assert bundle.evidence_receipts["prepared_packet_blockers"]


def test_three_surfaces_form_a_comparable_shadow_record(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            _bundle(packet),
        ],
    )
    payload = record.to_dict()

    assert payload["status"] == "shadow_execution_ready"
    assert payload["violations"] == []
    assert payload["comparison"]["comparable"] is True
    # legacy-vs-V2, legacy-vs-oracle, V2-vs-oracle
    assert len(payload["pairwise_deltas"]) == 3
    assert ENGINE_SURFACE_EXTERNAL_ORACLE in payload["shadow_result_surfaces"]
    assert payload["claim_promotion_allowed"] is False


def test_oracle_cannot_be_served_as_the_active_result(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            _bundle(packet),
        ],
        served_engine_surface=ENGINE_SURFACE_EXTERNAL_ORACLE,
    )

    assert record.ready is False
    assert (
        f"shadow_surface_cannot_be_served:{ENGINE_SURFACE_EXTERNAL_ORACLE}"
        in record.violations
    )


def test_mismatched_oracle_budget_blocks_the_paired_comparison(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            _bundle(packet, budget=9),
        ],
    )

    assert "mismatched_candidate_budget" in record.violations
