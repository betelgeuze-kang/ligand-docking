#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_LOCAL_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_SOURCE_ROUTE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON = (
    "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
)
DEFAULT_SOURCE_BRIDGE_JSON = "casp17/casp17_strict_blind_first_slot_source_bridge_current.json"
DEFAULT_AUDIT_DIR = "casp17/strict_blind_internal_prediction_source_audit"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_internal_prediction_source_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_AUDIT.md"

ROW_COLUMNS = [
    "source_id",
    "source_class",
    "source_status",
    "candidate_count",
    "ready_count",
    "blocked_count",
    "allowed_for_strict_blind",
    "proof_use",
    "evidence_ref",
    "next_action",
]
TEMPLATE_COLUMNS = [
    "source_id",
    "replacement_target_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "prediction_created_at",
    "native_release_date",
    "native_authority_ref",
    "prediction_author",
    "creation_evidence_ref",
    "no_leak_evidence_ref",
    "method_summary",
    "operator_clearance",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind internal prediction source audit only. It audits whether the first historical "
    "strict-blind slot has a pre-native internal prediction source and writes an operator manifest template. It "
    "does not create prediction PDBs, download official archive tarballs, reclassify external models as internal "
    "proof, approve no-leak provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or "
    "submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
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
        "local_candidate_board_json",
        "source_route_board_json",
        "official_archive_baseline_lane_json",
        "source_bridge_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _row(
    source_id: str,
    source_class: str,
    source_status: str,
    candidate_count: int,
    ready_count: int,
    blocked_count: int,
    allowed: bool,
    proof_use: str,
    evidence_ref: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_class": source_class,
        "source_status": source_status,
        "candidate_count": candidate_count,
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "allowed_for_strict_blind": str(bool(allowed)).lower(),
        "proof_use": proof_use,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
    }


def _build_rows(
    args: argparse.Namespace,
    first_slot: dict[str, Any],
    local: dict[str, Any],
    route: dict[str, Any],
    baseline: dict[str, Any],
    bridge: dict[str, Any],
    template_path: Path,
) -> list[dict[str, Any]]:
    local_count = _int(local.get("candidate_count"))
    local_ready = _int(local.get("strict_blind_eligible_count"))
    route_count = _int(route.get("route_count"))
    route_ready = _int(route.get("allowed_for_first_slot_count"))
    baseline_count = _int(baseline.get("baseline_candidate_count"))
    baseline_blocked = _int(baseline.get("strict_blind_import_blocked_count"))
    bridge_internal_blocked = _int(bridge.get("internal_prediction_blocked_count"))
    evidence_open = _int(first_slot.get("evidence_open_count"))
    return [
        _row(
            "required_prediction_dropzone",
            "first_slot_evidence",
            "missing_internal_prediction_pdb" if evidence_open else "first_slot_prediction_evidence_not_open",
            1,
            0 if evidence_open else 1,
            1 if evidence_open else 0,
            False,
            "required_internal_prediction_evidence",
            _text(first_slot.get("first_next_action")),
            "place a pre-native internal prediction PDB in the first-slot prediction dropzone",
        ),
        _row(
            "local_candidate_inventory",
            "local_internal_candidates",
            "no_local_strict_blind_prediction_candidates" if local_ready == 0 else "local_candidate_ready_for_review",
            local_count,
            local_ready,
            max(local_count - local_ready, 0),
            local_ready > 0,
            "internal_candidate_review_only_until_operator_clearance",
            _artifact(args.local_candidate_board_json),
            "promote only a candidate with pre-native prediction timestamp, no-leak evidence, ablation, and calibration",
        ),
        _row(
            "first_slot_source_route",
            "route_decision",
            _text(route.get("strict_blind_replacement_first_slot_source_route_board_status")),
            route_count,
            route_ready,
            max(route_count - route_ready, 0),
            route_ready > 0,
            "route_gate_for_internal_prediction_source",
            _artifact(args.source_route_board_json),
            _text(route.get("first_external_next_action")) or "source a pre-native internal prediction or replace candidate",
        ),
        _row(
            "official_archive_prediction_tarballs",
            "external_baseline",
            "blocked_external_other_team_baseline_only",
            baseline_count,
            _int(baseline.get("ready_count")),
            baseline_blocked,
            False,
            "baseline_only_not_internal_competitive_proof",
            _artifact(args.official_archive_baseline_lane_json),
            "keep official archive predictions in baseline lane; do not use them as internal proof",
        ),
        _row(
            "native_authority_source_bridge",
            "native_authority_bridge",
            _text(bridge.get("source_bridge_status")),
            _int(bridge.get("bridge_row_count")),
            _int(bridge.get("native_authority_bridge_ready_count")),
            bridge_internal_blocked + _int(bridge.get("operator_only_field_count")),
            False,
            "native_authority_preview_only_until_internal_prediction_supplied",
            _artifact(args.source_bridge_json),
            _text(bridge.get("first_next_action")),
        ),
        _row(
            "operator_internal_source_manifest",
            "operator_template",
            "ready_for_operator_internal_source_entry",
            1,
            1,
            0,
            False,
            "template_only_not_evidence",
            _artifact(template_path),
            "fill this manifest with a verified pre-native internal prediction source before intake mutation",
        ),
    ]


