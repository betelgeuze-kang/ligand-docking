import json
from pathlib import Path

from tools import build_casp17_massivefold_critical_rerank_score_ledger as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_no_native_score_ledger(tmp_path):
    experiment_json = tmp_path / "experiments.json"
    _write_json(
        experiment_json,
        {
            "summary": {
                "massivefold_critical_rerank_experiment_status": (
                    "massivefold_critical_rerank_experiment_ready_external_only"
                )
            },
            "rows": [
                {
                    "experiment_rank": 1,
                    "queue_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "confidence_gap": "0.02",
                    "gap_severity_score": "0.8",
                    "diversity_review_flag": "high_diversity_review",
                    "geometry_review_flag": "geometry_watch",
                    "low_confidence_review_flag": "low_confidence_watch",
                    "recommended_review_order": "top5_diversity_then_geometry_then_model1_gap",
                    "model1_filename": "r2350_model1.cif",
                    "model1_protocol": "woPaired",
                    "experiment_md": "experiments/r2350.md",
                },
                {
                    "experiment_rank": 2,
                    "queue_rank": 2,
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "confidence_gap": "0.08",
                    "gap_severity_score": "0.2",
                    "diversity_review_flag": "compact_top5_review",
                    "geometry_review_flag": "geometry_outlier_review",
                    "low_confidence_review_flag": "low_confidence_atom_review",
                    "recommended_review_order": "interface_geometry_then_model1_gap_then_top5_diversity",
                    "model1_filename": "h2312_model1.pdb",
                    "model1_protocol": "afm_basic_v1",
                    "experiment_md": "experiments/h2312.md",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--experiment-json",
            str(experiment_json),
            "--out-dir",
            str(tmp_path / "ledger"),
            "--out-json",
            str(tmp_path / "ledger.json"),
            "--out-csv",
            str(tmp_path / "ledger.csv"),
            "--out-md",
            str(tmp_path / "LEDGER.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_critical_rerank_score_ledger_status"] == (
        "massivefold_critical_rerank_score_ledger_ready_external_only"
    )
    assert summary["ledger_count"] == 2
    assert summary["ready_ledger_count"] == 2
    assert summary["calibrate_before_model1_freeze_count"] == 2
    assert summary["top_risk_target_id"] == "R2350"
    assert summary["top_risk_band"] == "calibrate_before_model1_freeze"

    rows = payload["rows"]
    assert rows[0]["target_id"] == "R2350"
    assert rows[0]["risk_score"] == "66"
    assert rows[1]["target_id"] == "H2312"
    assert rows[1]["interface_component"] == "0.15"
    assert (tmp_path / "ledger" / "01_rna_hybrid_r2350" / "SCORE_LEDGER.md").exists()
    assert "no-native" in (tmp_path / "LEDGER.md").read_text(encoding="utf-8")


def test_marks_partial_for_blocked_row_or_source(tmp_path):
    experiment_json = tmp_path / "experiments.json"
    _write_json(
        experiment_json,
        {
            "summary": {
                "massivefold_critical_rerank_experiment_status": (
                    "massivefold_critical_rerank_experiment_partial"
                )
            },
            "rows": [
                {
                    "experiment_rank": 1,
                    "queue_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "gap_severity_score": "0.8",
                    "blockers": "input_artifact_missing",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--experiment-json",
            str(experiment_json),
            "--out-dir",
            str(tmp_path / "ledger"),
            "--out-json",
            str(tmp_path / "ledger.json"),
            "--out-csv",
            str(tmp_path / "ledger.csv"),
            "--out-md",
            str(tmp_path / "LEDGER.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_critical_rerank_score_ledger_status"] == (
        "massivefold_critical_rerank_score_ledger_partial"
    )
    assert payload["summary"]["ready_ledger_count"] == 0
    assert payload["summary"]["blocked_ledger_count"] == 1
    assert payload["rows"][0]["ledger_status"] == "blocked_rerank_score"
