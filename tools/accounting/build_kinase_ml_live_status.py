#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

PROFILE_GLOBS = (
    "config/ligand_htvs_commercial_validation_no_leak_v3_gatefix1*.json",
    "config/ligand_htvs_commercial_validation_disjoint_strict_v3_gatefix1*.json",
    "config/ligand_htvs_commercial_validation_disjoint_strict_poscounter_smoke_v3_gatefix1*.json",
)
DEFAULT_CURRENT_PACKAGE_ROOT = "runs/biorxiv_external_validation_package_current.json"
DEFAULT_OUT_JSON = "runs/kinase_ml_live_status_current.json"
DEFAULT_OUT_CSV = "runs/kinase_ml_live_status_current.csv"
DEFAULT_OUT_MD = "runs/kinase_ml_live_status_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _score_is_ml_live(score_col: str) -> bool:
    return str(score_col or "").startswith("binding_score_composite_")


def _profile_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in PROFILE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            payload = _load_json(path)
            score_col = str(payload.get("ranking_score_col", "")).strip()
            rows.append(
                {
                    "row_kind": "profile",
                    "artifact": str(path),
                    "profile_version": str(payload.get("version", "")).strip(),
                    "ranking_score_col": score_col or "default_pipeline_fallback",
                    "ranking_probability_score_col": str(payload.get("ranking_probability_score_col", "")).strip(),
                    "ml_live_ready": _score_is_ml_live(score_col),
                }
            )
    return rows


def _extract_stage6_score_cols(payload: dict[str, Any]) -> tuple[str, str]:
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    return (
        str(stage6.get("ranking_score_col_used", "")).strip(),
        str(stage6.get("ranking_probability_score_col_used", "")).strip(),
    )


def _resolve_current_package_root(path_like: str) -> Path:
    resolved = _resolve(path_like)
    if resolved.is_file():
        payload = _load_json(resolved)
        package_root = str(payload.get("package_root", "")).strip()
        if package_root:
            return _resolve(package_root)
    return resolved


def _manifest_task_rows(package_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest_json in sorted(package_root.glob("sets/*/manifest.json")):
        payload = _load_json(manifest_json)
        for task in payload.get("tasks", []) or []:
            if str(task.get("domain", "")).strip() != "kinase":
                continue
            metrics = dict(task.get("metrics", {}) or {})
            score_col = str(metrics.get("ranking_score_col_used", "")).strip() or str(
                task.get("ranking_score_col_used", "")
            ).strip()
            prob_col = str(metrics.get("ranking_probability_score_col_used", "")).strip() or str(
                task.get("ranking_probability_score_col_used", "")
            ).strip()
            rows.append(
                {
                    "row_kind": "current_package",
                    "artifact": str(manifest_json),
                    "profile_version": str(task.get("task_id", "")).strip() or manifest_json.stem,
                    "ranking_score_col": score_col or "missing",
                    "ranking_probability_score_col": prob_col,
                    "ml_live_ready": _score_is_ml_live(score_col),
                }
            )
    return rows


def _current_package_rows(package_root: Path) -> list[dict[str, Any]]:
    manifest_rows = _manifest_task_rows(package_root)
    if manifest_rows:
        return manifest_rows

    rows: list[dict[str, Any]] = []
    for summary_json in sorted(package_root.glob("set*/files/kinase/*_summary.json")):
        payload = _load_json(summary_json)
        score_col, prob_col = _extract_stage6_score_cols(payload)
        rows.append(
            {
                "row_kind": "current_package",
                "artifact": str(summary_json),
                "profile_version": summary_json.stem,
                "ranking_score_col": score_col or "missing",
                "ranking_probability_score_col": prob_col,
                "ml_live_ready": _score_is_ml_live(score_col),
            }
        )
    return rows


def build_payload(package_root: str) -> dict[str, Any]:
    profile_rows = _profile_rows()
    package_rows = _current_package_rows(_resolve_current_package_root(package_root))
    all_rows = profile_rows + package_rows

    profile_ready = sum(1 for row in profile_rows if row["ml_live_ready"])
    package_ready = sum(1 for row in package_rows if row["ml_live_ready"])
    profile_pct = round(100.0 * profile_ready / len(profile_rows), 1) if profile_rows else 0.0
    package_pct = round(100.0 * package_ready / len(package_rows), 1) if package_rows else 0.0
    overall_pct = round((0.7 * profile_pct) + (0.3 * package_pct), 1)

    summary = {
        "status": (
            "kinase_ml_live_ready"
            if profile_pct == 100.0 and package_pct == 100.0
            else "kinase_ml_forward_profiles_ready_current_rerun_pending"
            if profile_pct == 100.0
            else "kinase_ml_live_incomplete"
        ),
        "profile_count": len(profile_rows),
        "profile_ml_live_count": profile_ready,
        "profile_completion_percent": profile_pct,
        "current_package_task_count": len(package_rows),
        "current_package_ml_live_count": package_ready,
        "current_package_completion_percent": package_pct,
        "overall_completion_percent": overall_pct,
        "remaining_completion_percent": round(max(0.0, 100.0 - overall_pct), 1),
        "next_required_step": (
            "Regenerate the promoted current external-validation package so the preserved kinase summaries stop advertising proxy-only ranking."
            if profile_pct == 100.0 and package_pct < 100.0
            else "Patch the remaining kinase profiles to binding_score_composite_v7."
        ),
    }
    return {"summary": summary, "rows": all_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Kinase ML Live Status",
        "",
        f"- status: `{summary['status']}`",
        f"- profile_completion_percent: `{summary['profile_completion_percent']}`",
        f"- current_package_completion_percent: `{summary['current_package_completion_percent']}`",
        f"- overall_completion_percent: `{summary['overall_completion_percent']}`",
        f"- remaining_completion_percent: `{summary['remaining_completion_percent']}`",
        "",
        "| row_kind | ranking_score_col | ml_live_ready | artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []) or []:
        lines.append(
            f"| `{row['row_kind']}` | `{row['ranking_score_col']}` | `{row['ml_live_ready']}` | `{row['artifact']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit whether kinase live profiles and current artifacts are using ML/composite ranking.")
    parser.add_argument("--current-package-root", default=DEFAULT_CURRENT_PACKAGE_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.current_package_root)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload.get("rows", []) or [])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
