#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXTERNAL_RECEIPTS_AUDIT_JSON = "runs/public_benchmark_external_receipts_audit_current.json"
DEFAULT_VINA_GNINA_WORK_ORDER_JSON = "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
DEFAULT_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_JSON = (
    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
)
DEFAULT_VINA_GNINA_SCORE_TEMPLATE_CSV = "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
DEFAULT_METRIC_SOURCE_RECEIPT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
)
DEFAULT_METRIC_SOURCE_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_OUT_JSON = "runs/public_benchmark_receipt_attach_packet_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_receipt_attach_packet_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_receipt_attach_packet_current.md"

PACKET_TYPE = "public_benchmark_receipt_attach_packet"
SCHEMA_VERSION = "public_benchmark_receipt_attach_packet_v1"
VINA_GNINA_APPROVAL_TOKEN = "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"

CLAIM_BOUNDARY = (
    "Public benchmark receipt attach packet only; it summarizes local operator-fill rows, pending fields, "
    "approval tokens, and follow-up commands for external benchmark receipts. It does not run Vina/GNINA, "
    "download benchmark datasets, compute metrics, approve receipt rows, promote claims, upload, email, "
    "deploy, or mutate external state."
)

CSV_FIELDS = [
    "lane_id",
    "status",
    "ready",
    "source_artifact",
    "operator_csv",
    "row_count",
    "pending_value_count",
    "pending_metadata_count",
    "pending_license_count",
    "pending_approval_token_count",
    "approval_token_required",
    "blocker",
    "next_required_step",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]

METRIC_SOURCE_PENDING_FIELDS = [
    ("metric_value", "receipt_metric_value_pending_count", "fill reviewed numeric metric value"),
    ("method", "receipt_method_pending_count", "fill method/tool used for metric derivation"),
    (
        "input_artifacts_reviewed",
        "receipt_input_artifacts_reviewed_pending_count",
        "confirm required input artifacts were reviewed",
    ),
    (
        "input_artifact_sha256s_reviewed",
        "receipt_input_artifact_sha256s_reviewed_pending_count",
        "confirm required input artifact hashes were reviewed",
    ),
    (
        "metric_source_artifact_reviewed",
        "receipt_metric_source_artifact_reviewed_pending_count",
        "confirm metric source artifact was reviewed",
    ),
    (
        "payload_schema_reviewed",
        "receipt_payload_schema_reviewed_pending_count",
        "confirm payload schema was reviewed",
    ),
    ("license_ok", "receipt_license_ok_pending_count", "confirm license_ok=true"),
    ("operator_id", "receipt_operator_id_pending_count", "fill reviewer/operator id"),
    ("reviewed_at_utc", "receipt_reviewed_at_utc_pending_count", "fill timezone-aware review timestamp"),
    ("approval_token", "receipt_approval_token_pending_count", "fill approval token"),
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
    return summary if isinstance(summary, dict) else payload


def _dict_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _csv_row_count(path_like: str | Path, *, root: Path = ROOT) -> int:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _csv_pending_field_counts(path_like: str | Path, *, root: Path = ROOT) -> dict[str, int]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}
    counts: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for field, value in row.items():
                text = _text(value)
                if not text or text.startswith("OPERATOR_FILL") or text.startswith("OPERATOR_CONFIRM"):
                    counts[_text(field)] = counts.get(_text(field), 0) + 1
    return {field: count for field, count in counts.items() if field}


def _field_required_action(*, field_name: str, required_value: str, approval_token_required: str) -> str:
    if field_name == "approval_token":
        return f"Fill approval_token with {approval_token_required} after operator review."
    if field_name == "license_ok":
        return "Confirm license_ok=true only after the benchmark input and receipt license review passes."
    if field_name in {"operator_id", "reviewed_at_utc"}:
        return f"Fill {field_name} with reviewed operator metadata."
    return f"Replace operator placeholder for {field_name} with {required_value}."


