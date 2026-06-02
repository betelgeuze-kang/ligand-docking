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

DEFAULT_METRIC_RUNWAY_JSON = "casp17/casp17_competitive_floor_target_identity_metric_runway_current.json"
DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.json"
)
DEFAULT_WORKORDER_AUDIT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_OPERATOR_PACKET_JSON = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_NATIVE_PROVENANCE_METRIC_UNLOCK_BRIDGE.md"
DEFAULT_OUT_HTML = "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.html"

CLAIM_BOUNDARY = (
    "CASP17 competitive-floor native/provenance metric unlock bridge only. It joins the target metric "
    "runway, native/provenance operator packet completion audit, and clearance workorder audit to show "
    "which operator values unlock native metric execution. It does not fetch native structures, fill "
    "operator values, clear no-leak provenance, compute native accuracy, serialize a CASP author code, "
    "or submit to CASP."
)

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "bridge_status",
    "packet_completion_status",
    "packet_audit_status",
    "workorder_audit_status",
    "metric_runway_status",
    "metric_requirement_count",
    "required_metric_names",
    "prediction_present",
    "ts_prediction_present",
    "native_dropzone_path_present",
    "native_file_present",
    "provenance_template_present",
    "manifest_stub_present",
    "metric_runway_present",
    "workorder_present",
    "packet_action_count",
    "packet_native_action_count",
    "packet_evidence_action_count",
    "packet_provenance_action_count",
    "packet_manifest_action_count",
    "native_candidate_count",
    "native_candidate_blocked_count",
    "native_candidate_no_candidate_count",
    "provenance_status",
    "evidence_ref_status",
    "identity_discovery_status",
    "operator_clearance_status",
    "manifest_stub_status",
    "native_prediction_identity_status",
    "packet_folder",
    "metric_runway_md",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "blocker_count",
    "blockers",
    "first_blocker",
    "next_action",
    "competitive_proof_eligible",
    "author_serialized",
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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in rows}


def _split_blockers(value: Any) -> list[str]:
    return [part for part in (_text(item) for item in _text(value).split(",")) if part]


