#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACTION_BOARD_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json"
DEFAULT_METRIC_RUNWAY_JSON = "casp17/casp17_competitive_floor_target_identity_metric_runway_current.json"
DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_NATIVE_CANDIDATE_PACKET_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_native_provenance_operator_packet"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_NATIVE_PROVENANCE_OPERATOR_PACKET.md"
DEFAULT_OUT_HTML = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.html"

CLAIM_BOUNDARY = (
    "CASP17 competitive-floor native/provenance operator packet only. It groups existing target-identity "
    "native dropzone, no-leak evidence, provenance, manifest, native-candidate, and metric-runway links "
    "for operator fill. It does not fetch native structures, clear no-leak provenance, copy coordinates, "
    "compute native accuracy, serialize a CASP author code, promote identities, mutate intake files, or submit to CASP."
)
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "operator_packet_status",
    "packet_folder",
    "packet_readme",
    "packet_manifest",
    "actions_csv",
    "native_candidates_csv",
    "action_count",
    "open_action_count",
    "native_action_count",
    "evidence_action_count",
    "provenance_action_count",
    "manifest_action_count",
    "metric_requirement_count",
    "required_metric_names",
    "metric_runway_status",
    "metric_runway_md",
    "workorder_folder",
    "workorder_readme",
    "prediction_pdb",
    "ts_prediction_pdb",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "native_candidate_count",
    "native_candidate_blocked_count",
    "native_candidate_no_candidate_count",
    "first_native_candidate_pdb_id",
    "first_native_candidate_status",
    "first_native_candidate_blockers",
    "prediction_status",
    "native_status",
    "provenance_status",
    "evidence_ref_status",
    "verification_command",
    "blockers",
    "next_action",
    "competitive_proof_eligible",
    "author_serialized",
    "claim_boundary",
    "submission_policy",
]

ACTION_COLUMNS = [
    "action_rank",
    "lane",
    "required_field",
    "required_artifact",
    "action_status",
    "blockers",
    "recommended_action",
    "unlocks",
    "verification_command",
]

NATIVE_CANDIDATE_COLUMNS = [
    "pdb_id",
    "candidate_status",
    "blockers",
    "download_url",
    "initial_release_date",
    "experimental_method",
    "resolution_combined",
    "struct_title",
    "native_source_pdb_suggestion",
    "next_action",
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get("target_id"))].append(row)
    return dict(grouped)


def _row_by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in rows}


