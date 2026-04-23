#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RT_KCAL_MOL_298K = 0.00198720425864083 * 298.15

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "csv": "runs/ca2_binding_verification_sheet_current.csv",
        "json": "runs/ca2_binding_verification_sheet_current.json",
        "md": "runs/ca2_binding_verification_sheet_current.md",
        "title": "CA2 Binding Verification Sheet",
    },
    "pxr": {
        "csv": "runs/pxr_binding_verification_sheet_current.csv",
        "json": "runs/pxr_binding_verification_sheet_current.json",
        "md": "runs/pxr_binding_verification_sheet_current.md",
        "title": "PXR Binding Verification Sheet",
    },
}

EVIDENCE: dict[str, dict[str, dict[str, Any]]] = {
    "ca2": {
        "core_binder_01": {
            "activity_type": "Ki",
            "value_nM": 12.0,
            "target_chembl_id": "CHEMBL205",
            "molecule_chembl_id": "CHEMBL20",
            "activity_id": "47560",
            "assay_chembl_id": "CHEMBL657848",
            "document_chembl_id": "CHEMBL1146805",
            "document_title": (
                "Carbonic anhydrase inhibitors. Inhibition of cytosolic isozyme XIII with aromatic "
                "and heterocyclic sulfonamides: a novel target for the drug design."
            ),
            "verification_status": "verified_chembl_binding",
            "verification_note": "Verified direct human CA2 Ki; ΔG proxy computed from Ki at 298.15 K.",
        },
        "core_binder_02": {
            "activity_type": "Ki",
            "value_nM": 14.0,
            "target_chembl_id": "CHEMBL205",
            "molecule_chembl_id": "CHEMBL19",
            "activity_id": "46288",
            "assay_chembl_id": "CHEMBL657848",
            "document_chembl_id": "CHEMBL1146805",
            "document_title": (
                "Carbonic anhydrase inhibitors. Inhibition of cytosolic isozyme XIII with aromatic "
                "and heterocyclic sulfonamides: a novel target for the drug design."
            ),
            "verification_status": "verified_chembl_binding",
            "verification_note": "Verified direct human CA2 Ki; ΔG proxy computed from Ki at 298.15 K.",
        },
        "core_binder_03": {
            "activity_type": "Ki",
            "value_nM": 8.0,
            "target_chembl_id": "CHEMBL205",
            "molecule_chembl_id": "CHEMBL18",
            "activity_id": "68854",
            "assay_chembl_id": "CHEMBL657152",
            "document_chembl_id": "CHEMBL1133556",
            "document_title": (
                "Carbonic anhydrase inhibitors: water-soluble 4-sulfamoylphenylthioureas as topical "
                "intraocular pressure-lowering agents with long-lasting effects."
            ),
            "verification_status": "verified_chembl_binding",
            "verification_note": "Verified direct human CA2 Ki; ΔG proxy computed from Ki at 298.15 K.",
        },
    },
    "pxr": {
        "core_eval_binder_01": {
            "activity_type": "EC50",
            "value_nM": 200.0,
            "target_chembl_id": "CHEMBL3401",
            "molecule_chembl_id": "CHEMBL374478",
            "activity_id": "15448139",
            "assay_chembl_id": "CHEMBL3531878",
            "document_chembl_id": "CHEMBL3525965",
            "document_title": "Identification of clinically used drugs that activate pregnane X receptors.",
            "verification_status": "verified_chembl_activity_proxy",
            "verification_note": "Verified human PXR EC50 activity proxy; ΔG proxy computed from EC50 at 298.15 K.",
        },
        "core_eval_binder_02": {
            "activity_type": "EC50",
            "value_nM": 2700.0,
            "target_chembl_id": "CHEMBL3401",
            "molecule_chembl_id": "CHEMBL104",
            "activity_id": "25049993",
            "assay_chembl_id": "CHEMBL5246992",
            "document_chembl_id": "CHEMBL5244274",
            "document_title": (
                "Designing Out PXR Activity on Drug Discovery Projects: A Review of Structure-Based "
                "Methods, Empirical and Computational Approaches."
            ),
            "verification_status": "verified_chembl_activity_proxy",
            "verification_note": "Verified human PXR EC50 activity proxy; ΔG proxy computed from EC50 at 298.15 K.",
        },
        "core_fit_binder_01": {
            "activity_type": "Ki",
            "value_nM": 27.0,
            "target_chembl_id": "CHEMBL3401",
            "molecule_chembl_id": "CHEMBL1237210",
            "activity_id": "2532000",
            "assay_chembl_id": "CHEMBL1012196",
            "document_chembl_id": "CHEMBL1148111",
            "document_title": (
                "Synthesis and biological evaluation of hyperforin analogues. Part I. "
                "Modification of the enolized cyclohexanedione moiety."
            ),
            "verification_status": "verified_chembl_binding",
            "verification_note": "Verified direct human PXR Ki; ΔG proxy computed from Ki at 298.15 K.",
        },
        "core_fit_binder_02": {
            "activity_type": "AC50",
            "value_nM": 18999.8,
            "target_chembl_id": "CHEMBL3401",
            "molecule_chembl_id": "CHEMBL157101",
            "activity_id": "25223889",
            "assay_chembl_id": "CHEMBL5291845",
            "document_chembl_id": "CHEMBL5291721",
            "document_title": (
                "A preclinical secondary pharmacology resource illuminates target-adverse drug reaction "
                "associations of marketed drugs."
            ),
            "verification_status": "verified_chembl_activity_proxy",
            "verification_note": "Verified human PXR AC50 activity proxy; ΔG proxy computed from AC50 at 298.15 K.",
        },
    },
}


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


