from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_feature_recovery_input as mod


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_inputs(tmp_path: Path, *, with_trajectory: bool = True) -> dict[str, Path]:
    readiness = tmp_path / "readiness.csv"
    labels = tmp_path / "labels.csv"
    split = tmp_path / "split.csv"
    native = tmp_path / "native.csv"
    native_pdb = tmp_path / "6cm4.pdb"
    traj_root = tmp_path / "traj"
    traj = traj_root / "run" / "stage2_trajectory_frames" / "shard_00001" / (
        "CHEMBL217_DRD2_HUMAN__rep9557__decoy_CHEMBL217_DRD2_HUMAN_09554.npz"
    )
    native_pdb.write_text("HEADER fixture\n", encoding="utf-8")
    if with_trajectory:
        traj.parent.mkdir(parents=True, exist_ok=True)
        traj.write_bytes(b"npz fixture placeholder")
    _write_csv(
        readiness,
        [
            {
                "target_id": "DRD2",
                "target_source_id": "CHEMBL217_DRD2_HUMAN",
                "materialization_role": "decoy_above_positive",
                "ligand_id": "decoy_CHEMBL217_DRD2_HUMAN_09554",
                "is_binder": "false",
                "retained_rank": "20",
                "retained_score": "-45.6",
                "anchor_distance_a": "4.99",
                "scoring_feature_cache_ready": "false",
                "blockers": "scoring_feature_cache_missing;decoy_currently_above_positive",
            }
        ],
        [
            "target_id",
            "target_source_id",
            "materialization_role",
            "ligand_id",
            "is_binder",
            "retained_rank",
            "retained_score",
            "anchor_distance_a",
            "scoring_feature_cache_ready",
            "blockers",
        ],
    )
    _write_csv(
        labels,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_CHEMBL217_DRD2_HUMAN_09554",
                "reference_binding_kcal_mol": "-2.95",
                "is_binder": "0",
                "smiles": "CCN",
                "scaffold": "CCN",
                "molecular_weight": "45.1",
                "logp": "0.1",
                "h_donors": "1",
                "h_acceptors": "1",
                "rot_bonds": "1",
            }
        ],
        [
            "target",
            "ligand_id",
            "reference_binding_kcal_mol",
            "is_binder",
            "smiles",
            "scaffold",
            "molecular_weight",
            "logp",
            "h_donors",
            "h_acceptors",
            "rot_bonds",
        ],
    )
    _write_csv(
        split,
        [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "decoy_CHEMBL217_DRD2_HUMAN_09554", "role": "far_ood_eval"}],
        ["target", "ligand_id", "role"],
    )
    _write_csv(
        native,
        [{"target": "CHEMBL217_DRD2_HUMAN", "native_pdb_path": str(native_pdb)}],
        ["target", "native_pdb_path"],
    )
    return {
        "readiness": readiness,
        "labels": labels,
        "split": split,
        "native": native,
        "traj_root": traj_root,
        "traj": traj,
    }


def test_feature_recovery_input_ready_when_local_evidence_exists(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, with_trajectory=True)

    payload = mod.build_gpcr_hard_decoy_feature_recovery_input(
        readiness_csv=paths["readiness"],
        labels_csv=paths["labels"],
        split_csv=paths["split"],
        trajectory_roots=[paths["traj_root"]],
        native_source_csvs=[paths["native"]],
    )

    assert payload["summary"]["status"] == "gpcr_hard_decoy_feature_recovery_input_ready"
    assert payload["summary"]["feature_cache_execution_ready"] is True
    assert payload["summary"]["feature_input_ready_row_count"] == 1
    assert payload["rows"][0]["blockers"] == ""
    input_row = payload["input_rows"][0]
    assert input_row["ligand_smiles"] == "CCN"
    assert input_row["binding_score_composite_v7"] == "-2.95"
    assert input_row["binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow"] == "-45.6"
    assert input_row["ligand_h_donors"] == "1"
    assert input_row["trajectory_npz"] == str(paths["traj"])


def test_feature_recovery_input_blocks_on_missing_trajectory(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, with_trajectory=False)

    payload = mod.build_gpcr_hard_decoy_feature_recovery_input(
        readiness_csv=paths["readiness"],
        labels_csv=paths["labels"],
        split_csv=paths["split"],
        trajectory_roots=[paths["traj_root"]],
        native_source_csvs=[paths["native"]],
    )

    assert payload["summary"]["status"] == "blocked_gpcr_hard_decoy_feature_recovery_input_incomplete"
    assert payload["summary"]["feature_cache_execution_ready"] is False
    assert payload["summary"]["missing_counts"]["trajectory_missing"] == 1
    assert payload["rows"][0]["blockers"] == "trajectory_npz_missing"
    assert payload["input_rows"] == []


def test_main_writes_manifest_and_input_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, with_trajectory=True)
    out_input = tmp_path / "input.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "manifest.csv"

    rc = mod.main(
        [
            "--readiness-csv",
            str(paths["readiness"]),
            "--labels-csv",
            str(paths["labels"]),
            "--split-csv",
            str(paths["split"]),
            "--trajectory-root",
            str(paths["traj_root"]),
            "--native-source-csv",
            str(paths["native"]),
            "--out-input-csv",
            str(out_input),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["out_input_csv"] == str(out_input)
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Feature Recovery Input")
    input_rows = list(csv.DictReader(out_input.open(encoding="utf-8")))
    manifest_rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert input_rows[0]["ligand_id"] == "decoy_CHEMBL217_DRD2_HUMAN_09554"
    assert manifest_rows[0]["feature_input_ready"] == "True"
