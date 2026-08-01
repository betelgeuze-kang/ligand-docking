from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
from types import SimpleNamespace

import pytest

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
)
import tools.build_engine_v2_source_paired_failure_atlas as atlas_builder


_TOP1_INDICES = {
    "5SD5_HWI": 41,
    "5SIS_JSM": 12,
    "6M2B_EZO": 0,
    "6T88_MWQ": 51,
    "6TW5_9M2": 5,
    "6TW7_NZB": 44,
    "6VTA_AKN": 11,
    "6WTN_RXT": 14,
}
_ROTOR_CASE_IDS = frozenset(
    {
        "5SD5_HWI",
        "5SIS_JSM",
        "6T88_MWQ",
        "6TW5_9M2",
        "6TW7_NZB",
        "6VTA_AKN",
        "6WTN_RXT",
    }
)
_RESCUE_PAIRS = ((8, 24), (13, 37), (18, 50), (23, 63))
_VALID_INDICES = {
    "6T88_MWQ": frozenset({5, 6, 7, 51}),
    "6VTA_AKN": frozenset({11, 20}),
    "6WTN_RXT": frozenset({14}),
}
_NATIVE_INDICES = {"6T88_MWQ": frozenset({5, 13, 37, 51})}
_ELIGIBLE_INDICES = {
    "5SIS_JSM": frozenset({12, 20}),
    "6M2B_EZO": frozenset({0}),
    "6T88_MWQ": frozenset({*range(15), 20, 21, 51}),
    "6TW7_NZB": frozenset({44, 45}),
    "6VTA_AKN": frozenset({11, 20, 21, 22}),
    "6WTN_RXT": frozenset({14, 20, 21, 22}),
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


def _digest(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode("ascii")).hexdigest()


def _seal(
    payload: dict[str, object], field: str = "receipt_sha256"
) -> dict[str, object]:
    payload[field] = _sha256(payload)
    return payload


_EXECUTION_POLICY = {
    "scorer_backend": "python_reference",
    "scorer_thread_count": 1,
}


def _case_artifacts(case_id: str) -> dict[str, str]:
    return {
        filename: _digest(case_id, filename)
        for filename in (
            "protein.pdb",
            "ligands.sdf",
            "ligand.sdf",
            "ligand_start_conf.sdf",
        )
    }


def _case_inputs(case_id: str) -> dict[str, str]:
    artifacts = _case_artifacts(case_id)
    return {
        "receptor": artifacts["protein.pdb"],
        "reference": artifacts["ligands.sdf"],
        "native": artifacts["ligand.sdf"],
        "seed": artifacts["ligand_start_conf.sdf"],
    }


def _execution_command(case_id: str) -> list[str]:
    return ["synthetic-historical-only", "--case-id", case_id]


def _execution_policy_tokens() -> list[str]:
    return [
        f"{key}={json.dumps(value, allow_nan=False, separators=(',', ':'))}"
        for key, value in sorted(_EXECUTION_POLICY.items())
    ]


def _strict_backend_receipt() -> dict[str, object]:
    return _seal(
        {
            "schema_id": "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0",
            "backend": "python_reference",
            "backend_version": "1.0.0",
            "implementation_source_sha256": "e" * 64,
            "options_fingerprint_sha256": "f" * 64,
            "extension_sha256": "",
            "cargo_lock_sha256": "",
            "rustc_version": "",
            "target_triple": "",
            "build_flags": [],
            "implicit_fallback_allowed": False,
        }
    )


def _zero_score_terms() -> dict[str, str]:
    return {
        name: (0.0).hex()
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
            "total_score",
        )
    }


def _strict_valid_result(case_id: str) -> dict[str, object]:
    candidates = tuple(
        (
            PublicRedockingEngineV2CandidateDiagnostic(
                proposal_index=index,
                status="success",
                proposal_mode="uniform_fallback",
                proposal_fingerprint_sha256=f"{index + 1:064x}",
                coordinate_fingerprint_sha256=f"{index + 193:064x}",
                score=float(index),
                rmsd_angstrom=float(index + 1),
                geometric_valid=True,
                chemical_valid=True,
                pose_artifact_sha256=f"{index + 65:064x}",
                score_terms_receipt_sha256=f"{index + 129:064x}",
                hbond_count=1,
                selection_eligible=True,
                score_term_binary64_hex=_zero_score_terms(),
            )
            if index < 5
            else PublicRedockingEngineV2CandidateDiagnostic(
                proposal_index=index,
                status="failure",
                error_code="synthetic_candidate_failure",
            )
        )
        for index in range(64)
    )
    diagnostics = PublicRedockingEngineV2Diagnostics(
        preparation_status="success",
        scorer_backend_receipt=_strict_backend_receipt(),
        receptor_atom_count=1,
        ligand_atom_count=1,
        receptor_partial_charge_count=1,
        ligand_partial_charge_count=1,
        receptor_donor_count=1,
        receptor_acceptor_count=1,
        ligand_donor_count=1,
        ligand_acceptor_count=1,
        candidates=candidates,
    )
    inputs = _case_inputs(case_id)
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="success",
        runtime_seconds=0.0,
        receptor_artifact_sha256=inputs["receptor"],
        reference_artifact_sha256=inputs["reference"],
        native_artifact_sha256=inputs["native"],
        seed_artifact_sha256=inputs["seed"],
        execution_command=_execution_command(case_id),
        execution_policy=_execution_policy_tokens(),
        rmsd_angstroms=tuple(float(index + 1) for index in range(5)),
        geometric_valid=(True,) * 5,
        chemical_valid=(True,) * 5,
        pose_artifact_sha256s=tuple(f"{index + 65:064x}" for index in range(5)),
        engine_v2_diagnostics=diagnostics,
    ).to_dict()


