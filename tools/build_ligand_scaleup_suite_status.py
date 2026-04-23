#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json_if_exists(path_str: str) -> Dict[str, Any]:
    path = _resolve_repo_path(path_str)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _join_list(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return ", ".join(str(v).strip() for v in values if str(v).strip())


def _artifact_state(*payloads: Dict[str, Any]) -> str:
    present = sum(1 for payload in payloads if isinstance(payload, dict) and payload)
    if present == 0:
        return "missing"
    if present == len(payloads):
        return "present"
    return "partial"


def _claim_safe_status(summary: Dict[str, Any]) -> str:
    if not summary:
        return "pending"
    explicit = str(summary.get("claim_safe_status", "") or "").strip()
    if explicit:
        return explicit
    flag = _safe_bool(summary.get("claim_safe"))
    if flag is True:
        return "claim_safe"
    if flag is False:
        return "not_claim_safe"
    return "pending"


def _comparison_status(summary: Dict[str, Any]) -> str:
    if not summary:
        return "pending"
    flag = _safe_bool(summary.get("comparison_artifact_ready"))
    if flag is True:
        return "available"
    if flag is False:
        return "pending"
    if str(summary.get("benchmark_stage", "")).strip().startswith("post_run"):
        return "available"
    return "pending"


def _launch_readiness_status(payload: Dict[str, Any]) -> str:
    readiness = payload.get("launch_readiness")
    if isinstance(readiness, dict):
        status = str(readiness.get("status", "") or "").strip()
        if status:
            return status
        ready = _safe_bool(readiness.get("ready"))
        if ready is True:
            return "ready"
        if ready is False:
            return "blocked"
    return "pending"


def _stage_plan_map(suite_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = suite_payload.get("stages")
    if not isinstance(rows, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _stage_result_map(suite_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = suite_payload.get("stage_results")
    if not isinstance(rows, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _stage_refresh_map(suite_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = suite_payload.get("suite_status_refreshes")
    if not isinstance(rows, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _suite_stage_enabled(stage_plan: Dict[str, Any]) -> Optional[bool]:
    enabled = _safe_bool(stage_plan.get("enabled"))
    return enabled


def _suite_stage_refresh_status(stage_result: Dict[str, Any], stage_refresh: Dict[str, Any]) -> str:
    refresh = stage_result.get("suite_status_refresh")
    if isinstance(refresh, dict):
        attempted = _safe_bool(refresh.get("ok"))
        if attempted is not None:
            return "refresh_ok" if attempted else "refresh_failed"
    if stage_refresh:
        ok = _safe_bool(stage_refresh.get("ok"))
        if ok is not None:
            return "refresh_ok" if ok else "refresh_failed"
    return "missing"


def _suite_stage_progress_status(stage_plan: Dict[str, Any], stage_result: Dict[str, Any]) -> str:
    if stage_result:
        if _safe_bool(stage_result.get("skipped")) is True:
            return "suite_execute_skipped"
        if _safe_bool(stage_result.get("ok")) is True:
            return "suite_execute_ok"
        if "returncode" in stage_result:
            return "suite_execute_failed"
    enabled = _suite_stage_enabled(stage_plan)
    if enabled is True:
        return "suite_dry_run_planned"
    if enabled is False:
        return "suite_stage_disabled"
    return "missing"


def _suite_stage_benchmark_stage(stage_plan: Dict[str, Any], stage_result: Dict[str, Any]) -> str:
    if stage_result:
        if _safe_bool(stage_result.get("skipped")) is True:
            return "suite_execute_skipped"
        if _safe_bool(stage_result.get("ok")) is True:
            return "suite_execute_ok"
        if "returncode" in stage_result:
            return "suite_execute_failed"
    enabled = _suite_stage_enabled(stage_plan)
    if enabled is True:
        return "suite_dry_run_planned"
    if enabled is False:
        return "suite_stage_disabled"
    return "pending"


def _suite_runner_meta(suite_dryrun: Dict[str, Any], suite_execute: Dict[str, Any]) -> Dict[str, Any]:
    payload = suite_execute or suite_dryrun
    latest_kind = "execute" if suite_execute else ("dry_run" if suite_dryrun else "missing")
    return {
        "artifact_state": _artifact_state(suite_dryrun, suite_execute),
        "latest_kind": latest_kind,
        "latest_generated_at_local": str(payload.get("generated_at_local", "") or ""),
        "dry_run_present": bool(suite_dryrun),
        "execute_present": bool(suite_execute),
        "dry_run_enabled_stage_count": _safe_int(suite_dryrun.get("enabled_stage_count")),
        "execute_completed_stage_count": _safe_int(suite_execute.get("completed_stage_count")),
        "execute_ok": _safe_bool(suite_execute.get("ok")),
        "execute_failed_stage_id": str(suite_execute.get("failed_stage_id", "") or ""),
        "execute_refresh_count": _safe_int(((suite_execute.get("final_execution_summary") or {}).get("suite_status_refresh_count"))),
    }


def _summary_matches_pilot(summary: Dict[str, Any], pilot_path: str) -> bool:
    if not summary:
        return False
    input_artifacts = summary.get("input_artifacts")
    if not isinstance(input_artifacts, dict):
        return False
    observed = str(input_artifacts.get("pilot_json", "") or "").strip()
    if not observed:
        return False
    expected = str(_resolve_repo_path(pilot_path))
    return str(Path(observed).resolve()) == expected


def _base_row(suite_id: str, suite_label: str) -> Dict[str, Any]:
    return {
        "suite_id": suite_id,
        "suite_label": suite_label,
        "artifact_state": "missing",
        "progress_status": "missing",
        "refresh_status": "missing",
        "benchmark_stage": "pending",
        "readiness_status": "pending",
        "comparison_kind": "",
        "comparison_status": "pending",
        "claim_safe_status": "pending",
        "commercialization_ready": None,
        "comparison_skipped": None,
        "selected_task_count": None,
        "selected_full_task_count": None,
        "selected_smoke_task_count": None,
        "target_scale_label": "",
        "domains_touched": [],
        "recommended_next_action": "Generate current artifacts for this suite.",
        "summary_attached": False,
    }


def _build_ab_row(ab_summary: Dict[str, Any]) -> Dict[str, Any]:
    row = _base_row("equal_size_ab", "Equal-size speedpack A/B")
    row["artifact_state"] = _artifact_state(ab_summary)
    if not ab_summary:
        return row
    scope = ab_summary.get("scope_summary") if isinstance(ab_summary.get("scope_summary"), dict) else {}
    row.update(
        {
            "benchmark_stage": str(ab_summary.get("benchmark_stage", "pending") or "pending"),
            "readiness_status": str(ab_summary.get("benchmark_stage", "pending") or "pending"),
            "comparison_kind": str(ab_summary.get("comparison_kind", "") or ""),
            "comparison_status": _comparison_status(ab_summary),
            "claim_safe_status": _claim_safe_status(ab_summary),
            "commercialization_ready": _safe_bool(ab_summary.get("commercialization_ready")),
            "progress_status": "prelaunch_scaffold",
            "refresh_status": "summary_attached",
            "selected_task_count": _safe_int(scope.get("selected_task_count") or scope.get("ligand_task_count")),
            "selected_full_task_count": _safe_int(scope.get("selected_full_task_count")),
            "selected_smoke_task_count": _safe_int(scope.get("selected_smoke_task_count")),
            "target_scale_label": "equal-size",
            "domains_touched": scope.get("domains_touched") if isinstance(scope.get("domains_touched"), list) else [],
            "recommended_next_action": str(ab_summary.get("recommended_next_action", row["recommended_next_action"]) or row["recommended_next_action"]),
            "summary_attached": True,
        }
    )
    return row


def _refresh_status(payload: Dict[str, Any], matched_summary: Dict[str, Any]) -> str:
    if matched_summary:
        return "summary_attached"
    refresh = payload.get("post_run_refresh")
    if isinstance(refresh, dict) and bool(refresh.get("attempted", False)):
        return "refresh_ok" if bool(refresh.get("ok", False)) else "refresh_failed"
    if isinstance(refresh, dict) and ("enabled" in refresh):
        return "refresh_planned" if bool(refresh.get("enabled", False)) else "refresh_disabled"
    return "missing"


def _progress_status(
    pilot: Dict[str, Any],
    dryrun: Dict[str, Any],
    matched_summary: Dict[str, Any],
    readiness_status: str,
) -> str:
    if matched_summary:
        return "post_run_with_summary"
    if pilot and bool(pilot.get("ok")) and str(pilot.get("candidate_run_root", "")).strip():
        refresh = pilot.get("post_run_refresh")
        if isinstance(refresh, dict) and bool(refresh.get("attempted", False)):
            return "post_run_partial" if not matched_summary else "post_run_with_summary"
        return "post_run_partial"
    if dryrun or pilot:
        if readiness_status == "ready":
            return "prelaunch_ready"
        if readiness_status == "blocked":
            return "prelaunch_blocked"
        return "prelaunch_scaffold"
    return "missing"


def _build_pilot_row(
    *,
    suite_id: str,
    suite_label: str,
    target_scale_label: str,
    pilot_json_path: str,
    pilot: Dict[str, Any],
    dryrun: Dict[str, Any],
    summary: Dict[str, Any],
    suite_stage_plan: Dict[str, Any],
    suite_stage_result: Dict[str, Any],
    suite_stage_refresh: Dict[str, Any],
) -> Dict[str, Any]:
    matched_summary = summary if ((pilot or dryrun) and _summary_matches_pilot(summary, pilot_json_path)) else {}
    row = _base_row(suite_id, suite_label)
    row["artifact_state"] = _artifact_state(pilot, dryrun, matched_summary, suite_stage_plan, suite_stage_result)
    row["target_scale_label"] = target_scale_label
    if not pilot and not dryrun and not matched_summary and not suite_stage_plan and not suite_stage_result:
        return row

    scope = pilot.get("scope_summary") if isinstance(pilot.get("scope_summary"), dict) else {}
    if not scope and isinstance(suite_stage_plan, dict):
        stage_expected = suite_stage_plan.get("expected_outputs")
        if isinstance(stage_expected, list):
            pass
    row["comparison_kind"] = str((pilot.get("comparison_kind") or dryrun.get("comparison_kind") or matched_summary.get("comparison_kind") or "") ).strip()
    row["selected_task_count"] = _safe_int(scope.get("ligand_stress_task_count"))
    row["selected_full_task_count"] = _safe_int(
        scope.get("full_task_count_target")
        if scope.get("full_task_count_target") is not None
        else scope.get("full_task_count_100k")
    )
    row["selected_smoke_task_count"] = _safe_int(scope.get("smoke_task_count_unchanged"))
    row["domains_touched"] = scope.get("domains_touched") if isinstance(scope.get("domains_touched"), list) else []
    row["readiness_status"] = _launch_readiness_status(dryrun or pilot)
    row["comparison_skipped"] = _safe_bool((pilot or {}).get("comparison_skipped"))
    row["recommended_next_action"] = str(
        (
            matched_summary.get("recommended_next_action")
            or ((pilot.get("launch_readiness") or {}).get("next_required_step") if isinstance(pilot.get("launch_readiness"), dict) else "")
            or str(suite_stage_plan.get("note", "") or "")
            or row["recommended_next_action"]
        )
    ).strip() or row["recommended_next_action"]
    row["refresh_status"] = _refresh_status(pilot, matched_summary)
    if row["refresh_status"] == "missing" and (suite_stage_result or suite_stage_refresh):
        row["refresh_status"] = _suite_stage_refresh_status(suite_stage_result, suite_stage_refresh)
    row["progress_status"] = _progress_status(pilot, dryrun, matched_summary, row["readiness_status"])
    if row["progress_status"] == "missing" and (suite_stage_plan or suite_stage_result):
        row["progress_status"] = _suite_stage_progress_status(suite_stage_plan, suite_stage_result)
    if matched_summary:
        row["benchmark_stage"] = str(matched_summary.get("benchmark_stage", "pending") or "pending")
        row["comparison_status"] = _comparison_status(matched_summary)
        row["claim_safe_status"] = _claim_safe_status(matched_summary)
        row["commercialization_ready"] = _safe_bool(matched_summary.get("commercialization_ready"))
        row["summary_attached"] = True
    else:
        if pilot and bool(pilot.get("ok")) and str(pilot.get("candidate_run_root", "")).strip():
            if row["refresh_status"] == "refresh_failed":
                row["benchmark_stage"] = "post_run_refresh_failed"
            elif row["comparison_skipped"] is True:
                row["benchmark_stage"] = "post_run_no_comparison"
            else:
                row["benchmark_stage"] = "post_run_partial"
        elif suite_stage_plan or suite_stage_result:
            row["benchmark_stage"] = _suite_stage_benchmark_stage(suite_stage_plan, suite_stage_result)
        else:
            row["benchmark_stage"] = "prelaunch_scaffold" if pilot or dryrun else "pending"
        row["comparison_status"] = (
            "skipped"
            if row["comparison_skipped"] is True
            else ("available" if bool((dryrun.get("comparison_enabled") if isinstance(dryrun, dict) else False)) else "pending")
        )
        row["claim_safe_status"] = "pending"
    return row


def build_suite_status(args: argparse.Namespace) -> Dict[str, Any]:
    suite_dryrun = _read_json_if_exists(getattr(args, "suite_dryrun_json", ""))
    suite_execute = _read_json_if_exists(getattr(args, "suite_execute_json", ""))
    suite_stage_plans = _stage_plan_map(suite_dryrun)
    suite_stage_results = _stage_result_map(suite_execute)
    suite_stage_refreshes = _stage_refresh_map(suite_execute)
    ab_summary = _read_json_if_exists(args.ab_summary_json)
    pilot_100k = _read_json_if_exists(args.pilot_100k_json)
    dryrun_100k = _read_json_if_exists(args.pilot_100k_dryrun_json)
    summary_100k = _read_json_if_exists(args.pilot_100k_summary_json)
    pilot_1m = _read_json_if_exists(args.pilot_1m_json)
    dryrun_1m = _read_json_if_exists(args.pilot_1m_dryrun_json)
    summary_1m = _read_json_if_exists(args.pilot_1m_summary_json)
    shared_summary = _read_json_if_exists(getattr(args, "shared_benchmark_summary_json", args.pilot_100k_summary_json))

    rows = [
        _build_ab_row(ab_summary),
        _build_pilot_row(
            suite_id="pilot_100k",
            suite_label="100k commercialization pilot",
            target_scale_label="100k",
            pilot_json_path=args.pilot_100k_json,
            pilot=pilot_100k,
            dryrun=dryrun_100k,
            summary=summary_100k or shared_summary,
            suite_stage_plan=suite_stage_plans.get("pilot_100k", {}),
            suite_stage_result=suite_stage_results.get("pilot_100k", {}),
            suite_stage_refresh=suite_stage_refreshes.get("pilot_100k", {}),
        ),
        _build_pilot_row(
            suite_id="pilot_1m",
            suite_label="1M commercialization pilot",
            target_scale_label="1M",
            pilot_json_path=args.pilot_1m_json,
            pilot=pilot_1m,
            dryrun=dryrun_1m,
            summary=summary_1m or shared_summary,
            suite_stage_plan=suite_stage_plans.get("pilot_1m", {}),
            suite_stage_result=suite_stage_results.get("pilot_1m", {}),
            suite_stage_refresh=suite_stage_refreshes.get("pilot_1m", {}),
        ),
    ]
    ready_rows = [row for row in rows if row.get("readiness_status") == "ready"]
    comparison_ready_rows = [row for row in rows if row.get("comparison_status") == "available"]
    commercialization_ready_rows = [row for row in rows if row.get("commercialization_ready") is True]
    post_run_rows = [row for row in rows if str(row.get("progress_status", "")).startswith("post_run")]
    refreshed_rows = [row for row in rows if row.get("refresh_status") in {"summary_attached", "refresh_ok"}]
    summary = {
        "suite_count": len(rows),
        "ready_suite_count": len(ready_rows),
        "comparison_ready_suite_count": len(comparison_ready_rows),
        "commercialization_ready_suite_count": len(commercialization_ready_rows),
        "post_run_suite_count": len(post_run_rows),
        "refreshed_suite_count": len(refreshed_rows),
        "pending_suite_ids": [row["suite_id"] for row in rows if row.get("artifact_state") != "present" or row.get("claim_safe_status") == "pending"],
        "summary_attached_suite_count": int(sum(1 for row in rows if bool(row.get("summary_attached")))),
    }
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "suite_rows": rows,
        "summary": summary,
        "suite_runner": _suite_runner_meta(suite_dryrun, suite_execute),
        "input_artifacts": {
            "suite_dryrun_json": str(_resolve_repo_path(getattr(args, "suite_dryrun_json", "runs/ligand_scaleup_suite_dryrun_current.json"))),
            "suite_execute_json": str(_resolve_repo_path(getattr(args, "suite_execute_json", "runs/ligand_scaleup_suite_current.json"))),
            "ab_summary_json": str(_resolve_repo_path(args.ab_summary_json)),
            "pilot_100k_json": str(_resolve_repo_path(args.pilot_100k_json)),
            "pilot_100k_dryrun_json": str(_resolve_repo_path(args.pilot_100k_dryrun_json)),
            "pilot_100k_summary_json": str(_resolve_repo_path(args.pilot_100k_summary_json)),
            "pilot_1m_json": str(_resolve_repo_path(args.pilot_1m_json)),
            "pilot_1m_dryrun_json": str(_resolve_repo_path(args.pilot_1m_dryrun_json)),
            "pilot_1m_summary_json": str(_resolve_repo_path(args.pilot_1m_summary_json)),
            "shared_benchmark_summary_json": str(_resolve_repo_path(getattr(args, "shared_benchmark_summary_json", args.pilot_100k_summary_json))),
        },
    }


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "suite_id",
        "suite_label",
        "artifact_state",
        "progress_status",
        "refresh_status",
        "benchmark_stage",
        "readiness_status",
        "comparison_kind",
        "comparison_status",
        "claim_safe_status",
        "commercialization_ready",
        "comparison_skipped",
        "selected_task_count",
        "selected_full_task_count",
        "selected_smoke_task_count",
        "target_scale_label",
        "domains_touched",
        "summary_attached",
        "recommended_next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["domains_touched"] = _join_list(row.get("domains_touched"))
            writer.writerow({k: flat.get(k, "") for k in fields})


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    rows = payload["suite_rows"]
    summary = payload["summary"]
    suite_runner = payload.get("suite_runner") if isinstance(payload.get("suite_runner"), dict) else {}
    lines = [
        "# Ligand Scale-up Suite Status",
        "",
        f"- generated_at_local: `{payload['generated_at_local']}`",
        f"- ready suites: `{summary['ready_suite_count']}/{summary['suite_count']}`",
        f"- comparison-ready suites: `{summary['comparison_ready_suite_count']}/{summary['suite_count']}`",
        f"- commercialization-ready suites: `{summary['commercialization_ready_suite_count']}/{summary['suite_count']}`",
        f"- post-run suites: `{summary['post_run_suite_count']}/{summary['suite_count']}`",
        f"- refreshed suites: `{summary['refreshed_suite_count']}/{summary['suite_count']}`",
        f"- summary-attached suites: `{summary['summary_attached_suite_count']}/{summary['suite_count']}`",
        f"- suite runner artifacts: `{suite_runner.get('artifact_state', 'missing')}`",
        f"- suite runner latest kind: `{suite_runner.get('latest_kind', 'missing')}`",
        "",
        "| suite_id | artifact_state | progress | refresh | benchmark_stage | readiness | comparison | claim_safe | commercialization_ready | tasks | full | smoke | scale | domains |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {suite_id} | {artifact_state} | {progress_status} | {refresh_status} | {benchmark_stage} | {readiness_status} | {comparison_status} | {claim_safe_status} | {commercialization_ready} | {selected_task_count} | {selected_full_task_count} | {selected_smoke_task_count} | {target_scale_label} | {domains} |".format(
                suite_id=row.get("suite_id", ""),
                artifact_state=row.get("artifact_state", ""),
                progress_status=row.get("progress_status", ""),
                refresh_status=row.get("refresh_status", ""),
                benchmark_stage=row.get("benchmark_stage", ""),
                readiness_status=row.get("readiness_status", ""),
                comparison_status=row.get("comparison_status", ""),
                claim_safe_status=row.get("claim_safe_status", ""),
                commercialization_ready=row.get("commercialization_ready", "pending"),
                selected_task_count=row.get("selected_task_count", ""),
                selected_full_task_count=row.get("selected_full_task_count", ""),
                selected_smoke_task_count=row.get("selected_smoke_task_count", ""),
                target_scale_label=row.get("target_scale_label", ""),
                domains=_join_list(row.get("domains_touched")),
            )
        )
    lines.append("")
    for row in rows:
        lines.append(f"## {row.get('suite_label', row.get('suite_id', 'suite'))}")
        lines.append("")
        lines.append(f"- recommended_next_action: `{row.get('recommended_next_action', '')}`")
        lines.append(f"- summary_attached: `{row.get('summary_attached', False)}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build suite-level commercialization scale-up status from current artifacts.")
    parser.add_argument("--suite-dryrun-json", default="runs/ligand_scaleup_suite_dryrun_current.json")
    parser.add_argument("--suite-execute-json", default="runs/ligand_scaleup_suite_current.json")
    parser.add_argument("--ab-summary-json", default="runs/ligand_speedpack_ab_summary_current.json")
    parser.add_argument("--pilot-100k-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    parser.add_argument("--pilot-100k-dryrun-json", default="runs/ligand_scaleup_100k_pilot_dryrun_current.json")
    parser.add_argument("--pilot-100k-summary-json", default="runs/ligand_scaleup_benchmark_summary_current.json")
    parser.add_argument("--pilot-1m-json", default="runs/ligand_scaleup_1m_pilot_current.json")
    parser.add_argument("--pilot-1m-dryrun-json", default="runs/ligand_scaleup_1m_pilot_dryrun_current.json")
    parser.add_argument("--pilot-1m-summary-json", default="runs/ligand_scaleup_1m_benchmark_summary_current.json")
    parser.add_argument("--shared-benchmark-summary-json", default="runs/ligand_scaleup_benchmark_summary_current.json")
    parser.add_argument("--out-json", default="runs/ligand_scaleup_suite_status_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_scaleup_suite_status_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_scaleup_suite_status_current.md")
    args = parser.parse_args()

    payload = build_suite_status(args)
    out_json = _resolve_repo_path(args.out_json)
    out_csv = _resolve_repo_path(args.out_csv)
    out_md = _resolve_repo_path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["suite_rows"])
    _write_md(out_md, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
