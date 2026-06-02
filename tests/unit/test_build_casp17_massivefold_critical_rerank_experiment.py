import json
from pathlib import Path

from tools import build_casp17_massivefold_critical_rerank_experiment as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_critical_rerank_experiment_packet(tmp_path):
    risk_json = tmp_path / "risk_queue.json"
    _write_json(
        risk_json,
        {
            "summary": {
                "massivefold_model1_risk_queue_status": (
                    "massivefold_model1_risk_queue_ready_external_only"
                )
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "target_family": "rna_hybrid",
                    "risk_tier": "critical_model1_margin",
                    "confidence_gap": "0.02",
                    "top5_score_spread": "0.2",
                    "top5_confidence_mean": "83.0",
                    "mean_diversity_to_model1_rmsd": "48.0",
                    "min_nearest_top5_rmsd": "25.0",
                    "max_geometry_outlier_score": "1.7",
                    "max_low_conf_atom_fraction": "0.02",
                    "model1_filename": "r2350_model1.cif",
                    "model1_protocol": "woPaired",
                    "target_action_md": "risk/r2350.md",
                },
                {
                    "queue_rank": 2,
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "target_family": "heteromer_or_immune_complex",
                    "risk_tier": "critical_model1_margin",
                    "confidence_gap": "0.08",
                    "top5_score_spread": "1.2",
                    "top5_confidence_mean": "101.0",
                    "mean_diversity_to_model1_rmsd": "18.0",
                    "min_nearest_top5_rmsd": "2.8",
                    "max_geometry_outlier_score": "3.2",
                    "max_low_conf_atom_fraction": "0.05",
                    "model1_filename": "h2312_model1.pdb",
                    "model1_protocol": "afm_basic_v1",
                    "target_action_md": "risk/h2312.md",
                },
                {
                    "queue_rank": 3,
                    "target_group": "rna_hybrid",
                    "target_id": "R2341",
                    "target_family": "rna_hybrid",
                    "risk_tier": "high_model1_margin",
                    "confidence_gap": "0.2",
                    "model1_filename": "not_selected.cif",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--risk-queue-json",
            str(risk_json),
            "--out-dir",
            str(tmp_path / "experiments"),
            "--out-json",
            str(tmp_path / "experiments.json"),
            "--out-csv",
            str(tmp_path / "experiments.csv"),
            "--out-md",
            str(tmp_path / "EXPERIMENTS.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_critical_rerank_experiment_status"] == (
        "massivefold_critical_rerank_experiment_ready_external_only"
    )
    assert summary["experiment_count"] == 2
    assert summary["ready_experiment_count"] == 2
    assert summary["rna_hybrid_experiment_count"] == 1
    assert summary["protein_complex_experiment_count"] == 1
    assert summary["high_diversity_review_count"] == 1
    assert summary["geometry_review_count"] == 1
    assert summary["low_confidence_review_count"] == 1
    assert summary["first_experiment_target_id"] == "R2350"

    rows = payload["rows"]
    assert [row["target_id"] for row in rows] == ["R2350", "H2312"]
    assert rows[0]["diversity_review_flag"] == "high_diversity_review"
    assert rows[1]["recommended_review_order"] == "interface_geometry_then_model1_gap_then_top5_diversity"
    assert (tmp_path / "experiments" / "01_rna_hybrid_r2350" / "EXPERIMENT.md").exists()
    assert "no-native" in (tmp_path / "EXPERIMENTS.md").read_text(encoding="utf-8")


def test_marks_partial_when_source_is_not_ready_or_row_blocked(tmp_path):
    risk_json = tmp_path / "risk_queue.json"
    _write_json(
        risk_json,
        {
            "summary": {"massivefold_model1_risk_queue_status": "massivefold_model1_risk_queue_partial"},
            "rows": [
                {
                    "queue_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "risk_tier": "critical_model1_margin",
                    "confidence_gap": "0.02",
                    "missing_artifact_count": 1,
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--risk-queue-json",
            str(risk_json),
            "--out-dir",
            str(tmp_path / "experiments"),
            "--out-json",
            str(tmp_path / "experiments.json"),
            "--out-csv",
            str(tmp_path / "experiments.csv"),
            "--out-md",
            str(tmp_path / "EXPERIMENTS.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_critical_rerank_experiment_status"] == (
        "massivefold_critical_rerank_experiment_partial"
    )
    assert payload["summary"]["ready_experiment_count"] == 0
    assert payload["summary"]["blocked_experiment_count"] == 1
    assert "input_artifact_missing" in payload["rows"][0]["blockers"]