def _pairs(case_id: str) -> list[dict[str, int]]:
    if case_id not in _ROTOR_CASE_IDS:
        return []
    return [
        {"target_proposal_index": target, "parent_proposal_index": parent}
        for target, parent in _RESCUE_PAIRS
    ]


def _refinement_payload(case_id: str, index: int) -> dict[str, object]:
    if case_id not in _ROTOR_CASE_IDS or index not in {row[0] for row in _RESCUE_PAIRS}:
        return {}
    unreachable = case_id == "6VTA_AKN" and index == 23
    no_variant = case_id == "5SD5_HWI" and index == 8
    parent = dict(_RESCUE_PAIRS)[index]
    payload: dict[str, object] = {
        field: None
        for field in atlas_builder._SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS
        if field != "receipt_sha256"
    }
    payload.update(
        {
            "schema_id": "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0",
            "development_only": True,
            "claim_safe": False,
            "fresh_execution_authorized": False,
            "scientifically_validated": False,
            "stage0_eligible": False,
            "source_paired_parent_proposal_index": parent,
            "source_paired_torsion_rescue_pairs": _pairs(case_id),
            "pre_coordinates_sha256": _digest(case_id, index, "pre"),
            "post_coordinates_sha256": _digest(case_id, index, "post"),
            "initial_receptor_penalty_binary64_hex": (8.0).hex(),
            "baseline_v6_receptor_penalty_binary64_hex": (6.0).hex(),
            "optimized_receptor_penalty_binary64_hex": (5.0).hex(),
            "final_receptor_penalty_binary64_hex": (6.0).hex(),
            "initial_internal_penalty_binary64_hex": (2.0).hex(),
            "baseline_v6_internal_penalty_binary64_hex": (1.5).hex(),
            "optimized_internal_penalty_binary64_hex": (1.0).hex(),
            "final_internal_penalty_binary64_hex": (1.5).hex(),
            "torsion_evaluated": not unreachable,
            "torsion_variant_available": not (unreachable or no_variant),
            "torsion_selected": False,
            "evaluated_torsion_steps": 0 if unreachable else 4,
            "accepted_torsion_steps": 0,
            "evaluated_total_torsion_path_radians_binary64_hex": (
                0.0 if unreachable else 0.5
            ).hex(),
            "total_torsion_path_radians_binary64_hex": (0.0).hex(),
            "minimum_selected_final_receptor_penalty_binary64_hex": (2.0).hex(),
            "maximum_selected_final_receptor_penalty_binary64_hex": (4.0).hex(),
            "selection_window_reachable_from_baseline_v6_receptor_penalty": (
                not unreachable
            ),
            "torsion_evaluation_skip_reason": (
                "selection_window_unreachable_under_receptor_nonincrease"
                if unreachable
                else "none"
            ),
            "selection_reason": "v6_retained_outside_final_receptor_penalty_window",
        }
    )
    return _seal(payload)


def _candidate(case_id: str, index: int, *, lane: str) -> dict[str, object]:
    rotor_case = case_id in _ROTOR_CASE_IDS
    rescue_parent_by_target = dict(_RESCUE_PAIRS) if rotor_case else {}
    rescue_target = lane == "rescue" and index in rescue_parent_by_target
    proposal_mode = (
        PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
        if rescue_target
        else (
            "uniform_v3_rigid_ensemble"
            if index in rescue_parent_by_target
            else "uniform_fallback"
        )
    )
    coordinate_index = rescue_parent_by_target[index] if rescue_target else index
    coordinate_sha256 = _digest(case_id, coordinate_index, "coordinate")
    top1 = index == _TOP1_INDICES[case_id]
    score = 0.0 if top1 else float(index + 1)
    native = index in _NATIVE_INDICES.get(case_id, frozenset())
    rmsd = 1.5 + index / 1000.0 if native else 3.0 + index / 100.0
    valid = index in _VALID_INDICES.get(case_id, frozenset())
    failed_checks: list[str] = [] if valid else ["minimum_distance_to_protein"]
    if case_id == "5SD5_HWI" and top1:
        failed_checks = [
            "internal_energy",
            "minimum_distance_to_protein",
            "volume_overlap_with_protein",
        ]
    eligible = index in _ELIGIBLE_INDICES.get(case_id, frozenset())
    if lane == "rescue" and case_id == "6T88_MWQ" and index == 13:
        eligible = False
    payload = _refinement_payload(case_id, index) if lane == "rescue" else {}
    candidate: dict[str, object] = {
        "schema_id": (
            PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
            if lane == "baseline"
            else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID
        ),
        "proposal_index": index,
        "status": "success",
        "proposal_mode": proposal_mode,
        "proposal_fingerprint_sha256": _digest(case_id, index, lane, "proposal"),
        "coordinate_fingerprint_sha256": coordinate_sha256,
        "score": score,
        "rmsd_angstrom": rmsd,
        "geometric_valid": valid,
        "chemical_valid": "internal_energy" not in failed_checks,
        "selection_eligible": eligible,
        "pose_artifact_sha256": _digest(case_id, index, lane, "pose"),
        "score_terms_receipt_sha256": _digest(case_id, index, lane, "terms"),
        "posebusters_failed_check_ids": failed_checks,
        "refinement_receipt_payload": payload,
        "refinement_receipt_sha256": payload.get(
            "receipt_sha256", _digest(case_id, index, lane, "refinement")
        ),
        "refinement_total_translation_binary64_hex": (
            [(1.0).hex(), (0.0).hex(), (0.0).hex()] if payload else []
        ),
        "refinement_total_rotation_vector_binary64_hex": (
            [(0.0).hex(), (0.0).hex(), (0.0).hex()] if payload else []
        ),
        "ensemble_source_proposal_index": None,
    }
    if lane == "rescue":
        candidate["torsion_rescue_parent_proposal_index"] = (
            rescue_parent_by_target[index] if rescue_target else None
        )
    return candidate


