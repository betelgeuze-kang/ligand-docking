from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


FIELDNAMES = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_pdb(path: Path, target: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                f"TARGET {target}",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                "ATOM      1 CA   ALA A   1       0.000   0.000   0.000  1.00 80.00           C  ",
                "ATOM      2 CB   ALA A   1       0.000   1.500   0.000  1.00 80.00           C  ",
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _ready_row(prediction: Path, native: Path) -> dict[str, object]:
    return {
        "benchmark_id": "hist_HIST001",
        "target_id": "HIST001",
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics_fixture",
        "prediction_created_at": "2025-01-01",
        "native_release_date": "2025-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
    }


def test_sidechain_native_manifest_sync_blocks_placeholder_and_missing_inputs(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    workorder = tmp_path / "workorder.json"
    _write_csv(
        manifest,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(tmp_path / "missing_prediction.pdb"),
                "native_pdb": str(tmp_path / "missing_native.pdb"),
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "prediction_method": "REQUIRED_INTERNAL_METHOD",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
            }
        ],
    )
    workorder.write_text(
        json.dumps(
            {
                "summary": {
                    "sidechain_native_benchmark_status": "blocked",
                    "workorder_action_count": 3,
                    "open_workorder_action_count": 3,
                },
                "rows": [
                    {
                        "action_id": "hist_REQUIRED_MONOMER_001:leakage_clearance",
                        "action_status": "open",
                        "next_action": "Replace placeholder leakage_clearance with operator-confirmed no_leak provenance.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_manifest_sync_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--workorder-json",
            str(workorder),
            "--target-watchlist-json",
            str(tmp_path / "missing_watchlist.json"),
            "--min-ready-total",
            "1",
            "--min-ready-monomer",
            "1",
            "--min-ready-complex",
            "0",
            "--out-manifest-csv",
            str(tmp_path / "candidate.csv"),
            "--out-json",
            str(tmp_path / "sync.json"),
            "--out-csv",
            str(tmp_path / "sync.csv"),
            "--out-md",
            str(tmp_path / "sync.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads((tmp_path / "sync.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    row = payload["rows"][0]
    candidate_rows = list(csv.DictReader((tmp_path / "candidate.csv").open(encoding="utf-8")))

    assert summary["sync_status"] == "blocked"
    assert summary["ready_row_count"] == 0
    assert summary["blocked_row_count"] == 1
    assert summary["workorder_open_action_count"] == 3
    assert summary["first_open_workorder_action_id"] == "hist_REQUIRED_MONOMER_001:leakage_clearance"
    assert row["sync_status"] == "blocked"
    assert "placeholder_target_id" in row["blockers"]
    assert "prediction_pdb_not_found" in row["blockers"]
    assert "native_pdb_not_found" in row["blockers"]
    assert candidate_rows == []
    assert "Sidechain-Native Manifest Sync Packet" in (tmp_path / "sync.md").read_text(encoding="utf-8")


def test_sidechain_native_manifest_sync_writes_ready_candidate_rows(tmp_path: Path) -> None:
    prediction = tmp_path / "prediction.pdb"
    native = tmp_path / "native.pdb"
    manifest = tmp_path / "manifest.csv"
    workorder = tmp_path / "workorder.json"
    _write_pdb(prediction, "HIST001")
    _write_pdb(native, "HIST001")
    _write_csv(manifest, [_ready_row(prediction, native)])
    workorder.write_text(
        json.dumps(
            {
                "summary": {
                    "sidechain_native_benchmark_status": "pass",
                    "workorder_action_count": 0,
                    "open_workorder_action_count": 0,
                },
                "rows": [],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_manifest_sync_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--workorder-json",
            str(workorder),
            "--target-watchlist-json",
            str(tmp_path / "missing_watchlist.json"),
            "--min-ready-total",
            "1",
            "--min-ready-monomer",
            "1",
            "--min-ready-complex",
            "0",
            "--out-manifest-csv",
            str(tmp_path / "candidate.csv"),
            "--out-json",
            str(tmp_path / "sync.json"),
            "--out-csv",
            str(tmp_path / "sync.csv"),
            "--out-md",
            str(tmp_path / "sync.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "sync.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    candidate_rows = list(csv.DictReader((tmp_path / "candidate.csv").open(encoding="utf-8")))

    assert summary["sync_status"] == "ready_for_sidechain_native_scoring"
    assert summary["ready_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert summary["ready_monomer_count"] == 1
    assert summary["ready_complex_count"] == 0
    assert summary["threshold_blockers"] == ""
    assert payload["rows"][0]["prediction_atom_record_count"] == 2
    assert payload["rows"][0]["native_atom_record_count"] == 2
    assert payload["candidate_manifest_rows"][0]["target_id"] == "HIST001"
    assert candidate_rows[0]["target_id"] == "HIST001"
    assert "Local sidechain-native manifest sync only" in summary["claim_boundary"]
