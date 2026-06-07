#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_METRIC_HANDOFF_JSON = "casp17/casp17_3d_molecular_object_metric_handoff_current.json"
DEFAULT_ORGANIC_CANDIDATE_JSON = "casp17/casp17_organic_ligand_slot_candidate_packet_current.json"
DEFAULT_ORGANIC_PROMOTION_JSON = "casp17/casp17_organic_ligand_slot_promotion_action_board_current.json"
DEFAULT_OUT_DIR = "casp17/casp17_3d_ligand_metric_gap_bridge"
DEFAULT_OUT_JSON = "casp17/casp17_3d_ligand_metric_gap_bridge_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_3d_ligand_metric_gap_bridge_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_3D_LIGAND_METRIC_GAP_BRIDGE.md"

LIGAND_METRIC_ACTIONS = {
    "LDDT-PLI": "lddt_pli_metric_inputs",
    "BiSyRMSD": "bisyrmsd_metric_inputs",
}
REQUIRED_ACTION_TYPES = [
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "prediction_chronology",
    "ligand_pose_reference",
    "strict_blind_slot_mapping",
]
CLAIM_BOUNDARY = (
    "CASP17 3D ligand metric gap bridge only. It crosswalks the 3D molecular object metric handoff's "
    "missing ligand metrics to review-ready organic ligand candidates and their promotion actions. It does not "
    "create ligand native objects, compute LDDT-PLI or BiSyRMSD, clear no-leak provenance, mark competitive proof, "
    "serialize a CASP author code, or submit to CASP."
)