def _audit_status(input_blockers: list[str], local_ready: int, route_ready: int, bridge_internal_blocked: int) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if local_ready > 0 or route_ready > 0:
        return "internal_prediction_source_candidate_ready_for_operator_review"
    if bridge_internal_blocked:
        return "internal_prediction_source_missing_for_first_slot"
    return "internal_prediction_source_audit_open"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    first_slot_payload = _read_json(args.first_slot_kit_json)
    local_payload = _read_json(args.local_candidate_board_json)
    route_payload = _read_json(args.source_route_board_json)
    baseline_payload = _read_json(args.official_archive_baseline_lane_json)
    bridge_payload = _read_json(args.source_bridge_json)
    first_slot = _summary(first_slot_payload)
    local = _summary(local_payload)
    route = _summary(route_payload)
    baseline = _summary(baseline_payload)
    bridge = _summary(bridge_payload)
    blockers = _input_blockers(args)
    benchmark_id = _text(first_slot.get("required_benchmark_id") or bridge.get("required_benchmark_id"))
    template_path = _resolve(args.audit_dir) / (benchmark_id or "hist_REQUIRED_MONOMER_001") / "internal_prediction_source_manifest_template.csv"
    rows = _build_rows(args, first_slot, local, route, baseline, bridge, template_path)
    local_ready = _int(local.get("strict_blind_eligible_count"))
    route_ready = _int(route.get("allowed_for_first_slot_count"))
    bridge_internal_blocked = _int(bridge.get("internal_prediction_blocked_count"))
    summary = {
        "packet_type": "casp17_strict_blind_internal_prediction_source_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_prediction_source_audit_status": _audit_status(
            blockers, local_ready, route_ready, bridge_internal_blocked
        ),
        "required_benchmark_id": benchmark_id,
        "required_target_id": _text(first_slot.get("required_target_id") or bridge.get("required_target_id")),
        "required_scope": _text(first_slot.get("scope") or bridge.get("required_scope")),
        "first_open_field": _text(first_slot.get("first_open_field")),
        "first_open_status": _text(first_slot.get("first_open_status")),
        "first_next_action": _text(first_slot.get("first_next_action")),
        "local_candidate_count": _int(local.get("candidate_count")),
        "local_strict_blind_eligible_count": local_ready,
        "local_prediction_present_count": _int(local.get("prediction_present_count")),
        "source_route_count": _int(route.get("route_count")),
        "source_route_allowed_count": route_ready,
        "official_baseline_candidate_count": _int(baseline.get("baseline_candidate_count")),
        "official_baseline_ready_count": _int(baseline.get("ready_count")),
        "official_strict_blind_blocked_count": _int(baseline.get("strict_blind_import_blocked_count")),
        "source_bridge_status": _text(bridge.get("source_bridge_status")),
        "native_authority_bridge_ready_count": _int(bridge.get("native_authority_bridge_ready_count")),
        "internal_prediction_blocked_count": bridge_internal_blocked,
        "operator_only_field_count": _int(bridge.get("operator_only_field_count")),
        "row_count": len(rows),
        "allowed_internal_source_count": sum(1 for row in rows if row["allowed_for_strict_blind"] == "true"),
        "template_count": 1,
        "audit_folder": _artifact(template_path.parent),
        "internal_source_manifest_template": _artifact(template_path),
        "first_blocker": "pre_native_internal_prediction_pdb_missing" if bridge_internal_blocked else "",
        "next_action": "fill internal prediction source manifest and place verified PDB in first-slot dropzone",
        "input_blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _template_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": "",
            "replacement_target_id": "",
            "target_id": summary["required_target_id"],
            "scope": summary["required_scope"],
            "prediction_pdb": "",
            "prediction_created_at": "",
            "native_release_date": "",
            "native_authority_ref": "",
            "prediction_author": "",
            "creation_evidence_ref": "",
            "no_leak_evidence_ref": "",
            "method_summary": "",
            "operator_clearance": "",
        }
    ]


