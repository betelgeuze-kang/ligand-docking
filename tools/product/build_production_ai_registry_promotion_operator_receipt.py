#!/usr/bin/env python3
"""Fail-closed operator receipt for production AI registry promotion."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = "config/production_ai_registry_promotion_operator_receipt_current.csv"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_OUT_JSON = "runs/production_ai_registry_promotion_operator_receipt_current.json"
DEFAULT_OUT_CSV = "runs/production_ai_registry_promotion_operator_receipt_current.csv"
DEFAULT_OUT_MD = "runs/production_ai_registry_promotion_operator_receipt_current.md"
APPROVAL_TOKEN = "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
ARTIFACT_ID = "residual_model_registry_guarded_promotion"

REQUIRED_COLUMNS = [
    "artifact_id",
    "operator_decision",
    "registry_artifact",
    "checkpoint_readiness_artifact",
    "production_promotion_allowed",
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
    "default_residual_mode",
    "trained_model_checkpoint_count",
    "registry_validation_command",
    "validation_chain_reviewed",
    "claim_boundary_reviewed",
    "customer_facing_mutation_policy_reviewed",
    "reviewer",
    "reviewed_at_utc",
    "approval_token",
    "external_state_mutated",
    "operator_attestation",
    "notes",
]
REQUIRED_TRUE_FIELDS = [
    "production_promotion_allowed",
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
    "validation_chain_reviewed",
    "claim_boundary_reviewed",
    "customer_facing_mutation_policy_reviewed",
]
VALID_DECISIONS = {"promote_guarded", "hold"}
PROMOTION_DECISIONS = {"promote_guarded"}
GUARDED_MODES = {"assist", "production", "production_guarded"}
PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
CLAIM_BOUNDARY = (
    "Production AI registry promotion operator receipt only; it validates local operator review rows against the "
    "current residual model registry and checkpoint-readiness artifacts. It does not edit the registry, create "
    "checkpoints, enable customer-facing mutation, run GPU jobs, deploy, upload, email, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path: Path, *, root: Path = ROOT) -> str:
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
    return any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


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
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


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


def _first_missing_gate(readiness: dict[str, Any]) -> str:
    gates = readiness.get("registry_promotion_missing_gate_ids")
    if isinstance(gates, list) and gates:
        return _text(gates[0])
    return ""


def _row_status(
    row: dict[str, Any],
    *,
    missing_columns: list[str],
    registry_summary: dict[str, Any],
    registry_present: bool,
    readiness_summary: dict[str, Any],
    readiness_present: bool,
    duplicate_artifact_ids: set[str],
) -> dict[str, Any]:
    artifact_id = _text(row.get("artifact_id"))
    decision = _text(row.get("operator_decision")).lower()
    default_mode = _text(row.get("default_residual_mode"))
    checkpoint_count = _int(row.get("trained_model_checkpoint_count"))
    blockers: list[str] = []
    row_has_placeholder = any(_has_placeholder(row.get(column)) for column in REQUIRED_COLUMNS)

    if missing_columns:
        blockers.append("receipt_columns_missing")
    if artifact_id != ARTIFACT_ID:
        blockers.append("artifact_id_missing_or_unrecognized")
    if artifact_id in duplicate_artifact_ids:
        blockers.append("duplicate_artifact_id")
    if row_has_placeholder:
        blockers.append("operator_placeholders_unfilled")
    if not decision or _has_placeholder(row.get("operator_decision")):
        blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        blockers.append("operator_decision_invalid")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    for field in REQUIRED_TRUE_FIELDS:
        if _bool_text(row.get(field)) is not True:
            blockers.append(f"{field}_not_true")
    if default_mode not in GUARDED_MODES:
        blockers.append("default_residual_mode_not_guarded")
    if checkpoint_count <= 0:
        blockers.append("trained_model_checkpoint_count_not_positive")
    if _bool_text(row.get("external_state_mutated")) is not False:
        blockers.append("external_state_mutated_present")
    if _text(row.get("operator_attestation")) != "reviewed_for_production_ai_registry_promotion":
        blockers.append("operator_attestation_missing_or_unaccepted")
    if not _text(row.get("reviewer")) or _has_placeholder(row.get("reviewer")):
        blockers.append("reviewer_missing")
    if not _is_iso_timestamp(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if not _text(row.get("registry_validation_command")):
        blockers.append("registry_validation_command_missing")
    if _text(row.get("registry_artifact")) != DEFAULT_REGISTRY_JSON:
        blockers.append("registry_artifact_path_mismatch")
    if _text(row.get("checkpoint_readiness_artifact")) != DEFAULT_CHECKPOINT_READINESS_JSON:
        blockers.append("checkpoint_readiness_artifact_path_mismatch")
    if not registry_present:
        blockers.append("registry_artifact_missing")
    if not readiness_present:
        blockers.append("checkpoint_readiness_artifact_missing")
    if (
        registry_present
        and default_mode
        and not _has_placeholder(default_mode)
        and default_mode != _text(registry_summary.get("default_residual_mode"))
    ):
        blockers.append("registry_default_residual_mode_mismatch")
    if (
        readiness_present
        and default_mode
        and not _has_placeholder(default_mode)
        and default_mode != _text(readiness_summary.get("default_residual_mode"))
    ):
        blockers.append("checkpoint_readiness_default_residual_mode_mismatch")
    if registry_present and checkpoint_count != _int(registry_summary.get("trained_model_checkpoint_count")):
        blockers.append("registry_trained_model_checkpoint_count_mismatch")
    if readiness_present and checkpoint_count != _int(readiness_summary.get("trained_model_checkpoint_count")):
        blockers.append("checkpoint_readiness_trained_model_checkpoint_count_mismatch")

    observed_fields = {
        "production_promotion_allowed": registry_summary.get("production_promotion_allowed"),
        "customer_facing_auto_correction_allowed": registry_summary.get(
            "customer_facing_auto_correction_allowed"
        ),
        "customer_facing_score_mutation_allowed": registry_summary.get(
            "customer_facing_score_mutation_allowed"
        ),
        "customer_facing_ranking_mutation_allowed": registry_summary.get(
            "customer_facing_ranking_mutation_allowed"
        ),
        "default_residual_mode": registry_summary.get("default_residual_mode"),
        "trained_model_checkpoint_count": registry_summary.get("trained_model_checkpoint_count"),
    }
    if decision in PROMOTION_DECISIONS:
        for field in REQUIRED_TRUE_FIELDS[:4]:
            if registry_summary.get(field) is not True:
                blockers.append(f"registry_{field}_not_true")
            if readiness_summary.get(field) is not True:
                blockers.append(f"checkpoint_readiness_{field}_not_true")
        if _text(registry_summary.get("default_residual_mode")) not in GUARDED_MODES:
            blockers.append("registry_default_residual_mode_not_guarded")
        if _text(readiness_summary.get("default_residual_mode")) not in GUARDED_MODES:
            blockers.append("checkpoint_readiness_default_residual_mode_not_guarded")
        if _int(registry_summary.get("trained_model_checkpoint_count")) <= 0:
            blockers.append("registry_trained_model_checkpoint_count_not_positive")
        if _int(readiness_summary.get("trained_model_checkpoint_count")) <= 0:
            blockers.append("checkpoint_readiness_trained_model_checkpoint_count_not_positive")
        if readiness_summary.get("registry_promotion_currently_satisfied") is not True:
            blockers.append("checkpoint_readiness_registry_promotion_not_satisfied")

    return {
        **{column: row.get(column, "") for column in REQUIRED_COLUMNS},
        "operator_decision": decision,
        "row_status": "pass" if not blockers else "blocked",
        "blocker_count": len(blockers),
        "blockers": ";".join(blockers),
        "observed_registry_status": _text(registry_summary.get("status")) or "missing",
        "observed_checkpoint_readiness_status": _text(readiness_summary.get("status")) or "missing",
        "observed_registry_default_residual_mode": _text(observed_fields["default_residual_mode"]),
        "observed_registry_production_promotion_allowed": bool(
            observed_fields["production_promotion_allowed"] is True
        ),
        "observed_registry_customer_facing_auto_correction_allowed": bool(
            observed_fields["customer_facing_auto_correction_allowed"] is True
        ),
        "observed_registry_customer_facing_score_mutation_allowed": bool(
            observed_fields["customer_facing_score_mutation_allowed"] is True
        ),
        "observed_registry_customer_facing_ranking_mutation_allowed": bool(
            observed_fields["customer_facing_ranking_mutation_allowed"] is True
        ),
        "observed_registry_trained_model_checkpoint_count": _int(
            observed_fields["trained_model_checkpoint_count"]
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            readiness_summary.get("registry_promotion_currently_satisfied") is True
        ),
        "observed_checkpoint_first_missing_gate": _first_missing_gate(readiness_summary),
        "external_state_mutated": False,
        "registry_edited_by_this_tool": False,
        "checkpoint_created_by_this_tool": False,
    }


def build_production_ai_registry_promotion_operator_receipt(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    registry_json: str | Path = DEFAULT_REGISTRY_JSON,
    checkpoint_readiness_json: str | Path = DEFAULT_CHECKPOINT_READINESS_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    raw_rows, missing_columns, receipt_present = _read_csv(receipt_csv, root=root_path)
    registry_packet, registry_present = _read_json(registry_json, root=root_path)
    readiness_packet, readiness_present = _read_json(checkpoint_readiness_json, root=root_path)
    registry_summary = _summary(registry_packet)
    readiness_summary = _summary(readiness_packet)
    artifact_ids = [_text(row.get("artifact_id")) for row in raw_rows if _text(row.get("artifact_id"))]
    duplicate_artifact_ids = {
        artifact_id for artifact_id in artifact_ids if artifact_ids.count(artifact_id) > 1
    }
    rows = [
        _row_status(
            row,
            missing_columns=missing_columns,
            registry_summary=registry_summary,
            registry_present=registry_present,
            readiness_summary=readiness_summary,
            readiness_present=readiness_present,
            duplicate_artifact_ids=duplicate_artifact_ids,
        )
        for row in raw_rows
    ]
    if ARTIFACT_ID not in artifact_ids:
        rows.append(
            {
                **{column: "" for column in REQUIRED_COLUMNS},
                "artifact_id": ARTIFACT_ID,
                "operator_decision": "",
                "row_status": "blocked",
                "blocker_count": 1,
                "blockers": "operator_receipt_row_missing",
                "observed_registry_status": _text(registry_summary.get("status")) or "missing",
                "observed_checkpoint_readiness_status": _text(readiness_summary.get("status")) or "missing",
                "observed_registry_default_residual_mode": _text(
                    registry_summary.get("default_residual_mode")
                ),
                "observed_registry_production_promotion_allowed": bool(
                    registry_summary.get("production_promotion_allowed") is True
                ),
                "observed_registry_customer_facing_auto_correction_allowed": bool(
                    registry_summary.get("customer_facing_auto_correction_allowed") is True
                ),
                "observed_registry_customer_facing_score_mutation_allowed": bool(
                    registry_summary.get("customer_facing_score_mutation_allowed") is True
                ),
                "observed_registry_customer_facing_ranking_mutation_allowed": bool(
                    registry_summary.get("customer_facing_ranking_mutation_allowed") is True
                ),
                "observed_registry_trained_model_checkpoint_count": _int(
                    registry_summary.get("trained_model_checkpoint_count")
                ),
                "observed_checkpoint_registry_promotion_currently_satisfied": bool(
                    readiness_summary.get("registry_promotion_currently_satisfied") is True
                ),
                "observed_checkpoint_first_missing_gate": _first_missing_gate(readiness_summary),
                "external_state_mutated": False,
                "registry_edited_by_this_tool": False,
                "checkpoint_created_by_this_tool": False,
            }
        )

    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    blocker_counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for row in blocked_rows:
        for blocker in _text(row.get("blockers")).split(";"):
            if blocker:
                first_seen.setdefault(blocker, len(first_seen))
                blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    most_common_blocker = (
        sorted(blocker_counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))[0][0]
        if blocker_counts
        else ""
    )
    summary_blockers: list[str] = []
    if not receipt_present:
        summary_blockers.append("receipt_csv_missing")
    if missing_columns:
        summary_blockers.append("receipt_columns_missing")
    if ARTIFACT_ID not in artifact_ids:
        summary_blockers.append("operator_receipt_row_missing")
    if duplicate_artifact_ids:
        summary_blockers.append("duplicate_operator_receipt_rows")
    if blocked_rows:
        summary_blockers.append("blocked_receipt_rows_present")
    ready = bool(rows) and not summary_blockers
    summary = {
        "packet_type": "production_ai_registry_promotion_operator_receipt",
        "status": (
            "production_ai_registry_promotion_operator_receipt_ready"
            if ready
            else "blocked_production_ai_registry_promotion_operator_receipt"
        ),
        "operator_receipt_ready": ready,
        "receipt_csv": _display_path(_resolve(receipt_csv, root=root_path), root=root_path),
        "registry_artifact": _display_path(_resolve(registry_json, root=root_path), root=root_path),
        "checkpoint_readiness_artifact": _display_path(
            _resolve(checkpoint_readiness_json, root=root_path),
            root=root_path,
        ),
        "receipt_present": receipt_present,
        "registry_artifact_present": registry_present,
        "checkpoint_readiness_artifact_present": readiness_present,
        "receipt_row_count": len(raw_rows),
        "pass_row_count": len(rows) - len(blocked_rows),
        "blocked_row_count": len(blocked_rows),
        "first_blocked_artifact_id": _text(first_blocked.get("artifact_id")),
        "first_blocked_row_blocker": next(
            (blocker for blocker in _text(first_blocked.get("blockers")).split(";") if blocker),
            "",
        ),
        "first_blocked_row_blockers": [
            blocker for blocker in _text(first_blocked.get("blockers")).split(";") if blocker
        ],
        "most_common_row_blocker": most_common_blocker,
        "approval_token_required": APPROVAL_TOKEN,
        "registry_promotion_required_gate_ids": [
            "production_promotion_allowed",
            "customer_facing_mutation_flags",
            "default_residual_mode_guarded",
            "trained_model_checkpoint_count_positive",
        ],
        "observed_registry_default_residual_mode": _text(
            registry_summary.get("default_residual_mode")
        ),
        "observed_registry_production_promotion_allowed": bool(
            registry_summary.get("production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_auto_correction_allowed": bool(
            registry_summary.get("customer_facing_auto_correction_allowed") is True
        ),
        "observed_registry_customer_facing_score_mutation_allowed": bool(
            registry_summary.get("customer_facing_score_mutation_allowed") is True
        ),
        "observed_registry_customer_facing_ranking_mutation_allowed": bool(
            registry_summary.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "observed_registry_trained_model_checkpoint_count": _int(
            registry_summary.get("trained_model_checkpoint_count")
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            readiness_summary.get("registry_promotion_currently_satisfied") is True
        ),
        "observed_checkpoint_registry_promotion_missing_gate_ids": [
            str(item) for item in (readiness_summary.get("registry_promotion_missing_gate_ids") or [])
        ],
        "blocker_count": len(summary_blockers),
        "blockers": summary_blockers,
        "registry_edited_by_this_tool": False,
        "checkpoint_created_by_this_tool": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Registry promotion receipt is ready; rerun registry, checkpoint-readiness, promotion workbench, "
            "and product-goal audit gates."
            if ready
            else "Fill the production AI registry promotion receipt with guarded promotion values, reviewer "
            "metadata, approval token, and verify the residual registry/checkpoint-readiness artifacts match."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Production AI Registry Promotion Operator Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- operator_receipt_ready: `{s['operator_receipt_ready']}`",
        f"- receipt_csv: `{s['receipt_csv']}`",
        f"- registry_artifact: `{s['registry_artifact']}`",
        f"- checkpoint_readiness_artifact: `{s['checkpoint_readiness_artifact']}`",
        f"- receipt_row_count: `{s['receipt_row_count']}`",
        f"- pass_row_count: `{s['pass_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- first_blocked_artifact_id: `{s['first_blocked_artifact_id']}`",
        f"- first_blocked_row_blocker: `{s['first_blocked_row_blocker']}`",
        f"- most_common_row_blocker: `{s['most_common_row_blocker']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- observed_registry_default_residual_mode: `{s['observed_registry_default_residual_mode']}`",
        f"- observed_registry_trained_model_checkpoint_count: `{s['observed_registry_trained_model_checkpoint_count']}`",
        f"- observed_checkpoint_registry_promotion_currently_satisfied: `{s['observed_checkpoint_registry_promotion_currently_satisfied']}`",
        f"- registry_edited_by_this_tool: `{s['registry_edited_by_this_tool']}`",
        f"- checkpoint_created_by_this_tool: `{s['checkpoint_created_by_this_tool']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| artifact | decision | status | blockers | observed mode | observed checkpoints |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['operator_decision']}` | `{row['row_status']}` | "
            f"`{row['blockers']}` | `{row['observed_registry_default_residual_mode']}` | "
            f"`{row['observed_registry_trained_model_checkpoint_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build production AI registry promotion operator receipt gate.")
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--checkpoint-readiness-json", default=DEFAULT_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_production_ai_registry_promotion_operator_receipt(
        receipt_csv=args.receipt_csv,
        registry_json=args.registry_json,
        checkpoint_readiness_json=args.checkpoint_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
