#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SELECTOR_OVERLAY_JSON = "casp17/casp17_massivefold_model1_combined_selector_overlay_current.json"
DEFAULT_FREEZE_READY_REVIEW_JSON = "casp17/casp17_massivefold_freeze_ready_review_packet_current.json"
DEFAULT_HOLD_PROBE_REVIEW_JSON = "casp17/casp17_massivefold_hold_probe_review_packet_current.json"
DEFAULT_TARGETED_PROBE_JSON = "casp17/casp17_massivefold_probe_required_targeted_probe_packet_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_post_probe_selector_decision_packet"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_POST_PROBE_SELECTOR_DECISION_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold post-probe selector decision packet only. It combines external MassiveFold "
    "freeze-ready reviews, hold/probe reviews, and no-native targeted probes into an external model1 "
    "selection decision map. It is not native accuracy, not internal prediction proof, not a CASP "
    "submission, and not permission to submit without operator approval."
)
EXTERNAL_ONLY_POLICY = "external_no_native_post_probe_selector_decision_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "post_probe_external_selector_decision_v1"

ROW_COLUMNS = [
    "decision_rank",
    "decision_status",
    "target_group",
    "target_id",
    "overlay_rank",
    "overlay_decision",
    "source_packet",
    "decision_class",
    "final_selector_decision",
    "selected_model_filename",
    "top_candidate_filename",
    "alternate_model_filename",
    "probe_result",
    "probe_margin",
    "confidence_score",
    "confidence_gap",
    "risk_score",
    "model_path",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "source_review_md",
    "source_probe_md",
    "decision_md",
    "model_present",
    "viewer_present",
    "projection_present",
    "top5_manifest_present",
    "alternate_present",
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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _decision_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['decision_rank']):02d}_{row['decision_class']}_{row['target_id'].lower()}"


def _source_for_target(
    target_id: str,
    overlay_row: dict[str, Any],
    freeze_by_target: dict[str, dict[str, Any]],
    hold_by_target: dict[str, dict[str, Any]],
    probe_by_target: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any], str, str]:
    freeze_row = freeze_by_target.get(target_id, {})
    hold_row = hold_by_target.get(target_id, {})
    probe_row = probe_by_target.get(target_id, {})
    overlay_decision = _text(overlay_row.get("overlay_decision"))
    if overlay_decision == "baseline_calibrated_freeze_ready":
        return (
            "freeze_ready_review",
            freeze_row,
            "freeze_candidate_existing",
            "external_model1_freeze_candidate_existing",
        )
    if probe_row:
        result = _text(probe_row.get("probe_result"))
        if result == "probe_pass_model1_retained_clear":
            return (
                "probe_required_targeted_probe",
                probe_row,
                "freeze_candidate_after_probe",
                "external_model1_freeze_candidate_after_targeted_probe",
            )
        if result == "probe_watch_model1_retained_low_margin":
            return (
                "probe_required_targeted_probe",
                probe_row,
                "watch_low_margin_after_probe",
                "external_model1_watch_low_margin_after_targeted_probe",
            )
        return (
            "probe_required_targeted_probe",
            probe_row,
            "manual_review_after_probe_failure",
            "external_model1_manual_review_after_probe_failure",
        )
    review_class = _text(hold_row.get("review_class"))
    if review_class == "interface_hold_review":
        return (
            "hold_probe_review",
            hold_row,
            "interface_hold",
            "external_model1_interface_hold_before_freeze",
        )
    if review_class == "manual_blocked_review":
        return (
            "hold_probe_review",
            hold_row,
            "manual_block",
            "external_model1_freeze_blocked_manual_review",
        )
    return ("selector_overlay", overlay_row, "unknown_hold", "external_model1_decision_unresolved")


