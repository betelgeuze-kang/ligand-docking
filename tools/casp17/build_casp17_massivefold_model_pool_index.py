#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACQUISITION_VERIFICATION_JSON = (
    "casp17/casp17_massivefold_acquisition_verification_board_current.json"
)
DEFAULT_TARGET_ID = "R2341"
DEFAULT_OUT_DIR = "casp17/massivefold_model_pool_index"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model_pool_index_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model_pool_index_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL_POOL_INDEX.md"

CLAIM_BOUNDARY = (
    "MassiveFold model pool index only. It parses organizer-provided external model tarball listings and stages "
    "balanced extraction/rerank candidates. These models remain external rerank and accuracy-estimation inputs, "
    "not internal predictions, not CASP submissions, and not competitive-proof evidence."
)

ROW_COLUMNS = [
    "pool_rank",
    "target_id",
    "model_set_id",
    "model_rank",
    "tar_member_path",
    "filename",
    "model_serial",
    "af_engine",
    "af_protocol",
    "seed",
    "sample",
    "pred",
    "rerank_bucket",
    "selection_rank",
    "selected_for_balanced_extract",
    "extract_destination",
    "extraction_status",
    "claim_boundary",
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
    return slug[:96] or "model"


def _verified_pool(rows: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("primary_target_id")) == target_id:
            return row
    return {}


def _parse_model_member(member: str) -> dict[str, Any] | None:
    filename = Path(member).name
    if not filename.lower().endswith((".cif", ".mmcif", ".pdb")):
        return None
    af3_pattern = re.compile(
        r"^Model_(?P<serial>\d+)_(?P<protocol>.+?)_af3_seed_(?P<seed>\d+)_sample_(?P<sample>\d+)_pred_(?P<pred>\d+)\.(?P<ext>cif|mmcif|pdb)$",
        re.IGNORECASE,
    )
    match = af3_pattern.match(filename)
    if match:
        protocol = match.group("protocol")
        return {
            "filename": filename,
            "model_serial": _int(match.group("serial")),
            "af_engine": "AF3",
            "af_protocol": protocol,
            "seed": _int(match.group("seed")),
            "sample": _int(match.group("sample")),
            "pred": _int(match.group("pred")),
            "rerank_bucket": protocol.replace("af3_", "", 1),
        }
    multimer_pattern = re.compile(
        r"^Model_(?P<serial>\d+)_(?P<engine>afm|cf)_(?P<protocol>.+?)_model_(?P<model>\d+)_multimer_v(?P<version>\d+)_pred_(?P<pred>\d+)\.(?P<ext>pdb|cif|mmcif)$",
        re.IGNORECASE,
    )
    match = multimer_pattern.match(filename)
    if match:
        engine = match.group("engine").upper()
        protocol = match.group("protocol")
        version = _int(match.group("version"))
        return {
            "filename": filename,
            "model_serial": _int(match.group("serial")),
            "af_engine": engine,
            "af_protocol": f"{engine.lower()}_{protocol}_multimer_v{version}",
            "seed": "",
            "sample": _int(match.group("model")),
            "pred": _int(match.group("pred")),
            "rerank_bucket": f"{engine.lower()}_{protocol}_v{version}",
        }
    if not match:
        return {
            "filename": filename,
            "model_serial": "",
            "af_engine": "unknown",
            "af_protocol": "unknown",
            "seed": "",
            "sample": "",
            "pred": "",
            "rerank_bucket": "unknown",
        }


def _read_listing(path_like: str) -> list[str]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def _select_balanced(rows: list[dict[str, Any]], per_bucket: int) -> set[int]:
    selected: set[int] = set()
    counts: Counter[str] = Counter()
    ordered = sorted(rows, key=lambda row: (_int(row.get("model_serial"), 999999), _int(row.get("model_rank"))))
    for row in ordered:
        bucket = _text(row.get("rerank_bucket")) or "unknown"
        if counts[bucket] >= per_bucket:
            continue
        selected.add(_int(row.get("model_rank")))
        counts[bucket] += 1
    return selected


def _build_rows(pool_row: dict[str, Any], target_id: str, out_dir: str | Path, per_bucket: int) -> list[dict[str, Any]]:
    if _text(pool_row.get("pool_verification_status")) != "verified_for_external_rerank_intake":
        return []
    listing_path = _text(pool_row.get("listing_path"))
    extract_root = _resolve(_text(pool_row.get("listing_path"))).parent
    model_rows: list[dict[str, Any]] = []
    model_set_id = _text(pool_row.get("model_set_id")) or target_id
    for model_rank, member in enumerate(_read_listing(listing_path), start=1):
        parsed = _parse_model_member(member)
        if parsed is None:
            continue
        destination = extract_root / member
        row = {
            "pool_rank": _int(pool_row.get("queue_rank")),
            "target_id": target_id,
            "model_set_id": model_set_id,
            "model_rank": len(model_rows) + 1,
            "tar_member_path": member,
            "filename": parsed["filename"],
            "model_serial": parsed["model_serial"],
            "af_engine": parsed["af_engine"],
            "af_protocol": parsed["af_protocol"],
            "seed": parsed["seed"],
            "sample": parsed["sample"],
            "pred": parsed["pred"],
            "rerank_bucket": parsed["rerank_bucket"],
            "selection_rank": "",
            "selected_for_balanced_extract": "False",
            "extract_destination": _artifact(destination),
            "extraction_status": "extracted" if destination.exists() else "awaiting_extract",
            "claim_boundary": CLAIM_BOUNDARY,
        }
        model_rows.append(row)
    selected = _select_balanced(model_rows, per_bucket)
    selection_rank = 0
    for row in model_rows:
        if _int(row.get("model_rank")) in selected:
            selection_rank += 1
            row["selected_for_balanced_extract"] = "True"
            row["selection_rank"] = selection_rank
    return model_rows


def _status(input_exists: bool, pool_row: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_massivefold_acquisition_verification_missing"
    if not pool_row:
        return "blocked_target_pool_missing"
    if _text(pool_row.get("pool_verification_status")) != "verified_for_external_rerank_intake":
        return "blocked_target_pool_not_verified"
    if not rows:
        return "blocked_model_listing_missing"
    selected = [row for row in rows if row["selected_for_balanced_extract"] == "True"]
    if selected and all(row["extraction_status"] == "extracted" for row in selected):
        return "massivefold_model_pool_representatives_extracted"
    return "massivefold_model_pool_index_ready_extract_pending"


def _write_extraction_manifest(out_dir: str | Path, target_id: str, rows: list[dict[str, Any]]) -> str:
    selected = [row for row in rows if row["selected_for_balanced_extract"] == "True"]
    path = _resolve(out_dir) / target_id.lower() / "balanced_extract_members.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(row["tar_member_path"] for row in selected) + ("\n" if selected else ""), encoding="utf-8")
    return _artifact(path)


def _write_bucket_csvs(out_dir: str | Path, target_id: str, rows: list[dict[str, Any]]) -> int:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("rerank_bucket")), []).append(row)
    root = _resolve(out_dir) / target_id.lower() / "protocol_buckets"
    for bucket, bucket_rows in sorted(grouped.items()):
        safe = _safe_slug(bucket)
        _write_csv(root / f"{safe}.csv", bucket_rows, ROW_COLUMNS)
    return len(grouped)


