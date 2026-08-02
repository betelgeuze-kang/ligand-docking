"""Engine adapter tests: canonical packet -> legacy/V2 -> common bundle (§17)."""

from __future__ import annotations

import pytest

from betelgeuze_engine.scoring.local_refinement import RefinementParameters
from betelgeuze_product.docking_result_bundle import (
    REQUIRED_BUNDLE_SECTIONS,
    validate_bundle_payload,
)
from betelgeuze_product.engine_adapters import (
    ENGINE_ADAPTER_SCHEMA_VERSION,
    ENGINE_V2_ADAPTER_VERSION,
    LEGACY_ADAPTER_VERSION,
    AdapterBudget,
    run_engine_adapter,
    run_engine_v2_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
)
from betelgeuze_product.preparation_service import build_preparation_packet
from betelgeuze_product.shadow_execution import build_shadow_execution_record

pytest.importorskip("rdkit")


def _receptor_pdb(atom_count: int = 40) -> str:
    return "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (index, index, float(index % 9), float(index % 5), float(index % 3))
        for index in range(1, atom_count + 1)
    )


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


def test_prepared_packet_is_ready(packet) -> None:
    assert packet.ready is True
    assert packet.blockers == ()


def test_legacy_adapter_emits_a_complete_bundle(packet) -> None:
    payload = run_legacy_adapter(packet).to_dict()

    assert payload["status"] == "docking_result_bundle_ready"
    assert payload["engine_surface"] == ENGINE_SURFACE_LEGACY_PRODUCT
    assert payload["engine_version"] == LEGACY_ADAPTER_VERSION
    assert validate_bundle_payload(payload) == []
    for section in REQUIRED_BUNDLE_SECTIONS:
        assert section in payload


def test_v2_adapter_emits_a_complete_bundle(packet) -> None:
    payload = run_engine_v2_adapter(packet).to_dict()

    assert payload["engine_surface"] == ENGINE_SURFACE_ENGINE_V2
    assert payload["engine_version"] == ENGINE_V2_ADAPTER_VERSION
    assert validate_bundle_payload(payload) == []


def test_both_surfaces_consume_the_identical_prepared_input(packet) -> None:
    legacy = run_legacy_adapter(packet)
    v2 = run_engine_v2_adapter(packet)

    assert legacy.prepared_input_hash == v2.prepared_input_hash == packet.prepared_input_hash
    assert legacy.receptor_input_hash == v2.receptor_input_hash
    assert legacy.ligand_input_hash == v2.ligand_input_hash
    assert legacy.pocket_identity == v2.pocket_identity


def test_both_surfaces_use_the_same_conformer_ensemble(packet) -> None:
    legacy = run_legacy_adapter(packet).evidence_receipts["conformer_ids"]
    v2 = run_engine_v2_adapter(packet).evidence_receipts["conformer_ids"]

    assert legacy == v2 == list(packet.ligand.conformer_ids)


def test_legacy_reports_no_refinement_and_v2_reports_refinement(packet) -> None:
    legacy = run_legacy_adapter(packet).evidence_receipts
    v2 = run_engine_v2_adapter(packet).evidence_receipts

    assert legacy["refinement_run_count"] == 0
    assert v2["refinement_run_count"] >= 1
    assert v2["refinement_converged_count"] <= v2["refinement_run_count"]


def test_refinement_improves_or_matches_the_legacy_score(packet) -> None:
    legacy_top = run_legacy_adapter(packet).top_pose
    v2_top = run_engine_v2_adapter(packet).top_pose

    assert legacy_top is not None and v2_top is not None
    # Bounded refinement minimizes the same energy, so V2 must not be worse.
    assert v2_top.total_score <= legacy_top.total_score + 1e-9


def test_every_pose_carries_per_term_scores(packet) -> None:
    payload = run_legacy_adapter(packet).to_dict()

    assert payload["pose_ensemble"]["pose_count"] >= 1
    for pose in payload["pose_ensemble"]["poses"]:
        terms = payload["per_term_score"][pose["pose_id"]]
        assert terms
        assert abs(sum(terms.values()) - pose["total_score"]) < 1e-6


def test_reported_poses_are_distinct_binding_modes(packet) -> None:
    payload = run_legacy_adapter(packet).to_dict()
    poses = payload["pose_ensemble"]["poses"]

    cluster_ids = [pose["cluster_id"] for pose in poses]
    assert len(set(cluster_ids)) == len(cluster_ids)
    assert payload["evidence_receipts"]["clustering"]["order_independent"] is True


def test_pose_ranks_are_contiguous_and_score_ordered(packet) -> None:
    poses = run_legacy_adapter(packet).poses

    assert [pose.rank for pose in poses] == list(range(1, len(poses) + 1))
    scores = [pose.total_score for pose in poses]
    assert scores == sorted(scores)


def test_failure_denominator_accounts_for_the_single_case(packet) -> None:
    denominator = run_legacy_adapter(packet).failure_denominator

    assert denominator.attempted_case_count == 1
    assert denominator.scored_case_count == 1
    assert denominator.failed_case_count == 0
    assert denominator.accounted is True