def _field(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(source.get(key))
        if value:
            return value
    return ""


def _build_row(
    *,
    rank: int,
    overlay_row: dict[str, Any],
    source_packet: str,
    source: dict[str, Any],
    decision_class: str,
    final_selector_decision: str,
) -> dict[str, Any]:
    target_id = _text(overlay_row.get("target_id")).upper()
    selected_model = _field(source, "selected_model_filename", "primary_model_filename") or _field(
        overlay_row, "selected_model_filename", "model1_filename"
    )
    top_candidate = _field(source, "top_candidate_filename") or selected_model
    alternate_model = _field(source, "alternate_model_filename")
    model_path = _field(source, "model_path")
    viewer_html = _field(source, "viewer_html")
    projection_svg = _field(source, "projection_svg")
    top5_manifest = _field(source, "top5_manifest_csv")
    source_review_md = _field(source, "review_md")
    source_probe_md = _field(source, "probe_md")
    blockers = []
    if not selected_model:
        blockers.append("selected_model_missing")
    if not _present(model_path):
        blockers.append("model_file_missing")
    if not _present(viewer_html):
        blockers.append("viewer_html_missing")
    if not _present(projection_svg):
        blockers.append("projection_svg_missing")
    if not _present(top5_manifest):
        blockers.append("top5_manifest_missing")
    if decision_class == "manual_block" and not alternate_model:
        blockers.append("manual_block_alternate_model_missing")
    return {
        "decision_rank": rank,
        "decision_status": "post_probe_selector_decision_ready_external_only" if not blockers else "post_probe_selector_decision_blocked",
        "target_group": _field(overlay_row, "target_group"),
        "target_id": target_id,
        "overlay_rank": _int(overlay_row.get("overlay_rank")),
        "overlay_decision": _field(overlay_row, "overlay_decision"),
        "source_packet": source_packet,
        "decision_class": decision_class,
        "final_selector_decision": final_selector_decision,
        "selected_model_filename": selected_model,
        "top_candidate_filename": top_candidate,
        "alternate_model_filename": alternate_model,
        "probe_result": _field(source, "probe_result") or _field(overlay_row, "probe_result"),
        "probe_margin": _field(source, "probe_margin") or _field(overlay_row, "probe_margin"),
        "confidence_score": _field(source, "confidence_score"),
        "confidence_gap": _field(source, "confidence_gap") or _field(overlay_row, "confidence_gap"),
        "risk_score": _field(source, "risk_score") or _field(overlay_row, "risk_score"),
        "model_path": _artifact(model_path),
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "top5_manifest_csv": _artifact(top5_manifest),
        "source_review_md": _artifact(source_review_md),
        "source_probe_md": _artifact(source_probe_md),
        "decision_md": "",
        "model_present": str(_present(model_path)),
        "viewer_present": str(_present(viewer_html)),
        "projection_present": str(_present(projection_svg)),
        "top5_manifest_present": str(_present(top5_manifest)),
        "alternate_present": str(bool(alternate_model)),
        "blockers": ",".join(blockers),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }


def _write_target_decision(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Post-Probe Selector Decision",
        "",
        f"- status: `{row['decision_status']}`",
        f"- decision class: `{row['decision_class']}`",
        f"- final selector decision: `{row['final_selector_decision']}`",
        f"- source packet: `{row['source_packet']}`",
        f"- selected model: `{row['selected_model_filename']}`",
        f"- top candidate: `{row['top_candidate_filename'] or '-'}`",
        f"- alternate model: `{row['alternate_model_filename'] or '-'}`",
        f"- probe result/margin: `{row['probe_result'] or '-'}` `{row['probe_margin'] or '-'}`",
        f"- viewer: `{row['viewer_html'] or '-'}`",
        f"- source review: `{row['source_review_md'] or '-'}`",
        f"- source probe: `{row['source_probe_md'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    overlay_payload = _read_json(args.selector_overlay_json)
    freeze_payload = _read_json(args.freeze_ready_review_json)
    hold_payload = _read_json(args.hold_probe_review_json)
    probe_payload = _read_json(args.targeted_probe_json)
    overlay_summary = _summary(overlay_payload)
    freeze_summary = _summary(freeze_payload)
    hold_summary = _summary(hold_payload)
    probe_summary = _summary(probe_payload)
    freeze_by_target = _by_target(_rows(freeze_payload))
    hold_by_target = _by_target(_rows(hold_payload))
    probe_by_target = _by_target(_rows(probe_payload))
    overlay_rows = sorted(_rows(overlay_payload), key=lambda row: _int(row.get("overlay_rank")) or 999)

    rows: list[dict[str, Any]] = []
    for rank, overlay_row in enumerate(overlay_rows, start=1):
        target_id = _text(overlay_row.get("target_id")).upper()
        source_packet, source, decision_class, final_decision = _source_for_target(
            target_id, overlay_row, freeze_by_target, hold_by_target, probe_by_target
        )
        row = _build_row(
            rank=rank,
            overlay_row=overlay_row,
            source_packet=source_packet,
            source=source,
            decision_class=decision_class,
            final_selector_decision=final_decision,
        )
        decision_md = _resolve(args.out_dir) / _decision_dir_name(row) / "SELECTOR_DECISION.md"
        row["decision_md"] = _artifact(decision_md)
        _write_target_decision(decision_md, row)
        rows.append(row)

    ready_rows = [row for row in rows if row["decision_status"] == "post_probe_selector_decision_ready_external_only"]
    blocked_rows = [row for row in rows if row["decision_status"] != "post_probe_selector_decision_ready_external_only"]
    freeze_rows = [
        row
        for row in rows
        if row["decision_class"] in {"freeze_candidate_existing", "freeze_candidate_after_probe"}
    ]
    watch_rows = [
        row for row in rows if row["decision_class"] in {"watch_low_margin_after_probe", "interface_hold"}
    ]
    manual_rows = [
        row
        for row in rows
        if row["decision_class"] in {"manual_block", "manual_review_after_probe_failure", "unknown_hold"}
    ]
    first = rows[0] if rows else {}
    status = (
        "massivefold_post_probe_selector_decision_packet_ready_external_only"
        if rows and not blocked_rows
        else "massivefold_post_probe_selector_decision_packet_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_post_probe_selector_decision_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_post_probe_selector_decision_packet_status": status,
        "selector_overlay_json": _artifact(args.selector_overlay_json),
        "selector_overlay_status": _text(
            overlay_summary.get("massivefold_model1_combined_selector_overlay_status")
        ),
        "freeze_ready_review_json": _artifact(args.freeze_ready_review_json),
        "freeze_ready_review_status": _text(
            freeze_summary.get("massivefold_freeze_ready_review_packet_status")
        ),
        "hold_probe_review_json": _artifact(args.hold_probe_review_json),
        "hold_probe_review_status": _text(hold_summary.get("massivefold_hold_probe_review_packet_status")),
        "targeted_probe_json": _artifact(args.targeted_probe_json),
        "targeted_probe_status": _text(
            probe_summary.get("massivefold_probe_required_targeted_probe_packet_status")
        ),
        "decision_count": len(rows),
        "ready_decision_count": len(ready_rows),
        "blocked_decision_count": len(blocked_rows),
        "freeze_candidate_count": len(freeze_rows),
        "watch_decision_count": len(watch_rows),
        "manual_block_decision_count": len(manual_rows),
        "existing_freeze_candidate_count": sum(
            1 for row in rows if row["decision_class"] == "freeze_candidate_existing"
        ),
        "probe_freeze_candidate_count": sum(
            1 for row in rows if row["decision_class"] == "freeze_candidate_after_probe"
        ),
        "probe_watch_count": sum(1 for row in rows if row["decision_class"] == "watch_low_margin_after_probe"),
        "interface_hold_count": sum(1 for row in rows if row["decision_class"] == "interface_hold"),
        "manual_review_after_probe_failure_count": sum(
            1 for row in rows if row["decision_class"] == "manual_review_after_probe_failure"
        ),
        "manual_block_count": sum(1 for row in rows if row["decision_class"] == "manual_block"),
        "rna_hybrid_decision_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_decision_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "model_present_count": sum(1 for row in rows if row["model_present"] == "True"),
        "viewer_present_count": sum(1 for row in rows if row["viewer_present"] == "True"),
        "projection_present_count": sum(1 for row in rows if row["projection_present"] == "True"),
        "top5_manifest_present_count": sum(1 for row in rows if row["top5_manifest_present"] == "True"),
        "alternate_present_count": sum(1 for row in rows if row["alternate_present"] == "True"),
        "first_decision_target_id": _text(first.get("target_id")),
        "first_decision_class": _text(first.get("decision_class")),
        "first_selector_decision": _text(first.get("final_selector_decision")),
        "first_selected_model_filename": _text(first.get("selected_model_filename")),
        "decision_dir": _artifact(args.out_dir),
        "decision_csv": _artifact(args.out_csv),
        "decision_html": _artifact(args.out_html),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": "review watch/manual/interface rows before any CASP rule-checked formatting; keep strict-blind proof separate",
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Post-Probe Selector Decision Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_post_probe_selector_decision_packet_status']}`",
        f"- decisions ready/blocked/total: `{summary['ready_decision_count']}/{summary['blocked_decision_count']}/{summary['decision_count']}`",
        f"- freeze/watch/manual: `{summary['freeze_candidate_count']}/{summary['watch_decision_count']}/{summary['manual_block_decision_count']}`",
        f"- freeze existing/probe: `{summary['existing_freeze_candidate_count']}/{summary['probe_freeze_candidate_count']}`",
        f"- watch probe/interface: `{summary['probe_watch_count']}/{summary['interface_hold_count']}`",
        f"- manual probe-fail/manual-block: `{summary['manual_review_after_probe_failure_count']}/{summary['manual_block_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_decision_count']}/{summary['protein_complex_decision_count']}`",
        f"- model/viewer/projection/top5/alternate: `{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top5_manifest_present_count']}/{summary['alternate_present_count']}`",
        f"- first decision: `{summary['first_decision_target_id'] or '-'}` `{summary['first_decision_class'] or '-'}` `{summary['first_selector_decision'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Decisions",
        "",
        "| rank | target | class | final decision | selected model | top candidate | margin | viewer | packet | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['decision_rank']}` | `{row['target_id']}` | `{row['decision_class']}` | "
            f"`{row['final_selector_decision']}` | `{row['selected_model_filename']}` | "
            f"`{row['top_candidate_filename'] or '-'}` | `{row['probe_margin'] or '-'}` | "
            f"`{row['viewer_html'] or '-'}` | `{row['decision_md']}` | `{row['blockers'] or '-'}` |"
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
        decision = html.escape(row["decision_md"])
        cards.append(
            "<section>"
            f"<h2>{html.escape(row['target_id'])} <span>{html.escape(row['decision_class'])}</span></h2>"
            f"<p><strong>{html.escape(row['selected_model_filename'])}</strong></p>"
            f"<p>{html.escape(row['final_selector_decision'])}</p>"
            f"<p>margin {html.escape(row['probe_margin'] or '-')} source {html.escape(row['source_packet'])}</p>"
            f"<p><a href=\"{viewer}\">viewer</a> <a href=\"{decision}\">decision</a></p>"
            f"<p>{html.escape(row['blockers'] or 'ready external-only selector decision')}</p>"
            "</section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Selector Decisions</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "section{border:1px solid #bbb;border-radius:6px;padding:14px;margin:12px 0}"
        "span{font-size:13px;font-weight:400;color:#555}a{margin-right:12px}</style></head><body>"
        "<h1>CASP17 MassiveFold Post-Probe Selector Decisions</h1>"
        f"<p>Status: {html.escape(summary['massivefold_post_probe_selector_decision_packet_status'])}</p>"
        f"<p>Ready/blocked/total: {summary['ready_decision_count']}/{summary['blocked_decision_count']}/{summary['decision_count']}</p>"
        f"<p>Freeze/watch/manual: {summary['freeze_candidate_count']}/{summary['watch_decision_count']}/{summary['manual_block_decision_count']}</p>"
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
    _write_json(_resolve(args.out_dir) / "post_probe_selector_decision_packet.json", payload)
    _write_csv(_resolve(args.out_dir) / "post_probe_selector_decision_packet.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a post-probe selector decision map for CASP17 MassiveFold rows.")
    parser.add_argument("--selector-overlay-json", default=DEFAULT_SELECTOR_OVERLAY_JSON)
    parser.add_argument("--freeze-ready-review-json", default=DEFAULT_FREEZE_READY_REVIEW_JSON)
    parser.add_argument("--hold-probe-review-json", default=DEFAULT_HOLD_PROBE_REVIEW_JSON)
    parser.add_argument("--targeted-probe-json", default=DEFAULT_TARGETED_PROBE_JSON)
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
                "status": payload["summary"]["massivefold_post_probe_selector_decision_packet_status"],
                "ready": payload["summary"]["ready_decision_count"],
                "blocked": payload["summary"]["blocked_decision_count"],
                "total": payload["summary"]["decision_count"],
                "freeze": payload["summary"]["freeze_candidate_count"],
                "watch": payload["summary"]["watch_decision_count"],
                "manual": payload["summary"]["manual_block_decision_count"],
                "first": payload["summary"]["first_decision_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
