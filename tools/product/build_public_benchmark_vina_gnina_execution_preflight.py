#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any

from tools.product.build_public_benchmark_vina_gnina_comparison_work_order import (
    APPROVAL_TOKEN,
    CSV_FIELDS as SCORE_TEMPLATE_FIELDS,
)


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RESULTS_JSON = "runs/pdbbind_casf_pose_affinity_results_current.json"
DEFAULT_WORK_ORDER_JSON = "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
DEFAULT_SCORE_TEMPLATE_CSV = "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
DEFAULT_OUT_JSON = "runs/public_benchmark_vina_gnina_execution_preflight_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_vina_gnina_execution_preflight_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_vina_gnina_execution_preflight_current.md"

PACKET_TYPE = "public_benchmark_vina_gnina_execution_preflight"
SCHEMA_VERSION = "public_benchmark_vina_gnina_execution_preflight_v1"

CLAIM_BOUNDARY = (
    "Public benchmark Vina/GNINA execution preflight only; it freezes the same-input score-template rows, "
    "checks whether local Vina/GNINA binaries are discoverable, and emits operator runbook rows for local "
    "same-input scoring. It does not run Vina, run GNINA, run docking, download datasets, write score values, "
    "approve receipts, promote claims, upload, email, deploy, or mutate external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "docking_results_emitted": False,
    "claim_promotion_allowed": False,
    "score_template_write_allowed": False,
}

