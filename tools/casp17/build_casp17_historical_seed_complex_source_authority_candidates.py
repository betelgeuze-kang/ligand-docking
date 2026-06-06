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

DEFAULT_SEED_INVENTORY_JSON = "runs/casp17_historical_identity_seed_inventory_current.json"
DEFAULT_PARAMETERIZATION_JSON = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json"
DEFAULT_CHEMBL_SEED_CSV = "runs/wetlab_tcruzi_pde_external_pdeb1_seed_packet_current.csv"
DEFAULT_BINDINGDB_SEED_CSV = "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_packet_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_complex_source_authority_candidates_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_complex_source_authority_candidates_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_COMPLEX_SOURCE_AUTHORITY_CANDIDATES.md"
DEFAULT_OUT_DIR = "casp17/historical_seed_complex_source_authority_candidates"

ROW_COLUMNS = [
    "candidate_rank",
    "target_id",
    "benchmark_id",
    "seed_rank",
    "batch_slot",
    "ligand_id",
    "candidate_status",
    "authority_kind",
    "native_authority_ref_candidate",
    "protein_authority_ref",
    "ligand_authority_ref",
    "protein_source_pdb",
    "complex_pdb",
    "minimized_complex_pdb",
    "ligand_source_dataset",
    "ligand_source_scope",
    "molecule_or_monomer_id",
    "target_organisms",
    "target_pref_names",
    "document_ids",
    "assay_ids",
    "standard_types",
    "best_document_year",
    "best_assay_description",
    "direct_tcruzi_pde_evidence",
    "homolog_seed_only",
    "parameterization_status",
    "protein_local_minimization_status",
    "local_minimization_survival_fraction",
    "ligand_heavy_atom_rmsd_A",
    "mean_min_distance_A",
    "contact_fraction",
    "claim_promotion_allowed",
    "operator_apply_allowed",
    "audit_folder",
    "blockers",
    "next_action",
    "claim_boundary",
]

CLAIM_BOUNDARY = (
    "CASP17 historical complex source-authority candidate packet only. It links local generated "
    "T. cruzi PDE protein-ligand references to explicit upstream source records: RCSB 3V94 chain B "
    "for the protein coordinates and ChEMBL/BindingDB homolog PDEB1 records for ligand evidence. "
    "It does not convert these generated complexes into experimental native structures, does not "
    "claim direct T. cruzi PDE wet-lab evidence, does not clear no-leak chronology, and does not "
    "submit or promote benchmark rows automatically."
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


def _float_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return str(float(text))
    except ValueError:
        return text


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_") or "unknown"


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _ligand_key_from_label(label: str) -> str:
    return re.sub(r"^\d+_", "", _safe_name(label))


def _chembl_url(identifier: str, kind: str) -> str:
    identifier = _text(identifier)
    if not identifier:
        return ""
    return f"https://www.ebi.ac.uk/chembl/{kind}_report_card/{identifier}/"


def _bindingdb_url(monomer_id: str) -> str:
    monomer_id = _text(monomer_id)
    return f"https://www.bindingdb.org/rwd/bind/chemsearch/marvin/MolStructure.jsp?monomerid={monomer_id}" if monomer_id else ""


def _source_ref(source_row: dict[str, Any]) -> tuple[str, str, str]:
    dataset = _text(source_row.get("source_dataset"))
    if dataset == "ChEMBL":
        molecule = _text(source_row.get("molecule_chembl_id"))
        target_ids = _text(source_row.get("target_chembl_ids"))
        document_ids = _text(source_row.get("document_chembl_ids"))
        assay_ids = _text(source_row.get("assay_chembl_ids"))
        refs = [f"chembl_molecule:{molecule}"]
        if target_ids:
            refs.append(f"chembl_target:{target_ids}")
        if document_ids:
            refs.append(f"chembl_document:{document_ids}")
        if assay_ids:
            refs.append(f"chembl_assay:{assay_ids}")
        return ";".join(refs), molecule, _chembl_url(molecule, "compound")
    if dataset == "BindingDB":
        monomer_id = _text(source_row.get("bindingdb_monomer_id"))
        refs = [f"bindingdb_monomer:{monomer_id}"] if monomer_id else []
        return ";".join(refs), monomer_id, _bindingdb_url(monomer_id)
    return "", "", ""


def _source_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_text(row.get("ligand_id")): row for row in rows if _text(row.get("ligand_id"))}


def _param_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("ligand_id")): row for row in rows if _text(row.get("ligand_id"))}


