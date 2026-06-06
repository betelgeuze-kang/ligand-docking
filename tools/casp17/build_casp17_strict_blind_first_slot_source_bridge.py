#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_OFFICIAL_ARCHIVE_SOURCE_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_current.json"
)
DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_slot_source_bridge_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_slot_source_bridge_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_SLOT_SOURCE_BRIDGE.md"
DEFAULT_BRIDGE_DIR = "casp17/historical_seed_strict_blind_first_slot_source_bridge"

ROW_COLUMNS = [
    "field_name",
    "bridge_status",
    "allowed_use",
    "candidate_value",
    "evidence_ref",
    "destination_path",
    "auto_apply_allowed",
    "operator_clearance_required",
    "next_action",
]
OPERATOR_PREVIEW_COLUMNS = [
    "field_name",
    "proposed_value",
    "evidence_ref",
    "operator_clearance",
    "auto_apply_allowed",
    "reason",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot source bridge only. It converts official CASP15/16 archive candidate metadata into "
    "a fail-closed operator preview for the first strict-blind slot. Official archive native structures may guide "
    "native authority review, but official archive prediction tarballs remain external/other-team baseline material "
    "and are not internal competitive-proof predictions. This tool does not download files, create evidence, approve "
    "no-leak provenance, mutate intake CSVs, compute CASP metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
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


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in [
        "first_slot_kit_json",
        "official_archive_source_candidates_json",
        "official_archive_baseline_lane_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _first_ready_candidate(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in source_rows:
        if _text(row.get("candidate_status")).startswith("pre_native_archive_candidate"):
            return row
    return source_rows[0] if source_rows else {}


def _destination(first_slot_rows: list[dict[str, Any]], field_name: str) -> str:
    for row in first_slot_rows:
        if _text(row.get("field_name")) == field_name:
            return _text(row.get("source_path"))
    return ""


def _bridge_rows(candidate: dict[str, Any], first_slot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_id = _text(candidate.get("target_id"))
    competition = _text(candidate.get("competition"))
    replacement_target_id = f"{competition}_{target_id}" if competition and target_id else ""
    candidate_ref = _text(candidate.get("source_folder")) or _text(candidate.get("targetlist_target_url"))
    native_url = _text(candidate.get("native_structure_file_url"))
    native_authority = _text(candidate.get("native_pdb_url")) or native_url
    prediction_tarball = _text(candidate.get("prediction_tarball_url"))
    prediction_archive_date = _text(candidate.get("prediction_archive_modified_at")).split(" ")[0]
    native_release_date = _text(candidate.get("native_public_anchor_date"))
    return [
        {
            "field_name": "replacement_target_id",
            "bridge_status": "operator_review_ready",
            "allowed_use": "target_identity_preview_only",
            "candidate_value": replacement_target_id,
            "evidence_ref": candidate_ref,
            "destination_path": "",
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "operator must accept the historical target identity before any intake mutation",
        },
        {
            "field_name": "prediction_pdb",
            "bridge_status": "blocked_internal_prediction_required",
            "allowed_use": "official_archive_prediction_tarball_baseline_only_not_internal_proof",
            "candidate_value": prediction_tarball,
            "evidence_ref": candidate_ref,
            "destination_path": _destination(first_slot_rows, "prediction_pdb"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "supply a pre-native internal prediction PDB; keep official archive models in baseline lane only",
        },
        {
            "field_name": "native_pdb",
            "bridge_status": "native_authority_candidate_ready_for_operator_download",
            "allowed_use": "native_reference_candidate_after_operator_target_selection",
            "candidate_value": native_url,
            "evidence_ref": native_authority,
            "destination_path": _destination(first_slot_rows, "native_pdb"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "operator may fetch this native PDB into the dropzone after accepting the target identity",
        },
        {
            "field_name": "native_authority_ref",
            "bridge_status": "native_authority_ref_candidate_ready",
            "allowed_use": "native_authority_markdown_candidate_after_operator_target_selection",
            "candidate_value": native_authority,
            "evidence_ref": candidate_ref,
            "destination_path": _destination(first_slot_rows, "native_authority_ref"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "write native authority markdown only after the target identity is accepted",
        },
        {
            "field_name": "prediction_created_at",
            "bridge_status": "operator_value_candidate_ready",
            "allowed_use": "chronology_candidate_from_archive_metadata",
            "candidate_value": prediction_archive_date,
            "evidence_ref": _text(candidate.get("prediction_index_url")),
            "destination_path": "",
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "operator must confirm archive timestamp semantics before using this date",
        },
        {
            "field_name": "native_release_date",
            "bridge_status": "operator_value_candidate_ready",
            "allowed_use": "native_public_anchor_date_candidate",
            "candidate_value": native_release_date,
            "evidence_ref": _text(candidate.get("native_public_anchor_url")),
            "destination_path": "",
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "operator must confirm the native/public anchor date before using this date",
        },
        {
            "field_name": "no_leak_evidence_ref",
            "bridge_status": "operator_evidence_required",
            "allowed_use": "not_available_from_official_archive_candidate",
            "candidate_value": "",
            "evidence_ref": "",
            "destination_path": _destination(first_slot_rows, "no_leak_evidence_ref"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "attach independent no-leak evidence for the internal prediction source",
        },
        {
            "field_name": "ablation_manifest_ref",
            "bridge_status": "operator_evidence_required",
            "allowed_use": "same_run_ablation_required_not_archive_baseline",
            "candidate_value": "",
            "evidence_ref": "",
            "destination_path": _destination(first_slot_rows, "ablation_manifest_ref"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "attach true same-run/pre-minimization ablation layers for the internal prediction",
        },
        {
            "field_name": "calibration_values_ref",
            "bridge_status": "operator_evidence_required",
            "allowed_use": "calibration_required_for_internal_model_selection",
            "candidate_value": "",
            "evidence_ref": "",
            "destination_path": _destination(first_slot_rows, "calibration_values_ref"),
            "auto_apply_allowed": "false",
            "operator_clearance_required": "true",
            "next_action": "attach calibration values for model1/best-of-5 ranking after internal prediction is supplied",
        },
    ]


def _operator_preview_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview = []
    for row in rows:
        preview.append(
            {
                "field_name": row["field_name"],
                "proposed_value": row["candidate_value"],
                "evidence_ref": row["evidence_ref"],
                "operator_clearance": "",
                "auto_apply_allowed": row["auto_apply_allowed"],
                "reason": row["allowed_use"],
            }
        )
    return preview


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    first_slot_payload = _read_json(args.first_slot_kit_json)
    source_payload = _read_json(args.official_archive_source_candidates_json)
    baseline_payload = _read_json(args.official_archive_baseline_lane_json)
    first_slot_summary = _summary(first_slot_payload)
    source_summary = _summary(source_payload)
    baseline_summary = _summary(baseline_payload)
    blockers = _input_blockers(args)
    source_rows = _rows(source_payload)
    first_slot_rows = _rows(first_slot_payload)
    candidate = _first_ready_candidate(source_rows)
    rows = _bridge_rows(candidate, first_slot_rows) if candidate else []
    native_ready = sum(1 for row in rows if row["field_name"] in {"native_pdb", "native_authority_ref"} and "ready" in row["bridge_status"])
    operator_only = sum(1 for row in rows if row["bridge_status"].startswith("operator_"))
    blocked_internal = sum(1 for row in rows if row["bridge_status"] == "blocked_internal_prediction_required")
    candidate_count = _int(source_summary.get("candidate_count"))
    status = "blocked_missing_inputs" if blockers else "awaiting_official_archive_candidate"
    if not blockers and candidate_count:
        status = "first_slot_source_bridge_ready_native_authority_only"
    if blocked_internal:
        status = "first_slot_source_bridge_internal_prediction_required"
    bridge_folder = _resolve(args.bridge_dir) / _text(first_slot_summary.get("required_benchmark_id") or "hist_REQUIRED_MONOMER_001")
    summary = {
        "packet_type": "casp17_strict_blind_first_slot_source_bridge",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_bridge_status": status,
        "required_benchmark_id": _text(first_slot_summary.get("required_benchmark_id")),
        "required_target_id": _text(first_slot_summary.get("required_target_id")),
        "required_scope": _text(first_slot_summary.get("scope")),
        "official_candidate_count": candidate_count,
        "official_ready_candidate_count": _int(source_summary.get("ready_candidate_count")),
        "official_native_authority_ready_count": _int(source_summary.get("native_authority_ready_count")),
        "official_prediction_baseline_only_count": _int(baseline_summary.get("other_team_model_baseline_only_count")),
        "strict_blind_import_blocked_count": _int(baseline_summary.get("strict_blind_import_blocked_count")),
        "bridge_row_count": len(rows),
        "native_authority_bridge_ready_count": native_ready,
        "operator_only_field_count": operator_only,
        "internal_prediction_blocked_count": blocked_internal,
        "auto_apply_allowed_count": sum(1 for row in rows if row["auto_apply_allowed"] == "true"),
        "first_candidate_id": _text(candidate.get("candidate_id")),
        "first_candidate_competition": _text(candidate.get("competition")),
        "first_candidate_target_id": _text(candidate.get("target_id")),
        "first_candidate_native_pdb_code": _text(candidate.get("native_pdb_code")),
        "first_candidate_native_url": _text(candidate.get("native_structure_file_url")),
        "first_candidate_prediction_tarball_url": _text(candidate.get("prediction_tarball_url")),
        "first_blocker": "internal_pre_native_prediction_pdb_required",
        "first_next_action": "provide a pre-native internal prediction PDB; use official archive files only for native authority/baseline review",
        "bridge_folder": _artifact(bridge_folder),
        "operator_value_preview_csv": _artifact(bridge_folder / "operator_value_preview.csv"),
        "source_bridge_md": _artifact(bridge_folder / "FIRST_SLOT_SOURCE_BRIDGE.md"),
        "input_blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def write_bridge_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.bridge_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "first_slot_source_bridge.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(folder / "operator_value_preview.csv", _operator_preview_rows(payload["rows"]), OPERATOR_PREVIEW_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind First Slot Source Bridge",
        "",
        f"- status: `{summary['source_bridge_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- official candidates ready/total: `{summary['official_ready_candidate_count']}/{summary['official_candidate_count']}`",
        f"- native authority bridge ready: `{summary['native_authority_bridge_ready_count']}`",
        f"- official prediction baseline-only/import-blocked: `{summary['official_prediction_baseline_only_count']}/{summary['strict_blind_import_blocked_count']}`",
        f"- auto-apply allowed: `{summary['auto_apply_allowed_count']}`",
        f"- first candidate: `{summary['first_candidate_competition']}` `{summary['first_candidate_target_id']}` `{summary['first_candidate_native_pdb_code']}`",
        f"- first blocker: `{summary['first_blocker']}`",
        f"- next action: {summary['first_next_action']}",
        "",
        "## Field Bridge",
        "",
        "| field | status | allowed use | candidate value | evidence | destination | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['bridge_status']}` | {row['allowed_use']} | `{row['candidate_value']}` | `{row['evidence_ref']}` | `{row['destination_path']}` | {row['next_action']} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    (folder / "FIRST_SLOT_SOURCE_BRIDGE.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Slot Source Bridge",
        "",
        "This board shows which first-slot source metadata can be reviewed and which fields remain operator-only.",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_bridge_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- official candidates ready/total: `{summary['official_ready_candidate_count']}/{summary['official_candidate_count']}`",
        f"- native authority bridge ready: `{summary['native_authority_bridge_ready_count']}`",
        f"- official prediction baseline-only/import-blocked: `{summary['official_prediction_baseline_only_count']}/{summary['strict_blind_import_blocked_count']}`",
        f"- operator-only/internal-blocked fields: `{summary['operator_only_field_count']}/{summary['internal_prediction_blocked_count']}`",
        f"- auto-apply allowed: `{summary['auto_apply_allowed_count']}`",
        f"- first candidate: `{summary['first_candidate_competition']}` `{summary['first_candidate_target_id']}` `{summary['first_candidate_native_pdb_code']}`",
        f"- first blocker: `{summary['first_blocker']}`",
        f"- first next action: {summary['first_next_action']}",
        f"- bridge folder: `{summary['bridge_folder']}`",
        "",
        "## Rows",
        "",
        "| field | status | allowed use | candidate value | destination | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['bridge_status']}` | {row['allowed_use']} | `{row['candidate_value']}` | `{row['destination_path']}` | {row['next_action']} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument(
        "--official-archive-source-candidates-json",
        default=DEFAULT_OFFICIAL_ARCHIVE_SOURCE_CANDIDATES_JSON,
    )
    parser.add_argument("--official-archive-baseline-lane-json", default=DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON)
    parser.add_argument("--bridge-dir", default=DEFAULT_BRIDGE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    write_bridge_folder(args, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
