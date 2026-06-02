#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COORDINATE_MATERIALIZATION_PLAN_JSON = (
    "casp17/casp17_3d_molecular_object_coordinate_materialization_plan_current.json"
)
DEFAULT_OUT_DIR = "casp17/3d_molecular_object_coordinate_materialized_library"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_coordinate_materialized_library_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_coordinate_materialized_library_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_COORDINATE_MATERIALIZED_LIBRARY.md"

SUPPORTED_MODES = {"symlink", "copy"}
SUPPORTED_COORDINATE_EXTENSIONS = {".pdb", ".cif"}
READY_PLAN_STATUS = "coordinate_materialization_ready_dry_run"
LIBRARY_GITIGNORE = """# CASP17 materialized coordinate files are local review artifacts.
**/coordinates/*.pdb
**/coordinates/*.cif
"""

CLAIM_BOUNDARY = (
    "CASP17 3D molecular object coordinate materialized library only. It materializes each "
    "source coordinate model from the dry-run plan into a protein-name/object folder with "
    "sha256 verification. The default symlink mode avoids duplicating raw coordinate bytes. "
    "It does not alter source models, compute native accuracy, serialize a CASP author code, "
    "or submit to CASP."
)

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "protein_name",
    "object_id",
    "materialization_status",
    "materialization_mode",
    "source_coordinate_path",
    "source_coordinate_format",
    "source_coordinate_present",
    "source_sha256",
    "source_bytes",
    "materialized_protein_folder",
    "materialized_object_folder",
    "materialized_coordinate_folder",
    "materialized_coordinate_path",
    "materialized_coordinate_present",
    "materialized_sha256",
    "materialized_bytes",
    "sha256_match",
    "symlink_target",
    "object_manifest",
    "object_readme",
    "protein_manifest",
    "blockers",
    "next_action",
    "claim_boundary",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = Path(os.path.abspath(_resolve(path_like)))
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


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


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and (ch.isalnum() or ch in {"_", "-"}) else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part)[:160] or "unknown"


def _sha256(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes(path_like: str | Path) -> int:
    path = _resolve(path_like)
    return path.stat().st_size if path.is_file() else 0


def _relative_symlink_target(source: Path, dest: Path) -> str:
    return os.path.relpath(source.resolve(), dest.parent.resolve())


def _destination_path(row: dict[str, Any], out_dir: str | Path) -> Path:
    protein = _safe_component(_text(row.get("atlas_protein_key")))
    obj = _safe_component(_text(row.get("atlas_object_key")))
    proposed = Path(_text(row.get("proposed_coordinate_copy_path")))
    filename = proposed.name if proposed.name else Path(_text(row.get("source_coordinate_path"))).name
    return _resolve(out_dir) / protein / obj / "coordinates" / filename


def _materialize_coordinate(source: Path, dest: Path, mode: str, blockers: list[str]) -> None:
    if not source.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if _sha256(source) != _sha256(dest):
            blockers.append("materialized_coordinate_conflict")
        return
    if dest.is_symlink() and not dest.exists():
        blockers.append("materialized_coordinate_broken_symlink_present")
        return
    if mode == "copy":
        shutil.copy2(source, dest)
    else:
        dest.symlink_to(_relative_symlink_target(source, dest))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] = ROW_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_library_gitignore(out_dir: str | Path) -> None:
    path = _resolve(out_dir) / ".gitignore"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LIBRARY_GITIGNORE, encoding="utf-8")


