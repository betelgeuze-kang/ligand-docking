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

DEFAULT_POST_PROBE_SELECTOR_DECISION_JSON = (
    "casp17/casp17_massivefold_post_probe_selector_decision_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_watch_manual_action_packet"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_watch_manual_action_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_watch_manual_action_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_WATCH_MANUAL_ACTION_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_massivefold_watch_manual_action_packet_current.html"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe "
    "selector holds into review actions for low-margin, interface, and manual-block cases. It is not "
    "native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit "
    "without operator approval."
)
EXTERNAL_ONLY_POLICY = "external_no_native_watch_manual_action_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "post_probe_watch_manual_action_packet_v1"
FREEZE_CLASSES = {"freeze_candidate_existing", "freeze_candidate_after_probe"}

ROW_COLUMNS = [
    "action_rank",
    "action_status",
    "target_group",
    "target_id",
    "decision_rank",
    "decision_class",
    "final_selector_decision",
    "action_class",
    "action_priority",
    "selected_model_filename",
    "alternate_model_filename",
    "probe_result",
    "probe_margin",
    "review_question",
    "exit_criterion",
    "model_path",
    "viewer_html",
    "projection_svg",
    "top5_manifest_csv",
    "source_decision_md",
    "action_md",
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


def _action_class(decision_class: str) -> tuple[str, int, str, str]:
    if decision_class == "manual_block":
        return (
            "manual_alternate_review",
            1,
            "Should the alternate/top candidate replace model1, or should this target remain blocked?",
            "operator records manual decision; do not freeze model1 until alternate/model1 choice is approved",
        )
    if decision_class == "interface_hold":
        return (
            "interface_geometry_review",
            1,
            "Does the model1 interface/assembly clear chain geometry, clash, and stoichiometry review?",
            "interface review clears chain geometry and no new high-risk assembly flag remains",
        )
    if decision_class == "watch_low_margin_after_probe":
        return (
            "low_margin_top5_review",
            2,
            "Does model1 remain acceptable after inspecting the nearest top5 competitor and margin?",
            "operator accepts low-margin model1 or reranks the top5 before any freeze",
        )
    return (
        "unresolved_selector_review",
        1,
        "What selector decision should be applied to this unresolved target?",
        "operator resolves selector decision class before any freeze",
    )


def _action_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['action_rank']):02d}_{row['action_class']}_{row['target_id'].lower()}"


