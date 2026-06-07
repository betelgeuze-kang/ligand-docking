from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAYERS = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _template_row(target_id: str, scope: str) -> dict[str, str]:
    row = {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": scope,
        "split": "historical",
        "prediction_pdb": f"predictions/{target_id}.pdb",
        "native_pdb": f"natives/{target_id}.pdb",
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics",
        "prediction_created_at": "2025-01-01",
        "native_release_date": "2025-06-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
        "selected_model_rank": "1",
        "best_model_rank": "1",
        "selected_native_metric": "0.91",
        "best_native_metric": "0.92",
        "selected_score": "12.0",
        "best_score": "13.0",
    }
    for layer in LAYERS:
        row[f"{layer}_prediction_pdb"] = f"layers/{layer}/{target_id}.pdb"
    return row


def _write_template(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_operator_import_packet_writes_candidate_manifests_when_preflight_passes(tmp_path: Path) -> None:
    template = tmp_path / "operator.csv"
    preflight = tmp_path / "preflight.json"
    _write_template(template, [_template_row("T9001", "monomer"), _template_row("H9002", "complex")])
    _write_json(preflight, {"summary": {"operator_preflight_status": "pass", "ready_count": 2, "blocked_count": 0}})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_operator_import_packet.py"),
            "--operator-template-csv",
            str(template),
            "--operator-preflight-json",
            str(preflight),
            "--min-ready-total",
            "2",
            "--out-historical-manifest-csv",
            str(tmp_path / "historical_manifest.csv"),
            "--out-calibration-csv",
            str(tmp_path / "calibration.csv"),
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
    historical_rows = list(csv.DictReader((tmp_path / "historical_manifest.csv").open("r", encoding="utf-8", newline="")))
    calibration_rows = list(csv.DictReader((tmp_path / "calibration.csv").open("r", encoding="utf-8", newline="")))

    assert payload["summary"]["import_status"] == "pass"
    assert payload["summary"]["historical_manifest_candidate_row_count"] == 2
    assert payload["summary"]["model_selection_calibration_candidate_row_count"] == 2
    assert historical_rows[0]["target_id"] == "T9001"
    assert historical_rows[0]["recursive_prediction_pdb"] == "layers/recursive/T9001.pdb"
    assert calibration_rows[1]["benchmark_id"] == "hist_H9002"
    assert calibration_rows[1]["best_native_metric"] == "0.92"
    assert "does not fetch natives" in payload["summary"]["claim_boundary"]


def test_operator_import_packet_blocks_when_preflight_not_pass(tmp_path: Path) -> None:
    template = tmp_path / "operator.csv"
    preflight = tmp_path / "preflight.json"
    _write_template(template, [_template_row("T9001", "monomer")])
    _write_json(preflight, {"summary": {"operator_preflight_status": "blocked", "ready_count": 0, "blocked_count": 1}})

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_operator_import_packet.py"),
            "--operator-template-csv",
            str(template),
            "--operator-preflight-json",
            str(preflight),
            "--min-ready-total",
            "1",
            "--out-historical-manifest-csv",
            str(tmp_path / "historical_manifest.csv"),
            "--out-calibration-csv",
            str(tmp_path / "calibration.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    historical_rows = list(csv.DictReader((tmp_path / "historical_manifest.csv").open("r", encoding="utf-8", newline="")))
    calibration_rows = list(csv.DictReader((tmp_path / "calibration.csv").open("r", encoding="utf-8", newline="")))

    assert result.returncode == 2
    assert payload["summary"]["import_status"] == "blocked"
    assert "operator_preflight_not_pass" in payload["summary"]["blockers"]
    assert historical_rows == []
    assert calibration_rows == []
