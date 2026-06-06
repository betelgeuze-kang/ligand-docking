#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TARGET_OBJECT_CSV = "casp17/casp17_target_object_models_current.csv"
DEFAULT_OUT_DIR = "casp17/protein_object_library_current"
DEFAULT_OUT_JSON = "casp17/casp17_protein_object_library_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_protein_object_library_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_PROTEIN_OBJECT_LIBRARY.md"

CLAIM_BOUNDARY = (
    "Local CASP17 protein-name object library only. It materializes review folders and "
    "pointers for already-generated internal 3D object models; it does not copy native "
    "structures, fetch external data, score native accuracy, or submit to CASP."
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


def _ascii_slug(value: str, *, fallback: str, max_len: int = 96) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    return slug[:max_len].rstrip("_") or fallback


def _read_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id", "protein_name", "object_id", "library_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _path_exists(row: dict[str, Any], key: str) -> bool:
    value = _text(row.get(key))
    return bool(value) and _resolve(value).is_file()


def _source_value(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(source.get(key))
        if value:
            return value
    return ""


def _render_object_readme(row: dict[str, Any]) -> str:
    blockers = _text(row.get("blockers")) or "-"
    return "\n".join(
        [
            f"# {row['target_id']} {row['object_id']}",
            "",
            f"- protein/complex: `{row['protein_name']}`",
            f"- chain: `{row['chain_id']}`",
            f"- status: `{row['library_status']}`",
            f"- atoms: `{row['atom_count']}` protein atoms `{row['protein_atom_count']}` residues `{row['residue_count']}`",
            f"- coordinates: `{row['coordinate_status']}`",
            f"- model: `{row['model_path']}`",
            f"- projection: `{row['projection_svg_path']}`",
            f"- viewer: `{row['viewer_html_path']}`",
            f"- source object folder: `{row['source_object_folder']}`",
            f"- blockers: `{blockers}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
    )


def _write_object_folder(row: dict[str, Any]) -> None:
    folder = _resolve(row["library_object_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(_render_object_readme(row), encoding="utf-8")
    manifest = {
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": row,
    }
    (folder / "object_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_protein_readme(protein_key: str, rows: list[dict[str, Any]]) -> str:
    first = rows[0]
    lines = [
        f"# {first['protein_name']}",
        "",
        f"- target: `{first['target_id']}`",
        f"- protein folder key: `{protein_key}`",
        f"- objects: `{len(rows)}`",
        f"- status: `{'pass' if all(row['library_status'] == 'pass' for row in rows) else 'blocked'}`",
        "",
        "## Objects",
        "",
        "| object | chain | atoms | protein atoms | residues | coordinates | folder | model | viewer | status |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['object_id']}` | `{row['chain_id']}` | {row['atom_count']} | "
            f"{row['protein_atom_count']} | {row['residue_count']} | `{row['coordinate_status']}` | "
            f"`{row['library_object_folder']}` | `{row['model_path']}` | `{row['viewer_html_path']}` | "
            f"`{row['library_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_protein_folder(protein_key: str, rows: list[dict[str, Any]]) -> None:
    folder = _resolve(rows[0]["library_protein_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(_render_protein_readme(protein_key, rows), encoding="utf-8")
    manifest = {
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "target_id": rows[0]["target_id"],
            "protein_name": rows[0]["protein_name"],
            "protein_key": protein_key,
            "library_protein_folder": rows[0]["library_protein_folder"],
            "object_count": len(rows),
            "pass_count": sum(1 for row in rows if row["library_status"] == "pass"),
            "blocked_count": sum(1 for row in rows if row["library_status"] != "pass"),
        },
        "objects": rows,
    }
    (folder / "protein_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _library_row(source: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    target_id = _text(source.get("target")).upper() or _text(source.get("target_id")).upper()
    protein_name = _text(source.get("protein/complex")) or _text(source.get("protein_name")) or target_id
    object_id = _text(source.get("object")) or _text(source.get("object_id"))
    chain_id = _text(source.get("chain")) or _text(source.get("chain_id"))
    protein_key = f"{target_id}_{_ascii_slug(protein_name, fallback=target_id)}"
    object_key = _ascii_slug(object_id or chain_id, fallback="object")
    protein_folder = out_dir / protein_key
    object_folder = protein_folder / object_key
    blockers: list[str] = []
    if not target_id:
        blockers.append("target_id_missing")
    if not protein_name:
        blockers.append("protein_name_missing")
    if not object_id:
        blockers.append("object_id_missing")
    if not chain_id:
        blockers.append("chain_id_missing")
    for value, blocker, is_dir in (
        (_source_value(source, "model", "model_path"), "model_pdb_missing", False),
        (_source_value(source, "projection", "projection_svg_path"), "projection_svg_missing", False),
        (_source_value(source, "viewer", "viewer_html_path"), "viewer_html_missing", False),
        (_source_value(source, "folder", "object_folder"), "source_object_folder_missing", True),
    ):
        if not value:
            blockers.append(f"{blocker}_path")
        else:
            path = _resolve(value)
            if is_dir:
                if not path.is_dir():
                    blockers.append(blocker)
            elif not path.is_file():
                blockers.append(blocker)
    coordinate_status = _text(source.get("coordinates")) or _text(source.get("coordinate_status"))
    if coordinate_status != "valid":
        blockers.append("coordinates_not_valid")
    if int(source.get("protein atoms") or source.get("protein_atom_count") or 0) <= 0:
        blockers.append("protein_atom_records_missing")
    return {
        "target_id": target_id,
        "protein_name": protein_name,
        "protein_key": protein_key,
        "object_id": object_id,
        "chain_id": chain_id,
        "library_status": "pass" if not blockers else "blocked",
        "library_protein_folder": _artifact(protein_folder),
        "library_object_folder": _artifact(object_folder),
        "source_object_folder": _artifact(source.get("folder") or source.get("object_folder") or ""),
        "model_path": _artifact(source.get("model") or source.get("model_path") or ""),
        "projection_svg_path": _artifact(source.get("projection") or source.get("projection_svg_path") or ""),
        "viewer_html_path": _artifact(source.get("viewer") or source.get("viewer_html_path") or ""),
        "atom_count": int(source.get("atoms") or source.get("atom_count") or 0),
        "protein_atom_count": int(source.get("protein atoms") or source.get("protein_atom_count") or 0),
        "residue_count": int(source.get("residues") or source.get("residue_count") or 0),
        "coordinate_status": coordinate_status,
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = _resolve(args.out_dir)
    source_rows = _read_rows(args.target_object_csv)
    rows = [_library_row(row, out_dir) for row in source_rows]
    for row in rows:
        _write_object_folder(row)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["protein_key"]].append(row)
    for protein_key, protein_rows in sorted(grouped.items()):
        _write_protein_folder(protein_key, protein_rows)

    pass_rows = [row for row in rows if row["library_status"] == "pass"]
    blocked_rows = [row for row in rows if row["library_status"] != "pass"]
    protein_folders = sorted(grouped)
    summary = {
        "packet_type": "casp17_protein_object_library",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "protein_object_library_status": "pass" if rows and not blocked_rows else "blocked",
        "target_object_csv": _artifact(args.target_object_csv),
        "library_dir": _artifact(out_dir),
        "protein_folder_count": len(protein_folders),
        "object_folder_count": len(rows),
        "pass_count": len(pass_rows),
        "blocked_count": len(blocked_rows),
        "model_pointer_count": sum(1 for row in rows if _path_exists(row, "model_path")),
        "projection_pointer_count": sum(1 for row in rows if _path_exists(row, "projection_svg_path")),
        "viewer_pointer_count": sum(1 for row in rows if _path_exists(row, "viewer_html_path")),
        "protein_atom_count": sum(int(row["protein_atom_count"]) for row in rows),
        "first_blocked_object": blocked_rows[0]["object_id"] if blocked_rows else "",
        "first_blocked_blockers": blocked_rows[0]["blockers"] if blocked_rows else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Protein Object Library",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- protein_object_library_status: `{summary['protein_object_library_status']}`",
        f"- protein folders: `{summary['protein_folder_count']}`",
        f"- object folders pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['object_folder_count']}`",
        f"- model/projection/viewer pointers: `{summary['model_pointer_count']}/{summary['projection_pointer_count']}/{summary['viewer_pointer_count']}`",
        f"- protein atoms: `{summary['protein_atom_count']}`",
        f"- library dir: `{summary['library_dir']}`",
        f"- first blocked object: `{summary['first_blocked_object'] or '-'}`",
        f"- first blocked blockers: `{summary['first_blocked_blockers'] or '-'}`",
        "",
        "## Objects",
        "",
        "| target | protein/complex | object | chain | status | object folder | model | viewer | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['object_id']}` | `{row['chain_id']}` | "
            f"`{row['library_status']}` | `{row['library_object_folder']}` | `{row['model_path']}` | "
            f"`{row['viewer_html_path']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | - | - | - | no objects |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_root_readme(out_dir: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    protein_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        protein_rows[row["protein_key"]].append(row)
    lines = [
        "# CASP17 Protein Object Library",
        "",
        f"- status: `{summary['protein_object_library_status']}`",
        f"- protein folders: `{summary['protein_folder_count']}`",
        f"- object folders: `{summary['object_folder_count']}`",
        f"- source catalog: `{summary['target_object_csv']}`",
        "",
        "## Protein Folders",
        "",
        "| protein folder | target | protein/complex | objects | status |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for protein_key, rows in sorted(protein_rows.items()):
        status = "pass" if all(row["library_status"] == "pass" for row in rows) else "blocked"
        lines.append(
            f"| `{rows[0]['library_protein_folder']}` | `{rows[0]['target_id']}` | "
            f"{rows[0]['protein_name']} | {len(rows)} | `{status}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(out_dir) / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a CASP17 protein-name library of per-object 3D model review folders."
    )
    parser.add_argument("--target-object-csv", default=DEFAULT_TARGET_OBJECT_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_root_readme(args.out_dir, payload)
    if payload["summary"]["protein_object_library_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