def _document_url(document_chembl_id: str) -> str:
    return f"https://www.ebi.ac.uk/chembl/document_report_card/{document_chembl_id}/"


def _dg_from_nm(value_nM: float) -> str:
    delta_g = RT_KCAL_MOL_298K * math.log(value_nM * 1e-9)
    return f"{delta_g:.4f}"


def _provenance_source(record: dict[str, Any]) -> str:
    prefix = (
        "chembl_direct_binding"
        if str(record["activity_type"]).upper() == "KI"
        else "chembl_activity_proxy"
    )
    return (
        f"{prefix}::{record['target_chembl_id']}::{record['molecule_chembl_id']}::"
        f"activity_{record['activity_id']}::assay_{record['assay_chembl_id']}::"
        f"{record['activity_type']}_{record['value_nM']}_nM::doc_{record['document_chembl_id']}"
    )


def build_payload(rows: list[dict[str, str]], family: str) -> dict[str, Any]:
    evidence_rows = EVIDENCE[family]
    verified_count = 0
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        record = evidence_rows.get(packet_step)
        if not record:
            continue
        row["verify_reference_binding_kcal_mol"] = _dg_from_nm(float(record["value_nM"]))
        row["verify_provenance_source"] = _provenance_source(record)
        row["verify_source_url"] = _document_url(str(record["document_chembl_id"]))
        row["verification_status"] = str(record["verification_status"])
        note = str(row.get("notes", "")).strip()
        row["notes"] = (
            f"{note} {record['verification_note']} Source title: {record['document_title']}"
        ).strip()
        verified_count += 1
    summary = {
        "family": family,
        "row_count": len(rows),
        "verified_row_count": verified_count,
        "remaining_pending_row_count": len(rows) - verified_count,
        "next_required_step": (
            "Copy verified binder rows into the authoritative replacement workbook once manual review is complete, "
            "then continue with remaining pending non-binder or OOD rows."
        ),
    }
    return {"summary": summary, "sheet_rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- verified_row_count: `{payload['summary']['verified_row_count']}`",
        f"- remaining_pending_row_count: `{payload['summary']['remaining_pending_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Verification Rows",
        "",
        "| priority_rank | packet_step | replacement_ligand_id | verify_reference_binding_kcal_mol | verification_status | verify_source_url |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["sheet_rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | "
            f"{row['verify_reference_binding_kcal_mol']} | `{row['verification_status']}` | `{row['verify_source_url']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply curated binding/provenance verification values into current family verification sheets.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--csv")
    parser.add_argument("--json")
    parser.add_argument("--md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("csv", "json", "md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.csv))
    payload = build_payload(rows, args.family)
    out_csv = _resolve(args.csv)
    out_json = _resolve(args.json)
    out_md = _resolve(args.md)
    _write_csv(out_csv, payload["sheet_rows"])
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
