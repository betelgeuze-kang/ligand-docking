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

DEFAULT_SELECTOR_OVERLAY_JSON = "casp17/casp17_massivefold_model1_combined_selector_overlay_current.json"
DEFAULT_MODEL_SELECTION_LEDGER_JSON = "casp17/casp17_massivefold_model_selection_ledger_current.json"
DEFAULT_RERANK_JSON_PATTERN = "casp17/casp17_massivefold_representative_rerank_packet_{target_lower}_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_freeze_ready_review_packet"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_freeze_ready_review_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_freeze_ready_review_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_FREEZE_READY_REVIEW_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_freeze_ready_review_packet_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold freeze-ready review packet only. It links external MassiveFold model1/top5 "
    "review artifacts selected by the baseline-calibrated no-native selector. It is not native accuracy, "
    "not internal prediction proof, not a CASP submission, and not permission to submit without operator approval."
)
EXTERNAL_ONLY_POLICY = "external_no_native_freeze_ready_review_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "baseline_calibrated_freeze_ready_review_packet_v1"

ROW_COLUMNS = [
    "review_rank",
    "review_status",
    "target_group",
    "target_id",
    "overlay_decision",
    "overlay_action",
    "selected_model_filename",
    "model_path",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "top5_candidate_count",
    "confidence_score",
    "probe_margin",
    "baseline_capture_rate",
    "model_present",
    "viewer_present",
    "projection_present",
    "top5_manifest_present",
    "review_md",
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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _present(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


def _target_rerank_path(pattern: str, target_id: str) -> str:
    return pattern.format(target=target_id, target_lower=target_id.lower(), target_upper=target_id.upper())


def _top5_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if _text(row.get("top5_candidate")).lower() == "true")


def _find_selected_rerank_row(rows: list[dict[str, Any]], selected_filename: str) -> dict[str, Any]:
    selected = _text(selected_filename)
    for row in rows:
        if _text(row.get("filename")) == selected:
            return row
    for row in rows:
        if _text(row.get("model1_candidate")).lower() == "true":
            return row
    return {}


def _review_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['review_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _write_target_review(path: Path, row: dict[str, Any], top5_rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {row['target_id']} MassiveFold freeze-ready review",
        "",
        f"- review status: `{row['review_status']}`",
        f"- selected model: `{row['selected_model_filename']}`",
        f"- viewer: `{row['viewer_html'] or '-'}`",
        f"- projection: `{row['projection_svg'] or '-'}`",
        f"- top5 manifest: `{row['top5_manifest_csv'] or '-'}`",
        f"- probe margin: `{row['probe_margin'] or '-'}`",
        f"- baseline capture rate: `{row['baseline_capture_rate'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Top5 Review Links",
        "",
        "| rank | filename | score | viewer | projection |",
        "| --- | --- | --- | --- | --- |",
    ]
    for top5 in top5_rows:
        lines.append(
            f"| `{_text(top5.get('top5_selection_rank')) or _text(top5.get('quality_rank'))}` | "
            f"`{_text(top5.get('filename'))}` | `{_text(top5.get('confidence_score')) or '-'}` | "
            f"`{_text(top5.get('viewer_html_path')) or '-'}` | `{_text(top5.get('projection_svg_path')) or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    overlay_payload = _read_json(args.selector_overlay_json)
    ledger_payload = _read_json(args.model_selection_ledger_json)
    overlay_summary = _summary(overlay_payload)
    ledger_summary = _summary(ledger_payload)
    ledger_by_target = _by_target(_rows(ledger_payload))
    out_dir = _resolve(args.out_dir)

    rows: list[dict[str, Any]] = []
    selected_overlay_rows = [
        row
        for row in _rows(overlay_payload)
        if _text(row.get("overlay_decision")) == "baseline_calibrated_freeze_ready"
    ]
    selected_overlay_rows.sort(key=lambda row: (_text(row.get("target_group")), _text(row.get("target_id"))))

    for rank, overlay_row in enumerate(selected_overlay_rows, start=1):
        target_id = _text(overlay_row.get("target_id")).upper()
        ledger_row = ledger_by_target.get(target_id, {})
        selected_filename = _text(overlay_row.get("selected_model_filename")) or _text(
            ledger_row.get("selected_model_filename")
        )
        rerank_path = _target_rerank_path(args.rerank_json_pattern, target_id)
        rerank_payload = _read_json(rerank_path)
        rerank_summary = _summary(rerank_payload)
        rerank_rows = _rows(rerank_payload)
        selected_rerank = _find_selected_rerank_row(rerank_rows, selected_filename)
        top5_rows = [
            row for row in rerank_rows if _text(row.get("top5_candidate")).lower() == "true"
        ]
        top5_rows.sort(key=lambda row: int(_text(row.get("top5_selection_rank")) or "999"))

        model_path = _text(selected_rerank.get("model_cif_path")) or _text(rerank_summary.get("model1_cif_path"))
        viewer_html = _text(selected_rerank.get("viewer_html_path")) or _text(rerank_summary.get("model1_viewer_html"))
        projection_svg = _text(selected_rerank.get("projection_svg_path"))
        top5_manifest = _text(rerank_summary.get("top5_manifest_csv")) or _text(ledger_row.get("source_candidate_manifest_csv"))
        blockers = []
        if not selected_rerank:
            blockers.append("selected_model_missing_from_rerank_rows")
        if not _present(model_path):
            blockers.append("model_file_missing")
        if not _present(viewer_html):
            blockers.append("viewer_html_missing")
        if not _present(projection_svg):
            blockers.append("projection_svg_missing")
        if not _present(top5_manifest):
            blockers.append("top5_manifest_missing")
        if _top5_count(rerank_rows) < 5:
            blockers.append("top5_candidate_count_below_5")

        row = {
            "review_rank": rank,
            "review_status": "freeze_ready_review_ready_external_only" if not blockers else "freeze_ready_review_blocked",
            "target_group": _text(overlay_row.get("target_group")),
            "target_id": target_id,
            "overlay_decision": _text(overlay_row.get("overlay_decision")),
            "overlay_action": _text(overlay_row.get("overlay_action")),
            "selected_model_filename": selected_filename,
            "model_path": _artifact(model_path),
            "viewer_html": _artifact(viewer_html),
            "projection_svg": _artifact(projection_svg),
            "top5_manifest_csv": _artifact(top5_manifest),
            "top5_candidate_count": _top5_count(rerank_rows),
            "confidence_score": _text(selected_rerank.get("confidence_score"))
            or _text(rerank_summary.get("model1_confidence_score")),
            "probe_margin": _text(overlay_row.get("probe_margin")),
            "baseline_capture_rate": _text(overlay_row.get("baseline_capture_rate")),
            "model_present": str(_present(model_path)),
            "viewer_present": str(_present(viewer_html)),
            "projection_present": str(_present(projection_svg)),
            "top5_manifest_present": str(_present(top5_manifest)),
            "review_md": "",
            "blockers": ",".join(blockers),
            "external_only_policy": EXTERNAL_ONLY_POLICY,
            "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
            "submission_policy": SUBMISSION_POLICY,
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
        }
        review = out_dir / _review_dir_name(row) / "FREEZE_READY_REVIEW.md"
        row["review_md"] = _artifact(review)
        _write_target_review(review, row, top5_rows)
        rows.append(row)

    ready_rows = [row for row in rows if row["review_status"] == "freeze_ready_review_ready_external_only"]
    blocked_rows = [row for row in rows if row["review_status"] != "freeze_ready_review_ready_external_only"]
    first = rows[0] if rows else {}
    status = (
        "massivefold_freeze_ready_review_packet_ready_external_only"
        if rows and not blocked_rows
        else "massivefold_freeze_ready_review_packet_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_freeze_ready_review_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_freeze_ready_review_packet_status": status,
        "selector_overlay_json": _artifact(args.selector_overlay_json),
        "selector_overlay_status": _text(
            overlay_summary.get("massivefold_model1_combined_selector_overlay_status")
        ),
        "model_selection_ledger_json": _artifact(args.model_selection_ledger_json),
        "model_selection_ledger_status": _text(ledger_summary.get("massivefold_model_selection_ledger_status")),
        "freeze_ready_target_count": len(rows),
        "ready_review_count": len(ready_rows),
        "blocked_review_count": len(blocked_rows),
        "model_present_count": sum(1 for row in rows if row["model_present"] == "True"),
        "viewer_present_count": sum(1 for row in rows if row["viewer_present"] == "True"),
        "projection_present_count": sum(1 for row in rows if row["projection_present"] == "True"),
        "top5_manifest_present_count": sum(1 for row in rows if row["top5_manifest_present"] == "True"),
        "top5_candidate_total": sum(int(row["top5_candidate_count"]) for row in rows),
        "first_review_target_id": _text(first.get("target_id")),
        "first_review_model_filename": _text(first.get("selected_model_filename")),
        "first_review_viewer_html": _text(first.get("viewer_html")),
        "first_review_md": _text(first.get("review_md")),
        "review_dir": _artifact(args.out_dir),
        "review_csv": _artifact(args.out_csv),
        "review_html": _artifact(args.out_html),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": (
            "operator visually inspects freeze-ready model1/top5 viewers before any CASP rule-checked formatting"
            if status == "massivefold_freeze_ready_review_packet_ready_external_only"
            else "repair missing freeze-ready viewer/model/projection artifacts before review"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Freeze-Ready Review Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_freeze_ready_review_packet_status']}`",
        f"- reviews ready/blocked/total: `{summary['ready_review_count']}/{summary['blocked_review_count']}/{summary['freeze_ready_target_count']}`",
        f"- model/viewer/projection/top5 present: `{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top5_manifest_present_count']}`",
        f"- top5 candidate total: `{summary['top5_candidate_total']}`",
        f"- first review: `{summary['first_review_target_id'] or '-'}` `{summary['first_review_model_filename'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Review Targets",
        "",
        "| rank | target | group | model | score | margin | viewer | review | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['selected_model_filename']}` | `{row['confidence_score'] or '-'}` | "
            f"`{row['probe_margin'] or '-'}` | `{row['viewer_html'] or '-'}` | "
            f"`{row['review_md']}` | `{row['blockers'] or '-'}` |"
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
        review = html.escape(row["review_md"])
        projection = html.escape(row["projection_svg"])
        cards.append(
            "<section>"
            f"<h2>{html.escape(row['target_id'])}</h2>"
            f"<p><strong>{html.escape(row['selected_model_filename'])}</strong></p>"
            f"<p>score {html.escape(row['confidence_score'] or '-')} margin {html.escape(row['probe_margin'] or '-')}</p>"
            f"<p><a href=\"{viewer}\">viewer</a> <a href=\"{projection}\">projection</a> <a href=\"{review}\">review</a></p>"
            f"<p>{html.escape(row['blockers'] or 'ready external-only review')}</p>"
            "</section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Freeze-Ready Review</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "section{border:1px solid #bbb;border-radius:6px;padding:14px;margin:12px 0}"
        "a{margin-right:12px}</style></head><body>"
        "<h1>CASP17 MassiveFold Freeze-Ready Review</h1>"
        f"<p>Status: {html.escape(summary['massivefold_freeze_ready_review_packet_status'])}</p>"
        f"<p>Ready/blocked/total: {summary['ready_review_count']}/{summary['blocked_review_count']}/{summary['freeze_ready_target_count']}</p>"
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
    _write_json(_resolve(args.out_dir) / "freeze_ready_review_packet.json", payload)
    _write_csv(_resolve(args.out_dir) / "freeze_ready_review_packet.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a MassiveFold freeze-ready external review packet.")
    parser.add_argument("--selector-overlay-json", default=DEFAULT_SELECTOR_OVERLAY_JSON)
    parser.add_argument("--model-selection-ledger-json", default=DEFAULT_MODEL_SELECTION_LEDGER_JSON)
    parser.add_argument("--rerank-json-pattern", default=DEFAULT_RERANK_JSON_PATTERN)
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
                "status": payload["summary"]["massivefold_freeze_ready_review_packet_status"],
                "ready": payload["summary"]["ready_review_count"],
                "blocked": payload["summary"]["blocked_review_count"],
                "total": payload["summary"]["freeze_ready_target_count"],
                "first": payload["summary"]["first_review_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
