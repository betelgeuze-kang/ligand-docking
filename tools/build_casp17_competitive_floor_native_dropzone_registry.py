#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRIMARY_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
)
DEFAULT_REPLACEMENT_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_native_dropzone_registry_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_native_dropzone_registry_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_NATIVE_DROPZONE_REGISTRY.md"

COORDINATE_SUFFIXES = {".pdb", ".cif", ".bcif", ".mmcif"}
REGISTRY_COLUMNS = [
    "registry_rank",
    "source_kind",
    "target_id",
    "replace_target_id",
    "target_name",
    "workorder_status",
    "selection_status",
    "workorder_folder",
    "native_dropzone_folder",
    "native_dropzone_pdb",
    "native_dropzone_readme",
    "readme_status",
    "native_file_status",
    "unexpected_coordinate_count",
    "coordinate_copy_count",
    "proof_eligible",
    "author_serialized",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 native dropzone registry only. It merges primary and replacement workorder native dropzones, "
    "checks README/native-file presence, and flags unexpected coordinate copies. It does not fetch native "
    "structures, clear no-leak provenance, compute metrics, serialize CASP author code, or submit to CASP."
)


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


def _boolish(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "eligible"}


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


def _coordinate_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in COORDINATE_SUFFIXES)


def _row_from_workorder(
    row: dict[str, Any],
    *,
    source_kind: str,
    registry_rank: int,
) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    native_dropzone_folder = _text(row.get("native_dropzone_folder"))
    native_dropzone_pdb = _text(row.get("native_dropzone_pdb"))
    native_dropzone_readme = _text(row.get("native_dropzone_readme"))
    folder_path = _resolve(native_dropzone_folder) if native_dropzone_folder else Path()
    native_path = _resolve(native_dropzone_pdb) if native_dropzone_pdb else Path()
    readme_path = _resolve(native_dropzone_readme) if native_dropzone_readme else Path()
    readme_present = bool(native_dropzone_readme and readme_path.is_file())
    native_present = bool(native_dropzone_pdb and native_path.is_file())
    coordinate_files = _coordinate_files(folder_path) if native_dropzone_folder else []
    expected_native = native_path.resolve() if native_dropzone_pdb else None
    unexpected_coordinates = [
        path
        for path in coordinate_files
        if expected_native is None or path.resolve() != expected_native
    ]

    blockers: list[str] = []
    next_actions: list[str] = []
    if not native_dropzone_folder:
        blockers.append("native_dropzone_folder_missing")
        next_actions.append("regenerate the primary/replacement workorder to materialize native dropzone paths")
    elif not folder_path.is_dir():
        blockers.append("native_dropzone_folder_missing")
        next_actions.append("regenerate the workorder or create the native dropzone folder")
    if not readme_present:
        blockers.append("native_dropzone_readme_missing")
        next_actions.append("regenerate the workorder to restore the native dropzone README")
    if not native_present:
        blockers.append("native_pdb_missing")
        next_actions.append("place the operator-cleared native PDB at the expected native_dropzone_pdb path")
    if unexpected_coordinates:
        blockers.append("unexpected_coordinate_copy_present")
        next_actions.append("move or quarantine unexpected coordinate files before provenance review")

    return {
        "registry_rank": registry_rank,
        "source_kind": source_kind,
        "target_id": target_id,
        "replace_target_id": _text(row.get("replace_target_id")).upper(),
        "target_name": _text(row.get("target_name")) or _text(row.get("replace_target_name")),
        "workorder_status": _text(row.get("workorder_status")),
        "selection_status": _text(row.get("selection_status")),
        "workorder_folder": _text(row.get("workorder_folder")),
        "native_dropzone_folder": native_dropzone_folder,
        "native_dropzone_pdb": native_dropzone_pdb,
        "native_dropzone_readme": native_dropzone_readme,
        "readme_status": "present" if readme_present else "missing",
        "native_file_status": "present" if native_present else "missing",
        "unexpected_coordinate_count": len(unexpected_coordinates),
        "coordinate_copy_count": len(coordinate_files),
        "proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
        "next_action": next_actions[0] if next_actions else "review native/provenance manifest for metric unlock",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    primary_payload = _read_json(args.primary_workorder_json)
    replacement_payload = _read_json(args.replacement_workorder_json)
    rows: list[dict[str, Any]] = []
    for source_kind, payload in (("primary", primary_payload), ("replacement", replacement_payload)):
        for row in _rows(payload):
            if source_kind == "replacement" and _text(row.get("selection_status")) != "selected_for_replacement_workorder":
                continue
            if not _text(row.get("native_dropzone_folder")) and not _text(row.get("native_dropzone_pdb")):
                continue
            rows.append(_row_from_workorder(row, source_kind=source_kind, registry_rank=len(rows) + 1))

    blocked_rows = [row for row in rows if _text(row.get("blockers"))]
    native_present_count = sum(1 for row in rows if row["native_file_status"] == "present")
    readme_present_count = sum(1 for row in rows if row["readme_status"] == "present")
    unexpected_coordinate_count = sum(int(row["unexpected_coordinate_count"]) for row in rows)
    coordinate_copy_count = sum(int(row["coordinate_copy_count"]) for row in rows)
    proof_eligible_count = sum(1 for row in rows if _boolish(row.get("proof_eligible")))
    author_serialized_count = sum(1 for row in rows if _boolish(row.get("author_serialized")))
    status = (
        "native_dropzone_registry_ready"
        if rows
        and not blocked_rows
        and native_present_count == len(rows)
        and proof_eligible_count == len(rows)
        and author_serialized_count == 0
        else "awaiting_native_files"
        if rows
        else "missing_workorder_dropzones"
    )
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_competitive_floor_native_dropzone_registry",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "native_dropzone_registry_status": status,
        "dropzone_count": len(rows),
        "primary_dropzone_count": sum(1 for row in rows if row["source_kind"] == "primary"),
        "replacement_dropzone_count": sum(1 for row in rows if row["source_kind"] == "replacement"),
        "dropzone_readme_count": readme_present_count,
        "native_present_count": native_present_count,
        "blocked_dropzone_count": len(blocked_rows),
        "unexpected_coordinate_count": unexpected_coordinate_count,
        "coordinate_copy_count": coordinate_copy_count,
        "proof_eligible_count": proof_eligible_count,
        "author_serialized_count": author_serialized_count,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_blockers": _text(first_blocked.get("blockers")),
        "first_blocked_next_action": _text(first_blocked.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# CASP17 Competitive Floor Native Dropzone Registry",
        "",
        f"- status: `{summary['native_dropzone_registry_status']}`",
        f"- dropzones primary/replacement/total: `{summary['primary_dropzone_count']}/{summary['replacement_dropzone_count']}/{summary['dropzone_count']}`",
        f"- readmes/native present/blocked: `{summary['dropzone_readme_count']}/{summary['native_present_count']}/{summary['blocked_dropzone_count']}`",
        f"- coordinate copies/unexpected: `{summary['coordinate_copy_count']}/{summary['unexpected_coordinate_count']}`",
        f"- proof eligible/author serialized: `{summary['proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
        "## Dropzones",
        "",
        "| rank | source | target | replace | readme | native | unexpected | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {rank} | {source} | `{target}` | `{replace}` | {readme} | {native} | {unexpected} | {blockers} | {next_action} |".format(
                rank=row["registry_rank"],
                source=row["source_kind"],
                target=row["target_id"],
                replace=row["replace_target_id"] or "-",
                readme=row["readme_status"],
                native=row["native_file_status"],
                unexpected=row["unexpected_coordinate_count"],
                blockers=row["blockers"] or "-",
                next_action=row["next_action"],
            )
        )
    lines.append("")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], REGISTRY_COLUMNS)
    _write_markdown(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 competitive-floor native dropzone registry.")
    parser.add_argument("--primary-workorder-json", default=DEFAULT_PRIMARY_WORKORDER_JSON)
    parser.add_argument("--replacement-workorder-json", default=DEFAULT_REPLACEMENT_WORKORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
