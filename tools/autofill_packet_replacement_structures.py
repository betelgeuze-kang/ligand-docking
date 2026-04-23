#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "aqp1": {
        "workbook_csv": "runs/aqp1_packet_replacement_workbook_current.csv",
        "draft_csv": "runs/aqp1_manual_verdict_draft_packet_current.csv",
        "workbook_json": "runs/aqp1_packet_replacement_workbook_current.json",
        "workbook_md": "runs/aqp1_packet_replacement_workbook_current.md",
        "out_json": "runs/aqp1_packet_structure_autofill_current.json",
        "out_csv": "runs/aqp1_packet_structure_autofill_current.csv",
        "out_md": "runs/aqp1_packet_structure_autofill_current.md",
        "title": "AQP1 Packet Structure Autofill",
        "workbook_title": "AQP1 Packet Replacement Workbook",
    },
    "ca2": {
        "workbook_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "draft_csv": "runs/ca2_packet_replacement_draft_current.csv",
        "workbook_json": "runs/ca2_packet_replacement_workbook_current.json",
        "workbook_md": "runs/ca2_packet_replacement_workbook_current.md",
        "out_json": "runs/ca2_packet_structure_autofill_current.json",
        "out_csv": "runs/ca2_packet_structure_autofill_current.csv",
        "out_md": "runs/ca2_packet_structure_autofill_current.md",
        "title": "CA2 Packet Structure Autofill",
        "workbook_title": "CA2 Packet Replacement Workbook",
    },
    "pxr": {
        "workbook_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "draft_csv": "runs/pxr_packet_replacement_draft_current.csv",
        "workbook_json": "runs/pxr_packet_replacement_workbook_current.json",
        "workbook_md": "runs/pxr_packet_replacement_workbook_current.md",
        "out_json": "runs/pxr_packet_structure_autofill_current.json",
        "out_csv": "runs/pxr_packet_structure_autofill_current.csv",
        "out_md": "runs/pxr_packet_structure_autofill_current.md",
        "title": "PXR Packet Structure Autofill",
        "workbook_title": "PXR Packet Replacement Workbook",
    },
}

PUBCHEM_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
    "{name}/property/CanonicalSMILES/JSON"
)


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _pubchem_structure_url(name: str) -> str:
    return PUBCHEM_URL.format(name=quote(name, safe=""))


def _required_missing_fields(row: dict[str, Any], family: str) -> list[str]:
    required = [
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_smiles",
        "replacement_scaffold",
    ]
    if family == "pxr" and str(row.get("apply_split_row", "")).strip().lower() == "yes":
        required.append("replacement_role")
    return [field for field in required if not str(row.get(field, "")).strip()]


