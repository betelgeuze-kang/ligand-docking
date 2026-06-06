#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PRIORITY_QUEUE_JSON = "casp17/casp17_rna_hybrid_massivefold_priority_queue_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_acquisition_verification_board"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_acquisition_verification_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_acquisition_verification_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_ACQUISITION_VERIFICATION_BOARD.md"

VERIFIED_STATUS = "verified_for_external_rerank_intake"
DOWNLOAD_POLICY = "download_only_to_external_pool_lane_and_preserve_hash_listing"
CLAIM_BOUNDARY = (
    "MassiveFold acquisition verification board only. It checks local tarball, hash, and listing evidence for "
    "organizer-provided external model pools. These structures remain external rerank/accuracy-estimation pools, "
    "not internal predictions, not CASP submissions, and not competitive-proof evidence."
)

ROW_COLUMNS = [
    "queue_rank",
    "model_set_id",
    "primary_target_id",
    "target_category",
    "ftp_filename",
    "ftp_size_bytes",
    "massivefold_tarball_url",
    "pool_folder",
    "download_path",
    "sha256_path",
    "listing_path",
    "action_folder",
    "action_md",
    "tarball_status",
    "tarball_size_bytes",
    "size_status",
    "sha256_status",
    "sha256_recorded",
    "sha256_actual",
    "listing_status",
    "listing_entry_count",
    "pool_verification_status",
    "download_policy",
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_recorded_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").split()[0].strip()
    except (OSError, IndexError):
        return ""


def _listing_entry_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip().lower().endswith((".cif", ".pdb", ".mmcif"))
        )
    except OSError:
        return 0


def _action_folder(base_dir: str | Path, row: dict[str, Any]) -> Path:
    rank = _int(row.get("queue_rank"))
    target = _text(row.get("primary_target_id")) or _text(row.get("model_set_id")) or "pool"
    return _resolve(base_dir) / f"{rank:02d}_{target.lower()}"


def _derive_paths(source: dict[str, Any]) -> tuple[str, str, str]:
    pool_folder = _text(source.get("pool_folder"))
    filename = _text(source.get("ftp_filename"))
    download_path = _text(source.get("download_path")) or f"{pool_folder}/downloads/{filename}"
    sha256_path = f"{pool_folder}/hashes/{filename}.sha256"
    listing_path = f"{pool_folder}/extracted_models/tarball_listing.txt"
    return download_path, sha256_path, listing_path


def _sha256_status(
    *,
    tarball_path: Path,
    sha256_path: Path,
    actual_size: int,
    max_hash_bytes: int,
) -> tuple[str, str, str]:
    recorded = _read_recorded_sha256(sha256_path)
    if not tarball_path.exists():
        return "awaiting_tarball", recorded, ""
    if not recorded:
        return "open_sha256_record_required", "", ""
    if actual_size > max_hash_bytes:
        return "sha256_record_present_unverified_large_file", recorded, ""
    actual = _sha256_file(tarball_path)
    if actual == recorded:
        return "sha256_match", recorded, actual
    return "blocked_sha256_mismatch", recorded, actual


def _pool_status(tarball_status: str, size_status: str, sha256_status: str, listing_status: str) -> str:
    if tarball_status != "tarball_present":
        return "open_tarball_download_required"
    if size_status != "size_matches_declared":
        return "blocked_tarball_size_mismatch"
    if sha256_status == "blocked_sha256_mismatch":
        return "blocked_sha256_mismatch"
    if sha256_status in {"open_sha256_record_required", "awaiting_tarball"}:
        return "open_sha256_record_required"
    if listing_status != "tarball_listing_present":
        return "open_tarball_listing_required"
    return VERIFIED_STATUS


def _next_action(status: str) -> str:
    if status == "open_tarball_download_required":
        return "download the tarball into the external-pool downloads folder, then record sha256 and tarball listing"
    if status == "blocked_tarball_size_mismatch":
        return "replace the partial or mismatched tarball with the declared FTP tarball before using this pool"
    if status == "blocked_sha256_mismatch":
        return "quarantine the tarball and redownload before any rerank or accuracy-estimation use"
    if status == "open_sha256_record_required":
        return "run sha256sum on the local tarball and store it in the hashes folder"
    if status == "open_tarball_listing_required":
        return "run tar -tzf on the local tarball and save extracted_models/tarball_listing.txt"
    return "pool may be used only as an external rerank/accuracy-estimation input with provenance preserved"


