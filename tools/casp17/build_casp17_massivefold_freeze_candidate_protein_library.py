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


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FREEZE_CANDIDATE_ESCROW_JSON = "casp17/casp17_massivefold_freeze_candidate_escrow_current.json"
DEFAULT_CURRENT_UPLOAD_QUEUE_JSON = "casp17/casp17_current_upload_queue_current.json"
DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OFFICIAL_TARGETLIST_CSV = "casp17/casp17_official_targetlist_snapshot_current.csv"
DEFAULT_OUT_DIR = "casp17/massivefold_freeze_candidate_protein_library"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_freeze_candidate_protein_library_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_freeze_candidate_protein_library_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_FREEZE_CANDIDATE_PROTEIN_LIBRARY.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_freeze_candidate_protein_library_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold freeze-candidate protein library only. It organizes external-only freeze "
    "candidates into protein-name folders with pointers to SHA-escrowed models, viewers, projections, "
    "and top5 manifests. It does not copy native structures, create internal predictions, score native "
    "accuracy, serialize a CASP author code, or submit to CASP."
)
EXTERNAL_ONLY_POLICY = "external_no_native_freeze_candidate_protein_library_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
OBJECT_ID = "model1_candidate"

ROW_COLUMNS = [
    "protein_key",
    "target_id",
    "protein_name",
    "protein_name_source",
    "target_group",
    "library_status",
    "object_id",
    "object_count",
    "library_protein_folder",
    "library_object_folder",
    "protein_readme",
    "protein_manifest",
    "object_readme",
    "object_manifest",
    "model_path",
    "model_sha256",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "top5_manifest_sha256",
    "escrow_md",
    "official_description",
    "human_expiration",
    "qa_expiration",
    "decision_class",
    "native_status",
    "competitive_proof_eligible",
    "blockers",
    "external_only_policy",
    "internal_prediction_policy",
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


def _is_true(value: Any) -> bool:
    return _text(value).lower() == "true"


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part).strip("_") or "unknown"


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


