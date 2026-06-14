#!/usr/bin/env python3
"""Read-only priority packet for R9 residual metric payload review."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESIDUAL_BOARD_JSON = "config/refine_tier_public_benchmark_residual_remediation_board_current.json"
DEFAULT_RESIDUAL_BOARD_CSV = "runs/refine_tier_public_benchmark_residual_remediation_board_current.csv"
DEFAULT_CANDIDATE_FILL_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.csv"
)
DEFAULT_OPERATOR_RECEIPT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.md"
METRIC_NAMES = ("dockq", "lddt_pli", "internal_deltaG")

CLAIM_BOUNDARY = (
    "R9 residual metric payload priority packet only joins existing residual, candidate-fill, and "
    "operator-receipt evidence to rank which DockQ, lDDT-PLI, and internal DeltaG payloads should be "
    "reviewed first. It does not compute metrics, write metric payload JSON, approve receipts, "
    "promote canonical intake, change production scoring, run docking/MD, download, upload, email, "
    "delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _read_csv(path_like: str | Path, *, root: Path) -> tuple[list[dict[str, str]], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): str(v) for k, v in row.items()} for row in csv.DictReader(handle)], True


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _metric_payload_paths(row: dict[str, str]) -> dict[str, str]:
    paths = _split_semicolon(row.get("required_reviewed_metric_payloads"))
    by_metric: dict[str, str] = {}
    for path in paths:
        for metric in METRIC_NAMES:
            if path.endswith(f"_{metric}.json"):
                by_metric[metric] = path
                break
    work_order_id = _text(row.get("work_order_id"))
    for metric in METRIC_NAMES:
        by_metric.setdefault(
            metric,
            f"runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_{metric}.json"
            if work_order_id
            else "",
        )
    return by_metric


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(row.get("suggested_work_order_id")),
        _text(row.get("target_id")),
        _text(row.get("pose_id")),
        _text(row.get("metric_name")),
    )


def _receipt_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(row.get("suggested_work_order_id")),
        _text(row.get("target_id")),
        _text(row.get("pose_id")),
        _text(row.get("metric_name")),
    )


def _artifact_present(path_like: str, *, root: Path) -> bool:
    if not path_like:
        return False
    if "::" in path_like:
        # Tar-member existence is verified upstream; this packet only checks local files.
        return False
    return _resolve(path_like, root=root).is_file()


def _read_metric_payload(path_like: str, *, root: Path) -> dict[str, Any]:
    payload, present = _read_json(path_like, root=root)
    if not present:
        return {}
    return payload


def _review_priority_class(residual: dict[str, str], receipt_missing: bool) -> str:
    if _bool(residual.get("leave_one_out_leverage")):
        return "residual_leverage_metric_payload_first"
    if _text(residual.get("cv_rank_error_vs_baseline")) == "worse":
        return "generalization_regression_metric_payload_first"
    if receipt_missing:
        return "existing_materialized_receipt_gap_first"
    direction = _text(residual.get("rank_direction"))
    if direction.startswith("overranked"):
        return "overbinding_metric_payload_review"
    if direction.startswith("underranked"):
        return "underbinding_metric_payload_review"
    return "metric_payload_review"


def _operator_gap_class(
    *,
    candidate: dict[str, str] | None,
    receipt: dict[str, str] | None,
    artifact_present: bool,
) -> str:
    if receipt is not None:
        status = _text(receipt.get("row_status"))
        if status == "pass":
            return "operator_receipt_passed"
        return "operator_receipt_blocked_placeholders"
    if artifact_present:
        return "existing_metric_payload_present_without_operator_receipt"
    if candidate is not None:
        return "candidate_value_present_payload_artifact_missing"
    return "missing_candidate_fill_and_operator_receipt"


def _next_operator_step(gap_class: str) -> str:
    if gap_class == "operator_receipt_blocked_placeholders":
        return "Fill metric value/method/review/license/operator fields in the current operator receipt row."
    if gap_class == "existing_metric_payload_present_without_operator_receipt":
        return "Create or extend an operator receipt row for the existing seeded metric payload before treating it as reviewed evidence."
    if gap_class == "candidate_value_present_payload_artifact_missing":
        return "Materialize and review the candidate metric source payload JSON, then fill the operator receipt row."
    if gap_class == "operator_receipt_passed":
        return "Rerun candidate fill, cross-validation, and bootstrap gates after all paired residual payloads are reviewed."
    return "Generate candidate metric source payload and operator receipt coverage before calibration reuse."


def build_refine_tier_public_benchmark_residual_metric_payload_priority_packet(
    *,
    residual_board_json: str | Path = DEFAULT_RESIDUAL_BOARD_JSON,
    residual_board_csv: str | Path = DEFAULT_RESIDUAL_BOARD_CSV,
    candidate_fill_csv: str | Path = DEFAULT_CANDIDATE_FILL_CSV,
    operator_receipt_csv: str | Path = DEFAULT_OPERATOR_RECEIPT_CSV,
    root: str | Path = ROOT,
    top_n_residuals: int = 12,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    board_payload, board_json_present = _read_json(residual_board_json, root=root_path)
    board_summary = board_payload.get("summary") if isinstance(board_payload.get("summary"), dict) else {}
    residual_rows, board_csv_present = _read_csv(residual_board_csv, root=root_path)
    candidate_rows, candidate_csv_present = _read_csv(candidate_fill_csv, root=root_path)
    receipt_rows, receipt_csv_present = _read_csv(operator_receipt_csv, root=root_path)
    candidate_by_key = {_candidate_key(row): row for row in candidate_rows}
    receipt_by_key = {_receipt_key(row): row for row in receipt_rows}

    selected_residuals = residual_rows[:top_n_residuals] if top_n_residuals > 0 else residual_rows
    priority_rows: list[dict[str, Any]] = []
    for residual in selected_residuals:
        paths_by_metric = _metric_payload_paths(residual)
        for metric in METRIC_NAMES:
            key = (
                _text(residual.get("work_order_id")),
                _text(residual.get("target_id")),
                _text(residual.get("pose_id")),
                metric,
            )
            candidate = candidate_by_key.get(key)
            receipt = receipt_by_key.get(key)
            expected_artifact = (
                _text(candidate.get("expected_metric_source_artifact"))
                if candidate is not None
                else _text(receipt.get("metric_source_artifact")) if receipt is not None else paths_by_metric.get(metric, "")
            )
            artifact_present = _artifact_present(expected_artifact, root=root_path)
            existing_payload = _read_metric_payload(expected_artifact, root=root_path) if artifact_present else {}
            gap_class = _operator_gap_class(
                candidate=candidate,
                receipt=receipt,
                artifact_present=artifact_present,
            )
            manual_pending_count = _int(receipt.get("operator_manual_pending_field_count")) if receipt else 0
            row = {
                "payload_priority_rank": len(priority_rows) + 1,
                "residual_priority_rank": _int(residual.get("priority_rank")),
                "target_id": _text(residual.get("target_id")),
                "pose_id": _text(residual.get("pose_id")),
                "work_order_id": _text(residual.get("work_order_id")),
                "split": _text(residual.get("split")),
                "residual_source": _text(residual.get("source")),
                "metric_name": metric,
                "review_priority_class": _review_priority_class(residual, receipt_missing=receipt is None),
                "operator_gap_class": gap_class,
                "primary_action": _text(residual.get("primary_action")),
                "rank_direction": _text(residual.get("rank_direction")),
                "cv_rank_error_vs_baseline": _text(residual.get("cv_rank_error_vs_baseline")),
                "locked_cv_rank_abs_error": _text(residual.get("locked_cv_rank_abs_error")),
                "baseline_rank_abs_error": _text(residual.get("baseline_rank_abs_error")),
                "leave_one_out_leverage": _bool(residual.get("leave_one_out_leverage")),
                "leave_one_out_bootstrap_p05_delta": _text(residual.get("leave_one_out_bootstrap_p05_delta")),
                "contact_per_atom": _text(residual.get("contact_per_atom")),
                "pose_atom_count": _text(residual.get("pose_atom_count")),
                "template_id": _text(candidate.get("template_id")) if candidate else _text(receipt.get("template_id")) if receipt else "",
                "candidate_queue_id": _text(candidate.get("candidate_queue_id")) if candidate else _text(receipt.get("candidate_queue_id")) if receipt else "",
                "metric_value_candidate": _text(candidate.get("metric_value_candidate")) if candidate else "",
                "method_candidate": _text(candidate.get("method_candidate")) if candidate else "",
                "existing_metric_value": _text(existing_payload.get("value")),
                "existing_metric_method": _text(existing_payload.get("method")),
                "metric_source_artifact": expected_artifact,
                "metric_source_artifact_present": artifact_present,
                "expected_metric_source_artifact_present_candidate": (
                    _bool(candidate.get("expected_metric_source_artifact_present")) if candidate else False
                ),
                "required_metric_input_artifacts": (
                    _text(receipt.get("required_metric_input_artifacts"))
                    if receipt
                    else _text(candidate.get("required_metric_input_artifacts")) if candidate else ";".join(existing_payload.get("input_artifacts", []) or [])
                ),
                "required_metric_input_artifact_sha256s": (
                    _text(receipt.get("required_metric_input_artifact_sha256s"))
                    if receipt
                    else _text(candidate.get("candidate_input_artifact_sha256s")) if candidate else ";".join(existing_payload.get("input_artifact_sha256s", []) or [])
                ),
                "candidate_input_artifact_sha256s_complete": (
                    _bool(candidate.get("candidate_input_artifact_sha256s_complete")) if candidate else bool(existing_payload)
                ),
                "operator_receipt_row_status": _text(receipt.get("row_status")) if receipt else "missing",
                "operator_receipt_blockers": _text(receipt.get("blockers")) if receipt else "operator_receipt_row_missing",
                "operator_review_surface_ready": _bool(receipt.get("operator_review_surface_ready")) if receipt else False,
                "operator_manual_pending_fields": _text(receipt.get("operator_manual_pending_fields")) if receipt else "operator_receipt_row_missing",
                "operator_manual_pending_field_count": manual_pending_count,
                "metric_source_template_row_fingerprint_verified": (
                    _bool(receipt.get("metric_source_template_row_fingerprint_verified")) if receipt else False
                ),
                "approval_token_required": APPROVAL_TOKEN,
                "next_operator_step": _next_operator_step(gap_class),
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
            priority_rows.append(row)

    candidate_matched = [row for row in priority_rows if row["metric_value_candidate"]]
    receipt_matched = [row for row in priority_rows if row["operator_receipt_row_status"] != "missing"]
    operator_blocked = [row for row in receipt_matched if row["operator_receipt_row_status"] == "blocked"]
    receipt_missing = [row for row in priority_rows if row["operator_receipt_row_status"] == "missing"]
    existing_without_receipt = [
        row
        for row in priority_rows
        if row["operator_gap_class"] == "existing_metric_payload_present_without_operator_receipt"
    ]
    summary = {
        "packet_type": "refine_tier_public_benchmark_residual_metric_payload_priority_packet",
        "status": (
            "refine_tier_public_benchmark_residual_metric_payload_priority_packet_ready"
            if board_csv_present and priority_rows
            else "blocked_refine_tier_public_benchmark_residual_metric_payload_priority_packet"
        ),
        "residual_board_json": _display(residual_board_json, root=root_path),
        "residual_board_json_present": board_json_present,
        "residual_board_csv": _display(residual_board_csv, root=root_path),
        "residual_board_csv_present": board_csv_present,
        "candidate_fill_csv": _display(candidate_fill_csv, root=root_path),
        "candidate_fill_csv_present": candidate_csv_present,
        "operator_receipt_csv": _display(operator_receipt_csv, root=root_path),
        "operator_receipt_csv_present": receipt_csv_present,
        "locked_cv_model_id": board_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": board_summary.get("locked_cv_bootstrap_p05"),
        "locked_cv_bootstrap_p05_gap_to_claim_grade": board_summary.get(
            "locked_cv_bootstrap_p05_gap_to_claim_grade"
        ),
        "selected_residual_action_row_count": len(selected_residuals),
        "metric_payload_priority_row_count": len(priority_rows),
        "candidate_fill_matched_payload_count": len(candidate_matched),
        "operator_receipt_matched_payload_count": len(receipt_matched),
        "operator_receipt_missing_payload_count": len(receipt_missing),
        "operator_receipt_blocked_payload_count": len(operator_blocked),
        "existing_metric_source_artifact_present_without_receipt_count": len(existing_without_receipt),
        "metric_source_artifact_present_count": sum(1 for row in priority_rows if row["metric_source_artifact_present"]),
        "operator_manual_pending_field_count": sum(_int(row["operator_manual_pending_field_count"]) for row in priority_rows),
        "residual_leverage_payload_count": sum(1 for row in priority_rows if row["leave_one_out_leverage"]),
        "cv_worse_payload_count": sum(
            1 for row in priority_rows if row["cv_rank_error_vs_baseline"] == "worse"
        ),
        "top_priority_target_id": priority_rows[0]["target_id"] if priority_rows else "",
        "top_priority_pose_id": priority_rows[0]["pose_id"] if priority_rows else "",
        "top_priority_metric_name": priority_rows[0]["metric_name"] if priority_rows else "",
        "first_missing_receipt_target_id": receipt_missing[0]["target_id"] if receipt_missing else "",
        "first_missing_receipt_pose_id": receipt_missing[0]["pose_id"] if receipt_missing else "",
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review the prioritized DockQ/lDDT-PLI/internal_deltaG payload rows, add missing seeded-payload "
            "operator receipt coverage, then rerun candidate fill, cross-validation, and bootstrap gates."
        ),
    }
    return {"summary": summary, "priority_rows": priority_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Residual Metric Payload Priority Packet",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- selected_residual_action_row_count: `{s['selected_residual_action_row_count']}`",
        f"- metric_payload_priority_row_count: `{s['metric_payload_priority_row_count']}`",
        f"- candidate_fill_matched_payload_count: `{s['candidate_fill_matched_payload_count']}`",
        f"- operator_receipt_matched_payload_count: `{s['operator_receipt_matched_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- existing_metric_source_artifact_present_without_receipt_count: `{s['existing_metric_source_artifact_present_without_receipt_count']}`",
        f"- operator_manual_pending_field_count: `{s['operator_manual_pending_field_count']}`",
        f"- residual_leverage_payload_count: `{s['residual_leverage_payload_count']}`",
        f"- cv_worse_payload_count: `{s['cv_worse_payload_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Priority Payloads",
        "",
        "| rank | residual | target | pose | metric | priority | gap | receipt | artifact |",
        "| ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["priority_rows"][:36]:
        lines.append(
            f"| `{row['payload_priority_rank']}` | `{row['residual_priority_rank']}` | "
            f"`{row['target_id']}` | `{row['pose_id']}` | `{row['metric_name']}` | "
            f"`{row['review_priority_class']}` | `{row['operator_gap_class']}` | "
            f"`{row['operator_receipt_row_status']}` | `{row['metric_source_artifact_present']}` |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an R9 residual metric payload priority packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--residual-board-json", default=DEFAULT_RESIDUAL_BOARD_JSON)
    parser.add_argument("--residual-board-csv", default=DEFAULT_RESIDUAL_BOARD_CSV)
    parser.add_argument("--candidate-fill-csv", default=DEFAULT_CANDIDATE_FILL_CSV)
    parser.add_argument("--operator-receipt-csv", default=DEFAULT_OPERATOR_RECEIPT_CSV)
    parser.add_argument("--top-n-residuals", type=int, default=12)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_residual_metric_payload_priority_packet(
        root=root,
        residual_board_json=args.residual_board_json,
        residual_board_csv=args.residual_board_csv,
        candidate_fill_csv=args.candidate_fill_csv,
        operator_receipt_csv=args.operator_receipt_csv,
        top_n_residuals=args.top_n_residuals,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["priority_rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