def _build_summary(
    args: argparse.Namespace,
    acquisition_payload: dict[str, Any],
    pool_row: dict[str, Any],
    rows: list[dict[str, Any]],
    input_exists: bool,
    extraction_manifest: str,
    bucket_file_count: int,
) -> dict[str, Any]:
    acquisition_summary = _summary(acquisition_payload)
    protocol_counts = Counter(_text(row.get("rerank_bucket")) for row in rows)
    selected = [row for row in rows if row["selected_for_balanced_extract"] == "True"]
    extracted_selected = [row for row in selected if row["extraction_status"] == "extracted"]
    first_selected = selected[0] if selected else {}
    return {
        "packet_type": "casp17_massivefold_model_pool_index",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model_pool_index_status": _status(input_exists, pool_row, rows),
        "target_id": args.target_id,
        "acquisition_verification_json": _artifact(args.acquisition_verification_json),
        "acquisition_verification_status": _text(
            acquisition_summary.get("massivefold_acquisition_verification_status")
        ),
        "target_pool_verification_status": _text(pool_row.get("pool_verification_status")),
        "tarball_sha256": _text(pool_row.get("sha256_actual")) or _text(pool_row.get("sha256_recorded")),
        "tarball_path": _text(pool_row.get("download_path")),
        "listing_path": _text(pool_row.get("listing_path")),
        "model_count": len(rows),
        "protocol_bucket_count": len(protocol_counts),
        "protocol_bucket_file_count": bucket_file_count,
        "selected_extract_count": len(selected),
        "selected_extracted_count": len(extracted_selected),
        "selected_extract_pending_count": len(selected) - len(extracted_selected),
        "first_selected_model": _text(first_selected.get("filename")),
        "first_selected_protocol": _text(first_selected.get("rerank_bucket")),
        "basic_count": protocol_counts["basic"],
        "wo_templates_count": protocol_counts["woTemplates"],
        "wo_unpaired_count": protocol_counts["woUnpaired"],
        "wo_paired_count": protocol_counts["woPaired"],
        "wo_unpaired_wo_paired_count": protocol_counts["woUnpaired_woPaired"],
        "wo_unpaired_wo_templates_count": protocol_counts["woUnpaired_woTemplates"],
        "wo_paired_wo_templates_count": protocol_counts["woPaired_woTemplates"],
        "wo_unpaired_wo_paired_wo_templates_count": protocol_counts["woUnpaired_woPaired_woTemplates"],
        "extraction_manifest": extraction_manifest,
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "extract the balanced representative member list from the verified tarball, then run external "
            "rerank and accuracy-estimation calibration without internal-proof claims"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.acquisition_verification_json)
    acquisition_payload = _read_json(input_path)
    pool_row = _verified_pool(_rows(acquisition_payload), args.target_id)
    rows = _build_rows(pool_row, args.target_id, args.out_dir, args.extract_per_bucket)
    extraction_manifest = _write_extraction_manifest(args.out_dir, args.target_id, rows)
    bucket_file_count = _write_bucket_csvs(args.out_dir, args.target_id, rows)
    summary = _build_summary(
        args,
        acquisition_payload,
        pool_row,
        rows,
        input_path.exists(),
        extraction_manifest,
        bucket_file_count,
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


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    selected = [row for row in payload["rows"] if row["selected_for_balanced_extract"] == "True"]
    lines = [
        "# CASP17 MassiveFold Model Pool Index",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model_pool_index_status']}`",
        f"- target: `{summary['target_id']}`",
        f"- models/protocols: `{summary['model_count']}/{summary['protocol_bucket_count']}`",
        f"- selected/extracted/pending: `{summary['selected_extract_count']}/{summary['selected_extracted_count']}/{summary['selected_extract_pending_count']}`",
        f"- protocol counts basic/woTemplates/woUnpaired/woPaired: `{summary['basic_count']}/{summary['wo_templates_count']}/{summary['wo_unpaired_count']}/{summary['wo_paired_count']}`",
        f"- combined protocol counts woUnpaired_woPaired/woUnpaired_woTemplates/woPaired_woTemplates/all3: `{summary['wo_unpaired_wo_paired_count']}/{summary['wo_unpaired_wo_templates_count']}/{summary['wo_paired_wo_templates_count']}/{summary['wo_unpaired_wo_paired_wo_templates_count']}`",
        f"- extraction manifest: `{summary['extraction_manifest']}`",
        f"- tarball sha256: `{summary['tarball_sha256'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Balanced Extract Representatives",
        "",
        "| selection | model | protocol | seed | sample | pred | status | member |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in selected:
        lines.append(
            f"| `{row['selection_rank']}` | `{row['filename']}` | `{row['rerank_bucket']}` | "
            f"`{row['seed']}` | `{row['sample']}` | `{row['pred']}` | `{row['extraction_status']}` | "
            f"`{row['tar_member_path']}` |"
        )
    if not selected:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 MassiveFold model-pool index from a verified tarball listing.")
    parser.add_argument("--acquisition-verification-json", default=DEFAULT_ACQUISITION_VERIFICATION_JSON)
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--extract-per-bucket", type=int, default=5)
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
