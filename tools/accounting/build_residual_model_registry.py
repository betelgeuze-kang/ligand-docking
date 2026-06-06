#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_RESIDUAL_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_GPCR_BREADTH_GATE_JSON = "runs/gpcr_residual_proof_breadth_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_CHECKPOINT_PREFLIGHT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_CHECKPOINT_SIDECAR_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_OUT_JSON = "runs/residual_model_registry_current.json"
DEFAULT_OUT_CSV = "runs/residual_model_registry_current.csv"
DEFAULT_OUT_MD = "runs/residual_model_registry_current.md"

REQUIRED_OUTPUT_FIELDS = [
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
]

COMPONENTS = [
    {
        "component_id": "topograph_corrector",
        "display_name": "TopoGraph Corrector",
        "model_family": "E(3)/SE(3)-ready topology graph encoder",
        "activation_mode": "shadow_or_assist",
        "primary_outputs": ["delta_score", "uncertainty"],
        "training_status": "registered_untrained",
        "guardrail": "abstain on OOD topology or correction magnitude breach",
    },
    {
        "component_id": "equivariant_residual_energy_force_model",
        "display_name": "Equivariant Residual Energy/Force Model",
        "model_family": "E(3)/SE(3)-equivariant graph residual model",
        "activation_mode": "shadow_only_until_checkpointed",
        "primary_outputs": ["delta_energy", "delta_force", "uncertainty"],
        "training_status": "registered_untrained",
        "guardrail": "predict delta_energy first and derive delta_force = -grad(delta_energy) when possible",
    },
    {
        "component_id": "physics_guard",
        "display_name": "Physics Guard",
        "model_family": "PINN-style physics constraint/loss/gate",
        "activation_mode": "always_on_gate",
        "primary_outputs": ["abstention_reason", "uncertainty"],
        "training_status": "registered_policy",
        "guardrail": "shrink or abstain on bond, angle, clash, or energy-drift violation",
    },
    {
        "component_id": "hard_decoy_rank_corrector",
        "display_name": "Hard-Decoy Rank Corrector",
        "model_family": "GPCR hard-decoy residual rank corrector",
        "activation_mode": "assist_candidate_only",
        "primary_outputs": ["delta_score", "corrected_score", "uncertainty"],
        "training_status": "registered_shadow_ab_evidence",
        "guardrail": "preserve binder retention and avoid pass-to-fail regression",
    },
    {
        "component_id": "stage_router",
        "display_name": "Stage Router",
        "model_family": "cost-aware stage2 route policy",
        "activation_mode": "shadow_or_assist",
        "primary_outputs": ["stage2_route_decision", "uncertainty"],
        "training_status": "registered_policy",
        "guardrail": "route uncertain or high-value candidates to frozen expensive path",
    },
    {
        "component_id": "uncertainty_abstainer",
        "display_name": "Uncertainty Abstainer",
        "model_family": "OOD/uncertainty/correction-magnitude abstention policy",
        "activation_mode": "always_on_gate",
        "primary_outputs": ["uncertainty", "abstention_reason"],
        "training_status": "registered_policy",
        "guardrail": "preserve raw baseline output whenever risk is high",
    },
]