def _smiles_features(smiles: str) -> dict[str, str]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES: {smiles}")
    canonical = Chem.MolToSmiles(mol, canonical=True)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
    if not scaffold:
        # Keep acyclic molecules actionable in packet workbooks instead of
        # leaving them structurally blank.
        scaffold = f"acyclic::{canonical}"
    return {
        "replacement_smiles": canonical,
        "replacement_molecular_weight": f"{Descriptors.MolWt(mol):.4f}",
        "replacement_logp": f"{Crippen.MolLogP(mol):.4f}",
        "replacement_h_donors": str(Lipinski.NumHDonors(mol)),
        "replacement_h_acceptors": str(Lipinski.NumHAcceptors(mol)),
        "replacement_rot_bonds": str(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "replacement_scaffold": scaffold,
    }


def resolve_pubchem_name(name: str, session: requests.Session | None = None) -> dict[str, str]:
    client = session or requests.Session()
    query_names = [name]
    if name.lower() == "sr12813":
        query_names.append("SR-12813")
    for query_name in query_names:
        response = client.get(_pubchem_structure_url(query_name), timeout=30)
        if response.status_code != 200:
            continue
        payload = response.json()
        props = payload.get("PropertyTable", {}).get("Properties", [])
        if not props:
            continue
        prop = props[0]
        smiles = (
            prop.get("CanonicalSMILES")
            or prop.get("ConnectivitySMILES")
            or prop.get("IsomericSMILES")
            or ""
        )
        if not smiles:
            continue
        features = _smiles_features(smiles)
        return {
            "resolved_query_name": query_name,
            "replacement_pubchem_cid": str(prop.get("CID", "")),
            "replacement_structure_resolution_status": "pubchem_name_resolved",
            "replacement_structure_resolution_url": _pubchem_structure_url(query_name),
            **features,
        }
    raise ValueError(f"Unable to resolve PubChem structure for name: {name}")


def build_payload(
    workbook_rows: list[dict[str, str]],
    draft_rows: list[dict[str, str]],
    family: str,
    resolver: Callable[[str], dict[str, str]],
) -> dict[str, Any]:
    draft_by_step = {str(row.get("packet_step", "")).strip(): row for row in draft_rows}
    updated_rows: list[dict[str, Any]] = []
    resolution_rows: list[dict[str, Any]] = []
    resolved_count = 0
    unchanged_count = 0
    failed_count = 0

    for workbook_row in workbook_rows:
        row = dict(workbook_row)
        packet_step = str(row.get("packet_step", "")).strip()
        draft = draft_by_step.get(packet_step, {})
        candidate_name = (
            str(draft.get("draft_candidate_ligand_name", "")).strip()
            or str(draft.get("candidate_name", "")).strip()
            or str(draft.get("replacement_candidate_name", "")).strip()
            or str(row.get("replacement_ligand_id", "")).strip()
        )
        candidate_kind = (
            str(draft.get("draft_candidate_source_kind", "")).strip()
            or str(draft.get("source_anchor", "")).strip()
            or str(draft.get("source_kind", "")).strip()
        )

        resolution_status = "no_candidate"
        resolution_error = ""
        resolved_fields: dict[str, str] = {}
        if candidate_name:
            try:
                resolved_fields = resolver(candidate_name)
                resolution_status = "resolved"
                resolved_count += 1
            except Exception as exc:  # pragma: no cover - exercised via fake resolver in unit tests
                resolution_status = "resolution_failed"
                resolution_error = str(exc)
                failed_count += 1
        else:
            unchanged_count += 1

        if resolved_fields:
            if not str(row.get("replacement_ligand_id", "")).strip():
                row["replacement_ligand_id"] = candidate_name
            if not str(row.get("replacement_source", "")).strip():
                source_kind = candidate_kind or "candidate_seed"
                row["replacement_source"] = f"pubchem_name_resolve_pending::{source_kind}"
            for key, value in resolved_fields.items():
                if not str(row.get(key, "")).strip():
                    row[key] = value
            note = str(row.get("notes", "")).strip()
            suffix = "Structure fields autofilled from PubChem name resolution; binding value and provenance still require manual verification."
            row["notes"] = f"{note} {suffix}".strip()
        elif resolution_status == "no_candidate":
            unchanged_count += 1

        missing = _required_missing_fields(row, family)
        row["required_missing_fields"] = ",".join(missing)
        row["row_ready_for_apply"] = "yes" if not missing else "no"

        updated_rows.append(row)
        resolution_rows.append(
            {
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "candidate_source_kind": candidate_kind,
                "resolution_status": resolution_status,
                "resolution_error": resolution_error,
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_source": str(row.get("replacement_source", "")).strip(),
                "replacement_smiles": str(row.get("replacement_smiles", "")).strip(),
                "replacement_scaffold": str(row.get("replacement_scaffold", "")).strip(),
                "required_missing_fields": row["required_missing_fields"],
            }
        )

    summary = {
        "family": family,
        "workbook_row_count": len(updated_rows),
        "resolved_row_count": resolved_count,
        "resolution_failed_row_count": failed_count,
        "structure_filled_row_count": sum(1 for row in updated_rows if str(row.get("replacement_smiles", "")).strip()),
        "rows_missing_only_binding_after_autofill": sum(
            1 for row in updated_rows if row.get("required_missing_fields", "") == "replacement_reference_binding_kcal_mol"
        ),
        "next_required_step": "Manually verify binding values and provenance for the autofilled rows, then promote only approved rows into claim-bearing packet edits.",
    }
    return {
        "summary": summary,
        "resolution_rows": resolution_rows,
        "workbook_rows": updated_rows,
    }


def _write_summary_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    summary = payload["summary"]
    lines = [
        f"# {title}",
        "",
        f"- family: `{summary['family']}`",
        f"- workbook_row_count: `{summary['workbook_row_count']}`",
        f"- resolved_row_count: `{summary['resolved_row_count']}`",
        f"- resolution_failed_row_count: `{summary['resolution_failed_row_count']}`",
        f"- structure_filled_row_count: `{summary['structure_filled_row_count']}`",
        f"- rows_missing_only_binding_after_autofill: `{summary['rows_missing_only_binding_after_autofill']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Resolution Rows",
        "",
        "| packet_step | candidate_name | resolution_status | replacement_source | required_missing_fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["resolution_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['candidate_name']}` | {row['resolution_status']} | `{row['replacement_source']}` | {row['required_missing_fields']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_workbook_json(path: Path, workbook_rows: list[dict[str, Any]], family: str) -> None:
    summary = {
        "target": workbook_rows[0].get("target", "") if workbook_rows else "",
        "workbook_row_count": len(workbook_rows),
        "ready_seed_row_count": sum(1 for row in workbook_rows if str(row.get("row_ready_for_apply", "")).lower() == "yes"),
        "packets_with_workbook_rows": len({str(row.get("packet", "")).strip() for row in workbook_rows}),
        "next_required_step": "Verify binding/provenance for autofilled rows before any claim-bearing apply step.",
        "family": family,
    }
    payload = {"summary": summary, "workbook_rows": workbook_rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_workbook_markdown(path: Path, workbook_rows: list[dict[str, Any]], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- workbook_row_count: `{len(workbook_rows)}`",
        f"- ready_row_count: `{sum(1 for row in workbook_rows if str(row.get('row_ready_for_apply', '')).lower() == 'yes')}`",
        "",
        "## Workbook",
        "",
        "| packet_step | replacement_ligand_id | replacement_source | replacement_smiles | replacement_scaffold | required_missing_fields |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in workbook_rows:
        lines.append(
            f"| {row.get('packet_step','')} | `{row.get('replacement_ligand_id','')}` | `{row.get('replacement_source','')}` | `{row.get('replacement_smiles','')}` | `{row.get('replacement_scaffold','')}` | {row.get('required_missing_fields','')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autofill low-risk structure fields into AQP1/CA2/PXR packet replacement workbooks.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--workbook-csv")
    parser.add_argument("--draft-csv")
    parser.add_argument("--workbook-json")
    parser.add_argument("--workbook-md")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("workbook_csv", "draft_csv", "workbook_json", "workbook_md", "out_json", "out_csv", "out_md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    workbook_rows = _read_csv(_resolve(args.workbook_csv))
    draft_rows = _read_csv(_resolve(args.draft_csv))
    session = requests.Session()
    payload = build_payload(
        workbook_rows,
        draft_rows,
        args.family,
        resolver=lambda name: resolve_pubchem_name(name, session=session),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    workbook_csv = _resolve(args.workbook_csv)
    workbook_json = _resolve(args.workbook_json)
    workbook_md = _resolve(args.workbook_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["resolution_rows"])
    _write_summary_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])
    _write_csv(workbook_csv, payload["workbook_rows"])
    _write_workbook_json(workbook_json, payload["workbook_rows"], args.family)
    _write_workbook_markdown(workbook_md, payload["workbook_rows"], FAMILY_DEFAULTS[args.family]["workbook_title"])


if __name__ == "__main__":
    main()
