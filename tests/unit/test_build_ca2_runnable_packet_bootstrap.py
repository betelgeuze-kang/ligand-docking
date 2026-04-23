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


def test_build_ca2_runnable_packet_bootstrap(tmp_path: Path) -> None:
    config = tmp_path / "config"
    runs = tmp_path / "runs"

    _write_csv(
        config / "real_drug_targets_blind_ca2_zn_v1.csv",
        ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
        [["CARBONIC_ANHYDRASE_2_ZN_BLIND", "data/1CA2.pdb", "1CA2", "0.0", "0.0", "0.0", "template TODO"]],
    )
    _write_csv(
        config / "ligand_target_metadata_blind_ca2_zn_v1.csv",
        ["target", "target_family", "sequence", "pocket_fingerprint"],
        [["CARBONIC_ANHYDRASE_2_ZN_BLIND", "METALLOENZYME", "TODO_SEQUENCE_P00918", "zn_active_site|metal"]],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "role"],
        [],
    )
    _write_csv(
        config / "ligand_meta_blind_ca2_zn_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "role"],
        [],
    )
    _write_csv(
        config / "ligand_meta_blind_ca2_zn_chembl50_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [],
    )

    _write_json(
        config / "ligand_htvs_blind_ca2_zn_v1.json",
        {
            "version": "ligand_htvs_blind_ca2_zn_v1",
            "targets": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
            "target_native_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
            "hard_decoy_fit_targets": "EGFR_KINASE",
        },
    )
    _write_json(
        config / "ligand_htvs_blind_ca2_zn_chembl50_v1.json",
        {
            "version": "ligand_htvs_blind_ca2_zn_chembl50_v1",
            "targets": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
            "target_native_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
            "hard_decoy_fit_targets": "EGFR_KINASE",
        },
    )
    _write_json(
        config / "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template",
            "primary_candidate": {"target": "CARBONIC_ANHYDRASE_2_ZN_BLIND"},
            "required_artifacts": {
                "target_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
                "target_metadata_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
                "core_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
                "core_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
                "core_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
                "ood_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
                "ood_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
                "ood_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
                "core_profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
                "ood_profile_json": "config/ligand_htvs_blind_ca2_zn_chembl50_v1.json",
                "smoke_profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
            },
            "placeholder_policies": {
                "fit_donor_target": "EGFR_KINASE",
                "fit_donor_policy_state": "placeholder_only_until_ca2_fit_packet_is_frozen",
            },
        },
    )

    out_json = runs / "ca2_runnable_packet_bootstrap_current.json"
    out_csv = runs / "ca2_runnable_packet_bootstrap_current.csv"
    out_md = runs / "ca2_runnable_packet_bootstrap_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_ca2_runnable_packet_bootstrap.py"),
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
    assert payload["summary"]["workbook_row_count"] == 10
    assert payload["summary"]["ready_row_count"] == 0
    assert payload["summary"]["blocked_row_count"] == 10
    assert payload["summary"]["runnable_before_data"] is False
    assert payload["placeholder_policies"]["fit_donor_target"] == "EGFR_KINASE"
    assert payload["csv_inspections"]["target_csv"]["zero_pocket_row_count"] == 1
    assert payload["csv_inspections"]["target_metadata_csv"]["placeholder_row_count"] == 1
    assert payload["csv_inspections"]["core_reference_csv"]["data_row_count"] == 0
    assert payload["json_inspections"]["core_profile_json"]["hard_decoy_fit_targets"] == "EGFR_KINASE"

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 10
    target_row = next(row for row in rows if row["artifact_key"] == "target_csv")
    assert target_row["status"] == "template_only"
    assert target_row["zero_pocket_row_count"] == "1"
    ref_row = next(row for row in rows if row["artifact_key"] == "core_reference_csv")
    assert ref_row["status"] == "header_only"
    profile_row = next(row for row in rows if row["artifact_key"] == "core_profile_json")
    assert profile_row["status"] == "scaffold_only"

    md_text = out_md.read_text(encoding="utf-8")
    assert "CA2 Runnable Packet Bootstrap" in md_text
    assert "## Placeholder Policies" in md_text
    assert "EGFR_KINASE" in md_text
    assert "Core ligand reference packet has only headers" in md_text