def _build_rows(priority_rows: list[dict[str, Any]], out_dir: str | Path, max_hash_bytes: int) -> list[dict[str, Any]]:
    sorted_rows = sorted(priority_rows, key=lambda row: _int(row.get("queue_rank")))
    rows: list[dict[str, Any]] = []
    for source in sorted_rows:
        download_path, sha256_path, listing_path = _derive_paths(source)
        tarball = _resolve(download_path)
        sha_path = _resolve(sha256_path)
        listing = _resolve(listing_path)
        expected_size = _int(source.get("ftp_size_bytes"))
        actual_size = tarball.stat().st_size if tarball.exists() else 0
        tarball_status = "tarball_present" if tarball.exists() else "awaiting_tarball_download"
        size_status = (
            "size_matches_declared"
            if tarball.exists() and (expected_size == 0 or actual_size == expected_size)
            else "awaiting_tarball_size_check"
            if not tarball.exists()
            else "blocked_size_mismatch"
        )
        sha_status, sha_recorded, sha_actual = _sha256_status(
            tarball_path=tarball,
            sha256_path=sha_path,
            actual_size=actual_size,
            max_hash_bytes=max_hash_bytes,
        )
        listing_count = _listing_entry_count(listing)
        listing_status = "tarball_listing_present" if listing.exists() else "awaiting_tarball_listing"
        status = _pool_status(tarball_status, size_status, sha_status, listing_status)
        action_folder = _action_folder(out_dir, source)
        rows.append(
            {
                "queue_rank": _int(source.get("queue_rank")),
                "model_set_id": _text(source.get("model_set_id")),
                "primary_target_id": _text(source.get("primary_target_id")),
                "target_category": _text(source.get("target_category")),
                "ftp_filename": _text(source.get("ftp_filename")),
                "ftp_size_bytes": expected_size,
                "massivefold_tarball_url": _text(source.get("massivefold_tarball_url")),
                "pool_folder": _text(source.get("pool_folder")),
                "download_path": _artifact(download_path),
                "sha256_path": _artifact(sha256_path),
                "listing_path": _artifact(listing_path),
                "action_folder": _artifact(action_folder),
                "action_md": _artifact(action_folder / "ACQUISITION_VERIFICATION.md"),
                "tarball_status": tarball_status,
                "tarball_size_bytes": actual_size,
                "size_status": size_status,
                "sha256_status": sha_status,
                "sha256_recorded": sha_recorded,
                "sha256_actual": sha_actual,
                "listing_status": listing_status,
                "listing_entry_count": listing_count,
                "pool_verification_status": status,
                "download_policy": DOWNLOAD_POLICY,
                "next_action": _next_action(status),
            }
        )
    return rows


