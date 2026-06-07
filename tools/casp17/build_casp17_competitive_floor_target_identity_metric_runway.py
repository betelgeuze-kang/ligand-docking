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

DEFAULT_CLEARANCE_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_CLEARANCE_WORKORDER_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
)
DEFAULT_NATIVE_CANDIDATE_PACKET_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_metric_runway"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_metric_runway_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_metric_runway_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_TARGET_IDENTITY_METRIC_RUNWAY.md"
DEFAULT_OUT_HTML = "casp17/casp17_competitive_floor_target_identity_metric_runway_current.html"

CLAIM_BOUNDARY = (
    "CASP17 competitive-floor target identity metric runway only. It maps target-identity clearance "
    "workorders to review-only metric requirements and native/provenance blockers. It does not fetch "
    "native structures, clear no-leak provenance, compute native accuracy, serialize a CASP author code, "
    "promote identities, mutate intake files, or submit to CASP."
)
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
COMPLEX_METRICS = ["GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity", "DockQ", "ICS", "IPS"]
MONOMER_METRICS = ["GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity"]

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "scope",
    "runway_status",
    "metric_family",
    "metric_requirement_count",
    "required_metric_names",
    "runway_folder",
    "runway_manifest",
    "metric_requirements_csv",
    "metric_runway_md",
    "workorder_folder",
    "readme_path",
    "prediction_pdb",
    "ts_prediction_pdb",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "native_candidate_count",
    "native_candidate_blocked_count",
    "native_candidate_review_count",
    "native_candidate_no_candidate_count",
    "first_native_candidate_pdb_id",
    "first_native_candidate_status",
    "first_native_candidate_blockers",
    "prediction_status",
    "native_status",
    "provenance_status",
    "evidence_ref_status",
    "identity_discovery_status",
    "operator_clearance_status",
    "blockers",
    "next_action",
    "competitive_proof_eligible",
    "author_serialized",
    "claim_boundary",
    "submission_policy",
]

METRIC_ROW_COLUMNS = [
    "metric_name",
    "metric_family",
    "metric_input_contract",
    "expected_input_prediction_pdb",
    "expected_input_native_pdb",
    "expected_output_status",
    "competitive_proof_eligible",
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


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _audit_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in _rows(payload)}


def _native_candidates_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _rows(payload):
        grouped.setdefault(_text(row.get("target_id")), []).append(row)
    return grouped


def _metric_names(scope: str) -> list[str]:
    return COMPLEX_METRICS[:] if _text(scope).lower() == "complex" else MONOMER_METRICS[:]


def _metric_input_contract(metric_name: str, metric_family: str) -> str:
    if metric_name in {"DockQ", "ICS", "IPS"}:
        return "prediction/native interface chain mapping"
    if metric_name == "MolProbity":
        return "prediction coordinate geometry validation"
    if metric_name == "lDDT":
        return "prediction/native residue mapping"
    return "prediction/native chain mapping"


