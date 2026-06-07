#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ORGANIZER_NOTICE_PACKET_JSON = "casp17/casp17_organizer_notice_packet_current.json"
DEFAULT_MASSIVEFOLD_EXTERNAL_POOL_INTAKE_JSON = "casp17/casp17_massivefold_external_pool_intake_current.json"
DEFAULT_OUT_DIR = "casp17/protein_complex_massivefold_priority_queue"
DEFAULT_OUT_JSON = "casp17/casp17_protein_complex_massivefold_priority_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_protein_complex_massivefold_priority_queue_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_PROTEIN_COMPLEX_MASSIVEFOLD_PRIORITY_QUEUE.md"

TARGET_CATEGORY = "protein_or_complex"
READY_STATUS = "ready_for_rule_checked_external_pool_acquisition"
MODEL_POOL_POLICY = "external_rerank_accuracy_estimation_pool"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
DOWNLOAD_POLICY = "operator_explicit_download_required_no_automatic_tarball_fetch"
COMPETITIVE_PROOF_ELIGIBLE = "False"

CLAIM_BOUNDARY = (
    "Protein/complex MassiveFold priority queue only. These rows are organizer-provided external model pools for "
    "rule-checked reranking and accuracy-estimation work on CASP17 protein, immune, and complex targets. They are "
    "not internal predictions, not CASP submissions, and not competitive-proof evidence."
)

