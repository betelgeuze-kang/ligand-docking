from __future__ import annotations

import json
from typing import Any

from betelgeuze_product.docking_request import (
    ALLOWED_SCOPE_FAMILIES,
    MAX_P0_LIGAND_COUNT,
    build_docking_job_record,
    validate_docking_request,
)

CLAIM_BOUNDARY = (
    "Product operational quality contract only; it audits local fail-closed docking intake, ledger privacy, "
    "traceability, scope limits, and safety flags from in-memory sample requests. It does not run docking, persist "
    "jobs, emit scientific results, upload data, send email, write licenses, assemble bundles, or mutate external state."
)

SAMPLE_REQUEST = {
    "request_type": "structure_analysis_ligand_docking",
    "family": "gpcr",
    "target_id": "ADRB2",
    "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
    "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return bool(value is True)


def _row(check: str, passed: bool, observed: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _sample_blocker_codes(payload: dict[str, Any]) -> set[str]:
    validation = validate_docking_request(payload)
    return {str(blocker.get("code")) for blocker in validation.get("blockers", []) if isinstance(blocker, dict)}


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _walk_sensitive_key_paths(value: Any, path: str = "") -> list[str]:
    sensitive_keys = {"request_payload", "pdb_content", "mmcif_content", "smiles", "inchi"}
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in sensitive_keys:
                paths.append(child_path)
            paths.extend(_walk_sensitive_key_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_walk_sensitive_key_paths(item, f"{path}[{index}]"))
    return paths


def _materialization_hash_only_ready(record: dict[str, Any]) -> bool:
    rows = record.get("materialization_ligands") or []
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        if any(key in row for key in ("smiles", "inchi", "compound_id", "source_value")):
            return False
        if row.get("source_redacted") is not True:
            return False
        source_kind = _text(row.get("source_kind"))
        source_hash = _text(row.get("source_value_sha256"))
        compound_hash = _text(row.get("compound_id_sha256"))
        if source_kind and len(source_hash) != 64:
            return False
        if compound_hash and len(compound_hash) != 64:
            return False
    return True


def build_product_operational_quality_contract(sample_request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = dict(sample_request or SAMPLE_REQUEST)
    record = build_docking_job_record(request, job_id="operational_quality_probe")
    record_json = _canonical_json(record)
    invalid_scope_codes = _sample_blocker_codes({**request, "family": "transporter"})
    duplicate_ligand_request = {
        **request,
        "ligands": [{"ligand_id": "dup", "smiles": "CCO"}, {"ligand_id": "dup", "smiles": "CCC"}],
    }
    duplicate_codes = _sample_blocker_codes(duplicate_ligand_request)
    multi_source_codes = _sample_blocker_codes({**request, "pdb_id": "2RH1"})

    fail_closed_ready = (
        record.get("status") == "accepted_fail_closed"
        and record.get("validation_status") == "pass"
        and record.get("execution_enabled") is False
        and record.get("docking_results_emitted") is False
        and record.get("production_ai_correction_applied") is False
        and record.get("external_state_mutated") is False
    )
    ai_correction_not_applied_ready = record.get("production_ai_correction_applied") is False
    shadow_abstention_ready = (
        record.get("production_ai_correction_applied") is False
        and record.get("production_ai_inference_subject_active") is False
        and record.get("production_ai_abstention_enforced") is True
        and _text(record.get("production_ai_default_residual_mode")) == "shadow"
        and record.get("production_ai_promotion_allowed") is False
        and record.get("production_ai_customer_facing_auto_correction_allowed") is False
        and record.get("production_ai_customer_facing_score_mutation_allowed") is False
        and record.get("production_ai_customer_facing_ranking_mutation_allowed") is False
        and int(record.get("production_ai_trained_checkpoint_count") or 0) == 0
        and "delta_force" in [str(item) for item in record.get("production_ai_selected_sidecar_missing_output_fields") or []]
    )
    guarded_active_ready = (
        record.get("production_ai_correction_applied") is False
        and record.get("production_ai_inference_subject_active") is True
        and record.get("production_ai_abstention_enforced") is False
        and _text(record.get("production_ai_default_residual_mode")) == "production_guarded"
        and record.get("production_ai_promotion_allowed") is True
        and record.get("production_ai_customer_facing_auto_correction_allowed") is True
        and record.get("production_ai_customer_facing_score_mutation_allowed") is True
        and int(record.get("production_ai_trained_checkpoint_count") or 0) > 0
        and record.get("production_ai_selected_sidecar_ready") is True
        and list(record.get("production_ai_selected_sidecar_missing_output_fields") or []) == []
    )
    production_ai_posture_ready = ai_correction_not_applied_ready and (
        shadow_abstention_ready or guarded_active_ready
    )
    sensitive_values = ["ATOM      1", "CCO", "CCC"]
    sensitive_key_paths = _walk_sensitive_key_paths(record)
    sensitive_keys_absent = not sensitive_key_paths
    sensitive_values_absent = all(value not in record_json for value in sensitive_values)
    materialization_hash_only_ready = _materialization_hash_only_ready(record)
    privacy_ready = sensitive_keys_absent and sensitive_values_absent and materialization_hash_only_ready
    traceability_ready = (
        len(_text(record.get("request_sha256"))) == 64
        and _text(record.get("job_id")) == "operational_quality_probe"
        and bool(_text(record.get("created_at_utc")))
        and _text(record.get("target_id")) == _text(request.get("target_id"))
    )
    scope_limit_ready = (
        set(record.get("allowed_scope_families") or []) == set(ALLOWED_SCOPE_FAMILIES)
        and "scope_family_not_delivery_ready" in invalid_scope_codes
        and "duplicate_ligand_ids" in duplicate_codes
        and "multiple_structure_sources" in multi_source_codes
    )
    heavy_policy_ready = _text(record.get("heavy_artifact_policy")) == "manifest_first_externalize_before_delete"

    rows = [
        _row(
            "fail_closed_docking_intake",
            fail_closed_ready,
            (
                f"status={record.get('status')};validation_status={record.get('validation_status')};"
                f"execution_enabled={record.get('execution_enabled')};docking_results_emitted={record.get('docking_results_emitted')};"
                f"production_ai_correction_applied={record.get('production_ai_correction_applied')}"
            ),
            "accepted_fail_closed validation pass with execution/results/production AI correction/external mutation disabled",
            "Commercial intake must accept valid requests only as queued fail-closed records until explicit execution approval.",
        ),
        _row(
            "production_ai_correction_fail_closed",
            production_ai_posture_ready,
            (
                f"production_ai_inference_subject_active={record.get('production_ai_inference_subject_active')};"
                f"production_ai_correction_applied={record.get('production_ai_correction_applied')};"
                f"production_ai_abstention_enforced={record.get('production_ai_abstention_enforced')};"
                f"default_residual_mode={record.get('production_ai_default_residual_mode')};"
                f"production_promotion_allowed={record.get('production_ai_promotion_allowed')};"
                f"customer_facing_auto_correction_allowed={record.get('production_ai_customer_facing_auto_correction_allowed')};"
                f"customer_facing_score_mutation_allowed={record.get('production_ai_customer_facing_score_mutation_allowed')};"
                f"customer_facing_ranking_mutation_allowed={record.get('production_ai_customer_facing_ranking_mutation_allowed')};"
                f"trained_checkpoint_count={record.get('production_ai_trained_checkpoint_count')};"
                f"selected_sidecar_ready={record.get('production_ai_selected_sidecar_ready')};"
                f"missing_sidecar_outputs={','.join(str(item) for item in record.get('production_ai_selected_sidecar_missing_output_fields') or [])};"
                f"shadow_abstention_ready={shadow_abstention_ready};guarded_active_ready={guarded_active_ready}"
            ),
            "job ledger records no applied production AI correction and is either shadow-abstaining or guarded production active with green sidecar evidence",
            "Commercial job records must separate active inference eligibility from whether an AI correction was actually applied at intake.",
        ),
        _row(
            "ledger_payload_privacy",
            privacy_ready,
            (
                f"sensitive_keys_absent={sensitive_keys_absent};sensitive_values_absent={sensitive_values_absent};"
                f"materialization_hash_only_ready={materialization_hash_only_ready};"
                f"sensitive_key_paths={','.join(sensitive_key_paths)}"
            ),
            "no raw request payload, inline structure text, SMILES/InChI, or ligand source value persisted in the job record; materialization refs are hash-only",
            "The audit ledger should keep traceability without retaining raw molecular input payloads in the status record.",
        ),
        _row(
            "request_traceability",
            traceability_ready,
            f"job_id={record.get('job_id')};sha256_len={len(_text(record.get('request_sha256')))};created_at={record.get('created_at_utc')}",
            "stable job id, request_sha256, created_at_utc, and target id",
            "Commercial support and CAMEO handoff need deterministic traceability for every accepted intake.",
        ),
        _row(
            "scope_limit_enforcement",
            scope_limit_ready,
            (
                f"allowed={','.join(record.get('allowed_scope_families') or [])};"
                f"invalid_scope={','.join(sorted(invalid_scope_codes))};"
                f"duplicate={','.join(sorted(duplicate_codes))};multi_source={','.join(sorted(multi_source_codes))}"
            ),
            "restricted family list plus invalid-family, duplicate-ligand, and multi-structure-source blockers",
            "The product must fail closed on scope widening and non-reproducible request shapes.",
        ),
        _row(
            "heavy_artifact_policy",
            heavy_policy_ready,
            _text(record.get("heavy_artifact_policy")) or "missing",
            "manifest_first_externalize_before_delete",
            "Large molecular artifacts need a manifest-first policy before cleanup or delivery handoff.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    ready = not blockers
    summary = {
        "packet_type": "product_operational_quality_contract",
        "status": "product_operational_quality_contract_ready" if ready else "blocked_product_operational_quality_contract",
        "operational_quality_ready": ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "fail_closed_docking_intake_ready": fail_closed_ready,
        "production_ai_correction_fail_closed_ready": production_ai_posture_ready,
        "production_ai_intake_correction_not_applied_ready": ai_correction_not_applied_ready,
        "production_ai_shadow_abstention_ready": shadow_abstention_ready,
        "production_ai_guarded_active_ready": guarded_active_ready,
        "sample_production_ai_inference_subject_active": record.get("production_ai_inference_subject_active") is True,
        "sample_production_ai_correction_applied": record.get("production_ai_correction_applied") is True,
        "sample_production_ai_abstention_enforced": record.get("production_ai_abstention_enforced") is True,
        "sample_production_ai_default_residual_mode": _text(record.get("production_ai_default_residual_mode")),
        "sample_production_ai_promotion_allowed": record.get("production_ai_promotion_allowed") is True,
        "sample_production_ai_customer_facing_auto_correction_allowed": record.get(
            "production_ai_customer_facing_auto_correction_allowed"
        )
        is True,
        "sample_production_ai_customer_facing_score_mutation_allowed": record.get(
            "production_ai_customer_facing_score_mutation_allowed"
        )
        is True,
        "sample_production_ai_customer_facing_ranking_mutation_allowed": record.get(
            "production_ai_customer_facing_ranking_mutation_allowed"
        )
        is True,
        "sample_production_ai_trained_checkpoint_count": int(record.get("production_ai_trained_checkpoint_count") or 0),
        "sample_production_ai_selected_sidecar_ready": record.get("production_ai_selected_sidecar_ready") is True,
        "sample_production_ai_selected_sidecar_missing_output_fields": list(
            record.get("production_ai_selected_sidecar_missing_output_fields") or []
        ),
        "ledger_payload_privacy_ready": privacy_ready,
        "ledger_materialization_hash_only_ready": materialization_hash_only_ready,
        "ledger_sensitive_key_paths": sensitive_key_paths,
        "request_traceability_ready": traceability_ready,
        "scope_limit_enforcement_ready": scope_limit_ready,
        "heavy_artifact_policy_ready": heavy_policy_ready,
        "sample_job_status": _text(record.get("status")),
        "sample_request_sha256": _text(record.get("request_sha256")),
        "allowed_scope_families": sorted(ALLOWED_SCOPE_FAMILIES),
        "max_p0_ligand_count": MAX_P0_LIGAND_COUNT,
        "input_payload_persisted": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operational quality contract is ready; release still depends on license, approved execution, bundle validation, and CAMEO evidence."
            if ready
            else "Repair failed operational-quality checks before treating the product surface as commercial-grade."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
