from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from tools.product import build_pocketmd_lite_bounded_metric_collector as mod


_INPUT_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "required_collection_metrics",
    "selected_trajectory_npz",
    "selected_trajectory_source",
    "selected_trajectory_readable",
    "selected_trajectory_claim_grade_metric_fields_present",
    "protein_structure_source_path",
    "protein_structure_source_path_available",
    "ligand_smiles",
    "ligand_smiles_present",
    "collection_input_ready",
    "claim_grade_metrics_already_present",
]


def _write_input_csv(path: Path, npz_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "entry_id": "ADRB2_GPCR_BLIND:ethanol",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "ethanol",
                "required_collection_metrics": (
                    "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count"
                ),
                "selected_trajectory_npz": str(npz_path),
                "selected_trajectory_source": "unit_fixture",
                "selected_trajectory_readable": "true",
                "selected_trajectory_claim_grade_metric_fields_present": "false",
                "protein_structure_source_path": "protein.pdb",
                "protein_structure_source_path_available": "true",
                "ligand_smiles": "CCO",
                "ligand_smiles_present": "true",
                "collection_input_ready": "true",
                "claim_grade_metrics_already_present": "false",
            }
        )


def _write_recovered_npz(path: Path, *, protein_atom_frames: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "protein_ca": np.asarray([[0.0, 0.0, 0.0], [8.5, 0.0, 0.0]], dtype=np.float32),
        "ligand_frames": np.asarray(
            [
                [[3.0, 0.0, 0.0], [5.4, 0.0, 0.0]],
                [[3.1, 0.1, 0.0], [5.5, 0.1, 0.0]],
            ],
            dtype=np.float32,
        ),
        "ligand_atom_frames": np.asarray(
            [
                [[3.0, 0.0, 0.0], [4.2, 0.0, 0.0], [5.4, 0.0, 0.0]],
                [[3.1, 0.1, 0.0], [4.3, 0.1, 0.0], [5.5, 0.1, 0.0]],
            ],
            dtype=np.float32,
        ),
        "ligand_atom_atomic_numbers": np.asarray([6, 6, 8], dtype=np.int16),
    }
    if protein_atom_frames:
        payload["protein_atom_frames"] = np.asarray(
            [
                [[0.0, 0.0, 0.0], [8.5, 0.0, 0.0], [5.5, 3.0, 0.0]],
                [[0.0, 0.0, 0.0], [8.5, 0.0, 0.0], [5.5, 3.0, 0.0]],
            ],
            dtype=np.float32,
        )
    np.savez(path, **payload)


def _write_recovery_json(path: Path, recovered_npz: Path, *, ready: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "entry_id": "ADRB2_GPCR_BLIND:ethanol",
                        "target": "ADRB2_GPCR_BLIND",
                        "ligand_id": "ethanol",
                        "collection_input_candidate_ready": ready,
                        "out_npz": str(recovered_npz),
                        "blockers": [] if ready else ["protein_atom_frames_missing"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_collector_writes_bounded_metric_npz_for_recovered_atomized_input(tmp_path: Path) -> None:
    pytest.importorskip("openmm")
    recovered = tmp_path / "recovered.npz"
    input_csv = tmp_path / "input.csv"
    recovery_json = tmp_path / "recovery.json"
    _write_recovered_npz(recovered)
    _write_input_csv(input_csv, recovered)
    _write_recovery_json(recovery_json, recovered)

    payload = mod.build_pocketmd_lite_bounded_metric_collector(
        input_csv=input_csv,
        recovery_json=recovery_json,
        out_root=tmp_path / "metrics",
        max_frames_per_row=2,
        openmm_max_iterations=5,
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "pocketmd_lite_bounded_metric_collector_ready"
    assert summary["measured_metric_row_count"] == 1
    assert row["claim_grade_metric_ready"] is True
    assert row["metric_source"] == mod.METRIC_SOURCE
    assert row["local_min_ligand_rmsd_a"] is not None
    assert row["contact_persistence"] is not None
    assert row["hbond_persistence"] is not None
    assert "full_protein_ligand_forcefield_parameterization_unavailable" in row["blockers"]
    with np.load(row["metric_npz"], allow_pickle=False) as metrics:
        assert "local_min_ligand_rmsd_a" in metrics.files
        assert "hbond_persistence" in metrics.files
        assert "initial_clash_count" in metrics.files
        assert str(metrics["pocketmd_lite_metric_source"].item()) == mod.METRIC_SOURCE
        assert metrics["full_forcefield_parameterization_claimed"].item() is False


def test_collector_keeps_rows_blocked_until_recovery_is_collection_ready(tmp_path: Path) -> None:
    recovered = tmp_path / "recovered.npz"
    input_csv = tmp_path / "input.csv"
    recovery_json = tmp_path / "recovery.json"
    _write_recovered_npz(recovered, protein_atom_frames=False)
    _write_input_csv(input_csv, recovered)
    _write_recovery_json(recovery_json, recovered, ready=False)

    payload = mod.build_pocketmd_lite_bounded_metric_collector(
        input_csv=input_csv,
        recovery_json=recovery_json,
        out_root=tmp_path / "metrics",
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "blocked_pocketmd_lite_bounded_metric_collector"
    assert summary["measured_metric_row_count"] == 0
    assert row["claim_grade_metric_ready"] is False
    assert row["blockers"] == ["protein_atom_frames_missing"]
    assert row["recommended_next_local_action"] == (
        "recover_or_generate_protein_atom_frames_then_rerun_bounded_metric_collector"
    )
