#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODE_COMPARISON_JSON = "runs/gpcr_residual_chembl50_v3_mode_comparison_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_assist_candidate_selection_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_assist_candidate_selection_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_assist_candidate_selection_current.md"

MEAN_DELTA_CAP = 0.01
PR_DELTA_MIN = 0.0

CLAIM_BOUNDARY = (
    "GPCR residual assist candidate selection only; selects per-task low-risk residual routing from existing local "
    "mode-comparison evidence. It does not alter rankings, promote assist/production mode, run docking, run benchmarks, "
    "train models, upload, submit, email, archive, externalize, or delete files."
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


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _mode_candidate(row: dict[str, Any], mode: str) -> dict[str, Any]:
    prefix = "shadow" if mode == "shadow" else "apply"
    pass_ok = row.get(f"{prefix}_pass") is True
    complete = row.get(f"{prefix}_complete") is True
    delta_pr = _float(row.get(f"delta_pr_auc_{prefix}_vs_baseline"))
    delta_ef1 = _float(row.get(f"delta_ef1_{prefix}_vs_baseline"))
    mean_delta = abs(_float(row.get(f"{prefix}_residual_mean_delta")))
    clean = bool(pass_ok and complete and delta_pr >= PR_DELTA_MIN and mean_delta <= MEAN_DELTA_CAP)
    return {
        "mode": mode,
        "pass_ok": pass_ok,
        "complete": complete,
        "delta_pr_auc_vs_baseline": delta_pr,
        "delta_ef1_vs_baseline": delta_ef1,
        "residual_mean_delta_abs": mean_delta,
        "pr_clean": delta_pr >= PR_DELTA_MIN,
        "norm_ok": mean_delta <= MEAN_DELTA_CAP,
        "clean": clean,
    }


def _select_row(row: dict[str, Any]) -> dict[str, Any]:
    candidates = [_mode_candidate(row, "shadow"), _mode_candidate(row, "apply")]
    clean_candidates = [candidate for candidate in candidates if candidate["clean"]]
    if clean_candidates:
        selected = sorted(clean_candidates, key=lambda item: (item["delta_ef1_vs_baseline"], item["delta_pr_auc_vs_baseline"]), reverse=True)[0]
        reason = "Selected clean residual mode with maximum EF1 gain and non-negative PR-AUC delta."
    else:
        selected = {
            "mode": "abstain",
            "pass_ok": bool(row.get("baseline_pass") is True),
            "complete": True,
            "delta_pr_auc_vs_baseline": 0.0,
            "delta_ef1_vs_baseline": 0.0,
            "residual_mean_delta_abs": 0.0,
            "pr_clean": True,
            "norm_ok": True,
            "clean": bool(row.get("baseline_pass") is True),
        }
        reason = "No clean residual mode; abstain and preserve baseline."
    return {
        "task_id": _text(row.get("task_id")),
        "baseline_pass": bool(row.get("baseline_pass") is True),
        "selected_mode": selected["mode"],
        "selected_pass_ok": selected["pass_ok"],
        "selected_delta_pr_auc_vs_baseline": selected["delta_pr_auc_vs_baseline"],
        "selected_delta_ef1_vs_baseline": selected["delta_ef1_vs_baseline"],
        "selected_residual_mean_delta_abs": selected["residual_mean_delta_abs"],
        "selected_pr_clean": selected["pr_clean"],
        "selected_norm_ok": selected["norm_ok"],
        "selected_clean": selected["clean"],
        "residual_assist_applied": selected["mode"] in {"shadow", "apply"} and selected["delta_ef1_vs_baseline"] > 0,
        "shadow_delta_pr_auc_vs_baseline": candidates[0]["delta_pr_auc_vs_baseline"],
        "shadow_delta_ef1_vs_baseline": candidates[0]["delta_ef1_vs_baseline"],
        "apply_delta_pr_auc_vs_baseline": candidates[1]["delta_pr_auc_vs_baseline"],
        "apply_delta_ef1_vs_baseline": candidates[1]["delta_ef1_vs_baseline"],
        "release_blocker": not bool(selected["clean"]),
        "reason": reason,
    }


def build_gpcr_residual_assist_candidate_selection(
    *,
    mode_comparison_packet: dict[str, Any],
    mode_comparison_path: str = DEFAULT_MODE_COMPARISON_JSON,
) -> dict[str, Any]:
    rows = [_select_row(row) for row in _rows(mode_comparison_packet)]
    task_count = len(rows)
    blocker_count = sum(1 for row in rows if row["release_blocker"])
    pr_warning_count = sum(1 for row in rows if not row["selected_pr_clean"])
    residual_applied_task_count = sum(1 for row in rows if row["residual_assist_applied"])
    intrusion_reduction_task_count = sum(1 for row in rows if row["selected_delta_ef1_vs_baseline"] > 0)
    pass_to_fail_count = sum(1 for row in rows if row["baseline_pass"] and not row["selected_pass_ok"])
    assist_candidate_ready = bool(
        task_count > 0
        and blocker_count == 0
        and pr_warning_count == 0
        and pass_to_fail_count == 0
        and residual_applied_task_count > 0
        and intrusion_reduction_task_count > 0
    )
    summary = {
        "packet_type": "gpcr_residual_assist_candidate_selection",
        "status": "gpcr_residual_assist_candidate_selection_ready" if assist_candidate_ready else "blocked_gpcr_residual_assist_candidate_selection",
        "assist_candidate_ready": assist_candidate_ready,
        "assist_promotion_candidate_ready": assist_candidate_ready,
        "mode_comparison_artifact": mode_comparison_path,
        "selection_policy": "per_task_clean_mode_max_ef1_else_abstain",
        "task_count": task_count,
        "blocker_count": blocker_count,
        "pr_auc_regression_warning_count": pr_warning_count,
        "pass_to_fail_regression_count": pass_to_fail_count,
        "residual_applied_task_count": residual_applied_task_count,
        "intrusion_reduction_task_count": intrusion_reduction_task_count,
        "correction_norm_cap": MEAN_DELTA_CAP,
        "pr_delta_min": PR_DELTA_MIN,
        "assist_promotion_allowed": False,
        "production_promotion_allowed": False,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this candidate selection as GPCR-local assist evidence, then require public benchmark assist comparison."
            if assist_candidate_ready
            else "Generate a clean per-task assist candidate with no PR-AUC regression and no pass-to-fail regression."
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
        "# GPCR Residual Assist Candidate Selection",
        "",
        f"- status: `{s['status']}`",
        f"- assist_candidate_ready: `{s['assist_candidate_ready']}`",
        f"- selection_policy: `{s['selection_policy']}`",
        f"- task_count: `{s['task_count']}`",
        f"- residual_applied_task_count: `{s['residual_applied_task_count']}`",
        f"- pr_auc_regression_warning_count: `{s['pr_auc_regression_warning_count']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        "",
        "## Selections",
        "",
        "| task | selected mode | dPR | dEF1 | pr clean | norm ok | assist applied | reason |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['task_id']}` | `{row['selected_mode']}` | `{row['selected_delta_pr_auc_vs_baseline']}` | "
            f"`{row['selected_delta_ef1_vs_baseline']}` | `{row['selected_pr_clean']}` | `{row['selected_norm_ok']}` | "
            f"`{row['residual_assist_applied']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR residual assist candidate selection from mode-comparison evidence.")
    parser.add_argument("--mode-comparison-json", default=DEFAULT_MODE_COMPARISON_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_gpcr_residual_assist_candidate_selection(
        mode_comparison_packet=_read_json_if_present(args.mode_comparison_json),
        mode_comparison_path=args.mode_comparison_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