CSV_FIELDS = [
    "pose_id",
    "complex_id",
    "pose_artifact_path",
    "pose_artifact_sha256",
    "score_template_row_present",
    "score_template_pending_fields",
    "vina_binary_present",
    "gnina_binary_present",
    "ready_for_local_same_input_scoring",
    "required_action",
    "approval_token_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(str(path_like))
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _read_csv_rows(path_like: str | Path, *, root: Path = ROOT) -> tuple[bool, list[str], list[dict[str, Any]]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return False, [], []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return True, list(reader.fieldnames or []), [dict(row) for row in reader]


def _is_executable(path_like: str | Path) -> bool:
    if not _text(path_like):
        return False
    path = Path(str(path_like))
    return path.is_file() and os.access(path, os.X_OK)


def _engine_path(engine_name: str, explicit_path: str | Path | None) -> str:
    if explicit_path is not None and _text(explicit_path):
        return str(explicit_path)
    return shutil.which(engine_name) or ""


def _pose_artifacts(results_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = _summary(results_payload)
    subset_identity = results.get("subset_identity")
    if not isinstance(subset_identity, dict):
        return {}
    rows = subset_identity.get("artifact_rows")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or _text(row.get("role")) != "pose":
            continue
        name = _text(row.get("name"))
        if not name:
            continue
        out[name] = {
            "pose_artifact_path": _text(row.get("relative_path")),
            "pose_artifact_sha256": _text(row.get("sha256")),
        }
    return out


def _pending_fields(row: dict[str, Any], fieldnames: list[str]) -> list[str]:
    pending: list[str] = []
    for field in SCORE_TEMPLATE_FIELDS:
        if field not in fieldnames:
            pending.append(field)
            continue
        value = _text(row.get(field))
        if not value or value.startswith("OPERATOR_FILL_"):
            pending.append(field)
    return pending


def _row(
    *,
    template_row: dict[str, Any],
    fieldnames: list[str],
    pose_artifacts: dict[str, dict[str, Any]],
    vina_present: bool,
    gnina_present: bool,
) -> dict[str, Any]:
    pose_id = _text(template_row.get("pose_id"))
    artifact = pose_artifacts.get(pose_id, {})
    pending_fields = _pending_fields(template_row, fieldnames)
    engines_ready = bool(vina_present and gnina_present)
    row_present = bool(pose_id)
    ready_for_scoring = bool(row_present and engines_ready)
    if not engines_ready:
        required_action = "install_or_expose_local_vina_and_gnina_binaries_before_same_input_scoring"
    elif pending_fields:
        required_action = "run_local_same_input_scoring_and_fill_score_template_receipt_fields"
    else:
        required_action = "rerun_score_template_receipt_and_external_receipts_audit"
    return {
        "pose_id": pose_id,
        "complex_id": _text(template_row.get("complex_id")),
        "pose_artifact_path": _text(artifact.get("pose_artifact_path")),
        "pose_artifact_sha256": _text(artifact.get("pose_artifact_sha256")),
        "score_template_row_present": row_present,
        "score_template_pending_fields": pending_fields,
        "vina_binary_present": vina_present,
        "gnina_binary_present": gnina_present,
        "ready_for_local_same_input_scoring": ready_for_scoring,
        "required_action": required_action,
        "approval_token_required": APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        **READ_ONLY_FLAGS,
    }


def build_public_benchmark_vina_gnina_execution_preflight(
    *,
    results_json: str | Path = DEFAULT_RESULTS_JSON,
    work_order_json: str | Path = DEFAULT_WORK_ORDER_JSON,
    score_template_csv: str | Path = DEFAULT_SCORE_TEMPLATE_CSV,
    vina_bin: str | Path | None = None,
    gnina_bin: str | Path | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    results_payload = _read_json(results_json, root=root)
    work_order_summary = _summary(_read_json(work_order_json, root=root))
    template_present, fieldnames, template_rows = _read_csv_rows(score_template_csv, root=root)
    vina_path = _engine_path("vina", vina_bin)
    gnina_path = _engine_path("gnina", gnina_bin)
    vina_present = _is_executable(vina_path)
    gnina_present = _is_executable(gnina_path)
    artifacts_by_pose = _pose_artifacts(results_payload)
    rows = [
        _row(
            template_row=row,
            fieldnames=fieldnames,
            pose_artifacts=artifacts_by_pose,
            vina_present=vina_present,
            gnina_present=gnina_present,
        )
        for row in template_rows
    ]

    work_order_ready = _bool(work_order_summary.get("work_order_ready"))
    expected_row_count = int(work_order_summary.get("pose_row_count", 0) or 0)
    row_count_match = bool(expected_row_count == 0 or expected_row_count == len(template_rows))
    missing_columns = [field for field in SCORE_TEMPLATE_FIELDS if field not in fieldnames]
    ready_row_count = sum(1 for row in rows if row["ready_for_local_same_input_scoring"])
    pending_field_counts: dict[str, int] = {}
    for row in rows:
        for field in row["score_template_pending_fields"]:
            pending_field_counts[field] = pending_field_counts.get(field, 0) + 1

    blockers: list[str] = []
    if not work_order_ready:
        blockers.append("comparison_work_order_not_ready")
    if not template_present:
        blockers.append("score_template_missing")
    if missing_columns:
        blockers.append("score_template_required_columns_missing")
    if not row_count_match:
        blockers.append("score_template_row_count_mismatch")
    if not vina_present:
        blockers.append("vina_binary_missing")
    if not gnina_present:
        blockers.append("gnina_binary_missing")
    if not rows:
        blockers.append("same_input_score_rows_missing")

    preflight_ready = bool(
        work_order_ready
        and template_present
        and rows
        and row_count_match
        and not missing_columns
        and vina_present
        and gnina_present
    )
    status = (
        "public_benchmark_vina_gnina_execution_preflight_ready"
        if preflight_ready
        else "blocked_public_benchmark_vina_gnina_execution_preflight"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "execution_preflight_ready": preflight_ready,
        "work_order_json": _display(work_order_json, root=root),
        "work_order_ready": work_order_ready,
        "results_json": _display(results_json, root=root),
        "score_template_csv": _display(score_template_csv, root=root),
        "score_template_present": template_present,
        "score_template_row_count": len(template_rows),
        "expected_row_count": expected_row_count,
        "score_template_row_count_match": row_count_match,
        "score_template_missing_column_count": len(missing_columns),
        "score_template_missing_columns": missing_columns,
        "score_template_pending_field_count": sum(pending_field_counts.values()),
        "score_template_pending_field_counts": dict(sorted(pending_field_counts.items())),
        "ready_for_local_same_input_scoring_row_count": ready_row_count,
        "blocked_for_local_same_input_scoring_row_count": len(rows) - ready_row_count,
        "vina_binary": _display(vina_path, root=root) if vina_path else "",
        "gnina_binary": _display(gnina_path, root=root) if gnina_path else "",
        "vina_binary_present": vina_present,
        "gnina_binary_present": gnina_present,
        "required_engine_ids": ["vina", "gnina"],
        "approval_token_required": APPROVAL_TOKEN,
        "adapter_command_after_fill": _text(work_order_summary.get("adapter_command_after_fill")),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_required_step": (
            "Run local same-input Vina/GNINA scoring for the frozen rows, fill the score template, then rerun the score-template receipt."
            if preflight_ready
            else "Install or expose local Vina and GNINA binaries, keep the frozen score-template rows unchanged, then rerun this preflight before scoring."
            if (not vina_present or not gnina_present)
            else "Restore the frozen work order and score template before local same-input scoring."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _fmt(row.get(field)) for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Public Benchmark Vina/GNINA Execution Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- execution_preflight_ready: `{str(summary['execution_preflight_ready']).lower()}`",
        f"- score_template_row_count: `{summary['score_template_row_count']}`",
        f"- ready_for_local_same_input_scoring_row_count: `{summary['ready_for_local_same_input_scoring_row_count']}`",
        f"- blocked_for_local_same_input_scoring_row_count: `{summary['blocked_for_local_same_input_scoring_row_count']}`",
        f"- vina_binary_present: `{str(summary['vina_binary_present']).lower()}`",
        f"- gnina_binary_present: `{str(summary['gnina_binary_present']).lower()}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| pose | complex | ready | required action | pending fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{pose}` | `{complex}` | `{ready}` | `{action}` | `{pending}` |".format(
                pose=row["pose_id"],
                complex=row["complex_id"],
                ready=str(row["ready_for_local_same_input_scoring"]).lower(),
                action=row["required_action"],
                pending=", ".join(row["score_template_pending_fields"]) or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Vina/GNINA same-input execution preflight.")
    parser.add_argument("--results-json", default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--score-template-csv", default=DEFAULT_SCORE_TEMPLATE_CSV)
    parser.add_argument("--vina-bin", default=None)
    parser.add_argument("--gnina-bin", default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_public_benchmark_vina_gnina_execution_preflight(
        results_json=args.results_json,
        work_order_json=args.work_order_json,
        score_template_csv=args.score_template_csv,
        vina_bin=args.vina_bin,
        gnina_bin=args.gnina_bin,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