ROW_COLUMNS = [
    "queue_rank",
    "queue_id",
    "pool_id",
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
    return slug[:96] or "protein_complex_pool"


def _pool_rank(row: dict[str, Any]) -> tuple[int, str, str]:
    pool_id = _text(row.get("pool_id"))
    match = re.search(r"(\d+)$", pool_id)
    pool_rank = int(match.group(1)) if match else 999999
    return (pool_rank, _text(row.get("model_set_id")), _text(row.get("primary_target_id")))


def _priority_reason(row: dict[str, Any]) -> str:
    target_id = _text(row.get("primary_target_id"))
    model_set = _text(row.get("model_set_id"))
    if target_id.startswith("H"):
        return "protein_heteromer_or_immune_complex_massivefold_pool_from_organizer_ftp_listing"
    if target_id.startswith("T"):
        return "protein_target_massivefold_pool_from_organizer_ftp_listing"
    return f"protein_complex_massivefold_pool_from_organizer_ftp_listing:{model_set}"


def _row_status(row: dict[str, Any]) -> str:
    if not _text(row.get("massivefold_tarball_url")):
        return "blocked_missing_tarball_url"
    if _text(row.get("target_category")) != TARGET_CATEGORY:
        return "blocked_non_protein_complex_category"
    return READY_STATUS


def _priority_folder(base_dir: str | Path, queue_rank: int, model_set_id: str) -> Path:
    return _resolve(base_dir) / f"{queue_rank:02d}_{_safe_slug(model_set_id)}"


def _build_rows(intake_rows: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    protein_rows = [
        row for row in intake_rows if _text(row.get("target_category")) == TARGET_CATEGORY
    ]
    sorted_rows = sorted(protein_rows, key=_pool_rank)
    result: list[dict[str, Any]] = []
    for queue_rank, source in enumerate(sorted_rows, start=1):
        model_set_id = _text(source.get("model_set_id"))
        folder = _priority_folder(out_dir, queue_rank, model_set_id)
        row = {
            "queue_rank": queue_rank,
            "queue_id": f"protein_complex_massivefold_priority_{queue_rank:03d}",
            "pool_id": _text(source.get("pool_id")),
            "model_set_id": model_set_id,
            "primary_target_id": _text(source.get("primary_target_id")),
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
            "priority_reason": _priority_reason(source),
            "model_pool_policy": _text(source.get("model_pool_policy")) or MODEL_POOL_POLICY,
            "internal_prediction_policy": _text(source.get("internal_prediction_policy"))
            or INTERNAL_PREDICTION_POLICY,
            "competitive_proof_eligible": _text(source.get("competitive_proof_eligible"))
            or COMPETITIVE_PROOF_ELIGIBLE,
            "download_policy": _text(source.get("download_policy")) or DOWNLOAD_POLICY,
            "row_status": "",
            "next_action": "",
        }
        row["row_status"] = _row_status(row)
        row["next_action"] = (
            "rule-check external MassiveFold use, download only into the external-pool folder, hash the tarball, "
            "extract a listing, then run protein/complex rerank and accuracy-estimation experiments without "
            "internal-proof claims"
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
        return "blocked_protein_complex_massivefold_pools_missing"
    if any(row["row_status"].startswith("blocked") for row in rows):
        return "blocked_protein_complex_massivefold_priority_queue"
    return "protein_complex_massivefold_priority_queue_ready"


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
    first = rows[0] if rows else {}
    largest = max(rows, key=lambda row: _int(row.get("ftp_size_bytes")), default={})
    return {
        "packet_type": "casp17_protein_complex_massivefold_priority_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "protein_complex_massivefold_priority_queue_status": _status(
            organizer_exists, intake_exists, rows
        ),
        "organizer_notice_packet_json": _artifact(args.organizer_notice_packet_json),
        "organizer_notice_status": _text(organizer_summary.get("organizer_notice_status")),
        "massivefold_external_pool_intake_json": _artifact(args.massivefold_external_pool_intake_json),
        "massivefold_external_pool_intake_status": _text(
            intake_summary.get("massivefold_external_pool_intake_status")
        ),
        "queue_row_count": len(rows),
        "ready_queue_row_count": len(ready_rows),
        "blocked_queue_row_count": len(blocked_rows),
        "first_priority_target_id": _text(first.get("primary_target_id")),
        "first_priority_model_set_id": _text(first.get("model_set_id")),
        "first_priority_reason": _text(first.get("priority_reason")),
        "largest_model_set_id": _text(largest.get("model_set_id")),
        "largest_pool_size_bytes": _int(largest.get("ftp_size_bytes")),
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
            "start with the first protein/complex MassiveFold pool, preserve external provenance, and use these "
            "models only for rerank/accuracy-estimation until CASP use rules are checked"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    organizer_path = _resolve(args.organizer_notice_packet_json)
    intake_path = _resolve(args.massivefold_external_pool_intake_json)
    organizer_payload = _read_json(organizer_path)
    intake_payload = _read_json(intake_path)
    rows = _build_rows(_rows(intake_payload), args.out_dir)
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
        f"# {row['primary_target_id']} Protein/Complex MassiveFold Priority Action",
        "",
        f"- queue_rank: `{row['queue_rank']}`",
        f"- queue_id: `{row['queue_id']}`",
        f"- pool_id: `{row['pool_id']}`",
        f"- model_set_id: `{row['model_set_id']}`",
        f"- priority_reason: `{row['priority_reason']}`",
        f"- row_status: `{row['row_status']}`",
        f"- tarball_url: `{row['massivefold_tarball_url']}`",
        f"- acquisition_manifest: `{row['acquisition_manifest'] or '-'}`",
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
        "# CASP17 Protein/Complex MassiveFold Priority Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['protein_complex_massivefold_priority_queue_status']}`",
        f"- queue rows ready/blocked/total: `{summary['ready_queue_row_count']}/{summary['blocked_queue_row_count']}/{summary['queue_row_count']}`",
        f"- first priority: `{summary['first_priority_target_id'] or '-'}` `{summary['first_priority_model_set_id'] or '-'}` `{summary['first_priority_reason'] or '-'}`",
        f"- largest pool: `{summary['largest_model_set_id'] or '-'}` bytes `{summary['largest_pool_size_bytes']}`",
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
        lines.append("| - | - | - | `blocked_protein_complex_massivefold_pools_missing` | - | - | - |")
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
    parser = argparse.ArgumentParser(description="Build CASP17 protein/complex MassiveFold priority queue.")
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
