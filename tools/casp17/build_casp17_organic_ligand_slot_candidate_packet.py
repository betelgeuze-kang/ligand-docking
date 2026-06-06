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

DEFAULT_COMPLEX_SOURCE_AUTHORITY_JSON = (
    "casp17/casp17_historical_seed_complex_source_authority_candidates_current.json"
)
DEFAULT_LANE_DECISION_PACKET_JSON = "casp17/casp17_historical_seed_lane_decision_packet_current.json"
DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON = (
    "casp17/casp17_win_tier_metric_surface_contract_current.json"
)
DEFAULT_OUT_DIR = "casp17/organic_ligand_slot_candidate_packet"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_slot_candidate_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_slot_candidate_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_SLOT_CANDIDATE_PACKET.md"

REVIEW_READY_STATUS = "organic_ligand_slot_candidate_ready_for_operator_review"
STRICT_BLIND_BLOCKED_STATUS = "blocked_homolog_source_no_leak_and_chronology_required"
COMPETITIVE_PROOF_ELIGIBLE = "False"
LIGAND_METRICS = ("LDDT-PLI", "BiSyRMSD")
AFFINITY_METRIC = "Kendall_tau_affinity"

CLAIM_BOUNDARY = (
    "CASP17 organic ligand slot candidate packet only. It identifies local historical protein-ligand "
    "complex candidates and their source-authority evidence, but it does not promote them into strict-blind "
    "competitive proof, does not treat homolog-only ligand evidence as direct native authority, and does not "
    "claim CASP17 ligand pose or affinity performance."
)

ROW_COLUMNS = [
    "candidate_rank",
    "candidate_id",
    "target_id",
    "benchmark_id",
    "ligand_id",
    "ligand_source_dataset",
    "molecule_or_monomer_id",
    "ligand_authority_ref",
    "protein_authority_ref",
    "native_authority_ref_candidate",
    "standard_types",
    "best_document_year",
    "best_assay_description",
    "local_reference_pdb",
    "prediction_pdb",
    "ligand_mol2",
    "ligand_conect_pdb",
    "ligand_template_xml",
    "local_reference_present",
    "prediction_present",
    "ligand_mol2_present",
    "ligand_template_present",
    "source_authority_status",
    "lane_decision_status",
    "strict_blind_eligible",
    "competitive_proof_allowed",
    "competitive_proof_eligible",
    "review_ready",
    "strict_blind_promotion_status",
    "lddt_pli_required",
    "bisyrmsd_required",
    "affinity_label_candidate",
    "metric_profile",
    "candidate_folder",
    "candidate_manifest",
    "blockers",
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


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_").lower()
    return slug[:96] or "organic_ligand_candidate"


def _dataset(value: str, authority_ref: str) -> str:
    text = f"{value} {authority_ref}".lower()
    if "bindingdb" in text or "bdb" in text:
        return "BindingDB"
    if "chembl" in text:
        return "ChEMBL"
    return value or "unknown"


def _is_ligand_candidate(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        _text(row.get(key))
        for key in (
            "ligand_source_dataset",
            "ligand_authority_ref",
            "ligand_id",
            "molecule_or_monomer_id",
            "target_id",
        )
    ).lower()
    return "chembl" in haystack or "bindingdb" in haystack or "bdb" in haystack


def _lane_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in _rows(payload) if _text(row.get("target_id"))}


def _default_ligand_file(reference_pdb: str, filename: str) -> str:
    if not reference_pdb:
        return ""
    folder = _resolve(reference_pdb).parent
    return _artifact(folder / filename)


