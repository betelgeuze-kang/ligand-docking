from __future__ import annotations

import json
from pathlib import Path

from tools import build_commercial_gap_closure_status as mod


def _e2e() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_end_to_end_rocm_benchmark_ready",
            "benchmark_ready": True,
            "docking_results_emitted": True,
            "processed_jobs": 10000,
            "scored_rows": 640,
            "jobs_per_hour": 100000.0,
            "unique_ligands_per_hour": 2000.0,
            "production_trajectory_profile_enabled": False,
            "bundle_zip_present": True,
            "bundle_validation_ok": True,
        }
    }


def _packaging() -> dict[str, object]:
    return {
        "summary": {
            "status": "amd_workstation_server_packaging_profile_ready",
            "workstation_profile_ready": True,
            "visible_device_count": 1,
            "current_topology": "single_gpu",
            "commercial_compute_default": "rocm_hip",
            "supported_amd_gpu_family": ["AMD Radeon RX 6900 XT"],
        }
    }


def _residual() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_shadow_ab_scaffold_ready",
            "residual_mode": "shadow",
            "assist_promotion_allowed": False,
            "production_promotion_allowed": False,
        }
    }


def _gpcr() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_hard_decoy_residual_proof_ready",
            "task_count": 2,
            "pr_auc_regression_warning_count": 1,
        }
    }


def _gpcr_breadth() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_residual_proof_breadth_gate_ready",
            "gpcr_residual_proof_breadth_gate_ready": True,
            "effective_gpcr_breadth_count": 7,
            "pr_auc_regression_warning_count": 0,
        }
    }


def _residual_registry() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_model_registry_ready",
            "registry_ready": True,
            "product_model_layer_ready": True,
            "default_residual_mode": "shadow",
            "production_promotion_allowed": False,
            "required_output_fields_present": True,
        }
    }


def _production_residual_registry() -> dict[str, object]:
    registry = _residual_registry()
    registry["summary"].update(  # type: ignore[index, union-attr]
        {
            "default_residual_mode": "production_guarded",
            "production_promotion_allowed": True,
            "production_mode_allowed": True,
            "customer_facing_auto_correction_allowed": True,
            "customer_facing_score_mutation_allowed": True,
            "customer_facing_ranking_mutation_allowed": True,
            "trained_model_checkpoint_count": 1,
            "checkpoint_preflight_ready": True,
            "production_checkpoint_blocked": False,
            "selected_sidecar_ready": True,
            "checkpoint_missing_output_fields": [],
            "checkpoint_missing_adapter_output_policy_fields": [],
        }
    )
    return registry


def _production_checkpoint_readiness() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_production_ai_checkpoint_readiness_ready",
            "production_ai_checkpoint_ready": True,
            "production_ai_inference_subject_active": True,
            "production_promotion_allowed": True,
            "trained_model_checkpoint_count": 1,
            "ready_checkpoint_count": 1,
            "checkpoint_preflight_ready": True,
            "selected_sidecar_ready": True,
        }
    }


def _public() -> dict[str, object]:
    return {
        "summary": {
            "status": "public_benchmark_residual_regression_gate_ready",
            "assist_promotion_allowed": False,
            "production_promotion_allowed": False,
        }
    }


def _alpha() -> dict[str, object]:
    return {"summary": {"status": "customer_alpha_bundle_manifest_ready", "customer_alpha_bundle_ready": True}}


def _commercial() -> dict[str, object]:
    return {
        "summary": {
            "local_self_hosted_api_cli_ready": True,
            "product_service_boundary_ready": True,
            "product_api_contract_ready": True,
            "delete_executed": False,
            "external_state_mutated": False,
        }
    }


