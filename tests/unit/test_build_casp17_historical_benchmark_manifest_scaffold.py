from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = {
    "prediction_method": "internal_physics_fixture",
    "prediction_created_at": "2024-01-01",
    "native_release_date": "2024-06-01",
    "prediction_generated_before_native_release": "true",
    "public_template_or_native_used_for_prediction": "false",
    "other_team_model_used": "false",
    "post_release_information_used": "false",
    "current_casp17_target": "false",
    "operator_clearance": "no_leak",
}


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "MODEL 1",
                "ATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C  ",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_historical_benchmark_manifest_scaffold_blocks_without_local_inputs(tmp_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_scaffold.py"),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--native-dir",
            str(tmp_path / "natives"),
            "--existing-manifest-csv",
            str(tmp_path / "missing_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["source_mode"] == "placeholder_required_inputs"
    assert payload["summary"]["scaffold_status"] == "blocked"
    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["ready_count"] == 0
    assert payload["summary"]["monomer_candidate_count"] == 1
    assert payload["summary"]["complex_candidate_count"] == 1
    assert "prediction_created_at" in payload["summary"]["required_provenance_columns"]
    assert all(row["manifest_ready_status"] == "blocked" for row in payload["rows"])
    assert "leakage_clearance_required" in payload["rows"][0]["blockers"]
    assert "prediction_created_at_required_iso_date" in payload["rows"][0]["blockers"]
    assert "operator_clearance_required" in payload["rows"][0]["blockers"]
    assert "recursive_prediction_pdb" in payload["summary"]["optional_ablation_layer_columns"]
    assert "statistical_rotamer_prediction_pdb" in (tmp_path / "scaffold.csv").read_text(encoding="utf-8").splitlines()[0]


def test_historical_benchmark_manifest_scaffold_reads_ready_existing_manifest(tmp_path: Path) -> None:
    prediction = tmp_path / "predictions" / "T9001_prediction.pdb"
    native = tmp_path / "natives" / "T9001_native.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_pdb(prediction)
    _write_pdb(native)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark_id",
                "target_id",
                "scope",
                "split",
                "prediction_pdb",
                "native_pdb",
                "leakage_clearance",
                *PROVENANCE,
                "recursive_prediction_pdb",
                "statistical_rotamer_prediction_pdb",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9001",
                "target_id": "T9001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "recursive_prediction_pdb": "runs/casp17_historical_ablation_predictions_current/recursive/T9001TS.pdb",
                "statistical_rotamer_prediction_pdb": "runs/casp17_historical_ablation_predictions_current/statistical_rotamer/T9001TS.pdb",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_scaffold.py"),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--native-dir",
            str(tmp_path / "natives"),
            "--existing-manifest-csv",
            str(manifest),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    csv_text = (tmp_path / "scaffold.csv").read_text(encoding="utf-8")

    assert payload["summary"]["source_mode"] == "existing_manifest"
    assert payload["summary"]["scaffold_status"] == "ready"
    assert payload["summary"]["ready_count"] == 1
    assert "statistical_rotamer_prediction_pdb" in payload["summary"]["optional_ablation_layer_columns"]
    assert payload["summary"]["preserved_extra_column_count"] == 2
    assert "recursive_prediction_pdb" in payload["summary"]["preserved_extra_columns"]
    assert payload["rows"][0]["manifest_ready_status"] == "ready"
    assert payload["rows"][0]["blockers"] == ""
    assert payload["rows"][0]["recursive_prediction_pdb"].endswith("/recursive/T9001TS.pdb")
    assert payload["rows"][0]["statistical_rotamer_prediction_pdb"].endswith("/statistical_rotamer/T9001TS.pdb")
    assert "hist_T9001" in csv_text
    assert "recursive_prediction_pdb" in csv_text


def test_historical_benchmark_manifest_scaffold_scans_local_pairs_but_requires_clearance(tmp_path: Path) -> None:
    _write_pdb(tmp_path / "predictions" / "H9002_prediction.pdb")
    _write_pdb(tmp_path / "natives" / "H9002_native.pdb")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_scaffold.py"),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--native-dir",
            str(tmp_path / "natives"),
            "--existing-manifest-csv",
            str(tmp_path / "missing_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["source_mode"] == "scanned_local_dirs"
    assert payload["summary"]["complex_candidate_count"] == 1
    assert row["target_id"] == "H9002"
    assert row["scope"] == "complex"
    assert row["manifest_ready_status"] == "blocked"
    assert row["prediction_pdb"]
    assert row["native_pdb"]
    assert "leakage_clearance_required" in row["blockers"]
    assert "prediction_created_at_required_iso_date" in row["blockers"]


def test_historical_benchmark_manifest_scaffold_merges_scanned_pair_provenance(tmp_path: Path) -> None:
    _write_pdb(tmp_path / "predictions" / "H9002_prediction.pdb")
    _write_pdb(tmp_path / "natives" / "H9002_native.pdb")
    provenance = tmp_path / "provenance.csv"
    with provenance.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark_id",
                "target_id",
                "scope",
                "split",
                "leakage_clearance",
                *PROVENANCE,
                "recursive_prediction_pdb",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_H9002",
                "target_id": "H9002",
                "scope": "complex",
                "split": "historical",
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "recursive_prediction_pdb": str(tmp_path / "layers" / "recursive" / "H9002TS.pdb"),
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_scaffold.py"),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--native-dir",
            str(tmp_path / "natives"),
            "--existing-manifest-csv",
            str(tmp_path / "missing_manifest.csv"),
            "--provenance-csv",
            str(provenance),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--out-provenance-template-csv",
            str(tmp_path / "provenance_template.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    template_text = (tmp_path / "provenance_template.csv").read_text(encoding="utf-8")

    assert payload["summary"]["source_mode"] == "scanned_local_dirs"
    assert payload["summary"]["scaffold_status"] == "ready"
    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["provenance_row_count"] == 1
    assert payload["summary"]["provenance_applied_count"] == 1
    assert row["manifest_ready_status"] == "ready"
    assert row["blockers"] == ""
    assert row["leakage_clearance"] == "no_leak"
    assert row["prediction_method"] == "internal_physics_fixture"
    assert row["recursive_prediction_pdb"].endswith("/layers/recursive/H9002TS.pdb")
    assert "hist_H9002" in template_text
    assert "recursive_prediction_pdb" in template_text


def test_historical_benchmark_manifest_scaffold_blocks_post_release_prediction(tmp_path: Path) -> None:
    prediction = tmp_path / "predictions" / "T9001_prediction.pdb"
    native = tmp_path / "natives" / "T9001_native.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_pdb(prediction)
    _write_pdb(native)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark_id",
                "target_id",
                "scope",
                "split",
                "prediction_pdb",
                "native_pdb",
                "leakage_clearance",
                *PROVENANCE,
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9001",
                "target_id": "T9001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "prediction_created_at": "2024-06-01",
                "native_release_date": "2024-06-01",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_scaffold.py"),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--native-dir",
            str(tmp_path / "natives"),
            "--existing-manifest-csv",
            str(manifest),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["scaffold_status"] == "blocked"
    assert "prediction_date_not_before_native_release" in payload["rows"][0]["blockers"]
