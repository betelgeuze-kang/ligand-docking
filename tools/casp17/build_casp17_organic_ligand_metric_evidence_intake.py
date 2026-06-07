#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LIGAND_BRIDGE_JSON = "casp17/casp17_3d_ligand_metric_gap_bridge_current.json"
DEFAULT_PROMOTION_JSON = "casp17/casp17_organic_ligand_slot_promotion_action_board_current.json"
DEFAULT_PACKET_ROOT = "casp17/organic_ligand_metric_evidence_intake"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_evidence_intake_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_evidence_intake_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_EVIDENCE_INTAKE.md"

REQUIRED_FIELD_TYPES = [
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "prediction_chronology",
    "ligand_pose_reference",
    "strict_blind_slot_mapping",
]

FIELD_GUIDANCE = {
    "direct_native_or_source_authority": {
        "kind": "direct_native_or_same_system_source_authority",
        "format": "path, URI, accession, or dossier for direct same receptor-ligand native/source authority",
        "examples": "RCSB/PDB same receptor-ligand native source; source-system structure release record",
        "reject": "homolog-only seed; generated pose; activity-only record without same-system structural authority",
    },
    "no_leak_provenance": {
        "kind": "independent_no_leak_provenance_dossier",
        "format": "path or URI to no-leak dossier plus negative controls",
        "examples": "run manifest excluding native/templates/other-team models; timestamped input ledger",
        "reject": "local path name only; current mtime only; broad assertion without source manifest",
    },
    "prediction_chronology": {
        "kind": "prediction_before_native_chronology",
        "format": "prediction_created_at, native_release_date, and explicit before-native comparison",
        "examples": "immutable job ledger date earlier than authoritative native/source release date",
        "reject": "post-native prediction; copied file date; true/false without source dates",
    },
    "ligand_pose_reference": {
        "kind": "metric_valid_ligand_pose_reference",
        "format": "native/reference receptor-ligand pose mapping with receptor chain and ligand identity",
        "examples": "binding-site residue map; native ligand atom map; receptor chain/residue mapping",
        "reject": "ligand-only activity label; unaligned homolog pose; template without atom identity mapping",
    },
    "strict_blind_slot_mapping": {
        "kind": "strict_blind_metric_slot_mapping",
        "format": "cleared strict-blind slot id, metric scope, and operator clearance",
        "examples": "approved organic ligand strict-blind slot after direct authority and no-leak review",
        "reject": "homolog-only candidate; retrospective-only calibration row; unreviewed slot alias",
    },
}

ROW_COLUMNS = [
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "ligand_source_dataset",
    "field_order",
    "field_key",
    "linked_action_id",
    "linked_action_status",
    "linked_action_md",
    "current_evidence",
    "required_artifact",
    "evidence_request_kind",
    "required_operator_value_format",
    "accepted_evidence_examples",
    "rejected_sources",
    "metric_names",
    "metric_bridge_row_count",
    "metric_action_mds",
    "packet_folder",
    "operator_template_csv",
    "dropzone_manifest_csv",
    "evidence_stub_md",
    "field_status",
    "blocker",
    "next_action",
]

TEMPLATE_COLUMNS = [
    "field_key",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "required_operator_value_format",
    "evidence_stub_md",
    "linked_action_md",
    "notes",
]