def test_commercial_gap_closure_status_tracks_open_residual_gaps() -> None:
    payload = mod.build_commercial_gap_closure_status(
        e2e_benchmark_packet=_e2e(),
        packaging_packet=_packaging(),
        residual_shadow_packet=_residual(),
        gpcr_proof_packet=_gpcr(),
        public_regression_packet=_public(),
        customer_alpha_packet=_alpha(),
        commercial_independence_packet=_commercial(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_commercial_gap_closure"
    assert summary["all_gaps_closed"] is False
    assert summary["closed_gap_count"] == 6
    assert summary["open_item_ids"] == [3, 4, 5, 10]
    assert summary["item6_scope"] == "current_personal_single_gpu_amd_pc"


def test_commercial_gap_closure_status_complete_when_all_evidence_is_promoted() -> None:
    residual = _residual()
    residual["summary"]["assist_promotion_allowed"] = True  # type: ignore[index]
    gpcr = _gpcr()
    gpcr["summary"]["task_count"] = 5  # type: ignore[index]
    gpcr["summary"]["pr_auc_regression_warning_count"] = 0  # type: ignore[index]
    public = _public()
    public["summary"]["assist_promotion_allowed"] = True  # type: ignore[index]
    payload = mod.build_commercial_gap_closure_status(
        e2e_benchmark_packet=_e2e(),
        packaging_packet=_packaging(),
        residual_shadow_packet=residual,
        gpcr_proof_packet=gpcr,
        public_regression_packet=public,
        residual_model_registry_packet=_production_residual_registry(),
        production_ai_checkpoint_readiness_packet=_production_checkpoint_readiness(),
        customer_alpha_packet=_alpha(),
        commercial_independence_packet=_commercial(),
    )

    summary = payload["summary"]
    assert summary["status"] == "commercial_gap_closure_complete"
    assert summary["closed_gap_count"] == 10
    assert summary["open_item_ids"] == []
    assert summary["residual_model_product_ready"] is True
    assert summary["production_ai_inference_subject_active"] is True


def test_commercial_gap_closure_status_uses_gpcr_breadth_gate_for_item4() -> None:
    residual = _residual()
    residual["summary"]["assist_promotion_allowed"] = True  # type: ignore[index]
    public = _public()
    public["summary"]["assist_promotion_allowed"] = True  # type: ignore[index]

    payload = mod.build_commercial_gap_closure_status(
        e2e_benchmark_packet=_e2e(),
        packaging_packet=_packaging(),
        residual_shadow_packet=residual,
        gpcr_proof_packet=_gpcr(),
        gpcr_breadth_gate_packet=_gpcr_breadth(),
        public_regression_packet=public,
        customer_alpha_packet=_alpha(),
        commercial_independence_packet=_commercial(),
    )

    item4 = [row for row in payload["rows"] if row["item_id"] == 4][0]
    summary = payload["summary"]
    assert item4["status"] == "closed"
    assert summary["open_item_ids"] == [10]


def test_commercial_gap_closure_status_keeps_shadow_registry_open_for_production_model() -> None:
    residual = _residual()
    assist_gate = {"summary": {"status": "residual_assist_promotion_gate_ready", "assist_promotion_allowed": True}}
    public_assist = {"summary": {"status": "public_benchmark_residual_assist_comparison_gate_ready", "assist_comparison_gate_ready": True}}

    payload = mod.build_commercial_gap_closure_status(
        e2e_benchmark_packet=_e2e(),
        packaging_packet=_packaging(),
        residual_shadow_packet=residual,
        residual_assist_gate_packet=assist_gate,
        gpcr_proof_packet=_gpcr(),
        gpcr_breadth_gate_packet=_gpcr_breadth(),
        public_regression_packet=_public(),
        public_assist_gate_packet=public_assist,
        residual_model_registry_packet=_residual_registry(),
        customer_alpha_packet=_alpha(),
        commercial_independence_packet=_commercial(),
    )

    summary = payload["summary"]
    item10 = [row for row in payload["rows"] if row["item_id"] == 10][0]
    assert summary["status"] == "blocked_commercial_gap_closure"
    assert summary["closed_gap_count"] == 9
    assert summary["open_item_ids"] == [10]
    assert summary["residual_model_registry_ready"] is True
    assert summary["residual_model_product_ready"] is False
    assert item10["status"] == "open"
    assert "registered_layer_ready=True" in item10["observed"]
    assert "production_promotion_allowed=False" in item10["observed"]


def test_commercial_gap_closure_status_cli_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "e2e": _e2e(),
        "packaging": _packaging(),
        "residual": _residual(),
        "gpcr": _gpcr(),
        "public": _public(),
        "alpha": _alpha(),
        "commercial": _commercial(),
    }
    written: dict[str, Path] = {}
    for name, packet in paths.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        written[name] = path
    out_json = tmp_path / "closure.json"
    out_csv = tmp_path / "closure.csv"
    out_md = tmp_path / "closure.md"

    mod.main(
        [
            "--e2e-benchmark-json",
            str(written["e2e"]),
            "--packaging-json",
            str(written["packaging"]),
            "--residual-shadow-json",
            str(written["residual"]),
            "--residual-assist-gate-json",
            str(tmp_path / "missing_residual_assist_gate.json"),
            "--gpcr-proof-json",
            str(written["gpcr"]),
            "--gpcr-breadth-gate-json",
            str(tmp_path / "missing_gpcr_breadth_gate.json"),
            "--public-regression-json",
            str(written["public"]),
            "--public-assist-gate-json",
            str(tmp_path / "missing_public_assist_gate.json"),
            "--residual-model-registry-json",
            str(tmp_path / "missing_residual_model_registry.json"),
            "--production-ai-checkpoint-readiness-json",
            str(tmp_path / "missing_production_ai_checkpoint_readiness.json"),
            "--customer-alpha-json",
            str(written["alpha"]),
            "--commercial-independence-json",
            str(written["commercial"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["open_item_ids"] == [3, 4, 5, 10]
    assert "item_id" in out_csv.read_text(encoding="utf-8")
    assert "Commercial Gap Closure Status" in out_md.read_text(encoding="utf-8")
