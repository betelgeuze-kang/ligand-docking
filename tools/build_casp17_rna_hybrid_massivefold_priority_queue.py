#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ORGANIZER_NOTICE_PACKET_JSON = "casp17/casp17_organizer_notice_packet_current.json"
DEFAULT_MASSIVEFOLD_EXTERNAL_POOL_INTAKE_JSON = "casp17/casp17_massivefold_external_pool_intake_current.json"
DEFAULT_OUT_DIR = "casp17/rna_hybrid_massivefold_priority_queue"
DEFAULT_OUT_JSON = "casp17/casp17_rna_hybrid_massivefold_priority_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_rna_hybrid_massivefold_priority_queue_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_RNA_HYBRID_MASSIVEFOLD_PRIORITY_QUEUE.md"

TARGET_CATEGORY = "rna_or_hybrid"
READY_STATUS = "ready_for_rule_checked_external_pool_acquisition"
MODEL_POOL_POLICY = "external_rerank_accuracy_estimation_pool"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
DOWNLOAD_POLICY = "operator_explicit_download_required_no_automatic_tarball_fetch"
COMPETITIVE_PROOF_ELIGIBLE = "False"
R2345_SEQUENCE_GUARD = "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"

CLAIM_BOUNDARY = (
    "RNA/hybrid MassiveFold priority queue only. These rows are organizer-provided external model pools for "
    "rule-checked reranking and accuracy-estimation work. They are not internal predictions, not CASP submissions, "
    "and not competitive-proof evidence."
)

