from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_json(rel_path: str) -> dict:
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


@pytest.mark.parametrize(
    ("rel_path", "target", "native_csv", "ligand_csv", "split_csv", "ligand_meta_csv", "target_meta_csv"),
    [
        (
            "config/ligand_htvs_blind_aqp1_v1.json",
            "AQP1_TRANSPORT_BLIND",
            "config/real_drug_targets_blind_aqp1_v1.csv",
            "config/ligand_binding_reference_blind_aqp1_v1.csv",
            "config/ligand_eval_splits_blind_aqp1_v1.csv",
            "config/ligand_meta_blind_aqp1_v1.csv",
            "config/ligand_target_metadata_blind_aqp1_v1.csv",
        ),
        (
            "config/ligand_htvs_blind_glut1_4pyp_v1.json",
            "GLUT1_TRANSPORT_BLIND",
            "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
            "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
            "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
            "config/ligand_meta_blind_glut1_4pyp_v1.csv",
            "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
        ),
    ],
)
def test_transporter_profiles_are_parseable_dry_run_scaffolds(
    rel_path: str,
    target: str,
    native_csv: str,
    ligand_csv: str,
    split_csv: str,
    ligand_meta_csv: str,
    target_meta_csv: str,
) -> None:
    payload = _load_json(rel_path)

    assert payload["version"] == Path(rel_path).stem
    assert payload["targets"] == target
    _contains_tokens(payload["description"], "dry-run", "structural", "template")
    assert payload["run_scope"] == "full"
    assert payload["dry_run"] is True

    assert payload["target_native_csv"] == native_csv
    assert payload["ligand_csv"] == ligand_csv
    assert payload["calibration_reference_csv"] == ligand_csv
    assert payload["ranking_labels_csv"] == ligand_csv
    assert payload["eval_split_csv"] == split_csv
    assert payload["leakage_ligand_meta_csv"] == ligand_meta_csv
    assert payload["leakage_target_meta_csv"] == target_meta_csv

    assert payload["hard_decoy_fit_targets"] == "EGFR_KINASE"
    assert payload["hard_decoy_targets"].split(",")[0] == "EGFR_KINASE"
    assert target in payload["hard_decoy_targets"].split(",")
    assert payload["run_calibration"] is False
    assert payload["require_ood_eval"] is False

    assert payload["smoke"]["max_ligands"] == 64
    assert payload["full"]["max_ligands"] == 10000
    assert payload["gate"]["min_eval_unique_keys"] == 200


def test_transporter_external_validation_template_is_parseable_non_runnable() -> None:
    payload = _load_json("config/external_validation_transporter_membrane_sets_v1_template.json")

    assert payload["protocol_id"] == "external_validation_transporter_membrane_sets_v1_template"
    assert payload["protocol_version"] == "template_v1"
    assert payload["status"] == "template_not_runnable"
    assert "membrane-transporter family" in payload["description"]

    assert payload["primary_candidates"] == {
        "core_blind": "AQP1_TRANSPORT_BLIND",
        "expanded_ood": "GLUT1_TRANSPORT_BLIND",
    }
    assert payload["scaffold_status"] == {
        "aqp1_profile_present": True,
        "glut1_profile_present": True,
        "aqp1_profile_dry_run_only": True,
        "glut1_profile_dry_run_only": True,
        "ready_for_validate_only": False,
        "claim_ready": False,
    }

    required = payload["required_artifacts"]
    assert required["aqp1_profile_json"] == "config/ligand_htvs_blind_aqp1_v1.json"
    assert required["glut1_profile_json"] == "config/ligand_htvs_blind_glut1_4pyp_v1.json"

    task_profiles = [task["profile_json"] for item in payload["sets"] for task in item["tasks"]]
    assert task_profiles == [
        "config/ligand_htvs_blind_aqp1_v1.json",
        "config/ligand_htvs_blind_glut1_4pyp_v1.json",
        "config/ligand_htvs_blind_aqp1_v1.json",
    ]

    task_sizes = [task["ligand_sizes"] for item in payload["sets"] for task in item["tasks"]]
    assert task_sizes == ["10000", "10000", "64"]
    assert all(size.isdigit() for size in task_sizes)
    assert any(
        all(token in note.lower() for token in ("dry-run", "structural", "templates", "only"))
        for note in payload["implementation_notes"]
    )
