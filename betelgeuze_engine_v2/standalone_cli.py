"""Claim-blocked standalone CPU CLI over :class:`DockingPipeline`.

Every molecular input is an already-prepared canonical Engine v2 document.
These commands perform no chemistry inference, network access, external
reservation, benchmark execution, or product action.
"""

from __future__ import annotations

import argparse
from importlib import resources
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Sequence

import torch

from .cli import (
    CLI_POCKET_INPUT_SCHEMA_ID,
    MAX_CLI_INPUT_BYTES,
    MAX_CLI_POCKET_BYTES,
    EngineV2CliError,
    _canonical_bytes,
    _failure_document,
    _load_canonical_pocket_document,
    _pocket_from_document,
    _read_bounded,
    _reject_duplicate_pairs,
    _sha256_bytes,
    _sha256_document,
    _write_private_bundle,
    _write_output_hardened as _write_output,
)
from .docking import DockingScope, PocketDefinition
from .docking.pipeline import (
    EXTERNAL_AUTHORITY_BLOCKERS,
    PIPELINE_CANDIDATE_SCHEMA_ID,
    PIPELINE_CLAIM_BLOCKERS,
    PIPELINE_PROFILE_SCHEMA_ID,
    PIPELINE_PROPOSAL_PLAN_SCHEMA_ID,
    PIPELINE_REQUEST_SCHEMA_ID,
    PIPELINE_RESULT_SCHEMA_ID,
    SEALED_CANONICAL_COMPONENT_BINDING,
    SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID,
    SYNTHETIC_D0_FIXTURE_ID,
    SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
    SYNTHETIC_D0_FIXTURE_REQUEST_SHA256,
    SYNTHETIC_ONLY_ACKNOWLEDGMENT,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    repository_synthetic_d0_fixture_admission,
)
from .docking.interaction_refinement import (
    INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_RECEIPT_V6_SCHEMA_ID,
)
from .docking.scorer_v1 import SCORER_V1_SCORE_ID, SCORER_V1_TERMS_SCHEMA_ID
from .docking.torsion_contact_refinement import (
    INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
)
from .molecular import (
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    canonical_system_sha256,
    require_valid_all_atom_system,
)
from .reference_pocket import derive_reference_pocket_from_path


STANDALONE_CLI_ID = "betelgeuze-dock/1.0.0"
LIGAND_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_ligand_manifest/1.1.0"
)
PIPELINE_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_pipeline_verification/1.2.0"
)
PIPELINE_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_pipeline_report/1.1.0"
)
EXPLICIT_POCKET_METHOD_ID = "explicit-spherical-known-pocket"
EXPLICIT_POCKET_METHOD_VERSION = "1.0.0"
_SYNTHETIC_D0_POCKET_METHOD_ID = "consumer-reviewed-sphere"
_SYNTHETIC_D0_POCKET_METHOD_VERSION = "1.0.0"
_SYNTHETIC_D0_POCKET_FRAME_ID = "prepared-receptor-frame-v1"
_SYNTHETIC_D0_CONSTRUCTION_PROOF_SCOPE = (
    "process_local_not_serialized_not_cryptographic_attestation"
)
_SYNTHETIC_D0_CAPABILITY_SCOPE = (
    "one_run_process_local_not_serialized_not_cryptographic_attestation"
)
_SYNTHETIC_D0_LIGAND_ATOM_COUNT = 5
_SYNTHETIC_D0_RECEPTOR_ATOM_COUNT = 5
_SYNTHETIC_D0_LIGAND_NONBONDED_PAIR_COUNT = 3
_SYNTHETIC_D0_LIGAND_EXCLUDED_PAIR_COUNT = 7
_SYNTHETIC_D0_RECEPTOR_FULL_CARTESIAN_PAIR_COUNT = 25
_SYNTHETIC_D0_RECEPTOR_OCCUPIED_CELL_COUNT = 3
_SYNTHETIC_D0_POCKET_RADIUS_ANGSTROM = 10.0
_SYNTHETIC_D0_BOND_LENGTH_TOLERANCE_ANGSTROM = 0.15
_SYNTHETIC_D0_LIGAND_SELF_CLASH_ANGSTROM = 0.75
_SYNTHETIC_D0_RECEPTOR_LIGAND_CLASH_ANGSTROM = 0.8
_SYNTHETIC_D0_ROTATION_TOLERANCE = 1.0e-6
_SYNTHETIC_D0_SEVERE_VDW_OVERLAP_SCALE = 0.55