def test_candidate_budget_is_recorded_per_surface(packet) -> None:
    budget = AdapterBudget(candidate_budget=3, max_reported_poses=2)
    bundle = run_legacy_adapter(packet, budget=budget)

    assert bundle.candidate_budget == 3
    assert bundle.evidence_receipts["budget"]["candidate_budget"] == 3
    assert len(bundle.poses) <= 2


def test_refinement_parameter_identity_is_recorded(packet) -> None:
    params = RefinementParameters(max_steps=4, max_displacement_a=0.4)
    budget = AdapterBudget(candidate_budget=4, refinement=params)
    receipts = run_engine_v2_adapter(packet, budget=budget).evidence_receipts

    assert receipts["budget"]["refinement_enabled"] is True
    assert receipts["budget"]["refinement_parameter_digest"] == params.parameter_digest


def test_adapter_runs_are_deterministic(packet) -> None:
    first = run_engine_v2_adapter(packet)
    second = run_engine_v2_adapter(packet)

    assert first.bundle_hash == second.bundle_hash


def test_blocked_packet_yields_a_counted_failure(macrocycle_packet) -> None:
    bundle = run_legacy_adapter(macrocycle_packet)
    payload = bundle.to_dict()

    assert macrocycle_packet.ready is False
    assert payload["status"] == "blocked_docking_result_bundle"
    assert bundle.poses == ()
    assert bundle.failure_denominator.failed_case_count == 1
    assert bundle.failure_denominator.accounted is True
    assert "prepared_input_not_ready" in bundle.blockers
    # A blocked bundle still names the prepared-packet blockers it inherited.
    assert payload["evidence_receipts"]["prepared_packet_blockers"]


def test_blocked_bundle_still_satisfies_the_result_schema(macrocycle_packet) -> None:
    payload = run_engine_v2_adapter(macrocycle_packet).to_dict()

    assert validate_bundle_payload(payload) == []


def test_unknown_engine_surface_is_rejected(packet) -> None:
    with pytest.raises(ValueError) as excinfo:
        run_engine_adapter(packet, engine_surface="some_other_engine")

    assert "unsupported_engine_surface" in str(excinfo.value)


def test_external_oracle_cannot_be_run_locally(packet) -> None:
    with pytest.raises(ValueError) as excinfo:
        run_engine_adapter(packet, engine_surface=ENGINE_SURFACE_EXTERNAL_ORACLE)

    assert "engine_surface_not_runnable_locally" in str(excinfo.value)


def test_adapters_feed_a_ready_shadow_execution_record(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[run_legacy_adapter(packet), run_engine_v2_adapter(packet)],
    )
    payload = record.to_dict()

    assert payload["status"] == "shadow_execution_ready"
    assert payload["violations"] == []
    assert payload["comparison"]["comparable"] is True
    assert len(payload["pairwise_deltas"]) == 1
    assert payload["claim_promotion_allowed"] is False


def test_shadow_delta_is_attributable_to_refinement(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[run_legacy_adapter(packet), run_engine_v2_adapter(packet)],
    )
    delta = record.to_dict()["pairwise_deltas"][0]

    # Same prepared input and same candidate budget, so the delta isolates the
    # only sanctioned difference: bounded refinement.
    legacy = record.by_surface[ENGINE_SURFACE_LEGACY_PRODUCT]
    v2 = record.by_surface[ENGINE_SURFACE_ENGINE_V2]
    assert legacy.candidate_budget == v2.candidate_budget
    assert delta["top_score_delta"] <= 1e-9


def test_mismatched_budget_blocks_the_shadow_comparison(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet, budget=AdapterBudget(candidate_budget=4)),
            run_engine_v2_adapter(packet, budget=AdapterBudget(candidate_budget=9)),
        ],
    )

    assert "mismatched_candidate_budget" in record.violations


def test_receipts_expose_adapter_schema_and_flexibility_lane(packet) -> None:
    receipts = run_legacy_adapter(packet).evidence_receipts

    assert receipts["adapter_schema_version"] == ENGINE_ADAPTER_SCHEMA_VERSION
    assert receipts["ligand_flexibility_lane"] == "rigid_component_plus_rotor"
    assert "do not prepare inputs" in receipts["claim_boundary"]


def test_benchmark_profile_and_claim_scope_are_carried_through(packet) -> None:
    bundle = run_legacy_adapter(
        packet, benchmark_profile="frozen_profile_v1", claim_scope="restricted_internal"
    )

    assert bundle.benchmark_profile == "frozen_profile_v1"
    assert bundle.claim_scope == "restricted_internal"


def test_geometric_and_chemistry_validity_are_reported(packet) -> None:
    payload = run_legacy_adapter(packet).to_dict()

    geometric = payload["geometric_validity"]
    chemistry = payload["chemistry_validity"]
    assert geometric["valid_pose_count"] + geometric["invalid_pose_count"] == len(
        payload["pose_ensemble"]["poses"]
    )
    assert chemistry["valid_pose_count"] + chemistry["invalid_pose_count"] == len(
        payload["pose_ensemble"]["poses"]
    )
