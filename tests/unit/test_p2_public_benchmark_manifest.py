from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.product.build_public_benchmark_manifest import build_public_benchmark_manifest


def test_public_benchmark_manifest_requires_license_for_known_dataset(tmp_path: Path) -> None:
    input_csv = tmp_path / "bench.csv"
    pd.DataFrame([
        {"target": "T1", "ligand_id": "L1", "receptor_path": "r.pdb", "ligand_path": "l.sdf", "split": "test"}
    ]).to_csv(input_csv, index=False)

    payload = build_public_benchmark_manifest(str(input_csv), dataset="pdbbind", out_json=str(tmp_path / "manifest.json"))

    assert payload["summary"]["status"] == "public_benchmark_manifest_license_receipt_required"
    assert payload["summary"]["dataset"] == "pdbbind_casf"
    assert payload["summary"]["row_count"] == 1


def test_public_benchmark_manifest_ready_for_custom_dataset(tmp_path: Path) -> None:
    input_csv = tmp_path / "bench.csv"
    pd.DataFrame([
        {
            "target": "T1",
            "ligand_id": "L1",
            "receptor_path": "r.pdb",
            "ligand_path": "l.sdf",
            "split": "test",
            "pose_rmsd_A": 1.5,
        }
    ]).to_csv(input_csv, index=False)

    payload = build_public_benchmark_manifest(
        str(input_csv), dataset="custom", out_json=str(tmp_path / "manifest.json"), out_csv=str(tmp_path / "manifest.csv")
    )

    assert payload["summary"]["status"] == "public_benchmark_manifest_ready"
    assert payload["rows"][0]["available_metric_columns"] == ["pose_rmsd_A"]
    assert (tmp_path / "manifest.csv").exists()
