import argparse
import datetime as dt
import json
from pathlib import Path

from tools import monitor_pxr_expansion as mon


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_render_scaffold_only_pxr_monitor(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.scaffold, "ROOT", tmp_path)
    monkeypatch.setattr(mon, "_auto_find_run_root", lambda: None)
    monkeypatch.setattr(mon, "_proc_lines", lambda pattern: [])

    _write_json(
        tmp_path / "config" / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_nuclear_receptor_pxr_v1_template",
            "status": "template_not_runnable",
            "primary_candidate": {
                "target": "PXR_NR1I2_BLIND",
                "native_pdb_path": "data/public_structures/pxr_1PXR.pdb",
            },
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
                "smoke_profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
            },
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "title": "Core Blind Set",
                    "tasks": [
                        {
                            "task_id": "nuclear_receptor_pxr_core_full",
                            "domain": "nuclear_receptor",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
                {
                    "set_id": "set2_expanded_ood",
                    "title": "Expanded OOD Set",
                    "tasks": [
                        {
                            "task_id": "nuclear_receptor_pxr_chembl50_full",
                            "domain": "nuclear_receptor",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
                {
                    "set_id": "set3_operational_smoke",
                    "title": "Operational Smoke Set",
                    "tasks": [
                        {
                            "task_id": "nuclear_receptor_pxr_smoke",
                            "domain": "nuclear_receptor",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
                            "ligand_sizes": "64",
                        }
                    ],
                },
            ],
        },
    )
    _write_json(
        tmp_path / "runs" / "pxr_runnable_packet_bootstrap_current.json",
        {
            "summary": {
                "ready_row_count": 1,
                "blocked_row_count": 9,
                "core_packet_ready": False,
                "ood_packet_ready": False,
                "fit_donor_policy_frozen": False,
                "runnable_before_data": False,
                "next_required_step": "Fill PXR target coordinates and ligand packets.",
            },
            "workbook_rows": [
                {
                    "step_id": "pxr_target_packet",
                    "status": "template_only",
                    "placeholder_row_count": 1,
                    "zero_pocket_row_count": 2,
                },
                {
                    "step_id": "pxr_target_metadata",
                    "status": "template_only",
                    "placeholder_row_count": 1,
                    "zero_pocket_row_count": 0,
                },
            ],
        },
    )
    for rel in [
        "data/public_structures/pxr_1PXR.pdb",
        "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
        "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
        "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".csv":
            path.write_text("target,ligand_id\n", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")
    for rel in [
        "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
        "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
    ]:
        _write_json(
            tmp_path / rel,
            {
                "targets": "PXR_NR1I2_BLIND",
                "dry_run": True,
                "template_profile": True,
                "template_execution_intent": "validate_only",
                "claim_ready": False,
                "target_native_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
                "ligand_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
                "calibration_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
                "ranking_labels_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
                "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
                "leakage_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
                "leakage_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
                "hard_decoy_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
                "hard_decoy_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
                "hard_decoy_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
                "hard_decoy_targets": "PXR_NR1I2_BLIND,EGFR_KINASE",
                "hard_decoy_fit_targets": "EGFR_KINASE",
            },
        )

    out = mon._render(
        argparse.Namespace(
            template_json="config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
            bootstrap_json="runs/pxr_runnable_packet_bootstrap_current.json",
            run_root="",
            loop=False,
            interval_sec=5.0,
            clear_screen=False,
            color=False,
        )
    )

    assert "PXR Expansion Monitor" in out
    assert "status: scaffold_only" in out
    assert "protocol_id: external_validation_biorxiv_nuclear_receptor_pxr_v1_template" in out
    assert "ready_rows=1  blocked_rows=9" in out
    assert "set1_core_blind: BLOCKED" in out
    assert "set2_expanded_ood: BLOCKED" in out
    assert "set3_operational_smoke: BLOCKED" in out
    assert "monitor: python3 tools/monitor_pxr_expansion.py" in out


def test_monitor_treats_ready_for_packet_as_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.scaffold, "ROOT", tmp_path)
    monkeypatch.setattr(mon, "_auto_find_run_root", lambda: None)
    monkeypatch.setattr(mon, "_proc_lines", lambda pattern: [])

    _write_json(
        tmp_path / "config" / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_nuclear_receptor_pxr_v1_template",
            "status": "template_not_runnable",
            "primary_candidate": {
                "target": "PXR_NR1I2_BLIND",
                "native_pdb_path": "data/public_structures/pxr_1PXR.pdb",
            },
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
                "smoke_profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
            },
            "sets": [
                {"set_id": "set1_core_blind", "tasks": [{"task_id": "nuclear_receptor_pxr_core_full", "ligand_sizes": "10000"}]},
                {"set_id": "set2_expanded_ood", "tasks": [{"task_id": "nuclear_receptor_pxr_chembl50_full", "ligand_sizes": "10000"}]},
                {"set_id": "set3_operational_smoke", "tasks": [{"task_id": "nuclear_receptor_pxr_smoke", "ligand_sizes": "64"}]},
            ],
        },
    )
    _write_json(
        tmp_path / "runs" / "pxr_runnable_packet_bootstrap_current.json",
        {
            "summary": {
                "ready_row_count": 3,
                "blocked_row_count": 7,
                "core_packet_ready": False,
                "ood_packet_ready": False,
                "fit_donor_policy_frozen": False,
                "runnable_before_data": False,
                "next_required_step": "Freeze the core packet and fit-donor policy.",
            },
            "workbook_rows": [
                {"step_id": "pxr_target_packet", "status": "ready_for_packet", "placeholder_row_count": 0, "zero_pocket_row_count": 0},
                {"step_id": "pxr_target_metadata", "status": "ready_for_packet", "placeholder_row_count": 0, "zero_pocket_row_count": 0},
            ],
        },
    )
    for rel in [
        "data/public_structures/pxr_1PXR.pdb",
        "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
        "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
        "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
        "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            _write_json(path, {})
        elif path.suffix == ".csv":
            path.write_text("target,ligand_id\n", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")

    out = mon._render(
        argparse.Namespace(
            template_json="config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
            bootstrap_json="runs/pxr_runnable_packet_bootstrap_current.json",
            run_root="",
            loop=False,
            interval_sec=5.0,
            clear_screen=False,
            color=False,
        )
    )

    assert "blocked_by=core_packet, fit_donor_policy" in out
    assert "blocked_by=ood_packet, fit_donor_policy" in out