ROW_COLUMNS = [
    "bridge_rank",
    "missing_metric_name",
    "candidate_id",
    "candidate_rank",
    "target_id",
    "ligand_id",
    "ligand_source_dataset",
    "review_ready",
    "candidate_metric_required",
    "metric_action_id",
    "metric_action_status",
    "metric_action_md",
    "direct_authority_action_status",
    "no_leak_action_status",
    "chronology_action_status",
    "ligand_pose_action_status",
    "strict_slot_action_status",
    "local_reference_present",
    "prediction_present",
    "ligand_mol2_present",
    "ligand_template_present",
    "competitive_proof_eligible",
    "blockers",
    "next_action",
    "candidate_manifest",
    "candidate_folder",
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


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass"}


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


def _missing_ligand_metrics(metric_handoff_summary: dict[str, Any]) -> list[str]:
    missing = [
        metric.strip()
        for metric in _text(metric_handoff_summary.get("missing_required_metric_names")).split(",")
        if metric.strip()
    ]
    return [metric for metric in missing if metric in LIGAND_METRIC_ACTIONS]


def _actions_by_candidate_type(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (_text(row.get("candidate_id")), _text(row.get("action_type"))): row
        for row in rows
        if _text(row.get("candidate_id")) and _text(row.get("action_type"))
    }


def _action_status(
    action_index: dict[tuple[str, str], dict[str, Any]],
    candidate_id: str,
    action_type: str,
) -> str:
    return _text(action_index.get((candidate_id, action_type), {}).get("action_status"))


def _candidate_metric_required(candidate: dict[str, Any], metric_name: str) -> bool:
    if metric_name == "LDDT-PLI":
        return _boolish(candidate.get("lddt_pli_required"))
    if metric_name == "BiSyRMSD":
        return _boolish(candidate.get("bisyrmsd_required"))
    return False


def _row_blockers(
    candidate: dict[str, Any],
    action_index: dict[tuple[str, str], dict[str, Any]],
    metric_name: str,
) -> list[str]:
    candidate_id = _text(candidate.get("candidate_id"))
    blockers: list[str] = []
    if not _boolish(candidate.get("review_ready")):
        blockers.append("candidate_not_review_ready")
    if not _candidate_metric_required(candidate, metric_name):
        blockers.append("metric_not_required_by_candidate")
    metric_action = action_index.get((candidate_id, LIGAND_METRIC_ACTIONS[metric_name]), {})
    if not metric_action:
        blockers.append("metric_action_missing")
    elif _text(metric_action.get("action_status")) != "open_metric_input_required":
        blockers.append("metric_action_status_unexpected")
    for action_type in REQUIRED_ACTION_TYPES:
        status = _action_status(action_index, candidate_id, action_type)
        if not status:
            blockers.append(f"{action_type}_action_missing")
        elif status.startswith("open_"):
            blockers.append(f"{action_type}_open")
    if not _boolish(candidate.get("competitive_proof_eligible")):
        blockers.append("candidate_not_competitive_proof_eligible")
    if _text(candidate.get("strict_blind_promotion_status")).startswith("blocked"):
        blockers.append("strict_blind_promotion_blocked")
    return list(dict.fromkeys(blockers))


def _bridge_row(
    rank: int,
    metric_name: str,
    candidate: dict[str, Any],
    action_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    candidate_id = _text(candidate.get("candidate_id"))
    metric_action = action_index.get((candidate_id, LIGAND_METRIC_ACTIONS[metric_name]), {})
    blockers = _row_blockers(candidate, action_index, metric_name)
    return {
        "bridge_rank": rank,
        "missing_metric_name": metric_name,
        "candidate_id": candidate_id,
        "candidate_rank": _int(candidate.get("candidate_rank")),
        "target_id": _text(candidate.get("target_id")),
        "ligand_id": _text(candidate.get("ligand_id")),
        "ligand_source_dataset": _text(candidate.get("ligand_source_dataset")),
        "review_ready": str(_boolish(candidate.get("review_ready"))),
        "candidate_metric_required": str(_candidate_metric_required(candidate, metric_name)),
        "metric_action_id": _text(metric_action.get("action_id")),
        "metric_action_status": _text(metric_action.get("action_status")),
        "metric_action_md": _artifact(metric_action.get("action_md", "")),
        "direct_authority_action_status": _action_status(
            action_index, candidate_id, "direct_native_or_source_authority"
        ),
        "no_leak_action_status": _action_status(action_index, candidate_id, "no_leak_provenance"),
        "chronology_action_status": _action_status(action_index, candidate_id, "prediction_chronology"),
        "ligand_pose_action_status": _action_status(action_index, candidate_id, "ligand_pose_reference"),
        "strict_slot_action_status": _action_status(action_index, candidate_id, "strict_blind_slot_mapping"),
        "local_reference_present": str(_boolish(candidate.get("local_reference_present"))),
        "prediction_present": str(_boolish(candidate.get("prediction_present"))),
        "ligand_mol2_present": str(_boolish(candidate.get("ligand_mol2_present"))),
        "ligand_template_present": str(_boolish(candidate.get("ligand_template_present"))),
        "competitive_proof_eligible": str(_boolish(candidate.get("competitive_proof_eligible"))),
        "blockers": ",".join(blockers),
        "next_action": (
            "clear direct authority, no-leak chronology, ligand pose reference, and strict-blind slot mapping "
            f"before computing {metric_name}"
        ),
        "candidate_manifest": _artifact(candidate.get("candidate_manifest", "")),
        "candidate_folder": _artifact(candidate.get("candidate_folder", "")),
    }


def _status(
    missing_metrics: list[str],
    candidate_rows: list[dict[str, Any]],
    bridge_rows: list[dict[str, Any]],
) -> str:
    if not missing_metrics:
        return "ligand_metric_gap_not_open_in_3d_handoff"
    if not candidate_rows:
        return "blocked_ligand_metric_gap_without_candidates"
    if not bridge_rows:
        return "blocked_ligand_metric_gap_without_metric_actions"
    if any(_text(row.get("competitive_proof_eligible")).lower() == "true" for row in bridge_rows):
        return "ligand_metric_gap_has_proof_ready_candidates"
    return "ligand_metric_gap_mapped_awaiting_strict_blind_evidence"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    metric_handoff_payload = _read_json(args.metric_handoff_json)
    candidate_payload = _read_json(args.organic_candidate_json)
    promotion_payload = _read_json(args.organic_promotion_json)
    metric_summary = _summary(metric_handoff_payload)
    candidate_summary = _summary(candidate_payload)
    promotion_summary = _summary(promotion_payload)
    missing_metrics = _missing_ligand_metrics(metric_summary)
    candidate_rows = _rows(candidate_payload)
    action_index = _actions_by_candidate_type(_rows(promotion_payload))
    bridge_rows: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        for metric_name in missing_metrics:
            if _candidate_metric_required(candidate, metric_name):
                bridge_rows.append(_bridge_row(len(bridge_rows) + 1, metric_name, candidate, action_index))
    blocked_rows = [row for row in bridge_rows if _text(row.get("blockers"))]
    first = bridge_rows[0] if bridge_rows else {}
    proof_candidate_ids = {
        _text(row.get("candidate_id"))
        for row in bridge_rows
        if _text(row.get("competitive_proof_eligible")).lower() == "true"
    }
    summary = {
        "packet_type": "casp17_3d_ligand_metric_gap_bridge",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "ligand_metric_gap_bridge_status": _status(missing_metrics, candidate_rows, bridge_rows),
        "metric_handoff_json": _artifact(args.metric_handoff_json),
        "metric_handoff_status": _text(metric_summary.get("metric_handoff_status")),
        "organic_candidate_json": _artifact(args.organic_candidate_json),
        "organic_candidate_status": _text(candidate_summary.get("organic_ligand_slot_candidate_status")),
        "organic_promotion_json": _artifact(args.organic_promotion_json),
        "organic_promotion_status": _text(
            promotion_summary.get("organic_ligand_slot_promotion_action_board_status")
        ),
        "out_dir": _artifact(args.out_dir),
        "missing_ligand_metric_count": len(missing_metrics),
        "missing_ligand_metric_names": ",".join(missing_metrics),
        "bridge_row_count": len(bridge_rows),
        "blocked_bridge_row_count": len(blocked_rows),
        "candidate_count": _int(candidate_summary.get("candidate_count")) or len(candidate_rows),
        "review_ready_candidate_count": _int(candidate_summary.get("review_ready_candidate_count")),
        "strict_blind_blocked_candidate_count": _int(
            candidate_summary.get("strict_blind_promotion_blocked_count")
        ),
        "proof_eligible_candidate_count": len(proof_candidate_ids),
        "lddt_pli_bridge_row_count": sum(1 for row in bridge_rows if row["missing_metric_name"] == "LDDT-PLI"),
        "bisyrmsd_bridge_row_count": sum(1 for row in bridge_rows if row["missing_metric_name"] == "BiSyRMSD"),
        "metric_action_link_count": sum(1 for row in bridge_rows if _text(row.get("metric_action_id"))),
        "direct_authority_open_count": sum(
            1 for row in bridge_rows if row["direct_authority_action_status"].startswith("open_")
        ),
        "no_leak_open_count": sum(1 for row in bridge_rows if row["no_leak_action_status"].startswith("open_")),
        "chronology_open_count": sum(1 for row in bridge_rows if row["chronology_action_status"].startswith("open_")),
        "ligand_pose_open_count": sum(
            1 for row in bridge_rows if row["ligand_pose_action_status"].startswith("open_")
        ),
        "strict_slot_open_count": sum(1 for row in bridge_rows if row["strict_slot_action_status"].startswith("open_")),
        "first_candidate_id": _text(first.get("candidate_id")),
        "first_target_id": _text(first.get("target_id")),
        "first_ligand_id": _text(first.get("ligand_id")),
        "first_metric_name": _text(first.get("missing_metric_name")),
        "first_metric_action_md": _text(first.get("metric_action_md")),
        "first_blocker": _text(first.get("blockers")).split(",")[0] if first else "",
        "next_action": (
            "Use the linked organic ligand promotion actions to clear direct authority, no-leak chronology, "
            "ligand pose mapping, and strict-blind slot mapping before computing ligand metrics."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": bridge_rows}


def _write_metric_bridge_files(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        by_metric.setdefault(row["missing_metric_name"], []).append(row)
    for metric_name, rows in by_metric.items():
        folder = _resolve(args.out_dir) / metric_name.lower().replace("-", "_")
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "bridge_rows.csv", rows, ROW_COLUMNS)
        lines = [
            f"# {metric_name} Ligand Metric Gap Bridge",
            "",
            f"- row_count: `{len(rows)}`",
            f"- proof eligible: `{sum(1 for row in rows if row['competitive_proof_eligible'] == 'True')}`",
            "",
            "| candidate | target | ligand | metric action | blockers |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['candidate_id']}` | `{row['target_id']}` | `{row['ligand_id']}` | "
                f"`{row['metric_action_md'] or '-'}` | `{row['blockers'] or '-'}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "BRIDGE.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 3D Ligand Metric Gap Bridge",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['ligand_metric_gap_bridge_status']}`",
        f"- missing ligand metrics: `{summary['missing_ligand_metric_names'] or '-'}`",
        f"- bridge rows blocked/total: `{summary['blocked_bridge_row_count']}/{summary['bridge_row_count']}`",
        f"- candidates review/proof/strict-blocked/total: `{summary['review_ready_candidate_count']}/{summary['proof_eligible_candidate_count']}/{summary['strict_blind_blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- metric rows LDDT-PLI/BiSyRMSD: `{summary['lddt_pli_bridge_row_count']}/{summary['bisyrmsd_bridge_row_count']}`",
        f"- action links/open direct/no-leak/chronology/pose/slot: `{summary['metric_action_link_count']}/{summary['direct_authority_open_count']}/{summary['no_leak_open_count']}/{summary['chronology_open_count']}/{summary['ligand_pose_open_count']}/{summary['strict_slot_open_count']}`",
        f"- first: `{summary['first_candidate_id'] or '-'}` `{summary['first_metric_name'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Bridge Rows",
        "",
        "| rank | metric | candidate | ligand | action | blockers |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['bridge_rank']} | `{row['missing_metric_name']}` | `{row['candidate_id']}` | "
            f"`{row['ligand_id']}` | `{row['metric_action_md'] or '-'}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_metric_bridge_files(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 3D ligand metric gap bridge.")
    parser.add_argument("--metric-handoff-json", default=DEFAULT_METRIC_HANDOFF_JSON)
    parser.add_argument("--organic-candidate-json", default=DEFAULT_ORGANIC_CANDIDATE_JSON)
    parser.add_argument("--organic-promotion-json", default=DEFAULT_ORGANIC_PROMOTION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
