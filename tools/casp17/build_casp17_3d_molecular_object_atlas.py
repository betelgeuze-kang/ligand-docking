#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CURRENT_OBJECT_LIBRARY_JSON = "casp17/casp17_protein_object_library_current.json"
DEFAULT_MASSIVEFOLD_FREEZE_PROTEIN_LIBRARY_JSON = (
    "casp17/casp17_massivefold_freeze_candidate_protein_library_current.json"
)
DEFAULT_OUT_DIR = "casp17/casp17_3d_molecular_object_atlas"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_atlas_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_atlas_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_ATLAS.md"
DEFAULT_OUT_HTML = "casp17/casp17_3d_molecular_object_atlas_current.html"

CLAIM_BOUNDARY = (
    "CASP17 3D molecular object atlas only. It unifies local current protein-object folders and "
    "external-only MassiveFold freeze-candidate folders into protein-name navigation folders with "
    "per-object manifests. It does not copy model coordinates, fetch structures, score native accuracy, "
    "serialize a CASP author code, or submit to CASP."
)
CURRENT_POLICY = "local_current_object_library_review_only_not_competitive_proof"
MASSIVEFOLD_POLICY = "external_freeze_candidate_review_only_not_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "target_group",
    "protein_name",
    "object_id",
    "object_role",
    "atlas_status",
    "atlas_protein_folder",
    "atlas_object_folder",
    "atlas_protein_readme",
    "atlas_protein_manifest",
    "atlas_object_readme",
    "atlas_object_manifest",
    "source_protein_folder",
    "source_object_folder",
    "source_protein_readme",
    "source_protein_manifest",
    "source_object_readme",
    "source_object_manifest",
    "model_path",
    "model_sha256",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "top5_manifest_sha256",
    "escrow_md",
    "native_status",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
    "source_policy",
    "submission_policy",
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


def _href(target: str | Path, html_path: str | Path) -> str:
    target_path = _resolve(target)
    base = _resolve(html_path).parent
    try:
        return Path(os.path.relpath(target_path, base)).as_posix()
    except ValueError:
        return _artifact(target_path)


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


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _target_group(target_id: str) -> str:
    if target_id.startswith("H"):
        return "protein_complex"
    if target_id.startswith("R"):
        return "rna_hybrid"
    if target_id.startswith("M"):
        return "hybrid"
    if target_id.startswith("D"):
        return "dna"
    return "protein_or_monomer"


