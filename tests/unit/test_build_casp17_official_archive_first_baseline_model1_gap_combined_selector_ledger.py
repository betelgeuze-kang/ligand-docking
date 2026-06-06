import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_model1_gap_combined_selector_ledger as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_combined_selector_promotes_retains_and_holds(tmp_path):
    triage_json = tmp_path / "triage.json"
    feature_json = tmp_path / "feature.json"
    consensus_json = tmp_path / "consensus.json"
    _write_json(
        triage_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_triage_status": (
                    "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T000",
                "first_native_pdb_code": "TEST",
            },
            "rows": [
                {
                    "target_id": "T000",
                    "group_id": "101",
                    "triage_band": "catastrophic_model1_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "50.000",
                    "model1_model_id": "T000TS101_1",
                    "best_top5_model_id": "T000TS101_3",
                },
                {
                    "target_id": "T000",
                    "group_id": "102",
                    "triage_band": "large_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "25.000",
                    "model1_model_id": "T000TS102_1",
                    "best_top5_model_id": "T000TS102_4",
                },
                {
                    "target_id": "T000",
                    "group_id": "103",
                    "triage_band": "large_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "10.000",
                    "model1_model_id": "T000TS103_1",
                    "best_top5_model_id": "T000TS103_2",
                },
            ],
        },
    )
    _write_json(
        feature_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_feature_probe_status": (
                    "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
                )
            },
            "rows": [
                {
                    "group_id": "101",
                    "geometry_signal": "ambiguous",
                    "geometry_risk_delta_model1_minus_best": "0.100",
                },
                {
                    "group_id": "102",
                    "geometry_signal": "ambiguous",
                    "geometry_risk_delta_model1_minus_best": "-0.200",
                },
                {
                    "group_id": "103",
                    "geometry_signal": "supports_model1",
                    "geometry_risk_delta_model1_minus_best": "-9.000",
                },
            ],
        },
    )
    _write_json(
        consensus_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_consensus_probe_status": (
                    "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
                )
            },
            "rows": [
                {
                    "group_id": "101",
                    "consensus_signal": "supports_best_top5",
                    "consensus_margin_model1_minus_best": "8.000",
                    "model1_consensus_rank": 5,
                    "best_top5_consensus_rank": 1,
                    "consensus_top_model_id": "T000TS101_3",
                },
                {
                    "group_id": "102",
                    "consensus_signal": "supports_model1",
                    "consensus_margin_model1_minus_best": "-4.000",
                    "model1_consensus_rank": 1,
                    "best_top5_consensus_rank": 3,
                    "consensus_top_model_id": "T000TS102_1",
                },
                {
                    "group_id": "103",
                    "consensus_signal": "supports_best_top5",
                    "consensus_margin_model1_minus_best": "3.000",
                    "model1_consensus_rank": 4,
                    "best_top5_consensus_rank": 1,
                    "consensus_top_model_id": "T000TS103_2",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--triage-json",
            str(triage_json),
            "--feature-probe-json",
            str(feature_json),
            "--consensus-probe-json",
            str(consensus_json),
            "--out-dir",
            str(tmp_path / "selector"),
            "--out-json",
            str(tmp_path / "selector.json"),
            "--out-csv",
            str(tmp_path / "selector.csv"),
            "--out-md",
            str(tmp_path / "SELECTOR.md"),
        ]
    )

    payload = mod.build_payload(args)
    summary = payload["summary"]
    decisions = {row["group_id"]: row["selector_decision"] for row in payload["rows"]}

    assert summary["official_archive_first_baseline_model1_gap_combined_selector_ledger_status"] == (
        "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
    )
    assert decisions == {"101": "promote_best_top5", "102": "retain_model1", "103": "hold_manual_review"}
    assert summary["promote_best_top5_count"] == 1
    assert summary["retain_model1_count"] == 1
    assert summary["hold_manual_review_count"] == 1
    assert summary["corrected_model1_failure_count"] == 1
    assert summary["retained_model1_failure_count"] == 1
    assert summary["manual_hold_model1_failure_count"] == 1
    assert summary["baseline_capture_rate"] == "0.333"

    mod.write_outputs(args, payload)

    assert (tmp_path / "selector.json").is_file()
    assert (tmp_path / "selector.csv").is_file()
    assert (tmp_path / "SELECTOR.md").is_file()
    assert (tmp_path / "selector" / "combined_selector_ledger.csv").is_file()
