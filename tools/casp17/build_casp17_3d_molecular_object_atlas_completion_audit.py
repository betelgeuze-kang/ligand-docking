#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ATLAS_JSON = "casp17/casp17_3d_molecular_object_atlas_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_ATLAS_COMPLETION_AUDIT.md"
DEFAULT_OUT_HTML = "casp17/casp17_3d_molecular_object_atlas_completion_audit_current.html"

CLAIM_BOUNDARY = (
    "CASP17 3D molecular object atlas completion audit only. It verifies that protein-name folders, "
    "per-object folders, manifests, readmes, model/viewer/projection links, MassiveFold top5/escrow links, "
    "and no-coordinate-copy hygiene are present for the already-built atlas. It does not copy coordinates, "
    "score native accuracy, serialize a CASP author code, or submit to CASP."
)

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "protein_name",
    "object_id",
    "audit_status",
    "atlas_protein_folder",
    "atlas_object_folder",
    "atlas_protein_readme",
    "atlas_protein_manifest",
    "atlas_object_readme",
    "atlas_object_manifest",
    "source_object_manifest",
    "source_object_readme",
    "model_path",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "escrow_md",
    "coordinate_copy_count",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _coordinate_copy_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file() and child.suffix.lower() in {".pdb", ".cif"})


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    atlas_protein_folder = _text(row.get("atlas_protein_folder"))
    atlas_object_folder = _text(row.get("atlas_object_folder"))
    coordinate_copy_count = _coordinate_copy_count(atlas_object_folder)
    required_files = [
        ("atlas_protein_readme_missing", row.get("atlas_protein_readme")),
        ("atlas_protein_manifest_missing", row.get("atlas_protein_manifest")),
        ("atlas_object_readme_missing", row.get("atlas_object_readme")),
        ("atlas_object_manifest_missing", row.get("atlas_object_manifest")),
        ("source_object_manifest_missing", row.get("source_object_manifest")),
        ("source_object_readme_missing", row.get("source_object_readme")),
        ("model_file_missing", row.get("model_path")),
        ("viewer_html_missing", row.get("viewer_html")),
        ("projection_svg_missing", row.get("projection_svg")),
    ]
    if not _is_dir(atlas_protein_folder):
        blockers.append("atlas_protein_folder_missing")
    if not _is_dir(atlas_object_folder):
        blockers.append("atlas_object_folder_missing")
    for blocker, path_like in required_files:
        if not _is_file(_text(path_like)):
            blockers.append(blocker)
    if _text(row.get("source_lane")) == "massivefold_freeze_candidate":
        if not _is_file(_text(row.get("top5_manifest_csv"))):
            blockers.append("top5_manifest_missing")
        if not _text(row.get("top5_manifest_sha256")):
            blockers.append("top5_sha256_missing")
        if not _is_file(_text(row.get("escrow_md"))):
            blockers.append("escrow_md_missing")
        if not _text(row.get("model_sha256")):
            blockers.append("model_sha256_missing")
    if coordinate_copy_count:
        blockers.append("atlas_coordinate_copy_present")
    if _text(row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if _text(row.get("author_serialized")).lower() != "false":
        blockers.append("author_serialized_not_false")
    if _text(row.get("atlas_status")) != "pass":
        blockers.append("source_atlas_status_not_pass")
    return {
        "atlas_protein_key": _text(row.get("atlas_protein_key")),
        "atlas_object_key": _text(row.get("atlas_object_key")),
        "source_lane": _text(row.get("source_lane")),
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "audit_status": "pass" if not blockers else "blocked",
        "atlas_protein_folder": _artifact(atlas_protein_folder),
        "atlas_object_folder": _artifact(atlas_object_folder),
        "atlas_protein_readme": _artifact(row.get("atlas_protein_readme", "")),
        "atlas_protein_manifest": _artifact(row.get("atlas_protein_manifest", "")),
        "atlas_object_readme": _artifact(row.get("atlas_object_readme", "")),
        "atlas_object_manifest": _artifact(row.get("atlas_object_manifest", "")),
        "source_object_manifest": _artifact(row.get("source_object_manifest", "")),
        "source_object_readme": _artifact(row.get("source_object_readme", "")),
        "model_path": _artifact(row.get("model_path", "")),
        "viewer_html": _artifact(row.get("viewer_html", "")),
        "projection_svg": _artifact(row.get("projection_svg", "")),
        "top5_manifest_csv": _artifact(row.get("top5_manifest_csv", "")),
        "escrow_md": _artifact(row.get("escrow_md", "")),
        "coordinate_copy_count": coordinate_copy_count,
        "competitive_proof_eligible": _text(row.get("competitive_proof_eligible")),
        "author_serialized": _text(row.get("author_serialized")),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    atlas_payload = _read_json(args.atlas_json)
    atlas_summary = _summary(atlas_payload)
    rows = [_audit_row(row) for row in _rows(atlas_payload)]
    protein_rows = _rows(atlas_payload, "protein_rows")
    blocked = [row for row in rows if row["audit_status"] != "pass"]
    atlas_dir = _text(atlas_summary.get("atlas_dir"))
    atlas_coordinate_copy_count = _coordinate_copy_count(atlas_dir)
    protein_folder_count = sum(1 for row in protein_rows if _is_dir(row.get("atlas_protein_folder", "")))
    protein_readme_count = sum(1 for row in protein_rows if _is_file(row.get("atlas_protein_readme", "")))
    protein_manifest_count = sum(1 for row in protein_rows if _is_file(row.get("atlas_protein_manifest", "")))
    status = "casp17_3d_molecular_object_atlas_completion_audit_pass"
    if not rows:
        status = "casp17_3d_molecular_object_atlas_completion_audit_blocked_no_objects"
    elif blocked or atlas_coordinate_copy_count:
        status = "casp17_3d_molecular_object_atlas_completion_audit_blocked"
    first = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_3d_molecular_object_atlas_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "atlas_completion_audit_status": status,
        "atlas_json": _artifact(args.atlas_json),
        "atlas_status": _text(atlas_summary.get("casp17_3d_molecular_object_atlas_status")),
        "atlas_dir": _artifact(atlas_dir),
        "html_audit_path": _artifact(args.out_html),
        "protein_count": len(protein_rows),
        "protein_folder_present_count": protein_folder_count,
        "protein_readme_present_count": protein_readme_count,
        "protein_manifest_present_count": protein_manifest_count,
        "object_count": len(rows),
        "object_pass_count": len(rows) - len(blocked),
        "object_blocked_count": len(blocked),
        "current_object_count": sum(1 for row in rows if row["source_lane"] == "current_object_library"),
        "massivefold_freeze_object_count": sum(
            1 for row in rows if row["source_lane"] == "massivefold_freeze_candidate"
        ),
        "atlas_object_folder_present_count": sum(1 for row in rows if _is_dir(row["atlas_object_folder"])),
        "atlas_object_readme_present_count": sum(1 for row in rows if _is_file(row["atlas_object_readme"])),
        "atlas_object_manifest_present_count": sum(1 for row in rows if _is_file(row["atlas_object_manifest"])),
        "source_object_manifest_present_count": sum(1 for row in rows if _is_file(row["source_object_manifest"])),
        "source_object_readme_present_count": sum(1 for row in rows if _is_file(row["source_object_readme"])),
        "model_link_present_count": sum(1 for row in rows if _is_file(row["model_path"])),
        "viewer_link_present_count": sum(1 for row in rows if _is_file(row["viewer_html"])),
        "projection_link_present_count": sum(1 for row in rows if _is_file(row["projection_svg"])),
        "top5_link_present_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "escrow_link_present_count": sum(1 for row in rows if _is_file(row["escrow_md"])),
        "object_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "atlas_coordinate_copy_count": atlas_coordinate_copy_count,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_blocked_object_key": _text(blocked[0].get("atlas_object_key")) if blocked else "",
        "first_blocked_protein_key": _text(blocked[0].get("atlas_protein_key")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": "Use this green audit as the 3D object organization gate while strict-blind metrics remain separately blocked.",
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
        "# CASP17 3D Molecular Object Atlas Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['atlas_completion_audit_status']}`",
        f"- proteins folder/readme/manifest/total: `{summary['protein_folder_present_count']}/{summary['protein_readme_present_count']}/{summary['protein_manifest_present_count']}/{summary['protein_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- source objects current/massivefold: `{summary['current_object_count']}/{summary['massivefold_freeze_object_count']}`",
        f"- atlas object folder/readme/manifest: `{summary['atlas_object_folder_present_count']}/{summary['atlas_object_readme_present_count']}/{summary['atlas_object_manifest_present_count']}`",
        f"- links model/viewer/projection/top5/escrow: `{summary['model_link_present_count']}/{summary['viewer_link_present_count']}/{summary['projection_link_present_count']}/{summary['top5_link_present_count']}/{summary['escrow_link_present_count']}`",
        f"- coordinate copies object/atlas: `{summary['object_coordinate_copy_count']}/{summary['atlas_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html audit: `{summary['html_audit_path']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}` blocked `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Object Rows",
        "",
        "| protein | object | source | status | blockers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['atlas_protein_key']}` | `{row['atlas_object_key']}` | `{row['source_lane']}` | "
            f"`{row['audit_status']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    body_rows = []
    for row in payload["rows"]:
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(row['target_id'])}</td>"
            f"<td>{html.escape(row['atlas_protein_key'])}</td>"
            f"<td>{html.escape(row['atlas_object_key'])}</td>"
            f"<td>{html.escape(row['source_lane'])}</td>"
            f"<td>{html.escape(row['audit_status'])}</td>"
            f"<td>{html.escape(row['blockers'] or '-')}</td>"
            "</tr>"
        )
    path = _resolve(path_like)
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 3D Molecular Object Atlas Completion Audit</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 3D Molecular Object Atlas Completion Audit</h1>",
            f"<p>Status: <code>{html.escape(summary['atlas_completion_audit_status'])}</code></p>",
            f"<p>Objects: {summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']} pass/blocked/total.</p>",
            "<table><thead><tr><th>target</th><th>protein</th><th>object</th><th>source</th><th>status</th><th>blockers</th></tr></thead><tbody>",
            "\n".join(body_rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 3D molecular object atlas completion.")
    parser.add_argument("--atlas-json", default=DEFAULT_ATLAS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
