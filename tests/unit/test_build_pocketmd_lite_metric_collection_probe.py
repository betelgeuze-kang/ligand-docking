from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from tools.product import build_pocketmd_lite_metric_collection_probe as mod


_COLUMNS = [
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


def _write_input_csv(path: Path, npz_path: Path, *, ligand_smiles: str = "CCO") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "entry_id": "T:L",
                "target": "T",
                "ligand_id": "L",
                "required_collection_metrics": "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count",
                "selected_trajectory_npz": str(npz_path),
                "selected_trajectory_source": "exact_basename_restore_candidate",
                "selected_trajectory_readable": "true",
                "selected_trajectory_claim_grade_metric_fields_present": "false",
                "protein_structure_source_path": "protein.pdb",
                "protein_structure_source_path_available": "true",
                "ligand_smiles": ligand_smiles,
                "ligand_smiles_present": "true" if ligand_smiles else "false",
                "collection_input_ready": "true",
                "claim_grade_metrics_already_present": "false",
            }
        )


def _write_npz(path: Path, *, include_metric_fields: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "protein_ca": np.asarray([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]], dtype=np.float32),
        "ligand_frames": np.asarray(
            [
                [[2.8, 0.0, 0.0], [4.4, 0.0, 0.0]],
                [[3.0, 0.0, 0.0], [4.6, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
        "frame_indices": np.asarray([0, 1], dtype=np.int32),
    }
    if include_metric_fields:
        payload["local_min_ligand_rmsd_a"] = np.asarray(1.1, dtype=np.float32)
        payload["hbond_persistence"] = np.asarray(0.7, dtype=np.float32)
        payload["initial_clash_count"] = np.asarray(2, dtype=np.int32)
    np.savez(path, **payload)


def _write_bounded_metric_collector_json(path: Path, metric_npz: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "entry_id": "T:L",
                        "status": "pocketmd_lite_bounded_metric_collector_metric_ready",
                        "metric_npz": str(metric_npz),
                        "claim_grade_metric_ready": True,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_probe_keeps_two_bead_collection_proxy_only(tmp_path: Path) -> None:
    npz_path = tmp_path / "traj.npz"
    input_csv = tmp_path / "input.csv"
    _write_npz(npz_path)
    _write_input_csv(input_csv, npz_path)

    payload = mod.build_pocketmd_lite_metric_collection_probe(input_csv=input_csv)

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_metric_collection_probe_proxy_only"
    assert summary["candidate_count"] == 1
    assert summary["telemetry_ready_count"] == 1
    assert summary["claim_grade_metric_ready_count"] == 0
    assert summary["candidate_csv_update_allowed"] is False
    row = payload["rows"][0]
    assert row["trajectory_schema"] == "coarse_two_bead_ca"
    assert row["coarse_local_min_survival_proxy"] is True
    assert row["coarse_hbond_persistence_proxy"] is not None
    assert row["claim_grade_metric_ready"] is False
    assert "initial_clash_count" in row["missing_claim_grade_metrics"]
    assert "ligand_trajectory_is_two_bead_proxy" in row["blockers"]


def test_probe_accepts_explicit_npz_metric_fields(tmp_path: Path) -> None:
    npz_path = tmp_path / "traj.npz"
    input_csv = tmp_path / "input.csv"
    _write_npz(npz_path, include_metric_fields=True)
    _write_input_csv(input_csv, npz_path)

    payload = mod.build_pocketmd_lite_metric_collection_probe(input_csv=input_csv)

    assert payload["summary"]["status"] == "pocketmd_lite_metric_collection_probe_ready"
    row = payload["rows"][0]
    assert row["claim_grade_metric_ready"] is True
    assert abs(row["exact_local_min_ligand_rmsd_a"] - 1.1) < 1e-6
    assert abs(row["exact_hbond_persistence"] - 0.7) < 1e-6
    assert row["exact_initial_clash_count"] == 2
    assert row["missing_claim_grade_metrics"] == []
    assert row["recommended_next_local_action"] == (
        "extract_claim_grade_metrics_into_candidate_csv_then_rerun_pocketmd_lite_report"
    )


def test_probe_accepts_bounded_metric_collector_npz_as_exact_source(tmp_path: Path) -> None:
    selected_npz = tmp_path / "selected.npz"
    metric_npz = tmp_path / "bounded_metrics.npz"
    input_csv = tmp_path / "input.csv"
    collector_json = tmp_path / "collector.json"
    _write_npz(selected_npz)
    _write_npz(metric_npz, include_metric_fields=True)
    _write_input_csv(input_csv, selected_npz)
    _write_bounded_metric_collector_json(collector_json, metric_npz)

    payload = mod.build_pocketmd_lite_metric_collection_probe(
        input_csv=input_csv,
        bounded_metric_collector_json=collector_json,
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "pocketmd_lite_metric_collection_probe_ready"
    assert summary["bounded_metric_source_ready_count"] == 1
    assert row["claim_grade_metric_ready"] is True
    assert row["exact_metric_source_npz"] == str(metric_npz)
    assert row["exact_metric_source_status"] == "pocketmd_lite_bounded_metric_collector_metric_ready"
    assert row["selected_trajectory_npz"] == str(selected_npz)
    assert abs(row["exact_local_min_ligand_rmsd_a"] - 1.1) < 1e-6


def test_main_writes_probe_artifacts(tmp_path: Path) -> None:
    npz_path = tmp_path / "traj.npz"
    input_csv = tmp_path / "input.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_npz(npz_path)
    _write_input_csv(input_csv, npz_path)

    rc = mod.main(
        [
            "--input-csv",
            str(input_csv),
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
    assert payload["summary"]["candidate_count"] == 1
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Metric Collection Probe")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["entry_id"] == "T:L"
