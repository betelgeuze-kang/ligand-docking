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


def _write_pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "MODEL 1\nATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    return str(path)


def _ready_row(root: Path, target_id: str, scope: str) -> dict[str, str]:
    row = {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": scope,
        "split": "historical",
        "prediction_pdb": _write_pdb(root / "predictions" / f"{target_id}_prediction.pdb"),
        "native_pdb": _write_pdb(root / "natives" / f"{target_id}_native.pdb"),
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
        "selected_score": "42.0",
        "best_score": "43.0",
    }
    for layer in LAYERS:
        row[f"{layer}_prediction_pdb"] = _write_pdb(root / "layers" / layer / f"{target_id}TS.pdb")
    return row


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
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


def test_win_tier_benchmark_operator_preflight_passes_ready_rows(tmp_path: Path) -> None:
    template = tmp_path / "operator.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_json(watchlist, {"rows": [{"target_id": "T1331", "human_open": True}]})
    _write_csv(template, [_ready_row(tmp_path, "T9001", "monomer"), _ready_row(tmp_path, "H9002", "complex")])

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_operator_preflight.py"),
            "--operator-template-csv",
            str(template),
            "--target-watchlist-json",
            str(watchlist),
            "--min-ready-total",
            "2",
            "--min-ready-monomer",
            "1",
            "--min-ready-complex",
            "1",
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "preflight.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))

    assert payload["summary"]["operator_preflight_status"] == "pass"
    assert payload["summary"]["ready_count"] == 2
    assert payload["summary"]["missing_ablation_layer_file_count"] == 0
    assert all(row["operator_row_status"] == "ready" for row in payload["rows"])
    assert "does not fetch natives" in payload["summary"]["claim_boundary"]


def test_win_tier_benchmark_operator_preflight_blocks_placeholders_and_missing_files(tmp_path: Path) -> None:
    template = tmp_path / "operator.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_json(watchlist, {"rows": [{"target_id": "T1331", "human_open": True}]})
    row = _ready_row(tmp_path, "T9001", "monomer")
    row["target_id"] = "REQUIRED_MONOMER_001"
    row["prediction_pdb"] = str(tmp_path / "missing_prediction.pdb")
    row["native_pdb"] = str(tmp_path / "missing_native.pdb")
    row["selected_model_rank"] = ""
    row["best_native_metric"] = ""
    row["recursive_prediction_pdb"] = str(tmp_path / "missing_layer.pdb")
    _write_csv(template, [row])

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_operator_preflight.py"),
            "--operator-template-csv",
            str(template),
            "--target-watchlist-json",
            str(watchlist),
            "--min-ready-total",
            "1",
            "--min-ready-monomer",
            "1",
            "--min-ready-complex",
            "0",
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "preflight.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))
    blockers = payload["rows"][0]["blockers"]

    assert result.returncode == 2
    assert payload["summary"]["operator_preflight_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["missing_prediction_count"] == 1
    assert payload["summary"]["missing_native_count"] == 1
    assert payload["summary"]["missing_ablation_layer_file_count"] == 1
    assert payload["summary"]["calibration_blocked_count"] == 1
    assert "placeholder_target_id" in blockers
    assert "selected_model_rank_required_1_to_5" in blockers
    assert "ablation_layer_prediction_pdb_missing" in blockers