def _build_action_row(rank: int, source: dict[str, Any]) -> dict[str, Any]:
    action_class, priority, question, exit_criterion = _action_class(_text(source.get("decision_class")))
    model_path = _text(source.get("model_path"))
    viewer_html = _text(source.get("viewer_html"))
    projection_svg = _text(source.get("projection_svg"))
    top5_manifest = _text(source.get("top5_manifest_csv"))
    alternate_model = _text(source.get("alternate_model_filename"))
    blockers = []
    if not _present(model_path):
        blockers.append("model_file_missing")
    if not _present(viewer_html):
        blockers.append("viewer_html_missing")
    if not _present(projection_svg):
        blockers.append("projection_svg_missing")
    if not _present(top5_manifest):
        blockers.append("top5_manifest_missing")
    if action_class == "manual_alternate_review" and not alternate_model:
        blockers.append("manual_alternate_missing")
    return {
        "action_rank": rank,
        "action_status": "watch_manual_action_ready_external_only" if not blockers else "watch_manual_action_blocked",
        "target_group": _text(source.get("target_group")),
        "target_id": _text(source.get("target_id")).upper(),
        "decision_rank": _int(source.get("decision_rank")),
        "decision_class": _text(source.get("decision_class")),
        "final_selector_decision": _text(source.get("final_selector_decision")),
        "action_class": action_class,
        "action_priority": priority,
        "selected_model_filename": _text(source.get("selected_model_filename")),
        "alternate_model_filename": alternate_model,
        "probe_result": _text(source.get("probe_result")),
        "probe_margin": _text(source.get("probe_margin")),
        "review_question": question,
        "exit_criterion": exit_criterion,
        "model_path": _artifact(model_path),
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "top5_manifest_csv": _artifact(top5_manifest),
        "source_decision_md": _artifact(source.get("decision_md", "")),
        "action_md": "",
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


def _write_target_action(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Watch/Manual Action",
        "",
        f"- status: `{row['action_status']}`",
        f"- action class: `{row['action_class']}`",
        f"- priority: `{row['action_priority']}`",
        f"- decision class: `{row['decision_class']}`",
        f"- final selector decision: `{row['final_selector_decision']}`",
        f"- selected model: `{row['selected_model_filename']}`",
        f"- alternate model: `{row['alternate_model_filename'] or '-'}`",
        f"- probe result/margin: `{row['probe_result'] or '-'}` `{row['probe_margin'] or '-'}`",
        f"- viewer: `{row['viewer_html'] or '-'}`",
        f"- top5 manifest: `{row['top5_manifest_csv'] or '-'}`",
        f"- source decision: `{row['source_decision_md'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Review Question",
        "",
        row["review_question"],
        "",
        "## Exit Criterion",
        "",
        row["exit_criterion"],
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
    action_sources = [
        row for row in _rows(decision_payload) if _text(row.get("decision_class")) not in FREEZE_CLASSES
    ]
    action_sources.sort(key=lambda row: (_int(row.get("decision_rank")), _text(row.get("target_id"))))
    rows: list[dict[str, Any]] = []
    for rank, source in enumerate(action_sources, start=1):
        row = _build_action_row(rank, source)
        action_md = _resolve(args.out_dir) / _action_dir_name(row) / "WATCH_MANUAL_ACTION.md"
        row["action_md"] = _artifact(action_md)
        _write_target_action(action_md, row)
        rows.append(row)

    ready_rows = [row for row in rows if row["action_status"] == "watch_manual_action_ready_external_only"]
    blocked_rows = [row for row in rows if row["action_status"] != "watch_manual_action_ready_external_only"]
    first = rows[0] if rows else {}
    status = (
        "massivefold_watch_manual_action_packet_ready_external_only"
        if rows and not blocked_rows
        else "massivefold_watch_manual_action_packet_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_watch_manual_action_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_watch_manual_action_packet_status": status,
        "post_probe_selector_decision_json": _artifact(args.post_probe_selector_decision_json),
        "post_probe_selector_decision_status": _text(
            decision_summary.get("massivefold_post_probe_selector_decision_packet_status")
        ),
        "action_count": len(rows),
        "ready_action_count": len(ready_rows),
        "blocked_action_count": len(blocked_rows),
        "manual_alternate_review_count": sum(1 for row in rows if row["action_class"] == "manual_alternate_review"),
        "interface_geometry_review_count": sum(1 for row in rows if row["action_class"] == "interface_geometry_review"),
        "low_margin_top5_review_count": sum(1 for row in rows if row["action_class"] == "low_margin_top5_review"),
        "priority1_action_count": sum(1 for row in rows if int(row["action_priority"]) == 1),
        "priority2_action_count": sum(1 for row in rows if int(row["action_priority"]) == 2),
        "rna_hybrid_action_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_action_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "model_present_count": sum(1 for row in rows if row["model_present"] == "True"),
        "viewer_present_count": sum(1 for row in rows if row["viewer_present"] == "True"),
        "projection_present_count": sum(1 for row in rows if row["projection_present"] == "True"),
        "top5_manifest_present_count": sum(1 for row in rows if row["top5_manifest_present"] == "True"),
        "alternate_present_count": sum(1 for row in rows if row["alternate_present"] == "True"),
        "first_action_target_id": _text(first.get("target_id")),
        "first_action_class": _text(first.get("action_class")),
        "first_action_priority": _text(first.get("action_priority")),
        "first_exit_criterion": _text(first.get("exit_criterion")),
        "action_dir": _artifact(args.out_dir),
        "action_csv": _artifact(args.out_csv),
        "action_html": _artifact(args.out_html),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": "operator resolves the five watch/manual/interface actions before any CASP rule-checked formatting",
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Watch/Manual Action Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_watch_manual_action_packet_status']}`",
        f"- actions ready/blocked/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- classes manual/interface/low-margin: `{summary['manual_alternate_review_count']}/{summary['interface_geometry_review_count']}/{summary['low_margin_top5_review_count']}`",
        f"- priority 1/2: `{summary['priority1_action_count']}/{summary['priority2_action_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_action_count']}/{summary['protein_complex_action_count']}`",
        f"- model/viewer/projection/top5/alternate: `{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top5_manifest_present_count']}/{summary['alternate_present_count']}`",
        f"- first action: `{summary['first_action_target_id'] or '-'}` `{summary['first_action_class'] or '-'}` priority `{summary['first_action_priority'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Actions",
        "",
        "| rank | target | class | priority | margin | question | viewer | action | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_rank']}` | `{row['target_id']}` | `{row['action_class']}` | "
            f"`{row['action_priority']}` | `{row['probe_margin'] or '-'}` | "
            f"{row['review_question']} | `{row['viewer_html'] or '-'}` | "
            f"`{row['action_md']}` | `{row['blockers'] or '-'}` |"
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
        action = html.escape(row["action_md"])
        cards.append(
            "<section>"
            f"<h2>{html.escape(row['target_id'])} <span>{html.escape(row['action_class'])}</span></h2>"
            f"<p><strong>{html.escape(row['selected_model_filename'])}</strong></p>"
            f"<p>priority {html.escape(str(row['action_priority']))} margin {html.escape(row['probe_margin'] or '-')}</p>"
            f"<p>{html.escape(row['review_question'])}</p>"
            f"<p><a href=\"{viewer}\">viewer</a> <a href=\"{action}\">action</a></p>"
            f"<p>{html.escape(row['blockers'] or 'ready external-only watch/manual action')}</p>"
            "</section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>CASP17 MassiveFold Watch Manual Actions</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "section{border:1px solid #bbb;border-radius:6px;padding:14px;margin:12px 0}"
        "span{font-size:13px;font-weight:400;color:#555}a{margin-right:12px}</style></head><body>"
        "<h1>CASP17 MassiveFold Watch/Manual Actions</h1>"
        f"<p>Status: {html.escape(summary['massivefold_watch_manual_action_packet_status'])}</p>"
        f"<p>Ready/blocked/total: {summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}</p>"
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
    _write_json(_resolve(args.out_dir) / "watch_manual_action_packet.json", payload)
    _write_csv(_resolve(args.out_dir) / "watch_manual_action_packet.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build watch/manual action rows from the MassiveFold post-probe selector map.")
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
                "status": payload["summary"]["massivefold_watch_manual_action_packet_status"],
                "ready": payload["summary"]["ready_action_count"],
                "blocked": payload["summary"]["blocked_action_count"],
                "total": payload["summary"]["action_count"],
                "manual": payload["summary"]["manual_alternate_review_count"],
                "interface": payload["summary"]["interface_geometry_review_count"],
                "low_margin": payload["summary"]["low_margin_top5_review_count"],
                "first": payload["summary"]["first_action_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
