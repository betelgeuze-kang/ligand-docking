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

DEFAULT_HOLD_PROBE_REVIEW_JSON = "casp17/casp17_massivefold_hold_probe_review_packet_current.json"
DEFAULT_RERANK_JSON_PATTERN = "casp17/casp17_massivefold_representative_rerank_packet_{target_lower}_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_probe_required_targeted_probe_packet"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_PROBE_REQUIRED_TARGETED_PROBE_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold "
    "top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. "
    "It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission "
    "to submit without operator approval."
)
EXTERNAL_ONLY_POLICY = "external_no_native_probe_required_targeted_probe_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
SCORING_RULE_ID = "probe_required_targeted_no_native_rescore_v1"
CLEAR_MARGIN = 0.5

ROW_COLUMNS = [
    "probe_rank",
    "probe_status",
    "target_group",
    "target_id",
    "review_rank",
    "review_class",
    "probe_type",
    "primary_model_filename",
    "model1_probe_score",
    "top_candidate_filename",
    "top_candidate_role",
    "top_candidate_probe_score",
    "probe_margin",
    "probe_result",
    "probe_recommendation",
    "confidence_score",
    "confidence_gap",
    "risk_score",
    "geometry_outlier_score",
    "low_conf_atom_fraction",
    "diversity_to_model1_rmsd",
    "top5_candidate_count",
    "model_path",
    "viewer_html",
    "projection_svg",
    "top_candidate_model_path",
    "top_candidate_viewer_html",
    "top_candidate_projection_svg",
    "top5_manifest_csv",
    "model_present",
    "viewer_present",
    "projection_present",
    "top_candidate_present",
    "top_candidate_viewer_present",
    "top5_manifest_present",
    "probe_md",
    "blockers",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "claim_boundary",
    "scoring_rule_id",
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


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _float_out(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


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


def _target_rerank_path(pattern: str, target_id: str) -> str:
    return pattern.format(target=target_id, target_lower=target_id.lower(), target_upper=target_id.upper())


def _top5_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if _text(row.get("top5_candidate")).lower() == "true"]
    selected.sort(key=lambda row: _int(row.get("top5_selection_rank")) or 999)
    return selected


def _find_model_row(rows: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    wanted = _text(filename)
    for row in rows:
        if wanted and _text(row.get("filename")) == wanted:
            return row
    for row in rows:
        if _text(row.get("model1_candidate")).lower() == "true":
            return row
    return {}


def _probe_score(candidate: dict[str, Any]) -> float:
    confidence = _float(candidate.get("confidence_score"))
    geometry = _float(candidate.get("geometry_outlier_score"))
    low_conf = _float(candidate.get("low_conf_atom_fraction"))
    diversity = _float(candidate.get("diversity_to_model1_rmsd"))
    return confidence - (0.25 * geometry) - (2.0 * low_conf) - (0.01 * diversity)


def _score_top5(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for row in _top5_rows(rows):
        scored.append({"row": row, "score": _probe_score(row)})
    scored.sort(key=lambda item: (-item["score"], _int(item["row"].get("top5_selection_rank")) or 999))
    return scored


def _is_model1(row: dict[str, Any]) -> bool:
    return _text(row.get("model1_candidate")).lower() == "true"


def _result_and_recommendation(top_is_model1: bool, margin: float) -> tuple[str, str]:
    if not top_is_model1:
        return "probe_fail_model1_displaced", "external_model1_freeze_blocked_manual_review"
    if margin < CLEAR_MARGIN:
        return "probe_watch_model1_retained_low_margin", "external_model1_watch_low_margin_after_probe"
    return "probe_pass_model1_retained_clear", "external_model1_freeze_candidate_after_probe"


def _probe_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['probe_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _write_target_probe(path: Path, row: dict[str, Any], scored_top5: list[dict[str, Any]]) -> None:
    lines = [
        f"# {row['target_id']} Probe-Required Targeted Probe",
        "",
        f"- status: `{row['probe_status']}`",
        f"- result: `{row['probe_result']}`",
        f"- recommendation: `{row['probe_recommendation']}`",
        f"- primary model: `{row['primary_model_filename']}`",
        f"- model1/top/margin: `{row['model1_probe_score']}/{row['top_candidate_probe_score']}/{row['probe_margin']}`",
        f"- top candidate: `{row['top_candidate_filename']}` `{row['top_candidate_role']}`",
        f"- scoring rule: `{row['scoring_rule_id']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Top5 No-Native Rescore",
        "",
        "| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, item in enumerate(scored_top5, start=1):
        candidate = item["row"]
        role = "model1" if _is_model1(candidate) else "competitor"
        lines.append(
            f"| `{rank}` | `{role}` | `{_text(candidate.get('filename'))}` | "
            f"`{_float_out(item['score'])}` | `{_text(candidate.get('confidence_score')) or '-'}` | "
            f"`{_text(candidate.get('geometry_outlier_score')) or '-'}` | "
            f"`{_text(candidate.get('low_conf_atom_fraction')) or '-'}` | "
            f"`{_text(candidate.get('diversity_to_model1_rmsd')) or '-'}` | "
            f"`{_text(candidate.get('viewer_html_path')) or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    hold_payload = _read_json(args.hold_probe_review_json)
    hold_summary = _summary(hold_payload)
    probe_source_rows = [
        row for row in _rows(hold_payload) if _text(row.get("review_class")) == "probe_required_review"
    ]
    probe_source_rows.sort(key=lambda row: _int(row.get("review_rank")))

    rows: list[dict[str, Any]] = []
    scored_by_target: dict[str, list[dict[str, Any]]] = {}
    for rank, source in enumerate(probe_source_rows, start=1):
        target_id = _text(source.get("target_id")).upper()
        primary_filename = _text(source.get("primary_model_filename"))
        rerank_payload = _read_json(_target_rerank_path(args.rerank_json_pattern, target_id))
        rerank_summary = _summary(rerank_payload)
        rerank_rows = _rows(rerank_payload)
        scored_top5 = _score_top5(rerank_rows)
        scored_by_target[target_id] = scored_top5
        primary_rerank = _find_model_row(rerank_rows, primary_filename)
        model1_item = next((item for item in scored_top5 if _is_model1(item["row"])), None)
        top_item = scored_top5[0] if scored_top5 else None
        competitor_item = next((item for item in scored_top5 if not _is_model1(item["row"])), None)
        model1_score = model1_item["score"] if model1_item else 0.0
        competitor_score = competitor_item["score"] if competitor_item else 0.0
        top_score = top_item["score"] if top_item else 0.0
        margin = model1_score - competitor_score if model1_item and competitor_item else 0.0
        top_row = top_item["row"] if top_item else {}
        top_is_model1 = bool(top_row) and _is_model1(top_row)
        probe_result, probe_recommendation = _result_and_recommendation(top_is_model1, margin)

        model_path = _text(primary_rerank.get("model_cif_path")) or _text(rerank_summary.get("model1_cif_path"))
        viewer_html = _text(primary_rerank.get("viewer_html_path")) or _text(rerank_summary.get("model1_viewer_html"))
        projection_svg = _text(primary_rerank.get("projection_svg_path"))
        top_model_path = _text(top_row.get("model_cif_path"))
        top_viewer_html = _text(top_row.get("viewer_html_path"))
        top_projection_svg = _text(top_row.get("projection_svg_path"))
        top5_manifest = _text(source.get("top5_manifest_csv")) or _text(rerank_summary.get("top5_manifest_csv"))

        blockers = []
        if not primary_rerank:
            blockers.append("primary_model_missing_from_rerank_rows")
        if not model1_item:
            blockers.append("model1_missing_from_top5_rows")
        if not top_item:
            blockers.append("top5_rows_missing")
        if len(scored_top5) < 5:
            blockers.append("top5_candidate_count_below_5")
        if not _present(model_path):
            blockers.append("model_file_missing")
        if not _present(viewer_html):
            blockers.append("viewer_html_missing")
        if not _present(projection_svg):
            blockers.append("projection_svg_missing")
        if not _present(top_model_path):
            blockers.append("top_candidate_model_file_missing")
        if not _present(top_viewer_html):
            blockers.append("top_candidate_viewer_html_missing")
        if not _present(top5_manifest):
            blockers.append("top5_manifest_missing")

        row = {
            "probe_rank": rank,
            "probe_status": "targeted_probe_ready_external_only" if not blockers else "targeted_probe_blocked",
            "target_group": _text(source.get("target_group")),
            "target_id": target_id,
            "review_rank": _int(source.get("review_rank")),
            "review_class": _text(source.get("review_class")),
            "probe_type": "top5_targeted_no_native_rescore",
            "primary_model_filename": primary_filename,
            "model1_probe_score": _float_out(model1_score),
            "top_candidate_filename": _text(top_row.get("filename")),
            "top_candidate_role": "model1" if top_is_model1 else "competitor",
            "top_candidate_probe_score": _float_out(top_score),
            "probe_margin": _float_out(margin),
            "probe_result": probe_result,
            "probe_recommendation": probe_recommendation,
            "confidence_score": _text(primary_rerank.get("confidence_score")) or _text(source.get("confidence_score")),
            "confidence_gap": _text(source.get("confidence_gap")),
            "risk_score": _text(source.get("risk_score")),
            "geometry_outlier_score": _text(primary_rerank.get("geometry_outlier_score")),
            "low_conf_atom_fraction": _text(primary_rerank.get("low_conf_atom_fraction")),
            "diversity_to_model1_rmsd": _text(primary_rerank.get("diversity_to_model1_rmsd")),
            "top5_candidate_count": len(scored_top5),
            "model_path": _artifact(model_path),
            "viewer_html": _artifact(viewer_html),
            "projection_svg": _artifact(projection_svg),
            "top_candidate_model_path": _artifact(top_model_path),
            "top_candidate_viewer_html": _artifact(top_viewer_html),
            "top_candidate_projection_svg": _artifact(top_projection_svg),
            "top5_manifest_csv": _artifact(top5_manifest),
            "model_present": str(_present(model_path)),
            "viewer_present": str(_present(viewer_html)),
            "projection_present": str(_present(projection_svg)),
            "top_candidate_present": str(_present(top_model_path)),
            "top_candidate_viewer_present": str(_present(top_viewer_html)),
            "top5_manifest_present": str(_present(top5_manifest)),
            "probe_md": "",
            "blockers": ",".join(blockers),
            "external_only_policy": EXTERNAL_ONLY_POLICY,
            "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
            "submission_policy": SUBMISSION_POLICY,
            "claim_boundary": CLAIM_BOUNDARY,
            "scoring_rule_id": SCORING_RULE_ID,
        }
        probe_md = _resolve(args.out_dir) / _probe_dir_name(row) / "TARGETED_PROBE.md"
        row["probe_md"] = _artifact(probe_md)
        _write_target_probe(probe_md, row, scored_top5)
        rows.append(row)

    ready_rows = [row for row in rows if row["probe_status"] == "targeted_probe_ready_external_only"]
    blocked_rows = [row for row in rows if row["probe_status"] != "targeted_probe_ready_external_only"]
    pass_rows = [row for row in rows if row["probe_result"] == "probe_pass_model1_retained_clear"]
    watch_rows = [row for row in rows if row["probe_result"] == "probe_watch_model1_retained_low_margin"]
    fail_rows = [row for row in rows if row["probe_result"] == "probe_fail_model1_displaced"]
    first = rows[0] if rows else {}
    status = (
        "massivefold_probe_required_targeted_probe_packet_ready_external_only"
        if rows and not blocked_rows
        else "massivefold_probe_required_targeted_probe_packet_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_probe_required_targeted_probe_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_probe_required_targeted_probe_packet_status": status,
        "hold_probe_review_json": _artifact(args.hold_probe_review_json),
        "hold_probe_review_status": _text(hold_summary.get("massivefold_hold_probe_review_packet_status")),
        "probe_target_count": len(rows),
        "ready_probe_count": len(ready_rows),
        "blocked_probe_count": len(blocked_rows),
        "probe_pass_count": len(pass_rows),
        "probe_watch_count": len(watch_rows),
        "probe_fail_count": len(fail_rows),
        "freeze_candidate_count": len(pass_rows),
        "watch_recommendation_count": len(watch_rows),
        "manual_review_recommendation_count": len(fail_rows),
        "rna_hybrid_probe_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_probe_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "model_present_count": sum(1 for row in rows if row["model_present"] == "True"),
        "viewer_present_count": sum(1 for row in rows if row["viewer_present"] == "True"),
        "projection_present_count": sum(1 for row in rows if row["projection_present"] == "True"),
        "top_candidate_present_count": sum(1 for row in rows if row["top_candidate_present"] == "True"),
        "top_candidate_viewer_present_count": sum(1 for row in rows if row["top_candidate_viewer_present"] == "True"),
        "top5_manifest_present_count": sum(1 for row in rows if row["top5_manifest_present"] == "True"),
        "top5_candidate_total": sum(int(row["top5_candidate_count"]) for row in rows),
        "clear_margin_threshold": _float_out(CLEAR_MARGIN),
        "first_probe_target_id": _text(first.get("target_id")),
        "first_probe_result": _text(first.get("probe_result")),
        "first_probe_margin": _text(first.get("probe_margin")),
        "first_probe_recommendation": _text(first.get("probe_recommendation")),
        "first_probe_model_filename": _text(first.get("primary_model_filename")),
        "probe_dir": _artifact(args.out_dir),
        "probe_csv": _artifact(args.out_csv),
        "probe_html": _artifact(args.out_html),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": (
            "feed clear/watch/fail probe recommendations into the external-only selector overlay review"
            if status == "massivefold_probe_required_targeted_probe_packet_ready_external_only"
            else "repair missing probe-required model/viewer/top5 artifacts before using probe recommendations"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "scoring_rule_id": SCORING_RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Probe-Required Targeted Probe Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_probe_required_targeted_probe_packet_status']}`",
        f"- probes ready/blocked/total: `{summary['ready_probe_count']}/{summary['blocked_probe_count']}/{summary['probe_target_count']}`",
        f"- pass/watch/fail: `{summary['probe_pass_count']}/{summary['probe_watch_count']}/{summary['probe_fail_count']}`",
        f"- recommendations freeze/watch/manual: `{summary['freeze_candidate_count']}/{summary['watch_recommendation_count']}/{summary['manual_review_recommendation_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_probe_count']}/{summary['protein_complex_probe_count']}`",
        f"- model/viewer/projection/top/top-viewer/top5: `{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top_candidate_present_count']}/{summary['top_candidate_viewer_present_count']}/{summary['top5_manifest_present_count']}`",
        f"- top5 candidate total: `{summary['top5_candidate_total']}` clear margin `{summary['clear_margin_threshold']}`",
        f"- first probe: `{summary['first_probe_target_id'] or '-'}` `{summary['first_probe_result'] or '-'}` margin `{summary['first_probe_margin'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Probe Targets",
        "",
        "| rank | target | group | result | recommendation | model | top | margin | viewer | probe | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['probe_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['probe_result']}` | `{row['probe_recommendation']}` | "
            f"`{row['primary_model_filename']}` | `{row['top_candidate_filename']}` | "
            f"`{row['probe_margin']}` | `{row['viewer_html'] or '-'}` | "
            f"`{row['probe_md']}` | `{row['blockers'] or '-'}` |"
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
        top_viewer = html.escape(row["top_candidate_viewer_html"])
        probe = html.escape(row["probe_md"])
        cards.append(
            "<section>"
            f"<h2>{html.escape(row['target_id'])} <span>{html.escape(row['probe_result'])}</span></h2>"
            f"<p><strong>{html.escape(row['primary_model_filename'])}</strong></p>"
            f"<p>recommendation {html.escape(row['probe_recommendation'])}</p>"
            f"<p>model1 {html.escape(row['model1_probe_score'])} top {html.escape(row['top_candidate_probe_score'])} "
            f"margin {html.escape(row['probe_margin'])}</p>"
            f"<p><a href=\"{viewer}\">model1 viewer</a> <a href=\"{top_viewer}\">top viewer</a> "
            f"<a href=\"{probe}\">probe</a></p>"
            f"<p>{html.escape(row['blockers'] or 'ready external-only targeted probe')}</p>"
            "</section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Targeted Probes</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "section{border:1px solid #bbb;border-radius:6px;padding:14px;margin:12px 0}"
        "span{font-size:13px;font-weight:400;color:#555}a{margin-right:12px}</style></head><body>"
        "<h1>CASP17 MassiveFold Probe-Required Targeted Probes</h1>"
        f"<p>Status: {html.escape(summary['massivefold_probe_required_targeted_probe_packet_status'])}</p>"
        f"<p>Ready/blocked/total: {summary['ready_probe_count']}/{summary['blocked_probe_count']}/{summary['probe_target_count']}</p>"
        f"<p>Pass/watch/fail: {summary['probe_pass_count']}/{summary['probe_watch_count']}/{summary['probe_fail_count']}</p>"
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
    _write_json(_resolve(args.out_dir) / "probe_required_targeted_probe_packet.json", payload)
    _write_csv(_resolve(args.out_dir) / "probe_required_targeted_probe_packet.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-native targeted probes for MassiveFold probe-required rows.")
    parser.add_argument("--hold-probe-review-json", default=DEFAULT_HOLD_PROBE_REVIEW_JSON)
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
                "status": payload["summary"]["massivefold_probe_required_targeted_probe_packet_status"],
                "ready": payload["summary"]["ready_probe_count"],
                "blocked": payload["summary"]["blocked_probe_count"],
                "total": payload["summary"]["probe_target_count"],
                "pass": payload["summary"]["probe_pass_count"],
                "watch": payload["summary"]["probe_watch_count"],
                "fail": payload["summary"]["probe_fail_count"],
                "first": payload["summary"]["first_probe_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
