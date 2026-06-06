#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ATLAS_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.json"
)
DEFAULT_OUT_DIR = "casp17/3d_molecular_object_coordinate_materialization_plan"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_coordinate_materialization_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_coordinate_materialization_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_COORDINATE_MATERIALIZATION_PLAN.md"

CLAIM_BOUNDARY = (
    "CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each "
    "protein/object atlas folder has a present source coordinate model and a deterministic proposed "
    "destination under the per-object folder. It does not copy coordinates, alter source models, "
    "compute native accuracy, serialize a CASP author code, or submit to CASP."
)

SUPPORTED_COORDINATE_EXTENSIONS = {".pdb", ".cif"}

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "protein_name",
    "object_id",
    "materialization_status",
    "source_coordinate_path",
    "source_coordinate_format",
    "source_coordinate_present",
    "atlas_protein_folder",
    "atlas_protein_folder_present",
    "atlas_protein_readme",
    "atlas_protein_readme_present",
    "atlas_protein_manifest",
    "atlas_protein_manifest_present",
    "atlas_object_folder",
    "atlas_object_folder_present",
    "atlas_object_readme",
    "atlas_object_readme_present",
    "atlas_object_manifest",
    "atlas_object_manifest_present",
    "proposed_coordinate_copy_path",
    "proposed_coordinate_copy_present",
    "existing_coordinate_copy_count",
    "coordinate_copy_policy",
    "blockers",
    "next_action",
    "claim_boundary",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


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


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _coordinate_copy_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.is_dir():
        return 0
    return sum(
        1
        for child in path.rglob("*")
        if child.is_file() and child.suffix.lower() in SUPPORTED_COORDINATE_EXTENSIONS
    )


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _proposed_coordinate_copy_path(atlas_object_folder: str, source_coordinate_path: str) -> str:
    source = _resolve(source_coordinate_path)
    suffix = source.suffix.lower() if source.suffix.lower() in SUPPORTED_COORDINATE_EXTENSIONS else ".pdb"
    stem = _safe_component(source.stem or "coordinate_model")
    return _artifact(_resolve(atlas_object_folder) / "coordinates" / f"{stem}{suffix}")


def _unique_present_count(rows: list[dict[str, Any]], path_key: str, present_key: str) -> int:
    return len(
        {
            row[path_key]
            for row in rows
            if row.get(present_key) == "true" and _text(row.get(path_key))
        }
    )


