import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_model1_probe_outcome as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_probe_outcomes_from_self_assessment_candidates(tmp_path):
    worklist_json = tmp_path / "worklist.json"
    rna_json = tmp_path / "rna_self.json"
    protein_json = tmp_path / "protein_self.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "massivefold_model1_probe_worklist_status": (
                    "massivefold_model1_probe_worklist_ready_external_only"
                )
            },
            "rows": [
                {
                    "workitem_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "probe_type": "top5_rerank_consistency_probe",
                    "probe_priority": 1,
                    "model1_filename": "model1.cif",
                    "model1_freeze_decision": "hold_model1_freeze_probe_required",
                    "workitem_md": "work/r2350.md",
                },
                {
                    "workitem_rank": 2,
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "probe_type": "lightweight_rescore_probe",
                    "probe_priority": 2,
                    "model1_filename": "model1.pdb",
                    "model1_freeze_decision": "conditional_watch_probe_before_final_model1",
                    "workitem_md": "work/h2312.md",
                },
            ],
        },
    )
    _write_json(
        rna_json,
        {
            "candidate_rows": [
                {
                    "target_id": "R2350",
                    "filename": "model1.cif",
                    "input_role": "model1",
                    "input_rank": 1,
                    "confidence_score": "10.0",
                    "geometry_outlier_score": "0.0",
                    "low_conf_atom_fraction": "0.0",
                    "diversity_to_model1_rmsd": "0.0",
                },
                {
                    "target_id": "R2350",
                    "filename": "decoy.cif",
                    "input_role": "top5_decoy",
                    "input_rank": 2,
                    "confidence_score": "9.9",
                    "geometry_outlier_score": "1.0",
                    "low_conf_atom_fraction": "0.1",
                    "diversity_to_model1_rmsd": "10.0",
                },
            ]
        },
    )
    _write_json(
        protein_json,
        {
            "candidate_rows": [
                {
                    "target_id": "H2312",
                    "filename": "model1.pdb",
                    "input_role": "model1",
                    "input_rank": 1,
                    "confidence_score": "8.0",
                    "geometry_outlier_score": "2.0",
                },
                {
                    "target_id": "H2312",
                    "filename": "decoy.pdb",
                    "input_role": "top5_decoy",
                    "input_rank": 2,
                    "confidence_score": "8.2",
                    "geometry_outlier_score": "0.0",
                },
            ]
        },
    )
    args = mod.parse_args(
        [
            "--probe-worklist-json",
            str(worklist_json),
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
            "--out-dir",
            str(tmp_path / "outcomes"),
            "--out-json",
            str(tmp_path / "outcomes.json"),
            "--out-csv",
            str(tmp_path / "outcomes.csv"),
            "--out-md",
            str(tmp_path / "OUTCOMES.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model1_probe_outcome_status"] == (
        "massivefold_model1_probe_outcome_ready_external_only"
    )
    assert summary["outcome_count"] == 2
    assert summary["probe_pass_count"] == 1
    assert summary["probe_fail_count"] == 1
    assert summary["freeze_ready_recommendation_count"] == 1
    assert summary["first_outcome_target_id"] == "R2350"

    rows = payload["rows"]
    assert rows[0]["target_id"] == "R2350"
    assert rows[0]["probe_result"] == "probe_pass_model1_retained"
    assert rows[0]["freeze_after_probe_recommendation"] == (
        "conditional_model1_freeze_ready_external_only"
    )
    assert rows[1]["target_id"] == "H2312"
    assert rows[1]["probe_result"] == "probe_fail_model1_displaced"
    assert rows[1]["freeze_after_probe_recommendation"] == (
        "keep_model1_freeze_blocked_and_escalate_manual_review"
    )
    assert (tmp_path / "outcomes" / "01_rna_hybrid_r2350" / "PROBE_OUTCOME.md").exists()
    assert "no-native" in (tmp_path / "OUTCOMES.md").read_text(encoding="utf-8")


def test_marks_partial_when_candidate_rows_are_missing(tmp_path):
    worklist_json = tmp_path / "worklist.json"
    rna_json = tmp_path / "rna_self.json"
    protein_json = tmp_path / "protein_self.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "massivefold_model1_probe_worklist_status": (
                    "massivefold_model1_probe_worklist_ready_external_only"
                )
            },
            "rows": [
                {
                    "workitem_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "probe_type": "top5_rerank_consistency_probe",
                    "probe_priority": 1,
                }
            ],
        },
    )
    _write_json(rna_json, {"candidate_rows": []})
    _write_json(protein_json, {"candidate_rows": []})
    args = mod.parse_args(
        [
            "--probe-worklist-json",
            str(worklist_json),
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
            "--out-dir",
            str(tmp_path / "outcomes"),
            "--out-json",
            str(tmp_path / "outcomes.json"),
            "--out-csv",
            str(tmp_path / "outcomes.csv"),
            "--out-md",
            str(tmp_path / "OUTCOMES.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_model1_probe_outcome_status"] == (
        "massivefold_model1_probe_outcome_partial"
    )
    assert payload["summary"]["ready_outcome_count"] == 0
    assert payload["summary"]["blocked_outcome_count"] == 1
    assert "candidate_rows_missing" in payload["rows"][0]["blockers"]
