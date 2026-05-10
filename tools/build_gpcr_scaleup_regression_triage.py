#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_SUMMARY_JSON = "runs/ligand_scaleup_benchmark_summary_current.json"
DEFAULT_SUITE_STATUS_JSON = "runs/ligand_scaleup_suite_status_current.json"
DEFAULT_FAILURE_ANALYSIS_JSON = "runs/gpcr_100k_failure_analysis_current.json"
DEFAULT_CANDIDATE_GLOB = "runs/external_validation_*gpcr*summary.json"
DEFAULT_OUT_JSON = "runs/gpcr_scaleup_regression_triage_current.json"
DEFAULT_OUT_MD = "runs/gpcr_scaleup_regression_triage_current.md"


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json_if_exists(path_str: str) -> dict[str, Any]:
    path = _resolve(path_str)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload.get("aggregate")
    if isinstance(aggregate, list):
        for row in aggregate:
            if isinstance(row, dict):
                return row
    return {}


def _cmd_value(payload: dict[str, Any], flag: str) -> str:
    failures = payload.get("failures")
    if not isinstance(failures, list):
        return ""
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        command = failure.get("command")
        if not isinstance(command, dict):
            continue
        cmd = command.get("cmd")
        if not isinstance(cmd, list):
            continue
        parts = [str(part) for part in cmd]
        for idx, part in enumerate(parts[:-1]):
            if part == flag:
                return parts[idx + 1]
    return ""


def _nested_stage_cmd_value(payload: dict[str, Any], stage_key: str, flag: str) -> str:
    stages = payload.get("stages")
    if not isinstance(stages, dict):
        return ""
    stage = stages.get(stage_key)
    if not isinstance(stage, dict):
        return ""
    cmd = stage.get("cmd")
    if not isinstance(cmd, list):
        return ""
    parts = [str(part) for part in cmd]
    for idx, part in enumerate(parts[:-1]):
        if part == flag:
            return parts[idx + 1]
    return ""


def _stage5_summary_for(path: Path) -> dict[str, Any]:
    stem = path.name
    candidates: list[Path] = []
    if stem.endswith("_summary.json"):
        candidates.append(path.with_name(stem[: -len("_summary.json")] + "_stage5_ranking_summary.json"))
        candidates.extend(sorted(path.parent.glob(stem[: -len("_summary.json")] + "_p0_n*_r*_stage5_ranking_summary.json")))
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
    return {}


def _infer_candidate_id(path: Path, payload: dict[str, Any]) -> str:
    source = " ".join([path.stem, _text(payload.get("profile_json")), _text(payload.get("tag")), _text(payload.get("profile"))]).lower()
    def _token_version(token: str) -> str:
        match = re.search(rf"{re.escape(token)}(?:_|-|_rescore_|-rescore-)?v(\d+)(?:_|-|$)", source)
        return match.group(1) if match else "1"

    if ("fixed_reference" in source or "fixed-ref" in source) and (
        "decoy_intrusion" in source or "decoy-intrusion" in source
    ):
        return "gpcr_core_fixed_reference_decoy_intrusion_v1"
    if "decoy_intrusion" in source or "decoy-intrusion" in source:
        version = _token_version("decoy_intrusion")
        if version == "1":
            version = _token_version("decoy-intrusion")
        return f"gpcr_core_decoy_intrusion_v{version}"
    if "linear" in source or "logit" in source:
        version = _token_version("linear")
        return f"gpcr_core_linear_rescore_v{version}"
    if "pharmacophore" in source:
        version = _token_version("pharmacophore")
        return f"gpcr_core_pharmacophore_v{version}"
    if "structure_support" in source or "structure-support" in source:
        version = _token_version("structure_support")
        if version == "1":
            version = _token_version("structure-support")
        return f"gpcr_core_structure_support_rescore_v{version}"
    if "beta_blocker_rescue" in source or "beta-blocker-rescue" in source:
        version = _token_version("beta_blocker_rescue")
        if version == "1":
            version = _token_version("beta-blocker-rescue")
        return f"gpcr_core_beta_blocker_rescue_v{version}"
    if "mismatch_contact" in source or "mismatch-contact" in source:
        version = _token_version("mismatch_contact")
        if version == "1":
            version = _token_version("mismatch-contact")
        return f"gpcr_core_mismatch_contact_rescore_v{version}"
    if "residualv4" in source or "residual-v4" in source:
        version = _token_version("residualv4")
        if version == "1":
            version = _token_version("residual-v4")
        return f"gpcr_core_residualv4_v{version}"
    if "repair" in source:
        version = _token_version("repair")
        return f"gpcr_core_repair_v{version}"
    compact = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    return compact or "gpcr_core_candidate_v1"