def _write_object_readme(path_like: str | Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['atlas_protein_key']} / {row['atlas_object_key']} Coordinate",
        "",
        f"- status: `{row['materialization_status']}`",
        f"- mode: `{row['materialization_mode']}`",
        f"- source: `{row['source_coordinate_path']}`",
        f"- materialized: `{row['materialized_coordinate_path']}`",
        f"- sha256 match: `{row['sha256_match']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_protein_readme(path_like: str | Path, protein_key: str, rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {protein_key} Materialized Coordinates",
        "",
        f"- objects: `{len(rows)}`",
        f"- pass/blocked: `{sum(1 for row in rows if row['materialization_status'] == 'coordinate_materialized')}/{sum(1 for row in rows if row['materialization_status'] != 'coordinate_materialized')}`",
        "",
        "| object | coordinate | sha256 match |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['atlas_object_key']}` | `{row['materialized_coordinate_path']}` | `{row['sha256_match']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _materialized_row(row: dict[str, Any], args: argparse.Namespace, global_blockers: list[str]) -> dict[str, Any]:
    blockers = list(global_blockers)
    source = _resolve(_text(row.get("source_coordinate_path")))
    dest = _destination_path(row, args.out_dir)
    source_suffix = source.suffix.lower()
    if _text(row.get("materialization_status")) != READY_PLAN_STATUS:
        blockers.append("coordinate_materialization_plan_row_not_ready")
    if not source.is_file():
        blockers.append("source_coordinate_missing")
    if source_suffix not in SUPPORTED_COORDINATE_EXTENSIONS:
        blockers.append("unsupported_coordinate_extension")
    _materialize_coordinate(source, dest, args.mode, blockers)
    source_sha = _sha256(source)
    materialized_sha = _sha256(dest)
    sha_match = bool(source_sha and materialized_sha and source_sha == materialized_sha)
    if not dest.is_file():
        blockers.append("materialized_coordinate_missing")
    if dest.is_file() and not sha_match:
        blockers.append("materialized_sha256_mismatch")
    blockers = list(dict.fromkeys(blockers))
    object_folder = dest.parent.parent
    protein_folder = object_folder.parent
    object_manifest = object_folder / "coordinate_manifest.json"
    object_readme = object_folder / "README.md"
    protein_manifest = protein_folder / "protein_coordinate_manifest.json"
    symlink_target = os.readlink(dest) if dest.is_symlink() else ""
    status = "coordinate_materialized" if not blockers else "coordinate_materialization_blocked"
    result = {
        "atlas_protein_key": _text(row.get("atlas_protein_key")),
        "atlas_object_key": _text(row.get("atlas_object_key")),
        "source_lane": _text(row.get("source_lane")),
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "materialization_status": status,
        "materialization_mode": args.mode,
        "source_coordinate_path": _artifact(source),
        "source_coordinate_format": source_suffix.lstrip("."),
        "source_coordinate_present": "true" if source.is_file() else "false",
        "source_sha256": source_sha,
        "source_bytes": _bytes(source),
        "materialized_protein_folder": _artifact(protein_folder),
        "materialized_object_folder": _artifact(object_folder),
        "materialized_coordinate_folder": _artifact(dest.parent),
        "materialized_coordinate_path": _artifact(dest),
        "materialized_coordinate_present": "true" if dest.is_file() else "false",
        "materialized_sha256": materialized_sha,
        "materialized_bytes": _bytes(dest),
        "sha256_match": "true" if sha_match else "false",
        "symlink_target": symlink_target,
        "object_manifest": _artifact(object_manifest),
        "object_readme": _artifact(object_readme),
        "protein_manifest": _artifact(protein_manifest),
        "blockers": ",".join(blockers),
        "next_action": (
            "Use this per-object materialized coordinate for local 3D review."
            if not blockers
            else "Resolve the first source/destination coordinate blocker, then rerun materialization."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_json(
        object_manifest,
        {
            "summary": {
                key: result[key]
                for key in [
                    "atlas_protein_key",
                    "atlas_object_key",
                    "target_id",
                    "protein_name",
                    "object_id",
                    "materialization_status",
                    "materialization_mode",
                    "source_coordinate_path",
                    "materialized_coordinate_path",
                    "source_sha256",
                    "materialized_sha256",
                    "sha256_match",
                    "blockers",
                ]
            },
            "claim_boundary": CLAIM_BOUNDARY,
        },
    )
    _write_object_readme(object_readme, result)
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    plan_payload = _read_json(args.coordinate_materialization_plan_json)
    plan_summary = _summary(plan_payload)
    global_blockers: list[str] = []
    if _text(plan_summary.get("coordinate_materialization_plan_status")) != "coordinate_materialization_plan_ready_dry_run":
        global_blockers.append("coordinate_materialization_plan_not_ready")
    if args.mode not in SUPPORTED_MODES:
        global_blockers.append("unsupported_materialization_mode")
    rows = [_materialized_row(row, args, global_blockers) for row in _rows(plan_payload)]
    rows_by_protein: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_protein[row["atlas_protein_key"]].append(row)
    for protein_key, protein_rows in rows_by_protein.items():
        protein_folder = _resolve(protein_rows[0]["materialized_protein_folder"])
        protein_manifest = protein_folder / "protein_coordinate_manifest.json"
        _write_json(
            protein_manifest,
            {
                "summary": {
                    "atlas_protein_key": protein_key,
                    "object_count": len(protein_rows),
                    "materialized_count": sum(
                        1 for row in protein_rows if row["materialization_status"] == "coordinate_materialized"
                    ),
                    "blocked_count": sum(
                        1 for row in protein_rows if row["materialization_status"] != "coordinate_materialized"
                    ),
                },
                "rows": protein_rows,
                "claim_boundary": CLAIM_BOUNDARY,
            },
        )
        _write_protein_readme(protein_folder / "README.md", protein_key, protein_rows)
    blocked = [row for row in rows if row["materialization_status"] != "coordinate_materialized"]
    first = rows[0] if rows else {}
    first_blocked = blocked[0] if blocked else {}
    status = "casp17_3d_molecular_object_coordinate_materialized_library_pass"
    if not rows:
        status = "casp17_3d_molecular_object_coordinate_materialized_library_blocked_no_objects"
    elif blocked:
        status = "casp17_3d_molecular_object_coordinate_materialized_library_blocked"
    summary = {
        "packet_type": "casp17_3d_molecular_object_coordinate_materialized_library",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "coordinate_materialized_library_status": status,
        "coordinate_materialization_plan_json": _artifact(args.coordinate_materialization_plan_json),
        "coordinate_materialization_plan_status": _text(plan_summary.get("coordinate_materialization_plan_status")),
        "out_dir": _artifact(args.out_dir),
        "materialization_mode": args.mode,
        "protein_count": len(rows_by_protein),
        "object_count": len(rows),
        "object_materialized_count": len(rows) - len(blocked),
        "object_blocked_count": len(blocked),
        "current_object_count": sum(1 for row in rows if row["source_lane"] == "current_object_library"),
        "massivefold_object_count": sum(1 for row in rows if row["source_lane"] == "massivefold_freeze_candidate"),
        "source_present_count": sum(1 for row in rows if row["source_coordinate_present"] == "true"),
        "materialized_present_count": sum(1 for row in rows if row["materialized_coordinate_present"] == "true"),
        "sha256_match_count": sum(1 for row in rows if row["sha256_match"] == "true"),
        "symlink_count": sum(1 for row in rows if _resolve(row["materialized_coordinate_path"]).is_symlink()),
        "copy_count": sum(
            1
            for row in rows
            if _resolve(row["materialized_coordinate_path"]).is_file()
            and not _resolve(row["materialized_coordinate_path"]).is_symlink()
        ),
        "pdb_count": sum(1 for row in rows if row["source_coordinate_format"] == "pdb"),
        "cif_count": sum(1 for row in rows if row["source_coordinate_format"] == "cif"),
        "source_total_bytes": sum(_int(row.get("source_bytes")) for row in rows),
        "materialized_total_bytes": sum(_int(row.get("materialized_bytes")) for row in rows),
        "protein_folder_count": len(
            {
                row["materialized_protein_folder"]
                for row in rows
                if _resolve(row["materialized_protein_folder"]).is_dir()
            }
        ),
        "object_folder_count": sum(1 for row in rows if _resolve(row["materialized_object_folder"]).is_dir()),
        "coordinate_folder_count": sum(1 for row in rows if _resolve(row["materialized_coordinate_folder"]).is_dir()),
        "proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_blocked_protein_key": _text(first_blocked.get("atlas_protein_key")),
        "first_blocked_object_key": _text(first_blocked.get("atlas_object_key")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",", 1)[0] if first_blocked else "",
        "next_action": (
            "Use the materialized per-object coordinate library for local 3D review; strict-blind metrics remain separate."
            if not blocked
            else "Repair blocked materialized coordinate rows, then rerun this builder."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 3D Molecular Object Coordinate Materialized Library",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['coordinate_materialized_library_status']}`",
        f"- plan: `{summary['coordinate_materialization_plan_status'] or '-'}`",
        f"- mode: `{summary['materialization_mode']}`",
        f"- proteins/objects: `{summary['protein_count']}/{summary['object_count']}`",
        f"- materialized/blocked: `{summary['object_materialized_count']}/{summary['object_blocked_count']}`",
        f"- source/materialized/sha-match: `{summary['source_present_count']}/{summary['materialized_present_count']}/{summary['sha256_match_count']}`",
        f"- current/massivefold objects: `{summary['current_object_count']}/{summary['massivefold_object_count']}`",
        f"- formats pdb/cif: `{summary['pdb_count']}/{summary['cif_count']}`",
        f"- symlink/copy: `{summary['symlink_count']}/{summary['copy_count']}`",
        f"- folders protein/object/coordinate: `{summary['protein_folder_count']}/{summary['object_folder_count']}/{summary['coordinate_folder_count']}`",
        f"- proof/author: `{summary['proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}`",
        f"- first blocked: `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocked_object_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_library_gitignore(args.out_dir)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 3D molecular object materialized coordinate library.")
    parser.add_argument("--coordinate-materialization-plan-json", default=DEFAULT_COORDINATE_MATERIALIZATION_PLAN_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="symlink")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
