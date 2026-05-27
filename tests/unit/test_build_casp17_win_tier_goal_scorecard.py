from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_tier_goal_scorecard_tracks_operator_goal_bands(tmp_path: Path) -> None:
    goal = tmp_path / "CASP17_WIN_TIER_GOAL.md"
    closure = tmp_path / "closure.json"
    inventory = tmp_path / "inventory.json"
    sidechain = tmp_path / "sidechain.json"
    historical = tmp_path / "historical.json"
    calibration = tmp_path / "calibration.json"

    goal.write_text(
        "\n".join(
            [
                "# CASP17 Win-Tier Goal Addendum",
                "- CASP17 scaffold score: `65 -> 90`",
                "- CASP17 competitive proof score: `15-25 -> 85-90`",
                "- category leaderboard objective: `top-5/top-3/top-1-2`",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        closure,
        {
            "summary": {
                "closure_status": "pass",
                "first_operator_input_action_id": "",
            }
        },
    )
    _write_json(
        inventory,
        {
            "summary": {
                "required_file_count": 480,
                "present_file_count": 480,
                "missing_file_count": 0,
            }
        },
    )
    _write_json(
        sidechain,
        {
            "summary": {
                "sidechain_native_benchmark_status": "pass",
                "pass_count": 40,
                "benchmark_count": 40,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "metric_surface_status": "pass",
                "casp15_regular_domain_winner_ratio": 0.92,
                "casp16_regular_domain_winner_ratio": 0.91,
                "casp16_domain_winner_ratio": 0.91,
                "model1_best_of5_gap_fraction": 0.06,
                "catastrophic_fail_count": 0,
                "monomer_win_tier_status": "pass",
                "dockq_acceptable_fraction": 0.93,
                "dockq_medium_fraction": 0.76,
                "dockq_high_fraction": 0.52,
                "immune_hard_target_high_fraction": 0.43,
                "mean_lddt_pli": 0.82,
                "bisyrmsd_2a_hit_fraction": 0.71,
                "affinity_kendall_tau": 0.56,
            }
        },
    )
    _write_json(
        calibration,
        {
            "summary": {
                "calibration_status": "pass",
                "top1_selection_accuracy": 0.72,
                "score_native_correlation": 0.73,
                "high_confidence_false_positive_rate": 0.04,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_goal_scorecard.py"),
            "--goal-addendum-md",
            str(goal),
            "--win-gap-closure-json",
            str(closure),
            "--benchmark-input-inventory-json",
            str(inventory),
            "--sidechain-native-benchmark-json",
            str(sidechain),
            "--historical-benchmark-json",
            str(historical),
            "--model-selection-calibration-json",
            str(calibration),
            "--out-json",
            str(tmp_path / "scorecard.json"),
            "--out-csv",
            str(tmp_path / "scorecard.csv"),
            "--out-md",
            str(tmp_path / "scorecard.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "scorecard.json").read_text(encoding="utf-8"))
    rows = {row["gate"]: row for row in payload["rows"]}

    assert payload["summary"]["scorecard_status"] == "pass"
    assert payload["summary"]["row_count"] == 10
    assert payload["summary"]["scaffold_score_current"] == 65
    assert payload["summary"]["scaffold_score_target"] == 90
    assert payload["summary"]["competitive_proof_score_current_band"] == "15-25"
    assert payload["summary"]["competitive_proof_score_target_band"] == "85-90"
    assert payload["summary"]["historical_bands"]["casp15_regular_domain"]["top3_cutoff"] == 85.0
    assert payload["summary"]["historical_bands"]["casp16_regular_domain"]["top5_cutoff"] == 33.3
    assert rows["goal_contract_documented"]["status"] == "pass"
    assert rows["winner_normalized_replay"]["target"].endswith(">= 0.90")
    assert rows["immune_protein_complex"]["status"] == "pass"
    assert rows["organic_ligand_protein_complex"]["status"] == "pass"
    assert rows["accuracy_estimation_model_selection"]["status"] == "pass"

    md = (tmp_path / "scorecard.md").read_text(encoding="utf-8")
    assert "CASP17 Win-Tier Goal Scorecard" in md
    assert "competitive proof score: `15-25 -> 85-90`" in md
    assert "DockQ acceptable >=90%" in md