def _first_present(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _needs_action(
    *,
    native_present: bool,
    evidence_status: str,
    provenance_status: str,
    identity_status: str,
    manifest_status: str,
) -> str:
    if not native_present:
        return "place operator-cleared native PDB in the native dropzone"
    if evidence_status != "verified":
        return "attach no-leak evidence reference and checksum"
    if provenance_status != "ready":
        return "complete provenance template values"
    if identity_status != "cleared":
        return "clear historical target identity and current-target leakage controls"
    if manifest_status != "ready":
        return "sync manifest stub after provenance values are complete"
    return "rerun clearance audit, promotion, and metric runway"


def _audit_row(
    target_id: str,
    metric: dict[str, Any],
    packet_audit: dict[str, Any],
    workorder_audit: dict[str, Any],
    packet: dict[str, Any],
    global_blockers: list[str],
) -> dict[str, Any]:
    blockers = global_blockers[:]
    metric_blockers = _split_blockers(metric.get("blockers"))
    workorder_blockers = _split_blockers(workorder_audit.get("blockers"))
    packet_blockers = _split_blockers(packet_audit.get("blockers"))
    blockers.extend(metric_blockers)
    blockers.extend(workorder_blockers)
    blockers.extend(f"packet_{blocker}" for blocker in packet_blockers)
    packet_status = _text(packet_audit.get("audit_status"))
    workorder_status = _text(workorder_audit.get("audit_status"))
    runway_status = _text(metric.get("runway_status"))
    evidence_status = _text(workorder_audit.get("evidence_ref_status")) or _text(metric.get("evidence_ref_status"))
    provenance_status = _text(workorder_audit.get("provenance_status")) or _text(metric.get("provenance_status"))
    identity_status = (
        _text(workorder_audit.get("identity_discovery_blocker_status"))
        or _text(metric.get("identity_discovery_status"))
    )
    manifest_status = _text(workorder_audit.get("manifest_stub_status"))
    native_present = bool(_int(packet_audit.get("native_file_present"))) or _text(metric.get("native_status")) == "present"
    if packet_status != "pass":
        blockers.append("packet_completion_audit_not_pass")
    if workorder_status != "pass":
        blockers.append("workorder_audit_not_pass")
    if runway_status != "ready_for_metric_after_native_provenance":
        blockers.append("metric_runway_not_ready")
    if not native_present:
        blockers.append("native_pdb_missing")
    if evidence_status != "verified":
        blockers.append("evidence_ref_required")
    if provenance_status != "ready":
        blockers.append("provenance_required")
    if identity_status != "cleared":
        blockers.append("identity_discovery_clearance_required")
    if manifest_status != "ready":
        blockers.append("manifest_sync_required")
    blockers = list(dict.fromkeys(blockers))
    bridge_status = "ready_for_metric_execution" if not blockers else "blocked_awaiting_native_provenance_values"
    target_name = _first_present(metric.get("target_name"), packet.get("target_name"), packet_audit.get("target_name"))
    next_action = _needs_action(
        native_present=native_present,
        evidence_status=evidence_status,
        provenance_status=provenance_status,
        identity_status=identity_status,
        manifest_status=manifest_status,
    )
    return {
        "target_id": target_id,
        "target_name": target_name,
        "bridge_status": bridge_status,
        "packet_completion_status": _text(packet_audit.get("operator_packet_status")),
        "packet_audit_status": packet_status,
        "workorder_audit_status": workorder_status,
        "metric_runway_status": runway_status,
        "metric_requirement_count": _int(metric.get("metric_requirement_count") or packet_audit.get("metric_requirement_count")),
        "required_metric_names": _text(metric.get("required_metric_names")),
        "prediction_present": _int(packet_audit.get("prediction_present")),
        "ts_prediction_present": _int(packet_audit.get("ts_prediction_present")),
        "native_dropzone_path_present": _int(packet_audit.get("native_dropzone_path_present")),
        "native_file_present": 1 if native_present else 0,
        "provenance_template_present": _int(packet_audit.get("provenance_template_present")),
        "manifest_stub_present": _int(packet_audit.get("manifest_stub_present")),
        "metric_runway_present": _int(packet_audit.get("metric_runway_present")),
        "workorder_present": _int(packet_audit.get("workorder_folder_present")),
        "packet_action_count": _int(packet_audit.get("action_csv_row_count") or packet.get("action_count")),
        "packet_native_action_count": _int(packet_audit.get("native_action_csv_count") or packet.get("native_action_count")),
        "packet_evidence_action_count": _int(
            packet_audit.get("evidence_action_csv_count") or packet.get("evidence_action_count")
        ),
        "packet_provenance_action_count": _int(
            packet_audit.get("provenance_action_csv_count") or packet.get("provenance_action_count")
        ),
        "packet_manifest_action_count": _int(
            packet_audit.get("manifest_action_csv_count") or packet.get("manifest_action_count")
        ),
        "native_candidate_count": _int(metric.get("native_candidate_count") or packet.get("native_candidate_count")),
        "native_candidate_blocked_count": _int(
            metric.get("native_candidate_blocked_count") or packet.get("native_candidate_blocked_count")
        ),
        "native_candidate_no_candidate_count": _int(
            metric.get("native_candidate_no_candidate_count") or packet.get("native_candidate_no_candidate_count")
        ),
        "provenance_status": provenance_status,
        "evidence_ref_status": evidence_status,
        "identity_discovery_status": identity_status,
        "operator_clearance_status": _text(metric.get("operator_clearance_status")),
        "manifest_stub_status": manifest_status,
        "native_prediction_identity_status": _text(workorder_audit.get("native_prediction_identity_status")),
        "packet_folder": _artifact(packet_audit.get("packet_folder") or packet.get("packet_folder", "")),
        "metric_runway_md": _artifact(metric.get("metric_runway_md", "")),
        "native_dropzone_pdb": _artifact(metric.get("native_dropzone_pdb") or packet.get("native_dropzone_pdb", "")),
        "provenance_template_csv": _artifact(
            metric.get("provenance_template_csv") or packet.get("provenance_template_csv", "")
        ),
        "manifest_stub_csv": _artifact(metric.get("manifest_stub_csv") or packet.get("manifest_stub_csv", "")),
        "blocker_count": len(blockers),
        "blockers": ",".join(blockers),
        "first_blocker": blockers[0] if blockers else "",
        "next_action": next_action,
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    metric_payload = _read_json(args.metric_runway_json)
    packet_audit_payload = _read_json(args.operator_packet_completion_audit_json)
    workorder_audit_payload = _read_json(args.workorder_audit_json)
    packet_payload = _read_json(args.operator_packet_json)
    metric_summary = _summary(metric_payload)
    packet_audit_summary = _summary(packet_audit_payload)
    workorder_audit_summary = _summary(workorder_audit_payload)
    metric_by_target = _by_target(_rows(metric_payload))
    packet_audit_by_target = _by_target(_rows(packet_audit_payload))
    workorder_audit_by_target = _by_target(_rows(workorder_audit_payload))
    packet_by_target = _by_target(_rows(packet_payload))
    target_ids = sorted(set(metric_by_target) | set(packet_audit_by_target) | set(workorder_audit_by_target) | set(packet_by_target))
    global_blockers: list[str] = []
    if _text(packet_audit_summary.get("operator_packet_completion_audit_status")) != (
        "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
    ):
        global_blockers.append("packet_completion_audit_not_pass")
    rows = [
        _audit_row(
            target_id,
            metric_by_target.get(target_id, {}),
            packet_audit_by_target.get(target_id, {}),
            workorder_audit_by_target.get(target_id, {}),
            packet_by_target.get(target_id, {}),
            global_blockers,
        )
        for target_id in target_ids
    ]
    blocked = [row for row in rows if row["bridge_status"] != "ready_for_metric_execution"]
    first = rows[0] if rows else {}
    first_blocked = blocked[0] if blocked else {}
    status = "casp17_competitive_floor_native_provenance_metric_unlock_bridge_ready"
    if not rows:
        status = "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_no_targets"
    elif blocked:
        status = "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values"
    summary = {
        "packet_type": "casp17_competitive_floor_native_provenance_metric_unlock_bridge",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "metric_unlock_bridge_status": status,
        "metric_runway_json": _artifact(args.metric_runway_json),
        "metric_runway_status": _text(metric_summary.get("metric_runway_status")),
        "operator_packet_completion_audit_json": _artifact(args.operator_packet_completion_audit_json),
        "operator_packet_completion_audit_status": _text(
            packet_audit_summary.get("operator_packet_completion_audit_status")
        ),
        "workorder_audit_json": _artifact(args.workorder_audit_json),
        "workorder_audit_status": _text(workorder_audit_summary.get("clearance_workorder_audit_status")),
        "operator_packet_json": _artifact(args.operator_packet_json),
        "html_bridge_path": _artifact(args.out_html),
        "target_count": len(rows),
        "target_ready_count": len(rows) - len(blocked),
        "target_blocked_count": len(blocked),
        "packet_pass_count": sum(1 for row in rows if row["packet_audit_status"] == "pass"),
        "workorder_audit_pass_count": sum(1 for row in rows if row["workorder_audit_status"] == "pass"),
        "metric_runway_ready_count": sum(
            1 for row in rows if row["metric_runway_status"] == "ready_for_metric_after_native_provenance"
        ),
        "metric_requirement_count": sum(_int(row.get("metric_requirement_count")) for row in rows),
        "prediction_present_count": sum(_int(row.get("prediction_present")) for row in rows),
        "ts_prediction_present_count": sum(_int(row.get("ts_prediction_present")) for row in rows),
        "native_dropzone_path_present_count": sum(_int(row.get("native_dropzone_path_present")) for row in rows),
        "native_file_present_count": sum(_int(row.get("native_file_present")) for row in rows),
        "provenance_template_present_count": sum(_int(row.get("provenance_template_present")) for row in rows),
        "manifest_stub_present_count": sum(_int(row.get("manifest_stub_present")) for row in rows),
        "metric_runway_present_count": sum(_int(row.get("metric_runway_present")) for row in rows),
        "workorder_present_count": sum(_int(row.get("workorder_present")) for row in rows),
        "packet_action_count": sum(_int(row.get("packet_action_count")) for row in rows),
        "packet_native_action_count": sum(_int(row.get("packet_native_action_count")) for row in rows),
        "packet_evidence_action_count": sum(_int(row.get("packet_evidence_action_count")) for row in rows),
        "packet_provenance_action_count": sum(_int(row.get("packet_provenance_action_count")) for row in rows),
        "packet_manifest_action_count": sum(_int(row.get("packet_manifest_action_count")) for row in rows),
        "native_candidate_count": sum(_int(row.get("native_candidate_count")) for row in rows),
        "native_candidate_blocked_count": sum(_int(row.get("native_candidate_blocked_count")) for row in rows),
        "native_candidate_no_candidate_count": sum(_int(row.get("native_candidate_no_candidate_count")) for row in rows),
        "provenance_ready_count": sum(1 for row in rows if row["provenance_status"] == "ready"),
        "evidence_ref_verified_count": sum(1 for row in rows if row["evidence_ref_status"] == "verified"),
        "identity_discovery_cleared_count": sum(1 for row in rows if row["identity_discovery_status"] == "cleared"),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_target_id": _text(first.get("target_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "next_action": "Fill native PDB, no-leak evidence, provenance, and manifest values, then rerun clearance audits.",
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
        "# CASP17 Competitive Floor Native/Provenance Metric Unlock Bridge",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['metric_unlock_bridge_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- packet/workorder/runway ready: `{summary['packet_pass_count']}/{summary['workorder_audit_pass_count']}/{summary['metric_runway_ready_count']}`",
        f"- metric requirements: `{summary['metric_requirement_count']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance-template/manifest/runway/workorder: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_dropzone_path_present_count']}/{summary['native_file_present_count']}/{summary['provenance_template_present_count']}/{summary['manifest_stub_present_count']}/{summary['metric_runway_present_count']}/{summary['workorder_present_count']}`",
        f"- packet actions native/evidence/provenance/manifest/total: `{summary['packet_native_action_count']}/{summary['packet_evidence_action_count']}/{summary['packet_provenance_action_count']}/{summary['packet_manifest_action_count']}/{summary['packet_action_count']}`",
        f"- native candidates blocked/no-candidate/total: `{summary['native_candidate_blocked_count']}/{summary['native_candidate_no_candidate_count']}/{summary['native_candidate_count']}`",
        f"- provenance/evidence/identity cleared: `{summary['provenance_ready_count']}/{summary['evidence_ref_verified_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | metrics | native | provenance | evidence | identity | next action |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['bridge_status']}` | `{row['metric_requirement_count']}` | "
            f"`{row['native_file_present']}` | `{row['provenance_status'] or '-'}` | "
            f"`{row['evidence_ref_status'] or '-'}` | `{row['identity_discovery_status'] or '-'}` | "
            f"{row['next_action']} |"
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
            f"<td>{html.escape(row['bridge_status'])}</td>"
            f"<td>{row['metric_requirement_count']}</td>"
            f"<td>{row['native_file_present']}</td>"
            f"<td>{html.escape(row['next_action'])}</td>"
            "</tr>"
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 Native Provenance Metric Unlock Bridge</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 Native Provenance Metric Unlock Bridge</h1>",
            f"<p>Status: <code>{html.escape(summary['metric_unlock_bridge_status'])}</code></p>",
            f"<p>Targets ready/blocked/total: {summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']}.</p>",
            "<table><thead><tr><th>target</th><th>name</th><th>status</th><th>metrics</th><th>native</th><th>next action</th></tr></thead><tbody>",
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
    parser = argparse.ArgumentParser(description="Build CASP17 native/provenance metric unlock bridge.")
    parser.add_argument("--metric-runway-json", default=DEFAULT_METRIC_RUNWAY_JSON)
    parser.add_argument(
        "--operator-packet-completion-audit-json",
        default=DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument("--workorder-audit-json", default=DEFAULT_WORKORDER_AUDIT_JSON)
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
