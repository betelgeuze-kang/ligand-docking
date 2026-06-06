from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
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


def test_build_casp17_win_tier_benchmark_operator_dashboard_summarizes_blocked_rows(tmp_path: Path) -> None:
    template = tmp_path / "template.csv"
    preflight_csv = tmp_path / "preflight.csv"
    preflight_json = tmp_path / "preflight.json"
    import_json = tmp_path / "import.json"
    closure_json = tmp_path / "closure.json"
    blockers = (
        "placeholder_target_id,prediction_pdb_not_found,native_pdb_not_found,"
        "ablation_layer_prediction_pdb_missing,selected_model_rank_required_1_to_5,"
        "leakage_clearance_required,operator_clearance_required"
    )
    _write_csv(
        template,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": "runs/prediction.pdb",
                "native_pdb": "runs/native.pdb",
            },
            {
                "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                "target_id": "REQUIRED_COMPLEX_001",
                "scope": "complex",
                "split": "historical",
                "prediction_pdb": "runs/complex_prediction.pdb",
                "native_pdb": "runs/complex_native.pdb",
            },
        ],
    )
    _write_csv(
        preflight_csv,
        [
            {
                "row_rank": 1,
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "operator_row_status": "blocked",
                "core_ready": "False",
                "ablation_ready": "False",
                "calibration_ready": "False",
                "prediction_pdb_exists": "False",
                "native_pdb_exists": "False",
                "ablation_layer_present_count": 0,
                "ablation_layer_required_count": 10,
                "missing_ablation_layers": "recursive,scored",
                "calibration_blockers": "selected_model_rank_required_1_to_5",
                "blockers": blockers,
            },
            {
                "row_rank": 2,
                "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                "target_id": "REQUIRED_COMPLEX_001",
                "scope": "complex",
                "operator_row_status": "blocked",
                "core_ready": "False",
                "ablation_ready": "False",
                "calibration_ready": "False",
                "prediction_pdb_exists": "False",
                "native_pdb_exists": "False",
                "ablation_layer_present_count": 0,
                "ablation_layer_required_count": 10,
                "missing_ablation_layers": "recursive,scored",
                "calibration_blockers": "selected_model_rank_required_1_to_5",
                "blockers": blockers,
            },
        ],
    )
    _write_json(
        preflight_json,
        {"summary": {"operator_preflight_status": "blocked", "ready_count": 0, "blocked_count": 2}},
    )
    _write_json(
        import_json,
        {
            "summary": {
                "import_status": "blocked",
                "historical_manifest_candidate_row_count": 0,
                "model_selection_calibration_candidate_row_count": 0,
            }
        },
    )
    _write_json(
        closure_json,
        {
            "summary": {
                "closure_status": "blocked_input",
                "current_proven_level": "review_quality",
                "next_unclosed_level": "competitive_floor",
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_operator_dashboard.py"),
            "--operator-template-csv",
            str(template),
            "--operator-preflight-json",
            str(preflight_json),
            "--operator-preflight-csv",
            str(preflight_csv),
            "--operator-import-json",
            str(import_json),
            "--closure-json",
            str(closure_json),
            "--out-json",
            str(tmp_path / "dashboard.json"),
            "--out-csv",
            str(tmp_path / "dashboard.csv"),
            "--out-md",
            str(tmp_path / "dashboard.md"),
            "--out-html",
            str(tmp_path / "dashboard.html"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = payload["rows"]
    html = (tmp_path / "dashboard.html").read_text(encoding="utf-8")

    assert summary["dashboard_status"] == "ready"
    assert summary["current_proven_level"] == "review_quality"
    assert summary["next_unclosed_level"] == "competitive_floor"
    assert summary["row_count"] == 2
    assert summary["ready_count"] == 0
    assert summary["blocked_count"] == 2
    assert summary["monomer_row_count"] == 1
    assert summary["complex_row_count"] == 1
    assert summary["monomer_metric_profile"] == "TM,GDT_TS,CA_lDDT"
    assert summary["complex_metric_profile"] == "TM,interface_F1,DockQ,QSbest,IPS"
    assert summary["needs_target_replacement_count"] == 2
    assert summary["needs_core_file_count"] == 2
    assert summary["needs_ablation_layer_count"] == 2
    assert summary["needs_calibration_count"] == 2
    assert summary["needs_provenance_count"] == 2
    assert rows[0]["metric_profile"] == "TM,GDT_TS,CA_lDDT"
    assert rows[1]["metric_profile"] == "TM,interface_F1,DockQ,QSbest,IPS"
    assert rows[1]["required_metric_profile"] == "TM,interface_F1,DockQ,QSbest,IPS"
    assert rows[0]["next_action"].startswith("Replace placeholder")
    assert "CASP17 Win Tier Benchmark Operator Dashboard" in html
    assert "TM,interface_F1,DockQ,QSbest,IPS" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "Local operator dashboard only" in payload["summary"]["claim_boundary"]
