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

DEFAULT_METRIC_HANDOFF_JSON = "casp17/casp17_3d_molecular_object_metric_handoff_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_3d_molecular_object_metric_handoff_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_molecular_object_metric_handoff_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_MOLECULAR_OBJECT_METRIC_HANDOFF_COMPLETION_AUDIT.md"
DEFAULT_OUT_HTML = "casp17/casp17_3d_molecular_object_metric_handoff_completion_audit_current.html"

READY_HANDOFF_PREFIX = "casp17_3d_molecular_object_metric_handoff_ready_review_only"
METRIC_EVIDENCE_STATUS = "awaiting_strict_blind_native_metric_evidence"
CLAIM_BOUNDARY = (
    "CASP17 3D molecular object metric handoff completion audit only. It verifies handoff folders, "
    "per-object manifests, metric requirement CSV/Markdown files, source links, no-coordinate-copy "
    "hygiene, and proof boundary flags. It does not copy model coordinates, compute native accuracy, "
    "serialize a CASP author code, claim strict-blind competitive proof, or submit to CASP."
)

ROW_COLUMNS = [
    "atlas_protein_key",
    "atlas_object_key",
    "source_lane",
    "target_id",
    "protein_name",
    "object_id",
    "metric_family",
    "audit_status",
    "handoff_status",
    "metric_evidence_status",
    "metric_requirement_count",
    "metric_requirement_csv_row_count",
    "required_metric_names",
    "metric_csv_names",
    "handoff_protein_folder",
    "handoff_protein_readme",
    "handoff_protein_manifest",
    "handoff_object_folder",
    "handoff_object_manifest",
    "metric_requirements_csv",
    "metric_handoff_md",
    "atlas_object_folder",
    "atlas_object_manifest",
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


def _metric_csv_names(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [_text(row.get("metric_name")) for row in csv.DictReader(handle) if _text(row.get("metric_name"))]
    except OSError:
        return []


def _audit_row(row: dict[str, Any], global_blockers: list[str]) -> dict[str, Any]:
    blockers = global_blockers[:]
    handoff_protein_folder = _text(row.get("handoff_protein_folder"))
    handoff_object_folder = _text(row.get("handoff_object_folder"))
    handoff_protein_readme = str(_resolve(handoff_protein_folder) / "README.md") if handoff_protein_folder else ""
    metric_names = [_text(metric) for metric in _text(row.get("required_metric_names")).split("|") if _text(metric)]
    csv_metric_names = _metric_csv_names(_text(row.get("metric_requirements_csv")))
    coordinate_copy_count = _coordinate_copy_count(handoff_object_folder)
    required_paths = [
        ("handoff_protein_folder_missing", handoff_protein_folder, _is_dir),
        ("handoff_protein_readme_missing", handoff_protein_readme, _is_file),
        ("handoff_protein_manifest_missing", row.get("handoff_protein_manifest"), _is_file),
        ("handoff_object_folder_missing", handoff_object_folder, _is_dir),
        ("handoff_object_manifest_missing", row.get("handoff_object_manifest"), _is_file),
        ("metric_requirements_csv_missing", row.get("metric_requirements_csv"), _is_file),
        ("metric_handoff_md_missing", row.get("metric_handoff_md"), _is_file),
        ("atlas_object_folder_missing", row.get("atlas_object_folder"), _is_dir),
        ("atlas_object_manifest_missing", row.get("atlas_object_manifest"), _is_file),
        ("model_file_missing", row.get("model_path"), _is_file),
        ("viewer_html_missing", row.get("viewer_html"), _is_file),
        ("projection_svg_missing", row.get("projection_svg"), _is_file),
    ]
    for blocker, path_like, predicate in required_paths:
        if not predicate(_text(path_like)):
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
    if _text(row.get("handoff_status")) != "ready_review_only":
        blockers.append("handoff_row_status_not_ready_review_only")
    if _text(row.get("metric_evidence_status")) != METRIC_EVIDENCE_STATUS:
        blockers.append("metric_evidence_status_not_awaiting_strict_blind")
    if _int(row.get("metric_requirement_count")) <= 0:
        blockers.append("metric_requirement_count_missing")
    if len(csv_metric_names) != _int(row.get("metric_requirement_count")):
        blockers.append("metric_requirement_csv_row_count_mismatch")
    if csv_metric_names != metric_names:
        blockers.append("metric_requirement_csv_names_mismatch")
    if coordinate_copy_count:
        blockers.append("handoff_coordinate_copy_present")
    if _text(row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if _text(row.get("author_serialized")).lower() != "false":
        blockers.append("author_serialized_not_false")
    return {
        "atlas_protein_key": _text(row.get("atlas_protein_key")),
        "atlas_object_key": _text(row.get("atlas_object_key")),
        "source_lane": _text(row.get("source_lane")),
        "target_id": _text(row.get("target_id")),
        "protein_name": _text(row.get("protein_name")),
        "object_id": _text(row.get("object_id")),
        "metric_family": _text(row.get("metric_family")),
        "audit_status": "pass" if not blockers else "blocked",
        "handoff_status": _text(row.get("handoff_status")),
        "metric_evidence_status": _text(row.get("metric_evidence_status")),
        "metric_requirement_count": _int(row.get("metric_requirement_count")),
        "metric_requirement_csv_row_count": len(csv_metric_names),
        "required_metric_names": "|".join(metric_names),
        "metric_csv_names": "|".join(csv_metric_names),
        "handoff_protein_folder": _artifact(handoff_protein_folder),
        "handoff_protein_readme": _artifact(handoff_protein_readme),
        "handoff_protein_manifest": _artifact(row.get("handoff_protein_manifest", "")),
        "handoff_object_folder": _artifact(handoff_object_folder),
        "handoff_object_manifest": _artifact(row.get("handoff_object_manifest", "")),
        "metric_requirements_csv": _artifact(row.get("metric_requirements_csv", "")),
        "metric_handoff_md": _artifact(row.get("metric_handoff_md", "")),
        "atlas_object_folder": _artifact(row.get("atlas_object_folder", "")),
        "atlas_object_manifest": _artifact(row.get("atlas_object_manifest", "")),
        "model_path": _artifact(row.get("model_path", "")),
        "viewer_html": _artifact(row.get("viewer_html", "")),
        "projection_svg": _artifact(row.get("projection_svg", "")),
        "top5_manifest_csv": _artifact(row.get("top5_manifest_csv", "")),
        "escrow_md": _artifact(row.get("escrow_md", "")),
        "coordinate_copy_count": coordinate_copy_count,
        "competitive_proof_eligible": _text(row.get("competitive_proof_eligible")),
        "author_serialized": _text(row.get("author_serialized")),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    handoff_payload = _read_json(args.metric_handoff_json)
    handoff_summary = _summary(handoff_payload)
    handoff_status = _text(handoff_summary.get("metric_handoff_status"))
    global_blockers: list[str] = []
    if not handoff_status.startswith(READY_HANDOFF_PREFIX):
        global_blockers.append("metric_handoff_status_not_ready_review_only")
    rows = [_audit_row(row, global_blockers) for row in _rows(handoff_payload)]
    blocked = [row for row in rows if row["audit_status"] != "pass"]
    protein_rows = _rows(handoff_payload, "protein_rows")
    out_dir = _text(handoff_summary.get("out_dir"))
    out_dir_coordinate_copy_count = _coordinate_copy_count(out_dir)
    protein_folder_count = sum(1 for row in protein_rows if _is_dir(row.get("handoff_protein_folder", "")))
    protein_readme_count = sum(
        1 for row in protein_rows if _is_file(str(_resolve(row.get("handoff_protein_folder", "")) / "README.md"))
    )
    protein_manifest_count = sum(1 for row in protein_rows if _is_file(row.get("handoff_protein_manifest", "")))
    status = "casp17_3d_molecular_object_metric_handoff_completion_audit_pass"
    if not rows:
        status = "casp17_3d_molecular_object_metric_handoff_completion_audit_blocked_no_objects"
    elif blocked or out_dir_coordinate_copy_count:
        status = "casp17_3d_molecular_object_metric_handoff_completion_audit_blocked"
    first = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_3d_molecular_object_metric_handoff_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "metric_handoff_completion_audit_status": status,
        "metric_handoff_json": _artifact(args.metric_handoff_json),
        "metric_handoff_status": handoff_status,
        "out_dir": _artifact(out_dir),
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
        "handoff_object_folder_present_count": sum(1 for row in rows if _is_dir(row["handoff_object_folder"])),
        "handoff_object_manifest_present_count": sum(1 for row in rows if _is_file(row["handoff_object_manifest"])),
        "metric_requirements_csv_present_count": sum(1 for row in rows if _is_file(row["metric_requirements_csv"])),
        "metric_handoff_md_present_count": sum(1 for row in rows if _is_file(row["metric_handoff_md"])),
        "atlas_object_manifest_present_count": sum(1 for row in rows if _is_file(row["atlas_object_manifest"])),
        "model_link_present_count": sum(1 for row in rows if _is_file(row["model_path"])),
        "viewer_link_present_count": sum(1 for row in rows if _is_file(row["viewer_html"])),
        "projection_link_present_count": sum(1 for row in rows if _is_file(row["projection_svg"])),
        "top5_link_present_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "escrow_link_present_count": sum(1 for row in rows if _is_file(row["escrow_md"])),
        "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in rows),
        "metric_requirement_csv_row_count": sum(_int(row.get("metric_requirement_csv_row_count")) for row in rows),
        "metric_requirement_csv_mismatch_count": sum(
            1
            for row in rows
            if _int(row.get("metric_requirement_count")) != _int(row.get("metric_requirement_csv_row_count"))
            or _text(row.get("required_metric_names")) != _text(row.get("metric_csv_names"))
        ),
        "metric_evidence_awaiting_count": sum(
            1 for row in rows if row["metric_evidence_status"] == METRIC_EVIDENCE_STATUS
        ),
        "object_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "out_dir_coordinate_copy_count": out_dir_coordinate_copy_count,
        "native_accuracy_count": 0,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_object_key": _text(first.get("atlas_object_key")),
        "first_protein_key": _text(first.get("atlas_protein_key")),
        "first_blocked_object_key": _text(blocked[0].get("atlas_object_key")) if blocked else "",
        "first_blocked_protein_key": _text(blocked[0].get("atlas_protein_key")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": "Use this green completion audit before relying on the 3D object metric handoff for review-only metric planning.",
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
        "# CASP17 3D Molecular Object Metric Handoff Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['metric_handoff_completion_audit_status']}`",
        f"- handoff status: `{summary['metric_handoff_status']}`",
        f"- proteins folder/readme/manifest/total: `{summary['protein_folder_present_count']}/{summary['protein_readme_present_count']}/{summary['protein_manifest_present_count']}/{summary['protein_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- source objects current/massivefold: `{summary['current_object_count']}/{summary['massivefold_freeze_object_count']}`",
        f"- object files folder/manifest/csv/md: `{summary['handoff_object_folder_present_count']}/{summary['handoff_object_manifest_present_count']}/{summary['metric_requirements_csv_present_count']}/{summary['metric_handoff_md_present_count']}`",
        f"- metric rows expected/csv/mismatch: `{summary['metric_requirement_count']}/{summary['metric_requirement_csv_row_count']}/{summary['metric_requirement_csv_mismatch_count']}`",
        f"- links model/viewer/projection/top5/escrow: `{summary['model_link_present_count']}/{summary['viewer_link_present_count']}/{summary['projection_link_present_count']}/{summary['top5_link_present_count']}/{summary['escrow_link_present_count']}`",
        f"- metric evidence awaiting: `{summary['metric_evidence_awaiting_count']}`",
        f"- coordinate copies object/out_dir: `{summary['object_coordinate_copy_count']}/{summary['out_dir_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html audit: `{summary['html_audit_path']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` `{summary['first_object_key'] or '-'}` blocked `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Object Rows",
        "",
        "| protein | object | family | status | metrics | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['atlas_protein_key']}` | `{row['atlas_object_key']}` | `{row['metric_family']}` | "
            f"`{row['audit_status']}` | `{row['metric_requirement_csv_row_count']}/{row['metric_requirement_count']}` | "
            f"`{row['blockers'] or '-'}` |"
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
            f"<td>{html.escape(row['metric_family'])}</td>"
            f"<td>{html.escape(row['audit_status'])}</td>"
            f"<td>{row['metric_requirement_csv_row_count']}/{row['metric_requirement_count']}</td>"
            f"<td>{html.escape(row['blockers'] or '-')}</td>"
            "</tr>"
        )
    path = _resolve(path_like)
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 3D Molecular Object Metric Handoff Completion Audit</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 3D Molecular Object Metric Handoff Completion Audit</h1>",
            f"<p>Status: <code>{html.escape(summary['metric_handoff_completion_audit_status'])}</code></p>",
            f"<p>Objects: {summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']} pass/blocked/total.</p>",
            "<table><thead><tr><th>target</th><th>protein</th><th>object</th><th>family</th><th>status</th><th>metrics</th><th>blockers</th></tr></thead><tbody>",
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
    parser = argparse.ArgumentParser(description="Audit CASP17 3D molecular object metric handoff completion.")
    parser.add_argument("--metric-handoff-json", default=DEFAULT_METRIC_HANDOFF_JSON)
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