CLAIM_BOUNDARY = (
    "Residual model registry only; records the product layer contract for residual components, outputs, mode policy, "
    "uncertainty abstention, and physics guard gating. It does not train a model, create checkpoints, change rankings, "
    "promote production mode, run docking, run benchmarks, upload, submit, email, archive, externalize, or delete files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocker_values(primary_blocker: str, prefix: str) -> list[str]:
    marker = f"{prefix}:"
    for item in primary_blocker.split(";"):
        item = item.strip()
        if not item.startswith(marker):
            continue
        return [part.strip() for part in item.removeprefix(marker).split(",") if part.strip()]
    return []


def build_residual_model_registry(
    *,
    residual_shadow_packet: dict[str, Any],
    residual_assist_gate_packet: dict[str, Any],
    gpcr_breadth_gate_packet: dict[str, Any],
    public_assist_gate_packet: dict[str, Any],
    checkpoint_preflight_packet: dict[str, Any] | None = None,
    checkpoint_sidecar_packet: dict[str, Any] | None = None,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    residual_assist_gate_path: str = DEFAULT_RESIDUAL_ASSIST_GATE_JSON,
    gpcr_breadth_gate_path: str = DEFAULT_GPCR_BREADTH_GATE_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    checkpoint_preflight_path: str = DEFAULT_CHECKPOINT_PREFLIGHT_JSON,
    checkpoint_sidecar_path: str = DEFAULT_CHECKPOINT_SIDECAR_JSON,
) -> dict[str, Any]:
    residual = _summary(residual_shadow_packet)
    assist = _summary(residual_assist_gate_packet)
    gpcr = _summary(gpcr_breadth_gate_packet)
    public = _summary(public_assist_gate_packet)
    checkpoint = _summary(checkpoint_preflight_packet or {})
    sidecar = _summary(checkpoint_sidecar_packet or {})

    residual_mode_shadow = _text(residual.get("residual_mode")) == "shadow"
    shadow_contract_ready = (
        residual_mode_shadow
        and residual.get("raw_baseline_preserved") is True
        and residual.get("no_customer_facing_ranking_change") is True
        and residual.get("abstention_fields_present") is True
    )
    assist_gate_ready = _text(assist.get("status")) == "residual_assist_promotion_gate_ready" and assist.get("assist_promotion_allowed") is True
    gpcr_breadth_ready = (
        _text(gpcr.get("status")) == "gpcr_residual_proof_breadth_gate_ready"
        and gpcr.get("gpcr_residual_proof_breadth_gate_ready") is True
    )
    public_assist_ready = (
        _text(public.get("status")) == "public_benchmark_residual_assist_comparison_gate_ready"
        and public.get("assist_comparison_gate_ready") is True
    )
    component_ids = {row["component_id"] for row in COMPONENTS}
    required_components_present = component_ids == {
        "topograph_corrector",
        "equivariant_residual_energy_force_model",
        "physics_guard",
        "hard_decoy_rank_corrector",
        "stage_router",
        "uncertainty_abstainer",
    }
    output_fields_present = set(REQUIRED_OUTPUT_FIELDS) == {
        "delta_score",
        "corrected_score",
        "delta_energy",
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    }
    registry_ready = bool(
        shadow_contract_ready
        and assist_gate_ready
        and gpcr_breadth_ready
        and public_assist_ready
        and required_components_present
        and output_fields_present
    )
    ready_checkpoint_count = int(checkpoint.get("ready_checkpoint_count") or 0)
    checkpoint_preflight_ready = (
        _text(checkpoint.get("status")) == "residual_production_checkpoint_preflight_ready"
        and checkpoint.get("checkpoint_preflight_ready") is True
        and ready_checkpoint_count > 0
    )
    production_promotion_allowed = bool(registry_ready and checkpoint_preflight_ready)
    customer_facing_auto_correction_allowed = bool(
        production_promotion_allowed
        and ready_checkpoint_count > 0
        and checkpoint_preflight_ready
    )
    default_residual_mode = "production_guarded" if production_promotion_allowed else "shadow"
    checkpoint_primary_blocker = _text(checkpoint.get("primary_blocker")) or (
        "none" if checkpoint_preflight_ready else "checkpoint_preflight_not_ready"
    )
    checkpoint_missing_output_fields = _blocker_values(checkpoint_primary_blocker, "missing_output_fields")
    checkpoint_missing_adapter_output_policy_fields = _blocker_values(
        checkpoint_primary_blocker,
        "missing_adapter_output_policy",
    )
    production_checkpoint_blocked = not checkpoint_preflight_ready
    selected_sidecar_status = _text(sidecar.get("status"))
    selected_sidecar_ready = bool(
        selected_sidecar_status == "residual_production_checkpoint_sidecar_ready"
        and sidecar.get("sidecar_ready") is True
    )
    selected_sidecar_blockers = [str(item) for item in sidecar.get("blockers") or []]
    selected_sidecar_missing_output_fields = [str(item) for item in sidecar.get("missing_production_output_fields") or []]
    selected_sidecar_training_contract_missing_label_fields = [
        str(item) for item in sidecar.get("training_contract_missing_label_fields") or []
    ]
    selected_sidecar_training_contract_missing_output_fields = [
        str(item) for item in sidecar.get("training_contract_missing_output_fields") or []
    ]
    selected_sidecar_detail = (
        ""
        if not sidecar
        else (
            f"selected_sidecar_status={selected_sidecar_status};"
            f"selected_sidecar_ready={selected_sidecar_ready};"
            f"selected_sidecar_checkpoint_path={_text(sidecar.get('checkpoint_path'))};"
            f"selected_sidecar_blockers={','.join(selected_sidecar_blockers)};"
            f"selected_sidecar_missing_output_fields={','.join(selected_sidecar_missing_output_fields)};"
            f"selected_sidecar_training_contract_ready={sidecar.get('production_training_data_contract_ready')};"
            f"selected_sidecar_training_contract_missing_label_fields={','.join(selected_sidecar_training_contract_missing_label_fields)};"
            f"selected_sidecar_force_receipt_ready={sidecar.get('force_gpu_return_receipt_ready')};"
            f"selected_sidecar_force_receipt_operator_verified={sidecar.get('force_gpu_return_receipt_operator_verified')};"
            f"selected_sidecar_force_receipt_operator_verified_true_count={sidecar.get('force_gpu_return_receipt_operator_verified_true_count')};"
            f"selected_sidecar_force_receipt_expected_queue_rows={sidecar.get('force_gpu_return_receipt_expected_queue_rows')}"
        )
    )
    promotion_blocked_reason = (
        "none"
        if production_promotion_allowed
        else (
            "production checkpoint preflight is blocked: "
            f"{checkpoint_primary_blocker}"
            + (f";{selected_sidecar_detail}" if selected_sidecar_detail else "")
            if checkpoint_primary_blocker and checkpoint_primary_blocker != "none"
            else "trained checkpoints and production benchmark gates are required before production residual mode"
        )
    )
    rows = []
    for component in COMPONENTS:
        row = dict(component)
        row.update(
            {
                "status": "registered",
                "required_for_product_layer": True,
                "checkpoint_required_for_production": component["training_status"] != "registered_policy",
                "execution_enabled": False,
                "benchmark_executed": False,
                "external_state_mutated": False,
            }
        )
        rows.append(row)

    summary = {
        "packet_type": "residual_model_registry",
        "status": "residual_model_registry_ready" if registry_ready else "blocked_residual_model_registry",
        "registry_ready": registry_ready,
        "product_model_layer_ready": registry_ready,
        "residual_layer_name": "Betelgeuze Residual Intelligence Layer",
        "default_residual_mode": default_residual_mode,
        "residual_mode_policy_locked": residual_mode_shadow,
        "assist_mode_evidence_ready": assist_gate_ready and gpcr_breadth_ready and public_assist_ready,
        "production_promotion_allowed": production_promotion_allowed,
        "production_mode_allowed": production_promotion_allowed,
        "customer_facing_auto_correction_allowed": customer_facing_auto_correction_allowed,
        "customer_facing_score_mutation_allowed": customer_facing_auto_correction_allowed,
        "customer_facing_ranking_mutation_allowed": customer_facing_auto_correction_allowed,
        "production_promotion_blocked_reason": promotion_blocked_reason,
        "checkpoint_preflight_ready": checkpoint_preflight_ready,
        "production_checkpoint_blocked": production_checkpoint_blocked,
        "checkpoint_primary_blocker": checkpoint_primary_blocker,
        "checkpoint_missing_output_fields": checkpoint_missing_output_fields,
        "checkpoint_missing_adapter_output_policy_fields": checkpoint_missing_adapter_output_policy_fields,
        "selected_sidecar_status": selected_sidecar_status,
        "selected_sidecar_ready": selected_sidecar_ready if sidecar else None,
        "selected_sidecar_checkpoint_path": _text(sidecar.get("checkpoint_path")),
        "selected_sidecar_blockers": selected_sidecar_blockers,
        "selected_sidecar_missing_output_fields": selected_sidecar_missing_output_fields,
        "selected_sidecar_training_contract_ready": bool(sidecar.get("production_training_data_contract_ready") is True),
        "selected_sidecar_training_contract_missing_label_fields": selected_sidecar_training_contract_missing_label_fields,
        "selected_sidecar_training_contract_missing_output_fields": selected_sidecar_training_contract_missing_output_fields,
        "selected_sidecar_force_receipt_ready": bool(sidecar.get("force_gpu_return_receipt_ready") is True),
        "selected_sidecar_force_receipt_operator_verified": bool(sidecar.get("force_gpu_return_receipt_operator_verified") is True),
        "selected_sidecar_force_receipt_operator_verified_true_count": int(
            sidecar.get("force_gpu_return_receipt_operator_verified_true_count") or 0
        ),
        "selected_sidecar_force_receipt_expected_queue_rows": int(
            sidecar.get("force_gpu_return_receipt_expected_queue_rows") or 0
        ),
        "selected_sidecar_detail": selected_sidecar_detail,
        "candidate_checkpoint_count": int(checkpoint.get("candidate_checkpoint_count") or 0),
        "trained_model_checkpoint_count": ready_checkpoint_count,
        "component_count": len(rows),
        "required_component_count": 6,
        "required_components_present": required_components_present,
        "required_output_fields": REQUIRED_OUTPUT_FIELDS,
        "required_output_fields_present": output_fields_present,
        "shadow_contract_ready": shadow_contract_ready,
        "assist_gate_ready": assist_gate_ready,
        "gpcr_breadth_gate_ready": gpcr_breadth_ready,
        "public_assist_gate_ready": public_assist_ready,
        "source_artifacts": [
            residual_shadow_path,
            residual_assist_gate_path,
            gpcr_breadth_gate_path,
            public_assist_gate_path,
            checkpoint_preflight_path,
            checkpoint_sidecar_path,
        ],
        "execution_enabled": False,
        "training_executed": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Product residual model layer has ready checkpoints and benchmark-bound preflight evidence; customer-facing guarded correction can be considered."
            if production_promotion_allowed
            else "Product residual model layer is registered; keep default residual_mode=shadow and require checkpoints plus benchmark gates before customer-facing correction."
            if registry_ready
            else "Repair the missing residual layer contract input before product model layer closure."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Model Registry",
        "",
        f"- status: `{s['status']}`",
        f"- product_model_layer_ready: `{s['product_model_layer_ready']}`",
        f"- default_residual_mode: `{s['default_residual_mode']}`",
        f"- production_promotion_allowed: `{s['production_promotion_allowed']}`",
        f"- customer_facing_auto_correction_allowed: `{s['customer_facing_auto_correction_allowed']}`",
        f"- checkpoint_preflight_ready: `{s['checkpoint_preflight_ready']}`",
        f"- production_checkpoint_blocked: `{s['production_checkpoint_blocked']}`",
        f"- checkpoint_primary_blocker: `{s['checkpoint_primary_blocker']}`",
        f"- checkpoint_missing_output_fields: `{','.join(s['checkpoint_missing_output_fields'])}`",
        f"- selected_sidecar_status: `{s['selected_sidecar_status']}`",
        f"- selected_sidecar_ready: `{s['selected_sidecar_ready']}`",
        f"- selected_sidecar_detail: `{s['selected_sidecar_detail']}`",
        f"- candidate_checkpoint_count: `{s['candidate_checkpoint_count']}`",
        f"- trained_model_checkpoint_count: `{s['trained_model_checkpoint_count']}`",
        f"- component_count: `{s['component_count']}` / `{s['required_component_count']}`",
        f"- required_output_fields_present: `{s['required_output_fields_present']}`",
        "",
        "## Components",
        "",
        "| component | status | model family | activation | outputs | guardrail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        outputs = ", ".join(row["primary_outputs"])
        lines.append(
            f"| `{row['display_name']}` | `{row['status']}` | `{row['model_family']}` | "
            f"`{row['activation_mode']}` | `{outputs}` | {row['guardrail']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Residual Intelligence model registry from local evidence.")
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--residual-assist-gate-json", default=DEFAULT_RESIDUAL_ASSIST_GATE_JSON)
    parser.add_argument("--gpcr-breadth-gate-json", default=DEFAULT_GPCR_BREADTH_GATE_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--checkpoint-preflight-json", default=DEFAULT_CHECKPOINT_PREFLIGHT_JSON)
    parser.add_argument("--checkpoint-sidecar-json", default=DEFAULT_CHECKPOINT_SIDECAR_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_model_registry(
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        residual_assist_gate_packet=_read_json_if_present(args.residual_assist_gate_json),
        gpcr_breadth_gate_packet=_read_json_if_present(args.gpcr_breadth_gate_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        checkpoint_preflight_packet=_read_json_if_present(args.checkpoint_preflight_json),
        checkpoint_sidecar_packet=_read_json_if_present(args.checkpoint_sidecar_json),
        residual_shadow_path=args.residual_shadow_json,
        residual_assist_gate_path=args.residual_assist_gate_json,
        gpcr_breadth_gate_path=args.gpcr_breadth_gate_json,
        public_assist_gate_path=args.public_assist_gate_json,
        checkpoint_preflight_path=args.checkpoint_preflight_json,
        checkpoint_sidecar_path=args.checkpoint_sidecar_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
