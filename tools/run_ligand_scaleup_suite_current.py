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


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Ligand Scale-up Suite",
        "",
        f"- `suite_id`: `{payload.get('suite_id', 'ligand_scaleup_suite_current')}`",
        f"- `generated_at_local`: `{payload.get('generated_at_local', '')}`",
        f"- `execution_requested`: `{bool(payload.get('execution_requested', False))}`",
        f"- `dry_run`: `{bool(payload.get('dry_run', False))}`",
        f"- `ok`: `{payload.get('ok', payload.get('launch_readiness', {}).get('ready', False))}`",
        "",
    ]
    readiness = payload.get("launch_readiness", {})
    if isinstance(readiness, dict):
        lines.extend(
            [
                "## Launch Readiness",
                "",
                f"- `status`: `{readiness.get('status', 'unknown')}`",
                f"- `ready`: `{bool(readiness.get('ready', False))}`",
                f"- `blocking_issue_count`: `{int(readiness.get('blocking_issue_count', 0))}`",
            ]
        )
        issues = readiness.get("blocking_issues", [])
        if isinstance(issues, list) and issues:
            lines.append("- `blocking_issues`:")
            for issue in issues:
                lines.append(f"  - `{issue}`")
        lines.append("")

    lines.extend(
        [
            "## Stages",
            "",
            "| Stage | Enabled | Result | Note |",
            "| --- | --- | --- | --- |",
        ]
    )
    stage_results = {
        str(row.get("stage_id")): row
        for row in payload.get("stage_results", [])
        if isinstance(row, dict)
    }
    for stage in payload.get("stages", []):
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("stage_id", "unknown"))
        result = stage_results.get(stage_id)
        if result is None:
            result_label = "planned" if bool(stage.get("enabled", False)) else "disabled"
        elif bool(result.get("skipped", False)):
            result_label = "skipped"
        elif bool(result.get("ok", False)):
            result_label = "ok"
        else:
            result_label = f"failed({result.get('returncode', '?')})"
        lines.append(
            f"| `{stage_id}` | `{bool(stage.get('enabled', False))}` | `{result_label}` | {stage.get('note', '')} |"
        )
    lines.append("")

    if stage_results:
        lines.extend(
            [
                "## Execution Summary",
                "",
            ]
        )
        summary = payload.get("final_execution_summary", {})
        if isinstance(summary, dict):
            for key in (
                "stage_success_count",
                "stage_failure_count",
                "stage_skipped_count",
                "suite_status_refresh_count",
                "suite_status_refresh_ok_count",
                "current_suite_status_json",
                "current_suite_status_csv",
                "current_suite_status_md",
            ):
                if key in summary:
                    lines.append(f"- `{key}`: `{summary[key]}`")
        failed_stage_id = payload.get("failed_stage_id")
        if failed_stage_id:
            lines.append(f"- `failed_stage_id`: `{failed_stage_id}`")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stage_row(
    *,
    stage_id: str,
    stage_order: int,
    enabled: bool,
    cmd: list[str],
    expected_outputs: list[str],
    note: str,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_order": int(stage_order),
        "enabled": bool(enabled),
        "cmd": cmd,
        "expected_outputs": expected_outputs,
        "note": note,
    }


