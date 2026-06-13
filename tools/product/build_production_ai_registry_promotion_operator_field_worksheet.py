#!/usr/bin/env python3
"""Field-level worksheet for guarded production AI registry promotion intake."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_production_ai_registry_promotion_operator_receipt import (
    APPROVAL_TOKEN,
    ARTIFACT_ID,
    DEFAULT_CHECKPOINT_READINESS_JSON,
    DEFAULT_RECEIPT_CSV,
    DEFAULT_REGISTRY_JSON,
    GUARDED_MODES,
    PLACEHOLDER_PREFIXES,
    REQUIRED_COLUMNS,
)
from tools.product.build_production_ai_registry_promotion_priority_packet import (
    DEFAULT_OPERATOR_RECEIPT_JSON,
    DEFAULT_OUT_JSON as DEFAULT_PRIORITY_PACKET_JSON,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/production_ai_registry_promotion_operator_field_worksheet_current.json"
DEFAULT_OUT_CSV = "runs/production_ai_registry_promotion_operator_field_worksheet_current.csv"
DEFAULT_OUT_MD = "runs/production_ai_registry_promotion_operator_field_worksheet_current.md"

DIAGNOSTIC_REQUIRED_FIELDS = {
    "production_promotion_allowed",
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
    "default_residual_mode",
    "trained_model_checkpoint_count",
}
TRUE_REVIEW_FIELDS = {
    "production_promotion_allowed",
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
    "validation_chain_reviewed",
    "claim_boundary_reviewed",
    "customer_facing_mutation_policy_reviewed",
}
REVIEW_METADATA_FIELDS = {
    "operator_decision",
    "reviewer",
    "reviewed_at_utc",
    "approval_token",
}
CLAIM_BOUNDARY = (
    "Production AI registry promotion operator field worksheet only; it expands the guarded promotion "
    "receipt template into field-level operator inputs. It does not edit the registry, create checkpoints, "
    "enable customer-facing mutation, promote models, run GPU jobs, deploy, upload, email, delete, commit, "
    "push, or mutate external state."
)

FIELD_ACTIONS: dict[str, str] = {
    "artifact_id": "Keep residual_model_registry_guarded_promotion.",
    "operator_decision": "Set promote_guarded only after every registry promotion gate is reviewed; otherwise keep hold.",
    "registry_artifact": "Keep the current residual registry artifact path.",
    "checkpoint_readiness_artifact": "Keep the current checkpoint-readiness artifact path.",
    "production_promotion_allowed": "Confirm true only after guarded registry promotion policy review.",
    "customer_facing_auto_correction_allowed": "Confirm true only after customer-facing auto-correction mutation policy review.",
    "customer_facing_score_mutation_allowed": "Confirm true only after customer-facing score mutation policy review.",
    "customer_facing_ranking_mutation_allowed": "Confirm true only after customer-facing ranking mutation policy review.",
    "default_residual_mode": "Select assist, production, or production_guarded; do not leave shadow for promotion.",
    "trained_model_checkpoint_count": "Copy the positive trained checkpoint count observed in the registry/checkpoint readiness artifacts.",
    "registry_validation_command": "Keep a command that rebuilds registry, checkpoint readiness, and promotion workbench gates.",
    "validation_chain_reviewed": "Confirm true after rerunning and reviewing the validation chain.",
    "claim_boundary_reviewed": "Confirm true after checking restricted-claim boundaries remain fail-closed.",
    "customer_facing_mutation_policy_reviewed": "Confirm true after customer-facing mutation policy is reviewed.",
    "reviewer": "Record the human/operator reviewer.",
    "reviewed_at_utc": "Record an ISO-8601 UTC review timestamp.",
    "approval_token": f"Use {APPROVAL_TOKEN} only for an approved guarded promotion review.",
    "external_state_mutated": "Keep false; this worksheet must never mutate external state.",
    "operator_attestation": "Keep reviewed_for_production_ai_registry_promotion.",
    "notes": "Record any operator caveat without changing promotion state.",
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], list(REQUIRED_COLUMNS), False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    return rows, missing_columns, True


def _receipt_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if _text(row.get("artifact_id")) == ARTIFACT_ID:
            return row
    return rows[0] if rows else {}


def _observed_value(
    field_name: str,
    *,
    registry_summary: dict[str, Any],
    checkpoint_summary: dict[str, Any],
) -> str:
    if field_name in DIAGNOSTIC_REQUIRED_FIELDS:
        value = registry_summary.get(field_name)
        if value in (None, ""):
            value = checkpoint_summary.get(field_name)
        return _text(value)
    return ""


def _expected_value(field_name: str, *, registry_summary: dict[str, Any]) -> str:
    if field_name == "artifact_id":
        return ARTIFACT_ID
    if field_name == "operator_decision":
        return "promote_guarded or hold"
    if field_name == "registry_artifact":
        return DEFAULT_REGISTRY_JSON
    if field_name == "checkpoint_readiness_artifact":
        return DEFAULT_CHECKPOINT_READINESS_JSON
    if field_name in TRUE_REVIEW_FIELDS:
        return "true"
    if field_name == "default_residual_mode":
        return "assist, production, or production_guarded"
    if field_name == "trained_model_checkpoint_count":
        return str(_int(registry_summary.get("trained_model_checkpoint_count")))
    if field_name == "registry_validation_command":
        return "rebuild registry, checkpoint-readiness, and promotion-workbench gates"
    if field_name == "reviewer":
        return "non-empty operator reviewer"
    if field_name == "reviewed_at_utc":
        return "ISO-8601 UTC timestamp"
    if field_name == "approval_token":
        return APPROVAL_TOKEN
    if field_name == "external_state_mutated":
        return "false"
    if field_name == "operator_attestation":
        return "reviewed_for_production_ai_registry_promotion"
    return ""


def _gate_id(field_name: str) -> str:
    if field_name == "trained_model_checkpoint_count":
        return "trained_model_checkpoint_count_positive"
    if field_name == "default_residual_mode":
        return "default_residual_mode_guarded"
    if field_name == "production_promotion_allowed":
        return "production_promotion_allowed"
    if field_name.startswith("customer_facing_") or field_name == "customer_facing_mutation_policy_reviewed":
        return "customer_facing_mutation_flags"
    if field_name in {"operator_decision", "approval_token", "reviewer", "reviewed_at_utc"}:
        return "operator_receipt_review"
    if field_name in {"validation_chain_reviewed", "registry_validation_command"}:
        return "validation_chain_review"
    if field_name == "claim_boundary_reviewed":
        return "claim_boundary_review"
    return ""


def _field_status(field_name: str, value: Any, *, registry_summary: dict[str, Any]) -> tuple[str, str]:
    text = _text(value)
    if _has_placeholder(value):
        if field_name == "notes":
            return "informational", ""
        return "operator_fill_pending", "operator_placeholder_or_empty"
    if field_name == "artifact_id":
        return ("ready", "") if text == ARTIFACT_ID else ("invalid", "artifact_id_mismatch")
    if field_name == "operator_decision":
        return ("ready", "") if text in {"promote_guarded", "hold"} else ("invalid", "operator_decision_invalid")
    if field_name == "registry_artifact":
        return ("ready", "") if text == DEFAULT_REGISTRY_JSON else ("invalid", "registry_artifact_path_mismatch")
    if field_name == "checkpoint_readiness_artifact":
        return (
            ("ready", "")
            if text == DEFAULT_CHECKPOINT_READINESS_JSON
            else ("invalid", "checkpoint_readiness_artifact_path_mismatch")
        )
    if field_name in TRUE_REVIEW_FIELDS:
        return ("ready", "") if _bool_text(value) else ("invalid", f"{field_name}_not_true")
    if field_name == "default_residual_mode":
        if text not in GUARDED_MODES:
            return "invalid", "default_residual_mode_not_guarded"
        if text != _text(registry_summary.get("default_residual_mode")):
            return "invalid", "registry_default_residual_mode_mismatch"
        return "ready", ""
    if field_name == "trained_model_checkpoint_count":
        if _int(value) <= 0:
            return "invalid", "trained_model_checkpoint_count_not_positive"
        if _int(value) != _int(registry_summary.get("trained_model_checkpoint_count")):
            return "invalid", "registry_trained_model_checkpoint_count_mismatch"
        return "ready", ""
    if field_name == "reviewed_at_utc":
        return ("ready", "") if _is_iso_timestamp(value) else ("invalid", "reviewed_at_utc_missing_or_invalid")
    if field_name == "approval_token":
        return ("ready", "") if text == APPROVAL_TOKEN else ("invalid", "approval_token_missing_or_invalid")
    if field_name == "external_state_mutated":
        return ("ready", "") if _bool_text(value) is False else ("invalid", "external_state_mutated_present")
    if field_name == "operator_attestation":
        return (
            ("ready", "")
            if text == "reviewed_for_production_ai_registry_promotion"
            else ("invalid", "operator_attestation_missing_or_unaccepted")
        )
    if field_name == "notes":
        return "informational", ""
    return ("ready", "") if text else ("operator_fill_pending", "operator_placeholder_or_empty")


def _field_row(
    field_name: str,
    *,
    column_present: bool,
    receipt_row: dict[str, str],
    registry_summary: dict[str, Any],
    checkpoint_summary: dict[str, Any],
    priority_summary: dict[str, Any],
) -> dict[str, Any]:
    value = receipt_row.get(field_name, "")
    status, blocker = (
        _field_status(field_name, value, registry_summary=registry_summary)
        if column_present
        else ("missing_column", "receipt_column_missing")
    )
    diagnostic_required = field_name in DIAGNOSTIC_REQUIRED_FIELDS
    operator_input_required = status == "operator_fill_pending"
    return {
        "field_name": field_name,
        "gate_id": _gate_id(field_name),
        "receipt_column_present": column_present,
        "required_for_operator_receipt": field_name != "notes",
        "diagnostic_required_field": diagnostic_required,
        "current_receipt_value": _text(value),
        "observed_registry_value": _observed_value(
            field_name,
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
        ),
        "expected_value_hint": _expected_value(field_name, registry_summary=registry_summary),
        "field_status": status,
        "blocker": blocker,
        "operator_input_required": operator_input_required,
        "top_priority_gate": _text(priority_summary.get("top_gate_id")),
        "operator_action": FIELD_ACTIONS.get(field_name, ""),
        "model_promoted": False,
        "customer_facing_mutation_enabled": False,
        "external_state_mutated": False,
    }


def build_production_ai_registry_promotion_operator_field_worksheet(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    operator_receipt_json: str | Path = DEFAULT_OPERATOR_RECEIPT_JSON,
    registry_json: str | Path = DEFAULT_REGISTRY_JSON,
    checkpoint_readiness_json: str | Path = DEFAULT_CHECKPOINT_READINESS_JSON,
    priority_packet_json: str | Path = DEFAULT_PRIORITY_PACKET_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    receipt_rows, missing_columns, receipt_csv_present = _read_csv(receipt_csv, root=root_path)
    operator_receipt_packet, operator_receipt_present = _read_json(
        operator_receipt_json,
        root=root_path,
    )
    registry_packet, registry_present = _read_json(registry_json, root=root_path)
    checkpoint_packet, checkpoint_present = _read_json(checkpoint_readiness_json, root=root_path)
    priority_packet, priority_present = _read_json(priority_packet_json, root=root_path)
    operator_receipt_summary = _summary(operator_receipt_packet)
    registry_summary = _summary(registry_packet)
    checkpoint_summary = _summary(checkpoint_packet)
    priority_summary = _summary(priority_packet)
    row = _receipt_row(receipt_rows)
    worksheet_rows = [
        _field_row(
            field_name,
            column_present=field_name not in missing_columns,
            receipt_row=row,
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
            priority_summary=priority_summary,
        )
        for field_name in REQUIRED_COLUMNS
    ]
    pending_rows = [row for row in worksheet_rows if row["field_status"] == "operator_fill_pending"]
    invalid_rows = [row for row in worksheet_rows if row["field_status"] in {"invalid", "missing_column"}]
    diagnostic_pending = [
        row for row in pending_rows if row.get("diagnostic_required_field") is True
    ]
    source_blockers: list[str] = []
    if not receipt_csv_present:
        source_blockers.append("receipt_csv_missing")
    if missing_columns:
        source_blockers.append("receipt_columns_missing")
    if not receipt_rows:
        source_blockers.append("receipt_row_missing")
    if not operator_receipt_present:
        source_blockers.append("operator_receipt_artifact_missing")
    if not registry_present:
        source_blockers.append("residual_registry_artifact_missing")
    if not checkpoint_present:
        source_blockers.append("checkpoint_readiness_artifact_missing")
    if not priority_present:
        source_blockers.append("priority_packet_artifact_missing")
    worksheet_ready = not source_blockers
    operator_fill_complete = worksheet_ready and not pending_rows and not invalid_rows
    summary = {
        "packet_type": "production_ai_registry_promotion_operator_field_worksheet",
        "status": (
            "production_ai_registry_promotion_operator_field_worksheet_ready"
            if worksheet_ready
            else "blocked_production_ai_registry_promotion_operator_field_worksheet"
        ),
        "field_worksheet_ready": worksheet_ready,
        "operator_fill_complete": operator_fill_complete,
        "receipt_csv": _display_path(receipt_csv, root=root_path),
        "operator_receipt_artifact": _display_path(operator_receipt_json, root=root_path),
        "operator_receipt_status": _text(operator_receipt_summary.get("status")),
        "operator_receipt_ready": bool(operator_receipt_summary.get("operator_receipt_ready") is True),
        "registry_artifact": _display_path(registry_json, root=root_path),
        "checkpoint_readiness_artifact": _display_path(checkpoint_readiness_json, root=root_path),
        "priority_packet_artifact": _display_path(priority_packet_json, root=root_path),
        "priority_packet_status": _text(priority_summary.get("status")),
        "receipt_csv_present": receipt_csv_present,
        "operator_receipt_artifact_present": operator_receipt_present,
        "registry_artifact_present": registry_present,
        "checkpoint_readiness_artifact_present": checkpoint_present,
        "priority_packet_artifact_present": priority_present,
        "receipt_row_count": len(receipt_rows),
        "worksheet_field_row_count": len(worksheet_rows),
        "required_receipt_field_count": len([row for row in worksheet_rows if row["required_for_operator_receipt"]]),
        "operator_fill_pending_field_count": len(pending_rows),
        "invalid_field_count": len(invalid_rows),
        "ready_field_count": len([row for row in worksheet_rows if row["field_status"] == "ready"]),
        "diagnostic_required_field_count": len(DIAGNOSTIC_REQUIRED_FIELDS),
        "diagnostic_required_pending_field_count": len(diagnostic_pending),
        "pending_field_names": [str(row["field_name"]) for row in pending_rows],
        "invalid_field_names": [str(row["field_name"]) for row in invalid_rows],
        "top_gate_id": _text(priority_summary.get("top_gate_id")),
        "top_priority_bucket": _text(priority_summary.get("top_priority_bucket")),
        "top_required_input": _text(priority_summary.get("top_required_input")),
        "top_next_operator_step": _text(priority_summary.get("top_next_operator_step")),
        "approval_token_required": APPROVAL_TOKEN,
        "observed_registry_default_residual_mode": _text(
            registry_summary.get("default_residual_mode")
        ),
        "observed_registry_production_promotion_allowed": bool(
            registry_summary.get("production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_mutation_flags_ready": all(
            registry_summary.get(field) is True
            for field in (
                "customer_facing_auto_correction_allowed",
                "customer_facing_score_mutation_allowed",
                "customer_facing_ranking_mutation_allowed",
            )
        ),
        "observed_registry_trained_model_checkpoint_count": _int(
            registry_summary.get("trained_model_checkpoint_count")
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            checkpoint_summary.get("registry_promotion_currently_satisfied") is True
        ),
        "observed_checkpoint_registry_promotion_missing_gate_ids": [
            str(item)
            for item in (
                checkpoint_summary.get("registry_promotion_missing_gate_ids") or []
            )
        ],
        "blocker_count": len(source_blockers),
        "blockers": source_blockers,
        "registry_edited_by_this_tool": False,
        "checkpoint_created_by_this_tool": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "customer_facing_mutation_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator receipt fields are complete; rerun operator receipt, priority packet, checkpoint readiness, "
            "promotion workbench, and product-goal audit."
            if operator_fill_complete
            else "Fill every operator_fill_pending field in the guarded promotion receipt template, starting with "
            "the top priority gate, then rerun the operator receipt and priority packet."
        ),
        "source_artifacts": [
            str(receipt_csv),
            str(operator_receipt_json),
            str(registry_json),
            str(checkpoint_readiness_json),
            str(priority_packet_json),
        ],
    }
    return {"summary": summary, "rows": worksheet_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Production AI Registry Promotion Operator Field Worksheet",
        "",
        f"- status: `{summary['status']}`",
        f"- field_worksheet_ready: `{summary['field_worksheet_ready']}`",
        f"- operator_fill_complete: `{summary['operator_fill_complete']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- diagnostic_required_pending_field_count: `{summary['diagnostic_required_pending_field_count']}`",
        f"- top_gate_id: `{summary['top_gate_id']}`",
        f"- observed_registry_default_residual_mode: `{summary['observed_registry_default_residual_mode']}`",
        f"- observed_registry_trained_model_checkpoint_count: `{summary['observed_registry_trained_model_checkpoint_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| field | gate | status | current | observed | expected | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['gate_id']}` | `{row['field_status']}` | "
            f"`{row['current_receipt_value']}` | `{row['observed_registry_value']}` | "
            f"`{row['expected_value_hint']}` | `{row['operator_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build field-level worksheet for production AI registry promotion operator receipt."
    )
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--operator-receipt-json", default=DEFAULT_OPERATOR_RECEIPT_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--checkpoint-readiness-json", default=DEFAULT_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--priority-packet-json", default=DEFAULT_PRIORITY_PACKET_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_production_ai_registry_promotion_operator_field_worksheet(
        receipt_csv=args.receipt_csv,
        operator_receipt_json=args.operator_receipt_json,
        registry_json=args.registry_json,
        checkpoint_readiness_json=args.checkpoint_readiness_json,
        priority_packet_json=args.priority_packet_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