def _runway_row(
    workorder: dict[str, Any],
    audit: dict[str, Any],
    native_candidates: list[dict[str, Any]],
    out_dir: Path,
) -> dict[str, Any]:
    target_id = _text(workorder.get("target_id"))
    target_name = _text(workorder.get("target_name"))
    scope = _text(workorder.get("scope")) or "monomer"
    metric_family = "protein_complex" if scope == "complex" else "monomer_domain"
    metrics = _metric_names(scope)
    runway_folder = out_dir / f"{target_id}_{_safe_component(target_name)}"
    native_blocked = [row for row in native_candidates if _text(row.get("candidate_status")).startswith("blocked")]
    native_review = [row for row in native_candidates if "review" in _text(row.get("candidate_status"))]
    native_missing = [row for row in native_candidates if _text(row.get("candidate_status")) == "no_rcsb_candidate_found"]
    first_candidate = native_candidates[0] if native_candidates else {}
    blockers: list[str] = []
    if not _is_file(workorder.get("prediction_pdb", "")):
        blockers.append("prediction_pdb_missing")
    if not _is_file(workorder.get("ts_prediction_pdb", "")):
        blockers.append("ts_prediction_pdb_missing")
    if not _is_file(workorder.get("native_dropzone_pdb", "")):
        blockers.append("native_pdb_missing")
    if not _is_file(workorder.get("provenance_template_csv", "")):
        blockers.append("provenance_template_missing")
    if not _is_file(workorder.get("manifest_stub_csv", "")):
        blockers.append("manifest_stub_missing")
    if not _is_dir(workorder.get("workorder_folder", "")):
        blockers.append("workorder_folder_missing")
    if _text(audit.get("audit_status")) != "pass":
        blockers.extend(
            blocker
            for blocker in _text(audit.get("blockers")).split(",")
            if blocker
            and blocker
            in {
                "native_pdb_missing",
                "identity_discovery_no_leak_clearance_required",
                "operator_required",
                "evidence_ref_required",
                "leakage_clearance_required",
                "operator_clearance_required",
            }
        )
    if not native_candidates:
        blockers.append("native_candidate_packet_missing")
    if native_blocked:
        blockers.append("native_candidate_blocked_review_required")
    if native_missing and len(native_missing) == len(native_candidates):
        blockers.append("native_candidate_missing")
    blockers = list(dict.fromkeys(blockers))
    status = "ready_for_metric_after_native_provenance" if not blockers else "blocked_awaiting_native_provenance"
    return {
        "target_id": target_id,
        "target_name": target_name,
        "scope": scope,
        "runway_status": status,
        "metric_family": metric_family,
        "metric_requirement_count": len(metrics),
        "required_metric_names": "|".join(metrics),
        "runway_folder": _artifact(runway_folder),
        "runway_manifest": _artifact(runway_folder / "metric_runway_manifest.json"),
        "metric_requirements_csv": _artifact(runway_folder / "metric_requirements.csv"),
        "metric_runway_md": _artifact(runway_folder / "METRIC_RUNWAY.md"),
        "workorder_folder": _artifact(workorder.get("workorder_folder", "")),
        "readme_path": _artifact(workorder.get("readme_path", "")),
        "prediction_pdb": _artifact(workorder.get("prediction_pdb", "")),
        "ts_prediction_pdb": _artifact(workorder.get("ts_prediction_pdb", "")),
        "native_dropzone_pdb": _artifact(workorder.get("native_dropzone_pdb", "")),
        "provenance_template_csv": _artifact(workorder.get("provenance_template_csv", "")),
        "manifest_stub_csv": _artifact(workorder.get("manifest_stub_csv", "")),
        "native_candidate_count": len(native_candidates),
        "native_candidate_blocked_count": len(native_blocked),
        "native_candidate_review_count": len(native_review),
        "native_candidate_no_candidate_count": len(native_missing),
        "first_native_candidate_pdb_id": _text(first_candidate.get("pdb_id")),
        "first_native_candidate_status": _text(first_candidate.get("candidate_status")),
        "first_native_candidate_blockers": _text(first_candidate.get("blockers")),
        "prediction_status": "present" if _is_file(workorder.get("prediction_pdb", "")) else "missing",
        "native_status": "present" if _is_file(workorder.get("native_dropzone_pdb", "")) else "missing",
        "provenance_status": _text(audit.get("provenance_status")) or "unknown",
        "evidence_ref_status": _text(audit.get("evidence_ref_status")) or "unknown",
        "identity_discovery_status": _text(audit.get("identity_discovery_blocker_status")) or "unknown",
        "operator_clearance_status": "required" if "operator_clearance_required" in blockers else "unknown",
        "blockers": ",".join(blockers),
        "next_action": (
            "place cleared native PDB, complete no-leak provenance, then run review-only metric calculations"
            if blockers
            else "run review-only metric calculations after final operator approval"
        ),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.clearance_workorder_json)
    workorder_summary = _summary(workorder_payload)
    audit_payload = _read_json(args.clearance_workorder_audit_json)
    audit_summary = _summary(audit_payload)
    native_candidate_payload = _read_json(args.native_candidate_packet_json)
    native_candidate_summary = _summary(native_candidate_payload)
    audit_by_target = _audit_by_target(audit_payload)
    native_by_target = _native_candidates_by_target(native_candidate_payload)
    out_dir = _resolve(args.out_dir)
    rows = [
        _runway_row(
            workorder,
            audit_by_target.get(_text(workorder.get("target_id")), {}),
            native_by_target.get(_text(workorder.get("target_id")), []),
            out_dir,
        )
        for workorder in _rows(workorder_payload)
    ]
    rows = sorted(rows, key=lambda row: row["target_id"])
    blocked = [row for row in rows if row["runway_status"] != "ready_for_metric_after_native_provenance"]
    first = rows[0] if rows else {}
    status = "casp17_competitive_floor_target_identity_metric_runway_ready"
    if not rows:
        status = "casp17_competitive_floor_target_identity_metric_runway_blocked_no_workorders"
    elif blocked:
        status = "casp17_competitive_floor_target_identity_metric_runway_blocked_awaiting_native_provenance"
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_metric_runway",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "metric_runway_status": status,
        "clearance_workorder_json": _artifact(args.clearance_workorder_json),
        "clearance_workorder_status": _text(workorder_summary.get("clearance_workorder_status")),
        "clearance_workorder_audit_json": _artifact(args.clearance_workorder_audit_json),
        "clearance_workorder_audit_status": _text(audit_summary.get("clearance_workorder_audit_status")),
        "native_candidate_packet_json": _artifact(args.native_candidate_packet_json),
        "native_candidate_packet_status": _text(native_candidate_summary.get("native_candidate_packet_status")),
        "out_dir": _artifact(args.out_dir),
        "html_runway_path": _artifact(args.out_html),
        "target_count": len(rows),
        "target_ready_count": len(rows) - len(blocked),
        "target_blocked_count": len(blocked),
        "complex_target_count": sum(1 for row in rows if row["scope"] == "complex"),
        "monomer_target_count": sum(1 for row in rows if row["scope"] != "complex"),
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
        "first_blocked_target_id": _text(blocked[0].get("target_id")) if blocked else "",
        "first_blocker": _text(blocked[0].get("blockers")).split(",")[0] if blocked else "",
        "next_action": "Fill native/provenance workorders, then use this runway to run complex metric calculations for competitive-floor identity targets.",
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
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