def _row_blockers(
    *,
    seed: dict[str, Any],
    param_row: dict[str, Any],
    source_row: dict[str, Any],
    protein_source_pdb: str,
    ligand_authority_ref: str,
) -> list[str]:
    blockers: list[str] = []
    if not _resolve(seed.get("native_pdb", "")).is_file():
        blockers.append("seed_complex_pdb_missing")
    if not _resolve(seed.get("prediction_pdb", "")).is_file():
        blockers.append("seed_minimized_complex_pdb_missing")
    if not param_row:
        blockers.append("parameterization_row_missing")
    if param_row and _text(param_row.get("parameterization_status")) != "integrated_openmm_system_ready":
        blockers.append("parameterization_not_ready")
    if param_row and _text(param_row.get("protein_local_minimization_status")) != "pass":
        blockers.append("protein_local_minimization_not_pass")
    if not _resolve(protein_source_pdb).is_file():
        blockers.append("protein_source_pdb_missing")
    if not source_row:
        blockers.append("ligand_source_row_missing")
    if not ligand_authority_ref:
        blockers.append("ligand_authority_ref_missing")
    if _bool(source_row.get("direct_tcruzi_pde_evidence")):
        return blockers
    blockers.append("direct_tcruzi_pde_evidence_absent_homolog_seed_only")
    return blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    seed_payload = _read_json(args.seed_inventory_json)
    parameterization_payload = _read_json(args.parameterization_json)
    parameterization_summary = parameterization_payload.get("summary") if isinstance(parameterization_payload.get("summary"), dict) else {}
    protein_source_pdb = _text(parameterization_summary.get("native_pdb"))
    protein_chain_id = _text(parameterization_summary.get("native_chain_id")) or "B"
    protein_authority_ref = f"rcsb:3V94;chain:{protein_chain_id};doi:10.2210/pdb3v94/pdb"
    param_by_ligand = _param_lookup(_json_rows(parameterization_payload))
    source_by_ligand = _source_lookup(_read_csv(args.chembl_seed_csv))
    source_by_ligand.update(_source_lookup(_read_csv(args.bindingdb_seed_csv)))

    rows: list[dict[str, Any]] = []
    for seed in _json_rows(seed_payload):
        if _text(seed.get("scope")) != "complex":
            continue
        label_key = _ligand_key_from_label(_text(seed.get("target_label")))
        ligand_id = next((candidate for candidate in param_by_ligand if candidate.endswith(label_key)), label_key)
        param_row = param_by_ligand.get(ligand_id, {})
        source_row = source_by_ligand.get(ligand_id, {})
        ligand_authority_ref, molecule_or_monomer_id, source_url = _source_ref(source_row)
        blockers = _row_blockers(
            seed=seed,
            param_row=param_row,
            source_row=source_row,
            protein_source_pdb=protein_source_pdb,
            ligand_authority_ref=ligand_authority_ref,
        )
        rank = len(rows) + 1
        folder_slot = _int(seed.get("batch_slot")) or _int(seed.get("seed_rank")) or rank
        folder = _resolve(args.out_dir) / f"{folder_slot:02d}_{_safe_name(_text(seed.get('target_id')))}"
        source_scope = _text(source_row.get("source_anchor")) or _text(source_row.get("claim_policy"))
        direct_evidence = _bool(source_row.get("direct_tcruzi_pde_evidence"))
        candidate_status = (
            "operator_direct_source_authority_review_ready"
            if direct_evidence and not blockers
            else "operator_homolog_source_authority_review_ready"
            if "direct_tcruzi_pde_evidence_absent_homolog_seed_only" in blockers
            and all(blocker == "direct_tcruzi_pde_evidence_absent_homolog_seed_only" for blocker in blockers)
            else "source_authority_blocked"
        )
        authority_ref_candidate = ";".join(
            part
            for part in (
                protein_authority_ref,
                ligand_authority_ref,
                f"source_scope:{_safe_name(source_scope)}" if source_scope else "",
                f"local_reference:{_artifact(seed.get('native_pdb', ''))}",
            )
            if part
        )
        rows.append(
            {
                "candidate_rank": rank,
                "target_id": _text(seed.get("target_id")),
                "benchmark_id": _text(seed.get("benchmark_id")),
                "seed_rank": _int(seed.get("seed_rank")),
                "batch_slot": _int(seed.get("batch_slot")),
                "ligand_id": ligand_id,
                "candidate_status": candidate_status,
                "authority_kind": "generated_complex_source_authority_review",
                "native_authority_ref_candidate": authority_ref_candidate,
                "protein_authority_ref": protein_authority_ref,
                "ligand_authority_ref": ligand_authority_ref,
                "protein_source_pdb": _artifact(protein_source_pdb),
                "complex_pdb": _artifact(seed.get("native_pdb", "")),
                "minimized_complex_pdb": _artifact(seed.get("prediction_pdb", "")),
                "ligand_source_dataset": _text(source_row.get("source_dataset")),
                "ligand_source_scope": source_scope,
                "molecule_or_monomer_id": molecule_or_monomer_id,
                "target_organisms": _text(source_row.get("target_organisms")),
                "target_pref_names": _text(source_row.get("target_pref_names")),
                "document_ids": _text(source_row.get("document_chembl_ids")),
                "assay_ids": _text(source_row.get("assay_chembl_ids")),
                "standard_types": _text(source_row.get("standard_types")),
                "best_document_year": _text(source_row.get("best_document_year")),
                "best_assay_description": _text(source_row.get("best_assay_description")),
                "direct_tcruzi_pde_evidence": direct_evidence,
                "homolog_seed_only": _bool(source_row.get("homolog_seed_only")),
                "parameterization_status": _text(param_row.get("parameterization_status")),
                "protein_local_minimization_status": _text(param_row.get("protein_local_minimization_status")),
                "local_minimization_survival_fraction": _float_text(
                    param_row.get("local_minimization_survival_fraction")
                ),
                "ligand_heavy_atom_rmsd_A": _float_text(param_row.get("ligand_heavy_atom_rmsd_A")),
                "mean_min_distance_A": _float_text(param_row.get("mean_min_distance_A")),
                "contact_fraction": _float_text(param_row.get("contact_fraction")),
                "claim_promotion_allowed": False,
                "operator_apply_allowed": False,
                "audit_folder": _artifact(folder),
                "blockers": ",".join(blockers),
                "next_action": (
                    "operator may cite this as source authority only after accepting the homolog-only claim boundary"
                    if candidate_status == "operator_homolog_source_authority_review_ready"
                    else "attach direct T. cruzi complex/native authority or replace this seed row"
                ),
                "claim_boundary": CLAIM_BOUNDARY,
                "source_url": source_url,
            }
        )

    review_ready = sum(1 for row in rows if row["candidate_status"].startswith("operator_"))
    direct_ready = sum(1 for row in rows if row["candidate_status"] == "operator_direct_source_authority_review_ready")
    homolog_ready = sum(1 for row in rows if row["candidate_status"] == "operator_homolog_source_authority_review_ready")
    blocked = len(rows) - review_ready
    first_blocked = next((row for row in rows if row["candidate_status"] == "source_authority_blocked"), rows[0] if rows else {})
    if not rows:
        status = "missing_complex_seed_rows"
    elif blocked:
        status = "complex_source_authority_candidates_blocked"
    elif direct_ready == len(rows):
        status = "complex_direct_source_authority_candidates_ready"
    else:
        status = "complex_homolog_source_authority_candidates_ready_claim_limited"
    summary = {
        "packet_type": "casp17_historical_seed_complex_source_authority_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "complex_source_authority_candidate_status": status,
        "candidate_row_count": len(rows),
        "operator_review_ready_count": review_ready,
        "direct_source_authority_ready_count": direct_ready,
        "homolog_source_authority_ready_count": homolog_ready,
        "source_authority_blocked_count": blocked,
        "operator_apply_allowed_count": sum(1 for row in rows if row["operator_apply_allowed"] is True),
        "claim_promotion_allowed_count": sum(1 for row in rows if row["claim_promotion_allowed"] is True),
        "protein_source_pdb": _artifact(protein_source_pdb),
        "protein_authority_ref": protein_authority_ref,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_row_folders(rows: list[dict[str, Any]]) -> None:
    by_folder: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_folder.setdefault(_text(row.get("audit_folder")), []).append(row)
    for folder_name, folder_rows in by_folder.items():
        folder = _resolve(folder_name)
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "source_authority_candidates.csv", folder_rows, ROW_COLUMNS)
        row = folder_rows[0]
        lines = [
            f"# CASP17 Complex Source Authority Candidate: {row['target_id']}",
            "",
            f"- status: `{row['candidate_status']}`",
            f"- ligand: `{row['ligand_id']}`",
            f"- protein authority: `{row['protein_authority_ref']}`",
            f"- ligand authority: `{row['ligand_authority_ref'] or '-'}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            f"- next action: {row['next_action']}",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
        (folder / "SOURCE_AUTHORITY.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Complex Source Authority Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['complex_source_authority_candidate_status']}`",
        f"- review-ready/direct/homolog/blocked: `{summary['operator_review_ready_count']}/{summary['direct_source_authority_ready_count']}/{summary['homolog_source_authority_ready_count']}/{summary['source_authority_blocked_count']}`",
        f"- operator-apply/claim-promotion allowed: `{summary['operator_apply_allowed_count']}/{summary['claim_promotion_allowed_count']}`",
        f"- protein source: `{summary['protein_source_pdb']}` `{summary['protein_authority_ref']}`",
        f"- first target: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| rank | target | status | ligand | source | direct | homolog | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['candidate_rank']} | `{row['target_id']}` | `{row['candidate_status']}` | "
            f"`{row['ligand_id']}` | `{row['ligand_source_dataset'] or '-'}` | "
            f"`{row['direct_tcruzi_pde_evidence']}` | `{row['homolog_seed_only']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | `missing_complex_seed_rows` |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_row_folders(payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build CASP17 historical seed complex source authority candidates."
    )
    parser.add_argument("--seed-inventory-json", default=DEFAULT_SEED_INVENTORY_JSON)
    parser.add_argument("--parameterization-json", default=DEFAULT_PARAMETERIZATION_JSON)
    parser.add_argument("--chembl-seed-csv", default=DEFAULT_CHEMBL_SEED_CSV)
    parser.add_argument("--bindingdb-seed-csv", default=DEFAULT_BINDINGDB_SEED_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