def _build_stage_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    tag_prefix = str(args.tag_prefix).strip()
    baseline_args: list[str] = []
    if str(args.baseline_run_root).strip():
        baseline_args.extend(["--baseline-run-root", str(args.baseline_run_root).strip()])
    else:
        baseline_args.extend(["--current-package-meta-json", str(args.current_package_meta_json).strip()])
    comparison_args = ["--comparison-out-root", str(args.comparison_out_root).strip()]

    speedpack_cmd = [
        sys.executable,
        str(ROOT / "tools/run_ligand_speedpack_ab_current.py"),
        "--tag",
        f"{tag_prefix}_speedpack_ab",
        "--source-spec-json",
        str(args.speedpack_source_spec_json).strip(),
        "--task-bundle",
        str(args.speedpack_task_bundle).strip(),
        "--generated-root",
        str(args.speedpack_generated_root).strip(),
        "--out-root",
        str(args.out_root).strip(),
        *comparison_args,
        *baseline_args,
    ]
    if str(args.speedpack_task_ids).strip():
        speedpack_cmd.extend(["--task-ids", str(args.speedpack_task_ids).strip()])
    if bool(args.speedpack_include_smoke):
        speedpack_cmd.append("--include-smoke")
    else:
        speedpack_cmd.append("--no-include-smoke")
    if str(args.speedpack_ligand_size_override).strip():
        speedpack_cmd.extend(["--ligand-size-override", str(args.speedpack_ligand_size_override).strip()])
    speedpack_cmd.append("--strict-auto" if bool(args.speedpack_strict_auto) else "--no-strict-auto")
    speedpack_cmd.append("--refresh-current-artifacts" if bool(args.refresh_current_artifacts) else "--no-refresh-current-artifacts")

    pilot_100k_cmd = [
        sys.executable,
        str(ROOT / "tools/run_ligand_scaleup_100k_pilot_current.py"),
        "--tag",
        f"{tag_prefix}_100k",
        "--sets",
        str(args.sets).strip(),
        "--set-spec-json",
        str(args.pilot_100k_set_spec_json).strip(),
        "--out-root",
        str(args.out_root).strip(),
        *comparison_args,
        *baseline_args,
        "--refresh-current-summaries" if bool(args.refresh_current_summaries) else "--no-refresh-current-summaries",
    ]

    pilot_1m_cmd = [
        sys.executable,
        str(ROOT / "tools/run_ligand_scaleup_1m_pilot_current.py"),
        "--tag",
        f"{tag_prefix}_1m",
        "--sets",
        str(args.sets).strip(),
        "--set-spec-json",
        str(args.pilot_1m_set_spec_json).strip(),
        "--out-root",
        str(args.out_root).strip(),
        *comparison_args,
        *baseline_args,
        "--refresh-current-summaries" if bool(args.refresh_current_summaries) else "--no-refresh-current-summaries",
    ]

    return [
        _stage_row(
            stage_id="speedpack_ab",
            stage_order=1,
            enabled=bool(args.enable_speedpack_ab),
            cmd=speedpack_cmd,
            expected_outputs=[
                "runs/ligand_speedpack_ab_current.json",
                "runs/ligand_speedpack_ab_summary_current.md",
            ],
            note="Equal-size speedpack A/B slice over selected slow ligand tasks.",
        ),
        _stage_row(
            stage_id="pilot_100k",
            stage_order=2,
            enabled=bool(args.enable_100k),
            cmd=pilot_100k_cmd,
            expected_outputs=[
                "runs/ligand_scaleup_100k_pilot_current.json",
                "runs/ligand_scaleup_benchmark_summary_current.md",
            ],
            note="Production-only 100k throughput pilot on the accepted cross-domain task surface.",
        ),
        _stage_row(
            stage_id="pilot_1m",
            stage_order=3,
            enabled=bool(args.enable_1m),
            cmd=pilot_1m_cmd,
            expected_outputs=[
                "runs/ligand_scaleup_1m_pilot_current.json",
                "runs/ligand_scaleup_benchmark_summary_current.md",
            ],
            note="Production-only 1M throughput pilot on the accepted cross-domain task surface.",
        ),
    ]


