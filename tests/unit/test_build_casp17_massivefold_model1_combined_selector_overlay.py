import json
from pathlib import Path

from tools import build_casp17_massivefold_model1_combined_selector_overlay as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ledger_row(target_id: str, *, decision: str, group: str = "rna_hybrid", probe: str = "", margin: str = "") -> dict:
    return {
        "target_id": target_id,
        "target_group": group,
        "target_family": "heteromer_or_immune_complex" if group == "protein_complex" else "",
        "ledger_decision": decision,
        "freeze_decision_class": (
            "conditional_freeze_ready"
            if decision == "external_model1_selected_conditional"
            else "watch_freeze_ready"
            if decision == "external_model1_selected_watch"
            else "manual_review_blocked"
            if decision == "external_model1_blocked_manual_review"
            else "review_only_unfrozen"
        ),
        "model1_freeze_state": "freeze_allowed_external_only_conditional",
        "selected_model_filename": f"{target_id}_selected.cif",
        "model1_filename": f"{target_id}_model1.cif",
        "probe_result": probe,
        "probe_margin": margin,
        "confidence_gap": "0.25",
        "top5_score_spread": "1.0",
        "mean_diversity_to_model1_rmsd": "10.0",
        "max_geometry_outlier_score": "1.0",
        "max_low_conf_atom_fraction": "0.01",
        "min_nearest_top5_rmsd": "2.0",
        "blockers": "",
    }


def test_massivefold_overlay_classifies_freeze_hold_block_and_probe(tmp_path):
    ledger_json = tmp_path / "ledger.json"
    risk_json = tmp_path / "risk.json"
    critical_json = tmp_path / "critical.json"
    baseline_json = tmp_path / "baseline.json"
    _write_json(
        ledger_json,
        {
            "summary": {"massivefold_model_selection_ledger_status": "massivefold_model_selection_ledger_ready_external_only"},
            "rows": [
                _ledger_row(
                    "R2350",
                    decision="external_model1_selected_conditional",
                    probe="probe_pass_model1_retained",
                    margin="0.75",
                ),
                _ledger_row(
                    "H2312",
                    group="protein_complex",
                    decision="external_model1_selected_watch",
                    probe="probe_pass_model1_retained",
                    margin="0.10",
                ),
                _ledger_row(
                    "R2352",
                    decision="external_model1_blocked_manual_review",
                    probe="probe_fail_model1_displaced",
                    margin="-0.20",
                ),
                _ledger_row("R2341", decision="external_model1_review_only_unfrozen"),
            ],
        },
    )
    _write_json(
        risk_json,
        {
            "summary": {"massivefold_model1_risk_queue_status": "massivefold_model1_risk_queue_ready_external_only"},
            "rows": [
                {"target_id": "R2350", "risk_tier": "critical_model1_margin", "low_margin": True},
                {"target_id": "H2312", "risk_tier": "critical_model1_margin", "low_margin": True},
                {"target_id": "R2352", "risk_tier": "critical_model1_margin", "low_margin": True},
                {"target_id": "R2341", "risk_tier": "low_margin_model1", "low_margin": True},
            ],
        },
    )
    _write_json(
        critical_json,
        {
            "summary": {
                "massivefold_critical_rerank_score_ledger_status": (
                    "massivefold_critical_rerank_score_ledger_ready_external_only"
                )
            },
            "rows": [
                {"target_id": "R2350", "risk_band": "calibrate_before_model1_freeze", "risk_score": "60.0"},
                {"target_id": "H2312", "risk_band": "critical_watch", "risk_score": "40.0"},
            ],
        },
    )
    _write_json(
        baseline_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_combined_selector_ledger_status": (
                    "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
                ),
                "baseline_capture_rate": "0.500",
                "baseline_non_capture_rate": "0.500",
            }
        },
    )
    args = mod.parse_args(
        [
            "--model-selection-ledger-json",
            str(ledger_json),
            "--risk-queue-json",
            str(risk_json),
            "--critical-rerank-score-ledger-json",
            str(critical_json),
            "--baseline-combined-selector-json",
            str(baseline_json),
            "--out-dir",
            str(tmp_path / "overlay"),
            "--out-json",
            str(tmp_path / "overlay.json"),
            "--out-csv",
            str(tmp_path / "overlay.csv"),
            "--out-md",
            str(tmp_path / "OVERLAY.md"),
        ]
    )

    payload = mod.build_payload(args)
    decisions = {row["target_id"]: row["overlay_decision"] for row in payload["rows"]}
    summary = payload["summary"]

    assert summary["massivefold_model1_combined_selector_overlay_status"] == (
        "massivefold_model1_combined_selector_overlay_ready_external_only"
    )
    assert decisions["R2350"] == "baseline_calibrated_freeze_ready"
    assert decisions["H2312"] == "selector_hold_interface_review"
    assert decisions["R2352"] == "selector_blocked_manual_review"
    assert decisions["R2341"] == "selector_probe_required"
    assert summary["freeze_ready_overlay_count"] == 1
    assert summary["not_freeze_ready_overlay_count"] == 3
    assert summary["baseline_capture_rate"] == "0.500"

    mod.write_outputs(args, payload)

    assert (tmp_path / "overlay.json").is_file()
    assert (tmp_path / "overlay.csv").is_file()
    assert (tmp_path / "OVERLAY.md").is_file()
    assert (tmp_path / "overlay" / "selector_overlay.csv").is_file()
