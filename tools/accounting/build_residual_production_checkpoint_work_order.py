#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFLIGHT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_SIDECAR_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_OUT_JSON = "runs/residual_production_checkpoint_work_order_current.json"
DEFAULT_OUT_CSV = "runs/residual_production_checkpoint_work_order_current.csv"
DEFAULT_OUT_MD = "runs/residual_production_checkpoint_work_order_current.md"

SIDE_CAR_SCHEMA = {
    "component_id": "topograph_corrector",
    "model_family": "protein_ligand_residual_v1",
    "checkpoint_sha256": "<sha256 from preflight row>",
    "required_output_fields": [
        "delta_score",
        "corrected_score",
        "delta_energy",
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ],
    "benchmark_gate_artifacts": [
        {"artifact": "runs/<benchmark_gate>.json", "status": "ready"}
    ],
    "uncertainty_calibrated": True,
    "physics_guard_bound": True,
    "promotion_mode": "production_guarded",
    "adapter_output_policy": {
        "delta_score": "learned_score_residual_head",
        "corrected_score": "raw_score_plus_learned_delta_score",
        "delta_energy": "validated_energy_head_or_fail_closed_guard",
        "delta_force": "validated_force_head_or_fail_closed_guard",
        "uncertainty": "calibrated_uncertainty_head",
        "abstention_reason": "policy_output_reason_for_high_uncertainty_missing_physics_or_contract_violation",
        "stage2_route_decision": "policy_output_route_for_frozen_expensive_path_or_guarded_accept",
    },
    "physics_guard_policy": "fail_closed_without_validated_energy_force_head_and_physics_guard_binding",
    "abstention_policy": "abstain_on_high_uncertainty_missing_physics_support_output_contract_violation_or_ood_scope",
    "production_training_data_contract_artifact": {
        "artifact": "runs/residual_production_training_data_contract_current.json",
        "required_ready_key": "production_training_data_ready",
        "observed_ready": "<true only when production_training_data_ready is true>",
        "status": "<ready|blocked>",
    },
    "force_gpu_worker_return_receipt_artifact": {
        "artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
        "required_ready_key": "gpu_worker_return_receipt_ready",
        "required_provenance_key": "queue_manifest_identity_coverage_ready",
        "observed_ready": "<true only when gpu_worker_return_receipt_ready is true>",
        "observed_provenance_ready": "<true only when queue_manifest_identity_coverage_ready is true>",
        "status": "<ready|blocked>",
    },
}

