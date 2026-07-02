#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.product.build_public_benchmark_vina_gnina_comparison_work_order import (
    APPROVAL_TOKEN,
    CSV_FIELDS as SCORE_TEMPLATE_FIELDS,
    validate_vina_gnina_score_template,
)


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORK_ORDER_JSON = "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
DEFAULT_SCORE_TEMPLATE_CSV = "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
DEFAULT_OUT_JSON = "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_vina_gnina_score_template_receipt_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_vina_gnina_score_template_receipt_current.md"

PACKET_TYPE = "public_benchmark_vina_gnina_score_template_receipt"
SCHEMA_VERSION = "public_benchmark_vina_gnina_score_template_receipt_v1"

CLAIM_BOUNDARY = (
    "Public benchmark Vina/GNINA same-input score-template receipt only; it validates an operator-filled "
    "local CSV against the frozen comparison work order. It does not run Vina, run GNINA, run docking, "
    "download datasets, compute benchmark deltas, approve claims, promote external benchmark wording, "
    "upload, email, deploy, or mutate external state."
)

CSV_FIELDS = [
    "pose_id",
    "complex_id",
    "status",
    "score_values_ready",
    "metadata_ready",
    "license_ok",
    "approval_token_ok",
    "blocker",
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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _is_number(value: Any) -> bool:
    try:
        float(_text(value))
    except ValueError:
        return False
    return bool(_text(value))


def _sha256_file(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv_rows(path_like: str | Path, *, root: Path = ROOT) -> tuple[bool, list[str], list[dict[str, Any]]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return False, [], []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return True, fieldnames, [dict(row) for row in reader]


def _row_status(row: dict[str, Any]) -> dict[str, Any]:
    missing_score_fields = [field for field in ("vina_score", "gnina_score") if not _is_number(row.get(field))]
    metadata_fields = (
        "comparison_score_source",
        "comparison_score_artifact_path",
        "comparison_score_artifact_sha256",
        "operator_engine_versions",
        "operator_prep_policy_sha256",
        "operator_method",
        "operator_reviewed_at_utc",
        "operator_id",
    )
    missing_metadata_fields = [
        field
        for field in metadata_fields
        if not _text(row.get(field)) or _text(row.get(field)).startswith("OPERATOR_FILL_")
    ]
    license_ok = _text(row.get("license_ok")).lower() in {"1", "true", "yes", "y"}
    approval_token_ok = _text(row.get("approval_token")) == APPROVAL_TOKEN
    blockers: list[str] = []
    if missing_score_fields:
        blockers.append("score_values_missing_or_invalid")
    if missing_metadata_fields:
        blockers.append("operator_metadata_missing_or_placeholder")
    if not license_ok:
        blockers.append("license_ok_pending")
    if not approval_token_ok:
        blockers.append("approval_token_pending")
    return {
        "pose_id": _text(row.get("pose_id")),
        "complex_id": _text(row.get("complex_id")),
        "status": "ready" if not blockers else "blocked",
        "score_values_ready": not missing_score_fields,
        "metadata_ready": not missing_metadata_fields,
        "license_ok": license_ok,
        "approval_token_ok": approval_token_ok,
        "blocker": ";".join(blockers),
    }


def build_public_benchmark_vina_gnina_score_template_receipt(
    *,
    work_order_json: str | Path = DEFAULT_WORK_ORDER_JSON,
    score_template_csv: str | Path = DEFAULT_SCORE_TEMPLATE_CSV,
    root: Path = ROOT,
) -> dict[str, Any]:
    work_order = _summary(_read_json(work_order_json, root=root))
    template_present, fieldnames, rows = _read_csv_rows(score_template_csv, root=root)
    validation = validate_vina_gnina_score_template(rows)
    row_checks = [_row_status(row) for row in rows]

    missing_columns = [field for field in SCORE_TEMPLATE_FIELDS if field not in fieldnames]
    work_order_present = bool(work_order)
    work_order_ready = _bool_true(work_order.get("work_order_ready"))
    expected_row_count = _int(work_order.get("pose_row_count"))
    row_count_match = bool(expected_row_count == 0 or expected_row_count == len(rows))
    template_path_match = (
        not _text(work_order.get("score_template_csv"))
        or _text(work_order.get("score_template_csv")) == _display(score_template_csv, root=root)
    )

    blockers: list[str] = []
    if not work_order_present:
        blockers.append(f"{_display(work_order_json, root=root)}:missing_or_invalid")
    elif not work_order_ready:
        blockers.append(f"{_display(work_order_json, root=root)}:work_order_ready_not_true")
    if not template_present:
        blockers.append(f"{_display(score_template_csv, root=root)}:missing")
    if missing_columns:
        blockers.append("score_template_required_columns_missing")
    if not row_count_match:
        blockers.append("score_template_row_count_mismatch")
    if not template_path_match:
        blockers.append("score_template_path_mismatch")
    blockers.extend(str(item) for item in validation["score_template_blockers"])

    ready = bool(
        template_present
        and work_order_present
        and work_order_ready
        and not missing_columns
        and row_count_match
        and template_path_match
        and validation["score_template_validation_ready"]
        and not blockers
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "public_benchmark_vina_gnina_score_template_receipt_ready"
            if ready
            else "blocked_public_benchmark_vina_gnina_score_template_receipt"
        ),
        "score_template_receipt_ready": ready,
        "comparison_score_evidence_ready": ready,
        "work_order_json": _display(work_order_json, root=root),
        "work_order_present": work_order_present,
        "work_order_ready": work_order_ready,
        "score_template_csv": _display(score_template_csv, root=root),
        "score_template_present": template_present,
        "score_template_sha256": _sha256_file(score_template_csv, root=root),
        "score_template_required_column_count": len(SCORE_TEMPLATE_FIELDS),
        "score_template_missing_column_count": len(missing_columns),
        "score_template_missing_columns": missing_columns,
        "score_template_row_count": len(rows),
        "expected_row_count": expected_row_count,
        "score_template_row_count_match": row_count_match,
        "score_template_path_match": template_path_match,
        "score_template_validation_ready": validation["score_template_validation_ready"],
        "score_template_filled_score_row_count": validation["score_template_filled_score_row_count"],
        "score_value_pending_count": validation["score_value_pending_count"],
        "invalid_score_value_count": validation["invalid_score_value_count"],
        "operator_metadata_pending_count": validation["operator_metadata_pending_count"],
        "operator_placeholder_pending_count": validation["operator_placeholder_pending_count"],
        "license_ok_pending_count": validation["license_ok_pending_count"],
        "approval_token_pending_count": validation["approval_token_pending_count"],
        "score_template_blocker_count": validation["score_template_blocker_count"],
        "score_template_blockers": validation["score_template_blockers"],
        "blocker_count": len(blockers),
        "blockers": blockers,
        "approval_token_required": APPROVAL_TOKEN,
        "adapter_command_after_fill": _text(work_order.get("adapter_command_after_fill")),
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            _text(work_order.get("adapter_command_after_fill"))
            if ready
            else "Fill every score-template row with same-input Vina/GNINA scores, review metadata, license_ok=true, and the approval token, then rebuild this receipt."
        ),
    }
    return {"summary": summary, "rows": row_checks}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Public Benchmark Vina/GNINA Score Template Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- score_template_receipt_ready: `{summary['score_template_receipt_ready']}`",
        f"- score_template_row_count: `{summary['score_template_row_count']}`",
        f"- score_template_filled_score_row_count: `{summary['score_template_filled_score_row_count']}`",
        f"- score_value_pending_count: `{summary['score_value_pending_count']}`",
        f"- operator_metadata_pending_count: `{summary['operator_metadata_pending_count']}`",
        f"- license_ok_pending_count: `{summary['license_ok_pending_count']}`",
        f"- approval_token_pending_count: `{summary['approval_token_pending_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        "",
        "| pose_id | status | blocker |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['pose_id']}` | `{row['status']}` | `{row['blocker'] or '-'}` |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate filled Vina/GNINA same-input public benchmark score CSV.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--score-template-csv", default=DEFAULT_SCORE_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_public_benchmark_vina_gnina_score_template_receipt(
        work_order_json=args.work_order_json,
        score_template_csv=args.score_template_csv,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
