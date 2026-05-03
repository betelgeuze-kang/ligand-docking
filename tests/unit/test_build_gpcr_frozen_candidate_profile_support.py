from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_gpcr_frozen_candidate_profile_support as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _freeze_packet() -> dict:
    return {
        "summary": {
            "frozen": True,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "freeze_packet_is_not_claim_authorization": True,
        },
        "accepted_candidate_rows": [
            {
                "accepted_for_freeze": True,
                "target": "CHEMBL217_DRD2_HUMAN",
                "target_family": "gpcr",
                "ligand_id": "CHEMBL301265",
                "reference_binding_kcal_mol": -14.772,
                "is_binder": True,
                "role": "far_ood_eval",
                "source": "ChEMBL activity 24865270 Kd pChEMBL 10.83",
                "source_url": "https://www.ebi.ac.uk/chembl/api/data/activity/24865270.json",
            },
            {
                "accepted_for_freeze": True,
                "target": "CHEMBL224_HTR2A_HUMAN",
                "target_family": "gpcr",
                "ligand_id": "CHEMBL341680",
                "reference_binding_kcal_mol": -13.2,
                "is_binder": True,
                "role": "far_ood_eval",
                "source": "ChEMBL activity fixture",
            },
        ],
    }


def _base_profile(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "base_profile.json"
    _write_json(
        path,
        {
            "version": "fixture_base",
            "targets": "ADRB2_GPCR_BLIND",
            "ligand_csv": "config/old_reference.csv",
            "ranking_labels_csv": "config/old_reference.csv",
            "calibration_reference_csv": "config/old_reference.csv",
            "eval_split_csv": "config/old_split.csv",
            "target_native_csv": "config/old_native.csv",
            "native_path_col": "native_pdb_path",
            "leakage_ligand_meta_csv": "config/old_ligand_meta.csv",
            "leakage_target_meta_csv": "config/old_target_meta.csv",
            "hard_decoy_reference_csv": "config/old_reference.csv",
            "hard_decoy_ligand_meta_csv": "config/old_ligand_meta.csv",
            "hard_decoy_target_meta_csv": "config/old_target_meta.csv",
            "hard_decoy_targets": "EGFR_KINASE,ADRB2_GPCR_BLIND",
            "ranking_eval_roles": "far_ood_eval",
            "run_leakage_audit": True,
        },
    )
    return path


def _native_fixture(path: Path, ligand_code: str = "8NU", ligand_chain: str = "A") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "HEADER    TEST GPCR NATIVE",
                f"HETATM    1  C1  {ligand_code:>3} {ligand_chain}   1       1.000   2.000   3.000  1.00 10.00           C",
                f"HETATM    2  C2  {ligand_code:>3} {ligand_chain}   1       3.000   4.000   5.000  1.00 10.00           C",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_missing_native_keeps_candidates_blocked_and_profile_not_ready(tmp_path: Path) -> None:
    freeze_json = tmp_path / "runs" / "freeze.json"
    out_dir = tmp_path / "runs" / "support"
    _write_json(freeze_json, _freeze_packet())

    payload = mod.build_support_packet(
        freeze_packet_json=freeze_json,
        base_profile_json=_base_profile(tmp_path),
        candidates_csv=None,
        native_source_csv=None,
        out_dir=out_dir,
    )

    assert payload["summary"]["profile_ready"] is False
    assert payload["summary"]["blocked_target_count"] == 2
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["router_claim_allowed"] is False
    assert payload["summary"]["platform_claim_allowed"] is False
    assert {row["native_status"] for row in payload["target_rows"]} == {"blocked_missing_native_or_pocket"}
    assert all(row["profile_ready"] is False for row in payload["target_rows"])

    native_rows = _read_csv(Path(payload["artifacts"]["native_csv"]))
    assert {row["status"] for row in native_rows} == {"blocked_missing_native_or_pocket"}
    assert all(row["native_pdb_path"] == "" for row in native_rows)


def test_complete_native_fixture_produces_ready_profile_pointing_to_generated_csvs(tmp_path: Path) -> None:
    freeze_json = tmp_path / "runs" / "freeze.json"
    native_csv = tmp_path / "config" / "native.csv"
    out_dir = tmp_path / "runs" / "support"
    drd2_pdb = _native_fixture(tmp_path / "native" / "drd2_fixture.pdb")
    htr2a_pdb = _native_fixture(tmp_path / "native" / "htr2a_fixture.pdb")
    _write_json(freeze_json, _freeze_packet())
    _write_csv(
        native_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "native_pdb_path": str(drd2_pdb),
                "pdb_id": "6CM4",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "pocket_source": "fixture_native_annotation",
                "ligand_code": "8NU",
                "ligand_chain": "A",
                "notes": "test native",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "native_pdb_path": str(htr2a_pdb),
                "pdb_id": "6A93",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "pocket_source": "fixture_native_annotation",
                "ligand_code": "8NU",
                "ligand_chain": "A",
                "notes": "test native",
            },
        ],
    )

    payload = mod.build_support_packet(
        freeze_packet_json=freeze_json,
        base_profile_json=_base_profile(tmp_path),
        candidates_csv=None,
        native_source_csv=native_csv,
        out_dir=out_dir,
    )

    assert payload["summary"]["profile_ready"] is True
    assert payload["summary"]["blocked_target_count"] == 0
    assert {row["profile_ready"] for row in payload["target_rows"]} == {True}

    profile = json.loads(Path(payload["artifacts"]["profile_json"]).read_text(encoding="utf-8"))
    assert profile["profile_ready"] is True
    assert profile["targets"] == "ADRB2_GPCR_BLIND,CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN"
    assert profile["hard_decoy_targets"] == (
        "ADRB2_GPCR_BLIND,CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,EGFR_KINASE"
    )
    assert profile["ligand_csv"] == str(out_dir / "candidate_reference.csv")
    assert profile["ranking_labels_csv"] == str(out_dir / "candidate_reference.csv")
    assert profile["eval_split_csv"] == str(out_dir / "candidate_splits.csv")
    assert profile["target_native_csv"] == str(out_dir / "native_targets.csv")
    assert profile["leakage_ligand_meta_csv"] == str(out_dir / "ligand_meta.csv")
    assert profile["leakage_target_meta_csv"] == str(out_dir / "target_meta.csv")

    reference_rows = _read_csv(Path(payload["artifacts"]["candidate_reference_csv"]))
    split_rows = _read_csv(Path(payload["artifacts"]["split_csv"]))
    assert [row["target"] for row in reference_rows] == [
        "CHEMBL217_DRD2_HUMAN",
        "CHEMBL224_HTR2A_HUMAN",
    ]
    assert {row["role"] for row in split_rows} == {"far_ood_eval"}


