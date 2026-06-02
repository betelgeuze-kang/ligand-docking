#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_POST_PROBE_SELECTOR_DECISION_JSON = (
    "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_freeze_candidate_format_preflight"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_FREEZE_CANDIDATE_FORMAT_PREFLIGHT.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold freeze-candidate format preflight only. It checks local external-only model "
    "candidate files, viewers, projections, target IDs, and top5 manifests before any operator-approved "
    "CASP rule check. It is not native accuracy, not internal prediction proof, not a CASP submission, "
    "and not permission to submit."
)
EXTERNAL_ONLY_POLICY = "external_no_native_freeze_candidate_format_preflight_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "external_freeze_candidate_format_preflight_v1"
FREEZE_CLASSES = {"freeze_candidate_existing", "freeze_candidate_after_probe"}
TARGET_ID_RE = re.compile(r"^[THRDM]\d{4,}$")
ALLOWED_SELECTED_EXTENSIONS = {".pdb", ".cif"}
ALLOWED_MODEL_PATH_EXTENSIONS = {".pdb", ".cif", ".mmcif"}

ROW_COLUMNS = [
    "preflight_rank",
    "preflight_status",
    "target_group",
    "target_id",
    "decision_rank",
    "decision_class",
    "final_selector_decision",
    "selected_model_filename",
    "selected_model_extension",
    "packaged_model_extension",
    "model_path",
    "model_size_bytes",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "source_decision_md",
    "preflight_md",
    "target_id_format_ok",
    "selected_extension_ok",
    "packaged_extension_ok",
    "model_present",
    "model_nonempty",
    "viewer_present",
    "projection_present",
    "top5_manifest_present",
    "blockers",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "claim_boundary",
    "rule_id",
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
        return int(float(str(value).strip()))
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


def _present(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


def _size(path_like: str) -> int:
    if not _present(path_like):
        return 0
    try:
        return _resolve(path_like).stat().st_size
    except OSError:
        return 0


def _extension(path_like: str) -> str:
    return Path(path_like).suffix.lower()


def _preflight_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['preflight_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_preflight_row(rank: int, source: dict[str, Any]) -> dict[str, Any]:
    target_id = _text(source.get("target_id")).upper()
    selected_filename = _text(source.get("selected_model_filename"))
    model_path = _text(source.get("model_path"))
    viewer_html = _text(source.get("viewer_html"))
    projection_svg = _text(source.get("projection_svg"))
    top5_manifest = _text(source.get("top5_manifest_csv"))
    selected_ext = _extension(selected_filename)
    packaged_ext = _extension(model_path)
    target_ok = bool(TARGET_ID_RE.match(target_id))
    selected_ext_ok = selected_ext in ALLOWED_SELECTED_EXTENSIONS
    packaged_ext_ok = packaged_ext in ALLOWED_MODEL_PATH_EXTENSIONS
    model_present = _present(model_path)
    model_size = _size(model_path)
    blockers = []
    if not selected_filename:
        blockers.append("selected_model_filename_missing")
    if not target_ok:
        blockers.append("target_id_format_invalid")
    if not selected_ext_ok:
        blockers.append("selected_model_extension_unsupported")
    if not packaged_ext_ok:
        blockers.append("packaged_model_extension_unsupported")
    if not model_present:
        blockers.append("model_file_missing")
    if model_present and model_size <= 0:
        blockers.append("model_file_empty")
    if not _present(viewer_html):
        blockers.append("viewer_html_missing")
    if not _present(projection_svg):
        blockers.append("projection_svg_missing")
    if not _present(top5_manifest):
        blockers.append("top5_manifest_missing")
    return {
        "preflight_rank": rank,
        "preflight_status": "freeze_candidate_format_preflight_ready_external_only"
        if not blockers
        else "freeze_candidate_format_preflight_blocked",
        "target_group": _text(source.get("target_group")),
        "target_id": target_id,
        "decision_rank": _int(source.get("decision_rank")),
        "decision_class": _text(source.get("decision_class")),
        "final_selector_decision": _text(source.get("final_selector_decision")),
        "selected_model_filename": selected_filename,
        "selected_model_extension": selected_ext,
        "packaged_model_extension": packaged_ext,
        "model_path": _artifact(model_path),
        "model_size_bytes": model_size,
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "top5_manifest_csv": _artifact(top5_manifest),
        "source_decision_md": _artifact(source.get("decision_md", "")),
        "preflight_md": "",
        "target_id_format_ok": str(target_ok),
        "selected_extension_ok": str(selected_ext_ok),
        "packaged_extension_ok": str(packaged_ext_ok),
        "model_present": str(model_present),
        "model_nonempty": str(model_size > 0),
        "viewer_present": str(_present(viewer_html)),
        "projection_present": str(_present(projection_svg)),
        "top5_manifest_present": str(_present(top5_manifest)),
        "blockers": ",".join(blockers),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }


def _write_target_preflight(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Freeze-Candidate Format Preflight",
        "",
        f"- status: `{row['preflight_status']}`",
        f"- decision class: `{row['decision_class']}`",
        f"- final selector decision: `{row['final_selector_decision']}`",
        f"- selected model: `{row['selected_model_filename']}`",
        f"- selected/packaged extension: `{row['selected_model_extension']}/{row['packaged_model_extension']}`",
        f"- model path: `{row['model_path']}`",
        f"- model size bytes: `{row['model_size_bytes']}`",
        f"- viewer: `{row['viewer_html'] or '-'}`",
        f"- projection: `{row['projection_svg'] or '-'}`",
        f"- top5 manifest: `{row['top5_manifest_csv'] or '-'}`",
        f"- source decision: `{row['source_decision_md'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Preflight Scope",
        "",
        "This packet only verifies local external-only readiness for later rule-checked formatting.",
        "It does not create a CASP submission file and does not approve submission.",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    decision_payload = _read_json(args.post_probe_selector_decision_json)
    decision_summary = _summary(decision_payload)
    freeze_rows = [
        row for row in _rows(decision_payload) if _text(row.get("decision_class")) in FREEZE_CLASSES
    ]
    freeze_rows.sort(key=lambda row: (_int(row.get("decision_rank")), _text(row.get("target_id"))))
    rows: list[dict[str, Any]] = []
    for rank, source in enumerate(freeze_rows, start=1):
        row = _build_preflight_row(rank, source)
        preflight_md = _resolve(args.out_dir) / _preflight_dir_name(row) / "FORMAT_PREFLIGHT.md"
        row["preflight_md"] = _artifact(preflight_md)
        _write_target_preflight(preflight_md, row)
        rows.append(row)

    ready_rows = [
        row for row in rows if row["preflight_status"] == "freeze_candidate_format_preflight_ready_external_only"
    ]
    blocked_rows = [
        row for row in rows if row["preflight_status"] != "freeze_candidate_format_preflight_ready_external_only"
    ]
    first = rows[0] if rows else {}
    status = (
        "massivefold_freeze_candidate_format_preflight_ready_external_only"
        if rows and not blocked_rows
        else "massivefold_freeze_candidate_format_preflight_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_freeze_candidate_format_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_freeze_candidate_format_preflight_status": status,
        "post_probe_selector_decision_json": _artifact(args.post_probe_selector_decision_json),
        "post_probe_selector_decision_status": _text(
            decision_summary.get("massivefold_post_probe_selector_decision_packet_status")
        ),
        "freeze_candidate_count": len(rows),
        "ready_preflight_count": len(ready_rows),
        "blocked_preflight_count": len(blocked_rows),
        "existing_freeze_candidate_count": sum(1 for row in rows if row["decision_class"] == "freeze_candidate_existing"),
        "probe_freeze_candidate_count": sum(1 for row in rows if row["decision_class"] == "freeze_candidate_after_probe"),
        "rna_hybrid_preflight_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_preflight_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "selected_pdb_count": sum(1 for row in rows if row["selected_model_extension"] == ".pdb"),
        "selected_cif_count": sum(1 for row in rows if row["selected_model_extension"] == ".cif"),
        "packaged_pdb_count": sum(1 for row in rows if row["packaged_model_extension"] == ".pdb"),
        "packaged_cif_count": sum(1 for row in rows if row["packaged_model_extension"] == ".cif"),
        "target_id_format_ok_count": sum(1 for row in rows if row["target_id_format_ok"] == "True"),
        "selected_extension_ok_count": sum(1 for row in rows if row["selected_extension_ok"] == "True"),
        "packaged_extension_ok_count": sum(1 for row in rows if row["packaged_extension_ok"] == "True"),
        "model_present_count": sum(1 for row in rows if row["model_present"] == "True"),
        "model_nonempty_count": sum(1 for row in rows if row["model_nonempty"] == "True"),
        "viewer_present_count": sum(1 for row in rows if row["viewer_present"] == "True"),
        "projection_present_count": sum(1 for row in rows if row["projection_present"] == "True"),
        "top5_manifest_present_count": sum(1 for row in rows if row["top5_manifest_present"] == "True"),
        "first_preflight_target_id": _text(first.get("target_id")),
        "first_preflight_model_filename": _text(first.get("selected_model_filename")),
        "first_preflight_model_path": _text(first.get("model_path")),
        "preflight_dir": _artifact(args.out_dir),
        "preflight_csv": _artifact(args.out_csv),
        "preflight_html": _artifact(args.out_html),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": "run official CASP rule checks only after operator resolves watch/manual actions and approves formatting",
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Freeze-Candidate Format Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_freeze_candidate_format_preflight_status']}`",
        f"- preflight ready/blocked/total: `{summary['ready_preflight_count']}/{summary['blocked_preflight_count']}/{summary['freeze_candidate_count']}`",
        f"- freeze existing/probe: `{summary['existing_freeze_candidate_count']}/{summary['probe_freeze_candidate_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_preflight_count']}/{summary['protein_complex_preflight_count']}`",
        f"- selected pdb/cif: `{summary['selected_pdb_count']}/{summary['selected_cif_count']}`",
        f"- packaged pdb/cif: `{summary['packaged_pdb_count']}/{summary['packaged_cif_count']}`",
        f"- target/ext/model/viewer/projection/top5: `{summary['target_id_format_ok_count']}/{summary['selected_extension_ok_count']}/{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top5_manifest_present_count']}`",
        f"- first preflight: `{summary['first_preflight_target_id'] or '-'}` `{summary['first_preflight_model_filename'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Freeze Candidates",
        "",
        "| rank | target | class | selected model | ext | bytes | viewer | preflight | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['preflight_rank']}` | `{row['target_id']}` | `{row['decision_class']}` | "
            f"`{row['selected_model_filename']}` | `{row['selected_model_extension']}` | "
            f"`{row['model_size_bytes']}` | `{row['viewer_html'] or '-'}` | "
            f"`{row['preflight_md']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    cards = []
    for row in payload["rows"]:
        viewer = html.escape(row["viewer_html"])
        preflight = html.escape(row["preflight_md"])
        cards.append(
            "<section>"
            f"<h2>{html.escape(row['target_id'])} <span>{html.escape(row['decision_class'])}</span></h2>"
            f"<p><strong>{html.escape(row['selected_model_filename'])}</strong></p>"
            f"<p>ext {html.escape(row['selected_model_extension'])}/{html.escape(row['packaged_model_extension'])} "
            f"bytes {html.escape(str(row['model_size_bytes']))}</p>"
            f"<p><a href=\"{viewer}\">viewer</a> <a href=\"{preflight}\">preflight</a></p>"
            f"<p>{html.escape(row['blockers'] or 'ready external-only format preflight')}</p>"
            "</section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Format Preflight</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "section{border:1px solid #bbb;border-radius:6px;padding:14px;margin:12px 0}"
        "span{font-size:13px;font-weight:400;color:#555}a{margin-right:12px}</style></head><body>"
        "<h1>CASP17 MassiveFold Freeze-Candidate Format Preflight</h1>"
        f"<p>Status: {html.escape(summary['massivefold_freeze_candidate_format_preflight_status'])}</p>"
        f"<p>Ready/blocked/total: {summary['ready_preflight_count']}/{summary['blocked_preflight_count']}/{summary['freeze_candidate_count']}</p>"
        + "".join(cards)
        + f"<h2>Claim Boundary</h2><p>{html.escape(CLAIM_BOUNDARY)}</p>"
        "</body></html>"
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _resolve(args.out_dir).mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)
    _write_json(_resolve(args.out_dir) / "freeze_candidate_format_preflight.json", payload)
    _write_csv(_resolve(args.out_dir) / "freeze_candidate_format_preflight.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build external-only format preflight rows for MassiveFold freeze candidates.")
    parser.add_argument("--post-probe-selector-decision-json", default=DEFAULT_POST_PROBE_SELECTOR_DECISION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["massivefold_freeze_candidate_format_preflight_status"],
                "ready": payload["summary"]["ready_preflight_count"],
                "blocked": payload["summary"]["blocked_preflight_count"],
                "total": payload["summary"]["freeze_candidate_count"],
                "existing": payload["summary"]["existing_freeze_candidate_count"],
                "probe": payload["summary"]["probe_freeze_candidate_count"],
                "first": payload["summary"]["first_preflight_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
