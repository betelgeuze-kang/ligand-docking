import json
from pathlib import Path

import pandas as pd

from tools import build_gpcr_score_reference_stats as mod


def test_build_payload_uses_fit_rows_only_and_records_eval_nonuse(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    split_csv = tmp_path / "split.csv"
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "binding_score_composite_v7": -10.0},
            {"target": "FIT_TARGET", "ligand_id": "fit_b", "binding_score_composite_v7": -6.0},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "eval_a", "binding_score_composite_v7": -30.0},
        ]
    ).to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "role": "fit"},
            {"target": "FIT_TARGET", "ligand_id": "fit_b", "role": "fit"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "eval_a", "role": "far_ood_eval"},
        ]
    ).to_csv(split_csv, index=False)

    payload = mod.build_payload(
        scores_csv=scores_csv,
        split_csv=split_csv,
        feature_cols=["binding_score_composite_v7"],
    )

    summary = payload["summary"]
    stats = payload["features"]["binding_score_composite_v7"]
    assert summary["status"] == "pass"
    assert summary["claim_safe_reference"] is True
    assert summary["reference_row_count"] == 2
    assert summary["excluded_role_available_row_count"] == 1
    assert summary["eval_role_used_in_reference_count"] == 0
    assert stats["count"] == 2
    assert stats["mean"] == -8.0
    assert round(stats["std"], 6) == round(2.8284271247461903, 6)


def test_build_payload_blocks_when_eval_role_is_requested_as_reference(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    split_csv = tmp_path / "split.csv"
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "binding_score_composite_v7": -10.0},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "eval_a", "binding_score_composite_v7": -30.0},
        ]
    ).to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "role": "fit"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "eval_a", "role": "far_ood_eval"},
        ]
    ).to_csv(split_csv, index=False)

    payload = mod.build_payload(
        scores_csv=scores_csv,
        split_csv=split_csv,
        include_roles=["fit", "far_ood_eval"],
        feature_cols=["binding_score_composite_v7"],
    )

    assert payload["summary"]["status"] == "blocked_eval_role_in_reference"
    assert payload["summary"]["claim_safe_reference"] is False
    assert payload["summary"]["eval_role_used_in_reference_count"] == 1


def test_main_writes_json_and_markdown(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    split_csv = tmp_path / "split.csv"
    out_json = tmp_path / "stats.json"
    out_md = tmp_path / "stats.md"
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "binding_score_composite_v7": -10.0},
            {"target": "FIT_TARGET", "ligand_id": "fit_b", "binding_score_composite_v7": -6.0},
        ]
    ).to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {"target": "FIT_TARGET", "ligand_id": "fit_a", "role": "fit"},
            {"target": "FIT_TARGET", "ligand_id": "fit_b", "role": "fit"},
        ]
    ).to_csv(split_csv, index=False)

    rc = mod.main(
        [
            "--scores-csv",
            str(scores_csv),
            "--split-csv",
            str(split_csv),
            "--feature-cols",
            "binding_score_composite_v7",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["summary"]["status"] == "pass"
    assert "binding_score_composite_v7" in out_md.read_text(encoding="utf-8")