def _result(case_id: str, *, lane: str) -> dict[str, object]:
    schema_id = (
        PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    inputs = _case_inputs(case_id)
    common: dict[str, object] = {
        "case_id": case_id,
        "engine_id": "engine_v2",
        "runtime_seconds": 0.0,
        "receptor_artifact_sha256": inputs["receptor"],
        "reference_artifact_sha256": inputs["reference"],
        "native_artifact_sha256": inputs["native"],
        "seed_artifact_sha256": inputs["seed"],
        "execution_command": _execution_command(case_id),
        "execution_policy": _execution_policy_tokens(),
    }
    if case_id == atlas_builder.EXPECTED_PREPARATION_FAILURE_CASE_ID:
        diagnostics: dict[str, object] = {
            "schema_id": schema_id,
            "preparation_status": "failure",
            "preparation_failure_code": "unsupported_large_ring_system",
            "candidates": [],
        }
        return {
            **common,
            "status": "failure",
            "failure_code": "engine_v2_input_unsupported",
            "rmsd_angstroms": [],
            "geometric_valid": [],
            "chemical_valid": [],
            "pose_artifact_sha256s": [],
            "engine_v2_diagnostics": diagnostics,
        }
    candidates = [_candidate(case_id, index, lane=lane) for index in range(64)]
    diagnostics = {
        "schema_id": schema_id,
        "preparation_status": "success",
        "preparation_failure_code": "",
        "candidate_budget": 64,
        "candidate_success_count": 64,
        "candidate_failure_count": 0,
        "candidates": candidates,
    }
    if lane == "rescue":
        diagnostics["source_paired_torsion_rescue_proposal_receipt"] = {
            "allocation": {
                "authority_rotor_count": 3 if case_id in _ROTOR_CASE_IDS else 0,
                "rescue_target_parent_pairs": _pairs(case_id),
            }
        }
    ranked = atlas_builder._ranked(candidates)[:5]
    return {
        **common,
        "status": "success",
        "failure_code": "",
        "rmsd_angstroms": [candidate["rmsd_angstrom"] for candidate in ranked],
        "geometric_valid": [candidate["geometric_valid"] for candidate in ranked],
        "chemical_valid": [candidate["chemical_valid"] for candidate in ranked],
        "pose_artifact_sha256s": [
            candidate["pose_artifact_sha256"] for candidate in ranked
        ],
        "engine_v2_diagnostics": diagnostics,
    }


def _results(lane: str) -> dict[str, dict[str, object]]:
    return {
        case_id: _result(case_id, lane=lane)
        for case_id in atlas_builder.EXPECTED_CASE_IDS
    }


def _lane_metrics(
    results: dict[str, dict[str, object]], lane: str
) -> dict[str, object]:
    metrics: dict[str, object] = atlas_builder._lane_counts(results, lane=lane)
    per_case: dict[str, object] = {}
    for case_id, result in results.items():
        diagnostics, candidates = atlas_builder._case_candidates(result, lane=lane)
        if not candidates:
            per_case[case_id] = {
                "candidate_success_count": 0,
                "exact_valid_candidate_count": 0,
                "selection_eligible_candidate_count": 0,
                "preparation_status": "failure",
                "preparation_failure_code": diagnostics["preparation_failure_code"],
                "proposal_oracle_recovery": None,
                "top1_recovery": None,
                "top5_recovery": None,
                "top1_proposal_index": None,
                "top1_valid": None,
                "top1_rmsd_angstrom_binary64_hex": None,
                "minimum_candidate_rmsd_angstrom_binary64_hex": None,
            }
            continue
        ranked = atlas_builder._ranked(candidates)
        exact_valid = [
            candidate
            for candidate in candidates
            if atlas_builder._posebusters_exact_valid(candidate)
        ]
        eligible = [
            candidate for candidate in candidates if candidate["selection_eligible"]
        ]
        per_case[case_id] = {
            "candidate_success_count": len(candidates),
            "exact_valid_candidate_count": len(exact_valid),
            "selection_eligible_candidate_count": len(eligible),
            "preparation_status": "success",
            "preparation_failure_code": "",
            "proposal_oracle_recovery": any(
                float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in candidates
            ),
            "top1_recovery": float(ranked[0]["rmsd_angstrom"]) <= 2.0,
            "top5_recovery": any(
                float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5]
            ),
            "top1_proposal_index": ranked[0]["proposal_index"],
            "top1_valid": atlas_builder._posebusters_exact_valid(ranked[0]),
            "top1_rmsd_angstrom_binary64_hex": float(ranked[0]["rmsd_angstrom"]).hex(),
            "minimum_candidate_rmsd_angstrom_binary64_hex": min(
                float(candidate["rmsd_angstrom"]) for candidate in candidates
            ).hex(),
        }
    metrics["per_case"] = per_case
    return metrics