def _materialization_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    source_coordinate_path = _text(row.get("model_path"))
    atlas_protein_folder = _text(row.get("atlas_protein_folder"))
    atlas_object_folder = _text(row.get("atlas_object_folder"))
    atlas_protein_readme = _text(row.get("atlas_protein_readme"))
    atlas_protein_manifest = _text(row.get("atlas_protein_manifest"))
    atlas_object_readme = _text(row.get("atlas_object_readme"))
    atlas_object_manifest = _text(row.get("atlas_object_manifest"))
    source_coordinate = _resolve(source_coordinate_path) if source_coordinate_path else Path()
    source_suffix = source_coordinate.suffix.lower()
    source_present = _is_file(source_coordinate_path)
    if not source_coordinate_path:
        blockers.append("source_coordinate_path_missing")
    elif not source_present:
        blockers.append("source_coordinate_file_missing")
    if source_coordinate_path and source_suffix not in SUPPORTED_COORDINATE_EXTENSIONS:
        blockers.append("unsupported_coordinate_extension")
    if not _is_dir(atlas_protein_folder):
        blockers.append("atlas_protein_folder_missing")
    if not _is_file(atlas_protein_readme):
        blockers.append("atlas_protein_readme_missing")
    if not _is_file(atlas_protein_manifest):
        blockers.append("atlas_protein_manifest_missing")
    if not _is_dir(atlas_object_folder):
        blockers.append("atlas_object_folder_missing")
    if not _is_file(atlas_object_readme):
        blockers.append("atlas_object_readme_missing")
    if not _is_file(atlas_object_manifest):
        blockers.append("atlas_object_manifest_missing")
    if _text(row.get("audit_status")) != "pass":
        blockers.append("atlas_completion_audit_not_pass")

    proposed_coordinate_copy_path = _proposed_coordinate_copy_path(atlas_object_folder, source_coordinate_path)
    existing_coordinate_copy_count = _coordinate_copy_count(atlas_object_folder)
    proposed_present = _is_file(proposed_coordinate_copy_path)
    status = "coordinate_materialization_ready_dry_run" if not blockers else "blocked_coordinate_materialization_inputs_missing"
    next_action = (
        "Keep link-only atlas as the tracked state; copy this source into the proposed per-object coordinates path only after operator approval."
        if not blockers
        else "Resolve the first missing source coordinate or atlas object folder input, then rerun this dry-run plan."
    )
    return {
        "atlas_protein_key": _text(row.get("atlas_protein_key")),
        "atlas_object_key": _text(row.get("atlas_object_key")),
        "source_lane": _text(row.get("source_lane")),
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "materialization_status": status,
        "source_coordinate_path": _artifact(source_coordinate_path),
        "source_coordinate_format": source_suffix.lstrip(".") if source_suffix else "",
        "source_coordinate_present": _bool_text(source_present),
        "atlas_protein_folder": _artifact(atlas_protein_folder),
        "atlas_protein_folder_present": _bool_text(_is_dir(atlas_protein_folder)),
        "atlas_protein_readme": _artifact(atlas_protein_readme),
        "atlas_protein_readme_present": _bool_text(_is_file(atlas_protein_readme)),
        "atlas_protein_manifest": _artifact(atlas_protein_manifest),
        "atlas_protein_manifest_present": _bool_text(_is_file(atlas_protein_manifest)),
        "atlas_object_folder": _artifact(atlas_object_folder),
        "atlas_object_folder_present": _bool_text(_is_dir(atlas_object_folder)),
        "atlas_object_readme": _artifact(atlas_object_readme),
        "atlas_object_readme_present": _bool_text(_is_file(atlas_object_readme)),
        "atlas_object_manifest": _artifact(atlas_object_manifest),
        "atlas_object_manifest_present": _bool_text(_is_file(atlas_object_manifest)),
        "proposed_coordinate_copy_path": proposed_coordinate_copy_path,
        "proposed_coordinate_copy_present": _bool_text(proposed_present),
        "existing_coordinate_copy_count": existing_coordinate_copy_count,
        "coordinate_copy_policy": "dry_run_no_copy",
        "blockers": ",".join(blockers),
        "next_action": next_action,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit_payload = _read_json(args.atlas_completion_audit_json)
    audit_summary = _summary(audit_payload)
    rows = [_materialization_row(row) for row in _rows(audit_payload)]
    blocked = [row for row in rows if row["materialization_status"] != "coordinate_materialization_ready_dry_run"]
    status = "coordinate_materialization_plan_ready_dry_run"
    if not rows:
        status = "blocked_coordinate_materialization_no_atlas_objects"
    elif blocked:
        status = "blocked_coordinate_materialization_inputs_missing"
    protein_keys = sorted({_text(row.get("atlas_protein_key")) for row in rows if _text(row.get("atlas_protein_key"))})
    first = rows[0] if rows else {}
    first_blocked = blocked[0] if blocked else {}
    summary = {
        "packet_type": "casp17_3d_molecular_object_coordinate_materialization_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "coordinate_materialization_plan_status": status,
        "atlas_completion_audit_json": _artifact(args.atlas_completion_audit_json),
        "atlas_completion_audit_status": _text(audit_summary.get("atlas_completion_audit_status")),
        "out_dir": _artifact(args.out_dir),
        "protein_count": len(protein_keys),
        "object_count": len(rows),
        "ready_object_count": len(rows) - len(blocked),
        "blocked_object_count": len(blocked),
        "current_object_count": sum(1 for row in rows if row["source_lane"] == "current_object_library"),
        "massivefold_freeze_object_count": sum(
            1 for row in rows if row["source_lane"] == "massivefold_freeze_candidate"
        ),
        "source_coordinate_present_count": sum(1 for row in rows if row["source_coordinate_present"] == "true"),
        "source_coordinate_missing_count": sum(1 for row in rows if row["source_coordinate_present"] != "true"),
        "supported_coordinate_format_count": sum(
            1 for row in rows if row["source_coordinate_format"] in {"pdb", "cif"}
        ),
        "unsupported_coordinate_format_count": sum(
            1 for row in rows if row["source_coordinate_format"] not in {"pdb", "cif"}
        ),
        "pdb_source_count": sum(1 for row in rows if row["source_coordinate_format"] == "pdb"),
        "cif_source_count": sum(1 for row in rows if row["source_coordinate_format"] == "cif"),
        "atlas_protein_folder_present_count": _unique_present_count(
            rows, "atlas_protein_folder", "atlas_protein_folder_present"
        ),
        "atlas_protein_readme_present_count": _unique_present_count(
            rows, "atlas_protein_readme", "atlas_protein_readme_present"
        ),
        "atlas_protein_manifest_present_count": _unique_present_count(
            rows, "atlas_protein_manifest", "atlas_protein_manifest_present"
        ),
        "atlas_object_folder_present_count": sum(
            1 for row in rows if row["atlas_object_folder_present"] == "true"
        ),
        "atlas_object_readme_present_count": sum(
            1 for row in rows if row["atlas_object_readme_present"] == "true"
        ),
        "atlas_object_manifest_present_count": sum(
            1 for row in rows if row["atlas_object_manifest_present"] == "true"
        ),
        "proposed_coordinate_copy_count": sum(
            1 for row in rows if _text(row.get("proposed_coordinate_copy_path"))
        ),
        "proposed_coordinate_copy_present_count": sum(
            1 for row in rows if row["proposed_coordinate_copy_present"] == "true"
        ),
        "existing_coordinate_copy_count": sum(_int(row.get("existing_coordinate_copy_count")) for row in rows),
        "coordinate_copy_policy": "dry_run_no_copy",
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_source_coordinate_path": _text(first.get("source_coordinate_path")),
        "first_proposed_coordinate_copy_path": _text(first.get("proposed_coordinate_copy_path")),
        "first_blocked_protein_key": _text(first_blocked.get("atlas_protein_key")),
        "first_blocked_object_key": _text(first_blocked.get("atlas_object_key")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if first_blocked else "",
        "next_action": (
            "Keep the atlas link-only in git; use per-object proposed paths as the operator-approved coordinate materialization map when a coordinate-copy package is explicitly needed."
            if status == "coordinate_materialization_plan_ready_dry_run"
            else "Resolve the first blocked coordinate materialization row, then rerun the dry-run plan."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 3D Molecular Object Coordinate Materialization Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['coordinate_materialization_plan_status']}`",
        f"- proteins/objects: `{summary['protein_count']}/{summary['object_count']}`",
        f"- objects ready/blocked: `{summary['ready_object_count']}/{summary['blocked_object_count']}`",
        f"- source objects current/massivefold: `{summary['current_object_count']}/{summary['massivefold_freeze_object_count']}`",
        f"- source coordinates present/missing: `{summary['source_coordinate_present_count']}/{summary['source_coordinate_missing_count']}`",
        f"- coordinate formats pdb/cif/unsupported: `{summary['pdb_source_count']}/{summary['cif_source_count']}/{summary['unsupported_coordinate_format_count']}`",
        f"- atlas protein folder/readme/manifest: `{summary['atlas_protein_folder_present_count']}/{summary['atlas_protein_readme_present_count']}/{summary['atlas_protein_manifest_present_count']}`",
        f"- atlas object folder/readme/manifest: `{summary['atlas_object_folder_present_count']}/{summary['atlas_object_readme_present_count']}/{summary['atlas_object_manifest_present_count']}`",
        f"- proposed/existing coordinate copies: `{summary['proposed_coordinate_copy_count']}/{summary['existing_coordinate_copy_count']}`",
        f"- policy: `{summary['coordinate_copy_policy']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}`",
        f"- first blocked: `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocked_object_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Object Rows",
        "",
        "| protein | object | source | status | source coordinate | proposed coordinate copy | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['atlas_protein_key']}` | `{row['atlas_object_key']}` | `{row['source_lane']}` | "
            f"`{row['materialization_status']}` | `{row['source_coordinate_path']}` | "
            f"`{row['proposed_coordinate_copy_path']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_per_protein_packets(out_dir_like: str | Path, payload: dict[str, Any]) -> None:
    out_dir = _resolve(out_dir_like)
    rows_by_protein: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        rows_by_protein[row["atlas_protein_key"]].append(row)
    for protein_key, rows in rows_by_protein.items():
        protein_dir = out_dir / _safe_component(protein_key)
        protein_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(protein_dir / "object_coordinate_rows.csv", rows)
        manifest = {
            "summary": {
                "packet_type": "casp17_3d_molecular_object_coordinate_materialization_protein_packet",
                "protein_key": protein_key,
                "object_count": len(rows),
                "ready_object_count": sum(
                    1 for row in rows if row["materialization_status"] == "coordinate_materialization_ready_dry_run"
                ),
                "blocked_object_count": sum(
                    1 for row in rows if row["materialization_status"] != "coordinate_materialization_ready_dry_run"
                ),
                "coordinate_copy_policy": "dry_run_no_copy",
                "claim_boundary": CLAIM_BOUNDARY,
            },
            "rows": rows,
        }
        _write_json(protein_dir / "protein_manifest.json", manifest)
        lines = [
            f"# {protein_key} Coordinate Materialization Plan",
            "",
            f"- object_count: `{manifest['summary']['object_count']}`",
            f"- ready/blocked: `{manifest['summary']['ready_object_count']}/{manifest['summary']['blocked_object_count']}`",
            f"- policy: `{manifest['summary']['coordinate_copy_policy']}`",
            "",
            "| object | status | source coordinate | proposed coordinate copy | blockers |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['atlas_object_key']}` | `{row['materialization_status']}` | "
                f"`{row['source_coordinate_path']}` | `{row['proposed_coordinate_copy_path']}` | "
                f"`{row['blockers'] or '-'}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (protein_dir / "MATERIALIZATION_PLAN.md").write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_per_protein_packets(args.out_dir, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a dry-run coordinate materialization plan for CASP17 3D molecular object atlas."
    )
    parser.add_argument("--atlas-completion-audit-json", default=DEFAULT_ATLAS_COMPLETION_AUDIT_JSON)
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