def _metric_rows(row: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "metric_name": metric,
            "metric_family": row["metric_family"],
            "metric_input_contract": _metric_input_contract(metric, row["metric_family"]),
            "expected_input_prediction_pdb": row["prediction_pdb"],
            "expected_input_native_pdb": row["native_dropzone_pdb"],
            "expected_output_status": "not_computed_awaiting_native_provenance",
            "competitive_proof_eligible": "false",
            "claim_boundary": CLAIM_BOUNDARY,
        }
        for metric in row["required_metric_names"].split("|")
        if metric
    ]


def _write_metric_csv(path_like: str | Path, rows: list[dict[str, str]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_runway_files(payload: dict[str, Any]) -> None:
    for row in payload["rows"]:
        folder = _resolve(row["runway_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        metric_rows = _metric_rows(row)
        _write_metric_csv(row["metric_requirements_csv"], metric_rows)
        _write_json(row["runway_manifest"], {"summary": row, "metric_rows": metric_rows})
        lines = [
            f"# {row['target_id']} Metric Runway",
            "",
            f"- target: `{row['target_name']}`",
            f"- status: `{row['runway_status']}`",
            f"- metric family: `{row['metric_family']}`",
            f"- metrics: `{row['required_metric_names']}`",
            f"- prediction: `{row['prediction_pdb']}`",
            f"- TS prediction: `{row['ts_prediction_pdb']}`",
            f"- native dropzone: `{row['native_dropzone_pdb']}`",
            f"- provenance template: `{row['provenance_template_csv']}`",
            f"- manifest stub: `{row['manifest_stub_csv']}`",
            f"- native candidates blocked/review/no-candidate/total: `{row['native_candidate_blocked_count']}/{row['native_candidate_review_count']}/{row['native_candidate_no_candidate_count']}/{row['native_candidate_count']}`",
            f"- competitive proof eligible: `{row['competitive_proof_eligible']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            "",
            "## Metric Requirements",
            "",
            "| metric | input contract | output status |",
            "| --- | --- | --- |",
        ]
        for metric_row in metric_rows:
            lines.append(
                f"| `{metric_row['metric_name']}` | `{metric_row['metric_input_contract']}` | "
                f"`{metric_row['expected_output_status']}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        _resolve(row["metric_runway_md"]).write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Target Identity Metric Runway",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['metric_runway_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- target family complex/monomer: `{summary['complex_target_count']}/{summary['monomer_target_count']}`",
        f"- metric requirements: `{summary['metric_requirement_count']}`",
        f"- prediction/native/provenance/evidence-ref ready: `{summary['prediction_present_count']}/{summary['native_present_count']}/{summary['provenance_ready_count']}/{summary['evidence_ref_ready_count']}`",
        f"- native candidates blocked/no-candidate/total: `{summary['native_candidate_blocked_count']}/{summary['native_candidate_no_candidate_count']}/{summary['native_candidate_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- html runway: `{summary['html_runway_path']}`",
        f"- first: `{summary['first_target_id'] or '-'}` blocked `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | metrics | prediction | native | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['runway_status']}` | `{row['metric_requirement_count']}` | "
            f"`{row['prediction_status']}` | `{row['native_status']}` | `{row['blockers'] or '-'}` |"
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
            f"<td>{html.escape(row['runway_status'])}</td>"
            f"<td>{row['metric_requirement_count']}</td>"
            f"<td>{html.escape(row['prediction_status'])}</td>"
            f"<td>{html.escape(row['native_status'])}</td>"
            f"<td>{html.escape(row['blockers'] or '-')}</td>"
            "</tr>"
        )
    path = _resolve(path_like)
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>CASP17 Competitive Floor Target Identity Metric Runway</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:6px;}th{background:#f5f5f5;text-align:left;}code{font-size:12px;}</style></head>",
            "<body>",
            "<h1>CASP17 Competitive Floor Target Identity Metric Runway</h1>",
            f"<p>Status: <code>{html.escape(summary['metric_runway_status'])}</code></p>",
            f"<p>Targets: {summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']} ready/blocked/total.</p>",
            "<table><thead><tr><th>target</th><th>name</th><th>status</th><th>metrics</th><th>prediction</th><th>native</th><th>blockers</th></tr></thead><tbody>",
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
    _write_runway_files(payload)
    _write_md(args.out_md, payload)
    _write_html(args.out_html, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 competitive-floor target identity metric runway.")
    parser.add_argument("--clearance-workorder-json", default=DEFAULT_CLEARANCE_WORKORDER_JSON)
    parser.add_argument("--clearance-workorder-audit-json", default=DEFAULT_CLEARANCE_WORKORDER_AUDIT_JSON)
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