ROW_COLUMNS = [
    "queue_rank",
    "queue_id",
    "model_set_id",
    "primary_target_id",
    "target_category",
    "bundle_format",
    "ftp_filename",
    "ftp_size_bytes",
    "ftp_modified_hint",
    "massivefold_tarball_url",
    "pool_folder",
    "acquisition_manifest",
    "priority_folder",
    "priority_action_md",
    "priority_reason",
    "r2345_invalid_request_status",
    "r2345_active_request_status",
    "sequence_guard",
    "model_pool_policy",
    "internal_prediction_policy",
    "competitive_proof_eligible",
    "download_policy",
    "row_status",
    "next_action",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_").lower()
    return slug[:96] or "rna_hybrid_pool"


def _notice_by_target(organizer_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    notices = organizer_payload.get("notice_rows") or organizer_payload.get("rows")
    result: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(notices, list):
        return result
    for row in notices:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id"))
        if target_id:
            result.setdefault(target_id, []).append(row)
    return result


def _target_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    target_id = _text(row.get("primary_target_id"))
    special_priority = {"R2341": 0, "R2345": 1}
    if target_id in special_priority:
        return (0, special_priority[target_id], target_id)
    match = re.search(r"(\d+)", target_id)
    numeric = int(match.group(1)) if match else 999999
    return (1, numeric, target_id)


def _priority_reason(target_id: str) -> str:
    if target_id == "R2341":
        return "organizer_notice_first_rna_massivefold_set_available"
    if target_id == "R2345":
        return "corrected_1130_pacific_request_only_with_0930_invalid_dna_t_request_quarantined"
    return "rna_hybrid_massivefold_pool_from_organizer_ftp_listing"


def _r2345_notice_status(notices: dict[str, list[dict[str, Any]]], request_status: str) -> str:
    for row in notices.get("R2345", []):
        if _text(row.get("request_status")) == request_status:
            return request_status
    return ""


def _row_status(row: dict[str, Any], target_id: str) -> str:
    if not _text(row.get("massivefold_tarball_url")):
        return "blocked_missing_tarball_url"
    if _text(row.get("target_category")) != TARGET_CATEGORY:
        return "blocked_non_rna_hybrid_category"
    if target_id == "R2345" and _text(row.get("sequence_guard")) != R2345_SEQUENCE_GUARD:
        return "blocked_r2345_sequence_guard_missing"
    return READY_STATUS


def _priority_folder(base_dir: str | Path, queue_rank: int, target_id: str) -> Path:
    return _resolve(base_dir) / f"{queue_rank:02d}_{_safe_slug(target_id)}"


def _build_rows(
    intake_rows: list[dict[str, Any]],
    notices: dict[str, list[dict[str, Any]]],
    out_dir: str | Path,
) -> list[dict[str, Any]]:
    rna_rows = [
        row for row in intake_rows if _text(row.get("target_category")) == TARGET_CATEGORY
    ]
    sorted_rows = sorted(rna_rows, key=_target_sort_key)
    result: list[dict[str, Any]] = []
    invalid_status = _r2345_notice_status(notices, "ignored_invalid_dna_t_in_rna_sequence")
    active_status = _r2345_notice_status(notices, "accepted_second_request_only")
    for queue_rank, source in enumerate(sorted_rows, start=1):
        target_id = _text(source.get("primary_target_id"))
        folder = _priority_folder(out_dir, queue_rank, target_id)
        row = {
            "queue_rank": queue_rank,
            "queue_id": f"rna_hybrid_massivefold_priority_{queue_rank:03d}",
            "model_set_id": _text(source.get("model_set_id")),
            "primary_target_id": target_id,
            "target_category": _text(source.get("target_category")),
            "bundle_format": _text(source.get("bundle_format")),
            "ftp_filename": _text(source.get("ftp_filename")),
            "ftp_size_bytes": _int(source.get("ftp_size_bytes")),
            "ftp_modified_hint": _text(source.get("ftp_modified_hint")),
            "massivefold_tarball_url": _text(source.get("massivefold_tarball_url")),
            "pool_folder": _text(source.get("pool_folder")),
            "acquisition_manifest": _text(source.get("acquisition_manifest")),
            "priority_folder": _artifact(folder),
            "priority_action_md": _artifact(folder / "PRIORITY_ACTION.md"),
            "priority_reason": _priority_reason(target_id),
            "r2345_invalid_request_status": invalid_status if target_id == "R2345" else "",
            "r2345_active_request_status": active_status if target_id == "R2345" else "",
            "sequence_guard": _text(source.get("sequence_guard")),
            "model_pool_policy": _text(source.get("model_pool_policy")) or MODEL_POOL_POLICY,
            "internal_prediction_policy": _text(source.get("internal_prediction_policy"))
            or INTERNAL_PREDICTION_POLICY,
            "competitive_proof_eligible": _text(source.get("competitive_proof_eligible"))
            or COMPETITIVE_PROOF_ELIGIBLE,
            "download_policy": _text(source.get("download_policy")) or DOWNLOAD_POLICY,
            "row_status": "",
            "next_action": "",
        }
        row["row_status"] = _row_status(row, target_id)
        row["next_action"] = (
            "rule-check external MassiveFold use, download only into the external-pool folder, hash the tarball, "
            "extract a listing, then run rerank/accuracy-estimation experiments without internal-proof claims"
        )
        result.append(row)
    return result


def _status(
    organizer_exists: bool,
    intake_exists: bool,
    rows: list[dict[str, Any]],
) -> str:
    if not organizer_exists:
        return "blocked_organizer_notice_packet_missing"
    if not intake_exists:
        return "blocked_massivefold_external_pool_intake_missing"
    if not rows:
        return "blocked_rna_hybrid_massivefold_pools_missing"
    if any(row["row_status"].startswith("blocked") for row in rows):
        return "blocked_rna_hybrid_massivefold_priority_queue"
    return "rna_hybrid_massivefold_priority_queue_ready"


def _build_summary(
    args: argparse.Namespace,
    organizer_payload: dict[str, Any],
    intake_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    organizer_exists: bool,
    intake_exists: bool,
) -> dict[str, Any]:
    organizer_summary = _summary(organizer_payload)
    intake_summary = _summary(intake_payload)
    ready_rows = [row for row in rows if row["row_status"] == READY_STATUS]
    blocked_rows = [row for row in rows if row["row_status"].startswith("blocked")]
    r2341 = next((row for row in rows if row["primary_target_id"] == "R2341"), {})
    r2345 = next((row for row in rows if row["primary_target_id"] == "R2345"), {})
    first = rows[0] if rows else {}
    return {
        "packet_type": "casp17_rna_hybrid_massivefold_priority_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "rna_hybrid_massivefold_priority_queue_status": _status(organizer_exists, intake_exists, rows),
        "organizer_notice_packet_json": _artifact(args.organizer_notice_packet_json),
        "organizer_notice_status": _text(organizer_summary.get("organizer_notice_status")),
        "massivefold_external_pool_intake_json": _artifact(args.massivefold_external_pool_intake_json),
        "massivefold_external_pool_intake_status": _text(
            intake_summary.get("massivefold_external_pool_intake_status")
        ),
        "queue_row_count": len(rows),
        "ready_queue_row_count": len(ready_rows),
        "blocked_queue_row_count": len(blocked_rows),
        "r2341_queue_rank": _int(r2341.get("queue_rank")),
        "r2345_queue_rank": _int(r2345.get("queue_rank")),
        "r2341_pool_present": bool(r2341),
        "r2345_pool_present": bool(r2345),
        "r2345_invalid_request_status": _text(r2345.get("r2345_invalid_request_status")),
        "r2345_active_request_status": _text(r2345.get("r2345_active_request_status")),
        "r2345_sequence_guard": _text(r2345.get("sequence_guard")) or R2345_SEQUENCE_GUARD,
        "r2345_invalid_request_quarantined": (
            _text(r2345.get("r2345_invalid_request_status")) == "ignored_invalid_dna_t_in_rna_sequence"
        ),
        "first_priority_target_id": _text(first.get("primary_target_id")),
        "first_priority_reason": _text(first.get("priority_reason")),
        "total_declared_size_bytes": sum(_int(row.get("ftp_size_bytes")) for row in rows),
        "competitive_proof_eligible_count": sum(
            1 for row in rows if _text(row.get("competitive_proof_eligible")) == "True"
        ),
        "internal_prediction_blocked_count": sum(
            1 for row in rows if _text(row.get("internal_prediction_policy")) == INTERNAL_PREDICTION_POLICY
        ),
        "download_policy": DOWNLOAD_POLICY,
        "model_pool_policy": MODEL_POOL_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "out_dir": _artifact(args.out_dir),
        "first_blocked_target_id": _text(blocked_rows[0].get("primary_target_id")) if blocked_rows else "",
        "first_blocked_status": _text(blocked_rows[0].get("row_status")) if blocked_rows else "",
        "next_action": (
            "start with R2341 for rule-checked external-pool acquisition and reranking; keep the R2345 09:30 "
            "Pacific DNA-T request quarantined and validate only the 11:30 Pacific RNA request before use"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    organizer_path = _resolve(args.organizer_notice_packet_json)
    intake_path = _resolve(args.massivefold_external_pool_intake_json)
    organizer_payload = _read_json(organizer_path)
    intake_payload = _read_json(intake_path)
    rows = _build_rows(_rows(intake_payload), _notice_by_target(organizer_payload), args.out_dir)
    summary = _build_summary(
        args,
        organizer_payload,
        intake_payload,
        rows,
        organizer_path.exists(),
        intake_path.exists(),
    )
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_priority_action(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['primary_target_id']} RNA/Hybrid MassiveFold Priority Action",
        "",
        f"- queue_rank: `{row['queue_rank']}`",
        f"- queue_id: `{row['queue_id']}`",
        f"- model_set_id: `{row['model_set_id']}`",
        f"- priority_reason: `{row['priority_reason']}`",
        f"- row_status: `{row['row_status']}`",
        f"- tarball_url: `{row['massivefold_tarball_url']}`",
        f"- acquisition_manifest: `{row['acquisition_manifest'] or '-'}`",
        f"- sequence_guard: `{row['sequence_guard'] or '-'}`",
        f"- r2345_invalid_request_status: `{row['r2345_invalid_request_status'] or '-'}`",
        f"- r2345_active_request_status: `{row['r2345_active_request_status'] or '-'}`",
        f"- internal_prediction_policy: `{row['internal_prediction_policy']}`",
        f"- competitive_proof_eligible: `{row['competitive_proof_eligible']}`",
        f"- download_policy: `{row['download_policy']}`",
        "",
        "## Next Action",
        "",
        row["next_action"],
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["priority_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PRIORITY_ACTION.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "priority_queue_row.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 RNA/Hybrid MassiveFold Priority Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['rna_hybrid_massivefold_priority_queue_status']}`",
        f"- queue rows ready/blocked/total: `{summary['ready_queue_row_count']}/{summary['blocked_queue_row_count']}/{summary['queue_row_count']}`",
        f"- first priority: `{summary['first_priority_target_id'] or '-'}` `{summary['first_priority_reason'] or '-'}`",
        f"- R2341 rank/present: `{summary['r2341_queue_rank']}`/`{summary['r2341_pool_present']}`",
        f"- R2345 rank/present: `{summary['r2345_queue_rank']}`/`{summary['r2345_pool_present']}`",
        f"- R2345 invalid/active/guard: `{summary['r2345_invalid_request_status'] or '-'}`/`{summary['r2345_active_request_status'] or '-'}`/`{summary['r2345_sequence_guard']}`",
        f"- proof/internal-blocked: `{summary['competitive_proof_eligible_count']}/{summary['internal_prediction_blocked_count']}`",
        f"- total declared size bytes: `{summary['total_declared_size_bytes']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Queue",
        "",
        "| rank | target | model_set | status | reason | size_bytes | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['queue_rank']}` | `{row['primary_target_id']}` | `{row['model_set_id']}` | "
            f"`{row['row_status']}` | `{row['priority_reason']}` | `{row['ftp_size_bytes']}` | "
            f"`{row['priority_action_md']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_rna_hybrid_massivefold_pools_missing` | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_priority_action(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 RNA/hybrid MassiveFold priority queue.")
    parser.add_argument("--organizer-notice-packet-json", default=DEFAULT_ORGANIZER_NOTICE_PACKET_JSON)
    parser.add_argument(
        "--massivefold-external-pool-intake-json",
        default=DEFAULT_MASSIVEFOLD_EXTERNAL_POOL_INTAKE_JSON,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
