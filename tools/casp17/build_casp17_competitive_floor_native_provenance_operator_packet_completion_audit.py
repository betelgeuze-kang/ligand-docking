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

DEFAULT_OPERATOR_PACKET_JSON = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_NATIVE_PROVENANCE_OPERATOR_PACKET_COMPLETION_AUDIT.md"
DEFAULT_OUT_HTML = "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.html"

READY_OPERATOR_PACKET_STATUSES = {
    "casp17_competitive_floor_native_provenance_operator_packet_open_actions",
    "casp17_competitive_floor_native_provenance_operator_packet_ready_after_operator_fill",
}
READY_ROW_STATUSES = {"open_actions", "ready_after_operator_fill"}
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor native/provenance operator packet completion audit only. It verifies "
    "target packet folders, packet manifests, action and native-candidate CSVs, upstream input links, "
    "no-coordinate-copy hygiene, and proof boundary flags. It does not fetch native structures, clear "
    "no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP."
)

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "audit_status",
    "operator_packet_status",
    "packet_folder",
    "packet_readme",
    "packet_manifest",
    "actions_csv",
    "native_candidates_csv",
    "packet_folder_present",
    "packet_readme_present",
    "packet_manifest_present",
    "actions_csv_present",
    "native_candidates_csv_present",
    "action_expected_row_count",
    "action_csv_row_count",
    "action_row_mismatch",
    "native_candidate_expected_row_count",
    "native_candidate_csv_row_count",
    "native_candidate_row_mismatch",
    "native_action_expected_count",
    "native_action_csv_count",
    "evidence_action_expected_count",
    "evidence_action_csv_count",
    "provenance_action_expected_count",
    "provenance_action_csv_count",
    "manifest_action_expected_count",
    "manifest_action_csv_count",
    "metric_requirement_count",
    "metric_runway_present",
    "workorder_folder_present",
    "workorder_readme_present",
    "prediction_present",
    "ts_prediction_present",
    "native_dropzone_path_present",
    "native_file_present",
    "provenance_template_present",
    "manifest_stub_present",
    "packet_coordinate_copy_count",
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


def _bool_int(value: bool) -> int:
    return 1 if value else 0


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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _coordinate_copy_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file() and child.suffix.lower() in {".pdb", ".cif"})


def _lane_count(rows: list[dict[str, str]], lane: str) -> int:
    return sum(1 for row in rows if _text(row.get("lane")) == lane)


