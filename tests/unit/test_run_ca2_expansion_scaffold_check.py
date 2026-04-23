from __future__ import annotations

import json
from pathlib import Path

from tools import run_ca2_expansion_scaffold_check as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [",".join(header)]
    body.extend(",".join(row) for row in rows)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def _build_ca2_package(root: Path) -> None:
    _write_json(
        root / "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
        {
            "protocol_id": "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template",
            "status": "template_not_runnable",
            "primary_candidate": {
                "target": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
                "native_pdb_path": "data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_pdb_1CA2.pdb",
            },
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
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "tasks": [
                        {
                            "task_id": "non_kinase_enzyme_ca2_core_full",
                            "domain": "non_kinase_enzyme",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
                            "ligand_sizes": "10000",
                            "date_tag_suffix": "ca2-core-full",
                        }
                    ],
                },
                {
                    "set_id": "set2_expanded_ood",
                    "tasks": [
                        {
                            "task_id": "non_kinase_enzyme_ca2_chembl50_full",
                            "domain": "non_kinase_enzyme",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_ca2_zn_chembl50_v1.json",
                            "ligand_sizes": "10000",
                            "date_tag_suffix": "ca2-chembl50-full",
                        }
                    ],
                },
                {
                    "set_id": "set3_operational_smoke",
                    "tasks": [
                        {
                            "task_id": "non_kinase_enzyme_ca2_smoke",
                            "domain": "non_kinase_enzyme",
                            "kind": "ligand_stress",
                            "profile_json": "config/ligand_htvs_blind_ca2_zn_v1.json",
                            "ligand_sizes": "64",
                            "date_tag_suffix": "ca2-smoke",
                        }
                    ],
                },
            ],
        },
    )
    _write_csv(
        root / "config/real_drug_targets_blind_ca2_zn_v1.csv",
        ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
        [
            ["EGFR_KINASE", "data/native/egfr_kinase.pdb", "1M17", "0.0", "0.0", "0.0", "fit donor"],
            [
                "CARBONIC_ANHYDRASE_2_ZN_BLIND",
                "data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_pdb_1CA2.pdb",
                "1CA2",
                "0.0",
                "0.0",
                "0.0",
                "ca2 template",
            ],
        ],
    )
    _write_csv(
        root / "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
        ["target", "target_family", "sequence", "pocket_fingerprint"],
        [
            ["EGFR_KINASE", "TYR_KINASE", "SEQ", "kinase"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "METALLOENZYME", "TODO_SEQUENCE_P00918", "zn_active_site"],
        ],
    )
    _write_csv(
        root / "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["EGFR_KINASE", "egfr_fit_01", "-9.1", "1", "template"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_core_01", "-8.0", "1", "template"],
        ],
    )
    _write_csv(
        root / "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
        ["target", "ligand_id", "role"],
        [
            ["EGFR_KINASE", "egfr_fit_01", "fit"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_core_01", "far_ood_eval"],
        ],
    )
    _write_csv(
        root / "config/ligand_meta_blind_ca2_zn_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["egfr_fit_01", "CC", "30.0", "1.0", "0", "0", "0", "fit"],
            ["ca2_core_01", "CN", "31.0", "1.1", "1", "1", "1", "ca2"],
        ],
    )
    _write_csv(
        root / "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["EGFR_KINASE", "egfr_fit_01", "-9.1", "1", "template"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_ood_01", "-8.4", "1", "template"],
        ],
    )
    _write_csv(
        root / "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        ["target", "ligand_id", "role"],
        [
            ["EGFR_KINASE", "egfr_fit_01", "fit"],
            ["CARBONIC_ANHYDRASE_2_ZN_BLIND", "ca2_ood_01", "far_ood_eval"],
        ],
    )
    _write_csv(
        root / "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["egfr_fit_01", "CC", "30.0", "1.0", "0", "0", "0", "fit"],
            ["ca2_ood_01", "CO", "32.0", "1.2", "1", "1", "1", "ca2"],
        ],
    )
    profile_common = {
        "targets": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
        "dry_run": True,
        "template_profile": True,
        "template_execution_intent": "validate_only",
        "claim_ready": False,
        "target_native_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
        "calibration_reference_csv": "",
        "ranking_labels_csv": "",
        "eval_split_csv": "",
        "leakage_target_meta_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
        "leakage_ligand_meta_csv": "",
        "hard_decoy_reference_csv": "",
        "hard_decoy_ligand_meta_csv": "",
        "hard_decoy_target_meta_csv": "config/ligand_target_metadata_blind_ca2_zn_v1.csv",
        "hard_decoy_targets": "EGFR_KINASE,CARBONIC_ANHYDRASE_2_ZN_BLIND",
        "hard_decoy_fit_targets": "EGFR_KINASE",
    }
    core_profile = dict(profile_common)
    core_profile.update(
        {
            "ligand_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
            "calibration_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
            "ranking_labels_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
            "hard_decoy_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
            "hard_decoy_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
        }
    )
    ood_profile = dict(profile_common)
    ood_profile.update(
        {
            "ligand_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
            "calibration_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
            "ranking_labels_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
            "eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
            "leakage_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
            "hard_decoy_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
            "hard_decoy_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
        }
    )
    _write_json(root / "config/ligand_htvs_blind_ca2_zn_v1.json", core_profile)
    _write_json(root / "config/ligand_htvs_blind_ca2_zn_chembl50_v1.json", ood_profile)
    (root / "data/native").mkdir(parents=True, exist_ok=True)
    (root / "data/native/egfr_kinase.pdb").write_text("EGFR\n", encoding="utf-8")
    (root / "data/public_structures/2026-02-19-measured20-strict-r1").mkdir(parents=True, exist_ok=True)
    (
        root / "data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_pdb_1CA2.pdb"
    ).write_text("CA2\n", encoding="utf-8")


def test_validate_ca2_scaffold_passes_for_consistent_package(monkeypatch, tmp_path: Path) -> None:
    _build_ca2_package(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.validate_ca2_scaffold()

    assert payload["pass"] is True
    assert payload["mode"] == "validate_only"
    assert payload["summary"]["failed_checks"] == 0
    assert payload["summary"]["passed_checks"] == payload["summary"]["total_checks"]


def test_validate_ca2_scaffold_fails_when_profile_is_not_validate_only(monkeypatch, tmp_path: Path) -> None:
    _build_ca2_package(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile_path = tmp_path / "config/ligand_htvs_blind_ca2_zn_v1.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["dry_run"] = False
    profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    out = mod.validate_ca2_scaffold()

    assert out["pass"] is False
    failed_ids = {row["check_id"] for row in out["checks"] if not row["ok"]}
    assert "profile_flag:core_profile_json:dry_run" in failed_ids


def test_main_returns_nonzero_and_json_for_task_link_mismatch(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    _build_ca2_package(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    template_path = tmp_path / "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    payload["sets"][1]["tasks"][0]["profile_json"] = "config/wrong_profile.json"
    template_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    rc = mod.main(["--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["pass"] is False
    failed_ids = {row["check_id"] for row in output["checks"] if not row["ok"]}
    assert "task_link:set2_expanded_ood:profile_json" in failed_ids