def _field_work_order_row(
    *,
    lane_id: str,
    source_artifact: str | Path,
    operator_csv: str | Path,
    field_name: str,
    pending_row_count: int,
    required_value: str,
    approval_token_required: str,
    root: Path,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "field_name": field_name,
        "pending_row_count": pending_row_count,
        "source_artifact": _display(source_artifact, root=root),
        "operator_csv": _display(operator_csv, root=root),
        "required_value": required_value,
        "approval_token_required": approval_token_required,
        "required_action": _field_required_action(
            field_name=field_name,
            required_value=required_value,
            approval_token_required=approval_token_required,
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _build_field_work_order_rows(
    *,
    vina_gnina_source: dict[str, Any],
    vina_gnina_source_artifact: str | Path,
    vina_gnina_score_template_csv: str | Path,
    metric_receipt: dict[str, Any],
    metric_source_receipt_json: str | Path,
    metric_source_receipt_csv: str | Path,
    root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    vina_pending_counts = vina_gnina_source.get("pending_field_counts")
    if not isinstance(vina_pending_counts, dict):
        vina_pending_counts = _csv_pending_field_counts(vina_gnina_score_template_csv, root=root)
    vina_token = _text(vina_gnina_source.get("approval_token_required")) or VINA_GNINA_APPROVAL_TOKEN
    for field_name, pending_count in sorted(vina_pending_counts.items()):
        count = _int(pending_count)
        if count <= 0:
            continue
        rows.append(
            _field_work_order_row(
                lane_id="vina_gnina_same_input_scores",
                source_artifact=vina_gnina_source_artifact,
                operator_csv=vina_gnina_score_template_csv,
                field_name=field_name,
                pending_row_count=count,
                required_value=(
                    f"{vina_token} for approval_token"
                    if field_name == "approval_token"
                    else "operator-reviewed same-input Vina/GNINA score evidence"
                ),
                approval_token_required=vina_token,
                root=root,
            )
        )

    metric_token = _text(metric_receipt.get("approval_token_required")) or (
        "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_METRIC_SOURCE_PAYLOAD"
    )
    for field_name, pending_key, required_value in METRIC_SOURCE_PENDING_FIELDS:
        count = _int(metric_receipt.get(pending_key))
        if count <= 0:
            continue
        rows.append(
            _field_work_order_row(
                lane_id="metric_source_receipt_rows",
                source_artifact=metric_source_receipt_json,
                operator_csv=metric_source_receipt_csv,
                field_name=field_name,
                pending_row_count=count,
                required_value=(
                    f"{metric_token} for approval_token"
                    if field_name == "approval_token"
                    else required_value
                ),
                approval_token_required=metric_token,
                root=root,
            )
        )
    return rows


def _score_evidence_row_work_order_rows(
    payload: dict[str, Any],
    *,
    source_artifact: str | Path,
    root: Path,
) -> list[dict[str, Any]]:
    summary = _summary(payload)
    claim_boundary = _text(summary.get("claim_boundary")) or CLAIM_BOUNDARY
    source = _display(source_artifact, root=root)
    rows: list[dict[str, Any]] = []
    for row in _dict_list(payload, "score_evidence_row_work_order_rows"):
        missing_fields = _string_list(row.get("missing_fields"))
        rows.append(
            {
                "work_order_id": _text(row.get("work_order_id")),
                "status": _text(row.get("status")) or "blocked",
                "pose_id": _text(row.get("pose_id")),
                "complex_id": _text(row.get("complex_id")),
                "operator_csv": _text(row.get("operator_csv")),
                "source_artifact": source,
                "missing_field_count": _int(row.get("missing_field_count"))
                or len(missing_fields),
                "missing_fields": missing_fields,
                "primary_missing_field": _text(row.get("primary_missing_field")),
                "primary_required_action": _text(row.get("primary_required_action")),
                "required_action": _text(row.get("required_action")),
                "blocker_count": _int(row.get("blocker_count")),
                "blockers": _string_list(row.get("blockers")),
                "score_values_ready": _bool_true(row.get("score_values_ready")),
                "metadata_ready": _bool_true(row.get("metadata_ready")),
                "license_ok": _bool_true(row.get("license_ok")),
                "approval_token_ok": _bool_true(row.get("approval_token_ok")),
                "approval_token_required": _text(row.get("approval_token_required")),
                "operator_action_required": row.get("operator_action_required") is not False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": _text(row.get("claim_boundary")) or claim_boundary,
            }
        )
    return rows


def _lane(
    *,
    lane_id: str,
    ready: bool,
    source_artifact: str | Path,
    operator_csv: str | Path,
    row_count: int,
    pending_value_count: int,
    pending_metadata_count: int,
    pending_license_count: int,
    pending_approval_token_count: int,
    approval_token_required: str,
    blocker: str,
    next_required_step: str,
    root: Path,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "source_artifact": _display(source_artifact, root=root),
        "operator_csv": _display(operator_csv, root=root),
        "row_count": row_count,
        "pending_value_count": pending_value_count,
        "pending_metadata_count": pending_metadata_count,
        "pending_license_count": pending_license_count,
        "pending_approval_token_count": pending_approval_token_count,
        "approval_token_required": approval_token_required,
        "blocker": "" if ready else blocker,
        "next_required_step": next_required_step,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_public_benchmark_receipt_attach_packet(
    *,
    external_receipts_audit_json: str | Path = DEFAULT_EXTERNAL_RECEIPTS_AUDIT_JSON,
    vina_gnina_work_order_json: str | Path = DEFAULT_VINA_GNINA_WORK_ORDER_JSON,
    vina_gnina_score_template_receipt_json: str | Path = DEFAULT_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_JSON,
    vina_gnina_score_template_csv: str | Path = DEFAULT_VINA_GNINA_SCORE_TEMPLATE_CSV,
    metric_source_receipt_json: str | Path = DEFAULT_METRIC_SOURCE_RECEIPT_JSON,
    metric_source_receipt_csv: str | Path = DEFAULT_METRIC_SOURCE_RECEIPT_CSV,
    root: Path = ROOT,
) -> dict[str, Any]:
    audit = _summary(_read_json(external_receipts_audit_json, root=root))
    vina_gnina = _summary(_read_json(vina_gnina_work_order_json, root=root))
    vina_gnina_receipt_payload = _read_json(vina_gnina_score_template_receipt_json, root=root)
    vina_gnina_receipt = _summary(vina_gnina_receipt_payload)
    metric_receipt = _summary(_read_json(metric_source_receipt_json, root=root))
    vina_gnina_receipt_present = bool(vina_gnina_receipt)
    vina_gnina_source = vina_gnina_receipt if vina_gnina_receipt_present else vina_gnina
    vina_gnina_source_artifact = (
        vina_gnina_score_template_receipt_json if vina_gnina_receipt_present else vina_gnina_work_order_json
    )

    vina_gnina_row_count = _int(vina_gnina_source.get("score_template_row_count")) or _csv_row_count(
        vina_gnina_score_template_csv, root=root
    )
    vina_gnina_ready = (
        _bool_true(vina_gnina_source.get("score_template_validation_ready"))
        and _int(vina_gnina_source.get("score_template_blocker_count")) == 0
        and vina_gnina_row_count > 0
    )
    vina_gnina_lane = _lane(
        lane_id="vina_gnina_same_input_scores",
        ready=vina_gnina_ready,
        source_artifact=vina_gnina_source_artifact,
        operator_csv=vina_gnina_score_template_csv,
        row_count=vina_gnina_row_count,
        pending_value_count=_int(vina_gnina_source.get("score_value_pending_count")),
        pending_metadata_count=_int(vina_gnina_source.get("operator_metadata_pending_count"))
        + _int(vina_gnina_source.get("operator_placeholder_pending_count")),
        pending_license_count=_int(vina_gnina_source.get("license_ok_pending_count")),
        pending_approval_token_count=_int(vina_gnina_source.get("approval_token_pending_count")),
        approval_token_required=_text(vina_gnina.get("approval_token_required")) or VINA_GNINA_APPROVAL_TOKEN,
        blocker="vina_gnina_same_input_score_evidence_missing",
        next_required_step=_text(vina_gnina_source.get("next_required_step"))
        or _text(vina_gnina.get("next_required_step"))
        or "Fill every Vina/GNINA same-input score template row, then rerun the comparison adapter.",
        root=root,
    )

    metric_row_count = _int(metric_receipt.get("row_count")) or _csv_row_count(
        metric_source_receipt_csv, root=root
    )
    metric_ready = (
        _bool_true(metric_receipt.get("claim_promotion_allowed"))
        and _int(metric_receipt.get("blocked_row_count")) == 0
        and metric_row_count > 0
    )
    metric_lane = _lane(
        lane_id="metric_source_receipt_rows",
        ready=metric_ready,
        source_artifact=metric_source_receipt_json,
        operator_csv=metric_source_receipt_csv,
        row_count=metric_row_count,
        pending_value_count=_int(metric_receipt.get("receipt_manual_field_pending_count")),
        pending_metadata_count=_int(metric_receipt.get("receipt_manual_field_pending_count")),
        pending_license_count=_int(metric_receipt.get("license_ok_pending_count")),
        pending_approval_token_count=_int(metric_receipt.get("receipt_approval_token_pending_count")),
        approval_token_required=_text(metric_receipt.get("approval_token_required"))
        or "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_METRIC_SOURCE_PAYLOAD",
        blocker="benchmark_metric_source_receipt_rows_unapproved",
        next_required_step=(
            "Fill reviewed metric values, methods, artifact review fields, license flags, and approval token "
            "for every metric-source receipt row."
        ),
        root=root,
    )

    rows = [vina_gnina_lane, metric_lane]
    field_work_order_rows = _build_field_work_order_rows(
        vina_gnina_source=vina_gnina_source,
        vina_gnina_source_artifact=vina_gnina_source_artifact,
        vina_gnina_score_template_csv=vina_gnina_score_template_csv,
        metric_receipt=metric_receipt,
        metric_source_receipt_json=metric_source_receipt_json,
        metric_source_receipt_csv=metric_source_receipt_csv,
        root=root,
    )
    score_evidence_row_work_order_rows = _score_evidence_row_work_order_rows(
        vina_gnina_receipt_payload if vina_gnina_receipt_present else {},
        source_artifact=vina_gnina_score_template_receipt_json,
        root=root,
    )
    ready_rows = [row for row in rows if row["ready"]]
    blocked_rows = [row for row in rows if not row["ready"]]
    packet_ready = len(ready_rows) == len(rows)
    primary_work_order_row = field_work_order_rows[0] if field_work_order_rows else {}
    primary_score_row_work_order = (
        score_evidence_row_work_order_rows[0] if score_evidence_row_work_order_rows else {}
    )
    score_evidence_row_work_order_row_count = len(score_evidence_row_work_order_rows) or _int(
        vina_gnina_receipt.get("score_evidence_row_work_order_row_count")
    )
    score_evidence_row_work_order_pending_field_count = sum(
        _int(row.get("missing_field_count")) for row in score_evidence_row_work_order_rows
    )
    if not score_evidence_row_work_order_pending_field_count:
        score_evidence_row_work_order_pending_field_count = (
            _int(vina_gnina_receipt.get("score_evidence_row_work_order_primary_missing_field_count"))
            if score_evidence_row_work_order_row_count
            else 0
        )
    score_evidence_row_work_order_ready = (
        _bool_true(vina_gnina_receipt.get("score_evidence_row_work_order_ready"))
        if "score_evidence_row_work_order_ready" in vina_gnina_receipt
        else score_evidence_row_work_order_row_count == 0
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "public_benchmark_receipt_attach_packet_ready"
        if packet_ready
        else "blocked_public_benchmark_receipt_attach_packet",
        "receipt_attach_packet_ready": packet_ready,
        "external_benchmark_receipts_ready": packet_ready
        and _bool_true(audit.get("external_benchmark_receipts_ready")),
        "claim_promotion_allowed": False,
        "lane_count": len(rows),
        "ready_lane_count": len(ready_rows),
        "blocked_lane_count": len(blocked_rows),
        "blocker_count": len(blocked_rows),
        "blockers": [f"{row['lane_id']}:{row['blocker']}" for row in blocked_rows],
        "field_work_order_ready": not field_work_order_rows,
        "field_work_order_row_count": len(field_work_order_rows),
        "field_work_order_pending_field_count": sum(
            _int(row.get("pending_row_count")) for row in field_work_order_rows
        ),
        "field_work_order_primary_lane_id": _text(primary_work_order_row.get("lane_id")),
        "field_work_order_primary_field_name": _text(primary_work_order_row.get("field_name")),
        "field_work_order_primary_pending_row_count": _int(
            primary_work_order_row.get("pending_row_count")
        ),
        "field_work_order_primary_required_value": _text(
            primary_work_order_row.get("required_value")
        ),
        "field_work_order_primary_required_action": _text(
            primary_work_order_row.get("required_action")
        ),
        "field_work_order_primary_approval_token_required": _text(
            primary_work_order_row.get("approval_token_required")
        ),
        "field_work_order_primary_operator_csv": _text(primary_work_order_row.get("operator_csv")),
        "field_work_order_primary_source_artifact": _text(
            primary_work_order_row.get("source_artifact")
        ),
        "score_evidence_row_work_order_ready": score_evidence_row_work_order_ready,
        "score_evidence_row_work_order_row_count": score_evidence_row_work_order_row_count,
        "score_evidence_row_work_order_pending_field_count": (
            score_evidence_row_work_order_pending_field_count
        ),
        "score_evidence_row_work_order_primary_work_order_id": _text(
            primary_score_row_work_order.get("work_order_id")
        ),
        "score_evidence_row_work_order_primary_pose_id": _text(
            primary_score_row_work_order.get("pose_id")
        )
        or _text(vina_gnina_receipt.get("score_evidence_row_work_order_primary_pose_id")),
        "score_evidence_row_work_order_primary_complex_id": _text(
            primary_score_row_work_order.get("complex_id")
        )
        or _text(vina_gnina_receipt.get("score_evidence_row_work_order_primary_complex_id")),
        "score_evidence_row_work_order_primary_missing_field_count": _int(
            primary_score_row_work_order.get("missing_field_count")
        )
        or _int(vina_gnina_receipt.get("score_evidence_row_work_order_primary_missing_field_count")),
        "score_evidence_row_work_order_primary_missing_fields": _string_list(
            primary_score_row_work_order.get("missing_fields")
        )
        or _string_list(vina_gnina_receipt.get("score_evidence_row_work_order_primary_missing_fields")),
        "score_evidence_row_work_order_primary_missing_field": _text(
            primary_score_row_work_order.get("primary_missing_field")
        ),
        "score_evidence_row_work_order_primary_required_action": _text(
            primary_score_row_work_order.get("required_action")
        )
        or _text(
            vina_gnina_receipt.get("score_evidence_row_work_order_primary_required_action")
        ),
        "score_evidence_row_work_order_primary_field_required_action": _text(
            primary_score_row_work_order.get("primary_required_action")
        ),
        "score_evidence_row_work_order_primary_operator_csv": _text(
            primary_score_row_work_order.get("operator_csv")
        )
        or _display(vina_gnina_score_template_csv, root=root),
        "score_evidence_row_work_order_primary_source_artifact": _text(
            primary_score_row_work_order.get("source_artifact")
        )
        or _display(vina_gnina_score_template_receipt_json, root=root),
        "primary_blocker_id": blocked_rows[0]["lane_id"] if blocked_rows else "",
        "primary_blocker": blocked_rows[0]["blocker"] if blocked_rows else "",
        "external_receipts_audit_status": _text(audit.get("status")),
        "external_receipts_audit_blocker_count": _int(audit.get("blocker_count")),
        "vina_gnina_score_template_receipt_present": vina_gnina_receipt_present,
        "vina_gnina_score_template_receipt_status": _text(vina_gnina_receipt.get("status")),
        "vina_gnina_score_template_receipt_json": _display(
            vina_gnina_score_template_receipt_json,
            root=root,
        ),
        "vina_gnina_score_template_csv": _display(vina_gnina_score_template_csv, root=root),
        "vina_gnina_score_template_row_count": vina_gnina_row_count,
        "vina_gnina_score_value_pending_count": vina_gnina_lane["pending_value_count"],
        "vina_gnina_operator_metadata_pending_count": _int(
            vina_gnina_source.get("operator_metadata_pending_count")
        ),
        "vina_gnina_operator_placeholder_pending_count": _int(
            vina_gnina_source.get("operator_placeholder_pending_count")
        ),
        "vina_gnina_license_ok_pending_count": vina_gnina_lane["pending_license_count"],
        "vina_gnina_approval_token_pending_count": vina_gnina_lane["pending_approval_token_count"],
        "metric_source_receipt_csv": _display(metric_source_receipt_csv, root=root),
        "metric_source_receipt_row_count": metric_row_count,
        "metric_source_receipt_blocked_row_count": _int(metric_receipt.get("blocked_row_count")),
        "metric_source_receipt_manual_field_pending_count": _int(
            metric_receipt.get("receipt_manual_field_pending_count")
        ),
        "metric_source_receipt_approval_token_pending_count": metric_lane[
            "pending_approval_token_count"
        ],
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": blocked_rows[0]["next_required_step"]
        if blocked_rows
        else "Receipt attach packet is ready; rerun the external benchmark receipts audit.",
    }
    return {
        "summary": summary,
        "rows": rows,
        "field_work_order_rows": field_work_order_rows,
        "score_evidence_row_work_order_rows": score_evidence_row_work_order_rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_text(item) for item in value if _text(item))
    return _text(value)


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Public Benchmark Receipt Attach Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- receipt_attach_packet_ready: `{summary['receipt_attach_packet_ready']}`",
        f"- ready_lane_count: `{summary['ready_lane_count']}` / `{summary['lane_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker_id: `{summary['primary_blocker_id']}`",
        f"- field_work_order_ready: `{summary['field_work_order_ready']}`",
        f"- field_work_order_row_count: `{summary['field_work_order_row_count']}`",
        f"- field_work_order_pending_field_count: `{summary['field_work_order_pending_field_count']}`",
        f"- score_evidence_row_work_order_ready: `{summary['score_evidence_row_work_order_ready']}`",
        f"- score_evidence_row_work_order_row_count: `{summary['score_evidence_row_work_order_row_count']}`",
        (
            "- score_evidence_row_work_order_pending_field_count: "
            f"`{summary['score_evidence_row_work_order_pending_field_count']}`"
        ),
        "",
        "| lane | status | rows | pending values | pending approvals | blocker |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['status']}` | `{row['row_count']}` | "
            f"`{row['pending_value_count']}` | `{row['pending_approval_token_count']}` | "
            f"`{row['blocker']}` |"
        )
    lines.extend(
        [
            "",
            "## Field Work Order",
            "",
            "| lane | field | pending rows | required value | action | operator csv |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in payload.get("field_work_order_rows", []):
        lines.append(
            f"| `{row['lane_id']}` | `{row['field_name']}` | `{row['pending_row_count']}` | "
            f"{row['required_value']} | {row['required_action']} | `{row['operator_csv']}` |"
        )
    lines.extend(
        [
            "",
            "## Score Evidence Row Work Order",
            "",
            "| pose | complex | missing fields | primary field | action | operator csv |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in payload.get("score_evidence_row_work_order_rows", []):
        lines.append(
            f"| `{row['pose_id']}` | `{row['complex_id']}` | `{row['missing_field_count']}` | "
            f"`{row['primary_missing_field']}` | {row['required_action']} | "
            f"`{row['operator_csv']}` |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build public benchmark receipt attach packet.")
    parser.add_argument("--external-receipts-audit-json", default=DEFAULT_EXTERNAL_RECEIPTS_AUDIT_JSON)
    parser.add_argument("--vina-gnina-work-order-json", default=DEFAULT_VINA_GNINA_WORK_ORDER_JSON)
    parser.add_argument(
        "--vina-gnina-score-template-receipt-json",
        default=DEFAULT_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_JSON,
    )
    parser.add_argument("--vina-gnina-score-template-csv", default=DEFAULT_VINA_GNINA_SCORE_TEMPLATE_CSV)
    parser.add_argument("--metric-source-receipt-json", default=DEFAULT_METRIC_SOURCE_RECEIPT_JSON)
    parser.add_argument("--metric-source-receipt-csv", default=DEFAULT_METRIC_SOURCE_RECEIPT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_public_benchmark_receipt_attach_packet(
        external_receipts_audit_json=args.external_receipts_audit_json,
        vina_gnina_work_order_json=args.vina_gnina_work_order_json,
        vina_gnina_score_template_receipt_json=args.vina_gnina_score_template_receipt_json,
        vina_gnina_score_template_csv=args.vina_gnina_score_template_csv,
        metric_source_receipt_json=args.metric_source_receipt_json,
        metric_source_receipt_csv=args.metric_source_receipt_csv,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