def test_generated_set_spec_is_not_claim_authorizing(tmp_path: Path) -> None:
    freeze_json = tmp_path / "runs" / "freeze.json"
    out_dir = tmp_path / "runs" / "support"
    _write_json(freeze_json, _freeze_packet())

    payload = mod.build_support_packet(
        freeze_packet_json=freeze_json,
        base_profile_json=_base_profile(tmp_path),
        candidates_csv=None,
        native_source_csv=None,
        out_dir=out_dir,
    )

    set_spec = json.loads(Path(payload["artifacts"]["set_spec_json"]).read_text(encoding="utf-8"))
    assert set_spec["claim_promotion_allowed"] is False
    assert set_spec["router_claim_allowed"] is False
    assert set_spec["platform_claim_allowed"] is False
    assert set_spec["claim_authorization"] is False
    assert set_spec["freeze_packet_is_not_claim_authorization"] is True
    assert set_spec["native_coordinates_fabricated"] is False


def test_missing_native_path_can_be_materialized_from_verified_pdb_centroid(tmp_path: Path, monkeypatch) -> None:
    freeze_json = tmp_path / "runs" / "freeze.json"
    native_csv = tmp_path / "config" / "native.csv"
    out_dir = tmp_path / "runs" / "support"
    _write_json(freeze_json, _freeze_packet())
    _write_csv(
        native_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "native_pdb_path": "",
                "pdb_id": "6CM4",
                "ligand_code": "8NU",
                "ligand_chain": "A",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "source_release": "fixture",
                "notes": "centroid source",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "native_pdb_path": str(_native_fixture(tmp_path / "native" / "htr2a_fixture.pdb")),
                "pdb_id": "6A93",
                "ligand_code": "8NU",
                "ligand_chain": "A",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "pocket_source": "fixture_native_annotation",
            },
        ],
    )

    def fake_download(_pdb_id: str, output_dir: Path):
        return _native_fixture(output_dir / "native_pdb" / "6cm4.pdb"), ""

    monkeypatch.setattr(mod, "_download_pdb", fake_download)

    payload = mod.build_support_packet(
        freeze_packet_json=freeze_json,
        base_profile_json=_base_profile(tmp_path),
        candidates_csv=None,
        native_source_csv=native_csv,
        out_dir=out_dir,
    )

    assert payload["summary"]["profile_ready"] is True
    native_rows = _read_csv(Path(payload["artifacts"]["native_csv"]))
    drd2 = next(row for row in native_rows if row["target"] == "CHEMBL217_DRD2_HUMAN")
    assert Path(drd2["native_pdb_path"]).exists()
    assert drd2["pocket_validation_status"] == "pass"
    assert drd2["pocket_ligand_atom_count"] == "2"