def _build_plan_payload(args: argparse.Namespace) -> dict[str, Any]:
    stages = _build_stage_plan(args)
    enabled_rows = [row for row in stages if bool(row["enabled"])]
    blocked_reason = ""
    if not enabled_rows:
        blocked_reason = "no stages enabled"
    return {
        "ok": True,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execution_requested": bool(args.execute),
        "dry_run": not bool(args.execute),
        "stop_on_failure": not bool(args.continue_on_error),
        "suite_id": "ligand_scaleup_suite_current",
        "tag_prefix": str(args.tag_prefix).strip(),
        "selected_sets": [tok.strip() for tok in str(args.sets).split(",") if tok.strip()],
        "refresh_current_artifacts": bool(args.refresh_current_artifacts),
        "refresh_current_summaries": bool(args.refresh_current_summaries),
        "enabled_stage_count": int(len(enabled_rows)),
        "disabled_stage_count": int(len(stages) - len(enabled_rows)),
        "launch_readiness": {
            "ready": bool(enabled_rows),
            "status": "ready" if enabled_rows else "blocked",
            "blocking_issue_count": 0 if enabled_rows else 1,
            "blocking_issues": [] if enabled_rows else [blocked_reason],
        },
        "stages": stages,
    }


def _suite_status_refresh_cmd() -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tools/build_ligand_scaleup_suite_status.py"),
    ]


def _refresh_suite_status() -> dict[str, Any]:
    cmd = _suite_status_refresh_cmd()
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    return {
        "ok": bool(rc == 0),
        "returncode": int(rc),
        "cmd": cmd,
    }