def _ab_report(
    baseline: dict[str, dict[str, object]],
    rescue: dict[str, dict[str, object]],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": atlas_builder.AB_SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "source_commit_sha256": atlas_builder.EXPECTED_SOURCE_COMMIT_SHA256,
        "case_ids": list(atlas_builder.EXPECTED_CASE_IDS),
        "case_ids_sha256": atlas_builder.EXPECTED_CASE_IDS_SHA256,
        "paired_evidence_bound_by_this_report": True,
        "development_only": True,
        "claim_safe": False,
        "fresh_execution_authorized": False,
        "public_claim_eligible": False,
        "primary_claim_eligible": False,
        "product_promotion_eligible": False,
        "scientifically_validated": False,
        "stage0_eligible": False,
        "engine_identity": {
            "implementation_sha256": "1" * 64,
            "evaluation_pipeline_sha256": "2" * 64,
            "execution_environment_sha256": "3" * 64,
            "interaction_refiner_config_sha256": "4" * 64,
        },
        "acceptance": {
            "decision": atlas_builder.EXPECTED_DECISION,
            "rescue_vs_parent_coordinate_change_candidate_count": 0,
            "selection_eligibility_regression_case_ids": ["6T88_MWQ"],
        },
        "candidate_level_changes": {
            "baseline_to_rescue_coordinate_change_candidate_count": 28,
            "baseline_to_rescue_coordinate_change_case_ids": [
                "5SD5_HWI",
                "5SIS_JSM",
                "6T88_MWQ",
                "6TW5_9M2",
                "6TW7_NZB",
                "6VTA_AKN",
                "6WTN_RXT",
            ],
        },
        "baseline": {"metrics": _lane_metrics(baseline, "baseline")},
        "rescue": {
            "metrics": _lane_metrics(rescue, "rescue"),
            "allocation_and_refinement": {
                "allocated_candidate_count": 28,
                "parent_coordinate_duplicate_candidate_count": 28,
                "torsion_selected_candidate_count": 0,
            },
        },
    }
    payload["report_sha256"] = _sha256(payload)
    return payload


def _materialization(case_id: str) -> dict[str, object]:
    artifacts = _case_artifacts(case_id)
    return _seal(
        {
            "schema_id": atlas_builder.PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
            "case_id": case_id,
            "source_archive_sha256": atlas_builder.PUBLIC_REDOCKING_ARCHIVE_SHA256,
            "hash_verified_archive": True,
            "archive_members": {
                filename: f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
                for filename in artifacts
            },
            "artifact_sha256s": artifacts,
            "frozen_case_seed": atlas_builder.frozen_public_redocking_case_seed(
                case_id
            ),
        }
    )


def _execution_receipt(
    result: dict[str, object],
    *,
    engine_identity: dict[str, object],
    materialization_sha256: str,
) -> dict[str, object]:
    case_id = str(result["case_id"])
    return _seal(
        {
            "schema_id": atlas_builder.PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
            "runner_id": atlas_builder.PUBLIC_REDOCKING_RUNNER_ID,
            "archive_sha256": atlas_builder.PUBLIC_REDOCKING_ARCHIVE_SHA256,
            "source_ids_sha256": atlas_builder.PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
            "command": _execution_command(case_id),
            "execution_policy": _EXECUTION_POLICY,
            "input_sha256s": _case_inputs(case_id),
            "materialization_receipt_sha256": materialization_sha256,
            "implementation_sha256": engine_identity["implementation_sha256"],
            "evaluation_pipeline_sha256": engine_identity["evaluation_pipeline_sha256"],
            "execution_environment_sha256": engine_identity[
                "execution_environment_sha256"
            ],
            "cache_read_allowed": False,
            "fresh_execution": True,
            "result": result,
        }
    )


def _analysis(
    *,
    source_receipts_sha256: dict[str, str],
) -> dict[str, object]:
    return _seal(
        {
            "schema_id": atlas_builder.ANALYSIS_SCHEMA_ID,
            "analysis_scope": "historical_contaminated_development_only",
            "contains_fresh_internal_blind_holdout": False,
            "case_ids": list(atlas_builder.EXPECTED_CASE_IDS),
            "source_receipts_sha256": source_receipts_sha256,
        },
        field="report_sha256",
    )


def _summary(
    *,
    lane: str,
    engine_identity: dict[str, object],
    results: dict[str, dict[str, object]],
    receipts: dict[str, dict[str, object]],
    materializations: dict[str, dict[str, object]],
) -> dict[str, object]:
    return _seal(
        {
            "schema_id": (
                atlas_builder.SUMMARY_SCHEMA_ID
                if lane == "baseline"
                else atlas_builder.RESCUE_SUMMARY_SCHEMA_ID
            ),
            "analysis_scope": "historical_contaminated_development_only",
            "runner_id": atlas_builder.PUBLIC_REDOCKING_RUNNER_ID,
            "case_count": len(atlas_builder.EXPECTED_CASE_IDS),
            "case_ids": list(atlas_builder.EXPECTED_CASE_IDS),
            "case_ids_sha256": atlas_builder.EXPECTED_CASE_IDS_SHA256,
            "engine_identity": engine_identity,
            "rows": [results[case_id] for case_id in atlas_builder.EXPECTED_CASE_IDS],
            "execution_receipts": [
                receipts[case_id] for case_id in atlas_builder.EXPECTED_CASE_IDS
            ],
            "materializations": [
                materializations[case_id] for case_id in atlas_builder.EXPECTED_CASE_IDS
            ],
            "profiles": [
                {"case_id": case_id} for case_id in atlas_builder.EXPECTED_CASE_IDS
            ],
            "benchmark_validated": False,
            "claim_safe": False,
            "contains_engineering_smoke": False,
            "contains_fresh_internal_blind_holdout": False,
            "fresh_execution_authorized": False,
            "primary_claim_eligible": False,
            "product_promotion_eligible": False,
            "product_qualified": False,
            "public_claim_eligible": False,
            "scientifically_validated": False,
        },
        field="summary_sha256",
    )


