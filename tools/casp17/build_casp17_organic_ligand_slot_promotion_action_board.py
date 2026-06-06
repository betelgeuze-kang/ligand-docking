#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_PACKET_JSON = "casp17/casp17_organic_ligand_slot_candidate_packet_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_slot_promotion_action_board"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_slot_promotion_action_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_slot_promotion_action_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_SLOT_PROMOTION_ACTION_BOARD.md"

ACTION_TYPES = [
    "reference_file_preflight",
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "prediction_chronology",
    "ligand_pose_reference",
    "affinity_numeric_label",
    "lddt_pli_metric_inputs",
    "bisyrmsd_metric_inputs",
    "strict_blind_slot_mapping",
]

CLAIM_BOUNDARY = (
    "Organic ligand strict-blind promotion action board only. It decomposes evidence needed to promote review "
    "candidates into CASP17 ligand slots, but it does not supply operator authority evidence, does not clear "
    "no-leak chronology, does not compute LDDT-PLI or BiSyRMSD, and does not mark any candidate as competitive proof."
)

ROW_COLUMNS = [
    "action_rank",
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "ligand_source_dataset",
    "action_id",
    "action_type",
    "action_status",
    "required_artifact",
    "current_evidence",
    "blocks",
    "recommended_owner",
    "action_folder",
    "action_md",
    "next_action",
]


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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


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


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:96] or "candidate"


def _candidate_folder(out_dir: str | Path, candidate: dict[str, Any]) -> Path:
    rank = _int(candidate.get("candidate_rank"))
    target = _text(candidate.get("target_id"))
    return _resolve(out_dir) / f"{rank:02d}_{_slug(target)}"


def _reference_file_preflight(candidate: dict[str, Any]) -> tuple[str, str, str]:
    required = [
        _text(candidate.get("local_reference_pdb")),
        _text(candidate.get("prediction_pdb")),
        _text(candidate.get("ligand_mol2")),
        _text(candidate.get("ligand_template_xml")),
    ]
    present = [
        _bool(candidate.get("local_reference_present")),
        _bool(candidate.get("prediction_present")),
        _bool(candidate.get("ligand_mol2_present")),
        _bool(candidate.get("ligand_template_present")),
    ]
    if all(required) and all(present):
        return (
            "reference_files_present_review_only",
            ";".join(required),
            "local reference/prediction/ligand files are present, but proof authority is still blocked",
        )
    return (
        "open_missing_reference_files",
        ";".join(required),
        "place missing local reference, prediction, ligand mol2, and ligand template files",
    )


def _action_spec(action_type: str, candidate: dict[str, Any]) -> tuple[str, str, str, str, str]:
    if action_type == "reference_file_preflight":
        status, required, next_action = _reference_file_preflight(candidate)
        return status, required, _text(candidate.get("candidate_manifest")), "candidate_core_files", next_action
    if action_type == "direct_native_or_source_authority":
        return (
            "open_operator_evidence_required",
            "direct experimental native/source authority for the same receptor-ligand system",
            _text(candidate.get("native_authority_ref_candidate")),
            "strict_blind_promotion,competitive_proof",
            "attach direct non-homolog native/source authority or explicitly replace this candidate",
        )
    if action_type == "no_leak_provenance":
        return (
            "open_operator_evidence_required",
            "independent no-leak provenance dossier and negative controls",
            _text(candidate.get("blockers")),
            "strict_blind_promotion,metric_surface",
            "attach independent no-leak evidence and operator clearance for this ligand candidate",
        )
    if action_type == "prediction_chronology":
        return (
            "open_operator_evidence_required",
            "prediction_created_at, native_release_date, before-native confirmation",
            _text(candidate.get("lane_decision_status")),
            "strict_blind_promotion,competitive_proof",
            "prove prediction chronology is before native/source release or keep candidate retrospective-only",
        )
    if action_type == "ligand_pose_reference":
        return (
            "open_operator_evidence_required",
            "ligand pose/native interaction reference suitable for ligand metrics",
            _text(candidate.get("local_reference_pdb")),
            "LDDT-PLI,BiSyRMSD",
            "attach a metric-valid ligand pose reference, including receptor/ligand chain and residue mapping",
        )
    if action_type == "affinity_numeric_label":
        if _bool(candidate.get("affinity_label_candidate")):
            status = "open_numeric_value_required"
            evidence = _text(candidate.get("standard_types"))
            next_action = "attach numeric Ki/IC50/Kd value, units, assay reference, censoring flag, and transform rule"
        else:
            status = "open_affinity_source_required"
            evidence = _text(candidate.get("ligand_authority_ref"))
            next_action = "find or attach numeric affinity evidence before affinity ranking is included"
        return (
            status,
            "numeric affinity label with units and assay provenance",
            evidence,
            "Kendall_tau_affinity",
            next_action,
        )
    if action_type == "lddt_pli_metric_inputs":
        return (
            "open_metric_input_required",
            "native and prediction receptor-ligand interaction maps for LDDT-PLI",
            _text(candidate.get("metric_profile")),
            "LDDT-PLI",
            "prepare LDDT-PLI input JSON after direct authority and no-leak evidence clear",
        )
    if action_type == "bisyrmsd_metric_inputs":
        return (
            "open_metric_input_required",
            "binding-site superposition and symmetry-corrected ligand pose RMSD inputs",
            _text(candidate.get("metric_profile")),
            "BiSyRMSD",
            "prepare BiSyRMSD input JSON after ligand pose reference is approved",
        )
    if action_type == "strict_blind_slot_mapping":
        return (
            "open_slot_mapping_required",
            "organic ligand strict-blind benchmark slot id and metric-surface row mapping",
            _text(candidate.get("strict_blind_promotion_status")),
            "metric_surface_contract,competitive_floor",
            "map only cleared candidates into organic ligand strict-blind slots; do not use homolog-only candidates",
        )
    raise ValueError(f"unknown action type: {action_type}")