def _status(input_exists: bool, rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_massivefold_priority_queue_missing"
    if not rows:
        return "blocked_no_massivefold_priority_pools"
    if all(row["pool_verification_status"] == VERIFIED_STATUS for row in rows):
        return "massivefold_external_pool_acquisition_verified"
    return "awaiting_massivefold_external_pool_acquisition"


def _priority_queue_status(priority_summary: dict[str, Any]) -> str:
    status_keys = (
        "rna_hybrid_massivefold_priority_queue_status",
        "protein_complex_massivefold_priority_queue_status",
    )
    for key in status_keys:
        status = _text(priority_summary.get(key))
        if status:
            return status
    return _text(priority_summary.get("priority_queue_status"))


def _build_summary(
    args: argparse.Namespace,
    priority_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    input_exists: bool,
) -> dict[str, Any]:
    priority_summary = _summary(priority_payload)
    verified_rows = [row for row in rows if row["pool_verification_status"] == VERIFIED_STATUS]
    open_rows = [row for row in rows if row["pool_verification_status"] != VERIFIED_STATUS]
    first_open = open_rows[0] if open_rows else {}
    first_priority = rows[0] if rows else {}
    return {
        "packet_type": "casp17_massivefold_acquisition_verification_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_acquisition_verification_status": _status(input_exists, rows),
        "priority_queue_json": _artifact(args.priority_queue_json),
        "priority_queue_status": _priority_queue_status(priority_summary),
        "acquisition_pool_count": len(rows),
        "verified_pool_count": len(verified_rows),
        "open_acquisition_action_count": len(open_rows),
        "tarball_present_count": sum(1 for row in rows if row["tarball_status"] == "tarball_present"),
        "size_match_count": sum(1 for row in rows if row["size_status"] == "size_matches_declared"),
        "sha256_record_present_count": sum(1 for row in rows if row["sha256_recorded"]),
        "sha256_verified_count": sum(1 for row in rows if row["sha256_status"] == "sha256_match"),
        "listing_present_count": sum(1 for row in rows if row["listing_status"] == "tarball_listing_present"),
        "listing_entry_count": sum(_int(row.get("listing_entry_count")) for row in rows),
        "first_priority_target_id": _text(first_priority.get("primary_target_id")),
        "first_priority_model_set_id": _text(first_priority.get("model_set_id")),
        "first_open_target_id": _text(first_open.get("primary_target_id")),
        "first_open_status": _text(first_open.get("pool_verification_status")),
        "first_open_action_md": _text(first_open.get("action_md")),
        "r2341_verification_status": _text(
            next((row["pool_verification_status"] for row in rows if row["primary_target_id"] == "R2341"), "")
        ),
        "r2345_verification_status": _text(
            next((row["pool_verification_status"] for row in rows if row["primary_target_id"] == "R2345"), "")
        ),
        "download_policy": DOWNLOAD_POLICY,
        "out_dir": _artifact(args.out_dir),
        "next_action": _next_action(_text(first_open.get("pool_verification_status"))),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.priority_queue_json)
    priority_payload = _read_json(input_path)
    rows = _build_rows(_rows(priority_payload), args.out_dir, args.max_hash_bytes)
    summary = _build_summary(args, priority_payload, rows, input_path.exists())
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


def _write_action(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['primary_target_id']} MassiveFold Acquisition Verification",
        "",
        f"- model_set_id: `{row['model_set_id']}`",
        f"- tarball_url: `{row['massivefold_tarball_url']}`",
        f"- download_path: `{row['download_path']}`",
        f"- sha256_path: `{row['sha256_path']}`",
        f"- listing_path: `{row['listing_path']}`",
        f"- verification_status: `{row['pool_verification_status']}`",
        f"- tarball/size/hash/listing: `{row['tarball_status']}`/`{row['size_status']}`/`{row['sha256_status']}`/`{row['listing_status']}`",
        "",
        "## Acquisition Commands",
        "",
        "```bash",
        f"mkdir -p {row['pool_folder']}/downloads {row['pool_folder']}/hashes {row['pool_folder']}/extracted_models",
        f"curl --fail --location --continue-at - --output {row['download_path']} '{row['massivefold_tarball_url']}'",
        f"sha256sum {row['download_path']} > {row['sha256_path']}",
        f"tar -tzf {row['download_path']} > {row['listing_path']}",
        "```",
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
    folder = _resolve(row["action_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ACQUISITION_VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "acquisition_verification.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Acquisition Verification Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_acquisition_verification_status']}`",
        f"- pools verified/open/total: `{summary['verified_pool_count']}/{summary['open_acquisition_action_count']}/{summary['acquisition_pool_count']}`",
        f"- tarball/size/hash/listing: `{summary['tarball_present_count']}/{summary['size_match_count']}/{summary['sha256_record_present_count']}/{summary['listing_present_count']}`",
        f"- first priority/open: `{summary['first_priority_target_id'] or '-'}`/`{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- R2341/R2345 verification: `{summary['r2341_verification_status'] or '-'}`/`{summary['r2345_verification_status'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Pools",
        "",
        "| rank | target | tarball | hash | listing | status | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['queue_rank']}` | `{row['primary_target_id']}` | `{row['tarball_status']}` | "
            f"`{row['sha256_status']}` | `{row['listing_status']}` | `{row['pool_verification_status']}` | "
            f"`{row['action_md']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `blocked_no_massivefold_priority_pools` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_action(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold external-pool acquisition verification board.")
    parser.add_argument("--priority-queue-json", default=DEFAULT_PRIORITY_QUEUE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-hash-bytes", type=int, default=10_000_000_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
