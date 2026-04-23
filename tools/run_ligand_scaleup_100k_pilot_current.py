#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_baseline_run_root(explicit: str, package_meta_json: str) -> str:
    if str(explicit).strip():
        return str((ROOT / explicit).resolve()) if not Path(explicit).is_absolute() else str(Path(explicit).resolve())
    meta_path = (ROOT / package_meta_json).resolve() if not Path(package_meta_json).is_absolute() else Path(package_meta_json).resolve()
    if not meta_path.exists():
        return ""
    meta = _read_json(meta_path)
    run_root = str(meta.get("run_root") or "").strip()
    return str(Path(run_root).resolve()) if run_root else ""


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _parse_csv_list(spec: str) -> list[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _selected_task_rows(set_spec_json: str, selected_sets: list[str]) -> list[dict[str, Any]]:
    spec = _read_json(_resolve_repo_path(set_spec_json))
    selected = set(selected_sets)
    rows: list[dict[str, Any]] = []
    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        if selected and set_id not in selected:
            continue
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            rows.append(
                {
                    "set_id": set_id,
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                    "profile_json": str(task.get("profile_json", "")).strip(),
                    "date_tag_suffix": str(task.get("date_tag_suffix", "")).strip(),
                }
            )
    return rows


def _profile_guardrail_audit(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    full_profile_paths: dict[str, Path] = {}
    for row in task_rows:
        if row.get("ligand_sizes") != "100000":
            continue
        profile_json = str(row.get("profile_json", "")).strip()
        if not profile_json:
            continue
        full_profile_paths[profile_json] = _resolve_repo_path(profile_json)

    profile_payloads: list[dict[str, Any]] = []
    missing_profile_count = 0
    for profile_json, path in sorted(full_profile_paths.items()):
        if not path.exists():
            missing_profile_count += 1
            continue
        payload = _read_json(path)
        payload["_profile_json"] = profile_json
        profile_payloads.append(payload)

    return {
        "profile_missing_json_count": missing_profile_count,
        "profile_missing_strict_preset_count": sum(
            1 for payload in profile_payloads if not bool(payload.get("traj_prod_stage2_preset_strict", False))
        ),
        "profile_missing_speedpack_count": sum(
            1 for payload in profile_payloads if not bool(payload.get("traj_prod_speedpack", False))
        ),
        "profile_missing_light_artifacts_count": sum(
            1 for payload in profile_payloads if not bool(payload.get("traj_prod_light_artifacts", False))
        ),
        "profile_missing_intent_count": sum(
            1 for payload in profile_payloads if not str(payload.get("traj_prod_profile_intent", "")).strip()
        ),
    }


def _selected_scope_summary(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    full_rows = [row for row in task_rows if row["ligand_sizes"] == "100000"]
    smoke_rows = [row for row in task_rows if row["ligand_sizes"] == "64"]
    return {
        "ligand_stress_task_count": len(task_rows),
        "full_task_count_100k": len(full_rows),
        "smoke_task_count_unchanged": len(smoke_rows),
        "full_set_ids": sorted({row["set_id"] for row in full_rows}),
        "smoke_set_ids": sorted({row["set_id"] for row in smoke_rows}),
        "domains_touched": sorted({row["domain"] for row in task_rows if str(row["domain"]).strip()}),
    }


def _guardrail_summary() -> list[dict[str, str]]:
    return [
        {"guardrail_id": "no_pass_to_fail", "threshold": "0 pass->fail transitions", "scope": "regression slice"},
        {"guardrail_id": "pr_auc_drop_max_0p02", "threshold": ">= -0.02 absolute", "scope": "regression slice"},
        {"guardrail_id": "top20_hit_drop_max_1", "threshold": ">= -1 hit", "scope": "regression slice"},
        {"guardrail_id": "slowest_domain_speedup_min_1p8x", "threshold": ">= 1.8x on slowest domain", "scope": "throughput benchmark"},
    ]


def _selected_drift_audit(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    nonstandard_rows = [row for row in task_rows if row["ligand_sizes"] not in {"100000", "64"}]
    full_rows = [row for row in task_rows if row["set_id"] in {"set1_core_blind", "set2_expanded_ood"}]
    smoke_rows = [row for row in task_rows if row["set_id"] == "set3_operational_smoke"]
    profile_audit = _profile_guardrail_audit(task_rows)
    return {
        "ok": bool(
            len(nonstandard_rows) == 0
            and all(row["ligand_sizes"] == "100000" for row in full_rows)
            and all(row["ligand_sizes"] == "64" for row in smoke_rows)
            and int(profile_audit["profile_missing_json_count"]) == 0
            and int(profile_audit["profile_missing_strict_preset_count"]) == 0
            and int(profile_audit["profile_missing_speedpack_count"]) == 0
            and int(profile_audit["profile_missing_light_artifacts_count"]) == 0
            and int(profile_audit["profile_missing_intent_count"]) == 0
        ),
        "nonstandard_ligand_size_count": len(nonstandard_rows),
        "full_task_non_100k_count": sum(1 for row in full_rows if row["ligand_sizes"] != "100000"),
        "smoke_task_non_64_count": sum(1 for row in smoke_rows if row["ligand_sizes"] != "64"),
        **profile_audit,
    }


def _build_launch_readiness(
    drift_audit: dict[str, Any],
    *,
    comparison_enabled: bool,
    comparison_skip_reason: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if int(drift_audit.get("nonstandard_ligand_size_count", 0)) > 0:
        blockers.append("pilot spec contains ligand_stress tasks outside the allowed 100000/64 shape")
    if int(drift_audit.get("full_task_non_100k_count", 0)) > 0:
        blockers.append("one or more full ligand_stress tasks are not set to 100000 ligands")
    if int(drift_audit.get("smoke_task_non_64_count", 0)) > 0:
        blockers.append("one or more smoke ligand_stress tasks are not preserved at 64 ligands")
    if int(drift_audit.get("profile_missing_json_count", 0)) > 0:
        blockers.append("one or more selected full-task profiles could not be read")
    if int(drift_audit.get("profile_missing_strict_preset_count", 0)) > 0:
        blockers.append("one or more selected full-task profiles are missing strict auto-preset governance")
    if int(drift_audit.get("profile_missing_speedpack_count", 0)) > 0:
        blockers.append("one or more selected full-task profiles are missing speedpack")
    if int(drift_audit.get("profile_missing_light_artifacts_count", 0)) > 0:
        blockers.append("one or more selected full-task profiles are missing light-artifact mode")
    if int(drift_audit.get("profile_missing_intent_count", 0)) > 0:
        blockers.append("one or more selected full-task profiles are missing traj_prod_profile_intent")
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
    candidate_run_root: Path,
    comparison_out_root: str,
    compare_label: str,
) -> dict[str, Any]:
    comparison_root = (ROOT / comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()
    steps = [
        {
            "step_id": "refresh_scaleup_kpi_table",
            "cmd": [sys.executable, str(ROOT / "tools/build_ligand_scaleup_kpi_table.py")],
        },
        {
            "step_id": "refresh_scaleup_100k_pilot_artifacts",
            "cmd": [sys.executable, str(ROOT / "tools/build_ligand_scaleup_100k_pilot.py")],
        },
        {
            "step_id": "refresh_scaleup_benchmark_summary",
            "cmd": [
                sys.executable,
                str(ROOT / "tools/build_ligand_scaleup_benchmark_summary.py"),
                "--pilot-json",
                "runs/ligand_scaleup_100k_pilot_current.json",
                "--comparison-json",
                str((comparison_root / "summary.json").resolve()),
                "--baseline-summary-json",
                str((Path(baseline_run_root) / "summary.json").resolve()) if baseline_run_root else "",
                "--candidate-summary-json",
                str((candidate_run_root / "summary.json").resolve()),
            ],
        },
    ]
    return {
        "enabled_by_default": True,
        "tag": tag,
        "candidate_run_root": str(candidate_run_root.resolve()),
        "comparison_root": str(comparison_root),
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the production-only 100k ligand scale-up pilot and compare it with the current accepted run.")
    ap.add_argument("--tag", default=f"{dt.date.today().isoformat()}_scaleup_100k_pilot_v1")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_scaleup_100k_pilot_v1.json")
    ap.add_argument("--baseline-run-root", default="")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--comparison-out-root", default="runs")
    ap.add_argument("--compare-label", default="")
    ap.add_argument("--skip-compare", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--refresh-current-summaries", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--refresh-fail-on-error", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)
    selected_sets = _parse_csv_list(args.sets)
    task_rows = _selected_task_rows(args.set_spec_json, selected_sets)
    scope_summary = _selected_scope_summary(task_rows)
    drift_audit = _selected_drift_audit(task_rows)
    candidate_run_root = ROOT / args.out_root / f"external_validation_blind_runs_{args.tag}"
    baseline_run_root = _resolve_baseline_run_root(args.baseline_run_root, args.current_package_meta_json)
    compare_label = str(args.compare_label).strip() or f"{args.tag}_vs_current"
    comparison_enabled = bool(baseline_run_root) and (not bool(args.skip_compare))
    comparison_skip_reason = "skip_compare" if bool(args.skip_compare) else ("baseline_run_root_not_found" if not baseline_run_root else "")
    launch_readiness = _build_launch_readiness(
        drift_audit,
        comparison_enabled=comparison_enabled,
        comparison_skip_reason=comparison_skip_reason,
    )

    run_cmd = [
        sys.executable,
        str(ROOT / "tools/run_external_validation_blind_sets.py"),
        "--tag",
        str(args.tag),
        "--sets",
        str(args.sets),
        "--set-spec-json",
        str(args.set_spec_json),
        "--out-root",
        str(args.out_root),
    ]
    compare_cmd = [
        sys.executable,
        str(ROOT / "tools/compare_biorxiv_external_validation_runs.py"),
        "--baseline-run-root",
        str(baseline_run_root),
        "--candidate-run-root",
        str(candidate_run_root.resolve()),
        "--out-root",
        str(args.comparison_out_root),
        "--label",
        compare_label,
    ]
    refresh_plan = _build_post_run_refresh_plan(
        tag=str(args.tag),
        baseline_run_root=str(baseline_run_root),
        candidate_run_root=candidate_run_root,
        comparison_out_root=str(args.comparison_out_root),
        compare_label=compare_label,
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "tag": args.tag,
                    "set_spec_json": str(_resolve_repo_path(args.set_spec_json)),
                    "selected_sets": selected_sets,
                    "selected_ligand_stress_task_count": len(task_rows),
                    "selected_full_task_count_100k": scope_summary["full_task_count_100k"],
                    "selected_smoke_task_count": scope_summary["smoke_task_count_unchanged"],
                    "selected_scope_summary": scope_summary,
                    "selected_drift_audit": drift_audit,
                    "task_rows": task_rows,
                    "guardrail_summary": _guardrail_summary(),
                    "launch_readiness": launch_readiness,
                    "baseline_run_root": str(baseline_run_root),
                    "baseline_run_root_found": bool(baseline_run_root),
                    "candidate_run_root": str(candidate_run_root.resolve()),
                    "compare_label": compare_label,
                    "comparison_root": str((ROOT / args.comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()),
                    "comparison_kind": "size_shift_operational_regression",
                    "selected_drift_audit": drift_audit,
                    "run_cmd": run_cmd,
                    "compare_cmd": compare_cmd if comparison_enabled else [],
                    "comparison_enabled": comparison_enabled,
                    "comparison_skipped": not comparison_enabled,
                    "comparison_skip_reason": comparison_skip_reason,
                    "post_run_refresh": {
                        "enabled": bool(args.refresh_current_summaries),
                        "fail_on_error": bool(args.refresh_fail_on_error),
                        "attempted": False,
                        "plan": refresh_plan,
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    run_rc = subprocess.run(run_cmd, cwd=str(ROOT)).returncode
    if run_rc != 0:
        return int(run_rc)

    if comparison_enabled:
        compare_rc = subprocess.run(compare_cmd, cwd=str(ROOT)).returncode
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
                "candidate_run_root": str(candidate_run_root.resolve()),
                "baseline_run_root": str(baseline_run_root),
                "comparison_root": str((ROOT / args.comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()) if comparison_enabled else "",
                "set_spec_json": str((ROOT / args.set_spec_json).resolve()),
                "comparison_kind": "size_shift_operational_regression",
                "comparison_skipped": not comparison_enabled,
                "reason": comparison_skip_reason if not comparison_enabled else "",
                "selected_scope_summary": scope_summary,
                "selected_drift_audit": drift_audit,
                "launch_readiness": launch_readiness,
                "post_run_refresh": refresh_result,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
