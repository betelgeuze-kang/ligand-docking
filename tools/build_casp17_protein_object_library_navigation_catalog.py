#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMPLETION_AUDIT_JSON = "casp17/casp17_protein_object_library_completion_audit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_protein_object_library_navigation_catalog_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_protein_object_library_navigation_catalog_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_PROTEIN_OBJECT_LIBRARY_NAVIGATION_CATALOG.md"
DEFAULT_OUT_HTML = "casp17/casp17_protein_object_library_navigation_catalog_current.html"

CLAIM_BOUNDARY = (
    "Local CASP17 protein-name 3D object navigation catalog only. It indexes already-generated "
    "protein folders, per-object folders, manifests, model files, projections, and local viewers. "
    "It does not fetch structures, score native accuracy, create predictions, or submit to CASP."
)

ROW_COLUMNS = [
    "protein_key",
    "target_id",
    "protein_name",
    "protein_status",
    "object_count",
    "pass_count",
    "blocked_count",
    "chain_ids",
    "library_protein_folder",
    "protein_readme",
    "protein_manifest",
    "first_object_id",
    "first_viewer_html_path",
    "first_projection_svg_path",
    "first_model_path",
    "catalog_status",
    "blockers",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _object_rows_by_protein(object_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in object_rows:
        grouped.setdefault(_text(row.get("protein_key")), []).append(row)
    return grouped


def _catalog_row(protein_row: dict[str, Any], object_rows: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_objects = sorted(object_rows, key=lambda row: (_text(row.get("chain_id")), _text(row.get("object_id"))))
    first_object = sorted_objects[0] if sorted_objects else {}
    blockers: list[str] = []
    if _text(protein_row.get("protein_status")) != "pass":
        blockers.append("protein_status_not_pass")
    if not sorted_objects:
        blockers.append("protein_object_rows_missing")
    if not _is_dir(protein_row.get("library_protein_folder", "")):
        blockers.append("protein_folder_missing")
    if not _is_file(protein_row.get("protein_readme", "")):
        blockers.append("protein_readme_missing")
    if not _is_file(protein_row.get("protein_manifest", "")):
        blockers.append("protein_manifest_missing")
    blocked_objects = [row for row in sorted_objects if _text(row.get("audit_status")) != "pass"]
    if blocked_objects:
        blockers.append("object_audit_blocked")
    chain_ids = ",".join(_text(row.get("chain_id")) for row in sorted_objects if _text(row.get("chain_id")))
    return {
        "protein_key": _text(protein_row.get("protein_key")),
        "target_id": _text(protein_row.get("target_id")),
        "protein_name": _text(protein_row.get("protein_name")),
        "protein_status": _text(protein_row.get("protein_status")),
        "object_count": len(sorted_objects),
        "pass_count": sum(1 for row in sorted_objects if _text(row.get("audit_status")) == "pass"),
        "blocked_count": len(blocked_objects),
        "chain_ids": chain_ids,
        "library_protein_folder": _text(protein_row.get("library_protein_folder")),
        "protein_readme": _text(protein_row.get("protein_readme")),
        "protein_manifest": _text(protein_row.get("protein_manifest")),
        "first_object_id": _text(first_object.get("object_id")),
        "first_viewer_html_path": _text(first_object.get("viewer_html_path")),
        "first_projection_svg_path": _text(first_object.get("projection_svg_path")),
        "first_model_path": _text(first_object.get("model_path")),
        "catalog_status": "pass" if not blockers else "blocked",
        "blockers": ",".join(blockers),
    }


def _build_rows(completion_payload: dict[str, Any]) -> list[dict[str, Any]]:
    object_rows = _rows(completion_payload)
    grouped = _object_rows_by_protein(object_rows)
    return [
        _catalog_row(protein_row, grouped.get(_text(protein_row.get("protein_key")), []))
        for protein_row in _rows(completion_payload, "protein_rows")
    ]


def _build_summary(
    args: argparse.Namespace,
    completion_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    input_exists: bool,
) -> dict[str, Any]:
    completion_summary = _summary(completion_payload)
    blocked = [row for row in rows if row["catalog_status"] != "pass"]
    largest = max(rows, key=lambda row: _int(row.get("object_count")), default={})
    first = rows[0] if rows else {}
    status = "protein_object_library_navigation_catalog_ready"
    if not input_exists:
        status = "blocked_completion_audit_missing"
    elif _text(completion_summary.get("completion_audit_status")) != "pass":
        status = "blocked_completion_audit_not_pass"
    elif not rows:
        status = "blocked_no_protein_rows"
    elif blocked:
        status = "blocked_navigation_catalog"
    return {
        "packet_type": "casp17_protein_object_library_navigation_catalog",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "navigation_catalog_status": status,
        "completion_audit_json": _artifact(args.completion_audit_json),
        "completion_audit_status": _text(completion_summary.get("completion_audit_status")),
        "protein_count": len(rows),
        "protein_pass_count": len(rows) - len(blocked),
        "protein_blocked_count": len(blocked),
        "object_count": sum(_int(row.get("object_count")) for row in rows),
        "object_pass_count": sum(_int(row.get("pass_count")) for row in rows),
        "object_blocked_count": sum(_int(row.get("blocked_count")) for row in rows),
        "protein_readme_link_count": sum(1 for row in rows if _is_file(row["protein_readme"])),
        "protein_manifest_link_count": sum(1 for row in rows if _is_file(row["protein_manifest"])),
        "first_protein_key": _text(first.get("protein_key")),
        "largest_protein_key": _text(largest.get("protein_key")),
        "largest_object_count": _int(largest.get("object_count")),
        "first_blocked_protein_key": _text(blocked[0].get("protein_key")) if blocked else "",
        "first_blocked_blockers": _text(blocked[0].get("blockers")) if blocked else "",
        "html_catalog_path": _artifact(args.out_html),
        "next_action": (
            "Use the protein-name navigation catalog to jump from each protein folder to its chain/object "
            "viewer, projection, model, and manifest while strict-blind benchmark evidence is filled."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.completion_audit_json)
    completion_payload = _read_json(input_path)
    rows = _build_rows(completion_payload)
    summary = _build_summary(args, completion_payload, rows, input_path.exists())
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
        "# CASP17 Protein Object Library Navigation Catalog",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['navigation_catalog_status']}`",
        f"- proteins pass/blocked/total: `{summary['protein_pass_count']}/{summary['protein_blocked_count']}/{summary['protein_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- protein readme/manifest links: `{summary['protein_readme_link_count']}/{summary['protein_manifest_link_count']}`",
        f"- largest protein folder: `{summary['largest_protein_key'] or '-'}` objects `{summary['largest_object_count']}`",
        f"- html catalog: `{summary['html_catalog_path']}`",
        f"- first blocked: `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Protein Folders",
        "",
        "| protein | target | objects | chains | status | folder | first viewer |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['protein_key']}` | `{row['target_id']}` | {row['object_count']} | "
            f"`{row['chain_ids'] or '-'}` | `{row['catalog_status']}` | "
            f"`{row['library_protein_folder']}` | `{row['first_viewer_html_path'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | 0 | - | `blocked` | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>CASP17 Protein Object Library Navigation Catalog</title>",
        "<style>",
        ":root { color-scheme: light; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }",
        "body { margin: 0; }",
        "header { position: sticky; top: 0; background: rgba(248,250,252,.96); border-bottom: 1px solid #cbd5e1; padding: 14px 18px; z-index: 2; }",
        "h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }",
        ".meta { color: #475569; display: flex; flex-wrap: wrap; gap: 10px; font-size: 13px; }",
        "main { padding: 18px; display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 12px; }",
        ".card { background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; display: grid; gap: 9px; }",
        ".name { font-weight: 700; overflow-wrap: anywhere; line-height: 1.3; }",
        ".stats { color: #475569; font-size: 12px; line-height: 1.45; }",
        ".links { display: flex; flex-wrap: wrap; gap: 8px; }",
        "a { color: #0f766e; text-decoration: none; font-size: 12px; font-weight: 700; }",
        "a:hover { text-decoration: underline; }",
        ".pass { color: #166534; font-weight: 700; font-size: 12px; }",
        ".blocked { color: #991b1b; font-weight: 700; font-size: 12px; }",
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        "<h1>CASP17 Protein Object Library Navigation Catalog</h1>",
        '<div class="meta">',
        f"<span>generated: {html.escape(str(summary['generated_at_local']))}</span>",
        f"<span>status: {html.escape(str(summary['navigation_catalog_status']))}</span>",
        f"<span>proteins: {summary['protein_pass_count']}/{summary['protein_count']}</span>",
        f"<span>objects: {summary['object_pass_count']}/{summary['object_count']}</span>",
        "</div>",
        "</header>",
        "<main>",
    ]
    for row in payload["rows"]:
        status = _text(row.get("catalog_status"))
        folder = _href(row["library_protein_folder"], path)
        readme = _href(row["protein_readme"], path)
        manifest = _href(row["protein_manifest"], path)
        viewer = _href(row["first_viewer_html_path"], path) if row["first_viewer_html_path"] else ""
        projection = _href(row["first_projection_svg_path"], path) if row["first_projection_svg_path"] else ""
        model = _href(row["first_model_path"], path) if row["first_model_path"] else ""
        lines.extend(
            [
                '<article class="card">',
                f'<div class="name">{html.escape(_text(row.get("protein_name")))}<br><span class="stats">{html.escape(_text(row.get("protein_key")))}</span></div>',
                f'<div class="{html.escape(status)}">{html.escape(status)}</div>',
                (
                    '<div class="stats">'
                    f"target {html.escape(_text(row.get('target_id')))}<br>"
                    f"objects {row['object_count']} / chains {html.escape(_text(row.get('chain_ids')) or '-')}<br>"
                    f"blockers {html.escape(_text(row.get('blockers')) or '-')}"
                    "</div>"
                ),
                '<div class="links">',
                f'<a href="{html.escape(folder, quote=True)}">Folder</a>',
                f'<a href="{html.escape(readme, quote=True)}">README</a>',
                f'<a href="{html.escape(manifest, quote=True)}">Manifest</a>',
            ]
        )
        if viewer:
            lines.append(f'<a href="{html.escape(viewer, quote=True)}">First Viewer</a>')
        if projection:
            lines.append(f'<a href="{html.escape(projection, quote=True)}">Projection</a>')
        if model:
            lines.append(f'<a href="{html.escape(model, quote=True)}">Model</a>')
        lines.extend(["</div>", "</article>"])
    if not payload["rows"]:
        lines.append("<p>No protein folders were available.</p>")
    lines.extend(
        [
            "</main>",
            f"<!-- {html.escape(CLAIM_BOUNDARY)} -->",
            "</body>",
            "</html>",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 protein-name 3D object navigation catalog.")
    parser.add_argument("--completion-audit-json", default=DEFAULT_COMPLETION_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["navigation_catalog_status"] != "protein_object_library_navigation_catalog_ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