def _audit_row(row: dict[str, Any], global_blockers: list[str]) -> dict[str, Any]:
    blockers = global_blockers[:]
    actions = _read_csv_rows(row.get("actions_csv", ""))
    native_candidates = _read_csv_rows(row.get("native_candidates_csv", ""))
    packet_coordinate_copy_count = _coordinate_copy_count(row.get("packet_folder", ""))
    path_checks = [
        ("packet_folder_missing", row.get("packet_folder", ""), _is_dir),
        ("packet_readme_missing", row.get("packet_readme", ""), _is_file),
        ("packet_manifest_missing", row.get("packet_manifest", ""), _is_file),
        ("actions_csv_missing", row.get("actions_csv", ""), _is_file),
        ("native_candidates_csv_missing", row.get("native_candidates_csv", ""), _is_file),
        ("metric_runway_missing", row.get("metric_runway_md", ""), _is_file),
        ("workorder_folder_missing", row.get("workorder_folder", ""), _is_dir),
        ("workorder_readme_missing", row.get("workorder_readme", ""), _is_file),
        ("prediction_pdb_missing", row.get("prediction_pdb", ""), _is_file),
        ("ts_prediction_pdb_missing", row.get("ts_prediction_pdb", ""), _is_file),
        ("provenance_template_missing", row.get("provenance_template_csv", ""), _is_file),
        ("manifest_stub_missing", row.get("manifest_stub_csv", ""), _is_file),
    ]
    for blocker, path_like, predicate in path_checks:
        if not predicate(_text(path_like)):
            blockers.append(blocker)
    if not _text(row.get("native_dropzone_pdb")):
        blockers.append("native_dropzone_path_missing")
    if _int(row.get("action_count")) != len(actions):
        blockers.append("action_csv_row_count_mismatch")
    if _int(row.get("native_candidate_count")) != len(native_candidates):
        blockers.append("native_candidate_csv_row_count_mismatch")
    lane_pairs = [
        ("native_action_count", "native_action_csv_count", "native_dropzone", "native_action_csv_count_mismatch"),
        ("evidence_action_count", "evidence_action_csv_count", "no_leak_evidence", "evidence_action_csv_count_mismatch"),
        ("provenance_action_count", "provenance_action_csv_count", "provenance_fields", "provenance_action_csv_count_mismatch"),
        ("manifest_action_count", "manifest_action_csv_count", "manifest_stub_sync", "manifest_action_csv_count_mismatch"),
    ]
    lane_counts: dict[str, int] = {}
    for expected_key, csv_key, lane, blocker in lane_pairs:
        lane_counts[csv_key] = _lane_count(actions, lane)
        if _int(row.get(expected_key)) != lane_counts[csv_key]:
            blockers.append(blocker)
    if _text(row.get("operator_packet_status")) not in READY_ROW_STATUSES:
        blockers.append("operator_packet_row_status_not_open_or_ready")
    if _text(row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if _text(row.get("author_serialized")).lower() != "false":
        blockers.append("author_serialized_not_false")
    if packet_coordinate_copy_count:
        blockers.append("packet_coordinate_copy_present")
    blockers = list(dict.fromkeys(blockers))
    return {
        "target_id": _text(row.get("target_id")),
        "target_name": _text(row.get("target_name")),
        "audit_status": "pass" if not blockers else "blocked",
        "operator_packet_status": _text(row.get("operator_packet_status")),
        "packet_folder": _artifact(row.get("packet_folder", "")),
        "packet_readme": _artifact(row.get("packet_readme", "")),
        "packet_manifest": _artifact(row.get("packet_manifest", "")),
        "actions_csv": _artifact(row.get("actions_csv", "")),
        "native_candidates_csv": _artifact(row.get("native_candidates_csv", "")),
        "packet_folder_present": _bool_int(_is_dir(row.get("packet_folder", ""))),
        "packet_readme_present": _bool_int(_is_file(row.get("packet_readme", ""))),
        "packet_manifest_present": _bool_int(_is_file(row.get("packet_manifest", ""))),
        "actions_csv_present": _bool_int(_is_file(row.get("actions_csv", ""))),
        "native_candidates_csv_present": _bool_int(_is_file(row.get("native_candidates_csv", ""))),
        "action_expected_row_count": _int(row.get("action_count")),
        "action_csv_row_count": len(actions),
        "action_row_mismatch": _bool_int(_int(row.get("action_count")) != len(actions)),
        "native_candidate_expected_row_count": _int(row.get("native_candidate_count")),
        "native_candidate_csv_row_count": len(native_candidates),
        "native_candidate_row_mismatch": _bool_int(_int(row.get("native_candidate_count")) != len(native_candidates)),
        "native_action_expected_count": _int(row.get("native_action_count")),
        "native_action_csv_count": lane_counts["native_action_csv_count"],
        "evidence_action_expected_count": _int(row.get("evidence_action_count")),
        "evidence_action_csv_count": lane_counts["evidence_action_csv_count"],
        "provenance_action_expected_count": _int(row.get("provenance_action_count")),
        "provenance_action_csv_count": lane_counts["provenance_action_csv_count"],
        "manifest_action_expected_count": _int(row.get("manifest_action_count")),
        "manifest_action_csv_count": lane_counts["manifest_action_csv_count"],
        "metric_requirement_count": _int(row.get("metric_requirement_count")),
        "metric_runway_present": _bool_int(_is_file(row.get("metric_runway_md", ""))),
        "workorder_folder_present": _bool_int(_is_dir(row.get("workorder_folder", ""))),
        "workorder_readme_present": _bool_int(_is_file(row.get("workorder_readme", ""))),
        "prediction_present": _bool_int(_is_file(row.get("prediction_pdb", ""))),
        "ts_prediction_present": _bool_int(_is_file(row.get("ts_prediction_pdb", ""))),
        "native_dropzone_path_present": _bool_int(bool(_text(row.get("native_dropzone_pdb")))),
        "native_file_present": _bool_int(_is_file(row.get("native_dropzone_pdb", ""))),
        "provenance_template_present": _bool_int(_is_file(row.get("provenance_template_csv", ""))),
        "manifest_stub_present": _bool_int(_is_file(row.get("manifest_stub_csv", ""))),
        "packet_coordinate_copy_count": packet_coordinate_copy_count,
        "competitive_proof_eligible": _text(row.get("competitive_proof_eligible")),
        "author_serialized": _text(row.get("author_serialized")),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    packet_payload = _read_json(args.operator_packet_json)
    packet_summary = _summary(packet_payload)
    packet_status = _text(packet_summary.get("operator_packet_status"))
    global_blockers: list[str] = []
    if packet_status not in READY_OPERATOR_PACKET_STATUSES:
        global_blockers.append("operator_packet_status_not_open_or_ready")
    rows = [_audit_row(row, global_blockers) for row in _rows(packet_payload)]
    blocked = [row for row in rows if row["audit_status"] != "pass"]
    out_dir = _text(packet_summary.get("out_dir"))
    out_dir_coordinate_copy_count = _coordinate_copy_count(out_dir)
    if out_dir_coordinate_copy_count:
        blocked = blocked or rows
    first = rows[0] if rows else {}
    status = "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
    if not rows:
        status = "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_blocked_no_targets"
    elif blocked or out_dir_coordinate_copy_count:
        status = "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_blocked"
    summary = {
        "packet_type": "casp17_competitive_floor_native_provenance_operator_packet_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "operator_packet_completion_audit_status": status,
        "operator_packet_json": _artifact(args.operator_packet_json),
        "operator_packet_status": packet_status,
        "out_dir": _artifact(out_dir),
        "html_audit_path": _artifact(args.out_html),
        "target_count": len(rows),
        "target_pass_count": sum(1 for row in rows if row["audit_status"] == "pass"),
        "target_blocked_count": len(blocked),
        "packet_folder_present_count": sum(_int(row.get("packet_folder_present")) for row in rows),
        "packet_readme_present_count": sum(_int(row.get("packet_readme_present")) for row in rows),
        "packet_manifest_present_count": sum(_int(row.get("packet_manifest_present")) for row in rows),
        "actions_csv_present_count": sum(_int(row.get("actions_csv_present")) for row in rows),
        "native_candidates_csv_present_count": sum(_int(row.get("native_candidates_csv_present")) for row in rows),
        "action_expected_row_count": sum(_int(row.get("action_expected_row_count")) for row in rows),
        "action_csv_row_count": sum(_int(row.get("action_csv_row_count")) for row in rows),
        "action_csv_mismatch_count": sum(_int(row.get("action_row_mismatch")) for row in rows),
        "native_candidate_expected_row_count": sum(
            _int(row.get("native_candidate_expected_row_count")) for row in rows
        ),
        "native_candidate_csv_row_count": sum(_int(row.get("native_candidate_csv_row_count")) for row in rows),
        "native_candidate_csv_mismatch_count": sum(_int(row.get("native_candidate_row_mismatch")) for row in rows),
        "native_action_csv_count": sum(_int(row.get("native_action_csv_count")) for row in rows),
        "evidence_action_csv_count": sum(_int(row.get("evidence_action_csv_count")) for row in rows),
        "provenance_action_csv_count": sum(_int(row.get("provenance_action_csv_count")) for row in rows),
        "manifest_action_csv_count": sum(_int(row.get("manifest_action_csv_count")) for row in rows),
        "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in rows),
        "metric_runway_present_count": sum(_int(row.get("metric_runway_present")) for row in rows),
        "workorder_folder_present_count": sum(_int(row.get("workorder_folder_present")) for row in rows),
        "workorder_readme_present_count": sum(_int(row.get("workorder_readme_present")) for row in rows),
        "prediction_present_count": sum(_int(row.get("prediction_present")) for row in rows),
        "ts_prediction_present_count": sum(_int(row.get("ts_prediction_present")) for row in rows),
        "native_dropzone_path_present_count": sum(_int(row.get("native_dropzone_path_present")) for row in rows),
        "native_file_present_count": sum(_int(row.get("native_file_present")) for row in rows),
        "provenance_template_present_count": sum(_int(row.get("provenance_template_present")) for row in rows),
        "manifest_stub_present_count": sum(_int(row.get("manifest_stub_present")) for row in rows),
        "packet_coordinate_copy_count": sum(_int(row.get("packet_coordinate_copy_count")) for row in rows),
        "out_dir_coordinate_copy_count": out_dir_coordinate_copy_count,
        "competitive_proof_eligible_count": sum(
            1 for row in rows if _text(row.get("competitive_proof_eligible")).lower() == "true"
        ),
        "author_serialized_count": sum(
            1 for row in rows if _text(row.get("author_serialized")).lower() == "true"
        ),
        "first_target_id": _text(first.get("target_id")),
        "first_blocked_target_id": _text(blocked[0].get("target_id")) if blocked else "",
        "next_action": "Use this green packet-file audit before filling native PDB and no-leak provenance values.",
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
        "# CASP17 Competitive Floor Native/Provenance Operator Packet Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['operator_packet_completion_audit_status']}`",
        f"- targets pass/blocked/total: `{summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- packet files folder/readme/manifest/actions/native-candidates: `{summary['packet_folder_present_count']}/{summary['packet_readme_present_count']}/{summary['packet_manifest_present_count']}/{summary['actions_csv_present_count']}/{summary['native_candidates_csv_present_count']}`",
        f"- action rows expected/csv/mismatch: `{summary['action_expected_row_count']}/{summary['action_csv_row_count']}/{summary['action_csv_mismatch_count']}`",
        f"- native candidates expected/csv/mismatch: `{summary['native_candidate_expected_row_count']}/{summary['native_candidate_csv_row_count']}/{summary['native_candidate_csv_mismatch_count']}`",
        f"- lanes native/evidence/provenance/manifest: `{summary['native_action_csv_count']}/{summary['evidence_action_csv_count']}/{summary['provenance_action_csv_count']}/{summary['manifest_action_csv_count']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_dropzone_path_present_count']}/{summary['native_file_present_count']}/{summary['provenance_template_present_count']}/{summary['manifest_stub_present_count']}/{summary['metric_runway_present_count']}/{summary['workorder_folder_present_count']}`",
        f"- coordinate copies target/out-dir: `{summary['packet_coordinate_copy_count']}/{summary['out_dir_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | packet | action rows | native candidates | native file | blockers |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['audit_status']}` | `{row['packet_folder']}` | "
            f"`{row['action_csv_row_count']}/{row['action_expected_row_count']}` | "
            f"`{row['native_candidate_csv_row_count']}/{row['native_candidate_expected_row_count']}` | "
            f"`{row['native_file_present']}` | `{row['blockers'] or '-'}` |"
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
            f"<td>{html.escape(row['audit_status'])}</td>"
            f"<td>{row['action_csv_row_count']}/{row['action_expected_row_count']}</td>"
            f"<td>{row['native_candidate_csv_row_count']}/{row['native_candidate_expected_row_count']}</td>"
            f"<td>{html.escape(row['blockers'])}</td>"
            "</tr>"
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 Native Provenance Operator Packet Completion Audit</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 Native Provenance Operator Packet Completion Audit</h1>",
            f"<p>Status: <code>{html.escape(summary['operator_packet_completion_audit_status'])}</code></p>",
            f"<p>Targets pass/blocked/total: {summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['target_count']}.</p>",
            "<table><thead><tr><th>target</th><th>name</th><th>status</th><th>actions</th><th>native candidates</th><th>blockers</th></tr></thead><tbody>",
            "\n".join(body_rows),
            "</tbody></table>",
            f"<p>{html.escape(summary['claim_boundary'])}</p>",
            "</body></html>",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 native/provenance operator packet completion.")
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
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