def _infer_candidate_tag(path: Path, payload: dict[str, Any]) -> str:
    profile = Path(_text(payload.get("profile_json"))).stem if _text(payload.get("profile_json")) else ""
    if profile:
        return profile
    return path.stem.removeprefix("external_validation_").removesuffix("_summary")


def _infer_mode(path: Path, payload: dict[str, Any]) -> str:
    source = " ".join([path.stem, _text(payload.get("profile_json")), _text(payload.get("tag")), _text(payload.get("profile"))]).lower()
    profile_json = _text(payload.get("profile_json"))
    if profile_json:
        profile = _read_json_if_exists(profile_json)
        mode = _text(profile.get("residual_prototype_mode")).lower()
        if mode == "apply":
            return "guarded_apply"
        if mode == "shadow_only":
            return "shadow"
    stage_mode = _nested_stage_cmd_value(payload, "stage3_backmapping_scoring", "--residual-prototype-mode").lower()
    if stage_mode == "apply":
        return "guarded_apply"
    if stage_mode == "shadow_only":
        return "shadow"
    if "shadow" in source:
        return "shadow"
    if "apply" in source:
        return "guarded_apply"
    if "candidate" in source:
        return "candidate"
    return "comparison"


def _is_candidate_summary(path: Path, payload: dict[str, Any]) -> bool:
    name = path.name.lower()
    if "_stage" in name or "_hard_decoy_" in name or "_sla_summary" in name:
        return False
    if "gpcr_core_full" not in name:
        return False
    source = " ".join([name, _text(payload.get("profile_json")).lower()])
    tokens = [
        "scaleup_100k",
        "decoy_intrusion",
        "decoy-intrusion",
        "fixed_reference",
        "fixed-ref",
        "linear",
        "logit",
        "pharmacophore",
        "structure_support",
        "structure-support",
        "beta_blocker_rescue",
        "beta-blocker-rescue",
        "mismatch_contact",
        "mismatch-contact",
        "residualv4",
        "repair",
    ]
    return any(token in source for token in tokens)