CLAIM_BOUNDARY = (
    "Residual production checkpoint work order only; ranks local checkpoint candidates and documents the metadata and "
    "benchmark evidence required for guarded promotion. It does not create sidecars, load model weights, train models, "
    "run inference, run docking, promote production mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _candidate_score(row: dict[str, Any]) -> tuple[int, int, int]:
    path = str(row.get("checkpoint_path") or "").lower()
    if "idp" in path:
        family_bonus = 0
    elif "residual_production_score_model" in path or "production_score_model" in path:
        family_bonus = 5
    elif any(token in path for token in ("protein_ligand", "ligand", "docking", "gpcr")) and "residual" in path:
        family_bonus = 4
    elif "airouter" in path:
        family_bonus = 2
    elif "residual" in path:
        family_bonus = 1
    elif "curriculum" in path:
        family_bonus = 1
    else:
        family_bonus = 0
    size = _int(row.get("size_bytes"))
    metadata_penalty = 0 if row.get("metadata_present") is True else -1
    return (family_bonus, metadata_penalty, size)


def _compatibility_status(checkpoint_path: str) -> str:
    path = checkpoint_path.lower()
    if "idp" in path:
        return "blocked_idp_residual_not_protein_ligand_docking"
    if "residual_production_score_model" in path or "production_score_model" in path:
        return "score_candidate_requires_output_head_guard_and_sidecar"
    if any(token in path for token in ("protein_ligand", "ligand", "docking", "gpcr")):
        return "candidate_requires_sidecar_and_benchmark_proof"
    if "airouter" in path:
        return "router_candidate_requires_output_contract_proof"
    return "unknown_candidate_requires_architecture_proof"


def _list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _sidecar_schema_with_observed_status(sidecar: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(SIDE_CAR_SCHEMA))
    training_ready = sidecar.get("production_training_data_contract_ready") is True
    force_ready = sidecar.get("force_gpu_return_receipt_ready") is True
    force_operator_verified = sidecar.get("force_gpu_return_receipt_operator_verified") is True
    force_manifest_status_vocab_ready = sidecar.get("force_gpu_return_receipt_manifest_status_vocab_ready") is True
    force_manifest_status_counts_ready = (
        _int(sidecar.get("force_gpu_return_receipt_manifest_status_placeholder_count")) == 0
        and _int(sidecar.get("force_gpu_return_receipt_manifest_status_invalid_count")) == 0
    )
    force_manifest_row_count_ready = sidecar.get("force_gpu_return_receipt_manifest_row_count_ready") is True
    force_artifact_ready = (
        force_ready
        and force_operator_verified
        and force_manifest_status_vocab_ready
        and force_manifest_status_counts_ready
        and force_manifest_row_count_ready
    )
    schema["production_training_data_contract_artifact"].update(
        {
            "observed_ready": training_ready,
            "status": "ready" if training_ready else "blocked",
        }
    )
    schema["force_gpu_worker_return_receipt_artifact"].update(
        {
            "observed_ready": force_ready,
            "observed_provenance_ready": force_artifact_ready,
            "observed_operator_verified": force_operator_verified,
            "observed_operator_verified_true_count": _int(
                sidecar.get("force_gpu_return_receipt_operator_verified_true_count")
            ),
            "observed_expected_queue_rows": _int(sidecar.get("force_gpu_return_receipt_expected_queue_rows")),
            "observed_manifest_ok_row_count": _int(sidecar.get("force_gpu_return_receipt_manifest_ok_row_count")),
            "observed_manifest_status_placeholder_count": _int(
                sidecar.get("force_gpu_return_receipt_manifest_status_placeholder_count")
            ),
            "observed_manifest_status_invalid_count": _int(
                sidecar.get("force_gpu_return_receipt_manifest_status_invalid_count")
            ),
            "observed_manifest_status_vocab_ready": force_manifest_status_vocab_ready,
            "observed_manifest_row_count_ready": force_manifest_row_count_ready,
            "observed_manifest_allowed_ok_status_values": _list(
                sidecar.get("force_gpu_return_receipt_manifest_allowed_ok_status_values")
            ),
            "status": "ready" if force_artifact_ready else "blocked",
        }
    )
    return schema


def _checkpoint_closure_blockers(registry: dict[str, Any], sidecar: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if registry.get("production_promotion_allowed") is not True:
        blockers.append("registry_production_promotion_allowed_false")
    for field in _list(registry.get("checkpoint_missing_output_fields")):
        blockers.append(f"registry_missing_output:{field}")
    for field in _list(registry.get("checkpoint_missing_adapter_output_policy_fields")):
        blockers.append(f"registry_missing_adapter_output_policy:{field}")
    for blocker in _list(sidecar.get("blockers")):
        blockers.append(f"sidecar:{blocker}")
    for field in _list(sidecar.get("missing_production_output_fields")):
        blockers.append(f"sidecar_missing_production_output:{field}")
    for field in _list(sidecar.get("training_contract_missing_label_fields")):
        blockers.append(f"training_missing_label:{field}")
    if sidecar.get("force_gpu_return_receipt_ready") is not True:
        blockers.append("force_gpu_return_receipt_not_ready")
    if sidecar.get("force_gpu_return_receipt_operator_verified") is not True:
        blockers.append("force_gpu_return_receipt_operator_not_verified")
    if _int(sidecar.get("force_gpu_return_receipt_operator_verified_true_count")) <= 0:
        blockers.append("force_gpu_return_receipt_operator_verified_true_count_zero")
    if _int(sidecar.get("force_gpu_return_receipt_manifest_status_placeholder_count")) > 0:
        blockers.append("force_gpu_return_receipt_manifest_status_placeholders")
    if _int(sidecar.get("force_gpu_return_receipt_manifest_status_invalid_count")) > 0:
        blockers.append("force_gpu_return_receipt_manifest_status_invalid")
    if sidecar.get("force_gpu_return_receipt_manifest_status_vocab_ready") is not True:
        blockers.append("force_gpu_return_receipt_manifest_status_vocab_not_ready")
    if sidecar.get("force_gpu_return_receipt_manifest_row_count_ready") is not True:
        blockers.append("force_gpu_return_receipt_manifest_row_count_not_ready")
    return list(dict.fromkeys(blockers))


def build_residual_production_checkpoint_work_order(
    *,
    preflight_packet: dict[str, Any],
    registry_packet: dict[str, Any],
    sidecar_packet: dict[str, Any] | None = None,
    preflight_path: str = DEFAULT_PREFLIGHT_JSON,
    registry_path: str = DEFAULT_REGISTRY_JSON,
    sidecar_path: str = DEFAULT_SIDECAR_JSON,
    candidate_limit: int = 10,
) -> dict[str, Any]:
    preflight = _summary(preflight_packet)
    registry = _summary(registry_packet)
    sidecar = _summary(sidecar_packet or {})
    required_sidecar_schema = _sidecar_schema_with_observed_status(sidecar)
    registry_checkpoint_missing_output_fields = _list(registry.get("checkpoint_missing_output_fields"))
    registry_checkpoint_missing_adapter_output_policy_fields = _list(
        registry.get("checkpoint_missing_adapter_output_policy_fields")
    )
    registry_checkpoint_primary_blocker = str(registry.get("checkpoint_primary_blocker") or "")
    checkpoint_closure_blockers = _checkpoint_closure_blockers(registry, sidecar)
    rows = [dict(row) for row in preflight_packet.get("rows", []) or [] if isinstance(row, dict)]
    ranked = sorted(rows, key=_candidate_score, reverse=True)[: max(0, candidate_limit)]
    work_rows: list[dict[str, Any]] = []
    for priority, row in enumerate(ranked, start=1):
        checkpoint_path = str(row.get("checkpoint_path") or "")
        candidate_sidecar_path = f"{checkpoint_path}.json" if checkpoint_path else ""
        compatibility_status = _compatibility_status(checkpoint_path)
        work_rows.append(
            {
                "priority": priority,
                "checkpoint_path": checkpoint_path,
                "sidecar_path": candidate_sidecar_path,
                "sha256": str(row.get("sha256") or ""),
                "model_family_guess": str(row.get("model_family") or ""),
                "compatibility_status": compatibility_status,
                "current_blockers": str(row.get("blockers") or ""),
                "registry_checkpoint_primary_blocker": registry_checkpoint_primary_blocker,
                "registry_checkpoint_missing_output_fields": ",".join(registry_checkpoint_missing_output_fields),
                "registry_checkpoint_missing_adapter_output_policy_fields": ",".join(
                    registry_checkpoint_missing_adapter_output_policy_fields
                ),
                "sidecar_builder_blockers": ",".join(_list(sidecar.get("blockers"))),
                "sidecar_builder_missing_production_output_fields": ",".join(
                    _list(sidecar.get("missing_production_output_fields"))
                ),
                "sidecar_builder_training_contract_missing_label_fields": ",".join(
                    _list(sidecar.get("training_contract_missing_label_fields"))
                ),
                "sidecar_builder_force_gpu_return_receipt_ready": sidecar.get("force_gpu_return_receipt_ready") is True,
                "sidecar_builder_force_gpu_return_receipt_operator_verified": sidecar.get(
                    "force_gpu_return_receipt_operator_verified"
                )
                is True,
                "sidecar_builder_force_gpu_return_receipt_operator_verified_true_count": _int(
                    sidecar.get("force_gpu_return_receipt_operator_verified_true_count")
                ),
                "sidecar_builder_force_gpu_return_receipt_expected_queue_rows": _int(
                    sidecar.get("force_gpu_return_receipt_expected_queue_rows")
                ),
                "sidecar_builder_force_gpu_return_receipt_manifest_ok_row_count": _int(
                    sidecar.get("force_gpu_return_receipt_manifest_ok_row_count")
                ),
                "sidecar_builder_force_gpu_return_receipt_manifest_status_invalid_count": _int(
                    sidecar.get("force_gpu_return_receipt_manifest_status_invalid_count")
                ),
                "sidecar_builder_force_gpu_return_receipt_manifest_status_vocab_ready": sidecar.get(
                    "force_gpu_return_receipt_manifest_status_vocab_ready"
                )
                is True,
                "sidecar_builder_force_gpu_return_receipt_manifest_row_count_ready": sidecar.get(
                    "force_gpu_return_receipt_manifest_row_count_ready"
                )
                is True,
                "checkpoint_closure_blockers": ",".join(checkpoint_closure_blockers),
                "required_action": (
                    "extend score candidate with production output head coverage, uncertainty calibration, physics guard binding, sidecar metadata, training-data contract, force GPU receipt provenance, and benchmark gates, then rerun preflight"
                    if compatibility_status == "score_candidate_requires_output_head_guard_and_sidecar"
                    else
                    "train or select a protein-ligand residual checkpoint, create sidecar metadata, attach ready training-data/force-receipt/benchmark gates, calibrate uncertainty, bind physics guard, then rerun preflight"
                    if compatibility_status.startswith("blocked_") or compatibility_status.startswith("unknown_")
                    else "create sidecar metadata, attach ready training-data/force-receipt/benchmark gates, calibrate uncertainty, bind physics guard, then rerun preflight"
                ),
                "acceptance_criteria": (
                    "ready_for_guarded_promotion=true in residual_production_checkpoint_preflight, "
                    "production_promotion_allowed=true in residual_model_registry, checkpoint_missing_output_fields "
                    "empty, checkpoint_missing_adapter_output_policy_fields empty, production_training_data_contract_ready=true, "
                    "and force_gpu_worker_return_receipt_ready=true"
                ),
                "verification_command": "python3 tools/build_residual_production_checkpoint_sidecar.py && python3 tools/build_residual_production_checkpoint_preflight.py && python3 tools/build_residual_model_registry.py && python3 tools/build_product_ai_architecture_gap_closure.py",
                "execution_enabled": False,
                "sidecar_created": False,
                "model_loaded": False,
                "training_executed": False,
                "external_state_mutated": False,
            }
        )
    out_summary = {
        "packet_type": "residual_production_checkpoint_work_order",
        "status": "residual_production_checkpoint_work_order_ready" if work_rows or preflight.get("checkpoint_preflight_ready") is True else "blocked_residual_production_checkpoint_work_order",
        "work_order_ready": bool(work_rows or preflight.get("checkpoint_preflight_ready") is True),
        "checkpoint_preflight_ready": preflight.get("checkpoint_preflight_ready") is True,
        "candidate_checkpoint_count": _int(preflight.get("candidate_checkpoint_count")),
        "sidecar_metadata_count": _int(preflight.get("sidecar_metadata_count")),
        "ready_checkpoint_count": _int(preflight.get("ready_checkpoint_count")),
        "ranked_candidate_count": len(work_rows),
        "compatible_candidate_count": sum(
            1
            for row in work_rows
            if str(row.get("compatibility_status") or "") == "candidate_requires_sidecar_and_benchmark_proof"
        ),
        "registry_default_residual_mode": registry.get("default_residual_mode"),
        "registry_production_promotion_allowed": registry.get("production_promotion_allowed"),
        "registry_production_checkpoint_blocked": registry.get("production_checkpoint_blocked") is True,
        "registry_checkpoint_primary_blocker": registry_checkpoint_primary_blocker,
        "registry_checkpoint_missing_output_fields": registry_checkpoint_missing_output_fields,
        "registry_checkpoint_missing_adapter_output_policy_fields": registry_checkpoint_missing_adapter_output_policy_fields,
        "checkpoint_closure_blockers": checkpoint_closure_blockers,
        "checkpoint_closure_blocker_count": len(checkpoint_closure_blockers),
        "sidecar_builder_status": sidecar.get("status", ""),
        "sidecar_builder_ready": sidecar.get("sidecar_ready") is True,
        "sidecar_builder_written": sidecar.get("sidecar_written") is True,
        "sidecar_builder_blockers": sidecar.get("blockers") if isinstance(sidecar.get("blockers"), list) else [],
        "sidecar_builder_missing_production_output_fields": _list(sidecar.get("missing_production_output_fields")),
        "sidecar_builder_training_contract_missing_label_fields": _list(
            sidecar.get("training_contract_missing_label_fields")
        ),
        "sidecar_builder_training_contract_missing_output_fields": _list(
            sidecar.get("training_contract_missing_output_fields")
        ),
        "sidecar_builder_checkpoint_path": sidecar.get("checkpoint_path", ""),
        "sidecar_builder_sidecar_path": sidecar.get("sidecar_path", ""),
        "sidecar_builder_training_data_contract_ready": sidecar.get("production_training_data_contract_ready") is True,
        "sidecar_builder_force_gpu_return_receipt_ready": sidecar.get("force_gpu_return_receipt_ready") is True,
        "sidecar_builder_force_gpu_return_receipt_operator_verified": sidecar.get(
            "force_gpu_return_receipt_operator_verified"
        )
        is True,
        "sidecar_builder_force_gpu_return_receipt_operator_verified_true_count": _int(
            sidecar.get("force_gpu_return_receipt_operator_verified_true_count")
        ),
        "sidecar_builder_force_gpu_return_receipt_expected_queue_rows": _int(
            sidecar.get("force_gpu_return_receipt_expected_queue_rows")
        ),
        "sidecar_builder_force_gpu_return_receipt_manifest_ok_row_count": _int(
            sidecar.get("force_gpu_return_receipt_manifest_ok_row_count")
        ),
        "sidecar_builder_force_gpu_return_receipt_manifest_status_invalid_count": _int(
            sidecar.get("force_gpu_return_receipt_manifest_status_invalid_count")
        ),
        "sidecar_builder_force_gpu_return_receipt_manifest_status_vocab_ready": sidecar.get(
            "force_gpu_return_receipt_manifest_status_vocab_ready"
        )
        is True,
        "sidecar_builder_force_gpu_return_receipt_manifest_row_count_ready": sidecar.get(
            "force_gpu_return_receipt_manifest_row_count_ready"
        )
        is True,
        "required_sidecar_schema": required_sidecar_schema,
        "source_artifacts": [preflight_path, registry_path, sidecar_path],
        "execution_enabled": False,
        "sidecar_created": False,
        "model_loaded": False,
        "training_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Ready checkpoint exists; rerun registry and architecture closure to verify promotion state."
            if preflight.get("checkpoint_preflight_ready") is True
            else "Choose or train a protein-ligand residual checkpoint, create the required sidecar metadata, attach ready training-data contract, force GPU receipt provenance, benchmark gates, and rerun preflight."
        ),
    }
    return {"summary": out_summary, "rows": work_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Checkpoint Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- checkpoint_preflight_ready: `{s['checkpoint_preflight_ready']}`",
        f"- candidate_checkpoint_count: `{s['candidate_checkpoint_count']}`",
        f"- sidecar_metadata_count: `{s['sidecar_metadata_count']}`",
        f"- ready_checkpoint_count: `{s['ready_checkpoint_count']}`",
        f"- ranked_candidate_count: `{s['ranked_candidate_count']}`",
        f"- compatible_candidate_count: `{s['compatible_candidate_count']}`",
        f"- registry_default_residual_mode: `{s['registry_default_residual_mode']}`",
        f"- registry_production_promotion_allowed: `{s['registry_production_promotion_allowed']}`",
        f"- registry_production_checkpoint_blocked: `{s['registry_production_checkpoint_blocked']}`",
        f"- registry_checkpoint_missing_output_fields: `{','.join(s['registry_checkpoint_missing_output_fields'])}`",
        f"- registry_checkpoint_missing_adapter_output_policy_fields: `{','.join(s['registry_checkpoint_missing_adapter_output_policy_fields'])}`",
        f"- sidecar_builder_status: `{s['sidecar_builder_status']}`",
        f"- sidecar_builder_ready: `{s['sidecar_builder_ready']}`",
        f"- sidecar_builder_training_data_contract_ready: `{s['sidecar_builder_training_data_contract_ready']}`",
        f"- sidecar_builder_force_gpu_return_receipt_ready: `{s['sidecar_builder_force_gpu_return_receipt_ready']}`",
        "",
        "## Candidate Actions",
        "",
        "| priority | checkpoint | sidecar | family guess | compatibility | blockers | registry output gaps | verification |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['checkpoint_path']}` | `{row['sidecar_path']}` | "
            f"`{row['model_family_guess']}` | `{row['compatibility_status']}` | `{row['current_blockers']}` | "
            f"`{row['registry_checkpoint_missing_output_fields']}` | `{row['verification_command']}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | `none` | `none` | `none` | `none` | `none` |")
    lines.extend(
        [
            "",
            "## Required Sidecar Schema",
            "",
            "```json",
            json.dumps(s["required_sidecar_schema"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual production checkpoint work order.")
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--sidecar-json", default=DEFAULT_SIDECAR_JSON)
    parser.add_argument("--candidate-limit", type=int, default=10)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_production_checkpoint_work_order(
        preflight_packet=_read_json(args.preflight_json),
        registry_packet=_read_json(args.registry_json),
        sidecar_packet=_read_json(args.sidecar_json),
        preflight_path=args.preflight_json,
        registry_path=args.registry_json,
        sidecar_path=args.sidecar_json,
        candidate_limit=args.candidate_limit,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
