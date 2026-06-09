#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_SUMMARY_JSON = "runs/local_delivery/bundle_product_gpcr_adrb2/artifacts/product_gpcr_adrb2_after_approval_summary.json"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_BUNDLE_MANIFEST_JSON = "runs/local_delivery/bundle_product_gpcr_adrb2/manifest.json"
DEFAULT_BUNDLE_VALIDATION_JSON = "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json"
DEFAULT_STAGE1_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_stage1_summary.json"
DEFAULT_STAGE2_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_stage2_traj_summary.json"
DEFAULT_STAGE3_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_stage3_summary.json"
DEFAULT_STAGE5_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_stage5_ranking_summary.json"
DEFAULT_SLA_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_sla_summary.json"
DEFAULT_OUT_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_BACKMAPPING_SMOKE_JSON = "runs/backmapping_scoring_batch_smoke_benchmark_current.json"
DEFAULT_OUT_CSV = "runs/product_end_to_end_rocm_benchmark_current.csv"
DEFAULT_OUT_MD = "runs/product_end_to_end_rocm_benchmark_current.md"

CLAIM_BOUNDARY = (
    "Product end-to-end ROCm benchmark evidence only; reconciles an existing local GPCR execution summary, stage "
    "summaries, ROCm manifest, and bundle validation. It does not launch docking, rerun benchmarks, train models, "
    "install packages, upload, submit, email, archive, externalize, or delete files. Throughput is scoped to the "
    "observed local GPCR run, not a broad multi-target production SLA."
)