def _tar_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name, payload in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _synthetic_bundle(
    *,
    analysis_drift_lane: str | None = None,
    execution_drift: str | None = None,
    input_drift_lane: str | None = None,
    result_input_drift_lane: str | None = None,
    result_projection_drift_lane: str | None = None,
    rescue_drift: str | None = None,
) -> dict[str, object]:
    baseline = _results("baseline")
    rescue = _results("rescue")
    report = _ab_report(baseline, rescue)
    if result_input_drift_lane is not None:
        input_drift_results = (
            baseline if result_input_drift_lane == "baseline" else rescue
        )
        input_drift_results[atlas_builder.EXPECTED_CASE_IDS[0]][
            "receptor_artifact_sha256"
        ] = "8" * 64
    if result_projection_drift_lane is not None:
        lane_results = (
            baseline if result_projection_drift_lane == "baseline" else rescue
        )
        first_result = lane_results[atlas_builder.EXPECTED_CASE_IDS[0]]
        rmsds = list(first_result["rmsd_angstroms"])
        rmsds[0] = float(rmsds[0]) + 0.125
        first_result["rmsd_angstroms"] = rmsds
    if rescue_drift in {
        "selected_true",
        "selected_nonbool",
        "parent_mismatch",
        "missing_field",
        "extra_field",
    }:
        candidate = rescue["6T88_MWQ"]["engine_v2_diagnostics"]["candidates"][8]
        payload = dict(candidate["refinement_receipt_payload"])
        payload.pop("receipt_sha256")
        if rescue_drift == "selected_true":
            payload["torsion_selected"] = True
        elif rescue_drift == "selected_nonbool":
            payload["torsion_selected"] = 1
        elif rescue_drift == "parent_mismatch":
            candidate["torsion_rescue_parent_proposal_index"] = 25
            payload["source_paired_parent_proposal_index"] = 25
        elif rescue_drift == "missing_field":
            payload.pop("config_sha256")
        else:
            payload["unexpected_field"] = "not-authorized"
        candidate["refinement_receipt_payload"] = _seal(payload)
        candidate["refinement_receipt_sha256"] = payload["receipt_sha256"]
    elif rescue_drift == "changed_index_mismatch":
        baseline_candidates = baseline["5SD5_HWI"]["engine_v2_diagnostics"][
            "candidates"
        ]
        rescue_candidates = rescue["5SD5_HWI"]["engine_v2_diagnostics"]["candidates"]
        baseline_candidates[8]["coordinate_fingerprint_sha256"] = baseline_candidates[
            24
        ]["coordinate_fingerprint_sha256"]
        rescue_candidates[9]["coordinate_fingerprint_sha256"] = _digest(
            "5SD5_HWI", 9, "unexpected-rescue-change"
        )
    report.pop("report_sha256")
    engine_identity = report["engine_identity"]
    assert isinstance(engine_identity, dict)
    members: dict[str, bytes] = {}
    for lane, results in (("baseline", baseline), ("rescue", rescue)):
        run_root = f".betelgeuze/synthetic/{lane}"
        analysis_path = f".betelgeuze/synthetic/{lane}-analysis.json"
        summary_path = f"{run_root}/{lane}-summary.json"
        receipts: dict[str, dict[str, object]] = {}
        materializations: dict[str, dict[str, object]] = {}
        receipt_hashes: dict[str, str] = {}
        for case_id in atlas_builder.EXPECTED_CASE_IDS:
            materialization = _materialization(case_id)
            receipt = _execution_receipt(
                results[case_id],
                engine_identity=engine_identity,
                materialization_sha256=str(materialization["receipt_sha256"]),
            )
            if (
                input_drift_lane == lane
                and case_id == atlas_builder.EXPECTED_CASE_IDS[0]
            ):
                receipt.pop("receipt_sha256")
                inputs = dict(receipt["input_sha256s"])
                inputs["receptor"] = "9" * 64
                receipt["input_sha256s"] = inputs
                _seal(receipt)
            if (
                execution_drift == f"{lane}_command"
                and case_id == atlas_builder.EXPECTED_CASE_IDS[0]
            ):
                receipt.pop("receipt_sha256")
                receipt["command"] = ["resealed-but-cross-wired"]
                _seal(receipt)
            if (
                execution_drift == f"{lane}_policy"
                and case_id == atlas_builder.EXPECTED_CASE_IDS[0]
            ):
                receipt.pop("receipt_sha256")
                receipt["execution_policy"] = {
                    **_EXECUTION_POLICY,
                    "scorer_thread_count": 2,
                }
                _seal(receipt)
            receipt_path = f"{run_root}/receipts/engine_v2/{case_id}.json"
            materialization_path = (
                f"{run_root}/receipts/materializations/{case_id}.json"
            )
            receipt_raw = _canonical_bytes(receipt) + b"\n"
            members[receipt_path] = receipt_raw
            members[materialization_path] = _canonical_bytes(materialization) + b"\n"
            receipts[case_id] = receipt
            materializations[case_id] = materialization
            receipt_hashes[receipt_path] = hashlib.sha256(receipt_raw).hexdigest()
        if analysis_drift_lane == lane:
            first_path = next(iter(receipt_hashes))
            receipt_hashes[first_path] = "9" * 64
        analysis = _analysis(source_receipts_sha256=receipt_hashes)
        summary = _summary(
            lane=lane,
            engine_identity=engine_identity,
            results=results,
            receipts=receipts,
            materializations=materializations,
        )
        analysis_raw = _canonical_bytes(analysis) + b"\n"
        summary_raw = _canonical_bytes(summary) + b"\n"
        members[analysis_path] = analysis_raw
        members[summary_path] = summary_raw
        lane_row = report[lane]
        assert isinstance(lane_row, dict)
        lane_row.update(
            {
                "run_root": run_root,
                "analysis_path": analysis_path,
                "analysis_file_sha256": hashlib.sha256(analysis_raw).hexdigest(),
                "analysis_self_sha256": analysis["report_sha256"],
                "summary_path": summary_path,
                "summary_file_sha256": hashlib.sha256(summary_raw).hexdigest(),
                "summary_self_sha256": summary["summary_sha256"],
            }
        )
    report["report_sha256"] = _sha256(report)
    report_member = ".betelgeuze/synthetic/source-paired-ab.json"
    members[report_member] = (
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii")
        + b"\n"
    )
    tar_raw = _tar_bytes(members)
    archive_raw = b"synthetic-zstd-envelope"
    manifest_raw = b"".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n".encode("ascii")
        for name, payload in sorted(members.items())
    )
    archive_name = "source-paired-ab.tar.zst"
    members_name = "source-paired-ab.members.sha256"
    archive_sha256 = hashlib.sha256(archive_raw).hexdigest()
    members_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    bundle_raw = (
        f"{archive_sha256}  {archive_name}\n{members_sha256}  {members_name}\n"
    ).encode("ascii")
    return {
        "archive_name": archive_name,
        "archive_raw": archive_raw,
        "archive_sha256": archive_sha256,
        "members_name": members_name,
        "members_raw": manifest_raw,
        "members_sha256": members_sha256,
        "bundle_name": "source-paired-ab.bundle.sha256",
        "bundle_raw": bundle_raw,
        "bundle_sha256": hashlib.sha256(bundle_raw).hexdigest(),
        "report_member": report_member,
        "report_sha256": report["report_sha256"],
        "tar_raw": tar_raw,
    }


