from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_ca2_ligand_packet_fill_workbook(tmp_path: Path) -> None:
    config = tmp_path / "config"
    runs = tmp_path / "runs"

    _write_csv(
        config / "ligand_binding_reference_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["EGFR_KINASE", "erlotinib", "-9.2", "1", "literature_proxy_v2"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_placeholder_binder_01", "-8.0", "1", "template_placeholder_needs_curation"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_real_candidate_01", "-7.2", "1", "manual_curated_note"],
        ],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "role"],
        [
            ["EGFR_KINASE", "erlotinib", "fit"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_placeholder_binder_01", "far_ood_eval"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_real_candidate_01", "core_eval"],
        ],
    )
    _write_csv(
        config / "ligand_meta_blind_ca2_zn_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["ca2_placeholder_binder_01", "O=S(=O)(N)c1ccc(cc1)N", "172.2", "-0.7", "2", "3", "1", "template_placeholder"],
            ["ca2_real_candidate_01", "C1=CC=NC=C1", "79.1", "0.5", "0", "1", "0", "pyridine"],
        ],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_ood_binder_01", "-8.4", "1", "template_placeholder_needs_curation"],
        ],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "role"],
        [],
    )
    _write_csv(
        config / "ligand_meta_blind_ca2_zn_chembl50_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["ca2_ood_binder_01", "O=S(=O)(N)c1ccc(cc1)N", "172.2", "-0.7", "2", "3", "1", "template_placeholder"],
        ],
    )
    _write_json(
        config / "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
        {
            "placeholder_policies": {
                "fit_donor_target": "EGFR_KINASE",
                "fit_donor_policy_state": "placeholder_only_until_ca2_fit_packet_is_frozen",
            }
        },
    )

    out_json = runs / "ca2_ligand_packet_fill_workbook_current.json"
    out_csv = runs / "ca2_ligand_packet_fill_workbook_current.csv"
    out_md = runs / "ca2_ligand_packet_fill_workbook_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_ca2_ligand_packet_fill_workbook.py"),
            "--template-json",
            "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_count"] == 2
    assert payload["summary"]["ligand_row_count"] == 3
    assert payload["summary"]["packets_blocked"] == 2
    assert payload["summary"]["placeholder_row_count"] >= 2
    assert payload["summary"]["fit_donor_carryover_candidate_count"] == 0
    assert payload["summary"]["most_common_next_action"]
    assert payload["placeholder_policies"]["fit_donor_target"] == "EGFR_KINASE"

    core_summary = next(row for row in payload["packet_summaries"] if row["packet"] == "core")
    assert core_summary["ligand_row_count"] == 2
    assert core_summary["status"] == "partially_curated"

    ood_summary = next(row for row in payload["packet_summaries"] if row["packet"] == "ood")
    assert ood_summary["status"] == "placeholder_only"

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 3
    real_core = next(row for row in rows if row["ligand_id"] == "ca2_real_candidate_01")
    assert real_core["packet"] == "core"
    assert real_core["in_reference"] == "yes"
    assert real_core["in_split"] == "yes"
    assert real_core["in_meta"] == "yes"
    assert real_core["target_mismatch"] == "no"

    ood_row = next(row for row in rows if row["ligand_id"] == "ca2_ood_binder_01")
    assert ood_row["in_reference"] == "yes"
    assert ood_row["in_split"] == "no"
    assert ood_row["meta_placeholder"] == "yes"

    md_text = out_md.read_text(encoding="utf-8")
    assert "CA2 Ligand Packet Fill Workbook" in md_text
    assert "## Placeholder Policies" in md_text
    assert "## Packet Summary" in md_text
    assert "Curate ligand ledger" in md_text
    assert "ca2_real_candidate_01" in md_text
