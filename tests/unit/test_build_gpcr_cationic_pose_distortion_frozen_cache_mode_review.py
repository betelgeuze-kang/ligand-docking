from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_cationic_pose_distortion_frozen_cache_mode_review_blocks_nonportable_modes(
    tmp_path: Path,
) -> None:
    none_positive = tmp_path / "none_positive.csv"
    allbasic_positive = tmp_path / "allbasic_positive.csv"
    none_scores = tmp_path / "none_scores.csv"
    allbasic_scores = tmp_path / "allbasic_scores.csv"
    labels = tmp_path / "labels.csv"
    out_json = tmp_path / "review.json"
    out_md = tmp_path / "review.md"
    _write_csv(
        none_positive,
        [
            {
                "target": "DRD2",
                "ligand_id": "CHEMBL301265",
                "label_free_support_pressure": 0.0,
                "label_free_penalty_pressure": 0.0,
                "cationic_center_contact_fraction_2p8_4p2A": 0.0,
            }
        ],
    )
    _write_csv(
        allbasic_positive,
        [
            {
                "target": "DRD2",
                "ligand_id": "CHEMBL301265",
                "label_free_support_pressure": 0.65,
                "label_free_penalty_pressure": 0.0,
                "cationic_center_contact_fraction_2p8_4p2A": 1.0,
            }
        ],
    )
    _write_csv(
        none_scores,
        [
            {"target": "DRD2", "ligand_id": "CHEMBL301265", "binding_score_composite_v7_residual_shadow": -5.0},
            {"target": "DRD2", "ligand_id": "decoy_1", "binding_score_composite_v7_residual_shadow": -1.0},
        ],
    )
    _write_csv(
        allbasic_scores,
        [
            {"target": "DRD2", "ligand_id": "decoy_1", "binding_score_composite_v7_residual_shadow": -9.0},
            {"target": "DRD2", "ligand_id": "CHEMBL301265", "binding_score_composite_v7_residual_shadow": -5.0},
        ],
    )
    _write_csv(
        labels,
        [
            {"target": "DRD2", "ligand_id": "CHEMBL301265", "is_binder": 1},
            {"target": "DRD2", "ligand_id": "decoy_1", "is_binder": 0},
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_cationic_pose_distortion_frozen_cache_mode_review.py"),
            "--none-positive-cache-csv",
            str(none_positive),
            "--allbasic-positive-cache-csv",
            str(allbasic_positive),
            "--none-partial-replay-scores-csv",
            str(none_scores),
            "--allbasic-partial-replay-scores-csv",
            str(allbasic_scores),
            "--labels-csv",
            str(labels),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert summary["status"] == "blocked_feature_contract_not_portable_yet"
    assert "label_free_none_anchor_mode_does_not_rescue_drd2_positive" in summary["blockers"]
    assert "all_basic_anchor_mode_overpromotes_decoys_in_partial_replay" in summary["blockers"]
    assert summary["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["partial_frozen_cache_is_not_claim_evidence"] is True
    assert "blocked_feature_contract_not_portable_yet" in out_md.read_text(encoding="utf-8")