def _write_bundle(repo_root: Path, bundle: dict[str, object]) -> dict[str, object]:
    state = repo_root / ".betelgeuze"
    state.mkdir(mode=0o700)
    paths: dict[str, Path] = {}
    for key in ("archive", "members", "bundle"):
        path = state / str(bundle[f"{key}_name"])
        path.write_bytes(bundle[f"{key}_raw"])
        path.chmod(0o600)
        paths[key] = path
    return {
        "repo_root": repo_root,
        "archive_path": paths["archive"],
        "members_path": paths["members"],
        "bundle_path": paths["bundle"],
        "report_member": bundle["report_member"],
        "expected_archive_sha256": bundle["archive_sha256"],
        "expected_members_sha256": bundle["members_sha256"],
        "expected_bundle_sha256": bundle["bundle_sha256"],
        "expected_report_sha256": bundle["report_sha256"],
    }


def _mock_zstd(
    monkeypatch: pytest.MonkeyPatch,
    bundle: dict[str, object],
) -> None:
    tar_raw = bundle["tar_raw"]
    manifest_raw = bundle["members_raw"]
    assert isinstance(tar_raw, bytes)
    assert isinstance(manifest_raw, bytes)
    monkeypatch.setattr(
        atlas_builder,
        "EXPECTED_EVIDENCE_ARCHIVE_SHA256",
        bundle["archive_sha256"],
    )
    monkeypatch.setattr(
        atlas_builder,
        "EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256",
        bundle["members_sha256"],
    )
    monkeypatch.setattr(
        atlas_builder,
        "EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256",
        bundle["bundle_sha256"],
    )
    monkeypatch.setattr(
        atlas_builder,
        "EXPECTED_EVIDENCE_MEMBER_COUNT",
        len(manifest_raw.splitlines()),
    )
    monkeypatch.setattr(
        atlas_builder,
        "_bounded_zstd_decompress",
        lambda _raw: tar_raw,
    )
    monkeypatch.setattr(
        atlas_builder,
        "_typed_development_result",
        lambda value, **_kwargs: SimpleNamespace(
            case_id=value["case_id"],
            engine_id=value["engine_id"],
            to_dict=lambda value=dict(value): value,
        ),
    )