DROPZONE_COLUMNS = [
    "field_key",
    "expected_evidence_stub_md",
    "linked_action_md",
    "dropzone_status",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric evidence intake only. It creates operator-facing templates, "
    "dropzone manifests, and evidence stubs to unblock LDDT-PLI and BiSyRMSD planning from the 3D ligand "
    "metric gap bridge. It does not fill operator values, approve no-leak provenance, compute LDDT-PLI or "
    "BiSyRMSD, mark competitive proof, serialize a CASP author code, or submit to CASP."
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


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug.lower() or "item"


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


def _actions_by_candidate_type(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (_text(row.get("candidate_id")), _text(row.get("action_type"))): row
        for row in rows
        if _text(row.get("candidate_id")) and _text(row.get("action_type"))
    }


def _bridge_by_candidate(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        candidate_id = _text(row.get("candidate_id"))
        if candidate_id:
            grouped.setdefault(candidate_id, []).append(row)
    return grouped


def _candidate_seed_rows(bridge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    seeds: list[dict[str, Any]] = []
    for row in sorted(
        bridge_rows,
        key=lambda item: (_int(item.get("candidate_rank")), _int(item.get("bridge_rank"))),
    ):
        candidate_id = _text(row.get("candidate_id"))
        if candidate_id and candidate_id not in seen:
            seen.add(candidate_id)
            seeds.append(row)
    return seeds


def _packet_folder(packet_root: str | Path, candidate: dict[str, Any]) -> Path:
    rank = _int(candidate.get("candidate_rank"))
    ligand = _slug(_text(candidate.get("ligand_id")) or _text(candidate.get("candidate_id")))
    return _resolve(packet_root) / f"{rank:02d}_{ligand}"


def _field_status(action: dict[str, Any]) -> str:
    status = _text(action.get("action_status"))
    if not action:
        return "missing_promotion_action"
    if status.startswith("open_"):
        return "awaiting_operator_evidence"
    return "evidence_ready_for_operator_review"


def _field_blocker(action: dict[str, Any]) -> str:
    status = _text(action.get("action_status"))
    if not action:
        return "promotion_action_missing"
    return status if status.startswith("open_") else ""


def _metric_names(rows: list[dict[str, Any]]) -> str:
    names = [_text(row.get("missing_metric_name")) for row in rows if _text(row.get("missing_metric_name"))]
    return ",".join(dict.fromkeys(names))


def _metric_action_mds(rows: list[dict[str, Any]]) -> str:
    paths = [_artifact(row.get("metric_action_md")) for row in rows if _text(row.get("metric_action_md"))]
    return ";".join(dict.fromkeys(paths))


def _intake_row(
    candidate: dict[str, Any],
    field_order: int,
    field_key: str,
    action: dict[str, Any],
    metric_rows: list[dict[str, Any]],
    packet_folder: Path,
) -> dict[str, Any]:
    guidance = FIELD_GUIDANCE[field_key]
    evidence_stub = packet_folder / "field_evidence" / f"{_slug(field_key)}.md"
    field_status = _field_status(action)
    return {
        "candidate_rank": _int(candidate.get("candidate_rank")),
        "candidate_id": _text(candidate.get("candidate_id")),
        "target_id": _text(candidate.get("target_id")),
        "ligand_id": _text(candidate.get("ligand_id")),
        "ligand_source_dataset": _text(candidate.get("ligand_source_dataset")),
        "field_order": field_order,
        "field_key": field_key,
        "linked_action_id": _text(action.get("action_id")),
        "linked_action_status": _text(action.get("action_status")),
        "linked_action_md": _artifact(action.get("action_md")),
        "current_evidence": _text(action.get("current_evidence")),
        "required_artifact": _text(action.get("required_artifact")),
        "evidence_request_kind": guidance["kind"],
        "required_operator_value_format": guidance["format"],
        "accepted_evidence_examples": guidance["examples"],
        "rejected_sources": guidance["reject"],
        "metric_names": _metric_names(metric_rows),
        "metric_bridge_row_count": len(metric_rows),
        "metric_action_mds": _metric_action_mds(metric_rows),
        "packet_folder": _artifact(packet_folder),
        "operator_template_csv": _artifact(packet_folder / "operator_evidence_template.csv"),
        "dropzone_manifest_csv": _artifact(packet_folder / "dropzone_manifest.csv"),
        "evidence_stub_md": _artifact(evidence_stub),
        "field_status": field_status,
        "blocker": _field_blocker(action),
        "next_action": (
            f"collect evidence in {_artifact(evidence_stub)}, then fill operator_value, "
            f"operator_evidence_ref, and operator_clearance for {field_key}"
            if field_status != "evidence_ready_for_operator_review"
            else f"review accepted evidence for {field_key} before ligand metric promotion"
        ),
    }


def _status(bridge_missing: bool, promotion_missing: bool, rows: list[dict[str, Any]]) -> str:
    if bridge_missing:
        return "blocked_ligand_metric_gap_bridge_missing"
    if promotion_missing:
        return "blocked_organic_ligand_promotion_board_missing"
    if not rows:
        return "blocked_organic_ligand_metric_evidence_rows_missing"
    if any(row["field_status"] != "evidence_ready_for_operator_review" for row in rows):
        return "awaiting_organic_ligand_metric_evidence_intake"
    return "organic_ligand_metric_evidence_ready_for_review"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    bridge_path = _resolve(args.ligand_bridge_json)
    promotion_path = _resolve(args.organic_promotion_json)
    bridge_payload = _read_json(bridge_path)
    promotion_payload = _read_json(promotion_path)
    bridge_summary = _summary(bridge_payload)
    promotion_summary = _summary(promotion_payload)
    bridge_rows = _rows(bridge_payload)
    promotion_rows = _rows(promotion_payload)
    actions = _actions_by_candidate_type(promotion_rows)
    bridge_grouped = _bridge_by_candidate(bridge_rows)
    rows: list[dict[str, Any]] = []
    for candidate in _candidate_seed_rows(bridge_rows):
        candidate_id = _text(candidate.get("candidate_id"))
        metric_rows = bridge_grouped.get(candidate_id, [])
        packet_folder = _packet_folder(args.packet_root, candidate)
        for field_order, field_key in enumerate(REQUIRED_FIELD_TYPES, start=1):
            rows.append(
                _intake_row(
                    candidate,
                    field_order,
                    field_key,
                    actions.get((candidate_id, field_key), {}),
                    metric_rows,
                    packet_folder,
                )
            )
    open_rows = [row for row in rows if row["field_status"] != "evidence_ready_for_operator_review"]
    ready_rows = [row for row in rows if row["field_status"] == "evidence_ready_for_operator_review"]
    first_open = open_rows[0] if open_rows else {}
    candidate_ids = list(dict.fromkeys(row["candidate_id"] for row in rows if row["candidate_id"]))
    ready_candidate_ids = {
        candidate_id
        for candidate_id in candidate_ids
        if all(
            row["field_status"] == "evidence_ready_for_operator_review"
            for row in rows
            if row["candidate_id"] == candidate_id
        )
    }
    summary = {
        "packet_type": "casp17_organic_ligand_metric_evidence_intake",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_evidence_intake_status": _status(
            not bridge_path.exists(),
            not promotion_path.exists(),
            rows,
        ),
        "ligand_bridge_json": _artifact(args.ligand_bridge_json),
        "ligand_bridge_status": _text(bridge_summary.get("ligand_metric_gap_bridge_status")),
        "organic_promotion_json": _artifact(args.organic_promotion_json),
        "organic_promotion_status": _text(
            promotion_summary.get("organic_ligand_slot_promotion_action_board_status")
        ),
        "packet_root": _artifact(args.packet_root),
        "candidate_count": len(candidate_ids),
        "ready_candidate_count": len(ready_candidate_ids),
        "blocked_candidate_count": len(candidate_ids) - len(ready_candidate_ids),
        "field_count": len(rows),
        "ready_field_count": len(ready_rows),
        "open_field_count": len(open_rows),
        "evidence_stub_count": len(rows),
        "operator_template_count": len(candidate_ids),
        "dropzone_manifest_count": len(candidate_ids),
        "metric_bridge_row_count": len(bridge_rows),
        "lddt_pli_bridge_row_count": sum(1 for row in bridge_rows if row.get("missing_metric_name") == "LDDT-PLI"),
        "bisyrmsd_bridge_row_count": sum(1 for row in bridge_rows if row.get("missing_metric_name") == "BiSyRMSD"),
        "direct_authority_field_count": sum(1 for row in rows if row["field_key"] == "direct_native_or_source_authority"),
        "no_leak_field_count": sum(1 for row in rows if row["field_key"] == "no_leak_provenance"),
        "chronology_field_count": sum(1 for row in rows if row["field_key"] == "prediction_chronology"),
        "ligand_pose_field_count": sum(1 for row in rows if row["field_key"] == "ligand_pose_reference"),
        "strict_slot_field_count": sum(1 for row in rows if row["field_key"] == "strict_blind_slot_mapping"),
        "linked_action_count": sum(1 for row in rows if row["linked_action_id"]),
        "first_open_candidate_id": _text(first_open.get("candidate_id")),
        "first_open_field_key": _text(first_open.get("field_key")),
        "first_open_blocker": _text(first_open.get("blocker")),
        "first_packet_folder": _text(first_open.get("packet_folder")),
        "next_action": (
            "Fill the generated operator evidence templates and stubs for direct authority, no-leak, chronology, "
            "ligand pose, and strict-blind slot mapping before computing LDDT-PLI or BiSyRMSD."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _template_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "field_key": row["field_key"],
            "operator_value": "",
            "operator_evidence_ref": "",
            "operator_clearance": "",
            "operator_id": "",
            "required_operator_value_format": row["required_operator_value_format"],
            "evidence_stub_md": row["evidence_stub_md"],
            "linked_action_md": row["linked_action_md"],
            "notes": row["next_action"],
        }
        for row in rows
    ]


def _dropzone_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "field_key": row["field_key"],
            "expected_evidence_stub_md": row["evidence_stub_md"],
            "linked_action_md": row["linked_action_md"],
            "dropzone_status": "awaiting_operator_evidence"
            if row["field_status"] != "evidence_ready_for_operator_review"
            else "ready_for_operator_review",
            "next_action": row["next_action"],
        }
        for row in rows
    ]


