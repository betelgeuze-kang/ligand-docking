#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATERIALIZATION_JSON = "runs/casp16_ligand_materialization_manifest_current.json"
DEFAULT_SCORECARD_ROWS_CSV = "data/competition_benchmarks/casp16_ligand/scorecard_rows.csv"
DEFAULT_OUT_JSON = "runs/casp16_ligand_scorecard_current.json"
DEFAULT_OUT_CSV = "runs/casp16_ligand_scorecard_current.csv"
DEFAULT_OUT_MD = "runs/casp16_ligand_scorecard_current.md"

PACKET_TYPE = "casp16_ligand_scorecard"
SCHEMA_VERSION = "casp16_ligand_scorecard_v1"
REQUIRED_SCORECARD_COLUMNS = (
    "target_id",
    "task_type",
    "metric_name",
    "metric_value",
    "result_source",
)
ALLOWED_TASK_TYPES = {"pose", "affinity"}
ALLOWED_METRICS = {"LDDT-PLI", "Kendall_tau"}

CLAIM_BOUNDARY = (
    "CASP16 ligand scorecard receipt only; it validates operator-reviewed metric rows derived from "
    "the local materialization receipt. It does not download CASP data, run docking, compute pose or "
    "affinity metrics, submit predictions, promote ligand commercial claims, or mutate external state "
    "outside requested receipt outputs."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(k): _text(v) for k, v in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def _floatable(value: Any) -> bool:
    try:
        float(str(value))
    except (TypeError, ValueError):
        return False
    return True


def build_casp16_ligand_scorecard(
    *,
    materialization_json: str | Path = DEFAULT_MATERIALIZATION_JSON,
    scorecard_rows_csv: str | Path = DEFAULT_SCORECARD_ROWS_CSV,
    min_score_rows: int = 1,
    root: Path = ROOT,
) -> dict[str, Any]:
    materialization = _resolve(materialization_json, root=root)
    score_rows_path = _resolve(scorecard_rows_csv, root=root)
    materialization_summary = _summary(_read_json(materialization, root=root))
    materialization_status = _text(materialization_summary.get("status"))
    materialization_ready = materialization_status == "casp16_ligand_materialization_ready"
    score_rows, score_columns = _read_rows(score_rows_path)
    missing_columns = [
        column for column in REQUIRED_SCORECARD_COLUMNS if column not in score_columns
    ]
    missing_value_count = sum(
        1
        for row in score_rows
        for column in REQUIRED_SCORECARD_COLUMNS
        if not _text(row.get(column))
    )
    invalid_metric_value_count = sum(
        1 for row in score_rows if _text(row.get("metric_value")) and not _floatable(row.get("metric_value"))
    )
    invalid_task_type_count = sum(
        1
        for row in score_rows
        if _text(row.get("task_type")) and _text(row.get("task_type")).lower() not in ALLOWED_TASK_TYPES
    )
    unsupported_metric_count = sum(
        1
        for row in score_rows
        if _text(row.get("metric_name")) and _text(row.get("metric_name")) not in ALLOWED_METRICS
    )
    pose_row_count = sum(
        1
        for row in score_rows
        if _text(row.get("task_type")).lower() == "pose"
        or _text(row.get("metric_name")) == "LDDT-PLI"
    )
    affinity_row_count = sum(
        1
        for row in score_rows
        if _text(row.get("task_type")).lower() == "affinity"
        or _text(row.get("metric_name")) == "Kendall_tau"
    )

    blockers: list[str] = []
    if not materialization_summary:
        blockers.append("materialization_json_missing_or_invalid")
    elif not materialization_ready:
        blockers.append("materialization_not_ready")
    if not score_rows_path.is_file():
        blockers.append("scorecard_rows_csv_missing")
    if missing_columns:
        blockers.append("scorecard_required_columns_missing")
    if len(score_rows) < int(min_score_rows):
        blockers.append("scorecard_rows_below_minimum")
    if missing_value_count:
        blockers.append("scorecard_required_values_missing")
    if invalid_metric_value_count:
        blockers.append("scorecard_metric_values_not_numeric")
    if invalid_task_type_count:
        blockers.append("scorecard_task_type_unsupported")
    if unsupported_metric_count:
        blockers.append("scorecard_metric_name_unsupported")
    if pose_row_count + affinity_row_count <= 0:
        blockers.append("scorecard_pose_or_affinity_rows_missing")
    blockers = sorted(set(blockers))

    scorecard_ready = not blockers
    rows = [
        {
            "check": "materialization_ready",
            "status": "pass" if materialization_ready else "fail",
            "observed": materialization_status or _display(materialization, root=root),
            "required": "casp16_ligand_materialization_ready",
        },
        {
            "check": "scorecard_rows_csv_present",
            "status": "pass" if score_rows_path.is_file() else "fail",
            "observed": _display(score_rows_path, root=root),
            "required": "operator-reviewed metric rows CSV",
        },
        {
            "check": "scorecard_required_columns",
            "status": "pass" if not missing_columns else "fail",
            "observed": ";".join(score_columns),
            "required": ";".join(REQUIRED_SCORECARD_COLUMNS),
        },
        {
            "check": "scorecard_rows_minimum",
            "status": "pass" if len(score_rows) >= int(min_score_rows) else "fail",
            "observed": str(len(score_rows)),
            "required": str(int(min_score_rows)),
        },
        {
            "check": "metric_rows_supported",
            "status": "pass"
            if invalid_metric_value_count == 0
            and invalid_task_type_count == 0
            and unsupported_metric_count == 0
            else "fail",
            "observed": (
                f"invalid_values={invalid_metric_value_count};"
                f"invalid_task_types={invalid_task_type_count};"
                f"unsupported_metrics={unsupported_metric_count}"
            ),
            "required": "numeric LDDT-PLI or Kendall_tau rows for pose/affinity tasks",
        },
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "casp16_ligand_scorecard_ready"
        if scorecard_ready
        else "blocked_casp16_ligand_scorecard",
        "scorecard_ready": scorecard_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "materialization_json": _display(materialization, root=root),
        "materialization_status": materialization_status,
        "materialization_ready": materialization_ready,
        "scorecard_rows_csv": _display(score_rows_path, root=root),
        "scorecard_rows_csv_present": score_rows_path.is_file(),
        "scorecard_row_count": len(score_rows),
        "pose_row_count": pose_row_count,
        "affinity_row_count": affinity_row_count,
        "scorecard_columns": score_columns,
        "missing_required_columns": missing_columns,
        "missing_value_count": missing_value_count,
        "invalid_metric_value_count": invalid_metric_value_count,
        "invalid_task_type_count": invalid_task_type_count,
        "unsupported_metric_count": unsupported_metric_count,
        "competition_evidence_role": "competition_credibility_evidence_only",
        "commercial_ligand_claim_allowed": False,
        "download_executed": False,
        "docking_executed": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach this scorecard to the CASP16 ligand source manifest and Package B bridge."
            if scorecard_ready
            else "Attach reviewed CASP16 ligand metric rows after materialization is ready, then rebuild this receipt."
        ),
    }
    return {"summary": summary, "rows": rows, "scorecard_rows": score_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(REQUIRED_SCORECARD_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# CASP16 Ligand Scorecard",
        "",
        f"- status: `{summary['status']}`",
        f"- scorecard_ready: `{summary['scorecard_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- scorecard_row_count: `{summary['scorecard_row_count']}`",
        f"- pose_row_count: `{summary['pose_row_count']}`",
        f"- affinity_row_count: `{summary['affinity_row_count']}`",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    lines.extend(f"- `{blocker}`" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a CASP16 ligand scorecard receipt without running docking.")
    parser.add_argument("--materialization-json", default=DEFAULT_MATERIALIZATION_JSON)
    parser.add_argument("--scorecard-rows-csv", default=DEFAULT_SCORECARD_ROWS_CSV)
    parser.add_argument("--min-score-rows", default=1, type=int)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_casp16_ligand_scorecard(
        materialization_json=args.materialization_json,
        scorecard_rows_csv=args.scorecard_rows_csv,
        min_score_rows=args.min_score_rows,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["scorecard_rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