def test_build_ca2_runnable_packet_bootstrap_ignores_helper_zero_pocket_row(tmp_path: Path) -> None:
    config = tmp_path / "config"
    runs = tmp_path / "runs"

    _write_csv(
        config / "real_drug_targets_blind_ca2_zn_v1.csv",
        ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
        [
            ["EGFR_KINASE", "data/egfr.pdb", "1M17", "0.0", "0.0", "0.0", "helper row"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "data/1CA2.pdb", "1CA2", "-6.788", "-1.621", "15.381", "frozen CA2"],
        ],
    )
    _write_csv(
        config / "ligand_target_metadata_blind_ca2_zn_v1.csv",
        ["target", "target_family", "sequence", "pocket_fingerprint"],
        [
            ["EGFR_KINASE", "TYR_KINASE", "AAAA", "kinase_atp"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "METALLOENZYME", "SHHWG", "zn_active_site|metal"],
        ],
    )
    for rel in [
        "ligand_binding_reference_blind_ca2_zn_v1.csv",
        "ligand_eval_splits_blind_ca2_zn_v1.csv",
        "ligand_meta_blind_ca2_zn_v1.csv",
        "ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        "ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        "ligand_meta_blind_ca2_zn_chembl50_v1.csv",
    ]:
        header = {
            "ligand_binding_reference_blind_ca2_zn_v1.csv": ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
            "ligand_eval_splits_blind_ca2_zn_v1.csv": ["target", "ligand_id", "role"],
            "ligand_meta_blind_ca2_zn_v1.csv": ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
            "ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv": ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
            "ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv": ["target", "ligand_id", "role"],
            "ligand_meta_blind_ca2_zn_chembl50_v1.csv": ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        }[rel]
        _write_csv(config / rel, header, [])

    _write_json(
        config / "ligand_htvs_blind_ca2_zn_v1.json",
        {"version": "ligand_htvs_blind_ca2_zn_v1", "targets": "CARBONIC_ANHYDRASE_2_ZN_BLIND", "hard_decoy_fit_targets": "EGFR_KINASE"},
    )
    _write_json(
        config / "ligand_htvs_blind_ca2_zn_chembl50_v1.json",
        {"version": "ligand_htvs_blind_ca2_zn_chembl50_v1", "targets": "CARBONIC_ANHYDRASE_2_ZN_BLIND", "hard_decoy_fit_targets": "EGFR_KINASE"},
    )
    _write_json(
        config / "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template",
            "primary_candidate": {"target": "CARBONIC_ANHYDRASE_2_ZN_BLIND"},
            "required_artifacts": {
                "target_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
                "target_metadata_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
                "core_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
                "core_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
                "core_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
                "ood_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
                "ood_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
                "ood_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
                "core_profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
                "ood_profile_json": "config/ligand_htvs_blind_ca2_zn_chembl50_v1.json",
                "smoke_profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
            },
            "placeholder_policies": {"fit_donor_target": "EGFR_KINASE", "fit_donor_policy_state": "placeholder_only_until_ca2_fit_packet_is_frozen"},
        },
    )

    out_json = runs / "ca2_runnable_packet_bootstrap_current.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_ca2_runnable_packet_bootstrap.py"),
            "--template-json",
            "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
            "--out-json",
            str(out_json),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["target_packet_ready"] is True
    assert payload["summary"]["target_metadata_ready"] is True
    target_row = next(row for row in payload["workbook_rows"] if row["step_id"] == "ca2_target_packet")
    assert target_row["status"] == "ready_for_packet"