def _read_official_csv(path_like: str | Path) -> dict[str, dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        rows = list(csv.DictReader(handle, delimiter=delimiter))
    return {_text(row.get("Target")).upper(): row for row in rows if _text(row.get("Target"))}


def _is_file(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _protein_name_and_source(
    target_id: str,
    queue_row: dict[str, Any],
    folder_row: dict[str, Any],
    official_row: dict[str, str],
    target_group: str,
) -> tuple[str, str]:
    queue_name = _text(queue_row.get("protein_name"))
    if queue_name:
        return queue_name, "current_upload_queue"
    folder_name = _text(folder_row.get("protein_name"))
    if folder_name:
        return folder_name, "target_model_folders"
    official_name = _text(official_row.get("Description"))
    if official_name:
        return official_name, "official_targetlist"
    return f"{target_id} {target_group.replace('_', ' ')}", "fallback_target_group"


def _build_row(
    escrow_row: dict[str, Any],
    queue_row: dict[str, Any],
    folder_row: dict[str, Any],
    official_row: dict[str, str],
    out_dir: Path,
) -> dict[str, Any]:
    target_id = _text(escrow_row.get("target_id")).upper()
    target_group = _text(escrow_row.get("target_group"))
    protein_name, protein_name_source = _protein_name_and_source(
        target_id, queue_row, folder_row, official_row, target_group
    )
    protein_key = f"{target_id}_{_safe_name(protein_name)}"
    protein_folder = out_dir / protein_key
    object_folder = protein_folder / OBJECT_ID
    protein_readme = protein_folder / "README.md"
    protein_manifest = protein_folder / "protein_manifest.json"
    object_readme = object_folder / "README.md"
    object_manifest = object_folder / "object_manifest.json"
    blockers: list[str] = []
    if _text(escrow_row.get("escrow_status")) != "freeze_candidate_escrow_ready_external_only":
        blockers.append("freeze_candidate_escrow_not_ready")
    if not _is_file(_text(escrow_row.get("model_path"))):
        blockers.append("model_file_missing")
    if not _text(escrow_row.get("model_sha256")):
        blockers.append("model_sha256_missing")
    if not _is_file(_text(escrow_row.get("viewer_html"))):
        blockers.append("viewer_html_missing")
    if not _is_file(_text(escrow_row.get("projection_svg"))):
        blockers.append("projection_svg_missing")
    if not _is_file(_text(escrow_row.get("top5_manifest_csv"))):
        blockers.append("top5_manifest_missing")
    if not _text(escrow_row.get("top5_manifest_sha256")):
        blockers.append("top5_sha256_missing")
    official_description = _text(official_row.get("Description"))
    if not official_description:
        blockers.append("official_description_missing")
    return {
        "protein_key": protein_key,
        "target_id": target_id,
        "protein_name": protein_name,
        "protein_name_source": protein_name_source,
        "target_group": target_group,
        "library_status": "pass" if not blockers else "blocked",
        "object_id": OBJECT_ID,
        "object_count": 1,
        "library_protein_folder": _artifact(protein_folder),
        "library_object_folder": _artifact(object_folder),
        "protein_readme": _artifact(protein_readme),
        "protein_manifest": _artifact(protein_manifest),
        "object_readme": _artifact(object_readme),
        "object_manifest": _artifact(object_manifest),
        "model_path": _text(escrow_row.get("model_path")),
        "model_sha256": _text(escrow_row.get("model_sha256")),
        "viewer_html": _text(escrow_row.get("viewer_html")),
        "projection_svg": _text(escrow_row.get("projection_svg")),
        "top5_manifest_csv": _text(escrow_row.get("top5_manifest_csv")),
        "top5_manifest_sha256": _text(escrow_row.get("top5_manifest_sha256")),
        "escrow_md": _text(escrow_row.get("escrow_md")),
        "official_description": official_description,
        "human_expiration": _text(queue_row.get("official_human_expiration")) or _text(official_row.get("Human Exp.")),
        "qa_expiration": _text(queue_row.get("official_qa_expiration")) or _text(official_row.get("QA Exp.")),
        "decision_class": _text(escrow_row.get("decision_class")),
        "native_status": _text(escrow_row.get("native_status")) or "official_native_release_pending",
        "competitive_proof_eligible": "false",
        "blockers": ",".join(blockers),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    escrow_payload = _read_json(args.freeze_candidate_escrow_json)
    queue_payload = _read_json(args.current_upload_queue_json)
    folder_payload = _read_json(args.target_model_folders_json)
    official_by_target = _read_official_csv(args.official_targetlist_csv)
    queue_by_target = _by_target(_rows(queue_payload))
    folder_by_target = _by_target(_rows(folder_payload))
    out_dir = _resolve(args.out_dir)
    rows = [
        _build_row(
            escrow_row,
            queue_by_target.get(_text(escrow_row.get("target_id")).upper(), {}),
            folder_by_target.get(_text(escrow_row.get("target_id")).upper(), {}),
            official_by_target.get(_text(escrow_row.get("target_id")).upper(), {}),
            out_dir,
        )
        for escrow_row in _rows(escrow_payload)
    ]
    rows.sort(key=lambda row: (row["target_group"], row["target_id"]))
    blocked = [row for row in rows if row["library_status"] != "pass"]
    summary = {
        "packet_type": "casp17_massivefold_freeze_candidate_protein_library",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_freeze_candidate_protein_library_status": (
            "massivefold_freeze_candidate_protein_library_ready_external_only"
            if rows and not blocked
            else (
                "massivefold_freeze_candidate_protein_library_partial_external_only"
                if rows
                else "massivefold_freeze_candidate_protein_library_blocked"
            )
        ),
        "freeze_candidate_escrow_status": _text(_summary(escrow_payload).get("massivefold_freeze_candidate_escrow_status")),
        "library_dir": _artifact(out_dir),
        "html_catalog_path": _artifact(args.out_html),
        "protein_count": len(rows),
        "protein_ready_count": len(rows) - len(blocked),
        "protein_blocked_count": len(blocked),
        "protein_pass_count": len(rows) - len(blocked),
        "object_count": sum(_int(row.get("object_count")) for row in rows),
        "object_ready_count": sum(_int(row.get("object_count")) for row in rows if row["library_status"] == "pass"),
        "object_blocked_count": sum(_int(row.get("object_count")) for row in blocked),
        "object_pass_count": sum(_int(row.get("object_count")) for row in rows if row["library_status"] == "pass"),
        "model_link_count": sum(1 for row in rows if _is_file(row["model_path"])),
        "viewer_link_count": sum(1 for row in rows if _is_file(row["viewer_html"])),
        "projection_link_count": sum(1 for row in rows if _is_file(row["projection_svg"])),
        "top5_link_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "escrow_link_count": sum(1 for row in rows if _is_file(row["escrow_md"])),
        "model_sha256_count": sum(1 for row in rows if _text(row.get("model_sha256"))),
        "top5_sha256_count": sum(1 for row in rows if _text(row.get("top5_manifest_sha256"))),
        "top5_manifest_link_count": sum(1 for row in rows if _is_file(row["top5_manifest_csv"])),
        "current_name_count": sum(
            1
            for row in rows
            if row.get("protein_name_source") in {"current_upload_queue", "target_model_folders"}
        ),
        "official_name_count": sum(1 for row in rows if _text(row.get("official_description"))),
        "official_description_count": sum(1 for row in rows if _text(row.get("official_description"))),
        "rna_hybrid_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "native_pending_count": len(rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_protein_key": _text(rows[0].get("protein_key")) if rows else "",
        "first_blocked_protein_key": _text(blocked[0].get("protein_key")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": "Open protein-name folders for freeze-candidate visual review; keep external-only proof boundary and run CASP rule checks separately.",
        "claim_boundary": CLAIM_BOUNDARY,
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
    }
    return {"summary": summary, "rows": rows}


def _write_target_files(row: dict[str, Any]) -> None:
    protein_folder = _resolve(row["library_protein_folder"])
    object_folder = _resolve(row["library_object_folder"])
    protein_folder.mkdir(parents=True, exist_ok=True)
    object_folder.mkdir(parents=True, exist_ok=True)
    _write_json(row["protein_manifest"], {"summary": row, "objects": [row]})
    _write_json(row["object_manifest"], {"summary": row})
    protein_lines = [
        f"# {row['protein_name']}",
        "",
        f"- target: `{row['target_id']}`",
        f"- protein folder key: `{row['protein_key']}`",
        f"- status: `{row['library_status']}`",
        f"- object: `{row['object_id']}`",
        f"- model: `{row['model_path']}`",
        f"- model sha256: `{row['model_sha256']}`",
        f"- viewer: `{row['viewer_html']}`",
        f"- projection: `{row['projection_svg']}`",
        f"- top5 manifest: `{row['top5_manifest_csv']}`",
        f"- escrow: `{row['escrow_md']}`",
        f"- native status: `{row['native_status']}`",
        f"- competitive proof eligible: `{row['competitive_proof_eligible']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    _resolve(row["protein_readme"]).write_text("\n".join(protein_lines), encoding="utf-8")
    object_lines = [
        f"# {row['target_id']} {row['object_id']}",
        "",
        f"- target group: `{row['target_group']}`",
        f"- decision class: `{row['decision_class']}`",
        f"- model path: `{row['model_path']}`",
        f"- model sha256: `{row['model_sha256']}`",
        f"- viewer: `{row['viewer_html']}`",
        f"- projection: `{row['projection_svg']}`",
        f"- top5 manifest: `{row['top5_manifest_csv']}`",
        f"- top5 sha256: `{row['top5_manifest_sha256']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    _resolve(row["object_readme"]).write_text("\n".join(object_lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Freeze-Candidate Protein Library",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_freeze_candidate_protein_library_status']}`",
        f"- proteins pass/blocked/total: `{summary['protein_pass_count']}/{summary['protein_blocked_count']}/{summary['protein_count']}`",
        f"- objects pass/blocked/total: `{summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}`",
        f"- sha model/top5: `{summary['model_sha256_count']}/{summary['top5_sha256_count']}`",
        f"- links model/viewer/projection/top5/escrow: `{summary['model_link_count']}/{summary['viewer_link_count']}/{summary['projection_link_count']}/{summary['top5_link_count']}/{summary['escrow_link_count']}`",
        f"- name sources current/official: `{summary['current_name_count']}/{summary['official_name_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_count']}/{summary['protein_complex_count']}`",
        f"- native/proof/author: `{summary['native_pending_count']}/{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html catalog: `{summary['html_catalog_path']}`",
        f"- first: `{summary['first_protein_key'] or '-'}` blocked `{summary['first_blocked_protein_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Protein Folders",
        "",
        "| protein | target | group | status | model | viewer | folder |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['protein_name']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['library_status']}` | `{row['model_path']}` | `{row['viewer_html']}` | "
            f"`{row['library_protein_folder']}` |"
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
            f"<td>{html.escape(row['target_group'])}</td>"
            f"<td>{html.escape(row['library_status'])}</td>"
            f"<td><a href=\"{html.escape(_href(row['protein_readme'], path))}\">folder</a></td>"
            f"<td><a href=\"{html.escape(_href(row['viewer_html'], path))}\">viewer</a></td>"
            f"<td><a href=\"{html.escape(_href(row['top5_manifest_csv'], path))}\">top5</a></td>"
            "</tr>"
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Freeze Candidate Protein Library</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 MassiveFold Freeze-Candidate Protein Library</h1>",
            f"<p>Status: <code>{html.escape(summary['massivefold_freeze_candidate_protein_library_status'])}</code></p>",
            f"<p>Proteins: {summary['protein_pass_count']}/{summary['protein_blocked_count']}/{summary['protein_count']} pass/blocked/total. Objects: {summary['object_pass_count']}/{summary['object_blocked_count']}/{summary['object_count']}.</p>",
            "<table><thead><tr><th>target</th><th>protein</th><th>group</th><th>status</th><th>folder</th><th>viewer</th><th>top5</th></tr></thead><tbody>",
            "\n".join(rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    for row in payload["rows"]:
        _write_target_files(row)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MassiveFold freeze-candidate protein-name library.")
    parser.add_argument("--freeze-candidate-escrow-json", default=DEFAULT_FREEZE_CANDIDATE_ESCROW_JSON)
    parser.add_argument("--current-upload-queue-json", default=DEFAULT_CURRENT_UPLOAD_QUEUE_JSON)
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--official-targetlist-csv", default=DEFAULT_OFFICIAL_TARGETLIST_CSV)
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
