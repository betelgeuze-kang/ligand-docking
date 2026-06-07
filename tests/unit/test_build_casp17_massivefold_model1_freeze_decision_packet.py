import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_model1_freeze_decision_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_freeze_decisions_from_probe_outcomes(tmp_path):
    probe_outcome_json = tmp_path / "probe_outcome.json"
    _write_json(
        probe_outcome_json,
        {
            "summary": {
                "massivefold_model1_probe_outcome_status": (
                    "massivefold_model1_probe_outcome_ready_external_only"
                )
            },
            "rows": [
                {
                    "outcome_rank": 1,
                    "outcome_status": "ready_external_no_native_probe_outcome",
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "probe_type": "top5_rerank_consistency_probe",
                    "probe_result": "probe_pass_model1_retained",
                    "probe_margin": "0.6",
                    "freeze_after_probe_recommendation": (
                        "conditional_model1_freeze_ready_external_only"
                    ),
                    "model1_filename": "r2350_model1.cif",
                    "top_candidate_filename": "r2350_model1.cif",
                    "top_candidate_role": "model1",
                    "model1_probe_score": "83.0",
                    "top_candidate_probe_score": "83.0",
                    "outcome_md": "outcomes/r2350.md",
                },
                {
                    "outcome_rank": 2,
                    "outcome_status": "ready_external_no_native_probe_outcome",
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "probe_type": "lightweight_rescore_probe",
                    "probe_result": "probe_pass_model1_retained",
                    "probe_margin": "0.1",
                    "freeze_after_probe_recommendation": "watch_model1_freeze_ready_after_probe",
                    "model1_filename": "h2312_model1.pdb",
                    "top_candidate_filename": "h2312_model1.pdb",
                    "top_candidate_role": "model1",
                    "model1_probe_score": "76.0",
                    "top_candidate_probe_score": "76.0",
                    "outcome_md": "outcomes/h2312.md",
                },
                {
                    "outcome_rank": 3,
                    "outcome_status": "ready_external_no_native_probe_outcome",
                    "target_group": "rna_hybrid",
                    "target_id": "R2352",
                    "probe_type": "lightweight_rescore_probe",
                    "probe_result": "probe_fail_model1_displaced",
                    "probe_margin": "-0.2",
                    "freeze_after_probe_recommendation": (
                        "keep_model1_freeze_blocked_and_escalate_manual_review"
                    ),
                    "model1_filename": "r2352_model1.cif",
                    "top_candidate_filename": "r2352_alt.cif",
                    "top_candidate_role": "top5_decoy",
                    "model1_probe_score": "70.0",
                    "top_candidate_probe_score": "70.2",
                    "outcome_md": "outcomes/r2352.md",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--probe-outcome-json",
            str(probe_outcome_json),
            "--out-dir",
            str(tmp_path / "decisions"),
            "--out-json",
            str(tmp_path / "decisions.json"),
            "--out-csv",
            str(tmp_path / "decisions.csv"),
            "--out-md",
            str(tmp_path / "DECISIONS.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model1_freeze_decision_packet_status"] == (
        "massivefold_model1_freeze_decision_packet_ready_external_only"
    )
    assert summary["decision_count"] == 3
    assert summary["ready_decision_count"] == 3
    assert summary["blocked_decision_count"] == 0
    assert summary["freeze_ready_total_count"] == 2
    assert summary["freeze_blocked_total_count"] == 1
    assert summary["conditional_freeze_ready_count"] == 1
    assert summary["watch_freeze_ready_count"] == 1
    assert summary["manual_review_blocked_count"] == 1
    assert summary["first_freeze_ready_target_id"] == "R2350"
    assert summary["first_blocked_target_id"] == "R2352"

    rows = payload["rows"]
    assert rows[0]["freeze_decision"] == "freeze_ready_external_only_conditional"
    assert rows[0]["final_model1_filename"] == "r2350_model1.cif"
    assert rows[1]["freeze_decision"] == "freeze_ready_external_only_watch"
    assert rows[2]["freeze_decision"] == "freeze_blocked_manual_review"
    assert rows[2]["final_model1_filename"] == ""
    assert rows[2]["alternate_model1_filename"] == "r2352_alt.cif"
    assert (tmp_path / "decisions" / "01_rna_hybrid_r2350" / "FREEZE_DECISION.md").exists()
    assert "external no-native" in (tmp_path / "DECISIONS.md").read_text(encoding="utf-8")


def test_marks_partial_when_source_probe_outcome_is_blocked(tmp_path):
    probe_outcome_json = tmp_path / "probe_outcome.json"
    _write_json(
        probe_outcome_json,
        {
            "summary": {
                "massivefold_model1_probe_outcome_status": "massivefold_model1_probe_outcome_partial"
            },
            "rows": [
                {
                    "outcome_rank": 1,
                    "outcome_status": "blocked_probe_outcome",
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "probe_result": "probe_fail_model1_displaced",
                    "freeze_after_probe_recommendation": (
                        "keep_model1_freeze_blocked_and_escalate_manual_review"
                    ),
                    "blockers": "candidate_rows_missing",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--probe-outcome-json",
            str(probe_outcome_json),
            "--out-dir",
            str(tmp_path / "decisions"),
            "--out-json",
            str(tmp_path / "decisions.json"),
            "--out-csv",
            str(tmp_path / "decisions.csv"),
            "--out-md",
            str(tmp_path / "DECISIONS.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_model1_freeze_decision_packet_status"] == (
        "massivefold_model1_freeze_decision_packet_partial"
    )
    assert payload["summary"]["ready_decision_count"] == 0
    assert payload["summary"]["blocked_decision_count"] == 1
    assert "candidate_rows_missing" in payload["rows"][0]["blockers"]
    assert "source_probe_outcome_blocked" in payload["rows"][0]["blockers"]