REQUIRED_STAGE_IDS = (
    "stage0_leakage_audit",
    "stage1_ligand_mapping",
    "stage2_trajectory_generation",
    "stage3_backmapping_scoring",
    "stage45_eval_integrity",
    "stage5_ranking_eval",
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
    return summary if isinstance(summary, dict) else packet


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


def _status_row(component: str, status: str, observed: str, required: str, reason: str, source_artifact: str) -> dict[str, Any]:
    return {
        "component": component,
        "status": status,
        "observed": observed,
        "required": required,
        "reason": reason,
        "source_artifact": source_artifact,
        "release_blocker": status == "fail",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def _stage_duration_seconds(run_summary: dict[str, Any]) -> float:
    total = 0.0
    for stage in (run_summary.get("stages") or {}).values():
        if isinstance(stage, dict):
            total += _float(stage.get("duration_sec"))
    return total


def _stages_ok(run_summary: dict[str, Any]) -> tuple[bool, list[str]]:
    stages = run_summary.get("stages") if isinstance(run_summary.get("stages"), dict) else {}
    failed: list[str] = []
    for stage_id in REQUIRED_STAGE_IDS:
        stage = stages.get(stage_id)
        if not isinstance(stage, dict) or stage.get("ok") is not True:
            failed.append(stage_id)
    return not failed, failed


def build_product_end_to_end_rocm_benchmark(
    *,
    run_summary_packet: dict[str, Any],
    rocm_manifest_packet: dict[str, Any],
    bundle_manifest_packet: dict[str, Any],
    bundle_validation_packet: dict[str, Any],
    stage1_packet: dict[str, Any],
    stage2_packet: dict[str, Any],
    stage3_packet: dict[str, Any],
    stage5_packet: dict[str, Any],
    sla_packet: dict[str, Any] | None = None,
    backmapping_smoke_packet: dict[str, Any] | None = None,
    run_summary_path: str = DEFAULT_RUN_SUMMARY_JSON,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    bundle_manifest_path: str = DEFAULT_BUNDLE_MANIFEST_JSON,
    bundle_validation_path: str = DEFAULT_BUNDLE_VALIDATION_JSON,
    stage1_path: str = DEFAULT_STAGE1_SUMMARY_JSON,
    stage2_path: str = DEFAULT_STAGE2_SUMMARY_JSON,
    stage3_path: str = DEFAULT_STAGE3_SUMMARY_JSON,
    stage5_path: str = DEFAULT_STAGE5_SUMMARY_JSON,
    sla_path: str = DEFAULT_SLA_SUMMARY_JSON,
    backmapping_smoke_path: str = DEFAULT_BACKMAPPING_SMOKE_JSON,
) -> dict[str, Any]:
    run_summary = _summary(run_summary_packet)
    rocm = _summary(rocm_manifest_packet)
    bundle_manifest = bundle_manifest_packet if "bundle_dir" in bundle_manifest_packet else _summary(bundle_manifest_packet)
    bundle_validation = bundle_validation_packet if "overall_ok" in bundle_validation_packet else _summary(bundle_validation_packet)
    stage1 = stage1_packet if "queue_rows" in stage1_packet else _summary(stage1_packet)
    stage2 = stage2_packet if "processed_rows" in stage2_packet else _summary(stage2_packet)
    stage3 = stage3_packet if "processed_jobs" in stage3_packet else _summary(stage3_packet)
    stage5 = stage5_packet if "rows_scores" in stage5_packet else _summary(stage5_packet)
    sla_packet = sla_packet or {}
    sla = sla_packet if "total_latency_sec" in sla_packet else _summary(sla_packet)
    backmapping_smoke_packet = backmapping_smoke_packet or {}
    backmapping_smoke = _summary(backmapping_smoke_packet)
    backmapping_batch_frames_per_sec = _float(backmapping_smoke.get("batch_frames_per_sec"))
    backmapping_smoke_ready = _text(backmapping_smoke.get("status")) == "backmapping_scoring_batch_smoke_benchmark_ready"

    rocm_ready = _text(rocm.get("status")) == "rocm_environment_manifest_ready" and rocm.get("manifest_ready") is True
    full_run_pass = run_summary.get("pass") is True and _text(run_summary.get("run_scope")) == "full"
    stages_ok, failed_stages = _stages_ok(run_summary)
    artifacts = run_summary.get("artifacts") if isinstance(run_summary.get("artifacts"), dict) else {}
    trajectory_engine_mode = _text(artifacts.get("trajectory_engine_mode"))
    rust_hip_evidence = trajectory_engine_mode == "rust_hip" and stage2.get("require_rust_hip") is True
    processed_jobs = _int(stage2.get("processed_rows") or stage1.get("queue_rows"))
    failed_jobs = _int(stage2.get("failed_rows"))
    scored_rows = _int(stage3.get("processed_jobs") or stage5.get("rows_scores"))
    unique_ligands_scored = _int(stage5.get("rows_eval") or stage3.get("replicate_group_count") or stage1.get("ligands"))
    ranking_pass = stage5.get("pass") is True and _float(stage5.get("observed_expected_score_coverage_ratio")) >= 0.99
    bundle_dir = _text(bundle_manifest.get("bundle_dir"))
    bundle_zip_present = bool(bundle_dir and (_resolve(bundle_dir) / "bundle.zip").exists())
    bundle_validation_ok = bundle_validation.get("overall_ok") is True and _int(bundle_validation.get("blocker_count")) == 0
    total_stage_seconds = _stage_duration_seconds(run_summary)
    if total_stage_seconds <= 0:
        total_stage_seconds = _float(sla.get("total_latency_sec"))
    jobs_per_hour = float(processed_jobs / total_stage_seconds * 3600.0) if processed_jobs and total_stage_seconds > 0 else 0.0
    unique_ligands_per_hour = float(unique_ligands_scored / total_stage_seconds * 3600.0) if unique_ligands_scored and total_stage_seconds > 0 else 0.0
    score_rows_per_sec = float(scored_rows / _float((run_summary.get("stages") or {}).get("stage3_backmapping_scoring", {}).get("duration_sec"))) if scored_rows and _float((run_summary.get("stages") or {}).get("stage3_backmapping_scoring", {}).get("duration_sec")) > 0 else 0.0
    failure_rate = float(failed_jobs / processed_jobs) if processed_jobs else 1.0
    production_profile_enabled = bool(
        (run_summary.get("traj_prod") or {}).get("enabled") is True
        or stage2.get("prod_mode") is True
        or sla.get("traj_stage2_engine_prod_mode") is True
    )

    rows = [
        _status_row("rocm_environment", "pass" if rocm_ready else "fail", _text(rocm.get("status")) or "missing", "rocm_environment_manifest_ready", "ROCm/HIP runtime must be visible before AMD-native claims.", rocm_manifest_path),
        _status_row("full_run_summary", "pass" if full_run_pass else "fail", f"pass={run_summary.get('pass')}; run_scope={run_summary.get('run_scope')}", "pass=true and run_scope=full", "End-to-end evidence must come from a completed full local run.", run_summary_path),
        _status_row("required_stage_chain", "pass" if stages_ok else "fail", "failed=" + ",".join(failed_stages) if failed_stages else "all required stages ok", "stage0/stage1/stage2/stage3/stage45/stage5 ok=true", "The run must include leakage, preparation, trajectory, scoring, integrity, and ranking stages.", run_summary_path),
        _status_row("rust_hip_trajectory_evidence", "pass" if rust_hip_evidence else "fail", f"trajectory_engine_mode={trajectory_engine_mode}; require_rust_hip={stage2.get('require_rust_hip')}", "trajectory_engine_mode=rust_hip and require_rust_hip=true", "The local run must prove the AMD-native trajectory path was required.", f"{run_summary_path}; {stage2_path}"),
        _status_row("score_and_ranking_evidence", "pass" if ranking_pass and scored_rows > 0 else "fail", f"scored_rows={scored_rows}; unique_ligands={unique_ligands_scored}; ranking_pass={stage5.get('pass')}", "scored rows > 0 and ranking pass with >=0.99 expected score coverage", "The benchmark must emit scored/ranked local results, not only a request contract.", f"{stage3_path}; {stage5_path}"),
        _status_row("throughput_metrics", "pass" if jobs_per_hour > 0 and unique_ligands_per_hour > 0 and failure_rate <= 0.05 else "fail", f"jobs_per_hour={jobs_per_hour:.3f}; unique_ligands_per_hour={unique_ligands_per_hour:.3f}; failure_rate={failure_rate:.6f}", "positive throughput and failure_rate <= 0.05", "A real end-to-end run must expose measured product throughput.", run_summary_path),
        _status_row("bundle_validation", "pass" if bundle_validation_ok and bundle_zip_present else "fail", f"bundle_validation_ok={bundle_validation_ok}; bundle_zip_present={bundle_zip_present}", "validated bundle.zip present", "Customer-facing evidence needs a validated local bundle artifact.", f"{bundle_manifest_path}; {bundle_validation_path}"),
        _status_row("production_trajectory_profile", "warn" if not production_profile_enabled else "pass", f"production_profile_enabled={production_profile_enabled}; prod_mode={stage2.get('prod_mode')}", "preferred true for final customer SLA claim", "The current run proves rust_hip execution but not the stricter production trajectory profile.", f"{run_summary_path}; {stage2_path}; {sla_path}"),
        _status_row(
            "backmapping_batch_smoke_benchmark",
            "pass" if backmapping_smoke_ready and backmapping_batch_frames_per_sec > 0 else "warn",
            f"status={backmapping_smoke.get('status')}; batch_frames_per_sec={backmapping_batch_frames_per_sec:.3f}",
            "backmapping_scoring_batch_smoke_benchmark_ready with positive batch_frames_per_sec",
            "Vectorized backmapping scoring should expose a recent local smoke throughput guard.",
            backmapping_smoke_path,
        ),
    ]
    fail_rows = [row for row in rows if row["status"] == "fail"]
    warn_rows = [row for row in rows if row["status"] == "warn"]
    benchmark_ready = not fail_rows
    summary = {
        "packet_type": "product_end_to_end_rocm_benchmark",
        "status": "product_end_to_end_rocm_benchmark_ready" if benchmark_ready else "blocked_product_end_to_end_rocm_benchmark",
        "benchmark_ready": benchmark_ready,
        "actual_end_to_end_run_evidence_ready": benchmark_ready,
        "rocm_end_to_end_throughput_ready": benchmark_ready,
        "run_scope": _text(run_summary.get("run_scope")),
        "run_pass": run_summary.get("pass") is True,
        "target_id": "ADRB2_GPCR_BLIND",
        "family": "gpcr",
        "trajectory_engine_mode": trajectory_engine_mode,
        "rust_hip_evidence_ready": rust_hip_evidence,
        "production_trajectory_profile_enabled": production_profile_enabled,
        "processed_jobs": processed_jobs,
        "failed_jobs": failed_jobs,
        "scored_rows": scored_rows,
        "unique_ligands_scored": unique_ligands_scored,
        "total_stage_seconds": total_stage_seconds,
        "jobs_per_hour": jobs_per_hour,
        "unique_ligands_per_hour": unique_ligands_per_hour,
        "score_rows_per_sec": score_rows_per_sec,
        "failure_rate": failure_rate,
        "backmapping_batch_smoke_ready": backmapping_smoke_ready,
        "backmapping_batch_frames_per_sec": backmapping_batch_frames_per_sec,
        "backmapping_batch_smoke_json": backmapping_smoke_path,
        "bundle_zip_present": bundle_zip_present,
        "bundle_validation_ok": bundle_validation_ok,
        "component_count": len(rows),
        "pass_component_count": sum(1 for row in rows if row["status"] == "pass"),
        "warning_component_count": len(warn_rows),
        "fail_component_count": len(fail_rows),
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": benchmark_ready,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this as the current single-target GPCR ROCm end-to-end benchmark baseline; harden production trajectory profile next."
            if benchmark_ready
            else "Run or ingest a full local ROCm/HIP docking execution with stage and bundle evidence."
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
        "# Product End-to-End ROCm Benchmark",
        "",
        f"- status: `{s['status']}`",
        f"- benchmark_ready: `{s['benchmark_ready']}`",
        f"- target_id: `{s['target_id']}`",
        f"- trajectory_engine_mode: `{s['trajectory_engine_mode']}`",
        f"- production_trajectory_profile_enabled: `{s['production_trajectory_profile_enabled']}`",
        f"- processed_jobs: `{s['processed_jobs']}`",
        f"- unique_ligands_scored: `{s['unique_ligands_scored']}`",
        f"- jobs_per_hour: `{s['jobs_per_hour']}`",
        f"- unique_ligands_per_hour: `{s['unique_ligands_per_hour']}`",
        f"- failure_rate: `{s['failure_rate']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        "",
        "## Components",
        "",
        "| component | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['component']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product end-to-end ROCm benchmark evidence from local run artifacts.")
    parser.add_argument("--run-summary-json", default=DEFAULT_RUN_SUMMARY_JSON)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--bundle-manifest-json", default=DEFAULT_BUNDLE_MANIFEST_JSON)
    parser.add_argument("--bundle-validation-json", default=DEFAULT_BUNDLE_VALIDATION_JSON)
    parser.add_argument("--stage1-summary-json", default=DEFAULT_STAGE1_SUMMARY_JSON)
    parser.add_argument("--stage2-summary-json", default=DEFAULT_STAGE2_SUMMARY_JSON)
    parser.add_argument("--stage3-summary-json", default=DEFAULT_STAGE3_SUMMARY_JSON)
    parser.add_argument("--stage5-summary-json", default=DEFAULT_STAGE5_SUMMARY_JSON)
    parser.add_argument("--sla-summary-json", default=DEFAULT_SLA_SUMMARY_JSON)
    parser.add_argument("--backmapping-smoke-json", default=DEFAULT_BACKMAPPING_SMOKE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_end_to_end_rocm_benchmark(
        run_summary_packet=_read_json_if_present(args.run_summary_json),
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        bundle_manifest_packet=_read_json_if_present(args.bundle_manifest_json),
        bundle_validation_packet=_read_json_if_present(args.bundle_validation_json),
        stage1_packet=_read_json_if_present(args.stage1_summary_json),
        stage2_packet=_read_json_if_present(args.stage2_summary_json),
        stage3_packet=_read_json_if_present(args.stage3_summary_json),
        stage5_packet=_read_json_if_present(args.stage5_summary_json),
        sla_packet=_read_json_if_present(args.sla_summary_json),
        backmapping_smoke_packet=_read_json_if_present(args.backmapping_smoke_json),
        run_summary_path=args.run_summary_json,
        rocm_manifest_path=args.rocm_manifest_json,
        bundle_manifest_path=args.bundle_manifest_json,
        bundle_validation_path=args.bundle_validation_json,
        stage1_path=args.stage1_summary_json,
        stage2_path=args.stage2_summary_json,
        stage3_path=args.stage3_summary_json,
        stage5_path=args.stage5_summary_json,
        sla_path=args.sla_summary_json,
        backmapping_smoke_path=args.backmapping_smoke_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