_RESULT_KEYS = frozenset(
    {
        "schema_id",
        "request_sha256",
        "profile_receipt_sha256",
        "pipeline_source_sha256",
        "scorer_source_sha256",
        "refiner_source_sha256",
        "prepared_input_receipt_sha256",
        "conformer_receipt_sha256",
        "authority_input_receipt_sha256",
        "proposal_plan_receipt_sha256",
        "guided_placement_receipt_sha256",
        "authenticated_search_receipt_sha256",
        "pipeline_source_binding_mode",
        "scorer_refiner_source_binding_status",
        "scorer_v1_result_receipt_sha256",
        "budget",
        "budget_sha256",
        "proposal_plan",
        "candidate_count",
        "success_count",
        "failure_count",
        "top_proposal_indices",
        "abstained",
        "component_ids",
        "component_binding_mode",
        "canonical_components_sealed",
        "arbitrary_dependency_injection_used",
        "component_chain_product_qualified",
        "evidence_record_capability_consumed",
        "evidence_record_capability_scope",
        "candidate_evidence",
        "blockers",
        "failure_denominator_preserved",
        "chemistry_inference_performed",
        "pocket_prediction_performed",
        "network_fetch_performed",
        "external_reservation_requested",
        "side_effect_evidence_status",
        "external_reservation_authorized",
        "caller_acknowledged_synthetic_fixture_only",
        "synthetic_fixture_identity_independently_verified",
        "synthetic_d0_fixture_id",
        "synthetic_d0_fixture_manifest_sha256",
        "synthetic_d0_fixture_admission_receipt_sha256",
        "synthetic_only_acknowledgment",
        "test_only",
        "historical_execution_authorized",
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
        "canonical_evidence_recorder_factory_sealed",
        "construction_proof_scope",
        "request",
        "profile",
        "receipt_sha256",
    }
)
_REQUEST_KEYS = frozenset(
    {
        "schema_id",
        "receptor_system_sha256",
        "ligand_system_sha256",
        "pocket_fingerprint_sha256",
        "seed",
        "profile_receipt_sha256",
        "fixture_id",
        "fixture_scope",
        "caller_acknowledged_input_scope",
        "synthetic_only_acknowledgment",
        "synthetic_fixture_identity_independently_verified",
        "test_only",
        "external_reservation_requested",
        "molecular_experiment_authorized",
        "request_sha256",
    }
)
_PROFILE_KEYS = frozenset(
    {
        "schema_id",
        "profile_id",
        "candidate_count",
        "top_k",
        "max_torsions",
        "max_refinement_steps",
        "translation_radius_angstrom_binary64_hex",
        "receptor_margin_angstrom_binary64_hex",
        "proposal_profile",
        "scorer",
        "refiner",
        "geometric_admission",
        "clearance_shadow_selection_enabled",
        "result_dependent_allocation",
        "full_budget_receipt_required",
        "full_proposal_plan_receipt_required",
        "failure_denominator_required",
        "test_only_profile",
        "stage0_eligible",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }
)
_CANDIDATE_KEYS = frozenset(
    {
        "schema_id",
        "candidate_id",
        "proposal_index",
        "status",
        "geometric_admission_status",
        "candidate_removed_from_denominator",
        "search_row_sha256",
        "source_proposal_fingerprint_sha256",
        "result_proposal_fingerprint_sha256",
        "score_binary64_hex",
        "selection_eligible",
        "pose_validity",
        "scorer_terms",
        "refinement_receipt",
        "error_code",
        "baseline_disagreement",
        "claim_safe",
        "canonical_recorder_factory_sealed",
        "construction_proof_scope",
        "receipt_sha256",
    }
)
_BUDGET_KEYS = frozenset(
    {
        "candidate_count",
        "top_k",
        "max_torsions",
        "max_refinement_steps",
        "translation_radius_angstrom",
        "seed",
    }
)
_PROPOSAL_PLAN_KEYS = frozenset(
    {
        "schema_id",
        "component_id",
        "request_sha256",
        "authority_input_receipt_sha256",
        "guidance_context_fingerprint_sha256",
        "guided_policy_fingerprint_sha256",
        "budget",
        "budget_sha256",
        "v3_proposal_indices",
        "allocation_result_dependent",
        "full_budget_bound",
        "claim_safe",
        "receipt_sha256",
    }
)
_POSE_VALIDITY_KEYS = frozenset(
    {
        "valid",
        "checks",
        "evaluated_checks",
        "complete",
        "valid_within_evaluated_scope",
        "measurements",
        "blockers",
        "not_evaluated_reasons",
        "claim_safe",
    }
)
_POSE_CHECK_KEYS = frozenset(
    {
        "proper_rotation",
        "bond_lengths_preserved",
        "ligand_self_clash_free",
        "receptor_ligand_clash_free",
        "declared_chirality_preserved",
        "inside_declared_pocket",
        "element_vdw_ligand_overlap_free",
        "element_vdw_receptor_overlap_free",
    }
)
_POSE_MEASUREMENT_KEYS = frozenset(
    {
        "atom_count",
        "rotation_orthogonality_max_error",
        "rotation_determinant",
        "max_bond_length_delta_angstrom",
        "minimum_ligand_nonbonded_distance_angstrom",
        "evaluated_ligand_nonbonded_pair_count",
        "excluded_ligand_pair_count",
        "minimum_declared_chiral_volume",
        "declared_chirality_center_count",
        "maximum_pocket_center_distance_angstrom",
        "minimum_receptor_ligand_distance_angstrom",
        "evaluated_receptor_ligand_pair_count",
        "full_cartesian_receptor_ligand_pair_count",
        "sparse_receptor_cell_count",
        "element_vdw_ligand_pair_count",
        "element_vdw_ligand_severe_overlap_count",
        "element_vdw_ligand_minimum_distance_angstrom",
        "element_vdw_ligand_minimum_ratio",
        "element_vdw_receptor_candidate_pair_count",
        "element_vdw_receptor_full_cartesian_pair_count",
        "element_vdw_receptor_cell_count",
        "element_vdw_receptor_severe_overlap_count",
        "element_vdw_receptor_minimum_distance_angstrom",
        "element_vdw_receptor_minimum_ratio",
    }
)
_POSE_INTEGER_MEASUREMENTS = frozenset(
    {
        "atom_count",
        "evaluated_ligand_nonbonded_pair_count",
        "excluded_ligand_pair_count",
        "declared_chirality_center_count",
        "evaluated_receptor_ligand_pair_count",
        "full_cartesian_receptor_ligand_pair_count",
        "sparse_receptor_cell_count",
        "element_vdw_ligand_pair_count",
        "element_vdw_ligand_severe_overlap_count",
        "element_vdw_receptor_candidate_pair_count",
        "element_vdw_receptor_full_cartesian_pair_count",
        "element_vdw_receptor_cell_count",
        "element_vdw_receptor_severe_overlap_count",
    }
)
_POSE_BLOCKER_BY_CHECK = {
    "proper_rotation": "rigid_rotation_not_proper_orthogonal",
    "bond_lengths_preserved": "bond_length_preservation_failed",
    "ligand_self_clash_free": "ligand_self_clash_detected",
    "receptor_ligand_clash_free": "receptor_ligand_clash_detected",
    "declared_chirality_preserved": "declared_chirality_not_preserved",
    "inside_declared_pocket": "pose_outside_declared_pocket",
    "element_vdw_ligand_overlap_free": (
        "element_vdw_ligand_severe_overlap_detected"
    ),
    "element_vdw_receptor_overlap_free": (
        "element_vdw_receptor_severe_overlap_detected"
    ),
}
_SCORER_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
)
_SCORER_TERMS_KEYS = frozenset(
    {
        "schema_id",
        "score_id",
        "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
        *(f"{name}_binary64_hex" for name in (*_SCORER_TERM_NAMES, "total_score")),
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
        "calibrated",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
)
_COMPONENT_ROLES = frozenset(
    {
        "input_preparer",
        "conformer_provider",
        "proposal_generator",
        "geometric_admission",
        "scorer",
        "refiner",
        "validity_evaluator",
        "ranker",
        "evidence_recorder",
    }
)
_DEFAULT_COMPONENT_IDS = {
    "input_preparer": "betelgeuze.engine_v2_canonical_prepared_input/1.0.0",
    "conformer_provider": "betelgeuze.engine_v2_retained_source_conformer/1.0.0",
    "proposal_generator": "betelgeuze.engine_v2_current_uniform_v3_proposals/1.0.0",
    "geometric_admission": (
        "betelgeuze.engine_v2_pass_through_geometric_admission/1.0.0"
    ),
    "scorer": "betelgeuze.engine_v2_current_scorer_v1_provider/1.0.0",
    "refiner": "betelgeuze.engine_v2_current_v7_refiner_provider/1.0.0",
    "validity_evaluator": "betelgeuze.engine_v2_embedded_element_validity/1.0.0",
    "ranker": "betelgeuze.engine_v2_embedded_stable_score_ranker/1.0.0",
    "evidence_recorder": "betelgeuze.engine_v2_canonical_pipeline_evidence/1.0.0",
}
_V6_RECEIPT_KEYS = frozenset(
    {
        "schema_id",
        "source_proposal_sha256",
        "config_sha256",
        "lane",
        "v3_proposal_indices",
        "nested_refiner_id",
        "nested_refiner_version",
        "nested_receipt_sha256",
        "initial_penalty_binary64_hex",
        "final_penalty_binary64_hex",
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rotation_steps",
        "line_search_evaluation_count",
        "fallback_direction_step_count",
        "original_pose_valid",
        "total_translation_binary64_hex",
        "total_rotation_vector_binary64_hex",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "ranking_score_reused_as_physical_energy",
        "source_lane_retained",
        "scientifically_validated",
        "receipt_sha256",
    }
)
_V6_CLEARANCE_RECEIPT_KEYS = frozenset(
    {
        "selection_reason",
        "comparison_v2_receipt_sha256",
        "baseline_v3_receipt_sha256",
        "clearance_receipt_sha256",
        "baseline_duplicate_of_v2_refinement",
        "baseline_final_penalty_binary64_hex",
        "clearance_evaluated",
        "clearance_initial_penalty_binary64_hex",
        "clearance_final_penalty_binary64_hex",
        "clearance_selected",
        "near_clear_penalty_binary64_hex",
    }
)
_REFINEMENT_RECEIPT_KEYS = frozenset(
    {
        "schema_id",
        "lane",
        "config_sha256",
        "source_proposal_sha256",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "baseline_coordinates_sha256",
        "baseline_v6_receipt_payload",
        "baseline_v6_receipt_sha256",
        "baseline_v6_max_steps",
        "baseline_v6_penalty_scope",
        "baseline_v6_receptor_penalty_binary64_hex",
        "baseline_v6_internal_penalty_binary64_hex",
        "baseline_v6_combined_penalty_binary64_hex",
        "initial_penalty_binary64_hex",
        "final_penalty_binary64_hex",
        "generic_penalty_scope",
        "initial_receptor_penalty_binary64_hex",
        "initial_internal_penalty_binary64_hex",
        "initial_combined_penalty_binary64_hex",
        "optimized_receptor_penalty_binary64_hex",
        "optimized_internal_penalty_binary64_hex",
        "optimized_combined_penalty_binary64_hex",
        "final_receptor_penalty_binary64_hex",
        "final_internal_penalty_binary64_hex",
        "final_combined_penalty_binary64_hex",
        "minimum_selected_final_receptor_penalty_binary64_hex",
        "maximum_selected_final_receptor_penalty_binary64_hex",
        "selection_window_reachable_from_baseline_v6_receptor_penalty",
        "evaluation_stopped_after_selection_window_became_unreachable",
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rotation_steps",
        "accepted_rigid_rotation_steps",
        "accepted_torsion_steps",
        "accepted_torsion_moves",
        "accepted_rotation_steps_include_torsion",
        "fallback_direction_step_count",
        "line_search_evaluation_count",
        "objective_evaluation_count",
        "fixed_objective_evaluation_count",
        "torsion_trial_objective_evaluation_count",
        "evaluated_torsion_steps",
        "evaluated_torsion_moves",
        "torsion_step_budget",
        "torsion_evaluated",
        "torsion_variant_available",
        "torsion_selected",
        "torsion_evaluation_skip_reason",
        "selection_reason",
        "source_lane_retained",
        "original_pose_valid",
        "rotatable_child_atom_indices",
        "v3_proposal_indices",
        "total_translation_binary64_hex",
        "total_rotation_vector_binary64_hex",
        "total_torsion_path_radians_binary64_hex",
        "evaluated_total_torsion_path_radians_binary64_hex",
        "posebusters_or_rmsd_used_for_selection",
        "ranking_score_reused_as_physical_energy",
        "scientifically_validated",
        "receipt_sha256",
    }
)
_V7_SCALAR_BINARY64_FIELDS = frozenset(
    {
        "baseline_v6_receptor_penalty_binary64_hex",
        "baseline_v6_internal_penalty_binary64_hex",
        "baseline_v6_combined_penalty_binary64_hex",
        "initial_penalty_binary64_hex",
        "final_penalty_binary64_hex",
        "initial_receptor_penalty_binary64_hex",
        "initial_internal_penalty_binary64_hex",
        "initial_combined_penalty_binary64_hex",
        "optimized_receptor_penalty_binary64_hex",
        "optimized_internal_penalty_binary64_hex",
        "optimized_combined_penalty_binary64_hex",
        "final_receptor_penalty_binary64_hex",
        "final_internal_penalty_binary64_hex",
        "final_combined_penalty_binary64_hex",
        "minimum_selected_final_receptor_penalty_binary64_hex",
        "maximum_selected_final_receptor_penalty_binary64_hex",
        "total_torsion_path_radians_binary64_hex",
        "evaluated_total_torsion_path_radians_binary64_hex",
    }
)
_V7_VECTOR_BINARY64_FIELDS = frozenset(
    {
        "total_translation_binary64_hex",
        "total_rotation_vector_binary64_hex",
    }
)
_V7_INTEGER_FIELDS = frozenset(
    {
        "baseline_v6_max_steps",
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rotation_steps",
        "accepted_rigid_rotation_steps",
        "accepted_torsion_steps",
        "fallback_direction_step_count",
        "line_search_evaluation_count",
        "objective_evaluation_count",
        "fixed_objective_evaluation_count",
        "torsion_trial_objective_evaluation_count",
        "evaluated_torsion_steps",
        "torsion_step_budget",
    }
)
_TORSION_MOVE_KEYS = frozenset(
    {
        "rotatable_child_atom_index",
        "delta_radians_binary64_hex",
        "receptor_penalty_binary64_hex",
        "internal_penalty_binary64_hex",
        "combined_penalty_binary64_hex",
    }
)
_V7_BOOLEAN_FIELDS = frozenset(
    {
        "selection_window_reachable_from_baseline_v6_receptor_penalty",
        "evaluation_stopped_after_selection_window_became_unreachable",
        "torsion_evaluated",
        "torsion_variant_available",
        "torsion_selected",
        "accepted_rotation_steps_include_torsion",
        "source_lane_retained",
        "original_pose_valid",
        "posebusters_or_rmsd_used_for_selection",
        "ranking_score_reused_as_physical_energy",
        "scientifically_validated",
    }
)


class StandaloneDockCliError(EngineV2CliError):
    """The standalone CLI failed closed."""


def _installed_source_sha256() -> str:
    try:
        payload = resources.files("betelgeuze_engine_v2").joinpath(
            "standalone_cli.py"
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise StandaloneDockCliError(
            "installed standalone CLI source is unavailable"
        ) from exc
    if not payload:
        raise StandaloneDockCliError("installed standalone CLI source is empty")
    return _sha256_bytes(payload)


def _installed_docking_source_sha256(filename: str) -> str:
    try:
        payload = resources.files("betelgeuze_engine_v2.docking").joinpath(
            filename
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise StandaloneDockCliError(
            f"installed docking source {filename!r} is unavailable"
        ) from exc
    if not payload:
        raise StandaloneDockCliError(
            f"installed docking source {filename!r} is empty"
        )
    return _sha256_bytes(payload)


def _canonical_system_from_path(path: Path, *, role: str) -> tuple[AllAtomSystem, bytes]:
    raw = _read_bounded(path, maximum=MAX_CLI_INPUT_BYTES, name=f"{role} document")
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise StandaloneDockCliError(f"{role} document has non-canonical line endings")
    try:
        system = all_atom_system_from_canonical_json(canonical)
        require_valid_all_atom_system(system)
    except (TypeError, ValueError) as exc:
        raise StandaloneDockCliError(f"{role} canonical system is invalid") from exc
    expected = canonical_system_json_bytes(system)
    if expected != canonical:
        raise StandaloneDockCliError(f"{role} document bytes are not canonical")
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise StandaloneDockCliError(f"{role} must use CPU float64 coordinates")
    if any(atom.partial_charge_e is None for atom in system.atoms):
        raise StandaloneDockCliError(f"{role} lacks explicit partial charges")
    return system, expected


def _write_canonical_system(
    payload: bytes,
    output: Path,
    *,
    overwrite: bool,
    input_paths: Sequence[Path] = (),
) -> None:
    document = json.loads(payload.decode("ascii"), object_pairs_hook=_reject_duplicate_pairs)
    if not isinstance(document, dict):
        raise StandaloneDockCliError("canonical system document is not an object")
    _write_output(
        document,
        output,
        overwrite=overwrite,
        input_paths=input_paths,
    )


def prepare_receptor(
    source: Path,
    output: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    system, canonical = _canonical_system_from_path(source, role="receptor")
    _write_canonical_system(
        canonical,
        output,
        overwrite=overwrite,
        input_paths=(source,),
    )
    return {
        "system_sha256": canonical_system_sha256(system),
        "output": str(output),
        "chemistry_inference_performed": False,
        "network_fetch_performed": False,
    }


def prepare_ligands(
    sources: Sequence[Path],
    output_directory: Path,
) -> dict[str, object]:
    if not sources:
        raise StandaloneDockCliError("at least one ligand input is required")
    rows: list[dict[str, object]] = []
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    for source in sources:
        system, canonical = _canonical_system_from_path(source, role="ligand")
        system_sha = canonical_system_sha256(system)
        if system_sha in seen:
            raise StandaloneDockCliError("ligand system identities must be unique")
        seen.add(system_sha)
        filename = f"{system_sha}.json"
        files[filename] = canonical + b"\n"
        rows.append(
            {
                "system_sha256": system_sha,
                "canonical_file": filename,
                "atom_count": system.atom_count,
                "model_count": system.model_count,
            }
        )
    rows.sort(key=lambda row: str(row["system_sha256"]))
    projection: dict[str, object] = {
        "schema_id": LIGAND_MANIFEST_SCHEMA_ID,
        "manifest_filename": "manifest.json",
        "systems": rows,
        "system_count": len(rows),
        "bundle_absent_only": True,
        "bundle_publication": (
            "private_sibling_staging_fsync_atomic_noreplace_parent_fsync"
        ),
        "chemistry_inference_performed": False,
        "network_fetch_performed": False,
        "claim_safe": False,
    }
    document = {**projection, "receipt_sha256": _sha256_document(projection)}
    files["manifest.json"] = _canonical_bytes(document) + b"\n"
    _write_private_bundle(
        files,
        output_directory,
        input_paths=tuple(sources),
    )
    return document


def _finite_vector3(values: Sequence[float]) -> torch.Tensor:
    if len(values) != 3:
        raise StandaloneDockCliError("pocket center requires exactly three values")
    center = torch.tensor(values, dtype=torch.float64)
    if not bool(torch.isfinite(center).all().item()):
        raise StandaloneDockCliError("pocket center must be finite")
    return center


def define_explicit_pocket(
    *,
    center_angstrom: Sequence[float],
    radius_angstrom: float,
    coordinate_frame_id: str,
    source_artifact: Path,
) -> dict[str, object]:
    source = _read_bounded(
        source_artifact,
        maximum=MAX_CLI_INPUT_BYTES,
        name="pocket source artifact",
    )
    radius = float(radius_angstrom)
    if not math.isfinite(radius) or not 0.0 < radius <= 100.0:
        raise StandaloneDockCliError("pocket radius is outside (0,100]")
    implementation_sha = _installed_source_sha256()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id=EXPLICIT_POCKET_METHOD_ID,
        method_version=EXPLICIT_POCKET_METHOD_VERSION,
        coordinate_frame_id=coordinate_frame_id,
        center=_finite_vector3(center_angstrom),
        radius_angstrom=radius,
        source_artifact_sha256=_sha256_bytes(source),
        implementation_source_sha256=implementation_sha,
        metadata={
            "operator_supplied_geometry": True,
            "pocket_prediction_performed": False,
            "implementation_source_preimport_attested": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )
    return {
        "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
        "scope": pocket.scope.value,
        "method_id": pocket.method_id,
        "method_version": pocket.method_version,
        "coordinate_frame_id": pocket.coordinate_frame_id,
        "center_angstrom": [float(value) for value in pocket.center.tolist()],
        "radius_angstrom": pocket.radius_angstrom,
        "source_artifact_sha256": pocket.source_artifact_sha256,
        "implementation_source_sha256": pocket.implementation_source_sha256,
        "metadata": dict(pocket.metadata),
    }


def _define_synthetic_d0_fixture_pocket() -> dict[str, object]:
    admission = repository_synthetic_d0_fixture_admission()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id=_SYNTHETIC_D0_POCKET_METHOD_ID,
        method_version=_SYNTHETIC_D0_POCKET_METHOD_VERSION,
        coordinate_frame_id=_SYNTHETIC_D0_POCKET_FRAME_ID,
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
        metadata={},
    )
    if pocket.fingerprint_sha256 != admission.pocket_fingerprint_sha256:
        raise StandaloneDockCliError(
            "package-owned synthetic D0 pocket identity is inconsistent"
        )
    return {
        "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
        "scope": pocket.scope.value,
        "method_id": pocket.method_id,
        "method_version": pocket.method_version,
        "coordinate_frame_id": pocket.coordinate_frame_id,
        "center_angstrom": [float(value) for value in pocket.center.tolist()],
        "radius_angstrom": pocket.radius_angstrom,
        "source_artifact_sha256": pocket.source_artifact_sha256,
        "implementation_source_sha256": pocket.implementation_source_sha256,
        "metadata": {},
    }


def define_pocket(arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.synthetic_d0_fixture:
        if (
            arguments.reference_ligand is not None
            or arguments.center is not None
            or arguments.radius is not None
            or arguments.source_artifact is not None
            or arguments.model_index is not None
            or arguments.padding_angstrom is not None
            or arguments.minimum_radius_angstrom is not None
            or arguments.coordinate_frame_id != _SYNTHETIC_D0_POCKET_FRAME_ID
        ):
            raise StandaloneDockCliError(
                "synthetic D0 pocket rejects caller geometry and requires only "
                "its exact coordinate frame"
            )
        return _define_synthetic_d0_fixture_pocket()
    if arguments.reference_ligand is not None:
        if arguments.radius is not None or arguments.source_artifact is not None:
            raise StandaloneDockCliError(
                "reference-ligand pockets do not accept explicit radius/source"
            )
        return derive_reference_pocket_from_path(
            arguments.reference_ligand,
            coordinate_frame_id=arguments.coordinate_frame_id,
            model_index=(
                0 if arguments.model_index is None else arguments.model_index
            ),
            padding_angstrom=(
                4.0
                if arguments.padding_angstrom is None
                else arguments.padding_angstrom
            ),
            minimum_radius_angstrom=(
                6.0
                if arguments.minimum_radius_angstrom is None
                else arguments.minimum_radius_angstrom
            ),
        )
    if (
        arguments.model_index is not None
        or arguments.padding_angstrom is not None
        or arguments.minimum_radius_angstrom is not None
    ):
        raise StandaloneDockCliError(
            "reference geometry tuning flags require --reference-ligand"
        )
    if arguments.center is None or arguments.radius is None or arguments.source_artifact is None:
        raise StandaloneDockCliError(
            "explicit pockets require --center, --radius, and --source-artifact"
        )
    return define_explicit_pocket(
        center_angstrom=arguments.center,
        radius_angstrom=arguments.radius,
        coordinate_frame_id=arguments.coordinate_frame_id,
        source_artifact=arguments.source_artifact,
    )


def dock(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    seed: int,
    synthetic_acknowledged: bool = False,
) -> dict[str, object]:
    if synthetic_acknowledged is not True:
        raise StandaloneDockCliError(
            "exact synthetic D0 docking requires --test-only-synthetic"
        )
    receptor, _ = _canonical_system_from_path(receptor_path, role="receptor")
    ligand, _ = _canonical_system_from_path(ligand_path, role="ligand")
    pocket_raw = _read_bounded(
        pocket_path,
        maximum=MAX_CLI_POCKET_BYTES,
        name="pocket document",
    )
    pocket = _pocket_from_document(_load_canonical_pocket_document(pocket_raw))
    admission = repository_synthetic_d0_fixture_admission()
    profile = DockingPipelineProfileV1()
    try:
        request = DockingPipelineRequestV1(
            receptor_system=receptor,
            ligand_system=ligand,
            pocket=pocket,
            seed=seed,
            synthetic_only_acknowledgment=SYNTHETIC_ONLY_ACKNOWLEDGMENT,
            fixture_admission=admission,
            profile=profile,
            test_only=True,
        )
        return DockingPipeline().run(request).to_dict()
    except DockingPipelineError as exc:
        raise StandaloneDockCliError(
            "synthetic D0 request failed exact package admission"
        ) from exc


def _load_canonical_json(path: Path, *, name: str, maximum: int) -> dict[str, object]:
    raw = _read_bounded(path, maximum=maximum, name=name)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise StandaloneDockCliError(f"{name} has non-canonical line endings")
    try:
        document = json.loads(
            canonical.decode("ascii"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StandaloneDockCliError(f"{name} is invalid JSON") from exc
    if not isinstance(document, dict) or _canonical_bytes(document) != canonical:
        raise StandaloneDockCliError(f"{name} bytes are not canonical")
    return document


def _require_exact_keys(
    document: Mapping[str, object],
    expected: frozenset[str],
    *,
    name: str,
) -> None:
    observed = set(document)
    missing = expected - observed
    unexpected = observed - expected
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(sorted(missing)))
        if unexpected:
            details.append("unexpected=" + ",".join(sorted(unexpected)))
        raise StandaloneDockCliError(
            f"{name} keys do not match the exact schema ({'; '.join(details)})"
        )


def _require_digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise StandaloneDockCliError(f"{name} is not a lowercase SHA-256")
    text = value
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise StandaloneDockCliError(f"{name} is not a lowercase SHA-256")
    return text


def _require_exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise StandaloneDockCliError(f"{name} is not an admitted integer")
    return value


def _require_exact_bool(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise StandaloneDockCliError(f"{name} is not an admitted boolean")
    return value


def _require_nonempty_text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StandaloneDockCliError(f"{name} is not an admitted string")
    return value


def _binary64(value: object, *, name: str) -> float:
    if not isinstance(value, str) or not value:
        raise StandaloneDockCliError(f"{name} is not a binary64 hex string")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise StandaloneDockCliError(f"{name} is not a binary64 hex string") from exc
    if not math.isfinite(number) or number.hex() != value:
        raise StandaloneDockCliError(f"{name} is not canonical finite binary64")
    return number


def _binary64_vector3(value: object, *, name: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise StandaloneDockCliError(f"{name} is not a binary64 vector3")
    return tuple(
        _binary64(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )


def _index_list(value: object, *, name: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise StandaloneDockCliError(f"{name} is not an index list")
    indices = tuple(
        _require_exact_int(index, name=f"{name}[{position}]")
        for position, index in enumerate(value)
    )
    if len(indices) != len(set(indices)):
        raise StandaloneDockCliError(f"{name} contains duplicate indices")
    return indices


def _torsion_moves(value: object, *, name: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise StandaloneDockCliError(f"{name} is not a torsion move list")
    rows: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise StandaloneDockCliError(f"{name}[{index}] is not an object")
        _require_exact_keys(raw, _TORSION_MOVE_KEYS, name=f"{name}[{index}]")
        _require_exact_int(
            raw.get("rotatable_child_atom_index"),
            name=f"{name}[{index}] rotor index",
        )
        for field in (
            "delta_radians_binary64_hex",
            "receptor_penalty_binary64_hex",
            "internal_penalty_binary64_hex",
            "combined_penalty_binary64_hex",
        ):
            _binary64(raw.get(field), name=f"{name}[{index}] {field}")
        rows.append(dict(raw))
    return tuple(rows)


def _require_hash(document: Mapping[str, object], field: str, projection: object) -> None:
    observed = _require_digest(document.get(field), name=field)
    expected = _sha256_document(projection)
    if observed != expected:
        raise StandaloneDockCliError(f"{field} mismatch")


def _verify_profile(profile: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(profile, _PROFILE_KEYS, name="pipeline profile")
    if profile.get("schema_id") != PIPELINE_PROFILE_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline profile schema is unsupported")
    try:
        normalized = DockingPipelineProfileV1().to_dict()
    except (TypeError, ValueError, RuntimeError) as exc:
        if isinstance(exc, StandaloneDockCliError):
            raise
        raise StandaloneDockCliError("pipeline profile semantics are invalid") from exc
    if dict(profile) != normalized:
        raise StandaloneDockCliError(
            "pipeline profile is not the exact admitted fixed64/Top5 profile"
        )
    return normalized


def _verify_request(
    request: Mapping[str, object],
    *,
    profile_receipt_sha256: str,
) -> dict[str, object]:
    _require_exact_keys(request, _REQUEST_KEYS, name="pipeline request")
    if request.get("schema_id") != PIPELINE_REQUEST_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline request schema is unsupported")
    admission = repository_synthetic_d0_fixture_admission()
    for field in (
        "receptor_system_sha256",
        "ligand_system_sha256",
        "pocket_fingerprint_sha256",
        "profile_receipt_sha256",
    ):
        _require_digest(request.get(field), name=f"request {field}")
    if request.get("profile_receipt_sha256") != profile_receipt_sha256:
        raise StandaloneDockCliError("request/profile receipt cross-binding mismatch")
    seed = _require_exact_int(request.get("seed"), name="request seed")
    if (
        seed != admission.seed
        or request.get("receptor_system_sha256")
        != admission.receptor_system_sha256
        or request.get("ligand_system_sha256") != admission.ligand_system_sha256
        or request.get("pocket_fingerprint_sha256")
        != admission.pocket_fingerprint_sha256
        or request.get("profile_receipt_sha256")
        != admission.profile_receipt_sha256
        or request.get("fixture_id") != admission.fixture_id
        or request.get("fixture_scope") != "repository_owned_synthetic_d0"
        or request.get("caller_acknowledged_input_scope")
        != "synthetic_fixture_only"
        or request.get("synthetic_only_acknowledgment")
        != SYNTHETIC_ONLY_ACKNOWLEDGMENT
        or request.get("synthetic_fixture_identity_independently_verified")
        is not True
    ):
        raise StandaloneDockCliError(
            "pipeline request is not the exact package-owned synthetic D0 fixture"
        )
    if (
        request.get("test_only") is not True
        or request.get("external_reservation_requested") is not False
        or request.get("molecular_experiment_authorized") is not False
    ):
        raise StandaloneDockCliError("pipeline request asserts forbidden execution authority")
    projection = dict(request)
    projection.pop("request_sha256")
    _require_hash(request, "request_sha256", projection)
    if request.get("request_sha256") != SYNTHETIC_D0_FIXTURE_REQUEST_SHA256:
        raise StandaloneDockCliError("pipeline request identity is not admitted")
    return dict(request)


def _budget_sha256(budget: Mapping[str, object]) -> str:
    return _sha256_document(
        {
            "schema_id": "betelgeuze.engine_v2_docking_budget_identity/1.0.0",
            "budget": dict(budget),
        }
    )


def _verify_budget(
    budget: Mapping[str, object],
    *,
    profile: Mapping[str, object],
    request: Mapping[str, object],
) -> str:
    _require_exact_keys(budget, _BUDGET_KEYS, name="pipeline budget")
    for field in (
        "candidate_count",
        "top_k",
        "max_torsions",
        "max_refinement_steps",
        "seed",
    ):
        _require_exact_int(budget.get(field), name=f"pipeline budget {field}")
    translation = budget.get("translation_radius_angstrom")
    if type(translation) is not float or not math.isfinite(translation):
        raise StandaloneDockCliError(
            "pipeline budget translation_radius_angstrom is not a finite float"
        )
    expected = {
        "candidate_count": profile["candidate_count"],
        "top_k": profile["top_k"],
        "max_torsions": profile["max_torsions"],
        "max_refinement_steps": profile["max_refinement_steps"],
        "translation_radius_angstrom": _binary64(
            profile["translation_radius_angstrom_binary64_hex"],
            name="profile translation radius",
        ),
        "seed": request["seed"],
    }
    if dict(budget) != expected:
        raise StandaloneDockCliError("pipeline budget is cross-wired")
    return _budget_sha256(budget)


def _verify_proposal_plan(
    plan: Mapping[str, object],
    *,
    request_sha256: str,
    authority_input_receipt_sha256: str,
    budget: Mapping[str, object],
    budget_sha256: str,
    proposal_component_id: str,
    candidate_count: int,
) -> tuple[str, tuple[int, ...]]:
    _require_exact_keys(plan, _PROPOSAL_PLAN_KEYS, name="pipeline proposal plan")
    if plan.get("schema_id") != PIPELINE_PROPOSAL_PLAN_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline proposal plan schema is unsupported")
    for field in (
        "authority_input_receipt_sha256",
        "guidance_context_fingerprint_sha256",
        "guided_policy_fingerprint_sha256",
        "budget_sha256",
    ):
        _require_digest(plan.get(field), name=f"pipeline proposal plan {field}")
    if (
        plan.get("component_id") != proposal_component_id
        or plan.get("request_sha256") != request_sha256
        or plan.get("authority_input_receipt_sha256")
        != authority_input_receipt_sha256
        or plan.get("budget") != dict(budget)
        or plan.get("budget_sha256") != budget_sha256
        or plan.get("allocation_result_dependent") is not False
        or plan.get("full_budget_bound") is not True
        or plan.get("claim_safe") is not False
    ):
        raise StandaloneDockCliError("pipeline proposal plan is cross-wired")
    indices = _index_list(
        plan.get("v3_proposal_indices"),
        name="pipeline proposal plan v3 indices",
    )
    if indices != tuple(sorted(indices)) or any(
        index >= candidate_count for index in indices
    ):
        raise StandaloneDockCliError("pipeline proposal allocation is invalid")
    projection = dict(plan)
    projection.pop("receipt_sha256")
    _require_hash(plan, "receipt_sha256", projection)
    return str(plan["receipt_sha256"]), indices


def _verify_pose_validity(document: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(document, _POSE_VALIDITY_KEYS, name="pose validity")
    checks = document.get("checks")
    evaluated = document.get("evaluated_checks")
    if not isinstance(checks, dict) or not isinstance(evaluated, dict):
        raise StandaloneDockCliError("pose validity check maps are missing")
    if set(checks) != _POSE_CHECK_KEYS or set(evaluated) != _POSE_CHECK_KEYS:
        raise StandaloneDockCliError("pose validity check keys are incomplete")
    if any(type(value) is not bool for value in (*checks.values(), *evaluated.values())):
        raise StandaloneDockCliError("pose validity checks must be booleans")
    complete = all(evaluated.values())
    valid_within_scope = all(
        checks[key] for key in _POSE_CHECK_KEYS if evaluated[key]
    )
    if document.get("complete") is not complete:
        raise StandaloneDockCliError("pose validity complete flag is inconsistent")
    if document.get("valid_within_evaluated_scope") is not valid_within_scope:
        raise StandaloneDockCliError("pose validity scoped result is inconsistent")
    if document.get("valid") is not (complete and valid_within_scope):
        raise StandaloneDockCliError("pose validity derived result is inconsistent")
    if document.get("claim_safe") is not False:
        raise StandaloneDockCliError("pose validity asserts a forbidden claim")
    measurements = document.get("measurements")
    if not isinstance(measurements, dict) or set(measurements) != _POSE_MEASUREMENT_KEYS:
        raise StandaloneDockCliError("pose validity measurements are invalid")
    for field, value in measurements.items():
        if field in _POSE_INTEGER_MEASUREMENTS:
            _require_exact_int(value, name=f"pose validity measurement {field}")
        elif (
            type(value) is not float
            or not math.isfinite(value)
            or (field != "rotation_determinant" and value < 0.0)
        ):
            raise StandaloneDockCliError(
                f"pose validity measurement {field} is not an admitted float"
            )
    if (
        measurements["atom_count"] != _SYNTHETIC_D0_LIGAND_ATOM_COUNT
        or measurements["declared_chirality_center_count"] != 0
        or measurements["minimum_declared_chiral_volume"] != 0.0
        or measurements["evaluated_ligand_nonbonded_pair_count"]
        != _SYNTHETIC_D0_LIGAND_NONBONDED_PAIR_COUNT
        or measurements["excluded_ligand_pair_count"]
        != _SYNTHETIC_D0_LIGAND_EXCLUDED_PAIR_COUNT
        or measurements["element_vdw_ligand_pair_count"]
        != measurements["evaluated_ligand_nonbonded_pair_count"]
        or measurements["full_cartesian_receptor_ligand_pair_count"]
        != _SYNTHETIC_D0_RECEPTOR_FULL_CARTESIAN_PAIR_COUNT
        or measurements["sparse_receptor_cell_count"]
        != _SYNTHETIC_D0_RECEPTOR_OCCUPIED_CELL_COUNT
        or measurements["sparse_receptor_cell_count"]
        > _SYNTHETIC_D0_RECEPTOR_ATOM_COUNT
    ):
        raise StandaloneDockCliError(
            "pose validity fixed synthetic D0 measurements are inconsistent"
        )
    expected_checks = {
        "proper_rotation": (
            measurements["rotation_orthogonality_max_error"]
            <= _SYNTHETIC_D0_ROTATION_TOLERANCE
            and abs(measurements["rotation_determinant"] - 1.0)
            <= _SYNTHETIC_D0_ROTATION_TOLERANCE
        ),
        "bond_lengths_preserved": (
            measurements["max_bond_length_delta_angstrom"]
            <= _SYNTHETIC_D0_BOND_LENGTH_TOLERANCE_ANGSTROM
        ),
        "ligand_self_clash_free": (
            measurements["minimum_ligand_nonbonded_distance_angstrom"]
            >= _SYNTHETIC_D0_LIGAND_SELF_CLASH_ANGSTROM
        ),
        "receptor_ligand_clash_free": (
            measurements["minimum_receptor_ligand_distance_angstrom"]
            >= _SYNTHETIC_D0_RECEPTOR_LIGAND_CLASH_ANGSTROM
        ),
        # The exact admitted fixture has no declared chirality center.  The
        # identity/count checks above make this otherwise non-derivable check
        # fully determined from the serialized measurement set.
        "declared_chirality_preserved": True,
        "inside_declared_pocket": (
            measurements["maximum_pocket_center_distance_angstrom"]
            <= _SYNTHETIC_D0_POCKET_RADIUS_ANGSTROM
        ),
        "element_vdw_ligand_overlap_free": (
            measurements["element_vdw_ligand_severe_overlap_count"] == 0
        ),
        "element_vdw_receptor_overlap_free": (
            measurements["element_vdw_receptor_severe_overlap_count"] == 0
        ),
    }
    if (
        measurements["element_vdw_receptor_full_cartesian_pair_count"]
        != measurements["full_cartesian_receptor_ligand_pair_count"]
        or measurements["element_vdw_receptor_candidate_pair_count"]
        != measurements["evaluated_receptor_ligand_pair_count"]
        or measurements["evaluated_receptor_ligand_pair_count"]
        > measurements["full_cartesian_receptor_ligand_pair_count"]
        or measurements["element_vdw_ligand_minimum_distance_angstrom"]
        != measurements["minimum_ligand_nonbonded_distance_angstrom"]
        or measurements["element_vdw_receptor_minimum_distance_angstrom"]
        != measurements["minimum_receptor_ligand_distance_angstrom"]
        or measurements["element_vdw_receptor_cell_count"]
        != measurements["sparse_receptor_cell_count"]
        or measurements["element_vdw_ligand_severe_overlap_count"]
        > measurements["element_vdw_ligand_pair_count"]
        or measurements["element_vdw_receptor_severe_overlap_count"]
        > measurements["element_vdw_receptor_candidate_pair_count"]
        or (
            measurements["element_vdw_ligand_severe_overlap_count"] == 0
        )
        is not (
            measurements["element_vdw_ligand_minimum_ratio"]
            >= _SYNTHETIC_D0_SEVERE_VDW_OVERLAP_SCALE
        )
        or (
            measurements["element_vdw_receptor_severe_overlap_count"] == 0
        )
        is not (
            measurements["element_vdw_receptor_minimum_ratio"]
            >= _SYNTHETIC_D0_SEVERE_VDW_OVERLAP_SCALE
        )
        or any(
            checks[check_name] is not expected
            for check_name, expected in expected_checks.items()
        )
    ):
        raise StandaloneDockCliError(
            "pose validity measured checks are inconsistent"
        )
    blockers = document.get("blockers")
    if (
        not isinstance(blockers, list)
        or any(not isinstance(value, str) or not value for value in blockers)
        or len(blockers) != len(set(blockers))
    ):
        raise StandaloneDockCliError("pose validity blockers are invalid")
    expected_blockers = [
        blocker
        for check, blocker in _POSE_BLOCKER_BY_CHECK.items()
        if evaluated[check] and not checks[check]
    ]
    if blockers != expected_blockers:
        raise StandaloneDockCliError("pose validity blockers are inconsistent")
    reasons = document.get("not_evaluated_reasons")
    expected_reason_keys = {key for key, value in evaluated.items() if not value}
    if (
        not isinstance(reasons, dict)
        or set(reasons) != expected_reason_keys
        or any(not isinstance(value, str) or not value for value in reasons.values())
    ):
        raise StandaloneDockCliError("pose validity non-evaluation reasons are inconsistent")
    return dict(document)


def _verify_scorer_terms(
    document: Mapping[str, object],
    *,
    authority_input_receipt_sha256: str,
    result_proposal_fingerprint_sha256: str,
    ligand_atom_count: int,
) -> float:
    _require_exact_keys(document, _SCORER_TERMS_KEYS, name="ScorerV1Terms")
    if document.get("schema_id") != SCORER_V1_TERMS_SCHEMA_ID:
        raise StandaloneDockCliError("ScorerV1Terms schema is unsupported")
    if document.get("score_id") != SCORER_V1_SCORE_ID:
        raise StandaloneDockCliError("ScorerV1Terms score identity is unsupported")
    for field in (
        "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
    ):
        _require_digest(document.get(field), name=f"ScorerV1Terms {field}")
    if document.get("authority_input_receipt_sha256") != authority_input_receipt_sha256:
        raise StandaloneDockCliError("ScorerV1Terms authority cross-binding mismatch")
    if document.get("proposal_fingerprint_sha256") != result_proposal_fingerprint_sha256:
        raise StandaloneDockCliError("ScorerV1Terms proposal cross-binding mismatch")
    values = {
        name: _binary64(
            document.get(f"{name}_binary64_hex"),
            name=f"ScorerV1Terms {name}",
        )
        for name in (*_SCORER_TERM_NAMES, "total_score")
    }
    if not math.isclose(
        values["total_score"],
        sum(values[name] for name in _SCORER_TERM_NAMES),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise StandaloneDockCliError("ScorerV1Terms total is inconsistent")
    counts: dict[str, int] = {}
    for field in (
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
    ):
        counts[field] = _require_exact_int(
            document.get(field),
            name=f"ScorerV1Terms {field}",
        )
    if (
        counts["ligand_pair_count"] > ligand_atom_count * (ligand_atom_count - 1) // 2
        or counts["hbond_count"] > counts["receptor_candidate_pair_count"]
        or counts["hydrophobic_contact_count"]
        > counts["receptor_candidate_pair_count"]
        or counts["buried_polar_count"] > ligand_atom_count
    ):
        raise StandaloneDockCliError("ScorerV1Terms count bounds are inconsistent")
    if any(
        document.get(field) is not False
        for field in ("calibrated", "scientifically_validated", "claim_safe")
    ):
        raise StandaloneDockCliError("ScorerV1Terms asserts a forbidden claim")
    projection = dict(document)
    projection.pop("receipt_sha256")
    _require_hash(document, "receipt_sha256", projection)
    return values["total_score"]


def _verify_v6_refinement_receipt(
    document: Mapping[str, object],
    *,
    source_proposal_fingerprint_sha256: str,
) -> str:
    observed_keys = set(document)
    clearance_variant = observed_keys == (
        _V6_RECEIPT_KEYS | _V6_CLEARANCE_RECEIPT_KEYS
    )
    _require_exact_keys(
        document,
        _V6_RECEIPT_KEYS | (_V6_CLEARANCE_RECEIPT_KEYS if clearance_variant else frozenset()),
        name="V6 refinement receipt",
    )
    if (
        document.get("schema_id")
        != INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_RECEIPT_V6_SCHEMA_ID
    ):
        raise StandaloneDockCliError("V6 refinement receipt schema is unsupported")
    for field in (
        "source_proposal_sha256",
        "config_sha256",
        "nested_receipt_sha256",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
    ):
        _require_digest(document.get(field), name=f"V6 refinement {field}")
    if document.get("source_proposal_sha256") != source_proposal_fingerprint_sha256:
        raise StandaloneDockCliError("V6 refinement source cross-binding mismatch")
    _require_nonempty_text(document.get("lane"), name="V6 refinement lane")
    _require_nonempty_text(
        document.get("nested_refiner_id"),
        name="V6 nested refiner identity",
    )
    _require_nonempty_text(
        document.get("nested_refiner_version"),
        name="V6 nested refiner version",
    )
    _index_list(document.get("v3_proposal_indices"), name="V6 v3 proposal indices")
    for field in (
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rotation_steps",
        "line_search_evaluation_count",
        "fallback_direction_step_count",
    ):
        _require_exact_int(document.get(field), name=f"V6 refinement {field}")
    for field in (
        "original_pose_valid",
        "ranking_score_reused_as_physical_energy",
        "source_lane_retained",
        "scientifically_validated",
    ):
        _require_exact_bool(document.get(field), name=f"V6 refinement {field}")
    for field in (
        "initial_penalty_binary64_hex",
        "final_penalty_binary64_hex",
    ):
        _binary64(document.get(field), name=f"V6 refinement {field}")
    for field in (
        "total_translation_binary64_hex",
        "total_rotation_vector_binary64_hex",
    ):
        _binary64_vector3(document.get(field), name=f"V6 refinement {field}")
    if clearance_variant:
        _require_nonempty_text(
            document.get("selection_reason"),
            name="V6 clearance selection reason",
        )
        for field in (
            "comparison_v2_receipt_sha256",
            "baseline_v3_receipt_sha256",
        ):
            _require_digest(document.get(field), name=f"V6 clearance {field}")
        for field in (
            "baseline_duplicate_of_v2_refinement",
            "clearance_evaluated",
            "clearance_selected",
        ):
            _require_exact_bool(document.get(field), name=f"V6 clearance {field}")
        for field in (
            "baseline_final_penalty_binary64_hex",
            "near_clear_penalty_binary64_hex",
        ):
            _binary64(document.get(field), name=f"V6 clearance {field}")
        if document.get("clearance_evaluated"):
            _require_digest(
                document.get("clearance_receipt_sha256"),
                name="V6 clearance receipt_sha256",
            )
            for field in (
                "clearance_initial_penalty_binary64_hex",
                "clearance_final_penalty_binary64_hex",
            ):
                _binary64(document.get(field), name=f"V6 clearance {field}")
        elif (
            document.get("clearance_receipt_sha256") != ""
            or document.get("clearance_initial_penalty_binary64_hex") != ""
            or document.get("clearance_final_penalty_binary64_hex") != ""
            or document.get("clearance_selected") is not False
        ):
            raise StandaloneDockCliError("V6 unevaluated clearance fields are inconsistent")
    if (
        document.get("ranking_score_reused_as_physical_energy") is not False
        or document.get("scientifically_validated") is not False
        or document.get("accepted_steps")
        != document.get("accepted_translation_steps")
        + document.get("accepted_rotation_steps")
    ):
        raise StandaloneDockCliError("V6 refinement receipt semantics are inconsistent")
    projection = dict(document)
    projection.pop("receipt_sha256")
    _require_hash(document, "receipt_sha256", projection)
    return str(document["receipt_sha256"])


def _verify_refinement_receipt(
    document: Mapping[str, object],
    *,
    source_proposal_fingerprint_sha256: str,
) -> tuple[int, ...]:
    _require_exact_keys(
        document,
        _REFINEMENT_RECEIPT_KEYS,
        name="V7 refinement receipt",
    )
    if document.get("schema_id") != INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID:
        raise StandaloneDockCliError("V7 refinement receipt schema is unsupported")
    for field in (
        "config_sha256",
        "source_proposal_sha256",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "baseline_coordinates_sha256",
        "baseline_v6_receipt_sha256",
    ):
        _require_digest(document.get(field), name=f"V7 refinement {field}")
    if document.get("source_proposal_sha256") != source_proposal_fingerprint_sha256:
        raise StandaloneDockCliError("V7 refinement source cross-binding mismatch")
    payload = document.get("baseline_v6_receipt_payload")
    if not isinstance(payload, dict):
        raise StandaloneDockCliError("V7 baseline V6 receipt payload is missing")
    baseline_receipt = _verify_v6_refinement_receipt(
        payload,
        source_proposal_fingerprint_sha256=source_proposal_fingerprint_sha256,
    )
    baseline_v3_indices = _index_list(
        payload.get("v3_proposal_indices"),
        name="V6 v3 proposal indices",
    )
    v7_v3_indices = _index_list(
        document.get("v3_proposal_indices"),
        name="V7 v3 proposal indices",
    )
    if (
        document.get("baseline_v6_receipt_sha256") != baseline_receipt
        or document.get("pre_coordinates_sha256")
        != payload.get("pre_coordinates_sha256")
        or document.get("baseline_coordinates_sha256")
        != payload.get("post_coordinates_sha256")
        or v7_v3_indices != baseline_v3_indices
        or document.get("original_pose_valid")
        is not payload.get("original_pose_valid")
    ):
        raise StandaloneDockCliError("V7/V6 refinement cross-binding mismatch")
    _require_nonempty_text(document.get("lane"), name="V7 refinement lane")
    _require_nonempty_text(
        document.get("selection_reason"),
        name="V7 refinement selection reason",
    )
    _require_nonempty_text(
        document.get("generic_penalty_scope"),
        name="V7 generic penalty scope",
    )
    _require_nonempty_text(
        document.get("baseline_v6_penalty_scope"),
        name="V7 baseline penalty scope",
    )
    _require_nonempty_text(
        document.get("torsion_evaluation_skip_reason"),
        name="V7 torsion skip reason",
    )
    _index_list(
        document.get("rotatable_child_atom_indices"),
        name="V7 rotatable child atom indices",
    )
    binary_values = {
        field: _binary64(document.get(field), name=f"V7 refinement {field}")
        for field in _V7_SCALAR_BINARY64_FIELDS
    }
    for field in _V7_VECTOR_BINARY64_FIELDS:
        _binary64_vector3(document.get(field), name=f"V7 refinement {field}")
    for field in _V7_INTEGER_FIELDS:
        _require_exact_int(document.get(field), name=f"V7 refinement {field}")
    for field in _V7_BOOLEAN_FIELDS:
        _require_exact_bool(document.get(field), name=f"V7 refinement {field}")
    evaluated_moves = _torsion_moves(
        document.get("evaluated_torsion_moves"),
        name="V7 evaluated torsion moves",
    )
    accepted_moves = _torsion_moves(
        document.get("accepted_torsion_moves"),
        name="V7 accepted torsion moves",
    )
    evaluated_torsion_path = sum(
        abs(
            _binary64(
                move["delta_radians_binary64_hex"],
                name="V7 evaluated torsion move delta",
            )
        )
        for move in evaluated_moves
    )
    accepted_torsion_path = sum(
        abs(
            _binary64(
                move["delta_radians_binary64_hex"],
                name="V7 accepted torsion move delta",
            )
        )
        for move in accepted_moves
    )
    if (
        document.get("posebusters_or_rmsd_used_for_selection") is not False
        or document.get("ranking_score_reused_as_physical_energy") is not False
        or document.get("scientifically_validated") is not False
    ):
        raise StandaloneDockCliError("V7 refinement receipt asserts forbidden semantics")
    if (
        document.get("accepted_rotation_steps")
        != document.get("accepted_rigid_rotation_steps")
        + document.get("accepted_torsion_steps")
        or document.get("accepted_steps")
        != document.get("accepted_translation_steps")
        + document.get("accepted_rotation_steps")
        or document.get("accepted_rotation_steps_include_torsion")
        is not True
        or document.get("evaluated_torsion_steps") != len(evaluated_moves)
        or document.get("accepted_torsion_steps") != len(accepted_moves)
        or document.get("torsion_variant_available") is not bool(evaluated_moves)
        or document.get("torsion_selected")
        and accepted_moves != evaluated_moves
        or not document.get("torsion_selected")
        and accepted_moves
        or document.get("torsion_selected")
        and not document.get("torsion_variant_available")
        or document.get("torsion_variant_available")
        and not document.get("torsion_evaluated")
        or document.get("objective_evaluation_count")
        != document.get("fixed_objective_evaluation_count")
        + document.get("torsion_trial_objective_evaluation_count")
        or document.get("accepted_translation_steps")
        != payload.get("accepted_translation_steps")
        or document.get("accepted_rigid_rotation_steps")
        != payload.get("accepted_rotation_steps")
        or document.get("total_translation_binary64_hex")
        != payload.get("total_translation_binary64_hex")
        or document.get("total_rotation_vector_binary64_hex")
        != payload.get("total_rotation_vector_binary64_hex")
        or document.get("line_search_evaluation_count")
        != payload.get("line_search_evaluation_count")
        + document.get("torsion_trial_objective_evaluation_count")
        or document.get("fallback_direction_step_count")
        != payload.get("fallback_direction_step_count")
        or document.get("fixed_objective_evaluation_count") != 2
        or document.get("torsion_evaluated")
        is not (document.get("torsion_evaluation_skip_reason") == "none")
        or not math.isclose(
            binary_values[
                "evaluated_total_torsion_path_radians_binary64_hex"
            ],
            evaluated_torsion_path,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        or not math.isclose(
            binary_values["total_torsion_path_radians_binary64_hex"],
            accepted_torsion_path,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        or binary_values["initial_penalty_binary64_hex"]
        != binary_values["initial_combined_penalty_binary64_hex"]
        or binary_values["final_penalty_binary64_hex"]
        != binary_values["final_combined_penalty_binary64_hex"]
        or binary_values[
            "minimum_selected_final_receptor_penalty_binary64_hex"
        ]
        >= binary_values[
            "maximum_selected_final_receptor_penalty_binary64_hex"
        ]
        or document.get("torsion_selected")
        is not (
            bool(evaluated_moves)
            and binary_values[
                "minimum_selected_final_receptor_penalty_binary64_hex"
            ]
            <= binary_values["optimized_receptor_penalty_binary64_hex"]
            < binary_values[
                "maximum_selected_final_receptor_penalty_binary64_hex"
            ]
        )
        or document.get("source_lane_retained") is not True
    ):
        raise StandaloneDockCliError("V7 refinement receipt counters are inconsistent")
    if document.get("torsion_selected"):
        if (
            document.get("lane") != "torsion_contact_v7_rescue"
            or document.get("selection_reason")
            != "final_receptor_penalty_window_selected"
            or document.get("post_coordinates_sha256")
            == document.get("baseline_coordinates_sha256")
        ):
            raise StandaloneDockCliError("V7 selected torsion state is inconsistent")
        selected_prefix = "optimized"
    else:
        expected_reason = (
            "v6_retained_outside_final_receptor_penalty_window"
            if evaluated_moves
            else "v6_baseline_retained_no_torsion_objective_reduction"
        )
        if (
            document.get("lane") != "rigid_v6_retained"
            or document.get("selection_reason") != expected_reason
            or document.get("post_coordinates_sha256")
            != document.get("baseline_coordinates_sha256")
        ):
            raise StandaloneDockCliError("V7 retained torsion state is inconsistent")
        selected_prefix = "baseline_v6"
    for objective in ("receptor", "internal", "combined"):
        if (
            document.get(f"final_{objective}_penalty_binary64_hex")
            != document.get(f"{selected_prefix}_{objective}_penalty_binary64_hex")
        ):
            raise StandaloneDockCliError("V7 final objective selection is inconsistent")
    projection = dict(document)
    projection.pop("receipt_sha256")
    _require_hash(document, "receipt_sha256", projection)
    return v7_v3_indices


def _verify_candidate(
    document: Mapping[str, object],
    *,
    proposal_index: int,
    authority_input_receipt_sha256: str,
) -> tuple[str, str, float | None, bool, tuple[int, ...] | None]:
    _require_exact_keys(document, _CANDIDATE_KEYS, name="pipeline candidate")
    if document.get("schema_id") != PIPELINE_CANDIDATE_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline candidate schema is unsupported")
    observed_proposal_index = _require_exact_int(
        document.get("proposal_index"),
        name="pipeline candidate proposal_index",
    )
    if observed_proposal_index != proposal_index:
        raise StandaloneDockCliError("pipeline candidate indices are incomplete")
    candidate_id = document.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise StandaloneDockCliError("pipeline candidate identity is invalid")
    for field in (
        "search_row_sha256",
        "source_proposal_fingerprint_sha256",
    ):
        _require_digest(document.get(field), name=f"candidate {field}")
    if (
        document.get("geometric_admission_status")
        != "not_enabled_in_current_v7_baseline"
        or document.get("candidate_removed_from_denominator") is not False
        or document.get("baseline_disagreement") != "not_evaluated"
        or document.get("claim_safe") is not False
        or document.get("canonical_recorder_factory_sealed") is not True
        or document.get("construction_proof_scope")
        != _SYNTHETIC_D0_CONSTRUCTION_PROOF_SCOPE
        or type(document.get("selection_eligible")) is not bool
    ):
        raise StandaloneDockCliError("pipeline candidate fixed semantics are invalid")
    status = document.get("status")
    if status not in {"success", "failure"}:
        raise StandaloneDockCliError("pipeline candidate status is unsupported")
    if status == "success":
        _require_digest(
            document.get("result_proposal_fingerprint_sha256"),
            name="candidate result_proposal_fingerprint_sha256",
        )
    elif document.get("result_proposal_fingerprint_sha256") != "":
        raise StandaloneDockCliError(
            "failed candidate result proposal fingerprint must be empty"
        )
    error_code = document.get("error_code")
    if not isinstance(error_code, str):
        raise StandaloneDockCliError("pipeline candidate error code is invalid")
    score_value = None
    score = document.get("score_binary64_hex")
    if score is not None:
        score_value = _binary64(score, name="candidate score")
    pose = document.get("pose_validity")
    terms = document.get("scorer_terms")
    refinement = document.get("refinement_receipt")
    refinement_v3_indices: tuple[int, ...] | None = None
    if status == "success":
        if error_code or score_value is None:
            raise StandaloneDockCliError("successful candidate status fields are inconsistent")
        if not isinstance(pose, dict) or not isinstance(terms, dict) or not isinstance(refinement, dict):
            raise StandaloneDockCliError("successful candidate evidence is incomplete")
        normalized_pose = _verify_pose_validity(pose)
        if normalized_pose.get("complete") is not True:
            raise StandaloneDockCliError("successful candidate validity is incomplete")
        terms_score = _verify_scorer_terms(
            terms,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            result_proposal_fingerprint_sha256=str(
                document["result_proposal_fingerprint_sha256"]
            ),
            ligand_atom_count=int(normalized_pose["measurements"]["atom_count"]),
        )
        if score_value.hex() != terms_score.hex():
            raise StandaloneDockCliError("candidate score/term cross-binding mismatch")
        refinement_v3_indices = _verify_refinement_receipt(
            refinement,
            source_proposal_fingerprint_sha256=str(
                document["source_proposal_fingerprint_sha256"]
            ),
        )
        if document.get("selection_eligible") is not normalized_pose.get("valid"):
            raise StandaloneDockCliError("candidate selection eligibility is inconsistent")
    else:
        if (
            not error_code
            or score is not None
            or pose is not None
            or terms is not None
            or document.get("selection_eligible") is not False
        ):
            raise StandaloneDockCliError("failed candidate evidence is inconsistent")
        if refinement is not None:
            if not isinstance(refinement, dict):
                raise StandaloneDockCliError("failed candidate refinement evidence is invalid")
            refinement_v3_indices = _verify_refinement_receipt(
                refinement,
                source_proposal_fingerprint_sha256=str(
                    document["source_proposal_fingerprint_sha256"]
                ),
            )
    projection = dict(document)
    projection.pop("receipt_sha256")
    _require_hash(document, "receipt_sha256", projection)
    return (
        candidate_id,
        str(status),
        score_value,
        bool(document["selection_eligible"]),
        refinement_v3_indices,
    )


def verify_pipeline_result(document: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(document, _RESULT_KEYS, name="pipeline result")
    if document.get("schema_id") != PIPELINE_RESULT_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline result schema is unsupported")
    result_projection = dict(document)
    result_projection.pop("request")
    result_projection.pop("profile")
    result_projection.pop("receipt_sha256")
    _require_hash(document, "receipt_sha256", result_projection)
    request = document.get("request")
    profile = document.get("profile")
    budget = document.get("budget")
    proposal_plan = document.get("proposal_plan")
    candidates = document.get("candidate_evidence")
    blockers = document.get("blockers")
    if not isinstance(request, dict) or not isinstance(profile, dict):
        raise StandaloneDockCliError("pipeline request/profile evidence is missing")
    if not isinstance(budget, dict) or not isinstance(proposal_plan, dict):
        raise StandaloneDockCliError("pipeline budget/proposal evidence is missing")
    if not isinstance(candidates, list) or not isinstance(blockers, list):
        raise StandaloneDockCliError("pipeline candidate/blocker evidence is missing")
    normalized_profile = _verify_profile(profile)
    profile_receipt = str(normalized_profile["receipt_sha256"])
    normalized_request = _verify_request(
        request,
        profile_receipt_sha256=profile_receipt,
    )
    if (
        document.get("request_sha256") != normalized_request["request_sha256"]
        or document.get("profile_receipt_sha256") != profile_receipt
    ):
        raise StandaloneDockCliError("pipeline top-level request/profile cross-binding mismatch")
    admission = repository_synthetic_d0_fixture_admission()
    admission_document = admission.to_dict()
    if (
        admission_document.get("schema_id")
        != SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID
        or document.get("synthetic_d0_fixture_id") != SYNTHETIC_D0_FIXTURE_ID
        or document.get("synthetic_d0_fixture_id") != admission.fixture_id
        or document.get("synthetic_d0_fixture_manifest_sha256")
        != SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
        or document.get("synthetic_d0_fixture_manifest_sha256")
        != admission.manifest_sha256
        or document.get("synthetic_d0_fixture_admission_receipt_sha256")
        != admission.receipt_sha256
        or document.get("synthetic_only_acknowledgment")
        != SYNTHETIC_ONLY_ACKNOWLEDGMENT
        or document.get("caller_acknowledged_synthetic_fixture_only") is not True
        or document.get("synthetic_fixture_identity_independently_verified")
        is not True
    ):
        raise StandaloneDockCliError(
            "pipeline synthetic D0 manifest/admission binding is invalid"
        )
    candidate_count = _require_exact_int(
        document.get("candidate_count"),
        name="pipeline candidate_count",
        minimum=1,
    )
    if (
        candidate_count != 64
        or candidate_count != len(candidates)
        or candidate_count != normalized_profile["candidate_count"]
        or normalized_profile.get("top_k") != 5
        or normalized_profile.get("failure_denominator_required") != 64
    ):
        raise StandaloneDockCliError("pipeline candidate denominator mismatch")
    for field in (
        "pipeline_source_sha256",
        "scorer_source_sha256",
        "refiner_source_sha256",
        "prepared_input_receipt_sha256",
        "conformer_receipt_sha256",
        "authority_input_receipt_sha256",
        "proposal_plan_receipt_sha256",
        "guided_placement_receipt_sha256",
        "authenticated_search_receipt_sha256",
        "scorer_v1_result_receipt_sha256",
        "budget_sha256",
    ):
        _require_digest(document.get(field), name=f"pipeline {field}")
    expected_source_hashes = {
        "pipeline_source_sha256": _installed_docking_source_sha256(
            "pipeline.py"
        ),
        "scorer_source_sha256": _installed_docking_source_sha256(
            "scorer_v1.py"
        ),
        "refiner_source_sha256": _installed_docking_source_sha256(
            "torsion_contact_refinement.py"
        ),
    }
    if any(
        document.get(field) != expected
        for field, expected in expected_source_hashes.items()
    ):
        raise StandaloneDockCliError(
            "pipeline installed source identities are cross-wired"
        )
    if (
        document.get("pipeline_source_binding_mode")
        != "observed_installed_package_resource_after_import_not_preimport_attested"
        or document.get("scorer_refiner_source_binding_status")
        != "observed_canonical_package_resources"
        or document.get("component_binding_mode")
        != SEALED_CANONICAL_COMPONENT_BINDING
        or document.get("canonical_components_sealed") is not True
        or document.get("arbitrary_dependency_injection_used") is not False
        or document.get("component_chain_product_qualified") is not False
    ):
        raise StandaloneDockCliError("pipeline canonical component binding is invalid")
    component_ids = document.get("component_ids")
    if (
        not isinstance(component_ids, dict)
        or set(component_ids) != _COMPONENT_ROLES
        or any(not isinstance(value, str) or not value for value in component_ids.values())
        or component_ids != _DEFAULT_COMPONENT_IDS
    ):
        raise StandaloneDockCliError("pipeline component identities are not canonical")
    derived_budget_sha256 = _verify_budget(
        budget,
        profile=normalized_profile,
        request=normalized_request,
    )
    if document.get("budget_sha256") != derived_budget_sha256:
        raise StandaloneDockCliError("pipeline budget receipt is cross-wired")
    proposal_receipt, proposal_v3_indices = _verify_proposal_plan(
        proposal_plan,
        request_sha256=str(normalized_request["request_sha256"]),
        authority_input_receipt_sha256=str(
            document["authority_input_receipt_sha256"]
        ),
        budget=budget,
        budget_sha256=derived_budget_sha256,
        proposal_component_id=str(component_ids["proposal_generator"]),
        candidate_count=candidate_count,
    )
    if document.get("proposal_plan_receipt_sha256") != proposal_receipt:
        raise StandaloneDockCliError("pipeline proposal plan receipt is cross-wired")
    candidate_rows: list[
        tuple[str, str, float | None, bool, tuple[int, ...] | None]
    ] = []
    authority_receipt = str(document["authority_input_receipt_sha256"])
    for index, row in enumerate(candidates):
        if not isinstance(row, dict):
            raise StandaloneDockCliError("pipeline candidate evidence is not an object")
        candidate_rows.append(
            _verify_candidate(
                row,
                proposal_index=index,
                authority_input_receipt_sha256=authority_receipt,
            )
        )
    candidate_ids = [row[0] for row in candidate_rows]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise StandaloneDockCliError("pipeline candidate identities are not unique")
    if any(
        refinement_indices is not None
        and refinement_indices != proposal_v3_indices
        for _, _, _, _, refinement_indices in candidate_rows
    ):
        raise StandaloneDockCliError(
            "pipeline proposal allocation/refinement receipt mismatch"
        )
    derived_success_count = sum(
        status == "success" for _, status, _, _, _ in candidate_rows
    )
    derived_failure_count = candidate_count - derived_success_count
    success_count = _require_exact_int(
        document.get("success_count"),
        name="pipeline success_count",
    )
    failure_count = _require_exact_int(
        document.get("failure_count"),
        name="pipeline failure_count",
    )
    if success_count != derived_success_count or failure_count != derived_failure_count:
        raise StandaloneDockCliError("pipeline success/failure counts are inconsistent")
    top_indices = document.get("top_proposal_indices")
    if (
        not isinstance(top_indices, list)
        or any(type(index) is not int or not 0 <= index < candidate_count for index in top_indices)
        or len(top_indices) != len(set(top_indices))
        or len(top_indices) > int(normalized_profile["top_k"])
    ):
        raise StandaloneDockCliError("pipeline Top-K indices are invalid")
    top_order: list[tuple[float, int, str]] = []
    for index in top_indices:
        candidate_id, status, score, eligible, _ = candidate_rows[index]
        if status != "success" or score is None or not eligible:
            raise StandaloneDockCliError("pipeline Top-K includes an ineligible candidate")
        top_order.append((score, index, candidate_id))
    if top_order != sorted(top_order):
        raise StandaloneDockCliError("pipeline Top-K stable score order is inconsistent")
    expected_top_indices = [
        index
        for _, index, _ in sorted(
            (score, index, candidate_id)
            for index, (candidate_id, status, score, eligible, _) in enumerate(
                candidate_rows
            )
            if status == "success" and score is not None and eligible
        )[: int(normalized_profile["top_k"])]
    ]
    if top_indices != expected_top_indices:
        raise StandaloneDockCliError("pipeline Top-K does not match the complete stable rank")
    derived_abstained = len(top_indices) < int(normalized_profile["top_k"])
    if document.get("abstained") is not derived_abstained:
        raise StandaloneDockCliError("pipeline abstention flag is inconsistent")
    if document.get("failure_denominator_preserved") is not True:
        raise StandaloneDockCliError("pipeline failure denominator is not preserved")
    if (
        document.get("chemistry_inference_performed") is not False
        or document.get("pocket_prediction_performed") is not False
        or document.get("network_fetch_performed") is not False
        or document.get("external_reservation_requested") is not False
        or document.get("external_reservation_authorized") is not False
        or document.get("side_effect_evidence_status")
        != "verified_absent_by_sealed_canonical_components"
        or document.get("test_only") is not True
    ):
        raise StandaloneDockCliError("pipeline fixed execution semantics are invalid")
    if (
        document.get("evidence_record_capability_consumed") is not True
        or document.get("evidence_record_capability_scope")
        != _SYNTHETIC_D0_CAPABILITY_SCOPE
        or document.get("canonical_evidence_recorder_factory_sealed") is not True
        or document.get("construction_proof_scope")
        != _SYNTHETIC_D0_CONSTRUCTION_PROOF_SCOPE
    ):
        raise StandaloneDockCliError(
            "pipeline serialized recorder/capability scope is invalid"
        )
    if (
        any(not isinstance(value, str) or not value for value in blockers)
        or len(blockers) != len(set(blockers))
    ):
        raise StandaloneDockCliError("pipeline blockers are invalid")
    if blockers != list(PIPELINE_CLAIM_BLOCKERS):
        raise StandaloneDockCliError("pipeline blockers are not the canonical ordered set")
    if any(value not in blockers for value in EXTERNAL_AUTHORITY_BLOCKERS):
        raise StandaloneDockCliError("pipeline external blockers are incomplete")
    required_false = (
        "historical_execution_authorized",
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    )
    if any(document.get(field) is not False for field in required_false):
        raise StandaloneDockCliError("pipeline result asserts forbidden authority")
    projection: dict[str, object] = {
        "schema_id": PIPELINE_VERIFICATION_SCHEMA_ID,
        "status": "verified_structural_consistency_only",
        "verification_scope": (
            "available_serialized_structure_only_no_opaque_upstream_content"
        ),
        "pipeline_result_receipt_sha256": document["receipt_sha256"],
        "request_sha256": normalized_request["request_sha256"],
        "profile_receipt_sha256": profile_receipt,
        "profile_id": normalized_profile["profile_id"],
        "synthetic_d0_fixture_id": admission.fixture_id,
        "synthetic_d0_fixture_manifest_sha256": admission.manifest_sha256,
        "synthetic_d0_fixture_admission_receipt_sha256": (
            admission.receipt_sha256
        ),
        "component_binding_mode": SEALED_CANONICAL_COMPONENT_BINDING,
        "candidate_count": candidate_count,
        "success_count": derived_success_count,
        "failure_count": derived_failure_count,
        "top_proposal_indices": list(top_indices),
        "abstained": derived_abstained,
        "blockers": list(blockers),
        "external_authority_blocker_count": len(EXTERNAL_AUTHORITY_BLOCKERS),
        "structural_consistency_verified": True,
        "self_hash_consistency_verified": True,
        "available_structural_cross_bindings_verified": True,
        "available_derived_semantics_verified": True,
        "verified_structural_items": [
            "exact_serialized_schema_keys",
            "embedded_structural_self_hashes",
            "available_admission_request_profile_budget_plan_bindings",
            "available_candidate_score_validity_refinement_bindings",
            "fixed64_failure_denominator_and_stable_top_k_at_most5",
            "sealed_component_and_false_authority_declarations",
        ],
        "opaque_upstream_receipt_content_verified": False,
        "cryptographic_signature_verified": False,
        "content_authenticity_verified": False,
        "source_preimport_attestation_verified": False,
        "external_authority_verified": False,
        "execution_authority_granted": False,
        "structural_consistency_valid": True,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256_document(projection)}


def report_pipeline_result(document: Mapping[str, object]) -> dict[str, object]:
    verification = verify_pipeline_result(document)
    projection: dict[str, object] = {
        "schema_id": PIPELINE_REPORT_SCHEMA_ID,
        "status": "structural_report_only",
        "verification_scope": verification["verification_scope"],
        "pipeline_result_receipt_sha256": verification[
            "pipeline_result_receipt_sha256"
        ],
        "verification_receipt_sha256": verification["receipt_sha256"],
        "profile_id": verification["profile_id"],
        "candidate_count": verification["candidate_count"],
        "success_count": verification["success_count"],
        "failure_count": verification["failure_count"],
        "top_proposal_indices": verification["top_proposal_indices"],
        "abstained": verification["abstained"],
        "blockers": verification["blockers"],
        "structural_consistency_verified": True,
        "cryptographic_signature_verified": False,
        "content_authenticity_verified": False,
        "source_preimport_attestation_verified": False,
        "external_authority_verified": False,
        "execution_authority_granted": False,
        "stage0_admission_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256_document(projection)}


class _CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StandaloneDockCliError(f"invalid command line: {message}")


def _parser() -> argparse.ArgumentParser:
    parser = _CanonicalArgumentParser(
        prog="betelgeuze-dock",
        description="Claim-blocked standalone CPU docking over canonical prepared inputs.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    receptor = commands.add_parser("prepare-receptor")
    receptor.add_argument("--input", type=Path, required=True)
    receptor.add_argument("--output", type=Path, required=True)
    receptor.add_argument("--overwrite", action="store_true")

    ligands = commands.add_parser("prepare-ligands")
    ligands.add_argument("--input", type=Path, action="append", required=True)
    ligands.add_argument("--output-dir", type=Path, required=True)

    pocket = commands.add_parser("define-pocket")
    source = pocket.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference-ligand", type=Path)
    source.add_argument("--center", type=float, nargs=3)
    source.add_argument("--synthetic-d0-fixture", action="store_true")
    pocket.add_argument("--radius", type=float)
    pocket.add_argument("--source-artifact", type=Path)
    pocket.add_argument("--coordinate-frame-id", required=True)
    pocket.add_argument("--model-index", type=int)
    pocket.add_argument("--padding-angstrom", type=float)
    pocket.add_argument("--minimum-radius-angstrom", type=float)
    pocket.add_argument("--output", type=Path, required=True)
    pocket.add_argument("--overwrite", action="store_true")

    docking = commands.add_parser("dock")
    docking.add_argument("--receptor", type=Path, required=True)
    docking.add_argument("--ligand", type=Path, required=True)
    docking.add_argument("--pocket", type=Path, required=True)
    docking.add_argument("--seed", type=int, required=True)
    docking.add_argument("--test-only-synthetic", action="store_true")
    docking.add_argument("--output", type=Path, required=True)
    docking.add_argument("--overwrite", action="store_true")

    verify = commands.add_parser("verify")
    verify.add_argument("--result", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--overwrite", action="store_true")

    report = commands.add_parser("report")
    report.add_argument("--result", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        if arguments.command == "prepare-receptor":
            prepare_receptor(arguments.input, arguments.output, overwrite=arguments.overwrite)
        elif arguments.command == "prepare-ligands":
            prepare_ligands(
                arguments.input,
                arguments.output_dir,
            )
        elif arguments.command == "define-pocket":
            document = define_pocket(arguments)
            source_paths = (
                ()
                if arguments.synthetic_d0_fixture
                else (
                    (arguments.reference_ligand,)
                    if arguments.reference_ligand is not None
                    else (arguments.source_artifact,)
                )
            )
            _write_output(
                document,
                arguments.output,
                overwrite=arguments.overwrite,
                input_paths=source_paths,
            )
        elif arguments.command == "dock":
            document = dock(
                receptor_path=arguments.receptor,
                ligand_path=arguments.ligand,
                pocket_path=arguments.pocket,
                seed=arguments.seed,
                synthetic_acknowledged=arguments.test_only_synthetic,
            )
            _write_output(
                document,
                arguments.output,
                overwrite=arguments.overwrite,
                input_paths=(
                    arguments.receptor,
                    arguments.ligand,
                    arguments.pocket,
                ),
            )
        elif arguments.command in {"verify", "report"}:
            result = _load_canonical_json(
                arguments.result,
                name="pipeline result",
                maximum=MAX_CLI_INPUT_BYTES,
            )
            document = (
                verify_pipeline_result(result)
                if arguments.command == "verify"
                else report_pipeline_result(result)
            )
            _write_output(
                document,
                arguments.output,
                overwrite=arguments.overwrite,
                input_paths=(arguments.result,),
            )
        else:  # pragma: no cover - argparse owns command admission.
            raise StandaloneDockCliError("unsupported command")
        return 0
    except Exception as exc:
        sys.stderr.buffer.write(_canonical_bytes(_failure_document(exc)) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXPLICIT_POCKET_METHOD_ID",
    "EXPLICIT_POCKET_METHOD_VERSION",
    "LIGAND_MANIFEST_SCHEMA_ID",
    "PIPELINE_REPORT_SCHEMA_ID",
    "PIPELINE_VERIFICATION_SCHEMA_ID",
    "STANDALONE_CLI_ID",
    "StandaloneDockCliError",
    "define_explicit_pocket",
    "dock",
    "main",
    "prepare_ligands",
    "prepare_receptor",
    "report_pipeline_result",
    "verify_pipeline_result",
]
