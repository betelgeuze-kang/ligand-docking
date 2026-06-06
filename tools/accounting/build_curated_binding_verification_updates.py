#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

RT_KCAL_PER_MOL_298K = 0.00198720425864083 * 298.15

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "out_json": "runs/ca2_binding_verification_updates_current.json",
        "out_csv": "runs/ca2_binding_verification_updates_current.csv",
        "out_md": "runs/ca2_binding_verification_updates_current.md",
        "title": "CA2 Binding Verification Updates",
    },
    "pxr": {
        "out_json": "runs/pxr_binding_verification_updates_current.json",
        "out_csv": "runs/pxr_binding_verification_updates_current.csv",
        "out_md": "runs/pxr_binding_verification_updates_current.md",
        "title": "PXR Binding Verification Updates",
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _to_kcal_mol_from_nm(value_nm: float) -> str:
    delta_g = RT_KCAL_PER_MOL_298K * math.log(float(value_nm) * 1.0e-9)
    return f"{delta_g:.4f}"


def _activity_url(activity_id: int) -> str:
    return f"https://www.ebi.ac.uk/chembl/api/data/activity/{activity_id}.json"


def _document_url(document_chembl_id: str) -> str:
    return f"https://www.ebi.ac.uk/chembl/document_report_card/{document_chembl_id}/"


def build_payload(family: str) -> dict[str, Any]:
    if family == "ca2":
        rows = [
            {
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(12.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL20::activity_47560::assay_CHEMBL657848::Ki_12.0_nM::doc_CHEMBL1146805",
                "verify_source_url": _document_url("CHEMBL1146805"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 12.0 nM in esterase assay (ChEMBL assay CHEMBL657848; document CHEMBL1146805).",
            },
            {
                "packet_step": "core_binder_02",
                "replacement_ligand_id": "methazolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(14.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL19::activity_46288::assay_CHEMBL657848::Ki_14.0_nM::doc_CHEMBL1146805",
                "verify_source_url": _document_url("CHEMBL1146805"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 14.0 nM in esterase assay (ChEMBL assay CHEMBL657848; document CHEMBL1146805).",
            },
            {
                "packet_step": "core_binder_03",
                "replacement_ligand_id": "ethoxzolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(8.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL18::activity_68854::assay_CHEMBL657152::Ki_8.0_nM::doc_CHEMBL1133556",
                "verify_source_url": _document_url("CHEMBL1133556"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 8.0 nM against recombinant enzyme (ChEMBL assay CHEMBL657152; document CHEMBL1133556).",
            },
            {
                "packet_step": "ood_binder_01",
                "replacement_ligand_id": "dorzolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(9.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL218490::activity_110109::assay_CHEMBL657156::Ki_9.0_nM::doc_CHEMBL1136178",
                "verify_source_url": _document_url("CHEMBL1136178"),
                "verification_status": "verified_chembl_ki_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 9.0 nM in direct enzyme inhibition assay (ChEMBL assay CHEMBL657156; document CHEMBL1136178).",
            },
            {
                "packet_step": "ood_binder_02",
                "replacement_ligand_id": "brinzolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(3.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL220491::activity_138028::assay_CHEMBL657156::Ki_3.0_nM::doc_CHEMBL1136178",
                "verify_source_url": _document_url("CHEMBL1136178"),
                "verification_status": "verified_chembl_ki_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 3.0 nM in direct enzyme inhibition assay (ChEMBL assay CHEMBL657156; document CHEMBL1136178).",
            },
            {
                "packet_step": "ood_binder_03",
                "replacement_ligand_id": "chlorzolamide",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(12.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL360356::activity_1424016::assay_CHEMBL828932::Ki_12.0_nM::doc_CHEMBL1141985",
                "verify_source_url": _document_url("CHEMBL1141985"),
                "verification_status": "verified_chembl_ki_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 12.0 nM for chlorzolamide (ChEMBL assay CHEMBL828932; document CHEMBL1141985).",
            },
        ]
    elif family == "pxr":
        rows = [
            {
                "packet_step": "core_eval_binder_01",
                "replacement_ligand_id": "rifampicin",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(200.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL374478::activity_15448139::assay_CHEMBL3531878::EC50_200.0_nM::doc_CHEMBL3525965",
                "verify_source_url": _document_url("CHEMBL3525965"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human PXR ligand-binding domain competitive binding / TR-FRET EC50 200.0 nM (ChEMBL assay CHEMBL3531878; document CHEMBL3525965).",
            },
            {
                "packet_step": "core_eval_binder_02",
                "replacement_ligand_id": "clotrimazole",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(2700.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL104::activity_25049993::assay_CHEMBL5246992::EC50_2700.0_nM::doc_CHEMBL5244274",
                "verify_source_url": _document_url("CHEMBL5244274"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human PXR activation EC50 2700.0 nM (ChEMBL assay CHEMBL5246992; document CHEMBL5244274).",
            },
            {
                "packet_step": "core_fit_binder_01",
                "replacement_ligand_id": "hyperforin",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(27.0),
                "verify_provenance_source": "chembl_direct_binding::CHEMBL3401::CHEMBL1237210::activity_2532000::assay_CHEMBL1012196::Ki_27.0_nM::doc_CHEMBL1148111",
                "verify_source_url": _document_url("CHEMBL1148111"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human PXR competition binding Ki 27.0 nM by [3H]SR12813 displacement assay (ChEMBL assay CHEMBL1012196; document CHEMBL1148111).",
            },
            {
                "packet_step": "core_fit_binder_02",
                "replacement_ligand_id": "ketoconazole",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(18999.8),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL157101::activity_25223889::assay_CHEMBL5291845::AC50_18999.8_nM::doc_CHEMBL5291721",
                "verify_source_url": _document_url("CHEMBL5291721"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human NR1I2/PXR antagonist activity AC50 18999.8 nM in TR-FRET cell-free assay (ChEMBL assay CHEMBL5291845; document CHEMBL5291721).",
            },
            {
                "packet_step": "ood_eval_binder_02",
                "replacement_ligand_id": "troglitazone",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(8900.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL408::activity_15465515::assay_CHEMBL3531878::EC50_8900.0_nM::doc_CHEMBL3525965",
                "verify_source_url": _document_url("CHEMBL3525965"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human PXR ligand-binding domain competitive binding / TR-FRET EC50 8900.0 nM (ChEMBL assay CHEMBL3531878; document CHEMBL3525965). Treat as activity proxy, not direct Ki/Kd.",
            },
            {
                "packet_step": "ood_eval_binder_01",
                "replacement_ligand_id": "nifedipine",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(30000.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL193::activity_25188218::assay_CHEMBL5291846::AC50_30000.0_nM::doc_CHEMBL5291721",
                "verify_source_url": _document_url("CHEMBL5291721"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human NR1I2/PXR activity proxy AC50 30000.0 nM in TR-FRET cell-free assay (ChEMBL assay CHEMBL5291846; document CHEMBL5291721). Treat as activity proxy, not direct Ki/Kd.",
            },
            {
                "packet_step": "ood_eval_binder_03",
                "replacement_ligand_id": "dexamethasone",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(30000.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL384467::activity_25188566::assay_CHEMBL5291846::AC50_30000.0_nM::doc_CHEMBL5291721",
                "verify_source_url": _document_url("CHEMBL5291721"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human NR1I2/PXR activity proxy AC50 30000.0 nM in TR-FRET cell-free assay (ChEMBL assay CHEMBL5291846; document CHEMBL5291721). Treat as activity proxy, not direct Ki/Kd.",
            },
            {
                "packet_step": "ood_fit_binder_02",
                "replacement_ligand_id": "sr12813",
                "verify_reference_binding_kcal_mol": _to_kcal_mol_from_nm(440.0),
                "verify_provenance_source": "chembl_activity_proxy::CHEMBL3401::CHEMBL458767::activity_15463738::assay_CHEMBL3531878::EC50_440.0_nM::doc_CHEMBL3525965",
                "verify_source_url": _document_url("CHEMBL3525965"),
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human PXR ligand-binding domain competitive binding / TR-FRET EC50 440.0 nM (ChEMBL assay CHEMBL3531878; document CHEMBL3525965). Treat as activity proxy, not direct Ki/Kd.",
            },
        ]
    else:  # pragma: no cover
        raise ValueError(f"Unsupported family: {family}")

    return {
        "summary": {
            "family": family,
            "row_count": len(rows),
            "verified_row_count": len(rows),
            "next_required_step": "Copy verified fields into the live verification sheet, then manually review before any workbook apply step.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- family: `{payload['summary']['family']}`",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- verified_row_count: `{payload['summary']['verified_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Verified Rows",
        "",
        "| packet_step | ligand | verify_reference_binding_kcal_mol | verification_status |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['verify_reference_binding_kcal_mol']} | `{row['verification_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build curated binder verification updates for CA2 or PXR.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("out_json", "out_csv", "out_md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    payload = build_payload(args.family)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
