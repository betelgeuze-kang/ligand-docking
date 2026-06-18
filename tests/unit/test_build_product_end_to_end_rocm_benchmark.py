from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_end_to_end_rocm_benchmark as mod


def _run_summary() -> dict[str, object]:
    return {
        "pass": True,
        "run_scope": "full",
        "artifacts": {"trajectory_engine_mode": "rust_hip"},
        "traj_prod": {"enabled": False},
        "stages": {
            "stage0_leakage_audit": {"ok": True, "duration_sec": 1.0},
            "stage1_ligand_mapping": {"ok": True, "duration_sec": 2.0},
            "stage2_trajectory_generation": {"ok": True, "duration_sec": 20.0},
            "stage3_backmapping_scoring": {"ok": True, "duration_sec": 4.0},
            "stage45_eval_integrity": {"ok": True, "duration_sec": 1.0},
            "stage5_ranking_eval": {"ok": True, "duration_sec": 2.0},
        },
    }


def _rocm() -> dict[str, object]:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "torch_rocm_ready": True,
            "visible_device_count": 1,
            "device_nodes_ready": True,
            "production_execution_ready": True,
            "commercial_compute_default": "rocm_hip",
            "cpu_fallback_allowed_for_product": False,
        }
    }


def _stage1() -> dict[str, object]:
    return {"queue_rows": 10000, "ligands": 206}


def _stage2() -> dict[str, object]:
    return {"processed_rows": 10000, "failed_rows": 0, "require_rust_hip": True, "prod_mode": False}


def _stage3() -> dict[str, object]:
    return {"processed_jobs": 640, "replicate_group_count": 200}


def _stage5() -> dict[str, object]:
    return {"pass": True, "rows_scores": 640, "rows_eval": 200, "observed_expected_score_coverage_ratio": 1.0}


def _ai_md_kpi() -> dict[str, object]:
    return {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready",
        "report_ready": True,
        "product_bundle_evidence_export_ready": True,
        "pose_ranking_hbond_benchmark": {
            "benchmark_ready": True,
            "top1_pose_id": "amide_near_hbond_pose",
            "overanchored_decoys_blocked": True,
        },
    }


def _product_image_preflight(*, ready: bool = True) -> dict[str, object]:
    return {
        "summary": {
            "status": "product_image_smoke_preflight_ready"
            if ready
            else "blocked_product_image_smoke_preflight",
            "preflight_ready": ready,
            "clean_container_smoke_ready": ready,
            "receipt_present": ready,
            "receipt_status": "product_image_smoke_ready" if ready else "blocked_product_image_smoke",
            "receipt_mode": "rocm-runtime" if ready else "build",
            "receipt_simulate_missing_profile_http": 422 if ready else 0,
            "container_runtime_receipt_ready": ready,
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1" if ready else "",
            "container_runtime_in_container": ready,
            "container_runtime_device_nodes_ready": ready,
            "container_runtime_torch_rocm_ready": ready,
            "container_runtime_torch_cuda_available": ready,
            "container_runtime_visible_device_count": 1 if ready else 0,
            "container_runtime_rust_hip_backend_enabled": ready,
            "product_runner_smoke_ready": ready,
        }
    }


def _backmapping_smoke() -> dict[str, object]:
    return {
        "summary": {
            "status": "backmapping_scoring_batch_smoke_benchmark_ready",
            "batch_frames_per_sec": 250.0,
        }
    }


def _payload(tmp_path: Path, **overrides: dict[str, object]) -> dict[str, object]:
    bundle_dir = tmp_path / "bundle_product_gpcr_adrb2"
    bundle_dir.mkdir()
    (bundle_dir / "bundle.zip").write_bytes(b"zip")
    packets = {
        "run_summary_packet": _run_summary(),
        "rocm_manifest_packet": _rocm(),
        "bundle_manifest_packet": {"bundle_dir": str(bundle_dir)},
        "bundle_validation_packet": {"overall_ok": True, "blocker_count": 0},
        "stage1_packet": _stage1(),
        "stage2_packet": _stage2(),
        "stage3_packet": _stage3(),
        "stage5_packet": _stage5(),
        "sla_packet": {"total_latency_sec": 30.0},
        "backmapping_smoke_packet": _backmapping_smoke(),
        "ai_md_engine_kpi_packet": _ai_md_kpi(),
        "product_image_smoke_preflight_packet": _product_image_preflight(),
    }
    packets.update(overrides)
    return mod.build_product_end_to_end_rocm_benchmark(**packets)


