import json
from pathlib import Path

from tools import build_casp17_massivefold_model_selection_ledger as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _self_row(target_id: str, filename: str, *, family: str = "") -> dict:
    return {
        "target_id": target_id,
        "target_family": family,
        "self_assessment_status": "ready_external_self_assessment_input",
        "model1_filename": filename,
        "model1_protocol": "basic",
        "model1_confidence_score": "10.0",
        "runner_up_confidence_score": "9.5",
        "confidence_gap": "0.5",
        "top5_score_spread": "1.0",
        "mean_diversity_to_model1_rmsd": "2.0",
        "max_geometry_outlier_score": "0.1",
        "max_low_conf_atom_fraction": "0.0",
        "min_nearest_top5_rmsd": "1.0",
        "target_self_assessment_md": f"self/{target_id}.md",
        "target_candidate_manifest_csv": f"self/{target_id}.csv",
    }


def test_builds_model_selection_ledger_from_freeze_and_self_assessment(tmp_path):
    freeze_json = tmp_path / "freeze.json"
    rna_json = tmp_path / "rna.json"
    protein_json = tmp_path / "protein.json"
    _write_json(
        freeze_json,
        {
            "summary": {
                "massivefold_model1_freeze_decision_packet_status": (
                    "massivefold_model1_freeze_decision_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "decision_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "freeze_decision": "freeze_ready_external_only_conditional",
                    "freeze_decision_class": "conditional_freeze_ready",
                    "model1_freeze_state": "freeze_allowed_external_only_conditional",
                    "final_model1_filename": "r2350_model1.cif",
                    "probe_result": "probe_pass_model1_retained",
                    "probe_margin": "0.6",
                    "decision_md": "freeze/r2350.md",
                },
                {
                    "decision_rank": 2,
                    "target_group": "rna_hybrid",
                    "target_id": "R2352",
                    "freeze_decision": "freeze_blocked_manual_review",
                    "freeze_decision_class": "manual_review_blocked",
                    "model1_freeze_state": "freeze_blocked_external_only",
                    "alternate_model1_filename": "r2352_alt.cif",
                    "probe_result": "probe_fail_model1_displaced",
                    "probe_margin": "-0.2",
                    "decision_md": "freeze/r2352.md",
                },
            ],
        },
    )
    _write_json(
        rna_json,
        {
            "summary": {"massivefold_rna_self_assessment_status": "massivefold_rna_self_assessment_ready_external_only"},
            "rows": [
                _self_row("R2350", "r2350_model1.cif"),
                _self_row("R2352", "r2352_model1.cif"),
                _self_row("R2341", "r2341_model1.cif"),
            ],
        },
    )
    _write_json(
        protein_json,
        {
            "summary": {
                "protein_complex_massivefold_self_assessment_status": (
                    "protein_complex_massivefold_self_assessment_ready_external_only"
                )
            },
            "rows": [_self_row("H2312", "h2312_model1.pdb", family="heteromer_or_immune_complex")],
        },
    )
    args = mod.parse_args(
        [
            "--freeze-decision-json",
            str(freeze_json),
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
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
    assert summary["massivefold_model_selection_ledger_status"] == (
        "massivefold_model_selection_ledger_ready_external_only"
    )
    assert summary["ledger_count"] == 4
    assert summary["ready_ledger_count"] == 4
    assert summary["conditional_selected_count"] == 1
    assert summary["watch_selected_count"] == 0
    assert summary["manual_review_blocked_count"] == 1
    assert summary["review_only_unfrozen_count"] == 2
    assert summary["freeze_ready_selected_count"] == 1
    assert summary["first_ledger_target_id"] == "R2350"
    assert summary["first_manual_review_target_id"] == "R2352"

    rows = payload["rows"]
    assert rows[0]["target_id"] == "R2350"
    assert rows[0]["ledger_decision"] == "external_model1_selected_conditional"
    assert rows[0]["selected_model_filename"] == "r2350_model1.cif"
    assert rows[1]["target_id"] == "R2352"
    assert rows[1]["ledger_decision"] == "external_model1_blocked_manual_review"
    assert rows[1]["alternate_model_filename"] == "r2352_alt.cif"
    assert {row["ledger_decision"] for row in rows[2:]} == {"external_model1_review_only_unfrozen"}
    assert (tmp_path / "ledger" / "01_rna_hybrid_r2350" / "MODEL_SELECTION_LEDGER.md").exists()
    assert "external no-native" in (tmp_path / "LEDGER.md").read_text(encoding="utf-8")


def test_marks_partial_when_freeze_row_lacks_self_assessment(tmp_path):
    freeze_json = tmp_path / "freeze.json"
    rna_json = tmp_path / "rna.json"
    protein_json = tmp_path / "protein.json"
    _write_json(
        freeze_json,
        {
            "summary": {
                "massivefold_model1_freeze_decision_packet_status": (
                    "massivefold_model1_freeze_decision_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "freeze_decision": "freeze_ready_external_only_conditional",
                    "freeze_decision_class": "conditional_freeze_ready",
                    "model1_freeze_state": "freeze_allowed_external_only_conditional",
                }
            ],
        },
    )
    _write_json(
        rna_json,
        {
            "summary": {"massivefold_rna_self_assessment_status": "massivefold_rna_self_assessment_ready_external_only"},
            "rows": [],
        },
    )
    _write_json(
        protein_json,
        {
            "summary": {
                "protein_complex_massivefold_self_assessment_status": (
                    "protein_complex_massivefold_self_assessment_ready_external_only"
                )
            },
            "rows": [],
        },
    )
    args = mod.parse_args(
        [
            "--freeze-decision-json",
            str(freeze_json),
            "--rna-self-assessment-json",
            str(rna_json),
            "--protein-complex-self-assessment-json",
            str(protein_json),
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

    assert payload["summary"]["massivefold_model_selection_ledger_status"] == (
        "massivefold_model_selection_ledger_partial"
    )
    assert payload["summary"]["blocked_ledger_count"] == 1
    assert payload["rows"][0]["blockers"] == "self_assessment_row_missing"