def _build_rows(candidate_rows: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    action_rank = 0
    for candidate in candidate_rows:
        base_folder = _candidate_folder(out_dir, candidate)
        for action_type in ACTION_TYPES:
            action_rank += 1
            status, required, evidence, blocks, next_action = _action_spec(action_type, candidate)
            action_id = f"organic_ligand_promotion_action_{action_rank:03d}"
            action_folder = base_folder / f"{action_rank:03d}_{action_type}"
            rows.append(
                {
                    "action_rank": action_rank,
                    "candidate_rank": _int(candidate.get("candidate_rank")),
                    "candidate_id": _text(candidate.get("candidate_id")),
                    "target_id": _text(candidate.get("target_id")),
                    "ligand_id": _text(candidate.get("ligand_id")),
                    "ligand_source_dataset": _text(candidate.get("ligand_source_dataset")),
                    "action_id": action_id,
                    "action_type": action_type,
                    "action_status": status,
                    "required_artifact": required,
                    "current_evidence": evidence,
                    "blocks": blocks,
                    "recommended_owner": "operator",
                    "action_folder": _artifact(action_folder),
                    "action_md": _artifact(action_folder / "ACTION.md"),
                    "next_action": next_action,
                }
            )
    return rows


def _status(input_exists: bool, rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_organic_ligand_candidate_packet_missing"
    if not rows:
        return "blocked_no_organic_ligand_promotion_actions"
    return "awaiting_organic_ligand_strict_blind_evidence"


def _build_summary(args: argparse.Namespace, candidate_payload: dict[str, Any], rows: list[dict[str, Any]], input_exists: bool) -> dict[str, Any]:
    candidate_summary = _summary(candidate_payload)
    status_counts = Counter(_text(row.get("action_status")) for row in rows)
    type_counts = Counter(_text(row.get("action_type")) for row in rows)
    open_rows = [row for row in rows if not _text(row.get("action_status")).endswith("_present_review_only")]
    first_open = open_rows[0] if open_rows else {}
    candidate_ids = {_text(row.get("candidate_id")) for row in rows if _text(row.get("candidate_id"))}
    proof_ready_candidates = 0
    return {
        "packet_type": "casp17_organic_ligand_slot_promotion_action_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_slot_promotion_action_board_status": _status(input_exists, rows),
        "candidate_packet_json": _artifact(args.candidate_packet_json),
        "candidate_packet_status": _text(candidate_summary.get("organic_ligand_slot_candidate_status")),
        "candidate_count": len(candidate_ids),
        "action_count": len(rows),
        "open_action_count": len(open_rows),
        "reference_file_preflight_pass_count": status_counts["reference_files_present_review_only"],
        "operator_evidence_required_count": status_counts["open_operator_evidence_required"],
        "numeric_value_required_count": status_counts["open_numeric_value_required"],
        "affinity_source_required_count": status_counts["open_affinity_source_required"],
        "metric_input_required_count": status_counts["open_metric_input_required"],
        "slot_mapping_required_count": status_counts["open_slot_mapping_required"],
        "direct_authority_action_count": type_counts["direct_native_or_source_authority"],
        "no_leak_action_count": type_counts["no_leak_provenance"],
        "chronology_action_count": type_counts["prediction_chronology"],
        "ligand_pose_reference_action_count": type_counts["ligand_pose_reference"],
        "lddt_pli_action_count": type_counts["lddt_pli_metric_inputs"],
        "bisyrmsd_action_count": type_counts["bisyrmsd_metric_inputs"],
        "proof_ready_candidate_count": proof_ready_candidates,
        "competitive_proof_eligible_count": _int(candidate_summary.get("competitive_proof_eligible_count")),
        "strict_blind_promotion_blocked_count": _int(
            candidate_summary.get("strict_blind_promotion_blocked_count")
        ),
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_action_type": _text(first_open.get("action_type")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "work the direct-authority, no-leak, chronology, ligand-pose, affinity, and metric-input actions "
            "before mapping any candidate into an organic ligand strict-blind slot"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.candidate_packet_json)
    candidate_payload = _read_json(input_path)
    rows = _build_rows(_rows(candidate_payload), args.out_dir)
    summary = _build_summary(args, candidate_payload, rows, input_path.exists())
    return {"summary": summary, "rows": rows}


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


def _write_action_file(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['action_id']} Organic Ligand Promotion Action",
        "",
        f"- candidate_id: `{row['candidate_id']}`",
        f"- target_id: `{row['target_id']}`",
        f"- ligand_id: `{row['ligand_id']}`",
        f"- action_type: `{row['action_type']}`",
        f"- action_status: `{row['action_status']}`",
        f"- required_artifact: `{row['required_artifact']}`",
        f"- current_evidence: `{row['current_evidence'] or '-'}`",
        f"- blocks: `{row['blocks']}`",
        "",
        "## Next Action",
        "",
        row["next_action"],
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["action_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ACTION.md").write_text("\n".join(lines), encoding="utf-8")


def _write_candidate_summaries(rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("candidate_id")), []).append(row)
    for candidate_id, candidate_rows in grouped.items():
        if not candidate_id:
            continue
        folder = _resolve(candidate_rows[0]["action_folder"]).parent
        _write_csv(folder / "promotion_actions.csv", candidate_rows, ROW_COLUMNS)
        lines = [
            f"# {candidate_id} Promotion Actions",
            "",
            f"- target_id: `{candidate_rows[0]['target_id']}`",
            f"- ligand_id: `{candidate_rows[0]['ligand_id']}`",
            f"- action_count: `{len(candidate_rows)}`",
            "",
            "| action | status | blocks | next |",
            "| --- | --- | --- | --- |",
        ]
        for row in candidate_rows:
            lines.append(
                f"| `{row['action_type']}` | `{row['action_status']}` | `{row['blocks']}` | `{row['next_action']}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "ACTIONS.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Slot Promotion Action Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_slot_promotion_action_board_status']}`",
        f"- candidates/actions/open: `{summary['candidate_count']}/{summary['action_count']}/{summary['open_action_count']}`",
        f"- reference-file preflight pass: `{summary['reference_file_preflight_pass_count']}`",
        f"- operator evidence/numeric/affinity-source: `{summary['operator_evidence_required_count']}/{summary['numeric_value_required_count']}/{summary['affinity_source_required_count']}`",
        f"- metric-input/slot-mapping: `{summary['metric_input_required_count']}/{summary['slot_mapping_required_count']}`",
        f"- proof ready/eligible/strict-blocked: `{summary['proof_ready_candidate_count']}/{summary['competitive_proof_eligible_count']}/{summary['strict_blind_promotion_blocked_count']}`",
        f"- first open: `{summary['first_open_action_id'] or '-'}` `{summary['first_open_target_id'] or '-'}` `{summary['first_open_action_type'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Actions",
        "",
        "| rank | candidate | target | action | status | blocks | action md |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_rank']}` | `{row['candidate_id']}` | `{row['target_id']}` | "
            f"`{row['action_type']}` | `{row['action_status']}` | `{row['blocks']}` | `{row['action_md']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked_no_organic_ligand_promotion_actions` | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_action_file(row)
    _write_candidate_summaries(payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand strict-blind promotion action board.")
    parser.add_argument("--candidate-packet-json", default=DEFAULT_CANDIDATE_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
