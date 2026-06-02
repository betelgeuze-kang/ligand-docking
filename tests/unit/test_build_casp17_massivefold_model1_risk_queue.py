import json
from pathlib import Path

from tools import build_casp17_massivefold_model1_risk_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_unified_model1_risk_queue(tmp_path):
    rna_json = tmp_path / "rna_self.json"
    protein_json = tmp_path / "protein_self.json"
    _write_json(
        rna_json,
        {
            "summary": {"low_margin_threshold": 1.0},
            "rows": [
                {
                    "target_id": "R2341",
                    "self_assessment_status": "ready_external_self_assessment_input",
                    "model1_filename": "rna_model1.cif",
                    "model1_protocol": "basic",
                    "confidence_gap": "0.4",
                    "top5_confidence_mean": "52.0",
                    "top5_score_spread": "1.0",
                    "mean_diversity_to_model1_rmsd": "40.0",
                    "min_nearest_top5_rmsd": "20.0",
                    "max_geometry_outlier_score": "2.0",
                    "max_low_conf_atom_fraction": "0.2",
                },
                {
                    "target_id": "R2345",
                    "self_assessment_status": "ready_external_self_assessment_input",
                    "model1_filename": "rna_guarded.cif",
                    "model1_protocol": "woUnpaired",
                    "confidence_gap": "1.5",
                    "top5_confidence_mean": "55.0",
                    "top5_score_spread": "4.0",
                    "mean_diversity_to_model1_rmsd": "30.0",
                    "min_nearest_top5_rmsd": "18.0",
                    "max_geometry_outlier_score": "1.0",
                    "max_low_conf_atom_fraction": "0.1",
                    "r2345_sequence_guard": "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only",
                },
            ],
        },
    )
    _write_json(
        protein_json,
        {
            "summary": {"low_margin_threshold": 2.0},
            "rows": [
                {
                    "target_id": "H1311",
                    "target_family": "heteromer_or_immune_complex",
                    "self_assessment_status": "ready_external_complex_self_assessment_input",
                    "model1_filename": "complex_model1.pdb",
                    "model1_protocol": "afm_basic_v3",
                "confidence_gap": "0.05",
                    "top5_confidence_mean": "102.0",
                    "top5_score_spread": "2.5",
                    "mean_diversity_to_model1_rmsd": "31.0",
                    "min_nearest_top5_rmsd": "2.4",
                    "max_geometry_outlier_score": "3.0",
                    "max_low_conf_atom_fraction": "0.01",
                    "missing_artifact_count": 0,
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
            "--out-dir",
            str(tmp_path / "queue"),
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "QUEUE.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model1_risk_queue_status"] == (
        "massivefold_model1_risk_queue_ready_external_only"
    )
    assert summary["target_count"] == 3
    assert summary["ready_target_count"] == 3
    assert summary["blocked_target_count"] == 0
    assert summary["low_margin_target_count"] == 2
    assert summary["critical_margin_target_count"] == 1
    assert summary["rna_hybrid_target_count"] == 2
    assert summary["protein_complex_target_count"] == 1
    assert summary["first_priority_target_id"] == "H1311"
    assert summary["first_priority_group"] == "protein_complex"

    rows = payload["rows"]
    assert rows[0]["target_id"] == "H1311"
    assert rows[0]["risk_tier"] == "critical_model1_margin"
    assert rows[1]["target_id"] == "R2341"
    assert rows[2]["target_id"] == "R2345"
    assert (tmp_path / "queue" / "01_protein_complex_h1311" / "RISK_ACTION.md").exists()
    assert "critical_model1_margin" in (tmp_path / "QUEUE.md").read_text(encoding="utf-8")


def test_marks_partial_when_a_self_assessment_row_is_blocked(tmp_path):
    rna_json = tmp_path / "rna_self.json"
    protein_json = tmp_path / "protein_self.json"
    _write_json(
        rna_json,
        {
            "summary": {"low_margin_threshold": 1.0},
            "rows": [
                {
                    "target_id": "R2341",
                    "self_assessment_status": "blocked_or_partial",
                    "model1_filename": "rna_model1.cif",
                    "confidence_gap": "0.1",
                    "missing_artifact_count": 1,
                }
            ],
        },
    )
    _write_json(protein_json, {"summary": {"low_margin_threshold": 2.0}, "rows": []})
    args = mod.parse_args(
        [
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
            "--out-dir",
            str(tmp_path / "queue"),
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "QUEUE.md"),
        ]
    )
    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["massivefold_model1_risk_queue_status"] == "massivefold_model1_risk_queue_partial"
    assert summary["ready_target_count"] == 0
    assert summary["blocked_target_count"] == 1
    assert "self_assessment_not_ready" in payload["rows"][0]["blockers"]
    assert "input_artifact_missing" in payload["rows"][0]["blockers"]