def _current_row(source: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    target_id = _text(source.get("target_id")).upper()
    protein_key = _text(source.get("protein_key")) or f"{target_id}_{_safe_component(_text(source.get('protein_name')))}"
    object_id = _text(source.get("object_id"))
    atlas_object_key = f"current_{_safe_component(object_id)}"
    atlas_protein_folder = out_dir / protein_key
    atlas_object_folder = atlas_protein_folder / atlas_object_key
    source_protein_folder = _text(source.get("library_protein_folder"))
    source_object_folder = _text(source.get("library_object_folder"))
    source_protein_readme = str(_resolve(source_protein_folder) / "README.md") if source_protein_folder else ""
    source_protein_manifest = str(_resolve(source_protein_folder) / "protein_manifest.json") if source_protein_folder else ""
    source_object_readme = str(_resolve(source_object_folder) / "README.md") if source_object_folder else ""
    source_object_manifest = str(_resolve(source_object_folder) / "object_manifest.json") if source_object_folder else ""
    model_path = _text(source.get("model_path"))
    viewer_html = _text(source.get("viewer_html_path"))
    projection_svg = _text(source.get("projection_svg_path"))
    blockers: list[str] = []
    if _text(source.get("library_status")) != "pass":
        blockers.append("source_library_status_not_pass")
    if not _is_dir(source_protein_folder):
        blockers.append("source_protein_folder_missing")
    if not _is_dir(source_object_folder):
        blockers.append("source_object_folder_missing")
    if not _is_file(source_protein_readme):
        blockers.append("source_protein_readme_missing")
    if not _is_file(source_protein_manifest):
        blockers.append("source_protein_manifest_missing")
    if not _is_file(source_object_readme):
        blockers.append("source_object_readme_missing")
    if not _is_file(source_object_manifest):
        blockers.append("source_object_manifest_missing")
    if not _is_file(model_path):
        blockers.append("model_file_missing")
    if not _is_file(viewer_html):
        blockers.append("viewer_html_missing")
    if not _is_file(projection_svg):
        blockers.append("projection_svg_missing")
    return {
        "atlas_protein_key": protein_key,
        "atlas_object_key": atlas_object_key,
        "source_lane": "current_object_library",
        "target_id": target_id,
        "target_group": _target_group(target_id),
        "protein_name": _text(source.get("protein_name")),
        "object_id": object_id,
        "object_role": _text(source.get("chain_id")) or object_id,
        "atlas_status": "pass" if not blockers else "blocked",
        "atlas_protein_folder": _artifact(atlas_protein_folder),
        "atlas_object_folder": _artifact(atlas_object_folder),
        "atlas_protein_readme": _artifact(atlas_protein_folder / "README.md"),
        "atlas_protein_manifest": _artifact(atlas_protein_folder / "protein_manifest.json"),
        "atlas_object_readme": _artifact(atlas_object_folder / "README.md"),
        "atlas_object_manifest": _artifact(atlas_object_folder / "object_manifest.json"),
        "source_protein_folder": _artifact(source_protein_folder),
        "source_object_folder": _artifact(source_object_folder),
        "source_protein_readme": _artifact(source_protein_readme),
        "source_protein_manifest": _artifact(source_protein_manifest),
        "source_object_readme": _artifact(source_object_readme),
        "source_object_manifest": _artifact(source_object_manifest),
        "model_path": _artifact(model_path),
        "model_sha256": "",
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "top5_manifest_csv": "",
        "top5_manifest_sha256": "",
        "escrow_md": "",
        "native_status": "native_accuracy_not_scored",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
        "source_policy": CURRENT_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _massivefold_row(source: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    protein_key = _text(source.get("protein_key"))
    object_id = _text(source.get("object_id")) or "model1_candidate"
    atlas_object_key = f"massivefold_{_safe_component(object_id)}"
    atlas_protein_folder = out_dir / protein_key
    atlas_object_folder = atlas_protein_folder / atlas_object_key
    model_path = _text(source.get("model_path"))
    viewer_html = _text(source.get("viewer_html"))
    projection_svg = _text(source.get("projection_svg"))
    top5_manifest = _text(source.get("top5_manifest_csv"))
    escrow_md = _text(source.get("escrow_md"))
    source_protein_folder = _text(source.get("library_protein_folder"))
    source_object_folder = _text(source.get("library_object_folder"))
    source_protein_readme = _text(source.get("protein_readme"))
    source_protein_manifest = _text(source.get("protein_manifest"))
    source_object_readme = _text(source.get("object_readme"))
    source_object_manifest = _text(source.get("object_manifest"))
    blockers: list[str] = []
    if _text(source.get("library_status")) != "pass":
        blockers.append("source_library_status_not_pass")
    if not _is_dir(source_protein_folder):
        blockers.append("source_protein_folder_missing")
    if not _is_dir(source_object_folder):
        blockers.append("source_object_folder_missing")
    if not _is_file(source_protein_readme):
        blockers.append("source_protein_readme_missing")
    if not _is_file(source_protein_manifest):
        blockers.append("source_protein_manifest_missing")
    if not _is_file(source_object_readme):
        blockers.append("source_object_readme_missing")
    if not _is_file(source_object_manifest):
        blockers.append("source_object_manifest_missing")
    if not _is_file(model_path):
        blockers.append("model_file_missing")
    if not _text(source.get("model_sha256")):
        blockers.append("model_sha256_missing")
    if not _is_file(viewer_html):
        blockers.append("viewer_html_missing")
    if not _is_file(projection_svg):
        blockers.append("projection_svg_missing")
    if not _is_file(top5_manifest):
        blockers.append("top5_manifest_missing")
    if not _text(source.get("top5_manifest_sha256")):
        blockers.append("top5_sha256_missing")
    if not _is_file(escrow_md):
        blockers.append("escrow_md_missing")
    return {
        "atlas_protein_key": protein_key,
        "atlas_object_key": atlas_object_key,
        "source_lane": "massivefold_freeze_candidate",
        "target_id": _text(source.get("target_id")).upper(),
        "target_group": _text(source.get("target_group")),
        "protein_name": _text(source.get("protein_name")),
        "object_id": object_id,
        "object_role": "model1_candidate",
        "atlas_status": "pass" if not blockers else "blocked",
        "atlas_protein_folder": _artifact(atlas_protein_folder),
        "atlas_object_folder": _artifact(atlas_object_folder),
        "atlas_protein_readme": _artifact(atlas_protein_folder / "README.md"),
        "atlas_protein_manifest": _artifact(atlas_protein_folder / "protein_manifest.json"),
        "atlas_object_readme": _artifact(atlas_object_folder / "README.md"),
        "atlas_object_manifest": _artifact(atlas_object_folder / "object_manifest.json"),
        "source_protein_folder": _artifact(source_protein_folder),
        "source_object_folder": _artifact(source_object_folder),
        "source_protein_readme": _artifact(source_protein_readme),
        "source_protein_manifest": _artifact(source_protein_manifest),
        "source_object_readme": _artifact(source_object_readme),
        "source_object_manifest": _artifact(source_object_manifest),
        "model_path": _artifact(model_path),
        "model_sha256": _text(source.get("model_sha256")),
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "top5_manifest_csv": _artifact(top5_manifest),
        "top5_manifest_sha256": _text(source.get("top5_manifest_sha256")),
        "escrow_md": _artifact(escrow_md),
        "native_status": _text(source.get("native_status")) or "official_native_release_pending",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
        "source_policy": MASSIVEFOLD_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _protein_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["atlas_protein_key"]].append(row)
    protein_rows: list[dict[str, Any]] = []
    for protein_key, protein_objects in sorted(grouped.items()):
        blocked = [row for row in protein_objects if row["atlas_status"] != "pass"]
        lanes = sorted({row["source_lane"] for row in protein_objects})
        first = sorted(protein_objects, key=lambda row: (row["source_lane"], row["atlas_object_key"]))[0]
        protein_rows.append(
            {
                "atlas_protein_key": protein_key,
                "target_id": first["target_id"],
                "protein_name": first["protein_name"],
                "atlas_protein_folder": first["atlas_protein_folder"],
                "atlas_protein_readme": first["atlas_protein_readme"],
                "atlas_protein_manifest": first["atlas_protein_manifest"],
                "object_count": len(protein_objects),
                "object_pass_count": len(protein_objects) - len(blocked),
                "object_blocked_count": len(blocked),
                "source_lanes": ",".join(lanes),
                "protein_status": "pass" if not blocked else "blocked",
                "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
            }
        )
    return protein_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    current_payload = _read_json(args.current_object_library_json)
    massivefold_payload = _read_json(args.massivefold_freeze_protein_library_json)
    out_dir = _resolve(args.out_dir)
    current_rows = [_current_row(row, out_dir) for row in _rows(current_payload)]
    massivefold_rows = [_massivefold_row(row, out_dir) for row in _rows(massivefold_payload)]
    rows = sorted(
        current_rows + massivefold_rows,
        key=lambda row: (row["atlas_protein_key"], row["source_lane"], row["atlas_object_key"]),
    )
    protein_rows = _protein_rows(rows)
    blocked = [row for row in rows if row["atlas_status"] != "pass"]
    current_keys = {row["atlas_protein_key"] for row in current_rows}
    massivefold_keys = {row["atlas_protein_key"] for row in massivefold_rows}
    first = rows[0] if rows else {}
    status = "casp17_3d_molecular_object_atlas_ready_review_only"
    if not rows:
        status = "casp17_3d_molecular_object_atlas_blocked_no_objects"
    elif blocked:
        status = "casp17_3d_molecular_object_atlas_blocked"
    summary = {
        "packet_type": "casp17_3d_molecular_object_atlas",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "casp17_3d_molecular_object_atlas_status": status,
        "current_object_library_status": _text(_summary(current_payload).get("protein_object_library_status")),
        "massivefold_freeze_candidate_protein_library_status": _text(
            _summary(massivefold_payload).get("massivefold_freeze_candidate_protein_library_status")
        ),
        "atlas_dir": _artifact(out_dir),
        "html_atlas_path": _artifact(args.out_html),
        "protein_count": len(protein_rows),
        "protein_pass_count": sum(1 for row in protein_rows if row["protein_status"] == "pass"),
        "protein_blocked_count": sum(1 for row in protein_rows if row["protein_status"] != "pass"),
        "object_count": len(rows),
        "object_pass_count": len(rows) - len(blocked),
        "object_blocked_count": len(blocked),
        "current_object_count": len(current_rows),
        "massivefold_freeze_object_count": len(massivefold_rows),
        "current_protein_count": len(current_keys),
        "massivefold_freeze_protein_count": len(massivefold_keys),
        "overlap_protein_count": len(current_keys & massivefold_keys),
        "model_link_count": sum(1 for row in rows if _is_file(row["model_path"])),
        "viewer_link_count": sum(1 for row in rows if _is_file(row["viewer_html"])),
        "projection_link_count": sum(1 for row in rows if _is_file(row["projection_svg"])),
        "top5_link_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "escrow_link_count": sum(1 for row in rows if _is_file(row["escrow_md"])),
        "model_sha256_count": sum(1 for row in rows if _text(row.get("model_sha256"))),
        "top5_sha256_count": sum(1 for row in rows if _text(row.get("top5_manifest_sha256"))),
        "source_object_manifest_link_count": sum(1 for row in rows if _is_file(row["source_object_manifest"])),
        "source_object_readme_link_count": sum(1 for row in rows if _is_file(row["source_object_readme"])),
        "atlas_object_manifest_expected_count": len(rows),
        "atlas_object_readme_expected_count": len(rows),
        "native_accuracy_count": 0,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_blocked_protein_key": _text(blocked[0].get("atlas_protein_key")) if blocked else "",
        "first_blocked_object_key": _text(blocked[0].get("atlas_object_key")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": (
            "Use the unified atlas to inspect every CASP17 3D object by protein name while strict-blind "
            "competitive proof and native metrics remain separately gated."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }
    return {"summary": summary, "protein_rows": protein_rows, "rows": rows}


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


def _write_atlas_files(payload: dict[str, Any]) -> None:
    by_protein: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        by_protein[row["atlas_protein_key"]].append(row)
        object_folder = _resolve(row["atlas_object_folder"])
        object_folder.mkdir(parents=True, exist_ok=True)
        _write_json(row["atlas_object_manifest"], {"summary": row})
        object_lines = [
            f"# {row['atlas_protein_key']} / {row['atlas_object_key']}",
            "",
            f"- source lane: `{row['source_lane']}`",
            f"- target: `{row['target_id']}`",
            f"- object: `{row['object_id']}`",
            f"- status: `{row['atlas_status']}`",
            f"- model: `{row['model_path']}`",
            f"- viewer: `{row['viewer_html']}`",
            f"- projection: `{row['projection_svg']}`",
            f"- source object manifest: `{row['source_object_manifest']}`",
            f"- top5 manifest: `{row['top5_manifest_csv'] or '-'}`",
            f"- escrow: `{row['escrow_md'] or '-'}`",
            f"- competitive proof eligible: `{row['competitive_proof_eligible']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
        _resolve(row["atlas_object_readme"]).write_text("\n".join(object_lines), encoding="utf-8")
    for protein in payload["protein_rows"]:
        protein_objects = sorted(
            by_protein[protein["atlas_protein_key"]],
            key=lambda row: (row["source_lane"], row["atlas_object_key"]),
        )
        protein_folder = _resolve(protein["atlas_protein_folder"])
        protein_folder.mkdir(parents=True, exist_ok=True)
        _write_json(protein["atlas_protein_manifest"], {"summary": protein, "objects": protein_objects})
        protein_lines = [
            f"# {protein['protein_name']}",
            "",
            f"- protein key: `{protein['atlas_protein_key']}`",
            f"- target: `{protein['target_id']}`",
            f"- objects pass/blocked/total: `{protein['object_pass_count']}/{protein['object_blocked_count']}/{protein['object_count']}`",
            f"- source lanes: `{protein['source_lanes']}`",
            "",
            "## Objects",
            "",
            "| object | source | status | viewer | model |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in protein_objects:
            protein_lines.append(
                f"| `{row['atlas_object_key']}` | `{row['source_lane']}` | `{row['atlas_status']}` | "
                f"`{row['viewer_html']}` | `{row['model_path']}` |"
            )
        protein_lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        _resolve(protein["atlas_protein_readme"]).write_text("\n".join(protein_lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 3D Molecular Object Atlas",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['casp17_3d_molecular_object_atlas_status']}`",
        f"- proteins pass/blocked/total: `{summary['protein_pass_count']}/{summary['protein_blocked_count']}/{summary['protein_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- source objects current/massivefold: `{summary['current_object_count']}/{summary['massivefold_freeze_object_count']}`",
        f"- source proteins current/massivefold/overlap: `{summary['current_protein_count']}/{summary['massivefold_freeze_protein_count']}/{summary['overlap_protein_count']}`",
        f"- links model/viewer/projection/top5/escrow: `{summary['model_link_count']}/{summary['viewer_link_count']}/{summary['projection_link_count']}/{summary['top5_link_count']}/{summary['escrow_link_count']}`",
        f"- sha model/top5: `{summary['model_sha256_count']}/{summary['top5_sha256_count']}`",
        f"- native/proof/author: `{summary['native_accuracy_count']}/{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html atlas: `{summary['html_atlas_path']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}` blocked `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Protein Folders",
        "",
        "| protein | objects | lanes | folder |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["protein_rows"]:
        lines.append(
            f"| `{row['atlas_protein_key']}` | `{row['object_pass_count']}/{row['object_blocked_count']}/{row['object_count']}` | "
            f"`{row['source_lanes']}` | `{row['atlas_protein_folder']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    rows = []
    for row in payload["rows"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(row['target_id'])}</td>"
            f"<td>{html.escape(row['protein_name'])}</td>"
            f"<td>{html.escape(row['atlas_object_key'])}</td>"
            f"<td>{html.escape(row['source_lane'])}</td>"
            f"<td>{html.escape(row['atlas_status'])}</td>"
            f"<td><a href=\"{html.escape(_href(row['atlas_object_readme'], path))}\">object</a></td>"
            f"<td><a href=\"{html.escape(_href(row['viewer_html'], path))}\">viewer</a></td>"
            f"<td><a href=\"{html.escape(_href(row['model_path'], path))}\">model</a></td>"
            "</tr>"
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 3D Molecular Object Atlas</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 3D Molecular Object Atlas</h1>",
            f"<p>Status: <code>{html.escape(summary['casp17_3d_molecular_object_atlas_status'])}</code></p>",
            f"<p>Proteins: {summary['protein_pass_count']}/{summary['protein_blocked_count']}/{summary['protein_count']} pass/blocked/total. Objects: {summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}.</p>",
            "<table><thead><tr><th>target</th><th>protein</th><th>object</th><th>source</th><th>status</th><th>folder</th><th>viewer</th><th>model</th></tr></thead><tbody>",
            "\n".join(rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_atlas_files(payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 unified 3D molecular object atlas.")
    parser.add_argument("--current-object-library-json", default=DEFAULT_CURRENT_OBJECT_LIBRARY_JSON)
    parser.add_argument(
        "--massivefold-freeze-protein-library-json",
        default=DEFAULT_MASSIVEFOLD_FREEZE_PROTEIN_LIBRARY_JSON,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