def _write_suite_artifacts(
    *,
    payload: dict[str, Any],
    json_path_str: str,
    md_path_str: str,
) -> None:
    _write_json(_resolve_repo_path(json_path_str), payload)
    _write_md(_resolve_repo_path(md_path_str), payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Dry-run-first orchestration layer for commercialization scale-up: speedpack A/B -> 100k -> 1M."
    )
    ap.add_argument("--tag-prefix", default=f"{dt.date.today().isoformat()}_ligand_scaleup_suite_v1")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--baseline-run-root", default="")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--comparison-out-root", default="runs")

    ap.add_argument("--enable-speedpack-ab", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--enable-100k", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--enable-1m", action=argparse.BooleanOptionalAction, default=True)

    ap.add_argument("--speedpack-source-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    ap.add_argument("--speedpack-task-bundle", default="trpv1_full")
    ap.add_argument("--speedpack-task-ids", default="")
    ap.add_argument("--speedpack-include-smoke", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--speedpack-ligand-size-override", default="")
    ap.add_argument("--speedpack-generated-root", default="runs/ligand_speedpack_ab_current")
    ap.add_argument("--speedpack-strict-auto", action=argparse.BooleanOptionalAction, default=True)

    ap.add_argument("--pilot-100k-set-spec-json", default="config/external_validation_biorxiv_scaleup_100k_pilot_v1.json")
    ap.add_argument("--pilot-1m-set-spec-json", default="config/external_validation_biorxiv_scaleup_1m_pilot_v1.json")

    ap.add_argument("--refresh-current-artifacts", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--refresh-current-summaries", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--refresh-suite-status", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--continue-on-error", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--suite-dryrun-json", default="runs/ligand_scaleup_suite_dryrun_current.json")
    ap.add_argument("--suite-dryrun-md", default="runs/ligand_scaleup_suite_dryrun_current.md")
    ap.add_argument("--suite-execution-json", default="runs/ligand_scaleup_suite_execution_current.json")
    ap.add_argument("--suite-execution-md", default="runs/ligand_scaleup_suite_execution_current.md")
    ap.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    payload = _build_plan_payload(args)
    if bool(args.dry_run) and (not bool(args.execute)):
        _write_suite_artifacts(
            payload=payload,
            json_path_str=str(args.suite_dryrun_json).strip(),
            md_path_str=str(args.suite_dryrun_md).strip(),
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if not bool(args.execute):
        _write_suite_artifacts(
            payload=payload,
            json_path_str=str(args.suite_dryrun_json).strip(),
            md_path_str=str(args.suite_dryrun_md).strip(),
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    readiness = payload.get("launch_readiness", {})
    if not bool(readiness.get("ready", False)):
        _write_suite_artifacts(
            payload=payload,
            json_path_str=str(args.suite_execution_json).strip(),
            md_path_str=str(args.suite_execution_md).strip(),
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    stage_results: list[dict[str, Any]] = []
    suite_status_refreshes: list[dict[str, Any]] = []
    for stage in payload["stages"]:
        if not bool(stage["enabled"]):
            stage_results.append(
                {
                    "stage_id": stage["stage_id"],
                    "enabled": False,
                    "skipped": True,
                    "reason": "disabled",
                    "returncode": 0,
                }
            )
            continue
        rc = subprocess.run(list(stage["cmd"]), cwd=str(ROOT)).returncode
        row = {
            "stage_id": stage["stage_id"],
            "enabled": True,
            "skipped": False,
            "returncode": int(rc),
            "ok": bool(rc == 0),
            "cmd": list(stage["cmd"]),
        }
        if rc == 0 and bool(args.refresh_suite_status):
            refresh_result = _refresh_suite_status()
            refresh_row = {
                "stage_id": stage["stage_id"],
                **refresh_result,
            }
            suite_status_refreshes.append(refresh_row)
            row["suite_status_refresh"] = refresh_result
        stage_results.append(row)
        if rc != 0 and not bool(args.continue_on_error):
            failure_payload = {
                **payload,
                "execution_requested": True,
                "dry_run": False,
                "stage_results": stage_results,
                "suite_status_refreshes": suite_status_refreshes,
                "completed_stage_count": int(sum(1 for item in stage_results if not bool(item.get("skipped", False)))),
                "failed_stage_id": row["stage_id"],
                "final_execution_summary": {
                    "stage_success_count": int(sum(1 for item in stage_results if bool(item.get("ok", False)))),
                    "stage_failure_count": int(sum(1 for item in stage_results if (not bool(item.get("skipped", False))) and (not bool(item.get("ok", False))))),
                    "suite_status_refresh_count": int(len(suite_status_refreshes)),
                    "suite_status_refresh_ok_count": int(sum(1 for item in suite_status_refreshes if bool(item.get("ok", False)))),
                    "current_suite_status_json": "runs/ligand_scaleup_suite_status_current.json",
                },
                "ok": False,
            }
            _write_suite_artifacts(
                payload=failure_payload,
                json_path_str=str(args.suite_execution_json).strip(),
                md_path_str=str(args.suite_execution_md).strip(),
            )
            print(
                json.dumps(
                    failure_payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return int(rc)

    all_ok = all(bool(row.get("ok", True)) for row in stage_results if not bool(row.get("skipped", False)))
    final_execution_summary = {
        "stage_success_count": int(sum(1 for item in stage_results if bool(item.get("ok", False)))),
        "stage_failure_count": int(sum(1 for item in stage_results if (not bool(item.get("skipped", False))) and (not bool(item.get("ok", False))))),
        "stage_skipped_count": int(sum(1 for item in stage_results if bool(item.get("skipped", False)))),
        "suite_status_refresh_count": int(len(suite_status_refreshes)),
        "suite_status_refresh_ok_count": int(sum(1 for item in suite_status_refreshes if bool(item.get("ok", False)))),
        "current_suite_status_json": "runs/ligand_scaleup_suite_status_current.json",
        "current_suite_status_csv": "runs/ligand_scaleup_suite_status_current.csv",
        "current_suite_status_md": "runs/ligand_scaleup_suite_status_current.md",
    }
    execution_payload = {
        **payload,
        "execution_requested": True,
        "dry_run": False,
        "stage_results": stage_results,
        "suite_status_refreshes": suite_status_refreshes,
        "completed_stage_count": int(sum(1 for item in stage_results if not bool(item.get("skipped", False)))),
        "final_execution_summary": final_execution_summary,
        "ok": bool(all_ok),
    }
    _write_suite_artifacts(
        payload=execution_payload,
        json_path_str=str(args.suite_execution_json).strip(),
        md_path_str=str(args.suite_execution_md).strip(),
    )
    print(
        json.dumps(
            execution_payload,
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
