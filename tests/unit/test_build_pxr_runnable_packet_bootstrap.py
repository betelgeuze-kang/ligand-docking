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


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_pxr_runnable_packet_bootstrap(tmp_path: Path) -> None:
    config = tmp_path / "config"
    runs = tmp_path / "runs"

    _write_csv(
        config / "real_drug_targets_blind_pxr_nr1i2_v1.csv",
        ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
        [["PXR_NR1I2_BLIND", "data/pxr.pdb", "TODO_PXR_PDB_ID", "0.0", "0.0", "0.0", "template TODO"]],
    )
    _write_csv(
        config / "ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        ["target", "target_family", "sequence", "pocket_fingerprint"],
        [["PXR_NR1I2_BLIND", "NUCLEAR_RECEPTOR", "TODO_UNIPROT_O75469_SEQUENCE", "nuclear_receptor_lbp|TODO"]],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [["PXR_NR1I2_BLIND", "pxr_fit_ligand_01", "TODO_BINDING_KCAL", "1", "pxr_blind_proxy_v1"]],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        ["target", "ligand_id", "role"],
        [["PXR_NR1I2_BLIND", "pxr_fit_ligand_01", "fit"]],
    )
    _write_csv(
        config / "ligand_meta_blind_pxr_nr1i2_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [["pxr_fit_ligand_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"]],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [["PXR_NR1I2_BLIND", "pxr_ood_ligand_01", "TODO_BINDING_KCAL", "1", "pxr_blind_proxy_v1"]],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        ["target", "ligand_id", "role"],
        [["PXR_NR1I2_BLIND", "pxr_ood_ligand_01", "far_ood_eval"]],
    )
    _write_csv(
        config / "ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [["pxr_ood_ligand_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"]],
    )

    _write_json(
        config / "ligand_htvs_blind_pxr_nr1i2_v1.json",
        {
            "version": "ligand_htvs_blind_pxr_nr1i2_v1",
            "targets": "PXR_NR1I2_BLIND",
            "target_native_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
            "hard_decoy_fit_targets": "PXR_NR1I2_BLIND",
            "dry_run": True,
        },
    )
    _write_json(
        config / "ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
        {
            "version": "ligand_htvs_blind_pxr_nr1i2_chembl50_v1",
            "targets": "PXR_NR1I2_BLIND",
            "target_native_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
            "hard_decoy_fit_targets": "PXR_NR1I2_BLIND",
            "dry_run": True,
        },
    )
    _write_json(
        config / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_nuclear_receptor_pxr_v1_template",
            "primary_candidate": {"target": "PXR_NR1I2_BLIND"},
            "required_artifacts": {
                "target_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
                "target_metadata_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
                "core_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
                "core_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
                "core_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
                "ood_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
                "ood_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
                "ood_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
                "core_profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
                "ood_profile_json": "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
                "smoke_profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json"
            },
            "scaffold_status": {
                "core_profile_present": True,
                "ood_profile_present": True,
                "core_profile_dry_run_only": True,
                "ood_profile_dry_run_only": True,
                "ready_for_validate_only": False,
                "claim_ready": False
            }
        },
    )

    out_json = runs / "pxr_runnable_packet_bootstrap_current.json"
    out_csv = runs / "pxr_runnable_packet_bootstrap_current.csv"
    out_md = runs / "pxr_runnable_packet_bootstrap_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_pxr_runnable_packet_bootstrap.py"),
            "--template-json",
            "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
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
    assert payload["summary"]["workbook_row_count"] == 11
    assert payload["summary"]["blocked_row_count"] == 9
    assert payload["summary"]["ready_row_count"] == 2
    assert payload["summary"]["runnable_before_data"] is False
    assert payload["summary"]["claim_ready"] is False
    assert payload["csv_inspections"]["target_csv"]["zero_pocket_row_count"] == 1
    assert payload["csv_inspections"]["target_metadata_csv"]["placeholder_row_count"] == 1
    assert payload["csv_inspections"]["ood_reference_csv"]["exists"] is True
    assert payload["json_inspections"]["core_profile_json"]["dry_run"] is True
    assert payload["json_inspections"]["ood_profile_json"]["dry_run"] is True

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 11
    target_row = next(row for row in rows if row["artifact_key"] == "target_csv")
    assert target_row["status"] == "template_only"
    ood_ref_row = next(row for row in rows if row["artifact_key"] == "ood_reference_csv")
    assert ood_ref_row["status"] == "template_only"
    profile_row = next(row for row in rows if row["artifact_key"] == "core_profile_json")
    assert profile_row["status"] == "scaffold_only"
    policy_row = next(row for row in rows if row["artifact_key"] == "fit_donor_policy")
    assert policy_row["status"] == "policy_pending"

    md_text = out_md.read_text(encoding="utf-8")
    _contains_tokens(md_text, "pxr", "runnable", "packet", "bootstrap")
    _contains_tokens(md_text, "scaffold", "status")
    _contains_tokens(md_text, "freeze", "pocket_x", "pocket_y", "pocket_z")
    _contains_tokens(md_text, "fit-donor", "policy")

    workbook_csv = runs / "pxr_packet_replacement_workbook_current.csv"
    _write_csv(
        workbook_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
            "replacement_ligand_id",
            "replacement_reference_binding_kcal_mol",
            "replacement_is_binder",
            "replacement_source",
            "replacement_role",
            "replacement_smiles",
            "replacement_scaffold",
            "required_missing_fields",
            "row_ready_for_apply",
        ],
        [
            ["core", "core_fit_binder_01", "core_fit_1", "core_fit_1", "-8.0", "1", "chembl_direct_binding::x", "fit", "CCO", "core_fit", "", "yes"],
            ["core", "core_eval_binder_01", "core_eval_1", "core_eval_1", "-7.5", "1", "chembl_activity_proxy::x", "far_ood_eval", "CCN", "core_eval", "", "yes"],
            ["core", "core_eval_non_binder_01", "core_decoy_1", "core_decoy_1", "-5.0", "0", "chembl_direct_binding::x", "far_ood_eval", "CCC", "core_decoy", "", "yes"],
            ["ood", "ood_fit_binder_01", "ood_fit_1", "ood_fit_1", "-8.2", "1", "chembl_direct_binding::x", "fit", "COC", "ood_fit", "", "yes"],
            ["ood", "ood_eval_binder_01", "ood_eval_1", "ood_eval_1", "-7.8", "1", "chembl_activity_proxy::x", "far_ood_eval", "CNC", "ood_eval", "", "yes"],
            ["ood", "ood_eval_non_binder_01", "ood_decoy_1", "ood_decoy_1", "-5.2", "0", "chembl_direct_binding::x", "far_ood_eval", "CO", "ood_decoy", "", "yes"],
        ],
    )
    rerun_json = runs / "pxr_runnable_packet_bootstrap_with_freeze_current.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_pxr_runnable_packet_bootstrap.py"),
            "--template-json",
            "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
            "--workbook-csv",
            str(workbook_csv),
            "--out-json",
            str(rerun_json),
            "--out-csv",
            str(runs / "pxr_runnable_packet_bootstrap_with_freeze_current.csv"),
            "--out-md",
            str(runs / "pxr_runnable_packet_bootstrap_with_freeze_current.md"),
        ],
        check=True,
        cwd=tmp_path,
    )
    rerun_payload = json.loads(rerun_json.read_text(encoding="utf-8"))
    assert rerun_payload["summary"]["curated_freeze_row_count"] == 6
    assert rerun_payload["summary"]["curated_freeze_blocked_row_count"] == 0
    assert rerun_payload["summary"]["claim_ready"] is True
