from __future__ import annotations

import json
from pathlib import Path

from tools import run_transporter_membrane_scaffold_check as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n", encoding="utf-8")


def _build_transport_scaffold_root(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in [
        "config/real_drug_targets_blind_aqp1_v1.csv",
        "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
        "config/ligand_target_metadata_blind_aqp1_v1.csv",
        "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
        "config/ligand_binding_reference_blind_aqp1_v1.csv",
        "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
        "config/ligand_eval_splits_blind_aqp1_v1.csv",
        "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
        "config/ligand_meta_blind_aqp1_v1.csv",
        "config/ligand_meta_blind_glut1_4pyp_v1.csv",
    ]:
        _write_csv(tmp_path / rel_path, "col")

    _write_json(
        tmp_path / "config/ligand_htvs_blind_aqp1_v1.json",
        {
            "version": "ligand_htvs_blind_aqp1_v1",
            "description": "Dry-run structural template for the first Aquaporin_1 membrane-transporter blind validation profile.",
            "targets": "AQP1_TRANSPORT_BLIND",
            "run_scope": "full",
            "dry_run": True,
            "target_native_csv": "config/real_drug_targets_blind_aqp1_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_aqp1_v1.csv",
            "calibration_reference_csv": "config/ligand_binding_reference_blind_aqp1_v1.csv",
            "ranking_labels_csv": "config/ligand_binding_reference_blind_aqp1_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_aqp1_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_aqp1_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_aqp1_v1.csv",
            "hard_decoy_fit_targets": "EGFR_KINASE",
            "hard_decoy_targets": "EGFR_KINASE,AQP1_TRANSPORT_BLIND",
        },
    )
    _write_json(
        tmp_path / "config/ligand_htvs_blind_glut1_4pyp_v1.json",
        {
            "version": "ligand_htvs_blind_glut1_4pyp_v1",
            "description": "Dry-run structural template for the first GLUT1_4PYP membrane-transporter blind validation profile.",
            "targets": "GLUT1_TRANSPORT_BLIND",
            "run_scope": "full",
            "dry_run": True,
            "target_native_csv": "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
            "ligand_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
            "calibration_reference_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
            "ranking_labels_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_glut1_4pyp_v1.csv",
            "leakage_target_meta_csv": "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
            "hard_decoy_fit_targets": "EGFR_KINASE",
            "hard_decoy_targets": "EGFR_KINASE,GLUT1_TRANSPORT_BLIND",
        },
    )
    _write_json(
        tmp_path / "config/external_validation_transporter_membrane_sets_v1_template.json",
        {
            "protocol_id": "external_validation_transporter_membrane_sets_v1_template",
            "status": "template_not_runnable",
            "primary_candidates": {
                "core_blind": "AQP1_TRANSPORT_BLIND",
                "expanded_ood": "GLUT1_TRANSPORT_BLIND",
            },
            "required_artifacts": dict(mod.EXPECTED_REQUIRED_ARTIFACTS),
            "scaffold_status": dict(mod.EXPECTED_SCAFFOLD_STATUS),
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "tasks": [
                        {
                            "task_id": "aqp1_core_full",
                            "domain": "transporter_membrane",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_aqp1_v1.json",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
                {
                    "set_id": "set2_expanded_ood",
                    "tasks": [
                        {
                            "task_id": "glut1_4pyp_full",
                            "domain": "transporter_membrane",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_glut1_4pyp_v1.json",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
                {
                    "set_id": "set3_operational_smoke",
                    "tasks": [
                        {
                            "task_id": "aqp1_smoke",
                            "domain": "transporter_membrane",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_aqp1_v1.json",
                            "ligand_sizes": "64",
                        }
                    ],
                },
            ],
        },
    )


def test_run_transporter_membrane_scaffold_check_ok(tmp_path: Path) -> None:
    _build_transport_scaffold_root(tmp_path)

    payload = mod.run_check(root=str(tmp_path))

    assert payload["ok"] is True
    assert payload["summary"]["artifact_count"] == 12
    assert payload["summary"]["artifact_exists_count"] == 12
    assert payload["summary"]["task_count"] == 3
    assert payload["summary"]["profile_count"] == 2
    assert payload["summary"]["dry_run_profile_count"] == 2
    assert payload["summary"]["ready_for_validate_only"] is False
    assert payload["summary"]["claim_ready"] is False
    assert payload["errors"] == []


def test_run_transporter_membrane_scaffold_check_main_fails_on_target_mismatch(tmp_path: Path, capsys) -> None:
    _build_transport_scaffold_root(tmp_path)
    profile_path = tmp_path / "config/ligand_htvs_blind_glut1_4pyp_v1.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["targets"] = "GLUT1_WRONG_TARGET"
    profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    rc = mod.main(["--root", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert out["ok"] is False
    assert any("profile target mismatch for config/ligand_htvs_blind_glut1_4pyp_v1.json" in msg for msg in out["errors"])
