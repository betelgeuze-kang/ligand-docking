#!/usr/bin/env python3
"""Verify the non-executing Engine V2 clearance activation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0"
EXPECTED_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
GOVERNANCE_BASE_COMMIT = "e782fb2dadd83ce4b9e41fc1af5b970fe63e28ca"
FROZEN_CLEARANCE_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)
EXPECTED_TOP_LEVEL_KEYS = {
    "activation_contract",
    "evidence_requirements",
    "execution_boundary",
    "frozen_dependencies",
    "governance_base_commit",
    "policy_sha256",
    "schema_id",
    "status",
}
EXPECTED_ACTIVATION_CONTRACT = {
    "activation_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_selection_activation_receipt/2.0.0"
    ),
    "candidate_evidence_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_candidate_evidence/2.0.0"
    ),
    "case_source_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_case_source_receipt/1.0.0"
    ),
    "current_v7_lineage_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_current_v7_lineage/1.0.0"
    ),
    "decision_before_scoring_required": True,
    "docking_state_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_activated_state/1.0.0"
    ),
    "internal_validity_evidence_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_internal_validity_evidence/1.0.0"
    ),
    "posebusters_evidence_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_posebusters_evidence/2.0.0"
    ),
    "ranking_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_arm_ranking/2.0.0"
    ),
    "rmsd_evidence_schema_id": (
        "betelgeuze.engine_v2_source_paired_clearance_rmsd_evidence/1.0.0"
    ),
    "snapshot_schema_id": (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_activation_snapshot/1.2.0"
    ),
}
EXPECTED_REQUIRED_INPUTS = (
    "case_source_receipt",
    "case_id",
    "source_case_member_receipt_sha256",
    "authenticated_input_receipt_payload",
    "authenticated_input_receipt_sha256",
    "validity_context_payload",
    "receptor_coordinates",
    "authenticated_receptor_atom_indices",
    "vdw_contact_policy_payload",
    "source_proposal_receipt_payload",
    "source_proposal_receipt_sha256",
    "current_v7_candidate_lineage_receipt",
    "current_v7_candidate_lineage_sha256",
    "source_v11_receipt_payload",
    "source_v11_receipt_sha256",
    "allocation_receipt_payload",
    "allocation_receipt_sha256",
    "candidate_id",
    "candidate_proposal_fingerprint_sha256",
    "current_v7_proposal_state",
    "source_v11_receipt_per_candidate",
    "source_proposal_fingerprint_sha256",
    "source_proposal_slot",
    "source_parent_slot",
    "v6_baseline_coordinates",
    "optimized_coordinates",
    "v6_baseline_torsion_angles",
    "optimized_torsion_angles",
    "source_torsion_metadata_sha256",
    "candidate_torsion_metadata_sha256",
    "v6_baseline_torsion_metadata_sha256",
    "optimized_torsion_metadata_sha256",
    "baseline_raw_minimum_distance",
    "optimized_raw_minimum_distance",
    "baseline_minimum_vdw_surface_gap",
    "optimized_minimum_vdw_surface_gap",
    "baseline_receptor_objective",
    "optimized_receptor_objective",
    "baseline_internal_objective",
    "optimized_internal_objective",
    "baseline_combined_objective",
    "optimized_combined_objective",
    "ligand_atom_count",
    "receptor_atom_count",
    "exact_pair_count",
    "torsion_variant_available",
    "torsion_selected",
    "full_scorer_v1_terms_receipt",
    "full_internal_pose_validity",
    "full_posebusters_check_map",
    "authenticated_rmsd_receipt",
    "raw_score_rank",
    "full_rank_ordering_receipt",
)
EXPECTED_POSEBUSTERS_CHECK_NAMES = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)
EXPECTED_FROZEN_DEPENDENCIES = {
    "allocation_schema_id": (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_allocation/1.0.0"
    ),
    "clearance_selection_policy_sha256": FROZEN_CLEARANCE_POLICY_SHA256,
    "historical_case_ids_sha256": (
        "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
    ),
    "historical_case_source_authority_sha256": (
        "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc"
    ),
    "historical_v11_archive_sha256": (
        "7a2561f646f3cf5434de6c79ed797073ac1b7e034e4fcd2291755a58128f5e98"
    ),
    "historical_v11_bundle_sha256": (
        "37d9478c78076eef908e3a86c712f49820078ab14289fb1ee26a1f8c4fc37ea5"
    ),
    "historical_v11_member_manifest_sha256": (
        "7ae57e3bec8ecf96b754e2038dd2eef023058c4ea1adae2fbf4933bf556cf6bd"
    ),
    "historical_v11_report_sha256": (
        "8d9e9eef5907e51fbf2f25385c7cb1468dbd099c5636715ddea78274ef22fae3"
    ),
    "internal_validity_required_check_set_sha256": (
        "dcab24089ac9c88daa53f3faeabd04d71fb819cbbe9f86982d964b657cbc5583"
    ),
    "posebusters_required_check_set_sha256": (
        "3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93"
    ),
    "posebusters_version": "0.3.1",
    "proposal_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_proposal_receipt/1.0.0"
    ),
    "source_v11_receipt_schema_id": (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
    ),
}
EXPECTED_EVIDENCE_REQUIREMENTS = {
    "activated_state_independent_rederivation_required": True,
    "all_allocated_targets_required": True,
    "authenticated_geometry_independent_clearance_rederivation_required": True,
    "authenticated_torsion_move_replay_required": True,
    "candidate_denominator_per_scored_case": 64,
    "case_source_frozen_archive_member_authority_required": True,
    "changed_slot_set_equals_selected_target_set": True,
    "current_v7_candidate_full_64_slot_lineage_required": True,
    "exact_snapshot_runtime_type_required": True,
    "full_internal_validity_context_and_pose_binding_required": True,
    "full_posebusters_check_map_required": True,
    "full_scorer_v1_terms_payload_required": True,
    "historical_archive_without_full_terms_accepted": False,
    "internal_pose_validity_payload_required": True,
    "posebusters_required_check_names": list(EXPECTED_POSEBUSTERS_CHECK_NAMES),
    "posebusters_required_check_set_sha256": (
        "3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93"
    ),
    "proposal_receipt_full_64_slot_lineage_required": True,
    "rank_order": ["total_score_binary64", "proposal_index"],
    "required_activation_inputs": list(EXPECTED_REQUIRED_INPUTS),
    "retained_target_scientific_projection_equality_required": True,
    "rmsd_reference_atom_mapping_symmetry_binding_required": True,
    "scorer_authority_bound_to_authenticated_input_required": True,
    "scorer_v1_terms_schema_id": "betelgeuze.engine_v2_scorer_v1_terms/1.1.0",
    "top1_top5_rederivable_from_receipts": True,
}
EXPECTED_EXECUTION_BOUNDARY = {
    "activation_evidence_construction_available": True,
    "customer_pose_emission_authorized": False,
    "fresh_holdout_execution_authorized": False,
    "generic_runner_cli_wired": False,
    "historical_ab_execution_authorized": False,
    "historical_result_materialization_authorized": False,
    "product_path_wired": False,
    "public_or_scientific_claim_authorized": False,
    "selection_changes_default_v7": False,
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_mapping(
    value: Mapping[str, Any],
    expected: Mapping[str, object],
    *,
    name: str,
) -> None:
    if set(value) != set(expected):
        raise ValueError(f"{name} keys are invalid")
    for key, expected_value in expected.items():
        observed = value.get(key)
        if type(observed) is not type(expected_value) or observed != expected_value:
            raise ValueError(f"{name}.{key} is invalid")


def verify_policy(policy: Mapping[str, Any]) -> None:
    if set(policy) != EXPECTED_TOP_LEVEL_KEYS:
        raise ValueError("activation policy top-level keys are invalid")
    if policy.get("schema_id") != SCHEMA_ID:
        raise ValueError("activation policy schema_id is invalid")
    if policy.get("status") != "implemented_not_execution_authorized":
        raise ValueError("activation policy status is invalid")
    if policy.get("governance_base_commit") != GOVERNANCE_BASE_COMMIT:
        raise ValueError("activation governance base commit is invalid")
    projection = dict(policy)
    observed_hash = projection.pop("policy_sha256", None)
    if not _is_sha256(observed_hash) or observed_hash != _sha256(projection):
        raise ValueError("activation policy self-hash is invalid")

    contract = _mapping(policy.get("activation_contract"), name="activation_contract")
    _exact_mapping(contract, EXPECTED_ACTIVATION_CONTRACT, name="activation_contract")

    dependencies = _mapping(
        policy.get("frozen_dependencies"), name="frozen_dependencies"
    )
    _exact_mapping(
        dependencies,
        EXPECTED_FROZEN_DEPENDENCIES,
        name="frozen_dependencies",
    )

    execution = _mapping(policy.get("execution_boundary"), name="execution_boundary")
    _exact_mapping(execution, EXPECTED_EXECUTION_BOUNDARY, name="execution_boundary")

    evidence = _mapping(
        policy.get("evidence_requirements"), name="evidence_requirements"
    )
    _exact_mapping(
        evidence,
        EXPECTED_EVIDENCE_REQUIREMENTS,
        name="activation evidence requirements",
    )
    if policy.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise ValueError("activation policy is not the frozen identity")


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"activation policy is not readable canonical JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("activation policy must be an object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/engine_v2_source_paired_clearance_activation.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        policy = _load(arguments.policy)
        verify_policy(policy)
    except ValueError as exc:
        print(f"engine-v2 clearance activation verification failed: {exc}")
        return 1
    print(f"verified {policy['policy_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
