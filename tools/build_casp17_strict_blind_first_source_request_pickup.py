#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_SOURCE_ROUTE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_REPAIR_FEASIBILITY_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_current.json"
)
DEFAULT_EVIDENCE_PACKET_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_packet_current.json"
DEFAULT_PICKUP_ROOT = "casp17/strict_blind_first_source_request_pickup"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_source_request_pickup_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_source_request_pickup_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_SOURCE_REQUEST_PICKUP.md"

ROW_COLUMNS = [
    "action_id",
    "action_status",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "action_kind",
    "resolution_path",
    "current_prediction_pdb",
    "current_prediction_created_at",
    "native_release_date",
    "current_prediction_before_native",
    "required_operator_input",
    "pickup_folder",
    "operator_decision_template_csv",
    "required_files_manifest_csv",
    "blocker",
    "next_action",
]
DECISION_TEMPLATE_COLUMNS = [
    "field_key",
    "operator_value",
    "operator_evidence_ref",
    "required_format",
    "notes",
]
FILE_MANIFEST_COLUMNS = [
    "file_key",
    "required_path_or_ref",
    "file_status",
    "required_format",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-source-request pickup only. It materializes the first source "
    "request into an operator decision packet for pre-native prediction sourcing or candidate replacement. "
    "It does not create prediction/native files, approve provenance, copy files into source manifests, "
    "compute CASP metrics, push remotes, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in ["source_request_packet_json", "source_route_json", "repair_feasibility_json", "evidence_packet_json"]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _first_request(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    first_id = _text(summary.get("first_request_id"))
    if first_id:
        for row in rows:
            if _text(row.get("request_id")) == first_id:
                return row
    open_rows = [row for row in rows if _text(row.get("request_status")) != "source_request_not_needed"]
    return open_rows[0] if open_rows else (rows[0] if rows else {})


def _date_before(left: str, right: str) -> str:
    left_text = _text(left)
    right_text = _text(right)
    if not left_text or not right_text:
        return ""
    return "True" if left_text < right_text else "False"


def _pickup_folder(root: str | Path, request: dict[str, Any]) -> Path:
    request_id = _text(request.get("request_id")) or "source_request"
    target = _text(request.get("candidate_target_id")) or "target"
    return _resolve(root) / f"{_slug(request_id)}_{_slug(target)}"


def _decision_template_rows(request: dict[str, Any], existing_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    existing = {_text(row.get("field_key")): row for row in existing_rows if _text(row.get("field_key"))}
    native_release_date = _text(request.get("native_release_date")) or "UNKNOWN"
    fields = [
        (
            "resolution_path",
            "acquire_pre_native_prediction_source|replace_candidate|defer_current_slot",
            "Choose the operator-approved route for this first strict-blind source request.",
        ),
        ("source_id", "internal source id; not official_archive/casp_official/massivefold_external", "Internal pre-native source identifier."),
        ("prediction_pdb", "local pre-native prediction PDB path with ATOM/HETATM records", "Verified pre-native prediction file."),
        ("prediction_created_at", "YYYY-MM-DD before native_release_date", f"Must be before {native_release_date}."),
        ("native_release_date", "YYYY-MM-DD authoritative native release date", "Copy from authoritative native source."),
        ("creation_evidence_ref", "artifact path or URI", "Independent timestamp evidence for the prediction artifact."),
        ("no_leak_evidence_ref", "artifact path or URI", "No-leak provenance evidence."),
        ("operator_clearance", "approved/clear/cleared/true/yes/operator_clear/operator_approved", "Operator signoff after evidence review."),
    ]
    rows = []
    for field_key, required_format, notes in fields:
        prior = existing.get(field_key, {})
        rows.append(
            {
                "field_key": field_key,
                "operator_value": _text(prior.get("operator_value")),
                "operator_evidence_ref": _text(prior.get("operator_evidence_ref")),
                "required_format": _text(prior.get("required_format")) or required_format,
                "notes": _text(prior.get("notes")) or notes,
            }
        )
    return rows


def _file_manifest_rows(request: dict[str, Any], evidence_summary: dict[str, Any]) -> list[dict[str, Any]]:
    dropzone = _text(evidence_summary.get("prediction_dropzone"))
    packet_folder = _text(evidence_summary.get("packet_folder"))
    return [
        {
            "file_key": "prediction_pdb",
            "required_path_or_ref": "",
            "file_status": "awaiting_operator_file",
            "required_format": "local pre-native prediction PDB with ATOM/HETATM records",
            "notes": "Do not use official archive or other-team model as internal proof.",
        },
        {
            "file_key": "prediction_pdb_dropzone",
            "required_path_or_ref": dropzone,
            "file_status": "awaiting_operator_file",
            "required_format": "copy of verified prediction_pdb after review",
            "notes": "Destination used later by the internal source apply plan.",
        },
        {
            "file_key": "creation_evidence_ref",
            "required_path_or_ref": f"{packet_folder}/field_evidence/creation_evidence_ref.md" if packet_folder else "",
            "file_status": "awaiting_operator_evidence",
            "required_format": "timestamp evidence created before native release",
            "notes": f"Current candidate prediction date is {_text(request.get('prediction_created_at')) or '-'}; native date is {_text(request.get('native_release_date')) or '-'}.",
        },
        {
            "file_key": "no_leak_evidence_ref",
            "required_path_or_ref": f"{packet_folder}/field_evidence/no_leak_evidence_ref.md" if packet_folder else "",
            "file_status": "awaiting_operator_evidence",
            "required_format": "no native/template/other-team leakage declaration with evidence",
            "notes": "Needed before any winner-normalized competitive proof claim.",
        },
    ]


def _build_rows(
    args: argparse.Namespace,
    request: dict[str, Any],
    source_route_summary: dict[str, Any],
    feasibility_summary: dict[str, Any],
    evidence_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    folder = _pickup_folder(args.pickup_root, request)
    decision_template = folder / "operator_decision_template.csv"
    file_manifest = folder / "required_files_manifest.csv"
    before_native = _date_before(request.get("prediction_created_at", ""), request.get("native_release_date", ""))
    common = {
        "request_id": _text(request.get("request_id")),
        "candidate_target_id": _text(request.get("candidate_target_id")),
        "candidate_scope": _text(request.get("candidate_scope")),
        "current_prediction_pdb": _text(request.get("current_prediction_pdb")),
        "current_prediction_created_at": _text(request.get("prediction_created_at")),
        "native_release_date": _text(request.get("native_release_date")),
        "current_prediction_before_native": before_native,
        "pickup_folder": _artifact(folder),
        "operator_decision_template_csv": _artifact(decision_template),
        "required_files_manifest_csv": _artifact(file_manifest),
    }
    return [
        {
            **common,
            "action_id": "first_source_pickup_001",
            "action_status": "operator_input_required",
            "action_kind": "acquire_pre_native_prediction_source",
            "resolution_path": "acquire_pre_native_prediction_source",
            "required_operator_input": "pre-native internal prediction PDB, source id, timestamp evidence, and no-leak provenance",
            "blocker": _text(request.get("first_blocker")) or "prediction_not_before_native",
            "next_action": _text(request.get("next_action"))
            or "attach pre-native prediction source evidence to the decision template",
        },
        {
            **common,
            "action_id": "first_source_pickup_002",
            "action_status": "blocked_no_pre_native_in_scope_candidate",
            "action_kind": "replace_with_in_scope_monomer_candidate",
            "resolution_path": "replace_candidate",
            "required_operator_input": "strict-blind monomer candidate whose prediction predates native release",
            "blocker": "no_allowed_first_slot_candidate"
            if _int(source_route_summary.get("allowed_for_first_slot_count")) == 0
            else "",
            "next_action": "source a different in-scope monomer candidate only if it has pre-native prediction provenance",
        },
        {
            **common,
            "action_id": "first_source_pickup_003",
            "action_status": "context_only_not_first_slot_resolution",
            "action_kind": "route_complex_candidates_to_complex_or_ligand_lane",
            "resolution_path": "defer_current_slot",
            "required_operator_input": "none for monomer first slot; keep complex candidates in their category lane",
            "blocker": "complex_candidates_out_of_scope_for_required_monomer_slot"
            if _int(source_route_summary.get("out_of_scope_route_count")) else "",
            "next_action": "keep complex/ligand candidates out of this monomer slot until their own strict-blind lane is active",
        },
    ]


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_first_source_request_missing"
    if rows[0]["current_prediction_before_native"] == "True":
        return "first_source_request_candidate_ready_for_evidence_review"
    return "first_source_request_requires_pre_native_source"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    request_payload = _read_json(args.source_request_packet_json)
    route_payload = _read_json(args.source_route_json)
    feasibility_payload = _read_json(args.repair_feasibility_json)
    evidence_payload = _read_json(args.evidence_packet_json)
    request_summary = _summary(request_payload)
    route_summary = _summary(route_payload)
    feasibility_summary = _summary(feasibility_payload)
    evidence_summary = _summary(evidence_payload)
    input_blockers = _input_blockers(args)
    request = {} if input_blockers else _first_request(_rows(request_payload), request_summary)
    rows = [] if input_blockers else _build_rows(args, request, route_summary, feasibility_summary, evidence_summary)
    blocked_count = sum(1 for row in rows if row["action_status"] != "operator_ready")
    first_action = rows[0] if rows else {}
    folder = _pickup_folder(args.pickup_root, request) if request else _resolve(args.pickup_root)
    summary = {
        "packet_type": "casp17_strict_blind_first_source_request_pickup",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_source_request_pickup_status": _status(input_blockers, rows),
        "source_request_packet_status": _text(request_summary.get("source_request_packet_status")),
        "source_route_board_status": _text(route_summary.get("strict_blind_replacement_first_slot_source_route_board_status")),
        "repair_feasibility_status": _text(
            feasibility_summary.get("strict_blind_replacement_first_slot_repair_feasibility_board_status")
        ),
        "evidence_packet_status": _text(evidence_summary.get("first_unlock_evidence_packet_status")),
        "request_id": _text(request.get("request_id")),
        "candidate_target_id": _text(request.get("candidate_target_id")),
        "candidate_scope": _text(request.get("candidate_scope")),
        "request_kind": _text(request.get("request_kind")),
        "first_blocker": _text(first_action.get("blocker")) if rows else ",".join(input_blockers),
        "first_action_id": _text(first_action.get("action_id")),
        "first_next_action": _text(first_action.get("next_action")) if rows else "provide required input JSON files",
        "current_prediction_pdb": _text(request.get("current_prediction_pdb")),
        "current_prediction_created_at": _text(request.get("prediction_created_at")),
        "native_release_date": _text(request.get("native_release_date")),
        "current_prediction_before_native": _text(first_action.get("current_prediction_before_native")),
        "pickup_option_count": len(rows),
        "ready_option_count": sum(1 for row in rows if row["action_status"] == "operator_ready"),
        "blocked_option_count": blocked_count,
        "in_scope_external_required_count": _int(route_summary.get("in_scope_external_required_count")),
        "out_of_scope_route_count": _int(route_summary.get("out_of_scope_route_count")),
        "external_pre_native_artifact_required_target_count": _int(
            feasibility_summary.get("external_pre_native_artifact_required_target_count")
        ),
        "pickup_folder": _artifact(folder),
        "operator_decision_template_csv": _artifact(folder / "operator_decision_template.csv") if request else "",
        "required_files_manifest_csv": _artifact(folder / "required_files_manifest.csv") if request else "",
        "operator_source_template_csv": _text(request.get("operator_template_csv")),
        "evidence_packet_folder": _text(evidence_summary.get("packet_folder")),
        "prediction_dropzone": _text(evidence_summary.get("prediction_dropzone")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_pickup_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    if not summary["request_id"]:
        return
    folder = _resolve(summary["pickup_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    decision_template = folder / "operator_decision_template.csv"
    file_manifest = folder / "required_files_manifest.csv"
    request = {
        "native_release_date": summary["native_release_date"],
        "prediction_created_at": summary["current_prediction_created_at"],
    }
    _write_csv(decision_template, _decision_template_rows(request, _read_csv(decision_template)), DECISION_TEMPLATE_COLUMNS)
    _write_csv(file_manifest, _file_manifest_rows(request, summary), FILE_MANIFEST_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind First Source Request Pickup",
        "",
        f"- status: `{summary['first_source_request_pickup_status']}`",
        f"- request/target: `{summary['request_id']}` `{summary['candidate_target_id']}` `{summary['candidate_scope']}`",
        f"- current prediction/native dates: `{summary['current_prediction_created_at'] or '-'}` / `{summary['native_release_date'] or '-'}`",
        f"- current prediction before native: `{summary['current_prediction_before_native'] or '-'}`",
        f"- first blocker: `{summary['first_action_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- decision template: `{summary['operator_decision_template_csv']}`",
        f"- required files: `{summary['required_files_manifest_csv']}`",
        f"- source request template: `{summary['operator_source_template_csv'] or '-'}`",
        "",
        "## Options",
        "",
        "| action | status | resolution | required input | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_status']}` | `{row['resolution_path']}` | "
            f"{row['required_operator_input']} | `{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    (folder / "OPERATOR_PICKUP.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Source Request Pickup",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_source_request_pickup_status']}`",
        f"- request/target: `{summary['request_id'] or '-'}` `{summary['candidate_target_id'] or '-'}` `{summary['candidate_scope'] or '-'}`",
        f"- current prediction/native dates: `{summary['current_prediction_created_at'] or '-'}` / `{summary['native_release_date'] or '-'}` before-native `{summary['current_prediction_before_native'] or '-'}`",
        f"- options ready/blocked/total: `{summary['ready_option_count']}/{summary['blocked_option_count']}/{summary['pickup_option_count']}`",
        f"- first blocker: `{summary['first_action_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- pickup folder: `{summary['pickup_folder'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| action | status | target | resolution | before native | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_status']}` | `{row['candidate_target_id']}` | "
            f"`{row['resolution_path']}` | `{row['current_prediction_before_native'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_pickup_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 first source request pickup packet.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--source-route-json", default=DEFAULT_SOURCE_ROUTE_JSON)
    parser.add_argument("--repair-feasibility-json", default=DEFAULT_REPAIR_FEASIBILITY_JSON)
    parser.add_argument("--evidence-packet-json", default=DEFAULT_EVIDENCE_PACKET_JSON)
    parser.add_argument("--pickup-root", default=DEFAULT_PICKUP_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