def test_authenticated_archive_builds_exact_source_paired_atlas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    _mock_zstd(monkeypatch, bundle)
    report = atlas_builder.build_authenticated_failure_atlas(
        **_write_bundle(tmp_path, bundle)
    )

    assert report["schema_id"] == atlas_builder.SCHEMA_ID
    assert report["case_ids"] == list(atlas_builder.EXPECTED_UNCOVERED_CASE_IDS)
    assert report["failure_class_counts"] == {
        "invalid_top1": 5,
        "valid_nonnative_top1": 2,
    }
    assert report["cross_lane_summary"]["rescue_parent_duplicate_count"] == 28
    assert report["cross_lane_summary"]["torsion_selected_count"] == 0
    assert report["authentication"]["both_raw_receipt_lanes_verified"] is True
    assert report["input_evidence"]["ab_report_member"] == bundle["report_member"]
    projection = dict(report)
    observed = projection.pop("report_sha256")
    assert observed == _sha256(projection)
    assert b"score_term_binary64_hex" not in _canonical_bytes(report)


def test_schema_and_reviewed_archive_identities_are_pinned() -> None:
    assert atlas_builder.SCHEMA_ID == (
        "betelgeuze.engine_v2_source_paired_failure_atlas/2.0.0"
    )
    assert atlas_builder.EXPECTED_EVIDENCE_ARCHIVE_SHA256 == (
        "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc"
    )
    assert atlas_builder.EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256 == (
        "7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21"
    )
    assert atlas_builder.EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256 == (
        "6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9"
    )


