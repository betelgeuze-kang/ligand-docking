from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools import build_residual_force_derivation_validation as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def _write_stage3(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["target", "ligand_id", "trajectory_npz", "backmapped_pdb", "delta_force_x"]
    path.write_text(
        ",".join(fields)
        + "\n"
        + "\n".join(",".join(str(row.get(field, "")) for field in fields) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def test_force_derivation_validation_blocks_nan_trajectory_paths(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": "nan"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "trajectory_npz": ""},
        ],
    )
    payload = mod.build_residual_force_derivation_validation(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 2},
            [
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)},
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "source_csv": str(stage5)},
            ],
        ),
        regeneration_manifest_csv=str(tmp_path / "missing_manifest.csv"),
        min_existing_npz_rows=1,
        min_npz_probe_successes=1,
    )

    summary = payload["summary"]
    assert summary["raw_trajectory_path_rows"] == 1
    assert summary["valid_trajectory_path_rows"] == 0
    assert summary["existing_trajectory_npz_rows"] == 0
    assert summary["delta_force_derivation_validation_ready"] is False
    assert "trajectory_npz_artifacts" in summary["blockers"]


def test_force_derivation_validation_accepts_npz_coordinate_energy_inputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    npz = tmp_path / "traj0.npz"
    np.savez(npz, ligand_coords=np.zeros((3, 4, 3)), energy=np.array([1.0, 0.5, 0.25]))
    pdb = tmp_path / "pose0.pdb"
    pdb.write_text("MODEL\nEND\n", encoding="utf-8")
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "lig0",
                "trajectory_npz": str(npz),
                "backmapped_pdb": str(pdb),
                "delta_force_x": 0.1,
            }
        ],
    )
    payload = mod.build_residual_force_derivation_validation(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 1},
            [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)}],
        ),
        regeneration_manifest_csv=str(tmp_path / "missing_manifest.csv"),
        min_existing_npz_rows=1,
        min_npz_probe_successes=1,
    )

    summary = payload["summary"]
    assert summary["delta_force_derivation_validation_ready"] is True
    assert summary["existing_trajectory_npz_rows"] == 1
    assert summary["derivation_input_sample_count"] == 1
    assert payload["npz_probes"][0]["probe_status"] == "npz_derivation_inputs_present"


def test_force_derivation_validation_accepts_regenerated_npz_remap(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    regenerated = tmp_path / "regen" / "shard_00000" / "q1.npz"
    regenerated.parent.mkdir(parents=True)
    np.savez(regenerated, ligand_coords=np.zeros((3, 4, 3)), energy=np.array([1.0, 0.5, 0.25]))
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "lig0",
                "trajectory_npz": "/missing/runA/q1.npz",
                "delta_force_x": 0.1,
            }
        ],
    )

    payload = mod.build_residual_force_derivation_validation(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 1},
            [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)}],
        ),
        trajectory_regeneration_queue_packet={
            "summary": {},
            "rows": [
                {
                    "original_trajectory_npz": "/missing/runA/q1.npz",
                    "expected_regenerated_trajectory_npz": str(regenerated),
                }
            ],
        },
        regeneration_manifest_csv=str(tmp_path / "missing_manifest.csv"),
        min_existing_npz_rows=1,
        min_npz_probe_successes=1,
    )

    summary = payload["summary"]
    assert summary["delta_force_derivation_validation_ready"] is True
    assert summary["trajectory_remap_candidate_rows"] == 1
    assert summary["existing_remapped_trajectory_npz_rows"] == 1
    assert payload["npz_probes"][0]["remapped_trajectory_npz"] == str(regenerated)


def test_force_derivation_validation_caps_existing_npz_floor_to_available_valid_paths(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    npz_a = tmp_path / "traj_a.npz"
    npz_b = tmp_path / "traj_b.npz"
    np.savez(npz_a, ligand_coords=np.zeros((3, 4, 3)), energy=np.array([1.0, 0.5, 0.25]))
    np.savez(npz_b, ligand_coords=np.zeros((3, 4, 3)), energy=np.array([1.0, 0.5, 0.25]))
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": str(npz_a), "delta_force_x": 0.1},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "trajectory_npz": str(npz_b), "delta_force_x": 0.2},
        ],
    )

    payload = mod.build_residual_force_derivation_validation(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 2},
            [
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)},
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "source_csv": str(stage5)},
            ],
        ),
        regeneration_manifest_csv=str(tmp_path / "missing_manifest.csv"),
        min_existing_npz_rows=5,
        min_npz_probe_successes=2,
    )

    summary = payload["summary"]
    assert summary["delta_force_derivation_validation_ready"] is True
    assert summary["min_existing_npz_rows"] == 5
    assert summary["effective_min_existing_npz_rows"] == 2
    assert summary["existing_npz_floor_capped_by_available_paths"] is True


def test_force_derivation_validation_caps_floor_to_regenerated_manifest_universe(tmp_path: Path) -> None:
    regen_a = tmp_path / "regen" / "q1.npz"
    regen_b = tmp_path / "regen" / "q2.npz"
    regen_a.parent.mkdir(parents=True)
    np.savez(regen_a, ligand_frames=np.zeros((3, 4, 3)), protein_ca=np.zeros((4, 3)))
    np.savez(regen_b, ligand_frames=np.zeros((3, 4, 3)), protein_ca=np.zeros((4, 3)))
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "status,trajectory_npz,target,ligand_id\n"
        f"ok_regenerated_npz,{regen_a},ADRB2_GPCR_BLIND,lig0\n"
        f"ok_regenerated_npz,{regen_b},ADRB2_GPCR_BLIND,lig1\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_force_derivation_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 0}, []),
        trajectory_regeneration_queue_packet={
            "summary": {"queue_rows": 2},
            "rows": [
                {"original_trajectory_npz": "/missing/q1.npz", "expected_regenerated_trajectory_npz": str(regen_a)},
                {"original_trajectory_npz": "/missing/q2.npz", "expected_regenerated_trajectory_npz": str(regen_b)},
            ],
        },
        regeneration_manifest_csv=str(manifest),
        min_existing_npz_rows=5,
        min_npz_probe_successes=2,
    )

    summary = payload["summary"]
    assert summary["delta_force_derivation_validation_ready"] is True
    assert summary["valid_trajectory_path_rows"] == 0
    assert summary["regeneration_queue_rows"] == 2
    assert summary["regeneration_manifest_ok_rows"] == 2
    assert summary["regeneration_manifest_existing_npz_rows"] == 2
    assert summary["available_npz_floor_candidate_rows"] == 2
    assert summary["effective_min_existing_npz_rows"] == 2
    assert summary["existing_npz_floor_capped_by_available_paths"] is True


def test_force_derivation_validation_cli_writes_outputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(tmp_path / "a_stage3_scores.csv", [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": "nan"}])
    supervised = tmp_path / "supervised.json"
    supervised.write_text(
        json.dumps(_packet({"rows_emitted": 1}, [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)}]))
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--supervised-dataset-json",
            str(supervised),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["valid_trajectory_path_rows"] == 0
    assert "trajectory_npz_artifacts" in out_csv.read_text(encoding="utf-8")
    assert "Residual Force Derivation Validation" in out_md.read_text(encoding="utf-8")
