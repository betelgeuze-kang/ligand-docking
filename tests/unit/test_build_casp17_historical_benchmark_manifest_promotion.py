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


def _write_watchlist(path: Path, current_targets: list[str]) -> None:
    path.write_text(
        json.dumps({"rows": [{"target_id": target_id, "human_open": True} for target_id in current_targets]}),
        encoding="utf-8",
    )


def _write_scaffold(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "benchmark_id",
        "target_id",
        "scope",
        "split",
        "prediction_pdb",
        "native_pdb",
        "leakage_clearance",
        *PROVENANCE,
        "manifest_ready_status",
        "blockers",
    ]
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_manifest_promotion_blocks_placeholder_and_missing_ready_rows(tmp_path: Path) -> None:
    scaffold = tmp_path / "scaffold.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist, [])
    _write_scaffold(
        scaffold,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER",
                "target_id": "REQUIRED_MONOMER",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": "",
                "native_pdb": "",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "manifest_ready_status": "blocked",
                "blockers": "prediction_pdb_missing",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_promotion.py"),
            "--scaffold-csv",
            str(scaffold),
            "--target-watchlist-json",
            str(watchlist),
            "--out-manifest-csv",
            str(tmp_path / "ready_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    ready_manifest = (tmp_path / "ready_manifest.csv").read_text(encoding="utf-8")

    assert payload["summary"]["promotion_status"] == "blocked"
    assert payload["summary"]["promoted_count"] == 0
    assert payload["summary"]["blocked_count"] == 1
    assert "ready_total_below_threshold" in payload["summary"]["threshold_blockers"]
    assert "placeholder_target_id" in payload["rows"][0]["blockers"]
    assert "recursive_prediction_pdb" in payload["summary"]["optional_ablation_layer_columns"]
    assert "statistical_rotamer_prediction_pdb" in ready_manifest.splitlines()[0]
    assert len(list(csv.DictReader(ready_manifest.splitlines()))) == 0


def test_manifest_promotion_promotes_monomer_and_complex_ready_rows(tmp_path: Path) -> None:
    monomer_prediction = tmp_path / "predictions/T9001_prediction.pdb"
    monomer_native = tmp_path / "natives/T9001_native.pdb"
    complex_prediction = tmp_path / "predictions/H9002_prediction.pdb"
    complex_native = tmp_path / "natives/H9002_native.pdb"
    for path in [monomer_prediction, monomer_native, complex_prediction, complex_native]:
        _write_pdb(path)
    scaffold = tmp_path / "scaffold.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist, ["T1331"])
    _write_scaffold(
        scaffold,
        [
            {
                "benchmark_id": "hist_T9001",
                "target_id": "T9001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(monomer_prediction),
                "native_pdb": str(monomer_native),
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "recursive_prediction_pdb": "runs/casp17_historical_ablation_predictions_current/recursive/T9001TS.pdb",
                "statistical_rotamer_prediction_pdb": "runs/casp17_historical_ablation_predictions_current/statistical_rotamer/T9001TS.pdb",
                "manifest_ready_status": "ready",
                "blockers": "",
            },
            {
                "benchmark_id": "hist_H9002",
                "target_id": "H9002",
                "scope": "complex",
                "split": "historical",
                "prediction_pdb": str(complex_prediction),
                "native_pdb": str(complex_native),
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "manifest_ready_status": "ready",
                "blockers": "",
            },
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_promotion.py"),
            "--scaffold-csv",
            str(scaffold),
            "--target-watchlist-json",
            str(watchlist),
            "--out-manifest-csv",
            str(tmp_path / "ready_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    ready_rows = list(csv.DictReader((tmp_path / "ready_manifest.csv").read_text(encoding="utf-8").splitlines()))

    assert payload["summary"]["promotion_status"] == "ready"
    assert payload["summary"]["promoted_count"] == 2
    assert payload["summary"]["monomer_promoted_count"] == 1
    assert payload["summary"]["complex_promoted_count"] == 1
    assert payload["summary"]["preserved_extra_column_count"] == 2
    assert "recursive_prediction_pdb" in payload["summary"]["preserved_extra_columns"]
    assert [row["target_id"] for row in ready_rows] == ["T9001", "H9002"]
    assert ready_rows[0]["prediction_created_at"] == "2024-01-01"
    assert ready_rows[0]["recursive_prediction_pdb"].endswith("/recursive/T9001TS.pdb")
    assert ready_rows[0]["statistical_rotamer_prediction_pdb"].endswith("/statistical_rotamer/T9001TS.pdb")
    assert "manifest_ready_status" not in ready_rows[0]


def test_manifest_promotion_blocks_current_casp17_targets(tmp_path: Path) -> None:
    prediction = tmp_path / "predictions/T1331_prediction.pdb"
    native = tmp_path / "natives/T1331_native.pdb"
    _write_pdb(prediction)
    _write_pdb(native)
    scaffold = tmp_path / "scaffold.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist, ["T1331"])
    _write_scaffold(
        scaffold,
        [
            {
                "benchmark_id": "hist_T1331",
                "target_id": "T1331",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
                **PROVENANCE,
                "manifest_ready_status": "ready",
                "blockers": "",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_promotion.py"),
            "--scaffold-csv",
            str(scaffold),
            "--target-watchlist-json",
            str(watchlist),
            "--out-manifest-csv",
            str(tmp_path / "ready_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--min-ready-complex",
            "0",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["promotion_status"] == "blocked"
    assert payload["summary"]["promoted_count"] == 0
    assert "current_casp17_target_not_allowed_for_historical_benchmark" in payload["rows"][0]["blockers"]


def test_manifest_promotion_blocks_missing_no_leak_provenance(tmp_path: Path) -> None:
    prediction = tmp_path / "predictions/T9001_prediction.pdb"
    native = tmp_path / "natives/T9001_native.pdb"
    _write_pdb(prediction)
    _write_pdb(native)
    scaffold = tmp_path / "scaffold.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist, [])
    _write_scaffold(
        scaffold,
        [
            {
                "benchmark_id": "hist_T9001",
                "target_id": "T9001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
                "manifest_ready_status": "ready",
                "blockers": "",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_manifest_promotion.py"),
            "--scaffold-csv",
            str(scaffold),
            "--target-watchlist-json",
            str(watchlist),
            "--out-manifest-csv",
            str(tmp_path / "ready_manifest.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--min-ready-complex",
            "0",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["promotion_status"] == "blocked"
    assert payload["summary"]["promoted_count"] == 0
    assert "prediction_created_at_required_iso_date" in payload["rows"][0]["blockers"]
    assert "operator_clearance_required" in payload["rows"][0]["blockers"]