def _packet_row(
    target_id: str,
    actions: list[dict[str, Any]],
    runway: dict[str, Any],
    workorder: dict[str, Any],
    native_candidates: list[dict[str, Any]],
    out_dir: Path,
) -> dict[str, Any]:
    target_name = _text(runway.get("target_name")) or _text(workorder.get("target_name")) or target_id
    packet_folder = out_dir / f"{target_id}_{_safe_component(target_name)}"
    open_actions = [row for row in actions if _text(row.get("action_status")) == "open"]
    lanes = [row.get("lane") for row in actions]
    native_blocked = [row for row in native_candidates if _text(row.get("candidate_status")).startswith("blocked")]
    native_missing = [row for row in native_candidates if _text(row.get("candidate_status")) == "no_rcsb_candidate_found"]
    first_candidate = native_candidates[0] if native_candidates else {}
    blockers = [
        blocker
        for row in actions
        for blocker in _text(row.get("blockers")).split(",")
        if blocker
    ]
    blockers.extend(blocker for blocker in _text(runway.get("blockers")).split(",") if blocker)
    if not _is_file(runway.get("prediction_pdb", "") or workorder.get("prediction_pdb", "")):
        blockers.append("prediction_pdb_missing")
    if not _is_file(runway.get("ts_prediction_pdb", "") or workorder.get("ts_prediction_pdb", "")):
        blockers.append("ts_prediction_pdb_missing")
    if not native_candidates:
        blockers.append("native_candidate_packet_missing")
    blockers = list(dict.fromkeys(blockers))
    verification_command = _text(actions[0].get("verification_command")) if actions else ""
    status = "open_actions" if open_actions or blockers else "ready_after_operator_fill"
    return {
        "target_id": target_id,
        "target_name": target_name,
        "operator_packet_status": status,
        "packet_folder": _artifact(packet_folder),
        "packet_readme": _artifact(packet_folder / "README.md"),
        "packet_manifest": _artifact(packet_folder / "operator_packet_manifest.json"),
        "actions_csv": _artifact(packet_folder / "actions.csv"),
        "native_candidates_csv": _artifact(packet_folder / "native_candidates.csv"),
        "action_count": len(actions),
        "open_action_count": len(open_actions),
        "native_action_count": lanes.count("native_dropzone"),
        "evidence_action_count": lanes.count("no_leak_evidence"),
        "provenance_action_count": lanes.count("provenance_fields"),
        "manifest_action_count": lanes.count("manifest_stub_sync"),
        "metric_requirement_count": _int(runway.get("metric_requirement_count")),
        "required_metric_names": _text(runway.get("required_metric_names")),
        "metric_runway_status": _text(runway.get("runway_status")),
        "metric_runway_md": _artifact(runway.get("metric_runway_md", "")),
        "workorder_folder": _artifact(workorder.get("workorder_folder", "")),
        "workorder_readme": _artifact(workorder.get("readme_path", "")),
        "prediction_pdb": _artifact(runway.get("prediction_pdb") or workorder.get("prediction_pdb", "")),
        "ts_prediction_pdb": _artifact(runway.get("ts_prediction_pdb") or workorder.get("ts_prediction_pdb", "")),
        "native_dropzone_pdb": _artifact(runway.get("native_dropzone_pdb") or workorder.get("native_dropzone_pdb", "")),
        "provenance_template_csv": _artifact(
            runway.get("provenance_template_csv") or workorder.get("provenance_template_csv", "")
        ),
        "manifest_stub_csv": _artifact(runway.get("manifest_stub_csv") or workorder.get("manifest_stub_csv", "")),
        "native_candidate_count": len(native_candidates),
        "native_candidate_blocked_count": len(native_blocked),
        "native_candidate_no_candidate_count": len(native_missing),
        "first_native_candidate_pdb_id": _text(first_candidate.get("pdb_id")),
        "first_native_candidate_status": _text(first_candidate.get("candidate_status")),
        "first_native_candidate_blockers": _text(first_candidate.get("blockers")),
        "prediction_status": _text(runway.get("prediction_status")) or "unknown",
        "native_status": _text(runway.get("native_status")) or "unknown",
        "provenance_status": _text(runway.get("provenance_status")) or "unknown",
        "evidence_ref_status": _text(runway.get("evidence_ref_status")) or "unknown",
        "verification_command": verification_command,
        "blockers": ",".join(blockers),
        "next_action": _text(actions[0].get("recommended_action")) if actions else _text(runway.get("next_action")),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    action_payload = _read_json(args.action_board_json)
    action_summary = _summary(action_payload)
    runway_payload = _read_json(args.metric_runway_json)
    runway_summary = _summary(runway_payload)
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    native_payload = _read_json(args.native_candidate_packet_json)
    native_summary = _summary(native_payload)
    actions_by_target = _by_target(_rows(action_payload))
    runway_by_target = _row_by_target(_rows(runway_payload))
    workorder_by_target = _row_by_target(_rows(workorder_payload))
    native_by_target = _by_target(_rows(native_payload))
    target_ids = sorted(set(actions_by_target) | set(runway_by_target) | set(workorder_by_target))
    out_dir = _resolve(args.out_dir)
    rows = [
        _packet_row(
            target_id,
            sorted(actions_by_target.get(target_id, []), key=lambda row: _int(row.get("action_rank"))),
            runway_by_target.get(target_id, {}),
            workorder_by_target.get(target_id, {}),
            native_by_target.get(target_id, []),
            out_dir,
        )
        for target_id in target_ids
    ]
    open_rows = [row for row in rows if row["operator_packet_status"] == "open_actions"]
    first = rows[0] if rows else {}
    status = "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
    if not rows:
        status = "casp17_competitive_floor_native_provenance_operator_packet_blocked_no_targets"
    elif not open_rows:
        status = "casp17_competitive_floor_native_provenance_operator_packet_ready_after_operator_fill"
    summary = {
        "packet_type": "casp17_competitive_floor_native_provenance_operator_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "operator_packet_status": status,
        "action_board_json": _artifact(args.action_board_json),
        "action_board_status": _text(action_summary.get("action_board_status")),
        "metric_runway_json": _artifact(args.metric_runway_json),
        "metric_runway_status": _text(runway_summary.get("metric_runway_status")),
        "workorder_json": _artifact(args.workorder_json),
        "workorder_status": _text(workorder_summary.get("clearance_workorder_status")),
        "native_candidate_packet_json": _artifact(args.native_candidate_packet_json),
        "native_candidate_packet_status": _text(native_summary.get("native_candidate_packet_status")),
        "out_dir": _artifact(args.out_dir),
        "html_packet_path": _artifact(args.out_html),
        "target_count": len(rows),
        "target_open_count": len(open_rows),
        "target_ready_count": len(rows) - len(open_rows),
        "action_count": sum(_int(row.get("action_count")) for row in rows),
        "open_action_count": sum(_int(row.get("open_action_count")) for row in rows),
        "native_action_count": sum(_int(row.get("native_action_count")) for row in rows),
        "evidence_action_count": sum(_int(row.get("evidence_action_count")) for row in rows),
        "provenance_action_count": sum(_int(row.get("provenance_action_count")) for row in rows),
        "manifest_action_count": sum(_int(row.get("manifest_action_count")) for row in rows),
        "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in rows),
        "prediction_present_count": sum(1 for row in rows if row["prediction_status"] == "present"),
        "native_present_count": sum(1 for row in rows if row["native_status"] == "present"),
        "provenance_ready_count": sum(1 for row in rows if row["provenance_status"] == "ready"),
        "evidence_ref_ready_count": sum(1 for row in rows if row["evidence_ref_status"] == "verified"),
        "native_candidate_count": sum(_int(row.get("native_candidate_count")) for row in rows),
        "native_candidate_blocked_count": sum(_int(row.get("native_candidate_blocked_count")) for row in rows),
        "native_candidate_no_candidate_count": sum(_int(row.get("native_candidate_no_candidate_count")) for row in rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_target_id": _text(first.get("target_id")),
        "first_open_target_id": _text(open_rows[0].get("target_id")) if open_rows else "",
        "first_open_next_action": _text(open_rows[0].get("next_action")) if open_rows else "",
        "next_action": "Fill each target packet's native PDB, no-leak evidence reference, provenance fields, and manifest sync.",
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_packet_files(payload: dict[str, Any], action_rows: list[dict[str, Any]], native_rows: list[dict[str, Any]]) -> None:
    actions_by_target = _by_target(action_rows)
    native_by_target = _by_target(native_rows)
    for row in payload["rows"]:
        folder = _resolve(row["packet_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        actions = sorted(actions_by_target.get(row["target_id"], []), key=lambda action: _int(action.get("action_rank")))
        natives = native_by_target.get(row["target_id"], [])
        _write_csv(row["actions_csv"], actions, ACTION_COLUMNS)
        _write_csv(row["native_candidates_csv"], natives, NATIVE_CANDIDATE_COLUMNS)
        _write_json(row["packet_manifest"], {"summary": row, "actions": actions, "native_candidates": natives})
        lines = [
            f"# {row['target_id']} Native/Provenance Operator Packet",
            "",
            f"- target: `{row['target_name']}`",
            f"- status: `{row['operator_packet_status']}`",
            f"- actions native/evidence/provenance/manifest: `{row['native_action_count']}/{row['evidence_action_count']}/{row['provenance_action_count']}/{row['manifest_action_count']}`",
            f"- metric requirements: `{row['metric_requirement_count']}`",
            f"- prediction: `{row['prediction_pdb']}`",
            f"- native dropzone: `{row['native_dropzone_pdb']}`",
            f"- provenance template: `{row['provenance_template_csv']}`",
            f"- manifest stub: `{row['manifest_stub_csv']}`",
            f"- metric runway: `{row['metric_runway_md']}`",
            f"- native candidates blocked/no-candidate/total: `{row['native_candidate_blocked_count']}/{row['native_candidate_no_candidate_count']}/{row['native_candidate_count']}`",
            f"- proof/author: `{row['competitive_proof_eligible']}/{row['author_serialized']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            "",
            "## Actions",
            "",
            "| lane | field | artifact | action |",
            "| --- | --- | --- | --- |",
        ]
        for action in actions:
            lines.append(
                f"| `{_text(action.get('lane'))}` | `{_text(action.get('required_field'))}` | "
                f"`{_text(action.get('required_artifact'))}` | `{_text(action.get('recommended_action'))}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        _resolve(row["packet_readme"]).write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Native/Provenance Operator Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['operator_packet_status']}`",
        f"- targets open/ready/total: `{summary['target_open_count']}/{summary['target_ready_count']}/{summary['target_count']}`",
        f"- actions open/total: `{summary['open_action_count']}/{summary['action_count']}`",
        f"- action lanes native/evidence/provenance/manifest: `{summary['native_action_count']}/{summary['evidence_action_count']}/{summary['provenance_action_count']}/{summary['manifest_action_count']}`",
        f"- metric requirements: `{summary['metric_requirement_count']}`",
        f"- prediction/native/provenance/evidence ready: `{summary['prediction_present_count']}/{summary['native_present_count']}/{summary['provenance_ready_count']}/{summary['evidence_ref_ready_count']}`",
        f"- native candidates blocked/no-candidate/total: `{summary['native_candidate_blocked_count']}/{summary['native_candidate_no_candidate_count']}/{summary['native_candidate_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html packet: `{summary['html_packet_path']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_next_action'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | actions | metrics | native | provenance | packet |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['operator_packet_status']}` | "
            f"`{row['open_action_count']}/{row['action_count']}` | `{row['metric_requirement_count']}` | "
            f"`{row['native_status']}` | `{row['provenance_status']}` | `{row['packet_folder']}` |"
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
            f"<td>{html.escape(row['target_name'])}</td>"
            f"<td>{html.escape(row['operator_packet_status'])}</td>"
            f"<td>{row['open_action_count']}/{row['action_count']}</td>"
            f"<td>{row['metric_requirement_count']}</td>"
            f"<td>{html.escape(row['native_status'])}</td>"
            f"<td>{html.escape(row['provenance_status'])}</td>"
            "</tr>"
        )
    path = _resolve(path_like)
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 Native Provenance Operator Packet</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 Native Provenance Operator Packet</h1>",
            f"<p>Status: <code>{html.escape(summary['operator_packet_status'])}</code></p>",
            f"<p>Actions: {summary['open_action_count']}/{summary['action_count']} open/total.</p>",
            "<table><thead><tr><th>target</th><th>name</th><th>status</th><th>actions</th><th>metrics</th><th>native</th><th>provenance</th></tr></thead><tbody>",
            "\n".join(body_rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    action_rows = _rows(_read_json(args.action_board_json))
    native_rows = _rows(_read_json(args.native_candidate_packet_json))
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_packet_files(payload, action_rows, native_rows)
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 native/provenance operator packet.")
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--metric-runway-json", default=DEFAULT_METRIC_RUNWAY_JSON)
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--native-candidate-packet-json", default=DEFAULT_NATIVE_CANDIDATE_PACKET_JSON)
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