def _write_audit_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.audit_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "internal_prediction_source_audit.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(folder / "internal_prediction_source_manifest_template.csv", _template_rows(summary), TEMPLATE_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Audit",
        "",
        f"- status: `{summary['internal_prediction_source_audit_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- local candidates eligible/total: `{summary['local_strict_blind_eligible_count']}/{summary['local_candidate_count']}`",
        f"- source routes allowed/total: `{summary['source_route_allowed_count']}/{summary['source_route_count']}`",
        f"- official baseline ready/blocked/total: `{summary['official_baseline_ready_count']}/{summary['official_strict_blind_blocked_count']}/{summary['official_baseline_candidate_count']}`",
        f"- bridge native/internal-blocked/operator-only: `{summary['native_authority_bridge_ready_count']}/{summary['internal_prediction_blocked_count']}/{summary['operator_only_field_count']}`",
        f"- first blocker: `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Rows",
        "",
        "| source | class | status | ready/blocked/total | allowed | proof use | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['source_id']}` | `{row['source_class']}` | `{row['source_status']}` | "
            f"`{row['ready_count']}/{row['blocked_count']}/{row['candidate_count']}` | "
            f"`{row['allowed_for_strict_blind']}` | {row['proof_use']} | {row['next_action']} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    (folder / "INTERNAL_PREDICTION_SOURCE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['internal_prediction_source_audit_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- first open field/status: `{summary['first_open_field'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- local candidates eligible/total/prediction-present: `{summary['local_strict_blind_eligible_count']}/{summary['local_candidate_count']}/{summary['local_prediction_present_count']}`",
        f"- source routes allowed/total: `{summary['source_route_allowed_count']}/{summary['source_route_count']}`",
        f"- official baseline ready/strict-blocked/total: `{summary['official_baseline_ready_count']}/{summary['official_strict_blind_blocked_count']}/{summary['official_baseline_candidate_count']}`",
        f"- bridge native/internal-blocked/operator-only: `{summary['native_authority_bridge_ready_count']}/{summary['internal_prediction_blocked_count']}/{summary['operator_only_field_count']}`",
        f"- allowed internal sources: `{summary['allowed_internal_source_count']}`",
        f"- manifest template: `{summary['internal_source_manifest_template']}`",
        f"- first blocker: `{summary['first_blocker'] or '-'}`",
        "",
        "## Source Audit",
        "",
        "| source | class | status | ready/blocked/total | allowed | proof use | evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['source_id']}` | `{row['source_class']}` | `{row['source_status']}` | "
            f"`{row['ready_count']}/{row['blocked_count']}/{row['candidate_count']}` | "
            f"`{row['allowed_for_strict_blind']}` | {row['proof_use']} | `{row['evidence_ref']}` |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_audit_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict-blind internal prediction source audit.")
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument("--local-candidate-board-json", default=DEFAULT_LOCAL_CANDIDATE_BOARD_JSON)
    parser.add_argument("--source-route-board-json", default=DEFAULT_SOURCE_ROUTE_BOARD_JSON)
    parser.add_argument("--official-archive-baseline-lane-json", default=DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON)
    parser.add_argument("--source-bridge-json", default=DEFAULT_SOURCE_BRIDGE_JSON)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
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