def test_product_end_to_end_rocm_benchmark_ready(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "product_end_to_end_rocm_benchmark_ready"
    assert summary["benchmark_ready"] is True
    assert summary["processed_jobs"] == 10000
    assert summary["unique_ligands_scored"] == 200
    assert summary["jobs_per_hour"] > 0
    assert summary["trajectory_engine_mode"] == "rust_hip"
    assert summary["rocm_hip_rust_runtime_ready"] is True
    assert summary["rocm_visible_device_count"] == 1
    assert summary["rocm_device_nodes_ready"] is True
    assert summary["production_trajectory_profile_enabled"] is False
    assert summary["warning_component_count"] == 1
    assert summary["ai_md_engine_kpi_report_ready"] is True
    assert summary["ai_md_engine_kpi_pose_ranking_hbond_ready"] is True
    assert summary["clean_container_smoke_ready"] is True
    assert summary["product_image_smoke_receipt_mode"] == "rocm-runtime"
    assert summary["product_image_smoke_container_runtime_receipt_ready"] is True
    assert summary["product_image_smoke_container_runtime_rust_hip_backend_enabled"] is True
    assert summary["docking_results_emitted"] is True
    assert summary["external_state_mutated"] is False


def test_product_end_to_end_rocm_benchmark_blocks_missing_stage(tmp_path: Path) -> None:
    run_summary = _run_summary()
    run_summary["stages"]["stage3_backmapping_scoring"]["ok"] = False  # type: ignore[index]

    payload = _payload(tmp_path, run_summary_packet=run_summary)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_end_to_end_rocm_benchmark"
    assert summary["benchmark_ready"] is False
    assert summary["fail_component_count"] >= 1


def test_product_end_to_end_rocm_benchmark_blocks_when_rocm_gpu_not_visible(tmp_path: Path) -> None:
    rocm = _rocm()
    rocm["summary"]["torch_rocm_ready"] = False  # type: ignore[index]
    rocm["summary"]["visible_device_count"] = 0  # type: ignore[index]
    rocm["summary"]["device_nodes_ready"] = False  # type: ignore[index]
    rocm["summary"]["production_execution_ready"] = False  # type: ignore[index]

    payload = _payload(tmp_path, rocm_manifest_packet=rocm)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_end_to_end_rocm_benchmark"
    assert summary["rocm_hip_rust_runtime_ready"] is False
    assert summary["rocm_visible_device_count"] == 0
    assert summary["rocm_device_nodes_ready"] is False


def test_product_end_to_end_rocm_benchmark_blocks_without_clean_container_smoke(
    tmp_path: Path,
) -> None:
    payload = _payload(
        tmp_path,
        product_image_smoke_preflight_packet=_product_image_preflight(ready=False),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_end_to_end_rocm_benchmark"
    assert summary["benchmark_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert any(row["component"] == "clean_container_rocm_runtime_smoke" for row in payload["rows"])


def test_product_end_to_end_rocm_benchmark_cli_writes_outputs(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle_product_gpcr_adrb2"
    bundle_dir.mkdir()
    (bundle_dir / "bundle.zip").write_bytes(b"zip")
    files = {
        "run.json": _run_summary(),
        "rocm.json": _rocm(),
        "manifest.json": {"bundle_dir": str(bundle_dir)},
        "validation.json": {"overall_ok": True, "blocker_count": 0},
        "stage1.json": _stage1(),
        "stage2.json": _stage2(),
        "stage3.json": _stage3(),
        "stage5.json": _stage5(),
        "sla.json": {"total_latency_sec": 30.0},
        "backmapping.json": _backmapping_smoke(),
        "kpi.json": _ai_md_kpi(),
        "preflight.json": _product_image_preflight(),
    }
    for name, packet in files.items():
        (tmp_path / name).write_text(json.dumps(packet) + "\n", encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--run-summary-json",
            str(tmp_path / "run.json"),
            "--rocm-manifest-json",
            str(tmp_path / "rocm.json"),
            "--bundle-manifest-json",
            str(tmp_path / "manifest.json"),
            "--bundle-validation-json",
            str(tmp_path / "validation.json"),
            "--stage1-summary-json",
            str(tmp_path / "stage1.json"),
            "--stage2-summary-json",
            str(tmp_path / "stage2.json"),
            "--stage3-summary-json",
            str(tmp_path / "stage3.json"),
            "--stage5-summary-json",
            str(tmp_path / "stage5.json"),
            "--sla-summary-json",
            str(tmp_path / "sla.json"),
            "--backmapping-smoke-json",
            str(tmp_path / "backmapping.json"),
            "--ai-md-engine-kpi-json",
            str(tmp_path / "kpi.json"),
            "--product-image-smoke-preflight-json",
            str(tmp_path / "preflight.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["benchmark_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["ai_md_engine_kpi_report_ready"] is True
    assert "component" in out_csv.read_text(encoding="utf-8")
    assert "Product End-to-End ROCm Benchmark" in out_md.read_text(encoding="utf-8")