def test_ready_profile_combines_base_rows_with_frozen_candidates(tmp_path: Path) -> None:
    freeze_json = tmp_path / "runs" / "freeze.json"
    native_csv = tmp_path / "config" / "native.csv"
    out_dir = tmp_path / "runs" / "support"
    base_ref = tmp_path / "config" / "base_reference.csv"
    base_split = tmp_path / "config" / "base_split.csv"
    base_ligand_meta = tmp_path / "config" / "base_ligand_meta.csv"
    base_target_meta = tmp_path / "config" / "base_target_meta.csv"
    base_native = tmp_path / "config" / "base_native.csv"
    base_native_pdb = _native_fixture(tmp_path / "native" / "adrb2_fixture.pdb")
    _write_json(freeze_json, _freeze_packet())
    _write_csv(
        base_ref,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carazolol",
                "reference_binding_kcal_mol": -10.2,
                "is_binder": 1,
                "source": "base_fixture",
            }
        ],
    )
    _write_csv(base_split, [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "carazolol", "role": "far_ood_eval"}])
    _write_csv(base_ligand_meta, [{"ligand_id": "carazolol", "smiles": "CCC", "scaffold": "fixture"}])
    _write_csv(
        base_target_meta,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "target_family": "GPCR_CLASS_A",
                "sequence": "BASESEQ",
                "pocket_fingerprint": "base_pocket",
            }
        ],
    )
    _write_csv(
        base_native,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "native_pdb_path": str(base_native_pdb),
                "pdb_id": "2RH1",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
            }
        ],
    )
    base_profile = tmp_path / "config" / "base_profile.json"
    _write_json(
        base_profile,
        {
            "version": "fixture_base",
            "targets": "ADRB2_GPCR_BLIND",
            "ligand_csv": str(base_ref),
            "ranking_labels_csv": str(base_ref),
            "calibration_reference_csv": str(base_ref),
            "eval_split_csv": str(base_split),
            "target_native_csv": str(base_native),
            "native_path_col": "native_pdb_path",
            "leakage_ligand_meta_csv": str(base_ligand_meta),
            "leakage_target_meta_csv": str(base_target_meta),
            "hard_decoy_reference_csv": str(base_ref),
            "hard_decoy_ligand_meta_csv": str(base_ligand_meta),
            "hard_decoy_target_meta_csv": str(base_target_meta),
            "hard_decoy_targets": "EGFR_KINASE,ADRB2_GPCR_BLIND",
        },
    )
    _write_csv(
        native_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "native_pdb_path": str(_native_fixture(tmp_path / "native" / "drd2_fixture.pdb")),
                "pdb_id": "6CM4",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "pocket_source": "fixture_native_annotation",
                "ligand_code": "8NU",
                "ligand_chain": "A",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "native_pdb_path": str(_native_fixture(tmp_path / "native" / "htr2a_fixture.pdb")),
                "pdb_id": "6A93",
                "pocket_x": 2.0,
                "pocket_y": 3.0,
                "pocket_z": 4.0,
                "pocket_source": "fixture_native_annotation",
                "ligand_code": "8NU",
                "ligand_chain": "A",
            },
        ],
    )

    payload = mod.build_support_packet(
        freeze_packet_json=freeze_json,
        base_profile_json=base_profile,
        candidates_csv=None,
        native_source_csv=native_csv,
        out_dir=out_dir,
    )

    assert payload["summary"]["profile_ready"] is True
    assert payload["summary"]["combined_reference_row_count"] == 3
    assert payload["summary"]["combined_split_row_count"] == 3
    profile = json.loads(Path(payload["artifacts"]["profile_json"]).read_text(encoding="utf-8"))
    assert profile["targets"] == "ADRB2_GPCR_BLIND,CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN"
    reference_rows = _read_csv(Path(payload["artifacts"]["candidate_reference_csv"]))
    assert {row["target"] for row in reference_rows} == {
        "ADRB2_GPCR_BLIND",
        "CHEMBL217_DRD2_HUMAN",
        "CHEMBL224_HTR2A_HUMAN",
    }
