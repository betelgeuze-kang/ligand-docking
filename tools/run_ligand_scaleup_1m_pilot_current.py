#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from tools.product.ligand_scaleup_pilot_helper import (
    ScaleupPilotPreset,
    build_guardrail_rows,
    build_run_current_payload,
    parse_csv_list,
    resolve_baseline_run_root,
)


ROOT = Path(__file__).resolve().parents[1]
PRESET = ScaleupPilotPreset.from_target_ligand_size(1_000_000)


def _build_launch_readiness(
    drift_audit: dict[str, Any],
    *,
    comparison_enabled: bool,
    comparison_skip_reason: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if int(drift_audit.get("nonstandard_ligand_size_count", 0)) > 0:
        blockers.append("pilot spec contains ligand_stress tasks outside the allowed 1000000/64 shape")
    if int(drift_audit.get("full_task_non_target_count", 0)) > 0:
        blockers.append("one or more full ligand_stress tasks are not set to 1000000 ligands")
    if int(drift_audit.get("smoke_task_non_64_count", 0)) > 0:
        blockers.append("one or more smoke ligand_stress tasks are not preserved at 64 ligands")
    if not comparison_enabled:
        if comparison_skip_reason == "skip_compare":
            blockers.append("comparison is explicitly disabled via --skip-compare")
        elif comparison_skip_reason == "baseline_run_root_not_found":
            blockers.append("baseline run root could not be resolved from the current package metadata")
        else:
            blockers.append("comparison against the accepted current run is not enabled")
    return {
        "ready": len(blockers) == 0,
        "status": "ready" if len(blockers) == 0 else "blocked",
        "blocking_issue_count": len(blockers),
        "blocking_issues": blockers,
        "comparison_required": True,
        "comparison_enabled": comparison_enabled,
    }


def _build_post_run_refresh_plan(
    *,
    tag: str,
    baseline_run_root: str,
    candidate_run_root: str,
    comparison_root: str,
) -> dict[str, Any]:
    steps = [
        {
            "step_id": "refresh_scaleup_kpi_table",
            "cmd": [sys.executable, str(ROOT / "tools/build_ligand_scaleup_kpi_table.py")],
        },
        {
            "step_id": "refresh_scaleup_1m_pilot_artifacts",
            "cmd": [sys.executable, str(ROOT / "tools/build_ligand_scaleup_1m_pilot.py")],
        },
        {
            "step_id": "refresh_scaleup_benchmark_summary",
            "cmd": [
                sys.executable,
                str(ROOT / "tools/product/build_ligand_scaleup_benchmark_summary.py"),
                "--pilot-json",
                "runs/ligand_scaleup_1m_pilot_current.json",
                "--comparison-json",
                str((Path(comparison_root) / "summary.json").resolve()),
                "--baseline-summary-json",
                str((Path(baseline_run_root) / "summary.json").resolve()) if baseline_run_root else "",
                "--candidate-summary-json",
                str((Path(candidate_run_root) / "summary.json").resolve()),
            ],
        },
    ]
    return {
        "enabled_by_default": True,
        "tag": tag,
        "candidate_run_root": str(Path(candidate_run_root).resolve()),
        "comparison_root": str(Path(comparison_root).resolve()),
        "steps": steps,
    }


def _execute_post_run_refresh(
    *,
    plan: dict[str, Any],
    enabled: bool,
    fail_on_error: bool,
) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "attempted": False,
            "ok": True,
            "step_count": int(len(plan.get("steps", []))),
            "steps": [],
            "skipped_reason": "disabled_by_flag",
        }
    step_results: list[dict[str, Any]] = []
    for step in plan.get("steps", []):
        cmd = list(step.get("cmd", []))
        rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
        row = {
            "step_id": str(step.get("step_id", "")),
            "returncode": int(rc),
            "ok": bool(rc == 0),
            "cmd": cmd,
        }
        step_results.append(row)
        if rc != 0 and fail_on_error:
            return {
                "enabled": True,
                "attempted": True,
                "ok": False,
                "step_count": int(len(step_results)),
                "steps": step_results,
                "failed_step_id": row["step_id"],
                "failed_returncode": int(rc),
            }
    return {
        "enabled": True,
        "attempted": True,
        "ok": all(bool(row.get("ok", False)) for row in step_results),
        "step_count": int(len(step_results)),
        "steps": step_results,
        "failed_step_id": next((row["step_id"] for row in step_results if not bool(row.get("ok", False))), ""),
        "failed_returncode": next((int(row["returncode"]) for row in step_results if not bool(row.get("ok", False))), 0),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Run the production-only {PRESET.target_scale_label} ligand scale-up pilot and compare it with the current accepted run."
    )
    parser.add_argument("--tag", default=f"{dt.date.today().isoformat()}_{PRESET.pilot_version_slug}")
    parser.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    parser.add_argument("--set-spec-json", default="config/external_validation_biorxiv_scaleup_1m_pilot_v1.json")
    parser.add_argument("--baseline-run-root", default="")
    parser.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    parser.add_argument("--out-root", default="runs/external_validation_blind_runs")
    parser.add_argument("--comparison-out-root", default="runs")
    parser.add_argument("--compare-label", default="")
    parser.add_argument("--skip-compare", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--refresh-current-summaries", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-fail-on-error", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(list(argv) if argv is not None else None)

    selected_sets = parse_csv_list(args.sets)
    baseline_run_root = resolve_baseline_run_root(
        args.baseline_run_root,
        args.current_package_meta_json,
        root=ROOT,
    )
    compare_label = str(args.compare_label).strip() or f"{args.tag}_vs_current"
    payload = build_run_current_payload(
        tag=str(args.tag),
        selected_sets=selected_sets,
        set_spec_json=str(args.set_spec_json),
        baseline_run_root=baseline_run_root,
        out_root=str(args.out_root),
        comparison_out_root=str(args.comparison_out_root),
        compare_label=compare_label,
        skip_compare=bool(args.skip_compare),
        preset=PRESET,
        root=ROOT,
    )
    payload["guardrail_summary"] = build_guardrail_rows(preset=PRESET)
    payload["launch_readiness"] = _build_launch_readiness(
        dict(payload.get("selected_drift_audit", {})),
        comparison_enabled=bool(payload.get("comparison_enabled", False)),
        comparison_skip_reason=str(payload.get("comparison_skip_reason", "")),
    )
    refresh_plan = _build_post_run_refresh_plan(
        tag=str(args.tag),
        baseline_run_root=str(baseline_run_root),
        candidate_run_root=str(payload.get("candidate_run_root", "")),
        comparison_root=str(payload.get("comparison_root", "")),
    )

    if args.dry_run:
        payload["dry_run"] = True
        payload["post_run_refresh"] = {
            "enabled": bool(args.refresh_current_summaries),
            "fail_on_error": bool(args.refresh_fail_on_error),
            "attempted": False,
            "plan": refresh_plan,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    run_rc = subprocess.run(payload["run_cmd"], cwd=str(ROOT)).returncode
    if run_rc != 0:
        return int(run_rc)

    if bool(payload.get("comparison_enabled", False)):
        compare_rc = subprocess.run(payload["compare_cmd"], cwd=str(ROOT)).returncode
        if compare_rc != 0:
            return int(compare_rc)

    refresh_result = _execute_post_run_refresh(
        plan=refresh_plan,
        enabled=bool(args.refresh_current_summaries),
        fail_on_error=bool(args.refresh_fail_on_error),
    )
    if bool(args.refresh_current_summaries) and bool(args.refresh_fail_on_error) and not bool(refresh_result.get("ok", False)):
        return int(refresh_result.get("failed_returncode", 1) or 1)

    print(
        json.dumps(
            {
                "ok": True,
                "tag": args.tag,
                "target_ligand_size": PRESET.target_ligand_size,
                "target_scale_label": PRESET.target_scale_label,
                "baseline_run_root": baseline_run_root,
                "candidate_run_root": payload["candidate_run_root"],
                "comparison_root": payload["comparison_root"] if bool(payload.get("comparison_enabled", False)) else "",
                "set_spec_json": payload["set_spec_json"],
                "comparison_kind": payload["comparison_kind"],
                "comparison_skipped": not bool(payload.get("comparison_enabled", False)),
                "reason": str(payload.get("comparison_skip_reason", "")) if not bool(payload.get("comparison_enabled", False)) else "",
                "selected_scope_summary": payload["selected_scope_summary"],
                "selected_drift_audit": payload["selected_drift_audit"],
                "launch_readiness": payload["launch_readiness"],
                "post_run_refresh": refresh_result,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
