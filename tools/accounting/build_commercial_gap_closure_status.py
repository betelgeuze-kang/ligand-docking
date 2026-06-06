#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_E2E_BENCHMARK_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_PACKAGING_JSON = "runs/amd_workstation_server_packaging_profile_current.json"
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_RESIDUAL_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_GPCR_BREADTH_GATE_JSON = "runs/gpcr_residual_proof_breadth_gate_current.json"
DEFAULT_PUBLIC_REGRESSION_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_CUSTOMER_ALPHA_JSON = "runs/customer_alpha_bundle_manifest_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_OUT_JSON = "runs/commercial_gap_closure_status_current.json"
DEFAULT_OUT_CSV = "runs/commercial_gap_closure_status_current.csv"
DEFAULT_OUT_MD = "runs/commercial_gap_closure_status_current.md"

CLAIM_BOUNDARY = (
    "Commercial gap closure status only; audits local evidence for the ten known productization gaps. It does not run "
    "docking, benchmarks, model training, package installs, cleanup, uploads, submissions, email, archive, "
    "externalization, or deletion. Item 6 is scoped to the current personal single-GPU AMD PC profile until separate "
    "multi-GPU server hardware evidence exists."
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
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row(
    item_id: int,
    gap: str,
    status: str,
    evidence: str,
    observed: str,
    close_requirement: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "close_requirement": close_requirement,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_commercial_gap_closure_status(
    *,
    e2e_benchmark_packet: dict[str, Any],
    packaging_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
    gpcr_proof_packet: dict[str, Any],
    public_regression_packet: dict[str, Any],
    customer_alpha_packet: dict[str, Any],
    commercial_independence_packet: dict[str, Any],
    residual_assist_gate_packet: dict[str, Any] | None = None,
    gpcr_breadth_gate_packet: dict[str, Any] | None = None,
    public_assist_gate_packet: dict[str, Any] | None = None,
    residual_model_registry_packet: dict[str, Any] | None = None,
    production_ai_checkpoint_readiness_packet: dict[str, Any] | None = None,
    e2e_benchmark_path: str = DEFAULT_E2E_BENCHMARK_JSON,
    packaging_path: str = DEFAULT_PACKAGING_JSON,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    residual_assist_gate_path: str = DEFAULT_RESIDUAL_ASSIST_GATE_JSON,
    gpcr_proof_path: str = DEFAULT_GPCR_PROOF_JSON,
    gpcr_breadth_gate_path: str = DEFAULT_GPCR_BREADTH_GATE_JSON,
    public_regression_path: str = DEFAULT_PUBLIC_REGRESSION_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    customer_alpha_path: str = DEFAULT_CUSTOMER_ALPHA_JSON,
    commercial_independence_path: str = DEFAULT_COMMERCIAL_INDEPENDENCE_JSON,
    residual_model_registry_path: str = DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON,
    production_ai_checkpoint_readiness_path: str = DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON,
) -> dict[str, Any]:
    e2e = _summary(e2e_benchmark_packet)
    packaging = _summary(packaging_packet)
    residual = _summary(residual_shadow_packet)
    assist_gate = _summary(residual_assist_gate_packet or {})
    gpcr = _summary(gpcr_proof_packet)
    gpcr_breadth = _summary(gpcr_breadth_gate_packet or {})
    public_regression = _summary(public_regression_packet)
    public_assist = _summary(public_assist_gate_packet or {})
    registry = _summary(residual_model_registry_packet or {})
    checkpoint_readiness = _summary(production_ai_checkpoint_readiness_packet or {})
    alpha = _summary(customer_alpha_packet)
    commercial = _summary(commercial_independence_packet)

    e2e_ready = _text(e2e.get("status")) == "product_end_to_end_rocm_benchmark_ready" and e2e.get("benchmark_ready") is True
    real_throughput_ready = e2e_ready and _float(e2e.get("jobs_per_hour")) > 0 and _float(e2e.get("unique_ligands_per_hour")) > 0
    residual_assist_ready = (
        assist_gate.get("assist_promotion_allowed") is True
        or residual.get("assist_promotion_allowed") is True
    )
    gpcr_broad_ready = (
        gpcr_breadth.get("gpcr_residual_proof_breadth_gate_ready") is True
        or (
            _text(gpcr.get("status")) == "gpcr_hard_decoy_residual_proof_ready"
            and _int(gpcr.get("task_count")) >= 5
            and _int(gpcr.get("pr_auc_regression_warning_count")) == 0
        )
    )
    public_improvement_ready = (
        public_assist.get("assist_comparison_gate_ready") is True
        or (
            _text(public_regression.get("status")) == "public_benchmark_residual_regression_gate_ready"
            and public_regression.get("assist_promotion_allowed") is True
        )
    )
    personal_pc_ready = (
        _text(packaging.get("status")) == "amd_workstation_server_packaging_profile_ready"
        and packaging.get("workstation_profile_ready") is True
        and _int(packaging.get("visible_device_count")) >= 1
        and _text(packaging.get("commercial_compute_default")) == "rocm_hip"
    )
    delivery_package_ready = (
        _text(alpha.get("status")) == "customer_alpha_bundle_manifest_ready"
        and alpha.get("customer_alpha_bundle_ready") is True
        and e2e.get("bundle_zip_present") is True
        and e2e.get("bundle_validation_ok") is True
    )
    ux_api_ops_ready = (
        commercial.get("local_self_hosted_api_cli_ready") is True
        and commercial.get("product_service_boundary_ready") is True
        and commercial.get("product_api_contract_ready") is True
    )
    storage_policy_ready = (
        commercial.get("delete_executed") is False
        and commercial.get("external_state_mutated") is False
        and Path(ROOT / "docs/local_delivery_claim_policy.md").exists()
        and Path(ROOT / "docs/local_delivery_runbook.md").exists()
    )
    residual_model_registry_ready = (
        registry.get("product_model_layer_ready") is True
        and registry.get("registry_ready") is True
        and _text(registry.get("default_residual_mode")) == "shadow"
        and registry.get("production_promotion_allowed") is False
        and registry.get("required_output_fields_present") is True
    )
    registry_production_inference_ready = (
        registry.get("product_model_layer_ready") is True
        and registry.get("registry_ready") is True
        and registry.get("production_promotion_allowed") is True
        and registry.get("production_mode_allowed") is True
        and registry.get("customer_facing_auto_correction_allowed") is True
        and registry.get("customer_facing_score_mutation_allowed") is True
        and registry.get("customer_facing_ranking_mutation_allowed") is True
        and _int(registry.get("trained_model_checkpoint_count")) > 0
        and registry.get("checkpoint_preflight_ready") is True
        and registry.get("production_checkpoint_blocked") is False
        and registry.get("selected_sidecar_ready") is True
        and not list(registry.get("checkpoint_missing_output_fields") or [])
        and not list(registry.get("checkpoint_missing_adapter_output_policy_fields") or [])
        and _text(registry.get("default_residual_mode")) in {"assist", "production", "production_guarded"}
    )
    checkpoint_readiness_production_inference_ready = (
        checkpoint_readiness.get("production_ai_checkpoint_ready") is True
        and checkpoint_readiness.get("production_ai_inference_subject_active") is True
        and _int(checkpoint_readiness.get("trained_model_checkpoint_count")) > 0
        and _int(checkpoint_readiness.get("ready_checkpoint_count")) > 0
        and checkpoint_readiness.get("checkpoint_preflight_ready") is True
        and checkpoint_readiness.get("selected_sidecar_ready") is True
        and checkpoint_readiness.get("production_promotion_allowed") is True
    )
    residual_model_product_ready = (
        registry_production_inference_ready
        or checkpoint_readiness_production_inference_ready
    )

    rows = [
        _row(
            1,
            "actual end-to-end production docking execution evidence",
            "closed" if e2e_ready and e2e.get("docking_results_emitted") is True else "open",
            e2e_benchmark_path,
            f"status={e2e.get('status')}; processed_jobs={e2e.get('processed_jobs')}; scored_rows={e2e.get('scored_rows')}",
            "completed full local run with ROCm/HIP trajectory, scoring, ranking, and bundle evidence",
            "Promote the current GPCR run as the first local end-to-end baseline, then repeat on larger/more diverse requests.",
        ),
        _row(
            2,
            "real ROCm end-to-end throughput, not proxy-only speed",
            "closed" if real_throughput_ready else "open",
            e2e_benchmark_path,
            f"jobs_per_hour={e2e.get('jobs_per_hour')}; unique_ligands_per_hour={e2e.get('unique_ligands_per_hour')}; production_profile={e2e.get('production_trajectory_profile_enabled')}",
            "positive throughput from a completed full local run",
            "Harden the production trajectory profile and collect N=100/1k/10k repeat scorecards on the same PC.",
        ),
        _row(
            3,
            "Residual Intelligence assist promotion",
            "closed" if residual_assist_ready else "open",
            f"{residual_shadow_path}; {residual_assist_gate_path}",
            f"residual_mode={residual.get('residual_mode')}; assist_gate_status={assist_gate.get('status')}; assist_promotion_allowed={residual_assist_ready}",
            "assist mode allowed by residual assist promotion gate",
            "Repair residual assist promotion gate blockers, starting with the gate primary blocker.",
        ),
        _row(
            4,
            "GPCR residual proof breadth",
            "closed" if gpcr_broad_ready else "open",
            f"{gpcr_proof_path}; {gpcr_breadth_gate_path}",
            f"proof_task_count={gpcr.get('task_count')}; proof_pr_auc_warning_count={gpcr.get('pr_auc_regression_warning_count')}; breadth_gate_status={gpcr_breadth.get('status')}; effective_gpcr_breadth_count={gpcr_breadth.get('effective_gpcr_breadth_count')}",
            ">=5 effective GPCR breadth units and zero routed PR-AUC regression warnings",
            "Expand hard-decoy residual proof beyond the current narrow slice.",
        ),
        _row(
            5,
            "public benchmark residual assist comparison evidence",
            "closed" if public_improvement_ready else "open",
            f"{public_regression_path}; {public_assist_gate_path}",
            f"assist_gate_status={public_assist.get('status')}; missing_assist_comparison_count={public_assist.get('missing_assist_comparison_count')}; assist_promotion_allowed={public_regression.get('assist_promotion_allowed')}",
            "per-suite public benchmark residual assist comparison proves no pass-to-fail or metric regression",
            "Add suite-specific assist replay before claiming public-suite metric improvement.",
        ),
        _row(
            6,
            "current personal AMD PC appliance profile",
            "closed" if personal_pc_ready else "open",
            packaging_path,
            f"topology={packaging.get('current_topology')}; visible_device_count={packaging.get('visible_device_count')}; gpu={packaging.get('supported_amd_gpu_family')}",
            "single-GPU AMD ROCm workstation profile ready on the current personal PC",
            "Keep server/multi-GPU claims out of scope until separate hardware exists; tune this PC profile first.",
        ),
        _row(
            7,
            "actual customer alpha delivery package",
            "closed" if delivery_package_ready else "open",
            f"{customer_alpha_path}; {e2e_benchmark_path}",
            f"alpha_ready={alpha.get('customer_alpha_bundle_ready')}; bundle_zip_present={e2e.get('bundle_zip_present')}; bundle_validation_ok={e2e.get('bundle_validation_ok')}",
            "validated bundle.zip plus alpha manifest",
            "Create a signed/offline customer bundle after the current unsigned local bundle baseline is stable.",
        ),
        _row(
            8,
            "customer-facing UX/API/operations surface",
            "closed" if ux_api_ops_ready else "open",
            commercial_independence_path,
            f"api_cli_ready={commercial.get('local_self_hosted_api_cli_ready')}; service_boundary_ready={commercial.get('product_service_boundary_ready')}; api_contract_ready={commercial.get('product_api_contract_ready')}",
            "local self-hosted API/CLI and service boundary ready",
            "Add job queue persistence, retry/progress UX, and customer report viewer as the next hardening layer.",
        ),
        _row(
            9,
            "storage, retention, and protected heavy-artifact policy",
            "closed" if storage_policy_ready else "open",
            f"{commercial_independence_path}; docs/local_delivery_claim_policy.md; docs/local_delivery_runbook.md",
            f"delete_executed={commercial.get('delete_executed')}; external_state_mutated={commercial.get('external_state_mutated')}",
            "local claim/runbook policy exists and no cleanup/delete has been executed by productization gates",
            "Convert protected heavy-artifact retention into a first-class product admin policy.",
        ),
        _row(
            10,
            "Residual Intelligence production model layer",
            "closed" if residual_model_product_ready else "open",
            f"{residual_shadow_path}; {public_regression_path}; {residual_model_registry_path}; {production_ai_checkpoint_readiness_path}",
            f"registry_status={registry.get('status')}; registered_layer_ready={residual_model_registry_ready}; product_model_layer_ready={registry.get('product_model_layer_ready')}; default_residual_mode={registry.get('default_residual_mode')}; production_promotion_allowed={registry.get('production_promotion_allowed')}; production_mode_allowed={registry.get('production_mode_allowed')}; trained_model_checkpoint_count={registry.get('trained_model_checkpoint_count')}; checkpoint_preflight_ready={registry.get('checkpoint_preflight_ready')}; selected_sidecar_ready={registry.get('selected_sidecar_ready')}; production_ai_checkpoint_ready={checkpoint_readiness.get('production_ai_checkpoint_ready')}; production_ai_inference_subject_active={checkpoint_readiness.get('production_ai_inference_subject_active')}",
            "trained checkpoint is preflight-ready, sidecar-bound, customer-facing guarded mode is allowed, and production inference subject is active",
            "Return GPU force-label evidence, train/promote a guarded checkpoint, bind sidecar metadata, rerun preflight, then rebuild production AI checkpoint readiness.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "commercial_gap_closure_status",
        "status": "commercial_gap_closure_complete" if not open_rows else "blocked_commercial_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "completion_percent": round((len(closed_rows) / len(rows)) * 100.0, 3),
        "item6_scope": "current_personal_single_gpu_amd_pc",
        "current_primary_open_item": first_open["item_id"] if first_open else "none",
        "current_primary_open_gap": first_open["gap"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All ten gaps are closed.",
        "closed_item_ids": [row["item_id"] for row in closed_rows],
        "open_item_ids": [row["item_id"] for row in open_rows],
        "residual_model_registry_ready": residual_model_registry_ready,
        "registry_production_inference_ready": registry_production_inference_ready,
        "checkpoint_readiness_production_inference_ready": checkpoint_readiness_production_inference_ready,
        "residual_model_product_ready": residual_model_product_ready,
        "production_ai_checkpoint_ready": checkpoint_readiness.get("production_ai_checkpoint_ready") is True,
        "production_ai_inference_subject_active": checkpoint_readiness.get("production_ai_inference_subject_active") is True,
        "trained_model_checkpoint_count": _int(
            checkpoint_readiness.get("trained_model_checkpoint_count") or registry.get("trained_model_checkpoint_count")
        ),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
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
        "# Commercial Gap Closure Status",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        f"- completion_percent: `{s['completion_percent']}`",
        f"- item6_scope: `{s['item6_scope']}`",
        f"- current_primary_open_item: `{s['current_primary_open_item']}`",
        f"- current_primary_open_gap: `{s['current_primary_open_gap']}`",
        "",
        "## Gaps",
        "",
        "| item | status | gap | observed | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['item_id']}` | `{row['status']}` | {row['gap']} | `{row['observed']}` | {row['next_action']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Current Next Action", "", f"- {s['current_next_action']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build closure status for the ten commercial productization gaps.")
    parser.add_argument("--e2e-benchmark-json", default=DEFAULT_E2E_BENCHMARK_JSON)
    parser.add_argument("--packaging-json", default=DEFAULT_PACKAGING_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--residual-assist-gate-json", default=DEFAULT_RESIDUAL_ASSIST_GATE_JSON)
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--gpcr-breadth-gate-json", default=DEFAULT_GPCR_BREADTH_GATE_JSON)
    parser.add_argument("--public-regression-json", default=DEFAULT_PUBLIC_REGRESSION_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--customer-alpha-json", default=DEFAULT_CUSTOMER_ALPHA_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--residual-model-registry-json", default=DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON)
    parser.add_argument("--production-ai-checkpoint-readiness-json", default=DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_commercial_gap_closure_status(
        e2e_benchmark_packet=_read_json_if_present(args.e2e_benchmark_json),
        packaging_packet=_read_json_if_present(args.packaging_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        residual_assist_gate_packet=_read_json_if_present(args.residual_assist_gate_json),
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        gpcr_breadth_gate_packet=_read_json_if_present(args.gpcr_breadth_gate_json),
        public_regression_packet=_read_json_if_present(args.public_regression_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        residual_model_registry_packet=_read_json_if_present(args.residual_model_registry_json),
        production_ai_checkpoint_readiness_packet=_read_json_if_present(args.production_ai_checkpoint_readiness_json),
        customer_alpha_packet=_read_json_if_present(args.customer_alpha_json),
        commercial_independence_packet=_read_json_if_present(args.commercial_independence_json),
        e2e_benchmark_path=args.e2e_benchmark_json,
        packaging_path=args.packaging_json,
        residual_shadow_path=args.residual_shadow_json,
        residual_assist_gate_path=args.residual_assist_gate_json,
        gpcr_proof_path=args.gpcr_proof_json,
        gpcr_breadth_gate_path=args.gpcr_breadth_gate_json,
        public_regression_path=args.public_regression_json,
        public_assist_gate_path=args.public_assist_gate_json,
        customer_alpha_path=args.customer_alpha_json,
        commercial_independence_path=args.commercial_independence_json,
        residual_model_registry_path=args.residual_model_registry_json,
        production_ai_checkpoint_readiness_path=args.production_ai_checkpoint_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
