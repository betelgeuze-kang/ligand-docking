from __future__ import annotations

import json
from pathlib import Path

from tools import build_gpcr_frozen_candidate_scoreability_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(header)]
    lines.extend(",".join(str(value) for value in row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _freeze_packet() -> dict:
    return {
        "summary": {"frozen": True},
        "accepted_candidate_rows": [
            {"target": "DRD2_GPCR_BLIND", "ligand_id": "CHEMBL301265"},
            {"target": "HTR2A_GPCR_BLIND", "ligand_id": "CHEMBL83894"},
        ],
    }


def _profile(tmp_path: Path) -> dict:
    return {
        "targets": "ADRB2_GPCR_BLIND",
        "hard_decoy_targets": "EGFR_KINASE,ADRB2_GPCR_BLIND",
        "target_native_csv": str(tmp_path / "native.csv"),
        "ranking_labels_csv": str(tmp_path / "labels.csv"),
        "eval_split_csv": str(tmp_path / "splits.csv"),
        "leakage_target_meta_csv": str(tmp_path / "target_meta.csv"),
        "leakage_ligand_meta_csv": str(tmp_path / "ligand_meta.csv"),
    }


def test_default_adrb2_profile_blocks_unwired_frozen_candidates(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    profile = tmp_path / "profile.json"
    _write_json(freeze, _freeze_packet())
    _write_json(profile, _profile(tmp_path))
    _write_csv(tmp_path / "native.csv", ["target", "native_pdb_path"], [["ADRB2_GPCR_BLIND", "missing.pdb"]])
    _write_csv(tmp_path / "labels.csv", ["target", "ligand_id"], [["ADRB2_GPCR_BLIND", "carazolol"]])
    _write_csv(tmp_path / "splits.csv", ["target", "ligand_id", "role"], [["ADRB2_GPCR_BLIND", "carazolol", "far_ood_eval"]])
    _write_csv(tmp_path / "target_meta.csv", ["target", "target_family"], [["ADRB2_GPCR_BLIND", "gpcr"]])
    _write_csv(tmp_path / "ligand_meta.csv", ["ligand_id", "smiles"], [["carazolol", "CCC"]])

    payload = mod.build_packet(freeze_json=freeze, profile_json=profile)

    assert payload["summary"]["pass"] is False
    assert "missing_profile_targets" in payload["summary"]["blockers"]
    assert "missing_native_targets" in payload["summary"]["blockers"]
    assert "missing_ranking_label_keys" in payload["summary"]["blockers"]
    assert payload["summary"]["claim_promotion_allowed"] is False


def test_scoreability_passes_when_profile_covers_all_candidate_surfaces(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    profile = tmp_path / "profile.json"
    native_pdb = tmp_path / "drd2.pdb"
    native_pdb.write_text("HEADER TEST\n", encoding="utf-8")
    _write_json(freeze, _freeze_packet())
    prof = _profile(tmp_path)
    prof["targets"] = "ADRB2_GPCR_BLIND,DRD2_GPCR_BLIND,HTR2A_GPCR_BLIND"
    prof["hard_decoy_targets"] = "EGFR_KINASE,ADRB2_GPCR_BLIND,DRD2_GPCR_BLIND,HTR2A_GPCR_BLIND"
    _write_json(profile, prof)
    _write_csv(
        tmp_path / "native.csv",
        ["target", "native_pdb_path"],
        [["DRD2_GPCR_BLIND", native_pdb], ["HTR2A_GPCR_BLIND", native_pdb]],
    )
    rows = [["DRD2_GPCR_BLIND", "CHEMBL301265"], ["HTR2A_GPCR_BLIND", "CHEMBL83894"]]
    _write_csv(tmp_path / "labels.csv", ["target", "ligand_id"], rows)
    _write_csv(tmp_path / "splits.csv", ["target", "ligand_id", "role"], [row + ["far_ood_eval"] for row in rows])
    _write_csv(tmp_path / "target_meta.csv", ["target", "target_family"], [[row[0], "gpcr"] for row in rows])
    _write_csv(tmp_path / "ligand_meta.csv", ["ligand_id", "smiles"], [["CHEMBL301265", "CCC"], ["CHEMBL83894", "NNN"]])

    payload = mod.build_packet(freeze_json=freeze, profile_json=profile)

    assert payload["summary"]["pass"] is True
    assert payload["summary"]["status"] == "pass"
    assert payload["summary"]["blockers"] == []
    assert payload["claim_boundary"]["fake_pass_allowed"] is False


def test_scoreability_blocks_when_profile_positive_count_is_below_frozen_count(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    profile = tmp_path / "profile.json"
    native_pdb = tmp_path / "drd2.pdb"
    native_pdb.write_text("HEADER TEST\n", encoding="utf-8")
    payload = _freeze_packet()
    payload["summary"]["positive_count"] = 3
    _write_json(freeze, payload)
    prof = _profile(tmp_path)
    prof["targets"] = "DRD2_GPCR_BLIND,HTR2A_GPCR_BLIND"
    prof["hard_decoy_targets"] = "DRD2_GPCR_BLIND,HTR2A_GPCR_BLIND"
    _write_json(profile, prof)
    rows = [["DRD2_GPCR_BLIND", "CHEMBL301265"], ["HTR2A_GPCR_BLIND", "CHEMBL83894"]]
    _write_csv(
        tmp_path / "native.csv",
        ["target", "native_pdb_path"],
        [["DRD2_GPCR_BLIND", native_pdb], ["HTR2A_GPCR_BLIND", native_pdb]],
    )
    _write_csv(tmp_path / "labels.csv", ["target", "ligand_id", "is_binder"], [row + [1] for row in rows])
    _write_csv(tmp_path / "splits.csv", ["target", "ligand_id", "role"], [row + ["far_ood_eval"] for row in rows])
    _write_csv(tmp_path / "target_meta.csv", ["target", "target_family"], [[row[0], "gpcr"] for row in rows])
    _write_csv(tmp_path / "ligand_meta.csv", ["ligand_id", "smiles"], [["CHEMBL301265", "CCC"], ["CHEMBL83894", "NNN"]])

    result = mod.build_packet(freeze_json=freeze, profile_json=profile)

    assert result["summary"]["pass"] is False
    assert result["summary"]["freeze_positive_count"] == 3
    assert result["summary"]["profile_positive_count"] == 2
    assert "profile_positive_count_below_freeze_packet" in result["summary"]["blockers"]


def test_missing_freeze_packet_blocks_conservatively(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    _write_json(profile, _profile(tmp_path))

    payload = mod.build_packet(freeze_json=tmp_path / "missing.json", profile_json=profile)

    assert payload["summary"]["pass"] is False
    assert "freeze_packet_missing" in payload["summary"]["blockers"]
    assert "accepted_candidate_rows_missing" in payload["summary"]["blockers"]
