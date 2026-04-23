from __future__ import annotations

import json
from pathlib import Path

from tools.run_pxr_expansion_scaffold_check import main


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(root: Path, *, ood_target: str = "PXR_NR1I2_BLIND") -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    template = {
        "protocol_id": "external_validation_biorxiv_nuclear_receptor_pxr_v1_template",
        "protocol_title": "Nuclear Receptor Expansion Template for PXR/NR1I2",
        "protocol_version": "template_v1",
        "status": "template_not_runnable",
        "description": "Planning template for adding a nuclear receptor family.",
        "primary_candidate": {
            "target": "PXR_NR1I2_BLIND",
            "native_pdb_path": "data/native/live_auto_nuclear_receptor_subfamily_1_group_i_member_2_o75469.pdb",
            "secondary_references": ["ESR1", "NR3C1"],
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
        "scaffold_status": {
            "core_profile_present": True,
            "ood_profile_present": True,
            "core_profile_dry_run_only": True,
            "ood_profile_dry_run_only": True,
            "ready_for_validate_only": False,
            "claim_ready": False,
        },
        "sets": [
            {
                "set_id": "set1_core_blind",
                "tasks": [
                    {
                        "task_id": "nuclear_receptor_pxr_core_full",
                        "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
                        "ligand_sizes": "10000",
                    }
                ],
            },
            {
                "set_id": "set2_expanded_ood",
                "tasks": [
                    {
                        "task_id": "nuclear_receptor_pxr_chembl50_full",
                        "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json",
                        "ligand_sizes": "10000",
                    }
                ],
            },
            {
                "set_id": "set3_operational_smoke",
                "tasks": [
                    {
                        "task_id": "nuclear_receptor_pxr_smoke",
                        "profile_json": "config/ligand_htvs_blind_pxr_nr1i2_v1.json",
                        "ligand_sizes": "64",
                    }
                ],
            },
        ],
    }
    _write_json(config_dir / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json", template)

    core_profile = {
        "version": "ligand_htvs_blind_pxr_nr1i2_v1",
        "description": "Template-only nuclear-receptor blind profile for PXR_NR1I2_BLIND. `dry_run: true` keeps this scaffold in validate-only mode, and `template_profile: true` marks it as non-claim and non-production even if `dry_run` is toggled later.",
        "targets": "PXR_NR1I2_BLIND",
        "run_scope": "full",
        "dry_run": True,
        "template_profile": True,
        "template_execution_intent": "validate_only",
        "claim_ready": False,
        "target_native_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
        "native_path_col": "native_pdb_path",
        "ligand_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "calibration_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "ranking_labels_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        "leakage_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "leakage_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
        "hard_decoy_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "hard_decoy_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
        "hard_decoy_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "hard_decoy_targets": "PXR_NR1I2_BLIND",
        "hard_decoy_fit_targets": "PXR_NR1I2_BLIND",
    }
    _write_json(config_dir / "ligand_htvs_blind_pxr_nr1i2_v1.json", core_profile)

    ood_profile = {
        "version": "ligand_htvs_blind_pxr_nr1i2_chembl50_v1",
        "description": "Template-only nuclear-receptor expanded-OOD profile for PXR_NR1I2_BLIND. `dry_run: true` keeps this scaffold in validate-only mode, and `template_profile: true` marks it as non-claim and non-production even if `dry_run` is toggled later.",
        "targets": ood_target,
        "run_scope": "full",
        "dry_run": True,
        "template_profile": True,
        "template_execution_intent": "validate_only",
        "claim_ready": False,
        "target_native_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
        "native_path_col": "native_pdb_path",
        "ligand_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "calibration_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "ranking_labels_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "leakage_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "leakage_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        "hard_decoy_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "hard_decoy_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        "hard_decoy_target_meta_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
        "hard_decoy_targets": ood_target,
        "hard_decoy_fit_targets": ood_target,
    }
    _write_json(config_dir / "ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json", ood_profile)

    _write_text(config_dir / "real_drug_targets_blind_pxr_nr1i2_v1.csv", "target,native_pdb_path\nPXR_NR1I2_BLIND,data/native/pxr.pdb\n")
    _write_text(config_dir / "ligand_target_metadata_blind_pxr_nr1i2_v1.csv", "target\nPXR_NR1I2_BLIND\n")
    _write_text(config_dir / "ligand_binding_reference_blind_pxr_nr1i2_v1.csv", "target,ligand_id\nPXR_NR1I2_BLIND,pxr_fit_ligand_1\n")
    _write_text(config_dir / "ligand_eval_splits_blind_pxr_nr1i2_v1.csv", "target,ligand_id,role\nPXR_NR1I2_BLIND,pxr_fit_ligand_1,fit\n")
    _write_text(config_dir / "ligand_meta_blind_pxr_nr1i2_v1.csv", "ligand_id\npxr_fit_ligand_1\n")


def test_run_pxr_expansion_scaffold_check_repo_contract(tmp_path: Path) -> None:
    out_json = tmp_path / "pxr_scaffold_check.json"
    rc = main(["--root", str(ROOT), "--out-json", str(out_json)])
    assert rc == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["pass"] is True
    assert payload["summary"]["error_count"] == 0
    assert payload["summary"]["current_required_artifact_exists_count"] == payload["summary"]["current_required_artifact_count"]
    assert payload["summary"]["deferred_artifact_count"] == 3
    assert set(payload["deferred_missing_artifacts"]) <= {
        "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
    }


def test_run_pxr_expansion_scaffold_check_allows_deferred_ood_artifacts(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    out_json = tmp_path / "runs" / "pxr_scaffold_check.json"

    rc = main(["--root", str(tmp_path), "--out-json", str(out_json)])
    assert rc == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["pass"] is True
    assert payload["summary"]["deferred_missing_count"] == 3
    assert payload["summary"]["warning_count"] == 1
    assert payload["profiles"][0]["target"] == "PXR_NR1I2_BLIND"
    assert payload["profiles"][1]["target"] == "PXR_NR1I2_BLIND"


def test_run_pxr_expansion_scaffold_check_fails_on_target_mismatch(tmp_path: Path) -> None:
    _build_fixture(tmp_path, ood_target="WRONG_TARGET")
    out_json = tmp_path / "runs" / "pxr_scaffold_check_fail.json"

    rc = main(["--root", str(tmp_path), "--out-json", str(out_json)])
    assert rc == 2

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["pass"] is False
    assert payload["summary"]["error_count"] >= 1
    assert any("targets must be PXR_NR1I2_BLIND" in err for err in payload["errors"])