def _write_candidate_packets(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    rows_by_folder: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        rows_by_folder.setdefault(row["packet_folder"], []).append(row)
    for folder_artifact, rows in rows_by_folder.items():
        folder = _resolve(folder_artifact)
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "operator_evidence_template.csv", _template_rows(rows), TEMPLATE_COLUMNS)
        _write_csv(folder / "dropzone_manifest.csv", _dropzone_rows(rows), DROPZONE_COLUMNS)
        field_dir = folder / "field_evidence"
        field_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            stub = _resolve(row["evidence_stub_md"])
            lines = [
                f"# {row['field_key']} Evidence Stub",
                "",
                f"- candidate_id: `{row['candidate_id']}`",
                f"- target_id: `{row['target_id']}`",
                f"- ligand_id: `{row['ligand_id']}`",
                f"- evidence_request_kind: `{row['evidence_request_kind']}`",
                f"- required_operator_value_format: `{row['required_operator_value_format']}`",
                f"- accepted_examples: {row['accepted_evidence_examples']}",
                f"- rejected_sources: {row['rejected_sources']}",
                f"- linked_action: `{row['linked_action_md'] or '-'}`",
                "",
                "## Operator Evidence",
                "",
                "- operator_value: ``",
                "- operator_evidence_ref: ``",
                "- operator_clearance: ``",
                "- operator_id: ``",
                "",
                "## Claim Boundary",
                "",
                CLAIM_BOUNDARY,
                "",
            ]
            stub.write_text("\n".join(lines), encoding="utf-8")
        first = rows[0]
        action_lines = [
            f"# Organic Ligand Metric Evidence Intake - {first['candidate_id']}",
            "",
            f"- target_id: `{first['target_id']}`",
            f"- ligand_id: `{first['ligand_id']}`",
            f"- fields open/total: `{sum(1 for row in rows if row['field_status'] != 'evidence_ready_for_operator_review')}/{len(rows)}`",
            f"- metric bridge rows: `{first['metric_bridge_row_count']}` `{first['metric_names']}`",
            f"- operator template: `{_artifact(folder / 'operator_evidence_template.csv')}`",
            f"- dropzone manifest: `{_artifact(folder / 'dropzone_manifest.csv')}`",
            "",
            "## Fields",
            "",
            "| field | status | blocker | stub |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            action_lines.append(
                f"| `{row['field_key']}` | `{row['field_status']}` | `{row['blocker'] or '-'}` | "
                f"`{row['evidence_stub_md']}` |"
            )
        action_lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "ACTION.md").write_text("\n".join(action_lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Evidence Intake",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_evidence_intake_status']}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- fields ready/open/total: `{summary['ready_field_count']}/{summary['open_field_count']}/{summary['field_count']}`",
        f"- templates/stubs/dropzones: `{summary['operator_template_count']}/{summary['evidence_stub_count']}/{summary['dropzone_manifest_count']}`",
        f"- metric bridge rows LDDT-PLI/BiSyRMSD/total: `{summary['lddt_pli_bridge_row_count']}/{summary['bisyrmsd_bridge_row_count']}/{summary['metric_bridge_row_count']}`",
        f"- field lanes direct/no-leak/chronology/pose/slot: `{summary['direct_authority_field_count']}/{summary['no_leak_field_count']}/{summary['chronology_field_count']}/{summary['ligand_pose_field_count']}/{summary['strict_slot_field_count']}`",
        f"- first open: `{summary['first_open_candidate_id'] or '-'}` `{summary['first_open_field_key'] or '-'}` `{summary['first_open_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Intake Rows",
        "",
        "| candidate | field | status | blocker | template | stub |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['field_key']}` | `{row['field_status']}` | "
            f"`{row['blocker'] or '-'}` | `{row['operator_template_csv']}` | `{row['evidence_stub_md']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_candidate_packets(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric evidence intake.")
    parser.add_argument("--ligand-bridge-json", default=DEFAULT_LIGAND_BRIDGE_JSON)
    parser.add_argument("--organic-promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--packet-root", default=DEFAULT_PACKET_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