def _present(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


def _candidate_folder(base_dir: str | Path, rank: int, target_id: str) -> Path:
    return _resolve(base_dir) / f"{rank:02d}_{_safe_slug(target_id)}"


def _blockers(source: dict[str, Any], lane: dict[str, Any]) -> str:
    blockers = []
    source_blockers = _text(source.get("blockers"))
    if source_blockers:
        blockers.append(source_blockers)
    if not _bool(source.get("direct_tcruzi_pde_evidence")):
        blockers.append("direct_tcruzi_pde_evidence_absent")
    if _bool(source.get("homolog_seed_only")):
        blockers.append("homolog_seed_only")
    if not _bool(lane.get("strict_blind_eligible")):
        blockers.append("strict_blind_not_eligible")
    if not _bool(lane.get("competitive_proof_allowed")):
        blockers.append("competitive_proof_not_allowed")
    blockers.append("operator_no_leak_chronology_native_authority_required")
    return ",".join(dict.fromkeys(blockers))


def _build_rows(
    source_rows: list[dict[str, Any]],
    lane_rows: dict[str, dict[str, Any]],
    out_dir: str | Path,
) -> list[dict[str, Any]]:
    candidate_rows = [row for row in source_rows if _is_ligand_candidate(row)]
    result: list[dict[str, Any]] = []
    for rank, source in enumerate(candidate_rows, start=1):
        target_id = _text(source.get("target_id"))
        lane = lane_rows.get(target_id, {})
        reference_pdb = _text(source.get("complex_pdb"))
        prediction_pdb = _text(source.get("minimized_complex_pdb"))
        ligand_mol2 = _default_ligand_file(reference_pdb, "ligand.mol2")
        ligand_conect_pdb = _default_ligand_file(reference_pdb, "ligand_LIG_conect.pdb")
        ligand_template_xml = _default_ligand_file(reference_pdb, "ligand_template.xml")
        folder = _candidate_folder(out_dir, rank, target_id)
        dataset = _dataset(
            _text(source.get("ligand_source_dataset")),
            _text(source.get("ligand_authority_ref")),
        )
        standard_types = _text(source.get("standard_types"))
        local_reference_present = _present(reference_pdb)
        prediction_present = _present(prediction_pdb)
        ligand_mol2_present = _present(ligand_mol2)
        ligand_template_present = _present(ligand_template_xml)
        review_ready = all(
            [
                _text(source.get("ligand_authority_ref")),
                _text(source.get("protein_authority_ref")),
                local_reference_present,
                prediction_present,
                ligand_mol2_present,
            ]
        )
        row = {
            "candidate_rank": rank,
            "candidate_id": f"organic_ligand_slot_candidate_{rank:03d}",
            "target_id": target_id,
            "benchmark_id": _text(source.get("benchmark_id")),
            "ligand_id": _text(source.get("ligand_id")),
            "ligand_source_dataset": dataset,
            "molecule_or_monomer_id": _text(source.get("molecule_or_monomer_id")),
            "ligand_authority_ref": _text(source.get("ligand_authority_ref")),
            "protein_authority_ref": _text(source.get("protein_authority_ref")),
            "native_authority_ref_candidate": _text(source.get("native_authority_ref_candidate")),
            "standard_types": standard_types,
            "best_document_year": _text(source.get("best_document_year")),
            "best_assay_description": _text(source.get("best_assay_description")),
            "local_reference_pdb": _artifact(reference_pdb) if reference_pdb else "",
            "prediction_pdb": _artifact(prediction_pdb) if prediction_pdb else "",
            "ligand_mol2": ligand_mol2,
            "ligand_conect_pdb": ligand_conect_pdb,
            "ligand_template_xml": ligand_template_xml,
            "local_reference_present": str(local_reference_present),
            "prediction_present": str(prediction_present),
            "ligand_mol2_present": str(ligand_mol2_present),
            "ligand_template_present": str(ligand_template_present),
            "source_authority_status": _text(source.get("candidate_status")),
            "lane_decision_status": _text(lane.get("lane_decision_status")),
            "strict_blind_eligible": str(_bool(lane.get("strict_blind_eligible"))),
            "competitive_proof_allowed": str(_bool(lane.get("competitive_proof_allowed"))),
            "competitive_proof_eligible": COMPETITIVE_PROOF_ELIGIBLE,
            "review_ready": str(review_ready),
            "strict_blind_promotion_status": STRICT_BLIND_BLOCKED_STATUS,
            "lddt_pli_required": "True",
            "bisyrmsd_required": "True",
            "affinity_label_candidate": str(bool(standard_types)),
            "metric_profile": ",".join((*LIGAND_METRICS, AFFINITY_METRIC)),
            "candidate_folder": _artifact(folder),
            "candidate_manifest": _artifact(folder / "CANDIDATE.md"),
            "blockers": _blockers(source, lane),
            "next_action": (
                "operator review only: attach direct native/source authority, no-leak chronology, prediction "
                "provenance, ligand-pose reference, and numeric affinity labels before any strict-blind slot "
                "promotion"
            ),
        }
        result.append(row)
    return result


def _status(input_exists: bool, rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_complex_source_authority_candidates_missing"
    if not rows:
        return "blocked_organic_ligand_candidates_missing"
    return "organic_ligand_slot_candidates_ready_for_operator_review"


def _build_summary(
    args: argparse.Namespace,
    source_payload: dict[str, Any],
    lane_payload: dict[str, Any],
    metric_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    source_exists: bool,
) -> dict[str, Any]:
    metric_summary = _summary(metric_payload)
    lane_summary = _summary(lane_payload)
    ready_rows = [row for row in rows if row["review_ready"] == "True"]
    chembl_rows = [row for row in rows if row["ligand_source_dataset"] == "ChEMBL"]
    bindingdb_rows = [row for row in rows if row["ligand_source_dataset"] == "BindingDB"]
    first = rows[0] if rows else {}
    return {
        "packet_type": "casp17_organic_ligand_slot_candidate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_slot_candidate_status": _status(source_exists, rows),
        "complex_source_authority_json": _artifact(args.complex_source_authority_json),
        "complex_source_authority_status": _text(
            _summary(source_payload).get("complex_source_authority_candidate_status")
        ),
        "lane_decision_packet_json": _artifact(args.lane_decision_packet_json),
        "lane_decision_status": _text(lane_summary.get("lane_decision_status")),
        "metric_surface_contract_json": _artifact(args.win_tier_metric_surface_contract_json),
        "metric_surface_contract_status": _text(metric_summary.get("metric_surface_contract_status")),
        "metric_contract_ligand_slot_gap_count": _int(metric_summary.get("organic_ligand_slot_count")),
        "candidate_count": len(rows),
        "chembl_candidate_count": len(chembl_rows),
        "bindingdb_candidate_count": len(bindingdb_rows),
        "review_ready_candidate_count": len(ready_rows),
        "competitive_proof_eligible_count": sum(
            1 for row in rows if row["competitive_proof_eligible"] == "True"
        ),
        "strict_blind_promotion_blocked_count": sum(
            1 for row in rows if row["strict_blind_promotion_status"] == STRICT_BLIND_BLOCKED_STATUS
        ),
        "local_reference_present_count": sum(1 for row in rows if row["local_reference_present"] == "True"),
        "prediction_present_count": sum(1 for row in rows if row["prediction_present"] == "True"),
        "ligand_mol2_present_count": sum(1 for row in rows if row["ligand_mol2_present"] == "True"),
        "ligand_template_present_count": sum(1 for row in rows if row["ligand_template_present"] == "True"),
        "lddt_pli_required_count": sum(1 for row in rows if row["lddt_pli_required"] == "True"),
        "bisyrmsd_required_count": sum(1 for row in rows if row["bisyrmsd_required"] == "True"),
        "affinity_label_candidate_count": sum(1 for row in rows if row["affinity_label_candidate"] == "True"),
        "first_candidate_id": _text(first.get("candidate_id")),
        "first_candidate_target_id": _text(first.get("target_id")),
        "first_candidate_ligand_id": _text(first.get("ligand_id")),
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "choose review-ready organic ligand candidates only after direct authority/no-leak evidence is attached; "
            "then map selected rows into organic ligand strict-blind slots for LDDT-PLI and BiSyRMSD"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_path = _resolve(args.complex_source_authority_json)
    source_payload = _read_json(source_path)
    lane_payload = _read_json(args.lane_decision_packet_json)
    metric_payload = _read_json(args.win_tier_metric_surface_contract_json)
    rows = _build_rows(_rows(source_payload), _lane_by_target(lane_payload), args.out_dir)
    summary = _build_summary(
        args,
        source_payload,
        lane_payload,
        metric_payload,
        rows,
        source_path.exists(),
    )
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


def _write_candidate_manifest(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Organic Ligand Slot Candidate",
        "",
        f"- candidate_id: `{row['candidate_id']}`",
        f"- benchmark_id: `{row['benchmark_id']}`",
        f"- ligand_id: `{row['ligand_id']}`",
        f"- ligand_source_dataset: `{row['ligand_source_dataset']}`",
        f"- molecule_or_monomer_id: `{row['molecule_or_monomer_id']}`",
        f"- review_ready: `{row['review_ready']}`",
        f"- competitive_proof_eligible: `{row['competitive_proof_eligible']}`",
        f"- strict_blind_promotion_status: `{row['strict_blind_promotion_status']}`",
        f"- metric_profile: `{row['metric_profile']}`",
        f"- local_reference_pdb: `{row['local_reference_pdb']}`",
        f"- prediction_pdb: `{row['prediction_pdb']}`",
        f"- ligand_mol2: `{row['ligand_mol2']}`",
        f"- ligand_authority_ref: `{row['ligand_authority_ref']}`",
        f"- protein_authority_ref: `{row['protein_authority_ref']}`",
        f"- blockers: `{row['blockers']}`",
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
    folder = _resolve(row["candidate_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CANDIDATE.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "candidate_row.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Slot Candidate Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_slot_candidate_status']}`",
        f"- candidates review/proof/total: `{summary['review_ready_candidate_count']}/{summary['competitive_proof_eligible_count']}/{summary['candidate_count']}`",
        f"- ChEMBL/BindingDB: `{summary['chembl_candidate_count']}/{summary['bindingdb_candidate_count']}`",
        f"- files reference/prediction/ligand/template: `{summary['local_reference_present_count']}/{summary['prediction_present_count']}/{summary['ligand_mol2_present_count']}/{summary['ligand_template_present_count']}`",
        f"- metric requirements LDDT-PLI/BiSyRMSD: `{summary['lddt_pli_required_count']}/{summary['bisyrmsd_required_count']}`",
        f"- affinity label candidates: `{summary['affinity_label_candidate_count']}`",
        f"- metric-contract ligand slots currently: `{summary['metric_contract_ligand_slot_gap_count']}`",
        f"- first candidate: `{summary['first_candidate_target_id'] or '-'}` `{summary['first_candidate_ligand_id'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Candidates",
        "",
        "| rank | target | ligand | source | review | proof | metrics | manifest |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_rank']}` | `{row['target_id']}` | `{row['ligand_id']}` | "
            f"`{row['ligand_source_dataset']}` | `{row['review_ready']}` | "
            f"`{row['competitive_proof_eligible']}` | `{row['metric_profile']}` | "
            f"`{row['candidate_manifest']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `False` | `False` | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_candidate_manifest(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand slot candidate packet.")
    parser.add_argument("--complex-source-authority-json", default=DEFAULT_COMPLEX_SOURCE_AUTHORITY_JSON)
    parser.add_argument("--lane-decision-packet-json", default=DEFAULT_LANE_DECISION_PACKET_JSON)
    parser.add_argument(
        "--win-tier-metric-surface-contract-json",
        default=DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON,
    )
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
