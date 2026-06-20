#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KPI_JSON = "runs/ai_md_engine_kpi_report_current.json"
DEFAULT_KPI_MD = "runs/ai_md_engine_kpi_report_current.md"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_PRODUCT_IMAGE_RECEIPT_JSON = "runs/product_image_smoke_receipt_current.json"
DEFAULT_NEXT_STEPS_DOC = "docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md"
DEFAULT_OUT_TAR = "runs/ai_md_product_evidence_bundle_current.tar.gz"
DEFAULT_OUT_JSON = "runs/ai_md_product_evidence_bundle_current.json"
DEFAULT_OUT_CSV = "runs/ai_md_product_evidence_bundle_current.csv"
DEFAULT_OUT_MD = "runs/ai_md_product_evidence_bundle_current.md"

CLAIM_BOUNDARY = (
    "AI-MD product evidence bundle export only; packages local ROCm/HIP/Rust runtime contracts, KPI reports, "
    "runner profile evidence, and implementation documents. It does not run docking, run GPU jobs, train models, "
    "promote claims, upload, submit, email, delete files, or mutate external state."
)

EXPECTED_ALLOWLISTED_RUNNER_SHIMS = (
    {
        "profile_id": "ligand_htvs_pipeline_default",
        "runner_script": "tools/run_ligand_htvs_pipeline.py",
        "adapter_import": "betelgeuze_engine.product.runners.htvs_pipeline",
    },
    {
        "profile_id": "backmapping_scoring.production",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "adapter_import": "betelgeuze_engine.product.runners.backmapping_scoring",
    },
    {
        "profile_id": "ligand_topk_delivery.production",
        "runner_script": "tools/run_ligand_topk_delivery.py",
        "adapter_import": "betelgeuze_engine.product.runners.topk_delivery",
    },
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _arcname(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return f"external_inputs/{_sha256_file(path)[:12]}_{path.name}"


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool_nested(payload: dict[str, Any], *keys: str) -> bool:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return False
        current = current.get(key)
    return current is True


def _validate_kpi_claim_metadata_gates(
    *,
    artifact_id: str,
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("packet_type") != "ai_md_engine_kpi_report":
        errors.append(f"kpi_json_packet_type_invalid:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "runner_claim_metadata_signed"):
        errors.append(f"kpi_runner_claim_metadata_not_signed:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "signed_manifest_verification_pass"):
        errors.append(f"kpi_signed_manifest_verification_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "runner_profile_validation_pass"):
        errors.append(f"kpi_runner_profile_validation_not_pass:{artifact_id}")
    if _int_value(payload.get("product_kpi", {}).get("enabled_profile_count")) < 3:
        errors.append(f"kpi_runner_profile_enabled_count_low:{artifact_id}")
    if _int_value(payload.get("product_kpi", {}).get("failed_profile_count")) != 0:
        errors.append(f"kpi_runner_profile_failed_count_nonzero:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "force_term_claim_metadata_ready"):
        errors.append(f"kpi_force_term_claim_metadata_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "force_term_result_contract_ready"):
        errors.append(f"kpi_force_term_result_contract_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "guarded_force_term_plugin_ready"):
        errors.append(f"kpi_guarded_force_term_plugin_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "onsps_backmap_evidence_schema_ready"):
        errors.append(f"kpi_onsps_backmap_evidence_schema_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_forcefield_bridge_ready"):
        errors.append(f"kpi_core_forcefield_bridge_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_compatibility_layer_ready"):
        errors.append(f"kpi_core_compatibility_layer_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "job_store_lazy_factory_ready"):
        errors.append(f"kpi_job_store_lazy_factory_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "allowlisted_runner_shim_contract_ready"):
        errors.append(f"kpi_allowlisted_runner_shim_contract_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "engine_topology_factory_facade_ready"):
        errors.append(f"kpi_engine_topology_factory_facade_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "source_artifacts_fresh"):
        errors.append(f"kpi_source_artifacts_not_fresh:{artifact_id}")
    runtime = payload.get("runtime_kpi")
    if not isinstance(runtime, dict):
        runtime = {}
    runtime_score = runtime.get("score_only_1k")
    if not isinstance(runtime_score, dict):
        runtime_score = {}
    runtime_onsps = runtime.get("top100_4bead_rescoring")
    if not isinstance(runtime_onsps, dict):
        runtime_onsps = {}
    runtime_residual = runtime.get("top10_force_residual")
    if not isinstance(runtime_residual, dict):
        runtime_residual = {}
    neighbor = runtime.get("neighbor_list_rebuild")
    if not isinstance(neighbor, dict):
        neighbor = {}
    if (
        _int_value(runtime_score.get("row_count")) < 1
        or _float_value(runtime_score.get("duration_sec")) <= 0.0
        or _float_value(runtime_score.get("rows_per_sec")) <= 0.0
    ):
        errors.append(f"kpi_runtime_score_only_1k_missing:{artifact_id}")
    if (
        _int_value(runtime_onsps.get("row_count")) < 1
        or _float_value(runtime_onsps.get("duration_sec")) <= 0.0
        or _float_value(runtime_onsps.get("rows_per_sec")) <= 0.0
        or _int_value(runtime_onsps.get("onsps_backmap_claim_safe_count")) < 1
    ):
        errors.append(f"kpi_runtime_top100_4bead_rescoring_missing:{artifact_id}")
    if (
        _int_value(runtime_residual.get("row_count")) < 1
        or _float_value(runtime_residual.get("duration_sec")) <= 0.0
        or _float_value(runtime_residual.get("rows_per_sec")) <= 0.0
        or _int_value(runtime_residual.get("applied_count")) < 1
    ):
        errors.append(f"kpi_runtime_top10_force_residual_missing:{artifact_id}")
    if runtime_residual.get("contract_ready") is not True:
        errors.append(f"kpi_runtime_top10_force_residual_contract_not_ready:{artifact_id}")
    if runtime_residual.get("top_k_policy_ready") is not True:
        errors.append(f"kpi_runtime_top10_force_residual_top_k_policy_not_ready:{artifact_id}")
    outside_top_k_report = runtime_residual.get("outside_top_k_report")
    if not isinstance(outside_top_k_report, dict):
        outside_top_k_report = {}
    outside_policy_caps = outside_top_k_report.get("policy_caps")
    if not isinstance(outside_policy_caps, dict):
        outside_policy_caps = {}
    if (
        outside_top_k_report.get("skipped_reason") != "outside_top_k_policy"
        or outside_top_k_report.get("applied") is not False
        or outside_top_k_report.get("top_k_eligible") is not False
        or _float_value(outside_top_k_report.get("rank_pct"))
        <= _float_value(outside_policy_caps.get("top_k_rank_pct"))
    ):
        errors.append(f"kpi_runtime_top10_force_residual_top_k_report_invalid:{artifact_id}")
    if _int_value(runtime_residual.get("nonfinite_uncertainty_abstention_count")) < 1:
        errors.append(f"kpi_runtime_force_residual_nonfinite_uncertainty_abstention_missing:{artifact_id}")
    if _int_value(runtime_residual.get("nonfinite_delta_score_abstention_count")) < 1:
        errors.append(f"kpi_runtime_force_residual_nonfinite_delta_abstention_missing:{artifact_id}")
    nonfinite_uncertainty_report = runtime_residual.get("nonfinite_uncertainty_report")
    if not isinstance(nonfinite_uncertainty_report, dict):
        nonfinite_uncertainty_report = {}
    if (
        nonfinite_uncertainty_report.get("skipped_reason") != "uncertainty_nonfinite"
        or nonfinite_uncertainty_report.get("applied") is not False
        or _float_value(nonfinite_uncertainty_report.get("uncertainty")) != 1.0
        or _float_value(nonfinite_uncertainty_report.get("confidence")) != 0.0
        or nonfinite_uncertainty_report.get("observed_caps_ready") is not True
    ):
        errors.append(f"kpi_runtime_force_residual_nonfinite_uncertainty_report_invalid:{artifact_id}")
    nonfinite_delta_report = runtime_residual.get("nonfinite_delta_score_report")
    if not isinstance(nonfinite_delta_report, dict):
        nonfinite_delta_report = {}
    if (
        nonfinite_delta_report.get("skipped_reason") != "delta_score_nonfinite"
        or nonfinite_delta_report.get("applied") is not False
        or _float_value(nonfinite_delta_report.get("delta_score")) != 0.0
        or nonfinite_delta_report.get("observed_caps_ready") is not True
    ):
        errors.append(f"kpi_runtime_force_residual_nonfinite_delta_report_invalid:{artifact_id}")
    if _float_value(runtime.get("memory_peak_mb")) <= 0.0:
        errors.append(f"kpi_runtime_memory_peak_missing:{artifact_id}")
    if (
        _int_value(neighbor.get("frame_count")) < 1
        or _int_value(neighbor.get("neighbor_list_rebuild_count")) < 1
        or _float_value(neighbor.get("neighbor_list_rebuild_frequency")) <= 0.0
        or neighbor.get("engine_neighbor_diagnostics_ready") is not True
        or _int_value(neighbor.get("last_forcefield_neighbor_pair_count"))
        != _int_value(neighbor.get("last_neighbor_pair_count"))
        or neighbor.get("forcefield_neighbor_pairs_provided") is not True
        or neighbor.get("forcefield_neighbor_source") != "provided"
    ):
        errors.append(f"kpi_runtime_neighbor_list_rebuild_missing:{artifact_id}")
    pm_runtime = (
        payload.get("pm_kpi_summary", {}).get("runtime", {})
        if isinstance(payload.get("pm_kpi_summary"), dict)
        else {}
    )
    if not isinstance(pm_runtime, dict):
        pm_runtime = {}
    if _float_value(pm_runtime.get("score_only_1k_runtime_sec")) != _float_value(
        runtime_score.get("duration_sec")
    ):
        errors.append(f"pm_runtime_score_only_duration_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("score_only_1k_rows_per_sec")) != _float_value(
        runtime_score.get("rows_per_sec")
    ):
        errors.append(f"pm_runtime_score_only_rows_per_sec_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("top100_4bead_rescoring_runtime_sec")) != _float_value(
        runtime_onsps.get("duration_sec")
    ):
        errors.append(f"pm_runtime_top100_4bead_duration_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("top100_4bead_rescoring_rows_per_sec")) != _float_value(
        runtime_onsps.get("rows_per_sec")
    ):
        errors.append(f"pm_runtime_top100_4bead_rows_per_sec_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("top10_force_residual_runtime_sec")) != _float_value(
        runtime_residual.get("duration_sec")
    ):
        errors.append(f"pm_runtime_top10_force_residual_duration_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("top10_force_residual_rows_per_sec")) != _float_value(
        runtime_residual.get("rows_per_sec")
    ):
        errors.append(f"pm_runtime_top10_force_residual_rows_per_sec_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("memory_peak_mb")) != _float_value(runtime.get("memory_peak_mb")):
        errors.append(f"pm_runtime_memory_peak_mismatch:{artifact_id}")
    if _float_value(pm_runtime.get("neighbor_list_rebuild_frequency")) != _float_value(
        neighbor.get("neighbor_list_rebuild_frequency")
    ):
        errors.append(f"pm_runtime_neighbor_list_rebuild_frequency_mismatch:{artifact_id}")
    physics = payload.get("physics_kpi")
    if not isinstance(physics, dict):
        physics = {}
    if (
        "finite_difference_force_error" not in physics
        or _float_value(physics.get("finite_difference_force_error")) >= 1e-3
    ):
        errors.append(f"kpi_physics_finite_difference_force_error_high:{artifact_id}")
    if (
        "energy_drift_smoke_pct" not in physics
        or _float_value(physics.get("energy_drift_smoke_pct")) >= 1e-2
    ):
        errors.append(f"kpi_physics_energy_drift_high:{artifact_id}")
    if (
        "neighbor_list_parity_error" not in physics
        or _float_value(physics.get("neighbor_list_parity_error")) != 0.0
    ):
        errors.append(f"kpi_physics_neighbor_list_parity_error:{artifact_id}")
    force_term_thresholds = physics.get("force_term_physics_validation_thresholds")
    if not isinstance(force_term_thresholds, dict):
        force_term_thresholds = {}
    fd_limit = _float_value(force_term_thresholds.get("finite_difference_force_error_max"))
    translation_limit = _float_value(force_term_thresholds.get("translation_invariance_error_max"))
    rotation_limit = _float_value(force_term_thresholds.get("rotation_equivariance_error_max"))
    drift_limit = _float_value(force_term_thresholds.get("energy_drift_smoke_pct_max"))
    if fd_limit <= 0.0 or translation_limit <= 0.0 or rotation_limit <= 0.0 or drift_limit <= 0.0:
        errors.append(f"kpi_physics_force_term_thresholds_invalid:{artifact_id}")
    force_term_rows = physics.get("force_term_physics_validation_rows")
    if not isinstance(force_term_rows, list):
        force_term_rows = []
    expected_force_terms = {"directional_hbond", "hydrophobic_contact", "legacy_lj"}
    observed_force_terms = {
        str(row.get("term") or "")
        for row in force_term_rows
        if isinstance(row, dict) and str(row.get("term") or "")
    }
    if observed_force_terms != expected_force_terms:
        errors.append(f"kpi_physics_force_term_validation_terms_invalid:{artifact_id}")
    if _int_value(physics.get("force_term_physics_validation_term_count")) != len(expected_force_terms):
        errors.append(f"kpi_physics_force_term_validation_term_count_invalid:{artifact_id}")
    if _int_value(physics.get("force_term_physics_validation_claim_safe_count")) != len(expected_force_terms):
        errors.append(f"kpi_physics_force_term_validation_claim_safe_count_invalid:{artifact_id}")
    if physics.get("force_term_physics_validation_ready") is not True:
        errors.append(f"kpi_physics_force_term_validation_not_ready:{artifact_id}")
    if physics.get("force_term_physics_validation_claim_safe_ready") is not True:
        errors.append(f"kpi_physics_force_term_validation_claim_safe_not_ready:{artifact_id}")
    if _float_value(physics.get("force_term_finite_difference_max_error")) >= fd_limit:
        errors.append(f"kpi_physics_force_term_finite_difference_high:{artifact_id}")
    if _float_value(physics.get("force_term_translation_invariance_max_error")) >= translation_limit:
        errors.append(f"kpi_physics_force_term_translation_invariance_high:{artifact_id}")
    if _float_value(physics.get("force_term_rotation_equivariance_max_error")) >= rotation_limit:
        errors.append(f"kpi_physics_force_term_rotation_equivariance_high:{artifact_id}")
    if _float_value(physics.get("force_term_energy_drift_max_pct")) >= drift_limit:
        errors.append(f"kpi_physics_force_term_energy_drift_high:{artifact_id}")
    for row in force_term_rows:
        if not isinstance(row, dict):
            errors.append(f"kpi_physics_force_term_validation_row_invalid:{artifact_id}")
            continue
        term = str(row.get("term") or "unknown_term")
        if row.get("ready") is not True:
            errors.append(f"kpi_physics_force_term_validation_row_not_ready:{artifact_id}:{term}")
        if row.get("status") != "pass" or row.get("force_term_status") != "pass":
            errors.append(f"kpi_physics_force_term_validation_row_status_invalid:{artifact_id}:{term}")
        if row.get("claim_safe") is not True or str(row.get("blocked_reason") or ""):
            errors.append(f"kpi_physics_force_term_validation_row_claim_not_safe:{artifact_id}:{term}")
        if _float_value(row.get("finite_difference_force_error")) >= fd_limit:
            errors.append(f"kpi_physics_force_term_validation_row_finite_difference_high:{artifact_id}:{term}")
        if _float_value(row.get("translation_invariance_error")) >= translation_limit:
            errors.append(f"kpi_physics_force_term_validation_row_translation_high:{artifact_id}:{term}")
        if _float_value(row.get("rotation_equivariance_error")) >= rotation_limit:
            errors.append(f"kpi_physics_force_term_validation_row_rotation_high:{artifact_id}:{term}")
        if _float_value(row.get("energy_drift_smoke_pct")) >= drift_limit:
            errors.append(f"kpi_physics_force_term_validation_row_energy_drift_high:{artifact_id}:{term}")
    if "topology_invalid_rate" not in physics or _float_value(physics.get("topology_invalid_rate")) >= 0.2:
        errors.append(f"kpi_physics_topology_invalid_rate_high:{artifact_id}")
    if "backmapping_failure_rate" not in physics or _float_value(physics.get("backmapping_failure_rate")) >= 0.5:
        errors.append(f"kpi_physics_backmapping_failure_rate_high:{artifact_id}")
    chemistry = payload.get("chemistry_kpi")
    if not isinstance(chemistry, dict):
        chemistry = {}
        errors.append(f"kpi_chemistry_missing:{artifact_id}")
    chemistry_fixture_count = _int_value(chemistry.get("fixture_count"))
    chemistry_rows = chemistry.get("rows")
    if not isinstance(chemistry_rows, list):
        chemistry_rows = []
    if chemistry_fixture_count < 7:
        errors.append(f"kpi_chemistry_fixture_count_low:{artifact_id}")
    if len(chemistry_rows) != chemistry_fixture_count:
        errors.append(f"kpi_chemistry_rows_count_mismatch:{artifact_id}")
    chemistry_fixtures = {
        str(row.get("fixture") or "")
        for row in chemistry_rows
        if isinstance(row, dict) and str(row.get("fixture") or "")
    }
    required_chemistry_fixtures = {
        "ethanol",
        "amide",
        "tertiary_amine",
        "carboxylate",
        "phosphate",
        "heteroaryl_nitrogen",
        "invalid_smiles",
    }
    if not required_chemistry_fixtures.issubset(chemistry_fixtures):
        errors.append(f"kpi_chemistry_required_fixtures_missing:{artifact_id}")
    if chemistry.get("hbond_evidence_schema_ready") is not True:
        errors.append(f"kpi_chemistry_hbond_schema_not_ready:{artifact_id}")
    if _int_value(chemistry.get("hbond_evidence_schema_ready_count")) != chemistry_fixture_count:
        errors.append(f"kpi_chemistry_hbond_schema_ready_count_mismatch:{artifact_id}")
    if chemistry.get("ligand_topology_validity_schema_ready") is not True:
        errors.append(f"kpi_chemistry_ligand_topology_schema_not_ready:{artifact_id}")
    if _int_value(chemistry.get("ligand_topology_validity_schema_ready_count")) != chemistry_fixture_count:
        errors.append(f"kpi_chemistry_ligand_topology_schema_ready_count_mismatch:{artifact_id}")
    if _int_value(chemistry.get("hbond_donor_site_count")) < 1:
        errors.append(f"kpi_chemistry_hbond_donor_sites_missing:{artifact_id}")
    if _int_value(chemistry.get("hbond_acceptor_site_count")) < 1:
        errors.append(f"kpi_chemistry_hbond_acceptor_sites_missing:{artifact_id}")
    if _int_value(chemistry.get("hbond_recovery_fixture_count")) < 1:
        errors.append(f"kpi_chemistry_hbond_recovery_missing:{artifact_id}")
    if _int_value(chemistry.get("unsatisfied_donor_acceptor_fixture_count")) < 1:
        errors.append(f"kpi_chemistry_unsatisfied_fixture_missing:{artifact_id}")
    if (
        _int_value(chemistry.get("unsatisfied_donor_count"))
        + _int_value(chemistry.get("unsatisfied_acceptor_count"))
        < 1
    ):
        errors.append(f"kpi_chemistry_unsatisfied_counts_missing:{artifact_id}")
    if chemistry.get("chirality_preservation_ready") is not True:
        errors.append(f"kpi_chemistry_chirality_not_ready:{artifact_id}")
    if (
        _int_value(chemistry.get("chirality_preservation_fixture_count")) < 1
        or _int_value(chemistry.get("unassigned_chirality_blocked_fixture_count")) < 1
    ):
        errors.append(f"kpi_chemistry_chirality_fixture_missing:{artifact_id}")
    if chemistry.get("ring_validity_ready") is not True or _int_value(
        chemistry.get("ring_validity_fixture_count")
    ) < 1:
        errors.append(f"kpi_chemistry_ring_validity_missing:{artifact_id}")
    if chemistry.get("tautomer_validity_ready") is not True or _int_value(
        chemistry.get("tautomer_validity_fixture_count")
    ) < 1:
        errors.append(f"kpi_chemistry_tautomer_validity_missing:{artifact_id}")
    if chemistry.get("protonation_validity_ready") is not True or _int_value(
        chemistry.get("protonation_validity_fixture_count")
    ) < 1:
        errors.append(f"kpi_chemistry_protonation_validity_missing:{artifact_id}")
    if _int_value(chemistry.get("backmap_evaluable_fixture_count")) < 1:
        errors.append(f"kpi_chemistry_backmap_evaluable_missing:{artifact_id}")
    if _int_value(chemistry.get("backmap_claim_safe_fixture_count")) < 1:
        errors.append(f"kpi_chemistry_backmap_claim_safe_missing:{artifact_id}")
    if "backmapping_failure_rate" not in chemistry or _float_value(
        chemistry.get("backmapping_failure_rate")
    ) >= 0.5:
        errors.append(f"kpi_chemistry_backmapping_failure_rate_high:{artifact_id}")
    for row in chemistry_rows:
        if not isinstance(row, dict):
            errors.append(f"kpi_chemistry_row_invalid:{artifact_id}")
            continue
        fixture = str(row.get("fixture") or "unknown_fixture")
        if row.get("hbond_schema_ready") is not True:
            errors.append(f"kpi_chemistry_row_hbond_schema_not_ready:{artifact_id}:{fixture}")
        if row.get("hbond_threshold_schema_ready") is not True:
            errors.append(f"kpi_chemistry_row_hbond_threshold_schema_not_ready:{artifact_id}:{fixture}")
        if row.get("hbond_pair_schema_ready") is not True:
            errors.append(f"kpi_chemistry_row_hbond_pair_schema_not_ready:{artifact_id}:{fixture}")
        if row.get("hbond_geometry_flags_ready") is not True:
            errors.append(f"kpi_chemistry_row_hbond_geometry_flags_not_ready:{artifact_id}:{fixture}")
        if row.get("ligand_validity_schema_ready") is not True:
            errors.append(f"kpi_chemistry_row_ligand_topology_schema_not_ready:{artifact_id}:{fixture}")
    topology_smoke = (
        payload.get("product_kpi", {}).get("engine_topology_factory_facade_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(topology_smoke, dict):
        topology_smoke = {}
    if topology_smoke.get("facade") != "betelgeuze_engine.topology.TopologyFactoryFacade":
        errors.append(f"kpi_topology_factory_facade_identity_invalid:{artifact_id}")
    if topology_smoke.get("valid_claim_safe") is not True:
        errors.append(f"kpi_topology_factory_valid_claim_not_safe:{artifact_id}")
    if topology_smoke.get("valid_topology_fidelity") != "sequence_mapped":
        errors.append(f"kpi_topology_factory_valid_fidelity_invalid:{artifact_id}")
    if _int_value(topology_smoke.get("valid_protein_residue_count")) < 1:
        errors.append(f"kpi_topology_factory_valid_protein_residues_missing:{artifact_id}")
    if topology_smoke.get("valid_protein_topology_valid") is not True:
        errors.append(f"kpi_topology_factory_valid_protein_not_valid:{artifact_id}")
    if topology_smoke.get("valid_ligand_topology_schema_version") != "ligand_topology_validity_v1":
        errors.append(f"kpi_topology_factory_valid_ligand_schema_missing:{artifact_id}")
    if _int_value(topology_smoke.get("placeholder_protein_residue_count")) < 1:
        errors.append(f"kpi_topology_factory_placeholder_protein_residues_missing:{artifact_id}")
    if topology_smoke.get("placeholder_protein_topology_valid") is not True:
        errors.append(f"kpi_topology_factory_placeholder_protein_not_valid:{artifact_id}")
    if topology_smoke.get("placeholder_blocked_reason") != "placeholder_alanine_topology":
        errors.append(f"kpi_topology_factory_placeholder_blocker_invalid:{artifact_id}")
    if _int_value(topology_smoke.get("empty_protein_residue_count")) != 0:
        errors.append(f"kpi_topology_factory_empty_protein_count_invalid:{artifact_id}")
    if topology_smoke.get("empty_protein_topology_valid") is not False:
        errors.append(f"kpi_topology_factory_empty_protein_not_blocked:{artifact_id}")
    if topology_smoke.get("empty_protein_blocked_reason") != "empty_protein_topology":
        errors.append(f"kpi_topology_factory_empty_protein_blocker_invalid:{artifact_id}")
    if topology_smoke.get("invalid_ligand_blocked_reason") != "invalid_smiles":
        errors.append(f"kpi_topology_factory_invalid_ligand_blocker_invalid:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "runner_claim_metadata_manifest_smoke", "ready"):
        errors.append(f"kpi_runner_claim_metadata_manifest_smoke_not_ready:{artifact_id}")
    manifest_smoke = (
        payload.get("product_kpi", {}).get("runner_claim_metadata_manifest_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(manifest_smoke, dict):
        manifest_smoke = {}
    if manifest_smoke.get("manifest_ligand_topology_valid") is not True:
        errors.append(f"kpi_manifest_ligand_topology_valid_missing:{artifact_id}")
    if manifest_smoke.get("manifest_ligand_topology_claim_safe") is not True:
        errors.append(f"kpi_manifest_ligand_topology_claim_safe_missing:{artifact_id}")
    if manifest_smoke.get("manifest_ligand_topology_schema_version") != "ligand_topology_validity_v1":
        errors.append(f"kpi_manifest_ligand_topology_schema_missing:{artifact_id}")
    if _int_value(manifest_smoke.get("manifest_ligand_topology_schema_ready_row_count")) < 1:
        errors.append(f"kpi_manifest_ligand_topology_schema_rows_missing:{artifact_id}")
    if _int_value(manifest_smoke.get("manifest_ligand_topology_claim_safe_row_count")) < 1:
        errors.append(f"kpi_manifest_ligand_topology_claim_safe_rows_missing:{artifact_id}")
    if manifest_smoke.get("manifest_hbond_evidence_schema_version") != "hbond_evidence_v1":
        errors.append(f"kpi_manifest_hbond_evidence_schema_missing:{artifact_id}")
    if _int_value(manifest_smoke.get("manifest_hbond_evidence_schema_ready_row_count")) < 1:
        errors.append(f"kpi_manifest_hbond_evidence_schema_rows_missing:{artifact_id}")
    if manifest_smoke.get("manifest_claim_safe") is not False:
        errors.append(f"kpi_manifest_blocked_claim_not_blocked:{artifact_id}")
    if not str(manifest_smoke.get("manifest_blocked_reason") or ""):
        errors.append(f"kpi_manifest_blocked_reason_missing:{artifact_id}")
    if manifest_smoke.get("force_residual_summary_present") is not True:
        errors.append(f"kpi_manifest_force_residual_summary_missing:{artifact_id}")
    if manifest_smoke.get("manifest_force_residual_schema_version") != "force_residual_claim_metadata_v1":
        errors.append(f"kpi_manifest_force_residual_schema_missing:{artifact_id}")
    if manifest_smoke.get("manifest_force_residual_policy_caps_ready") is not True:
        errors.append(f"kpi_manifest_force_residual_policy_caps_not_ready:{artifact_id}")
    if manifest_smoke.get("manifest_force_residual_observed_caps_ready") is not True:
        errors.append(f"kpi_manifest_force_residual_observed_caps_not_ready:{artifact_id}")
    if manifest_smoke.get("manifest_force_residual_contract_ready") is not True:
        errors.append(f"kpi_manifest_force_residual_contract_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "force_term_claim_metadata_smoke", "ready"):
        errors.append(f"kpi_force_term_claim_metadata_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "guarded_force_term_plugin_smoke", "ready"):
        errors.append(f"kpi_guarded_force_term_plugin_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "onsps_backmap_evidence_schema_smoke", "ready"):
        errors.append(f"kpi_onsps_backmap_evidence_schema_smoke_not_ready:{artifact_id}")
    force_term_smoke = (
        payload.get("product_kpi", {}).get("force_term_claim_metadata_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(force_term_smoke, dict):
        force_term_smoke = {}
    forcefield_claim_rows = force_term_smoke.get("forcefield_claim_rows")
    if not isinstance(forcefield_claim_rows, list):
        forcefield_claim_rows = []
    force_term_contract_rows = force_term_smoke.get("term_result_contract_rows")
    if not isinstance(force_term_contract_rows, list):
        force_term_contract_rows = []
    if force_term_smoke.get("forcefield_claim_metadata_schema_version") != "force_term_claim_metadata_v1":
        errors.append(f"kpi_force_term_claim_metadata_schema_missing:{artifact_id}")
    if force_term_smoke.get("forcefield_hbond_evidence_schema_version") != "hbond_evidence_v1":
        errors.append(f"kpi_forcefield_hbond_evidence_schema_missing:{artifact_id}")
    if (
        force_term_smoke.get("forcefield_neighbor_diagnostics_ready") is not True
        or _int_value(force_term_smoke.get("forcefield_neighbor_pair_count")) < 1
        or force_term_smoke.get("forcefield_neighbor_pairs_provided") is not False
        or force_term_smoke.get("forcefield_neighbor_source") != "full_neighbor_pairs"
    ):
        errors.append(f"kpi_forcefield_neighbor_diagnostics_missing:{artifact_id}")
    if force_term_smoke.get("term_result_contract_ready") is not True:
        errors.append(f"kpi_force_term_result_contract_smoke_not_ready:{artifact_id}")
    if not force_term_contract_rows:
        errors.append(f"kpi_force_term_result_contract_rows_missing:{artifact_id}")
    elif not all(
        isinstance(row, dict)
        and row.get("ready") is True
        and row.get("energy_shape") == [1]
        and isinstance(row.get("forces_shape"), list)
        and row.get("energy_finite") is True
        and row.get("forces_finite") is True
        and row.get("diagnostics_keys_present") is True
        and row.get("claim_metadata_keys_present") is True
        and str(row.get("term") or "") == str(row.get("diagnostics_term") or "")
        and str(row.get("term") or "") == str(row.get("claim_force_term_name") or "")
        and str(row.get("diagnostics_status") or "") == "pass"
        and str(row.get("claim_force_term_status") or "") == "pass"
        for row in force_term_contract_rows
    ):
        errors.append(f"kpi_force_term_result_contract_rows_invalid:{artifact_id}")
    if _int_value(force_term_smoke.get("forcefield_claim_safe_count")) < 1:
        errors.append(f"kpi_force_term_claim_safe_rows_missing:{artifact_id}")
    if _int_value(force_term_smoke.get("forcefield_blocked_count")) != 0:
        errors.append(f"kpi_force_term_blocked_rows_present:{artifact_id}")
    if not forcefield_claim_rows:
        errors.append(f"kpi_force_term_claim_rows_missing:{artifact_id}")
    elif not all(
        isinstance(row, dict)
        and row.get("claim_safe") is True
        and str(row.get("force_term_name") or "")
        and str(row.get("force_term_status") or "") == "pass"
        for row in forcefield_claim_rows
    ):
        errors.append(f"kpi_force_term_claim_rows_not_safe:{artifact_id}")
    if not any(
        isinstance(row, dict)
        and row.get("force_term_name") == "directional_hbond"
        and row.get("hbond_evidence_schema_version") == "hbond_evidence_v1"
        and row.get("hbond_evidence_schema_ready") is True
        for row in forcefield_claim_rows
    ):
        errors.append(f"kpi_force_term_hbond_schema_row_missing:{artifact_id}")
    guarded_smoke = (
        payload.get("product_kpi", {}).get("guarded_force_term_plugin_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(guarded_smoke, dict):
        guarded_smoke = {}
    if guarded_smoke.get("term") != "screened_electrostatics":
        errors.append(f"kpi_guarded_force_term_plugin_term_missing:{artifact_id}")
    if guarded_smoke.get("claim_safe") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_claim_not_safe:{artifact_id}")
    if guarded_smoke.get("force_term_status") != "pass":
        errors.append(f"kpi_guarded_force_term_plugin_status_not_pass:{artifact_id}")
    if guarded_smoke.get("missing_charge_blocked") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_missing_charge_not_blocked:{artifact_id}")
    if guarded_smoke.get("unvalidated_charge_blocked") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_unvalidated_charge_not_blocked:{artifact_id}")
    if guarded_smoke.get("forcefield_claim_safe") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_forcefield_not_claim_safe:{artifact_id}")
    if float(guarded_smoke.get("finite_difference_force_error") or 1.0) >= 1e-5:
        errors.append(f"kpi_guarded_force_term_plugin_finite_difference_high:{artifact_id}")
    if guarded_smoke.get("policy_caps_ready") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_policy_caps_not_ready:{artifact_id}")
    if guarded_smoke.get("observed_caps_ready") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_observed_caps_not_ready:{artifact_id}")
    if guarded_smoke.get("bounded_correction_ready") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_bounded_correction_not_ready:{artifact_id}")
    if guarded_smoke.get("policy_cap_exceeded_blocked") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_cap_exceeded_not_blocked:{artifact_id}")
    if guarded_smoke.get("forcefield_bounded_row_ready") is not True:
        errors.append(f"kpi_guarded_force_term_plugin_forcefield_bounded_row_missing:{artifact_id}")
    if (
        guarded_smoke.get("abs_energy_within_cap") is not True
        or guarded_smoke.get("force_norm_within_cap") is not True
        or guarded_smoke.get("active_pair_count_within_cap") is not True
    ):
        errors.append(f"kpi_guarded_force_term_plugin_observed_cap_flags_invalid:{artifact_id}")
    forcefield_guarded_row = guarded_smoke.get("forcefield_guarded_claim_row")
    if not isinstance(forcefield_guarded_row, dict):
        forcefield_guarded_row = {}
    if (
        forcefield_guarded_row.get("force_term_name") != "screened_electrostatics"
        or forcefield_guarded_row.get("policy_caps_ready") is not True
        or forcefield_guarded_row.get("observed_caps_ready") is not True
        or forcefield_guarded_row.get("bounded_correction_ready") is not True
        or forcefield_guarded_row.get("abs_energy_within_cap") is not True
        or forcefield_guarded_row.get("force_norm_within_cap") is not True
        or forcefield_guarded_row.get("active_pair_count_within_cap") is not True
        or not isinstance(forcefield_guarded_row.get("policy_caps"), dict)
        or not forcefield_guarded_row.get("policy_caps")
    ):
        errors.append(f"kpi_guarded_force_term_plugin_forcefield_bounded_row_invalid:{artifact_id}")
    onsps_smoke = (
        payload.get("product_kpi", {}).get("onsps_backmap_evidence_schema_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(onsps_smoke, dict):
        onsps_smoke = {}
    if onsps_smoke.get("schema_version") != "onsps_backmap_evidence_v1":
        errors.append(f"kpi_onsps_backmap_schema_version_missing:{artifact_id}")
    if onsps_smoke.get("valid_claim_safe") is not True:
        errors.append(f"kpi_onsps_backmap_valid_claim_not_safe:{artifact_id}")
    if onsps_smoke.get("valid_backmap_status") != "ok":
        errors.append(f"kpi_onsps_backmap_valid_status_not_ok:{artifact_id}")
    if _int_value(onsps_smoke.get("valid_mapped_site_count")) < 1:
        errors.append(f"kpi_onsps_backmap_valid_mapped_sites_missing:{artifact_id}")
    if onsps_smoke.get("empty_blocked_reason") != "invalid_two_bead_geometry":
        errors.append(f"kpi_onsps_backmap_empty_blocker_missing:{artifact_id}")
    if onsps_smoke.get("no_sites_blocked_reason") != "no_onsps_sites":
        errors.append(f"kpi_onsps_backmap_no_sites_blocker_missing:{artifact_id}")
    if onsps_smoke.get("hbond_onsps_schema_version") != "onsps_backmap_evidence_v1":
        errors.append(f"kpi_hbond_onsps_backmap_schema_missing:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_forcefield_bridge_smoke", "ready"):
        errors.append(f"kpi_core_forcefield_bridge_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_compatibility_layer_smoke", "ready"):
        errors.append(f"kpi_core_compatibility_layer_smoke_not_ready:{artifact_id}")
    core_forcefield_smoke = (
        payload.get("product_kpi", {}).get("core_forcefield_bridge_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(core_forcefield_smoke, dict):
        core_forcefield_smoke = {}
    if core_forcefield_smoke.get("result_claim_safe") is not True:
        errors.append(f"kpi_core_forcefield_bridge_claim_not_safe:{artifact_id}")
    if core_forcefield_smoke.get("force_term_claim_metadata_ready") is not True:
        errors.append(f"kpi_core_forcefield_bridge_claim_metadata_not_ready:{artifact_id}")
    if core_forcefield_smoke.get("force_term_plugins") != ["legacy_lj"]:
        errors.append(f"kpi_core_forcefield_bridge_plugins_invalid:{artifact_id}")
    if core_forcefield_smoke.get("energy_shape") != [1]:
        errors.append(f"kpi_core_forcefield_bridge_energy_shape_invalid:{artifact_id}")
    if not isinstance(core_forcefield_smoke.get("forces_shape"), list):
        errors.append(f"kpi_core_forcefield_bridge_forces_shape_missing:{artifact_id}")
    if (
        core_forcefield_smoke.get("neighbor_diagnostics_ready") is not True
        or _int_value(core_forcefield_smoke.get("neighbor_pair_count")) < 1
        or core_forcefield_smoke.get("neighbor_pairs_provided") is not False
        or core_forcefield_smoke.get("neighbor_source") != "full_neighbor_pairs"
    ):
        errors.append(f"kpi_core_forcefield_bridge_neighbor_diagnostics_missing:{artifact_id}")
    if core_forcefield_smoke.get("bridge_execution_scope") != "metadata_contract_only_not_runtime_gpu_claim":
        errors.append(f"kpi_core_forcefield_bridge_scope_invalid:{artifact_id}")
    core_compat_smoke = (
        payload.get("product_kpi", {}).get("core_compatibility_layer_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(core_compat_smoke, dict):
        core_compat_smoke = {}
    compat_rows = core_compat_smoke.get("rows")
    if not isinstance(compat_rows, list):
        compat_rows = []
    expected_compat_contracts = {
        "onsps_backmap_shim": ("core.onsps_backmap", "betelgeuze_engine.backmapping.onsps", "import_identity"),
        "topology_protein_bridge": ("core.topology", "betelgeuze_engine.topology.protein", "engine_dataclass_bridge"),
        "forcefield_product_bridge": ("core.forcefield", "betelgeuze_engine.physics", "energy_forces_claim_metadata_bridge"),
    }
    compat_by_contract = {
        str(row.get("contract") or ""): row
        for row in compat_rows
        if isinstance(row, dict)
    }
    if int(core_compat_smoke.get("row_count") or 0) != len(expected_compat_contracts):
        errors.append(f"kpi_core_compatibility_layer_row_count_invalid:{artifact_id}")
    if set(compat_by_contract) != set(expected_compat_contracts):
        errors.append(f"kpi_core_compatibility_layer_contracts_invalid:{artifact_id}")
    for contract, (legacy_module, canonical_module, bridge_type) in expected_compat_contracts.items():
        row = compat_by_contract.get(contract)
        if not isinstance(row, dict):
            continue
        if row.get("ready") is not True:
            errors.append(f"kpi_core_compatibility_layer_row_not_ready:{artifact_id}:{contract}")
        if row.get("legacy_module") != legacy_module:
            errors.append(f"kpi_core_compatibility_layer_legacy_module_invalid:{artifact_id}:{contract}")
        if row.get("canonical_module") != canonical_module:
            errors.append(f"kpi_core_compatibility_layer_canonical_module_invalid:{artifact_id}:{contract}")
        if row.get("bridge_type") != bridge_type:
            errors.append(f"kpi_core_compatibility_layer_bridge_type_invalid:{artifact_id}:{contract}")
        if str(row.get("error") or ""):
            errors.append(f"kpi_core_compatibility_layer_row_error:{artifact_id}:{contract}")
    topology_row = compat_by_contract.get("topology_protein_bridge", {})
    if isinstance(topology_row, dict):
        if topology_row.get("topology_fidelity") != "sequence_mapped":
            errors.append(f"kpi_core_topology_bridge_fidelity_invalid:{artifact_id}")
        if topology_row.get("protein_topology_type") != "ProteinTopology":
            errors.append(f"kpi_core_topology_bridge_type_invalid:{artifact_id}")
        if _int_value(topology_row.get("hbond_role_count")) < 1:
            errors.append(f"kpi_core_topology_bridge_hbond_roles_missing:{artifact_id}")
    forcefield_row = compat_by_contract.get("forcefield_product_bridge", {})
    if isinstance(forcefield_row, dict):
        if forcefield_row.get("result_claim_safe") is not True:
            errors.append(f"kpi_core_forcefield_compat_claim_not_safe:{artifact_id}")
        if forcefield_row.get("force_term_claim_metadata_ready") is not True:
            errors.append(f"kpi_core_forcefield_compat_claim_metadata_not_ready:{artifact_id}")
        if forcefield_row.get("force_term_plugins") != ["legacy_lj"]:
            errors.append(f"kpi_core_forcefield_compat_plugins_invalid:{artifact_id}")
        if (
            forcefield_row.get("neighbor_diagnostics_ready") is not True
            or _int_value(forcefield_row.get("neighbor_pair_count")) < 1
            or forcefield_row.get("neighbor_pairs_provided") is not False
            or forcefield_row.get("neighbor_source") != "full_neighbor_pairs"
        ):
            errors.append(f"kpi_core_forcefield_compat_neighbor_diagnostics_missing:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "job_store_lazy_factory_smoke", "ready"):
        errors.append(f"kpi_job_store_lazy_factory_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "allowlisted_runner_shim_contract", "ready"):
        errors.append(f"kpi_allowlisted_runner_shim_contract_smoke_not_ready:{artifact_id}")
    runner_shim = (
        payload.get("product_kpi", {}).get("allowlisted_runner_shim_contract", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(runner_shim, dict):
        runner_shim = {}
    runner_rows = runner_shim.get("rows")
    if not isinstance(runner_rows, list):
        runner_rows = []
    expected_runner_count = len(EXPECTED_ALLOWLISTED_RUNNER_SHIMS)
    if _int_value(runner_shim.get("runner_count")) != expected_runner_count:
        errors.append(f"kpi_allowlisted_runner_shim_runner_count_mismatch:{artifact_id}")
    if len(runner_rows) != expected_runner_count:
        errors.append(f"kpi_allowlisted_runner_shim_rows_count_mismatch:{artifact_id}")
    rows_by_profile = {
        str(row.get("profile_id") or ""): row
        for row in runner_rows
        if isinstance(row, dict)
    }
    expected_profile_ids = {entry["profile_id"] for entry in EXPECTED_ALLOWLISTED_RUNNER_SHIMS}
    if set(rows_by_profile) != expected_profile_ids:
        errors.append(f"kpi_allowlisted_runner_shim_profile_identities_invalid:{artifact_id}")
    for entry in EXPECTED_ALLOWLISTED_RUNNER_SHIMS:
        profile_id = entry["profile_id"]
        row = rows_by_profile.get(profile_id)
        if not isinstance(row, dict):
            errors.append(f"kpi_allowlisted_runner_shim_row_missing:{artifact_id}:{profile_id}")
            continue
        if str(row.get("profile_id") or "") != profile_id:
            errors.append(f"kpi_allowlisted_runner_shim_profile_id_invalid:{artifact_id}:{profile_id}")
        if str(row.get("runner_script") or "") != entry["runner_script"]:
            errors.append(f"kpi_allowlisted_runner_shim_runner_script_invalid:{artifact_id}:{profile_id}")
        if str(row.get("profile_runner_script") or "") != entry["runner_script"]:
            errors.append(f"kpi_allowlisted_runner_shim_profile_runner_script_invalid:{artifact_id}:{profile_id}")
        if str(row.get("adapter_import") or "") != entry["adapter_import"]:
            errors.append(f"kpi_allowlisted_runner_shim_adapter_import_invalid:{artifact_id}:{profile_id}")
        if row.get("adapter_import_present") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_adapter_import_not_present:{artifact_id}:{profile_id}")
        if row.get("shim_contract_type") != "canonical_module_alias":
            errors.append(f"kpi_allowlisted_runner_shim_contract_type_invalid:{artifact_id}:{profile_id}")
        if row.get("sys_modules_alias_ready") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_sys_modules_alias_not_ready:{artifact_id}:{profile_id}")
        if row.get("self_implementation_blocked") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_self_implementation_not_blocked:{artifact_id}:{profile_id}")
        if row.get("runtime_adapter_identity_ready") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_runtime_adapter_identity_not_ready:{artifact_id}:{profile_id}")
        missing_symbols = row.get("missing_runtime_symbols")
        if not isinstance(missing_symbols, list) or missing_symbols:
            errors.append(f"kpi_allowlisted_runner_shim_missing_runtime_symbols:{artifact_id}:{profile_id}")
        if str(row.get("runtime_adapter_error") or ""):
            errors.append(f"kpi_allowlisted_runner_shim_runtime_adapter_error:{artifact_id}:{profile_id}")
        if str(row.get("error") or ""):
            errors.append(f"kpi_allowlisted_runner_shim_row_error:{artifact_id}:{profile_id}")
        if row.get("ready") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_row_not_ready:{artifact_id}:{profile_id}")
        script_hash = str(row.get("script_hash") or "")
        profile_hash = str(row.get("profile_runner_script_sha256") or "")
        if not script_hash or not profile_hash or script_hash != profile_hash:
            errors.append(f"kpi_allowlisted_runner_shim_hash_mismatch:{artifact_id}:{profile_id}")
        if row.get("hash_matches") is not True:
            errors.append(f"kpi_allowlisted_runner_shim_hash_matches_not_true:{artifact_id}:{profile_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "runner_claim_metadata_signed"):
        errors.append(f"pm_runner_claim_metadata_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "signed_manifest_verification_pass"):
        errors.append(f"pm_signed_manifest_verification_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "runner_profile_validation_pass"):
        errors.append(f"pm_runner_profile_validation_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "force_term_claim_metadata_ready"):
        errors.append(f"pm_force_term_claim_metadata_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "force_term_result_contract_ready"):
        errors.append(f"pm_force_term_result_contract_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "guarded_force_term_plugin_ready"):
        errors.append(f"pm_guarded_force_term_plugin_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "onsps_backmap_evidence_schema_ready"):
        errors.append(f"pm_onsps_backmap_evidence_schema_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "core_forcefield_bridge_ready"):
        errors.append(f"pm_core_forcefield_bridge_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "core_compatibility_layer_ready"):
        errors.append(f"pm_core_compatibility_layer_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "job_store_lazy_factory_ready"):
        errors.append(f"pm_job_store_lazy_factory_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "allowlisted_runner_shim_contract_ready"):
        errors.append(f"pm_allowlisted_runner_shim_contract_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "source_artifacts_fresh"):
        errors.append(f"pm_source_artifacts_fresh_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "blocked_claim_correctly_blocked"):
        errors.append(f"kpi_blocked_claim_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "blocked_claim_correctly_blocked"):
        errors.append(f"pm_blocked_claim_gate_missing:{artifact_id}")
    product_kpi = payload.get("product_kpi")
    if not isinstance(product_kpi, dict):
        product_kpi = {}
    pm_product = (
        payload.get("pm_kpi_summary", {}).get("product", {})
        if isinstance(payload.get("pm_kpi_summary"), dict)
        else {}
    )
    if not isinstance(pm_product, dict):
        pm_product = {}
    if (product_kpi.get("bundle_validation_pass") is True) != (
        pm_product.get("bundle_validation_pass") is True
    ):
        errors.append(f"pm_product_bundle_validation_gate_mismatch:{artifact_id}")
    if _int_value(pm_product.get("clean_install_missing_requirement_count")) != _int_value(
        product_kpi.get("clean_install_missing_requirement_count")
    ):
        errors.append(f"pm_product_clean_install_missing_count_mismatch:{artifact_id}")
    if list(pm_product.get("clean_install_missing_requirements") or []) != list(
        product_kpi.get("clean_install_missing_requirements") or []
    ):
        errors.append(f"pm_product_clean_install_missing_requirements_mismatch:{artifact_id}")
    if list(pm_product.get("product_image_preflight_blocker_codes") or []) != list(
        product_kpi.get("product_image_preflight_blocker_codes") or []
    ):
        errors.append(f"pm_product_image_preflight_blocker_codes_mismatch:{artifact_id}")
    if _int_value(pm_product.get("clean_container_missing_requirement_count")) != _int_value(
        product_kpi.get("clean_container_missing_requirement_count")
    ):
        errors.append(f"pm_product_clean_container_missing_count_mismatch:{artifact_id}")
    if list(pm_product.get("clean_container_missing_requirements") or []) != list(
        product_kpi.get("clean_container_missing_requirements") or []
    ):
        errors.append(f"pm_product_clean_container_missing_requirements_mismatch:{artifact_id}")
    if _int_value(pm_product.get("source_artifact_fresh_count")) != _int_value(
        product_kpi.get("source_artifact_fresh_count")
    ):
        errors.append(f"pm_product_source_artifact_fresh_count_mismatch:{artifact_id}")
    if _int_value(pm_product.get("source_artifact_stale_count")) != _int_value(
        product_kpi.get("source_artifact_stale_count")
    ):
        errors.append(f"pm_product_source_artifact_stale_count_mismatch:{artifact_id}")
    if list(pm_product.get("source_artifact_stale_ids") or []) != list(
        product_kpi.get("source_artifact_stale_ids") or []
    ):
        errors.append(f"pm_product_source_artifact_stale_ids_mismatch:{artifact_id}")
    if _int_value(pm_product.get("enabled_profile_count")) != _int_value(
        product_kpi.get("enabled_profile_count")
    ):
        errors.append(f"pm_product_enabled_profile_count_mismatch:{artifact_id}")
    if _int_value(pm_product.get("failed_profile_count")) != _int_value(
        product_kpi.get("failed_profile_count")
    ):
        errors.append(f"pm_product_failed_profile_count_mismatch:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_bounded_policy_ready"):
        errors.append(f"pm_force_residual_bounded_policy_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_observed_caps_ready"):
        errors.append(f"pm_force_residual_observed_caps_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_contract_ready"):
        errors.append(f"pm_force_residual_contract_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_confidence_abstention_ready"):
        errors.append(f"pm_force_residual_confidence_abstention_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_top_k_policy_ready"):
        errors.append(f"pm_force_residual_top_k_policy_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "score_only_1k_runtime_tracked"):
        errors.append(f"pm_score_only_1k_runtime_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "top100_4bead_rescoring_runtime_tracked"):
        errors.append(f"pm_top100_4bead_rescoring_runtime_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "top10_force_residual_runtime_tracked"):
        errors.append(f"pm_top10_force_residual_runtime_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "memory_peak_tracked"):
        errors.append(f"pm_memory_peak_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "neighbor_list_rebuild_frequency_tracked"):
        errors.append(f"pm_neighbor_list_rebuild_frequency_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "force_term_physics_validation_ready"):
        errors.append(f"pm_force_term_physics_validation_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "force_term_physics_validation_claim_safe_ready"):
        errors.append(f"pm_force_term_physics_validation_claim_safe_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "finite_difference_force_error_pass"):
        errors.append(f"pm_finite_difference_force_error_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "energy_drift_pass"):
        errors.append(f"pm_energy_drift_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "neighbor_list_parity_pass"):
        errors.append(f"pm_neighbor_list_parity_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "topology_invalid_rate_pass"):
        errors.append(f"pm_topology_invalid_rate_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "backmapping_failure_rate_pass"):
        errors.append(f"pm_backmapping_failure_rate_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "hbond_evidence_schema_ready"):
        errors.append(f"pm_hbond_evidence_schema_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "ligand_topology_validity_schema_ready"):
        errors.append(f"pm_ligand_topology_validity_schema_gate_missing:{artifact_id}")
    if _int_value(
        payload.get("pm_kpi_summary", {}).get("chemistry", {}).get("hbond_recovery_pose_count")
        if isinstance(payload.get("pm_kpi_summary"), dict)
        else 0
    ) < 1:
        errors.append(f"pm_hbond_recovery_pose_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "unsatisfied_donor_acceptor_detection"):
        errors.append(f"pm_unsatisfied_donor_acceptor_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "overanchored_decoy_rejection"):
        errors.append(f"pm_overanchored_decoy_rejection_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "chirality_preservation_ready"):
        errors.append(f"pm_chirality_preservation_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "ring_validity_ready"):
        errors.append(f"pm_ring_validity_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "tautomer_validity_ready"):
        errors.append(f"pm_tautomer_validity_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "chemistry", "protonation_validity_ready"):
        errors.append(f"pm_protonation_validity_gate_missing:{artifact_id}")
    pose_benchmark = payload.get("pose_ranking_hbond_benchmark")
    if not isinstance(pose_benchmark, dict):
        pose_benchmark = {}
    pm_chemistry = (
        payload.get("pm_kpi_summary", {}).get("chemistry", {})
        if isinstance(payload.get("pm_kpi_summary"), dict)
        else {}
    )
    if not isinstance(pm_chemistry, dict):
        pm_chemistry = {}
    if _int_value(pm_chemistry.get("hbond_evidence_schema_ready_count")) != _int_value(
        chemistry.get("hbond_evidence_schema_ready_count")
    ):
        errors.append(f"pm_chemistry_hbond_schema_ready_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("ligand_topology_validity_schema_ready_count")) != _int_value(
        chemistry.get("ligand_topology_validity_schema_ready_count")
    ):
        errors.append(f"pm_chemistry_ligand_topology_schema_ready_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("hbond_donor_site_count")) != _int_value(
        chemistry.get("hbond_donor_site_count")
    ):
        errors.append(f"pm_chemistry_hbond_donor_site_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("hbond_acceptor_site_count")) != _int_value(
        chemistry.get("hbond_acceptor_site_count")
    ):
        errors.append(f"pm_chemistry_hbond_acceptor_site_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("hbond_recovery_fixture_count")) != _int_value(
        chemistry.get("hbond_recovery_fixture_count")
    ):
        errors.append(f"pm_chemistry_hbond_recovery_fixture_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("hbond_recovery_pose_count")) != _int_value(
        pose_benchmark.get("hbond_recovery_pose_count")
    ):
        errors.append(f"pm_chemistry_hbond_recovery_pose_count_mismatch:{artifact_id}")
    if list(pm_chemistry.get("hbond_recovery_pose_ids") or []) != list(
        pose_benchmark.get("hbond_recovery_pose_ids") or []
    ):
        errors.append(f"pm_chemistry_hbond_recovery_pose_ids_mismatch:{artifact_id}")
    if _float_value(pm_chemistry.get("hbond_recovery_confidence_min")) != _float_value(
        pose_benchmark.get("hbond_recovery_confidence_min")
    ):
        errors.append(f"pm_chemistry_hbond_recovery_confidence_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("unsatisfied_donor_acceptor_fixture_count")) != _int_value(
        chemistry.get("unsatisfied_donor_acceptor_fixture_count")
    ):
        errors.append(f"pm_chemistry_unsatisfied_fixture_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("unsatisfied_donor_count")) != _int_value(
        chemistry.get("unsatisfied_donor_count")
    ):
        errors.append(f"pm_chemistry_unsatisfied_donor_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("unsatisfied_acceptor_count")) != _int_value(
        chemistry.get("unsatisfied_acceptor_count")
    ):
        errors.append(f"pm_chemistry_unsatisfied_acceptor_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("unsatisfied_donor_acceptor_pose_count")) != _int_value(
        pose_benchmark.get("unsatisfied_donor_acceptor_pose_count")
    ):
        errors.append(f"pm_chemistry_unsatisfied_pose_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("chirality_preservation_fixture_count")) != _int_value(
        chemistry.get("chirality_preservation_fixture_count")
    ):
        errors.append(f"pm_chemistry_chirality_fixture_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("unassigned_chirality_blocked_fixture_count")) != _int_value(
        chemistry.get("unassigned_chirality_blocked_fixture_count")
    ):
        errors.append(f"pm_chemistry_unassigned_chirality_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("ring_validity_fixture_count")) != _int_value(
        chemistry.get("ring_validity_fixture_count")
    ):
        errors.append(f"pm_chemistry_ring_fixture_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("tautomer_validity_fixture_count")) != _int_value(
        chemistry.get("tautomer_validity_fixture_count")
    ):
        errors.append(f"pm_chemistry_tautomer_fixture_count_mismatch:{artifact_id}")
    if _int_value(pm_chemistry.get("protonation_validity_fixture_count")) != _int_value(
        chemistry.get("protonation_validity_fixture_count")
    ):
        errors.append(f"pm_chemistry_protonation_fixture_count_mismatch:{artifact_id}")
    if pose_benchmark.get("benchmark_ready") is not True:
        errors.append(f"kpi_pose_ranking_hbond_benchmark_not_ready:{artifact_id}")
    if pose_benchmark.get("top1_pose_id") != pose_benchmark.get("top1_expected_pose_id"):
        errors.append(f"kpi_pose_ranking_top1_not_expected:{artifact_id}")
    if _int_value(pose_benchmark.get("hbond_recovery_pose_count")) < 1:
        errors.append(f"kpi_pose_ranking_hbond_recovery_missing:{artifact_id}")
    if pose_benchmark.get("overanchored_decoys_blocked") is not True:
        errors.append(f"kpi_pose_ranking_overanchored_decoy_not_blocked:{artifact_id}")
    if pose_benchmark.get("unsatisfied_donor_acceptor_detected") is not True:
        errors.append(f"kpi_pose_ranking_unsatisfied_donor_acceptor_missing:{artifact_id}")
    required_pose_roles = {
        "hbond_recovery_pose",
        "unsatisfied_donor_pose",
        "far_decoy_pose",
        "overanchored_decoy_pose",
        "invalid_ligand_pose",
    }
    observed_pose_roles = {
        str(role)
        for role in pose_benchmark.get("observed_pose_roles", [])
        if str(role)
    }
    pose_rows = pose_benchmark.get("rows")
    if not isinstance(pose_rows, list) or not pose_rows:
        errors.append(f"kpi_pose_ranking_rows_missing:{artifact_id}")
        pose_rows = []
    row_roles = {
        str(row.get("benchmark_role") or "")
        for row in pose_rows
        if isinstance(row, dict) and str(row.get("benchmark_role") or "")
    }
    if not required_pose_roles.issubset(observed_pose_roles | row_roles):
        errors.append(f"kpi_pose_ranking_required_roles_missing:{artifact_id}")
    if pose_benchmark.get("row_contracts_ready") is not True:
        errors.append(f"kpi_pose_ranking_row_contracts_not_ready:{artifact_id}")
    for row in pose_rows:
        if not isinstance(row, dict):
            errors.append(f"kpi_pose_ranking_row_invalid:{artifact_id}")
            continue
        pose_id = str(row.get("pose_id") or "unknown_pose")
        if row.get("benchmark_contract_pass") is not True:
            errors.append(f"kpi_pose_ranking_row_contract_failed:{artifact_id}:{pose_id}")
        if not isinstance(row.get("benchmark_contract_checks"), dict):
            errors.append(f"kpi_pose_ranking_row_contract_checks_missing:{artifact_id}:{pose_id}")
        if row.get("hbond_schema_ready") is not True:
            errors.append(f"kpi_pose_ranking_row_hbond_schema_not_ready:{artifact_id}:{pose_id}")
        if row.get("hbond_threshold_schema_ready") is not True:
            errors.append(f"kpi_pose_ranking_row_hbond_threshold_schema_not_ready:{artifact_id}:{pose_id}")
        if row.get("hbond_pair_schema_ready") is not True:
            errors.append(f"kpi_pose_ranking_row_hbond_pair_schema_not_ready:{artifact_id}:{pose_id}")
        if row.get("hbond_geometry_flags_ready") is not True:
            errors.append(f"kpi_pose_ranking_row_hbond_geometry_flags_not_ready:{artifact_id}:{pose_id}")
        if row.get("hbond_claim_safe") is not row.get("expected_claim_safe"):
            errors.append(f"kpi_pose_ranking_row_claim_expectation_mismatch:{artifact_id}:{pose_id}")
        expected_blocked_reason = str(row.get("expected_blocked_reason") or "")
        if str(row.get("hbond_blocked_reason") or "") != expected_blocked_reason:
            errors.append(f"kpi_pose_ranking_row_blocked_reason_mismatch:{artifact_id}:{pose_id}")
    if _int_value(pose_benchmark.get("fixture_count")) != len(pose_rows):
        errors.append(f"kpi_pose_ranking_fixture_count_mismatch:{artifact_id}")
    expected_row_contract_pass_count = sum(
        1
        for row in pose_rows
        if isinstance(row, dict) and row.get("benchmark_contract_pass") is True
    )
    if _int_value(pose_benchmark.get("row_contract_pass_count")) != expected_row_contract_pass_count:
        errors.append(f"kpi_pose_ranking_row_contract_pass_count_mismatch:{artifact_id}")
    canonical_required_roles = {
        "hbond_recovery_pose",
        "unsatisfied_donor_pose",
        "far_decoy_pose",
        "overanchored_decoy_pose",
        "invalid_ligand_pose",
    }
    payload_required_roles = {
        str(role)
        for role in (pose_benchmark.get("required_pose_roles") or [])
        if str(role)
    }
    if payload_required_roles != canonical_required_roles:
        errors.append(f"kpi_pose_ranking_required_pose_roles_drift:{artifact_id}")
    row_role_set = {
        str(row.get("benchmark_role") or "")
        for row in pose_rows
        if isinstance(row, dict) and str(row.get("benchmark_role") or "")
    }
    payload_observed_roles = {
        str(role)
        for role in (pose_benchmark.get("observed_pose_roles") or [])
        if str(role)
    }
    if payload_observed_roles != row_role_set:
        errors.append(f"kpi_pose_ranking_observed_pose_roles_drift:{artifact_id}")
    ranking_order = pose_benchmark.get("ranking_order")
    if not isinstance(ranking_order, list) or not ranking_order:
        errors.append(f"kpi_pose_ranking_ranking_order_missing:{artifact_id}")
        ranking_order_str: list[str] = []
    else:
        ranking_order_str = [str(pose_id) for pose_id in ranking_order]
    row_pose_ids = [
        str(row.get("pose_id") or "")
        for row in pose_rows
        if isinstance(row, dict) and str(row.get("pose_id") or "")
    ]
    if sorted(ranking_order_str) != sorted(row_pose_ids):
        errors.append(f"kpi_pose_ranking_ranking_order_membership_drift:{artifact_id}")
    if len(set(ranking_order_str)) != len(ranking_order_str):
        errors.append(f"kpi_pose_ranking_ranking_order_duplicates:{artifact_id}")
    if ranking_order_str and str(pose_benchmark.get("top1_pose_id") or "") != ranking_order_str[0]:
        errors.append(f"kpi_pose_ranking_top1_not_ranking_order_head:{artifact_id}")
    rows_by_pose_id = {
        str(row.get("pose_id") or ""): row
        for row in pose_rows
        if isinstance(row, dict) and str(row.get("pose_id") or "")
    }
    hbond_recovery_rows = [
        row
        for row in pose_rows
        if isinstance(row, dict)
        and str(row.get("benchmark_role") or "") == "hbond_recovery_pose"
        and row.get("hbond_claim_safe") is True
    ]
    if _int_value(pose_benchmark.get("hbond_recovery_pose_count")) != len(hbond_recovery_rows):
        errors.append(f"kpi_pose_ranking_hbond_recovery_count_drift:{artifact_id}")
    payload_recovery_ids = [
        str(pose_id) for pose_id in (pose_benchmark.get("hbond_recovery_pose_ids") or [])
    ]
    expected_recovery_ids = [str(row.get("pose_id") or "") for row in hbond_recovery_rows]
    if payload_recovery_ids != expected_recovery_ids:
        errors.append(f"kpi_pose_ranking_hbond_recovery_ids_drift:{artifact_id}")
    top1_pose_id = str(pose_benchmark.get("top1_pose_id") or "")
    if top1_pose_id and top1_pose_id not in rows_by_pose_id:
        errors.append(f"kpi_pose_ranking_top1_pose_id_not_in_rows:{artifact_id}")
    elif top1_pose_id:
        top1_row = rows_by_pose_id[top1_pose_id]
        if str(top1_row.get("benchmark_role") or "") != "hbond_recovery_pose":
            errors.append(f"kpi_pose_ranking_top1_role_not_hbond_recovery:{artifact_id}")
        if top1_row.get("hbond_claim_safe") is not True:
            errors.append(f"kpi_pose_ranking_top1_not_claim_safe:{artifact_id}")
    overanchored_rows = [
        row
        for row in pose_rows
        if isinstance(row, dict)
        and str(row.get("benchmark_role") or "") == "overanchored_decoy_pose"
    ]
    expected_overanchored_blocked = bool(overanchored_rows) and all(
        row.get("hbond_claim_safe") is False for row in overanchored_rows
    )
    if (pose_benchmark.get("overanchored_decoys_blocked") is True) != expected_overanchored_blocked:
        errors.append(f"kpi_pose_ranking_overanchored_summary_drift:{artifact_id}")
    unsatisfied_rows = [
        row
        for row in pose_rows
        if isinstance(row, dict)
        and (
            _int_value(row.get("unsatisfied_donor_count")) > 0
            or _int_value(row.get("unsatisfied_acceptor_count")) > 0
        )
    ]
    if (pose_benchmark.get("unsatisfied_donor_acceptor_detected") is True) != bool(unsatisfied_rows):
        errors.append(f"kpi_pose_ranking_unsatisfied_detected_summary_drift:{artifact_id}")
    if _int_value(pose_benchmark.get("unsatisfied_donor_acceptor_pose_count")) != len(unsatisfied_rows):
        errors.append(f"kpi_pose_ranking_unsatisfied_pose_count_drift:{artifact_id}")
    for role in (
        "far_decoy_pose",
        "overanchored_decoy_pose",
        "unsatisfied_donor_pose",
        "invalid_ligand_pose",
    ):
        role_rows = [
            row
            for row in pose_rows
            if isinstance(row, dict)
            and str(row.get("benchmark_role") or "") == role
        ]
        if not role_rows:
            continue
        if not all(row.get("hbond_claim_safe") is False for row in role_rows):
            errors.append(f"kpi_pose_ranking_blocked_role_not_blocked:{artifact_id}:{role}")
    return errors


def _rocm_product_runtime_ready(rocm_summary: dict[str, Any]) -> bool:
    visible_device_count = int(rocm_summary.get("visible_device_count") or 0)
    production_execution_ready = rocm_summary.get("production_execution_ready")
    production_ready = bool(production_execution_ready) if production_execution_ready is not None else visible_device_count > 0
    return bool(
        rocm_summary.get("commercial_compute_default") == "rocm_hip"
        and rocm_summary.get("torch_rocm_ready") is True
        and visible_device_count > 0
        and rocm_summary.get("device_nodes_ready", True) is True
        and production_ready
        and rocm_summary.get("cpu_fallback_allowed_for_product", False) is False
    )


def _default_artifacts(
    *,
    kpi_json: str,
    kpi_md: str,
    rocm_manifest_json: str,
    product_image_preflight_json: str,
    product_image_receipt_json: str,
    next_steps_doc: str,
) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": "ai_md_engine_kpi_report_json",
            "artifact_path": kpi_json,
            "role": "local_pc_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "ai_md_engine_kpi_report_md",
            "artifact_path": kpi_md,
            "role": "human_readable_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "rocm_environment_manifest_json",
            "artifact_path": rocm_manifest_json,
            "role": "gpu_rocm_hip_runtime_gate",
            "required": True,
        },
        {
            "artifact_id": "product_image_smoke_preflight_json",
            "artifact_path": product_image_preflight_json,
            "role": "clean_container_smoke_gate",
            "required": True,
        },
        {
            "artifact_id": "product_image_smoke_receipt_json",
            "artifact_path": product_image_receipt_json,
            "role": "clean_container_rocm_runtime_receipt",
            "required": False,
        },
        {
            "artifact_id": "next_steps_doc",
            "artifact_path": next_steps_doc,
            "role": "engineering_plan",
            "required": True,
        },
        {
            "artifact_id": "product_dockerfile",
            "artifact_path": "Dockerfile.product",
            "role": "rocm_hip_rust_container_contract",
            "required": True,
        },
        {
            "artifact_id": "product_rocm_requirements",
            "artifact_path": "requirements-product-rocm.txt",
            "role": "torch_rocm_dependency_contract",
            "required": True,
        },
        {
            "artifact_id": "product_rocm_requirements_profile",
            "artifact_path": "requirements-rocm.txt",
            "role": "torch_rocm_dependency_profile",
            "required": True,
        },
        {
            "artifact_id": "product_requirements_base",
            "artifact_path": "requirements-base.txt",
            "role": "shared_non_torch_dependency_profile",
            "required": True,
        },
        {
            "artifact_id": "backmapping_runner_profile",
            "artifact_path": "config/api_validated_runner_profiles/backmapping_scoring.production.json",
            "role": "allowlisted_runner_profile",
            "required": True,
        },
        {
            "artifact_id": "product_end_to_end_rocm_benchmark_json",
            "artifact_path": "runs/product_end_to_end_rocm_benchmark_current.json",
            "role": "optional_end_to_end_rocm_benchmark",
            "required": False,
        },
    ]


def _artifact_rows(artifact_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in artifact_specs:
        artifact_path = str(spec.get("artifact_path") or "")
        path = _resolve(artifact_path)
        key = f"{spec.get('artifact_id')}::{path}"
        if key in seen:
            continue
        seen.add(key)
        exists = path.exists() and path.is_file()
        rows.append(
            {
                "artifact_id": str(spec.get("artifact_id") or path.name),
                "artifact_path": artifact_path,
                "role": str(spec.get("role") or "evidence"),
                "required": bool(spec.get("required", True)),
                "exists": exists,
                "missing": not exists,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size if exists else 0,
                "bundle_arcname": _arcname(path) if exists else "",
                "included_in_bundle": exists,
                "release_blocker": bool(spec.get("required", True) and not exists),
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return rows


def _write_tar(path_like: str | Path, rows: list[dict[str, Any]]) -> tuple[bool, int, int, str]:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    included = [row for row in rows if row["included_in_bundle"] is True]
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for row in included:
            tar.add(_resolve(str(row["artifact_path"])), arcname=str(row["bundle_arcname"]), recursive=False)
    return path.exists(), path.stat().st_size if path.exists() else 0, len(included), _sha256_file(path)


def validate_product_evidence_bundle(
    *,
    bundle_packet: dict[str, Any],
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    summary = _summary(bundle_packet)
    rows = [dict(row) for row in bundle_packet.get("rows") or [] if isinstance(row, dict)]
    included_rows = [row for row in rows if row.get("included_in_bundle") is True]
    errors: list[str] = []
    kpi_rows = [
        row
        for row in included_rows
        if str(row.get("role") or "") == "local_pc_runtime_report"
        and str(row.get("bundle_arcname") or "")
    ]
    kpi_claim_metadata_gate_count = 0
    kpi_claim_metadata_gate_validated_count = 0

    tar_path_text = str(summary.get("bundle_tar_path") or "")
    tar_path = Path(tar_path_text)
    if tar_path_text:
        tar_path = tar_path if tar_path.is_absolute() else root_path / tar_path
    tar_member_sha256: dict[str, str] = {}
    if not tar_path_text or not tar_path.exists() or not tar_path.is_file():
        errors.append("bundle_tar_missing")
        tar_names: set[str] = set()
        tar_sha = ""
    else:
        tar_sha = _sha256_file(tar_path)
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                members = [member for member in tar.getmembers() if member.isfile()]
                tar_names = {member.name for member in members}
                kpi_arcnames = {str(row.get("bundle_arcname") or "") for row in kpi_rows}
                for member in members:
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        errors.append(f"bundle_tar_member_unreadable:{member.name}")
                        continue
                    h = hashlib.sha256()
                    member_chunks: list[bytes] = []
                    collect_json = member.name in kpi_arcnames
                    for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                        h.update(chunk)
                        if collect_json:
                            member_chunks.append(chunk)
                    tar_member_sha256[member.name] = h.hexdigest()
                    if collect_json:
                        artifact_id = next(
                            str(row.get("artifact_id") or member.name)
                            for row in kpi_rows
                            if str(row.get("bundle_arcname") or "") == member.name
                        )
                        kpi_claim_metadata_gate_count += 1
                        try:
                            payload = json.loads(b"".join(member_chunks).decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            errors.append(f"kpi_json_unreadable:{artifact_id}")
                            continue
                        if not isinstance(payload, dict):
                            errors.append(f"kpi_json_not_object:{artifact_id}")
                            continue
                        kpi_errors = _validate_kpi_claim_metadata_gates(
                            artifact_id=artifact_id,
                            payload=payload,
                        )
                        errors.extend(kpi_errors)
                        if not kpi_errors:
                            kpi_claim_metadata_gate_validated_count += 1
        except tarfile.TarError:
            tar_names = set()
            errors.append("bundle_tar_unreadable")

    expected_names = {str(row.get("bundle_arcname") or "") for row in included_rows if row.get("bundle_arcname")}
    if tar_names != expected_names:
        errors.append("bundle_tar_members_mismatch")
    if int(summary.get("bundle_tar_member_count") or 0) != len(included_rows):
        errors.append("bundle_tar_member_count_mismatch")
    if tar_sha and str(summary.get("bundle_tar_sha256") or "") != tar_sha:
        errors.append("bundle_tar_sha256_mismatch")

    for row in rows:
        artifact_path = str(row.get("artifact_path") or "")
        path = Path(artifact_path)
        resolved = path if path.is_absolute() else root_path / path
        if row.get("included_in_bundle") is True:
            arcname = str(row.get("bundle_arcname") or "")
            member_sha = tar_member_sha256.get(arcname)
            if not member_sha:
                errors.append(f"bundle_tar_member_missing:{row.get('artifact_id')}")
                continue
            if str(row.get("sha256") or "") != member_sha:
                errors.append(f"artifact_sha256_mismatch:{row.get('artifact_id')}")
            continue
        if row.get("required") is True and not resolved.exists():
            errors.append(f"required_artifact_missing:{row.get('artifact_id')}")
            continue
        if row.get("exists") is True:
            actual_sha = _sha256_file(resolved)
            if actual_sha and str(row.get("sha256") or "") != actual_sha:
                errors.append(f"artifact_sha256_mismatch:{row.get('artifact_id')}")

    source_fresh_ids: list[str] = []
    source_stale_ids: list[str] = []
    for row in included_rows:
        artifact_path = str(row.get("artifact_path") or "")
        path = Path(artifact_path)
        resolved = path if path.is_absolute() else root_path / path
        artifact_id = str(row.get("artifact_id") or artifact_path)
        actual_sha = _sha256_file(resolved)
        expected_sha = str(row.get("sha256") or "")
        if actual_sha and actual_sha == expected_sha:
            source_fresh_ids.append(artifact_id)
        else:
            source_stale_ids.append(artifact_id)

    pass_ready = bool(summary.get("bundle_export_ready") is True and included_rows and not errors)
    return {
        "bundle_validation_pass": pass_ready,
        "bundle_validation_checked": True,
        "bundle_validation_error_count": len(errors),
        "bundle_validation_errors": errors,
        "bundle_validation_tar_member_count": len(tar_names),
        "bundle_validation_expected_member_count": len(expected_names),
        "kpi_claim_metadata_gate_count": kpi_claim_metadata_gate_count,
        "kpi_claim_metadata_gate_validated_count": kpi_claim_metadata_gate_validated_count,
        "kpi_claim_metadata_gates_validated": bool(
            kpi_claim_metadata_gate_count > 0
            and kpi_claim_metadata_gate_validated_count == kpi_claim_metadata_gate_count
        ),
        "source_artifacts_fresh": bool(included_rows and not source_stale_ids),
        "source_artifact_fresh_count": len(source_fresh_ids),
        "source_artifact_stale_count": len(source_stale_ids),
        "source_artifact_stale_ids": source_stale_ids,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_payload(
    *,
    kpi_packet: dict[str, Any],
    rocm_manifest_packet: dict[str, Any],
    product_image_preflight_packet: dict[str, Any],
    artifact_specs: list[dict[str, Any]],
    out_tar: str = DEFAULT_OUT_TAR,
) -> dict[str, Any]:
    rows = _artifact_rows(artifact_specs)
    missing_required = [row for row in rows if row["required"] is True and row["exists"] is not True]
    kpi_summary = _summary(kpi_packet)
    rocm_summary = _summary(rocm_manifest_packet)
    image_summary = _summary(product_image_preflight_packet)
    image_preflight_blocker_codes = [
        str(row.get("code") or "")
        for row in product_image_preflight_packet.get("blockers", [])
        if isinstance(row, dict) and str(row.get("code") or "")
    ]
    kpi_ready = bool(kpi_summary.get("status") == "ai_md_engine_kpi_report_ready" and kpi_summary.get("report_ready") is True)
    product_kpi = kpi_summary.get("product_kpi") if isinstance(kpi_summary.get("product_kpi"), dict) else {}
    pm_kpi_summary = kpi_summary.get("pm_kpi_summary") if isinstance(kpi_summary.get("pm_kpi_summary"), dict) else {}
    pm_chemistry = pm_kpi_summary.get("chemistry") if isinstance(pm_kpi_summary.get("chemistry"), dict) else {}
    kpi_failed_gate_ids = [
        str(gate_id)
        for gate_id in pm_kpi_summary.get("failed_gate_ids", [])
        if str(gate_id)
    ] if isinstance(pm_kpi_summary, dict) else []
    pose_benchmark = (
        kpi_summary.get("pose_ranking_hbond_benchmark")
        if isinstance(kpi_summary.get("pose_ranking_hbond_benchmark"), dict)
        else {}
    )
    runner_claim_metadata_signed = bool(product_kpi.get("runner_claim_metadata_signed") is True)
    runner_manifest_smoke = (
        product_kpi.get("runner_claim_metadata_manifest_smoke")
        if isinstance(product_kpi.get("runner_claim_metadata_manifest_smoke"), dict)
        else {}
    )
    force_residual_summary_signed = bool(
        runner_manifest_smoke.get("force_residual_summary_present") is True
        and runner_manifest_smoke.get("manifest_force_residual_schema_version")
        == "force_residual_claim_metadata_v1"
        and runner_manifest_smoke.get("manifest_force_residual_policy_caps_ready") is True
        and runner_manifest_smoke.get("manifest_force_residual_observed_caps_ready") is True
        and runner_manifest_smoke.get("manifest_force_residual_contract_ready") is True
    )
    force_term_claim_metadata_ready = bool(product_kpi.get("force_term_claim_metadata_ready") is True)
    force_term_result_contract_ready = bool(product_kpi.get("force_term_result_contract_ready") is True)
    guarded_force_term_plugin_ready = bool(product_kpi.get("guarded_force_term_plugin_ready") is True)
    onsps_backmap_evidence_schema_ready = bool(
        product_kpi.get("onsps_backmap_evidence_schema_ready") is True
    )
    core_forcefield_bridge_ready = bool(product_kpi.get("core_forcefield_bridge_ready") is True)
    core_compatibility_layer_ready = bool(product_kpi.get("core_compatibility_layer_ready") is True)
    job_store_lazy_factory_ready = bool(product_kpi.get("job_store_lazy_factory_ready") is True)
    allowlisted_runner_shim_contract_ready = bool(
        product_kpi.get("allowlisted_runner_shim_contract_ready") is True
    )
    chemistry_pm_gates_ready = bool(
        pm_chemistry.get("hbond_evidence_schema_ready") is True
        and pm_chemistry.get("ligand_topology_validity_schema_ready") is True
        and _int_value(pm_chemistry.get("hbond_recovery_pose_count")) >= 1
        and pm_chemistry.get("unsatisfied_donor_acceptor_detection") is True
        and pm_chemistry.get("overanchored_decoy_rejection") is True
        and pm_chemistry.get("chirality_preservation_ready") is True
        and pm_chemistry.get("ring_validity_ready") is True
        and pm_chemistry.get("tautomer_validity_ready") is True
        and pm_chemistry.get("protonation_validity_ready") is True
    )
    pose_ranking_hbond_benchmark_ready = bool(
        pose_benchmark.get("benchmark_ready") is True
        and pose_benchmark.get("top1_pose_id") == pose_benchmark.get("top1_expected_pose_id")
        and _int_value(pose_benchmark.get("hbond_recovery_pose_count")) >= 1
        and pose_benchmark.get("overanchored_decoys_blocked") is True
        and pose_benchmark.get("unsatisfied_donor_acceptor_detected") is True
        and pose_benchmark.get("row_contracts_ready") is True
    )
    rocm_ready = _rocm_product_runtime_ready(rocm_summary)
    image_hbond_evidence_receipt_ready = bool(
        image_summary.get("backmapping_hbond_evidence_receipt_ready") is True
        or (
            image_summary.get("backmapping_hbond_evidence_schema_version") == "hbond_evidence_v1"
            and image_summary.get("backmapping_hbond_claim_metadata_schema_version") == "hbond_evidence_v1"
            and _int_value(image_summary.get("backmapping_hbond_claim_metadata_schema_ready_row_count")) >= 1
            and _int_value(image_summary.get("backmapping_hbond_evaluated_row_count")) >= 1
        )
    )
    image_onsps_backmap_receipt_ready = bool(
        image_summary.get("backmapping_onsps_backmap_receipt_ready") is True
        or (
            image_summary.get("backmapping_onsps_backmap_schema_version") == "onsps_backmap_evidence_v1"
            and _int_value(image_summary.get("backmapping_onsps_backmap_claim_safe_row_count")) >= 1
        )
    )
    image_ligand_topology_receipt_ready = bool(
        image_summary.get("backmapping_ligand_topology_schema_version") == "ligand_topology_validity_v1"
        and _int_value(image_summary.get("backmapping_ligand_topology_schema_ready_row_count")) >= 1
        and (
            image_summary.get("backmapping_ligand_topology_receipt_ready") is True
            or (
                image_summary.get("backmapping_ligand_topology_valid") is True
            and image_summary.get("backmapping_ligand_topology_claim_safe") is True
            and _int_value(image_summary.get("backmapping_ligand_topology_claim_safe_row_count")) >= 1
            and _int_value(image_summary.get("backmapping_ligand_topology_invalid_row_count")) == 0
            )
        )
    )
    image_container_runtime_receipt_ready = bool(
        image_summary.get("container_runtime_receipt_ready") is True
        and image_summary.get("container_runtime_proof_schema_version") == "rocm_container_runtime_proof_v1"
        and image_summary.get("container_runtime_in_container") is True
        and image_summary.get("container_runtime_device_nodes_ready") is True
        and image_summary.get("container_runtime_torch_rocm_ready") is True
        and image_summary.get("container_runtime_torch_cuda_available") is True
        and _int_value(image_summary.get("container_runtime_visible_device_count")) > 0
        and image_summary.get("container_runtime_rust_hip_backend_enabled") is True
    )
    clean_container_requirements = {
        "clean_container_smoke_receipt_ready": image_summary.get("clean_container_smoke_ready") is True,
        "product_image_receipt_status_ready": image_summary.get("receipt_status") == "product_image_smoke_ready",
        "product_image_receipt_mode_rocm_runtime": image_summary.get("receipt_mode") == "rocm-runtime",
        "container_runtime_receipt_ready": image_container_runtime_receipt_ready,
        "product_runner_smoke_ready": image_summary.get("product_runner_smoke_ready") is True,
        "product_runner_claim_metadata_ready": image_summary.get("product_runner_claim_metadata_ready") is True,
        "tier_alpha_result_manifest_signature_verified": (
            image_summary.get("tier_alpha_result_manifest_signature_verified") is True
        ),
        "tier_alpha_result_manifest_completed": image_summary.get("tier_alpha_result_manifest_status") == "completed",
        "backmapping_runner_claim_metadata_ready": (
            image_summary.get("backmapping_runner_claim_metadata_ready") is True
        ),
        "backmapping_ligand_topology_receipt_ready": image_ligand_topology_receipt_ready,
        "backmapping_hbond_evidence_receipt_ready": image_hbond_evidence_receipt_ready,
        "backmapping_onsps_backmap_receipt_ready": image_onsps_backmap_receipt_ready,
        "simulate_missing_profile_returns_422": (
            _int_value(image_summary.get("receipt_simulate_missing_profile_http")) == 422
        ),
    }
    clean_container_missing_requirements = [
        requirement for requirement, passed in clean_container_requirements.items() if passed is not True
    ]
    clean_container_smoke_ready = bool(
        not clean_container_missing_requirements
    )
    bundle_input_ready = not missing_required and bool(rows)
    tar_exists = False
    tar_size = 0
    tar_member_count = 0
    tar_sha = ""
    if bundle_input_ready:
        tar_exists, tar_size, tar_member_count, tar_sha = _write_tar(out_tar, rows)
    bundle_ready = bool(bundle_input_ready and tar_exists and tar_sha)
    provisional_packet = {
        "summary": {
            "bundle_export_ready": bundle_ready,
            "bundle_tar_path": out_tar,
            "bundle_tar_sha256": tar_sha,
            "bundle_tar_member_count": tar_member_count,
        },
        "rows": rows,
    }
    validation = validate_product_evidence_bundle(bundle_packet=provisional_packet)
    product_claim_ready = bool(
        bundle_ready
        and kpi_ready
        and rocm_ready
        and clean_container_smoke_ready
        and runner_claim_metadata_signed
        and force_residual_summary_signed
        and force_term_claim_metadata_ready
        and force_term_result_contract_ready
        and guarded_force_term_plugin_ready
        and onsps_backmap_evidence_schema_ready
        and core_forcefield_bridge_ready
        and core_compatibility_layer_ready
        and job_store_lazy_factory_ready
        and allowlisted_runner_shim_contract_ready
        and chemistry_pm_gates_ready
        and pose_ranking_hbond_benchmark_ready
        and validation["kpi_claim_metadata_gates_validated"] is True
    )
    if product_claim_ready:
        next_required_step = "Use this local evidence bundle as the AI-MD product runtime handoff packet."
    elif not bundle_ready:
        next_required_step = "Generate all required local AI-MD evidence artifacts before bundle export."
    elif rocm_ready and not clean_container_smoke_ready:
        next_required_step = (
            "Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh and attach the clean "
            "container smoke receipt before product claim promotion."
        )
    else:
        next_required_step = "Expose ROCm/HIP GPU visibility to PyTorch and regenerate the KPI report before product claim promotion."
    summary = {
        "packet_type": "ai_md_product_evidence_bundle",
        "status": "ai_md_product_evidence_bundle_ready" if bundle_ready else "blocked_ai_md_product_evidence_bundle",
        "bundle_export_ready": bundle_ready,
        "product_claim_ready": product_claim_ready,
        "kpi_report_ready": kpi_ready,
        "kpi_failed_gate_count": len(kpi_failed_gate_ids),
        "kpi_failed_gate_ids": kpi_failed_gate_ids,
        "runner_claim_metadata_signed": runner_claim_metadata_signed,
        "force_residual_summary_signed": force_residual_summary_signed,
        "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
        "force_term_result_contract_ready": force_term_result_contract_ready,
        "guarded_force_term_plugin_ready": guarded_force_term_plugin_ready,
        "onsps_backmap_evidence_schema_ready": onsps_backmap_evidence_schema_ready,
        "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
        "core_compatibility_layer_ready": core_compatibility_layer_ready,
        "job_store_lazy_factory_ready": job_store_lazy_factory_ready,
        "allowlisted_runner_shim_contract_ready": allowlisted_runner_shim_contract_ready,
        "chemistry_pm_gates_ready": chemistry_pm_gates_ready,
        "pose_ranking_hbond_benchmark_ready": pose_ranking_hbond_benchmark_ready,
        "pose_ranking_hbond_row_contracts_ready": bool(
            pose_benchmark.get("row_contracts_ready") is True
        ),
        "pose_ranking_hbond_row_contract_pass_count": _int_value(
            pose_benchmark.get("row_contract_pass_count")
        ),
        "hbond_recovery_pose_count": _int_value(pm_chemistry.get("hbond_recovery_pose_count")),
        "overanchored_decoy_rejection": bool(pm_chemistry.get("overanchored_decoy_rejection") is True),
        "unsatisfied_donor_acceptor_detection": bool(
            pm_chemistry.get("unsatisfied_donor_acceptor_detection") is True
        ),
        "kpi_claim_metadata_gates_validated": bool(validation["kpi_claim_metadata_gates_validated"]),
        "kpi_claim_metadata_gate_count": int(validation["kpi_claim_metadata_gate_count"]),
        "kpi_claim_metadata_gate_validated_count": int(validation["kpi_claim_metadata_gate_validated_count"]),
        "rocm_hip_rust_runtime_ready": rocm_ready,
        "clean_container_smoke_ready": clean_container_smoke_ready,
        "clean_container_missing_requirement_count": len(clean_container_missing_requirements),
        "clean_container_missing_requirements": clean_container_missing_requirements,
        "product_image_preflight_status": str(image_summary.get("status") or ""),
        "product_image_preflight_ready": bool(image_summary.get("preflight_ready") is True),
        "product_image_docker_cli_present": bool(image_summary.get("docker_cli_present") is True),
        "product_image_preflight_blocker_count": len(image_preflight_blocker_codes),
        "product_image_preflight_blocker_codes": image_preflight_blocker_codes,
        "product_image_preflight_next_required_step": str(image_summary.get("next_required_step") or ""),
        "product_image_receipt_present": bool(image_summary.get("receipt_present") is True),
        "container_runtime_receipt_ready": image_container_runtime_receipt_ready,
        "container_runtime_proof_schema_version": str(
            image_summary.get("container_runtime_proof_schema_version") or ""
        ),
        "container_runtime_in_container": bool(image_summary.get("container_runtime_in_container") is True),
        "container_runtime_device_nodes_ready": bool(
            image_summary.get("container_runtime_device_nodes_ready") is True
        ),
        "container_runtime_torch_rocm_ready": bool(
            image_summary.get("container_runtime_torch_rocm_ready") is True
        ),
        "container_runtime_torch_cuda_available": bool(
            image_summary.get("container_runtime_torch_cuda_available") is True
        ),
        "container_runtime_visible_device_count": _int_value(
            image_summary.get("container_runtime_visible_device_count")
        ),
        "container_runtime_rust_hip_backend_enabled": bool(
            image_summary.get("container_runtime_rust_hip_backend_enabled") is True
        ),
        "product_runner_smoke_ready": bool(image_summary.get("product_runner_smoke_ready") is True),
        "product_runner_claim_metadata_ready": bool(image_summary.get("product_runner_claim_metadata_ready") is True),
        "product_image_receipt_mode": str(image_summary.get("receipt_mode") or ""),
        "tier_alpha_result_manifest_signature_verified": bool(
            image_summary.get("tier_alpha_result_manifest_signature_verified") is True
        ),
        "tier_alpha_result_manifest_status": str(image_summary.get("tier_alpha_result_manifest_status") or ""),
        "backmapping_runner_claim_metadata_ready": bool(
            image_summary.get("backmapping_runner_claim_metadata_ready") is True
        ),
        "backmapping_ligand_topology_receipt_ready": image_ligand_topology_receipt_ready,
        "backmapping_ligand_topology_schema_version": str(
            image_summary.get("backmapping_ligand_topology_schema_version") or ""
        ),
        "backmapping_ligand_topology_schema_ready_row_count": _int_value(
            image_summary.get("backmapping_ligand_topology_schema_ready_row_count")
        ),
        "backmapping_ligand_topology_valid": bool(
            image_summary.get("backmapping_ligand_topology_valid") is True
        ),
        "backmapping_ligand_topology_claim_safe": bool(
            image_summary.get("backmapping_ligand_topology_claim_safe") is True
        ),
        "backmapping_ligand_topology_claim_safe_row_count": _int_value(
            image_summary.get("backmapping_ligand_topology_claim_safe_row_count")
        ),
        "backmapping_ligand_topology_invalid_row_count": _int_value(
            image_summary.get("backmapping_ligand_topology_invalid_row_count")
        ),
        "backmapping_hbond_evidence_receipt_ready": image_hbond_evidence_receipt_ready,
        "backmapping_onsps_backmap_receipt_ready": image_onsps_backmap_receipt_ready,
        "backmapping_hbond_evidence_schema_version": str(
            image_summary.get("backmapping_hbond_evidence_schema_version") or ""
        ),
        "backmapping_hbond_claim_metadata_schema_version": str(
            image_summary.get("backmapping_hbond_claim_metadata_schema_version") or ""
        ),
        "backmapping_hbond_claim_metadata_schema_ready_row_count": _int_value(
            image_summary.get("backmapping_hbond_claim_metadata_schema_ready_row_count")
        ),
        "backmapping_onsps_backmap_schema_version": str(
            image_summary.get("backmapping_onsps_backmap_schema_version") or ""
        ),
        "backmapping_hbond_evaluated_row_count": _int_value(
            image_summary.get("backmapping_hbond_evaluated_row_count")
        ),
        "backmapping_onsps_backmap_claim_safe_row_count": _int_value(
            image_summary.get("backmapping_onsps_backmap_claim_safe_row_count")
        ),
        "cpu_fallback_allowed_for_product": False,
        "required_artifact_count": sum(1 for row in rows if row["required"] is True),
        "required_artifact_missing_count": len(missing_required),
        "source_artifact_count": len(rows),
        "included_artifact_count": sum(1 for row in rows if row["included_in_bundle"] is True),
        "bundle_tar_path": out_tar,
        "bundle_tar_exists": tar_exists,
        "bundle_tar_size_bytes": tar_size,
        "bundle_tar_member_count": tar_member_count,
        "bundle_tar_sha256": tar_sha,
        "bundle_validation_pass": bool(validation["bundle_validation_pass"]),
        "bundle_validation_checked": bool(validation["bundle_validation_checked"]),
        "bundle_validation_error_count": int(validation["bundle_validation_error_count"]),
        "bundle_validation_errors": list(validation["bundle_validation_errors"]),
        "source_artifacts_fresh": bool(validation["source_artifacts_fresh"]),
        "source_artifact_fresh_count": int(validation["source_artifact_fresh_count"]),
        "source_artifact_stale_count": int(validation["source_artifact_stale_count"]),
        "source_artifact_stale_ids": list(validation["source_artifact_stale_ids"]),
        "product_runtime_completion_rule": (
            "commercial_compute_default=rocm_hip; torch_rocm_ready=true; visible_device_count>0; "
            "device_nodes_ready=true; cpu_fallback_allowed_for_product=false"
        ),
        "next_required_step": next_required_step,
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    blockers = []
    if missing_required:
        blockers.append(
            {
                "code": "required_artifacts_missing",
                "count": len(missing_required),
                "artifact_ids": [row["artifact_id"] for row in missing_required],
            }
        )
    if bundle_ready and not rocm_ready:
        blockers.append({"code": "rocm_hip_rust_runtime_not_ready"})
    if bundle_ready and not kpi_ready:
        blockers.append(
            {
                "code": "kpi_report_not_ready",
                "failed_gate_ids": kpi_failed_gate_ids,
            }
        )
    if bundle_ready and not runner_claim_metadata_signed:
        blockers.append({"code": "runner_claim_metadata_not_signed"})
    if bundle_ready and not force_residual_summary_signed:
        blockers.append({"code": "force_residual_summary_not_signed"})
    if bundle_ready and not force_term_claim_metadata_ready:
        blockers.append({"code": "force_term_claim_metadata_not_ready"})
    if bundle_ready and not force_term_result_contract_ready:
        blockers.append({"code": "force_term_result_contract_not_ready"})
    if bundle_ready and not guarded_force_term_plugin_ready:
        blockers.append({"code": "guarded_force_term_plugin_not_ready"})
    if bundle_ready and not onsps_backmap_evidence_schema_ready:
        blockers.append({"code": "onsps_backmap_evidence_schema_not_ready"})
    if bundle_ready and not core_forcefield_bridge_ready:
        blockers.append({"code": "core_forcefield_bridge_not_ready"})
    if bundle_ready and not core_compatibility_layer_ready:
        blockers.append({"code": "core_compatibility_layer_not_ready"})
    if bundle_ready and not job_store_lazy_factory_ready:
        blockers.append({"code": "job_store_lazy_factory_not_ready"})
    if bundle_ready and not allowlisted_runner_shim_contract_ready:
        blockers.append({"code": "allowlisted_runner_shim_contract_not_ready"})
    if bundle_ready and not chemistry_pm_gates_ready:
        blockers.append({"code": "chemistry_pm_gates_not_ready"})
    if bundle_ready and not pose_ranking_hbond_benchmark_ready:
        blockers.append({"code": "pose_ranking_hbond_benchmark_not_ready"})
    if bundle_ready and validation["kpi_claim_metadata_gates_validated"] is not True:
        blockers.append({"code": "kpi_claim_metadata_gates_not_validated"})
    if bundle_ready and not clean_container_smoke_ready:
        blockers.append(
            {
                "code": "clean_container_smoke_not_ready",
                "missing_requirements": clean_container_missing_requirements,
            }
        )
    if bundle_ready and not clean_container_smoke_ready and image_preflight_blocker_codes:
        blockers.append(
            {
                "code": "product_image_preflight_blocked",
                "preflight_blockers": image_preflight_blocker_codes,
            }
        )
    if bundle_ready and validation["bundle_validation_pass"] is not True:
        blockers.append({"code": "bundle_validation_failed", "errors": list(validation["bundle_validation_errors"])})
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# AI-MD Product Evidence Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- bundle_export_ready: `{s['bundle_export_ready']}`",
        f"- product_claim_ready: `{s['product_claim_ready']}`",
        f"- kpi_report_ready: `{s['kpi_report_ready']}`",
        f"- rocm_hip_rust_runtime_ready: `{s['rocm_hip_rust_runtime_ready']}`",
        f"- clean_container_smoke_ready: `{s['clean_container_smoke_ready']}`",
        f"- product_image_preflight_status: `{s['product_image_preflight_status']}`",
        f"- product_image_preflight_blocker_codes: `{','.join(s['product_image_preflight_blocker_codes'])}`",
        f"- allowlisted_runner_shim_contract_ready: `{s['allowlisted_runner_shim_contract_ready']}`",
        f"- bundle_tar_path: `{s['bundle_tar_path']}`",
        f"- bundle_tar_sha256: `{s['bundle_tar_sha256']}`",
        f"- required_artifact_missing_count: `{s['required_artifact_missing_count']}`",
        "",
        "## Artifacts",
        "",
        "| artifact | required | exists | role | sha256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['required']}` | `{row['exists']}` | "
            f"`{row['role']}` | `{row['sha256']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local AI-MD product evidence bundle export.")
    parser.add_argument("--kpi-json", default=DEFAULT_KPI_JSON)
    parser.add_argument("--kpi-md", default=DEFAULT_KPI_MD)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--product-image-receipt-json", default=DEFAULT_PRODUCT_IMAGE_RECEIPT_JSON)
    parser.add_argument("--next-steps-doc", default=DEFAULT_NEXT_STEPS_DOC)
    parser.add_argument("--out-tar", default=DEFAULT_OUT_TAR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_specs = _default_artifacts(
        kpi_json=args.kpi_json,
        kpi_md=args.kpi_md,
        rocm_manifest_json=args.rocm_manifest_json,
        product_image_preflight_json=args.product_image_preflight_json,
        product_image_receipt_json=args.product_image_receipt_json,
        next_steps_doc=args.next_steps_doc,
    )
    payload = build_payload(
        kpi_packet=_read_json_if_present(args.kpi_json),
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        product_image_preflight_packet=_read_json_if_present(args.product_image_preflight_json),
        artifact_specs=artifact_specs,
        out_tar=args.out_tar,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_tar": args.out_tar}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