def test_production_result_binding_rejects_nested_candidate_drift() -> None:
    result = _strict_valid_result(atlas_builder.EXPECTED_CASE_IDS[0])
    assert (
        atlas_builder._typed_development_result(
            result,
            _legacy_source_paired_receipt_authority=(
                atlas_builder._VERIFIED_LEGACY_SOURCE_PAIRED_RECEIPT_AUTHORITY
            ),
        ).to_dict()
        == result
    )
    tampered = json.loads(json.dumps(result))
    tampered["engine_v2_diagnostics"]["candidates"][0]["hbond_count"] = -1

    with pytest.raises(ValueError, match="development_source_result_schema_invalid"):
        atlas_builder._typed_development_result(
            tampered,
            _legacy_source_paired_receipt_authority=(
                atlas_builder._VERIFIED_LEGACY_SOURCE_PAIRED_RECEIPT_AUTHORITY
            ),
        )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_authenticated_archive_rejects_analysis_receipt_drift(
    lane: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(analysis_drift_lane=lane)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match="receipts contradict the analysis"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize(
    ("drift", "message"),
    (
        ("selected_true", "candidate-level A/B changes"),
        ("selected_nonbool", "source-paired rescue receipt"),
        ("parent_mismatch", "allocation parent binding"),
        ("missing_field", "source-paired rescue receipt"),
        ("extra_field", "source-paired rescue receipt"),
        ("changed_index_mismatch", "coordinate changes contradict"),
    ),
)
def test_authenticated_archive_rejects_resealed_rescue_semantic_drift(
    drift: str,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(rescue_drift=drift)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match=message):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize("layer", ("archive", "manifest", "bundle"))
def test_authenticated_archive_rejects_chain_tamper(
    layer: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    _mock_zstd(monkeypatch, bundle)
    arguments = _write_bundle(tmp_path, bundle)
    if layer == "archive":
        arguments["archive_path"].write_bytes(b"tampered")
    elif layer == "manifest":
        lines = arguments["members_path"].read_text(encoding="ascii").splitlines()
        _, _, name = lines[0].partition("  ")
        lines[0] = f"{'0' * 64}  {name}"
        manifest_raw = ("\n".join(lines) + "\n").encode("ascii")
        arguments["members_path"].write_bytes(manifest_raw)
        members_sha256 = hashlib.sha256(manifest_raw).hexdigest()
        bundle_raw = (
            f"{arguments['expected_archive_sha256']}  "
            f"{arguments['archive_path'].name}\n"
            f"{members_sha256}  {arguments['members_path'].name}\n"
        ).encode("ascii")
        arguments["bundle_path"].write_bytes(bundle_raw)
        arguments["expected_members_sha256"] = members_sha256
        arguments["expected_bundle_sha256"] = hashlib.sha256(bundle_raw).hexdigest()
    else:
        bundle_raw = (
            arguments["bundle_path"]
            .read_bytes()
            .replace(
                arguments["members_path"].name.encode("ascii"),
                b"wrong.members.sha256",
            )
        )
        arguments["bundle_path"].write_bytes(bundle_raw)
        arguments["expected_bundle_sha256"] = hashlib.sha256(bundle_raw).hexdigest()

    with pytest.raises(ValueError, match="archive bundle|member hash|cross-links"):
        atlas_builder.build_authenticated_failure_atlas(**arguments)


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_authenticated_archive_rejects_materialization_input_drift(
    lane: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(input_drift_lane=lane)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match="materialization is cross-wired"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_authenticated_archive_rejects_result_input_drift(
    lane: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(result_input_drift_lane=lane)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match="materialization is cross-wired"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize("drift", ("baseline_command", "baseline_policy"))
def test_authenticated_archive_rejects_execution_binding_drift(
    drift: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(execution_drift=drift)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match="typed result is cross-wired"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_authenticated_archive_rejects_ranked_result_projection_drift(
    lane: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle(result_projection_drift_lane=lane)
    _mock_zstd(monkeypatch, bundle)

    with pytest.raises(ValueError, match="ranked result contradicts"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


def test_authenticated_archive_rejects_strict_result_binding_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    _mock_zstd(monkeypatch, bundle)

    def reject_result(_value: object, **_kwargs: object) -> object:
        raise ValueError("synthetic strict rejection")

    monkeypatch.setattr(atlas_builder, "_typed_development_result", reject_result)
    with pytest.raises(ValueError, match="strict result binding"):
        atlas_builder.build_authenticated_failure_atlas(
            **_write_bundle(tmp_path, bundle)
        )


@pytest.mark.parametrize(
    ("path_key", "bound_name"),
    (
        ("members_path", "MAX_MEMBER_MANIFEST_BYTES"),
        ("bundle_path", "MAX_BUNDLE_CHECKSUM_BYTES"),
    ),
)
def test_authenticated_archive_bounds_sidecars(
    path_key: str,
    bound_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    _mock_zstd(monkeypatch, bundle)
    arguments = _write_bundle(tmp_path, bundle)
    payload_size = arguments[path_key].stat().st_size
    monkeypatch.setattr(atlas_builder, bound_name, payload_size - 1)

    with pytest.raises(ValueError, match="bounded regular-file contract"):
        atlas_builder.build_authenticated_failure_atlas(**arguments)


def test_pure_draft_cannot_emit_authoritative_atlas() -> None:
    baseline = _results("baseline")
    rescue = _results("rescue")
    draft = atlas_builder._build_failure_atlas_payload(
        ab_report=_ab_report(baseline, rescue),
        baseline_results=baseline,
        rescue_results=rescue,
    )

    assert "schema_id" not in draft
    assert "report_sha256" not in draft
    assert "input_evidence" not in draft


def test_bounded_zstd_decompress_stops_oversize_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.BytesIO(b"123456789")
            self.killed = False

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> int:
            return -9 if self.killed else 0

    process = FakeProcess()
    monkeypatch.setattr(atlas_builder, "MAX_TAR_BYTES", 8)
    monkeypatch.setattr(
        atlas_builder.subprocess,
        "Popen",
        lambda *_args, **_kwargs: process,
    )

    with pytest.raises(ValueError, match="bounded tar size"):
        atlas_builder._bounded_zstd_decompress(b"verified compressed bytes")
    assert process.killed is True


def test_output_is_confined_hardened_and_exclusive(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    relative = atlas_builder._output_relative_path(
        repo_root, Path(".betelgeuze/atlas/report.json")
    )
    atlas_builder._write_exclusive(repo_root, relative, b"first\n")
    output = repo_root / relative

    assert output.read_bytes() == b"first\n"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    with pytest.raises(FileExistsError):
        atlas_builder._write_exclusive(repo_root, relative, b"second\n")
    assert output.read_bytes() == b"first\n"
    assert not tuple(output.parent.glob(f".{output.name}.*.tmp"))

    outside = tmp_path / "outside" / "atlas.json"
    with pytest.raises(ValueError, match="inside the repository"):
        atlas_builder._output_relative_path(repo_root, outside)
    assert not outside.parent.exists()

    symlink_repo = tmp_path / "symlink-repo"
    symlink_repo.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    os.symlink(external, symlink_repo / ".betelgeuze")
    symlink_relative = atlas_builder._output_relative_path(
        symlink_repo, Path(".betelgeuze/atlas.json")
    )
    with pytest.raises(OSError):
        atlas_builder._write_exclusive(
            symlink_repo,
            symlink_relative,
            b"blocked\n",
        )
    assert not (external / "atlas.json").exists()

    real_artifacts = repo_root / ".betelgeuze" / "real-artifacts"
    real_artifacts.mkdir()
    artifact = real_artifacts / "archive.bin"
    artifact.write_bytes(b"archive")
    artifact.chmod(0o600)
    os.symlink("real-artifacts", repo_root / ".betelgeuze" / "artifact-link")
    with pytest.raises(ValueError, match="cannot be opened safely"):
        atlas_builder._bounded_repository_artifact_bytes(
            repo_root,
            Path(".betelgeuze/artifact-link/archive.bin"),
            maximum=1024,
            name="archive",
        )

    repo_root_link = tmp_path / "repo-root-link"
    os.symlink(repo_root, repo_root_link)
    with pytest.raises(ValueError, match="cannot be opened safely"):
        atlas_builder._bounded_repository_artifact_bytes(
            repo_root_link,
            Path(".betelgeuze/real-artifacts/archive.bin"),
            maximum=1024,
            name="archive",
        )


def test_artifact_reader_rejects_parent_swap_after_lexical_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    state = repo_root / ".betelgeuze"
    state.mkdir(parents=True)
    artifact = state / "archive.bin"
    artifact.write_bytes(b"reviewed archive")
    artifact.chmod(0o600)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_artifact = outside / "archive.bin"
    outside_artifact.write_bytes(b"prohibited replacement")
    outside_artifact.chmod(0o600)
    retained_state = repo_root / ".betelgeuze-retained"
    original = atlas_builder._lexical_repository_artifact
    swapped = False

    def swap_parent_after_validation(
        root: Path,
        path: Path,
        *,
        name: str,
    ) -> tuple[Path, Path]:
        nonlocal swapped
        location = original(root, path, name=name)
        state.rename(retained_state)
        os.symlink(outside, state)
        swapped = True
        return location

    monkeypatch.setattr(
        atlas_builder,
        "_lexical_repository_artifact",
        swap_parent_after_validation,
    )
    with pytest.raises(ValueError, match="cannot be opened safely"):
        atlas_builder._bounded_repository_artifact_bytes(
            repo_root,
            Path(".betelgeuze/archive.bin"),
            maximum=1024,
            name="archive",
        )
    assert swapped is True
