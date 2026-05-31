#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON = "casp17/casp17_protein_object_library_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_protein_object_library_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_protein_object_library_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_PROTEIN_OBJECT_LIBRARY_COMPLETION_AUDIT.md"

CLAIM_BOUNDARY = (
    "Local CASP17 3D object-library completion audit only. It verifies protein-name folders, per-object "
    "folders, manifests, model pointers, projection pointers, and viewer pointers for already-generated "
    "internal 3D molecular models. It does not score native accuracy, fetch external structures, or submit "
    "CASP predictions."
)

ROW_COLUMNS = [
    "target_id",
    "protein_name",
    "protein_key",
    "object_id",
    "chain_id",
    "audit_status",
    "library_status",
    "library_protein_folder",
    "library_object_folder",
    "protein_readme",
    "protein_manifest",
    "object_readme",
    "object_manifest",
    "model_path",
    "projection_svg_path",
    "viewer_html_path",
    "source_object_folder",
    "coordinate_status",
    "protein_atom_count",
    "residue_count",
    "blockers",
]

PROTEIN_COLUMNS = [
    "protein_key",
    "target_id",
    "protein_name",
    "library_protein_folder",
    "object_count",
    "pass_count",
    "blocked_count",
    "protein_status",
    "protein_readme",
    "protein_manifest",
    "blockers",
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


def _read_manifest(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.is_file():
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


def _manifest_summary_field(path_like: str | Path, key: str) -> str:
    manifest = _read_manifest(path_like)
    summary = manifest.get("summary")
    if isinstance(summary, dict):
        return _text(summary.get(key))
    return ""


def _audit_object_row(row: dict[str, Any]) -> dict[str, Any]:
    protein_folder = _text(row.get("library_protein_folder"))
    object_folder = _text(row.get("library_object_folder"))
    protein_readme = _artifact(_resolve(protein_folder) / "README.md") if protein_folder else ""
    protein_manifest = _artifact(_resolve(protein_folder) / "protein_manifest.json") if protein_folder else ""
    object_readme = _artifact(_resolve(object_folder) / "README.md") if object_folder else ""
    object_manifest = _artifact(_resolve(object_folder) / "object_manifest.json") if object_folder else ""
    blockers: list[str] = []
    checks = [
        (_is_dir(protein_folder), "protein_folder_missing"),
        (_is_file(protein_readme), "protein_readme_missing"),
        (_is_file(protein_manifest), "protein_manifest_missing"),
        (_is_dir(object_folder), "object_folder_missing"),
        (_is_file(object_readme), "object_readme_missing"),
        (_is_file(object_manifest), "object_manifest_missing"),
        (_is_file(row.get("model_path", "")), "model_pdb_missing"),
        (_is_file(row.get("projection_svg_path", "")), "projection_svg_missing"),
        (_is_file(row.get("viewer_html_path", "")), "viewer_html_missing"),
        (_is_dir(row.get("source_object_folder", "")), "source_object_folder_missing"),
        (_text(row.get("library_status")) == "pass", "library_status_not_pass"),
        (_text(row.get("coordinate_status")) == "valid", "coordinate_status_not_valid"),
        (_int(row.get("protein_atom_count")) > 0, "protein_atom_count_missing"),
        (_int(row.get("residue_count")) > 0, "residue_count_missing"),
    ]
    blockers.extend(blocker for ok, blocker in checks if not ok)
    if _manifest_summary_field(object_manifest, "object_id") != _text(row.get("object_id")):
        blockers.append("object_manifest_id_mismatch")
    protein_manifest_key = _manifest_summary_field(protein_manifest, "protein_key")
    if protein_manifest_key != _text(row.get("protein_key")):
        blockers.append("protein_manifest_key_mismatch")
    return {
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "protein_key": _text(row.get("protein_key")),
        "object_id": _text(row.get("object_id")),
        "chain_id": _text(row.get("chain_id")),
        "audit_status": "pass" if not blockers else "blocked",
        "library_status": _text(row.get("library_status")),
        "library_protein_folder": protein_folder,
        "library_object_folder": object_folder,
        "protein_readme": protein_readme,
        "protein_manifest": protein_manifest,
        "object_readme": object_readme,
        "object_manifest": object_manifest,
        "model_path": _text(row.get("model_path")),
        "projection_svg_path": _text(row.get("projection_svg_path")),
        "viewer_html_path": _text(row.get("viewer_html_path")),
        "source_object_folder": _text(row.get("source_object_folder")),
        "coordinate_status": _text(row.get("coordinate_status")),
        "protein_atom_count": _int(row.get("protein_atom_count")),
        "residue_count": _int(row.get("residue_count")),
        "blockers": ",".join(blockers),
    }


def _protein_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["protein_key"], []).append(row)
    out: list[dict[str, Any]] = []
    for protein_key, protein_rows in sorted(grouped.items()):
        first = protein_rows[0]
        blockers: list[str] = []
        protein_manifest = first["protein_manifest"]
        manifest_count = _int(_manifest_summary_field(protein_manifest, "object_count"), -1)
        if manifest_count != len(protein_rows):
            blockers.append("protein_manifest_object_count_mismatch")
        blocked = [row for row in protein_rows if row["audit_status"] != "pass"]
        for row in blocked[:3]:
            blockers.append(f"{row['object_id']}:{row['blockers']}")
        out.append(
            {
                "protein_key": protein_key,
                "target_id": first["target_id"],
                "protein_name": first["protein_name"],
                "library_protein_folder": first["library_protein_folder"],
                "object_count": len(protein_rows),
                "pass_count": len(protein_rows) - len(blocked),
                "blocked_count": len(blocked),
                "protein_status": "pass" if not blockers else "blocked",
                "protein_readme": first["protein_readme"],
                "protein_manifest": protein_manifest,
                "blockers": ",".join(blockers),
            }
        )
    return out


def _build_summary(
    args: argparse.Namespace,
    library_payload: dict[str, Any],
    object_rows: list[dict[str, Any]],
    protein_rows: list[dict[str, Any]],
    input_exists: bool,
) -> dict[str, Any]:
    library_summary = _summary(library_payload)
    blocked_objects = [row for row in object_rows if row["audit_status"] != "pass"]
    blocked_proteins = [row for row in protein_rows if row["protein_status"] != "pass"]
    first_blocked = blocked_objects[0] if blocked_objects else {}
    status = "pass"
    if not input_exists:
        status = "blocked_library_json_missing"
    elif not object_rows:
        status = "blocked_no_object_rows"
    elif blocked_objects or blocked_proteins:
        status = "blocked"
    return {
        "packet_type": "casp17_protein_object_library_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "completion_audit_status": status,
        "protein_object_library_json": _artifact(args.protein_object_library_json),
        "library_status": _text(library_summary.get("protein_object_library_status")),
        "library_dir": _text(library_summary.get("library_dir")),
        "protein_folder_count": len(protein_rows),
        "protein_folder_pass_count": len(protein_rows) - len(blocked_proteins),
        "protein_folder_blocked_count": len(blocked_proteins),
        "object_folder_count": len(object_rows),
        "object_pass_count": len(object_rows) - len(blocked_objects),
        "object_blocked_count": len(blocked_objects),
        "model_file_present_count": sum(1 for row in object_rows if _is_file(row["model_path"])),
        "projection_file_present_count": sum(1 for row in object_rows if _is_file(row["projection_svg_path"])),
        "viewer_file_present_count": sum(1 for row in object_rows if _is_file(row["viewer_html_path"])),
        "object_manifest_present_count": sum(1 for row in object_rows if _is_file(row["object_manifest"])),
        "protein_manifest_present_count": sum(1 for row in protein_rows if _is_file(row["protein_manifest"])),
        "coordinate_valid_count": sum(1 for row in object_rows if row["coordinate_status"] == "valid"),
        "protein_atom_count": sum(_int(row["protein_atom_count"]) for row in object_rows),
        "residue_count": sum(_int(row["residue_count"]) for row in object_rows),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_object_id": _text(first_blocked.get("object_id")),
        "first_blocked_blockers": _text(first_blocked.get("blockers")),
        "next_action": (
            "keep protein-name folders, per-object manifests, model PDBs, projections, and viewers green while "
            "strict-blind historical benchmark evidence is filled"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.protein_object_library_json)
    library_payload = _read_json(input_path)
    object_rows = [_audit_object_row(row) for row in _rows(library_payload)]
    protein_rows = _protein_rows(object_rows)
    summary = _build_summary(args, library_payload, object_rows, protein_rows, input_path.exists())
    return {"summary": summary, "protein_rows": protein_rows, "rows": object_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Protein Object Library Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['completion_audit_status']}`",
        f"- proteins pass/blocked/total: `{summary['protein_folder_pass_count']}/{summary['protein_folder_blocked_count']}/{summary['protein_folder_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_folder_count']}`",
        f"- model/projection/viewer files: `{summary['model_file_present_count']}/{summary['projection_file_present_count']}/{summary['viewer_file_present_count']}`",
        f"- object/protein manifests: `{summary['object_manifest_present_count']}/{summary['protein_manifest_present_count']}`",
        f"- coordinate-valid objects: `{summary['coordinate_valid_count']}`",
        f"- protein atoms/residues: `{summary['protein_atom_count']}/{summary['residue_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_object_id'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Protein Folders",
        "",
        "| protein folder | target | objects | pass/blocked | status |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["protein_rows"]:
        lines.append(
            f"| `{row['library_protein_folder']}` | `{row['target_id']}` | {row['object_count']} | "
            f"`{row['pass_count']}/{row['blocked_count']}` | `{row['protein_status']}` |"
        )
    if not payload["protein_rows"]:
        lines.append("| - | - | 0 | `0/0` | `blocked` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_csv(_resolve(args.out_csv).with_name("casp17_protein_object_library_completion_audit_proteins_current.csv"), payload["protein_rows"], PROTEIN_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 protein-name 3D object library completion.")
    parser.add_argument("--protein-object-library-json", default=DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["completion_audit_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