def _candidate_metrics(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = _first_aggregate(payload)
    stage5 = _stage5_summary_for(path)
    stage5_metrics = stage5.get("metrics") if isinstance(stage5.get("metrics"), dict) else {}
    return {
        "ranking_pr_auc": _safe_float(stage5_metrics.get("pr_auc", aggregate.get("ranking_pr_auc_mean"))),
        "topk_hit_rate": _safe_float(aggregate.get("topk_hit_rate_mean")),
        "ranking_unique_auc": _safe_float(stage5_metrics.get("roc_auc_unique_key", aggregate.get("ranking_unique_auc_mean"))),
        "operational_gate_pass_mean": _safe_float(aggregate.get("operational_gate_pass_mean")),
    }


def _score_column(path: Path, payload: dict[str, Any]) -> str:
    direct = _text(payload.get("score_column") or payload.get("score_col") or payload.get("rank_col"))
    if direct:
        return direct
    command_score = _cmd_value(payload, "--ranking-score-col")
    if command_score:
        return command_score
    stage5 = _stage5_summary_for(path)
    metrics = stage5.get("metrics") if isinstance(stage5.get("metrics"), dict) else {}
    return _text(metrics.get("probability_score_col_used"))


def _candidate_row(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    passed = _safe_bool(payload.get("pass"))
    candidate_id = _infer_candidate_id(path, payload)
    return {
        "candidate_id": candidate_id,
        "artifact": str(path),
        "tag": _infer_candidate_tag(path, payload),
        "profile": _text(payload.get("profile") or payload.get("profile_json")),
        "score_column": _score_column(path, payload),
        "mode": _infer_mode(path, payload),
        "pass": passed,
        "claim_allowed": False,
        "evidence_role": "comparison_only",
        "comparison_only": True,
        "reject_evidence": bool(passed is False),
        "metrics": _candidate_metrics(path, payload),
        "triage_note": (
            "failed candidate is rejection evidence only"
            if passed is False
            else "passing candidate is comparison-only evidence, not a delivery or router claim"
        ),
    }


def _candidate_mode_priority(row: dict[str, Any]) -> int:
    mode = str(row.get("mode", ""))
    priorities = {
        "guarded_apply": 4,
        "candidate": 3,
        "comparison": 2,
        "shadow": 1,
    }
    return priorities.get(mode, 0)


def _prefer_candidate_row(current: dict[str, Any], row: dict[str, Any]) -> bool:
    current_priority = _candidate_mode_priority(current)
    row_priority = _candidate_mode_priority(row)
    if row_priority != current_priority:
        return row_priority > current_priority
    current_pass = current.get("pass")
    row_pass = row.get("pass")
    if current_pass is True and row_pass is False:
        return True
    if current_pass is False and row_pass is True:
        return False
    current_metrics = current.get("metrics") if isinstance(current.get("metrics"), dict) else {}
    row_metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    current_metric_count = sum(1 for value in current_metrics.values() if value is not None)
    row_metric_count = sum(1 for value in row_metrics.values() if value is not None)
    if row_metric_count != current_metric_count:
        return row_metric_count > current_metric_count
    return len(str(row.get("artifact", ""))) < len(str(current.get("artifact", "")))


def _discover_candidates(candidate_glob: str) -> list[dict[str, Any]]:
    pattern = str(_resolve(candidate_glob))
    rows_by_id: dict[str, dict[str, Any]] = {}
    for path_str in sorted(glob.glob(pattern)):
        path = Path(path_str)
        payload = _read_json_if_exists(str(path))
        if not payload or not _is_candidate_summary(path, payload):
            continue
        row = _candidate_row(path, payload)
        current = rows_by_id.get(row["candidate_id"])
        if current is None:
            rows_by_id[row["candidate_id"]] = row
            continue
        if _prefer_candidate_row(current, row):
            rows_by_id[row["candidate_id"]] = row
    return sorted(rows_by_id.values(), key=lambda row: str(row.get("candidate_id", "")))


def _guardrail_fail_count(benchmark: dict[str, Any]) -> int:
    explicit = _safe_int(benchmark.get("guardrail_fail_count"))
    if explicit is not None:
        return explicit
    rows = benchmark.get("guardrail_rows")
    if not isinstance(rows, list):
        return 0
    return int(sum(1 for row in rows if isinstance(row, dict) and row.get("pass") is False))


def _primary_blocker_task(benchmark: dict[str, Any]) -> str:
    candidates = [
        benchmark.get("primary_regression_task_id"),
        (benchmark.get("regression_diagnostics") or {}).get("primary_regression_task_id")
        if isinstance(benchmark.get("regression_diagnostics"), dict)
        else "",
        (benchmark.get("scaleup_repair_packet") or {}).get("task_id") if isinstance(benchmark.get("scaleup_repair_packet"), dict) else "",
    ]
    for candidate in candidates:
        if _text(candidate):
            return _text(candidate)
    return ""


def _claim_safe(benchmark: dict[str, Any]) -> bool:
    explicit = _safe_bool(benchmark.get("claim_safe"))
    if explicit is not None:
        return explicit
    return False


def _claim_safe_status(benchmark: dict[str, Any], claim_safe: bool) -> str:
    explicit = _text(benchmark.get("claim_safe_status"))
    if explicit:
        return explicit
    return "claim_safe" if claim_safe else "regression_guardrail_failed"


def _recommended_next_action(claim_safe: bool, primary_blocker_task: str) -> str:
    if not claim_safe:
        task = primary_blocker_task or "gpcr_core_full"
        return (
            f"Keep claim_safe=false for {task}; continue guarded/shadow diagnostics or run a new score "
            "family-held-out validation before any router promotion."
        )
    return "Review guarded/shadow diagnostics and independent held-out validation before expanding the claim scope."


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    benchmark = _read_json_if_exists(args.benchmark_summary_json)
    suite_status = _read_json_if_exists(args.suite_status_json)
    failure_analysis = _read_json_if_exists(args.failure_analysis_json)
    candidates = _discover_candidates(args.candidate_glob)
    claim_safe = _claim_safe(benchmark)
    claim_safe_status = _claim_safe_status(benchmark, claim_safe)
    primary_blocker_task = _primary_blocker_task(benchmark)
    rejected_count = int(sum(1 for row in candidates if row.get("reject_evidence") is True))
    comparison_only_count = int(sum(1 for row in candidates if row.get("claim_allowed") is False))
    summary = {
        "claim_safe": claim_safe,
        "claim_safe_status": claim_safe_status,
        "primary_blocker_task": primary_blocker_task,
        "guardrail_fail_count": _guardrail_fail_count(benchmark),
        "candidate_count": int(len(candidates)),
        "rejected_candidate_count": rejected_count,
        "comparison_only_candidate_count": comparison_only_count,
        "recommended_next_action": _recommended_next_action(claim_safe, primary_blocker_task),
    }
    score_diagnostics = failure_analysis.get("score_diagnostics") if isinstance(failure_analysis.get("score_diagnostics"), dict) else {}
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": summary,
        "regression_diagnostics": benchmark.get("regression_diagnostics", {}),
        "guardrail_rows": benchmark.get("guardrail_rows", []),
        "failure_analysis_summary": failure_analysis.get("summary", {}) if isinstance(failure_analysis.get("summary"), dict) else {},
        "score_diagnostics": score_diagnostics,
        "suite_status_summary": suite_status.get("summary", {}) if isinstance(suite_status.get("summary"), dict) else {},
        "candidates": candidates,
        "input_artifacts": {
            "benchmark_summary_json": str(_resolve(args.benchmark_summary_json)),
            "suite_status_json": str(_resolve(args.suite_status_json)),
            "failure_analysis_json": str(_resolve(args.failure_analysis_json)),
            "candidate_glob": args.candidate_glob,
        },
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Scale-up Regression Triage",
        "",
        "## Summary",
        "",
        f"- claim_safe: `{summary['claim_safe']}`",
        f"- claim_safe_status: `{summary['claim_safe_status']}`",
        f"- primary_blocker_task: `{summary['primary_blocker_task']}`",
        f"- guardrail_fail_count: `{summary['guardrail_fail_count']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- rejected_candidate_count: `{summary['rejected_candidate_count']}`",
        f"- comparison_only_candidate_count: `{summary['comparison_only_candidate_count']}`",
        f"- recommended_next_action: {summary['recommended_next_action']}",
        "",
        "## Score Diagnostics",
        "",
    ]
    score = payload.get("score_diagnostics") if isinstance(payload.get("score_diagnostics"), dict) else {}
    lines.extend(
        [
            f"- available: `{score.get('available', False)}`",
            f"- existing_score_recovery_status: `{score.get('existing_score_recovery_status', '')}`",
            f"- root_cause_tags: `{score.get('root_cause_tags', [])}`",
            "",
            "## Candidates",
            "",
            "| candidate_id | mode | pass | claim_allowed | reject_evidence | score_column | pr_auc | topk_hit_rate |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: |",
        ]
    )
    for row in payload.get("candidates", []):
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        lines.append(
            f"| `{row.get('candidate_id', '')}` | `{row.get('mode', '')}` | `{row.get('pass')}` | "
            f"`{row.get('claim_allowed')}` | `{row.get('reject_evidence')}` | `{row.get('score_column', '')}` | "
            f"{metrics.get('ranking_pr_auc')} | {metrics.get('topk_hit_rate')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_md(out_md, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local GPCR scale-up regression triage packet without turning comparison-only evidence into claims."
    )
    parser.add_argument("--benchmark-summary-json", default=DEFAULT_BENCHMARK_SUMMARY_JSON)
    parser.add_argument("--suite-status-json", default=DEFAULT_SUITE_STATUS_JSON)
    parser.add_argument("--failure-analysis-json", default=DEFAULT_FAILURE_ANALYSIS_JSON)
    parser.add_argument("--candidate-glob", default=DEFAULT_CANDIDATE_GLOB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    write_outputs(parse_args())


if __name__ == "__main__":
    main()
