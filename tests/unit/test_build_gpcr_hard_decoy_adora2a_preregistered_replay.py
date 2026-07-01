from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from tools.product import build_gpcr_hard_decoy_adora2a_preregistered_replay as mod
from tools.product.build_gpcr_hard_decoy_adora2a_neutral_rescue_probe import (
    BASELINE_BLEND_SCORE_COL,
    SCORE_COL as PROBE_SCORE_COL,
)


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    scores = tmp_path / "scores.csv"
    labels = tmp_path / "labels.csv"
    split = tmp_path / "split.csv"
    probe_scores = tmp_path / "probe_scores.csv"
    targets = [
        "CHEMBL217_DRD2_HUMAN",
        "CHEMBL224_HTR2A_HUMAN",
        "CHEMBL233_OPRM1_HUMAN",
        "CHEMBL251_ADORA2A_HUMAN",
    ]
    score_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    probe_rows: list[dict[str, object]] = []
    for target in targets:
        for idx in range(6):
            ligand_id = f"{target}_{idx}"
            is_binder = idx == 0
            is_adora2a = target == "CHEMBL251_ADORA2A_HUMAN"
            h_donors = 0 if is_binder else 2
            h_acceptors = 5 if is_binder and is_adora2a else 4
            basic_amine_count = 0 if is_binder else 1
            baseline_score = -1.0 if is_binder else 0.0
            support = bool(is_adora2a and is_binder)
            pressure = bool(is_adora2a and not is_binder)
            probe_score = baseline_score - (0.8 if support else 0.0) + (1.2 if pressure else 0.0)
            score_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "mean_min_distance_A": 4.0 if is_binder else 5.0 + idx * 0.1,
                    "binding_score_composite_v7": 0.5,
                    "ligand_h_donors": h_donors,
                    "ligand_h_acceptors": h_acceptors,
                    "ligand_logp": 4.0,
                    "ligand_rot_bonds": 4,
                    "basic_amine_count": basic_amine_count,
                }
            )
            label_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "is_binder": int(is_binder),
                    "reference_binding_kcal_mol": -10 if is_binder else -2,
                }
            )
            split_rows.append({"target": target, "ligand_id": ligand_id, "role": "far_ood_eval"})
            probe_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "mean_min_distance_A": 4.0 if is_binder else 5.0 + idx * 0.1,
                    BASELINE_BLEND_SCORE_COL: baseline_score,
                    PROBE_SCORE_COL: probe_score,
                }
            )
    _write_csv(
        scores,
        score_rows,
        [
            "target",
            "ligand_id",
            "mean_min_distance_A",
            "binding_score_composite_v7",
            "ligand_h_donors",
            "ligand_h_acceptors",
            "ligand_logp",
            "ligand_rot_bonds",
            "basic_amine_count",
        ],
    )
    _write_csv(
        labels,
        label_rows,
        ["target", "ligand_id", "is_binder", "reference_binding_kcal_mol"],
    )
    _write_csv(split, split_rows, ["target", "ligand_id", "role"])
    _write_csv(
        probe_scores,
        probe_rows,
        ["target", "ligand_id", "mean_min_distance_A", BASELINE_BLEND_SCORE_COL, PROBE_SCORE_COL],
    )
    return scores, labels, split, probe_scores


def test_preregistered_replay_uses_runner_and_matches_probe_score(tmp_path: Path) -> None:
    scores, labels, split, probe_scores = _fixture(tmp_path)
    spec_json = tmp_path / "spec.json"

    scores_out, payload = mod.build_replay(
        scores_csv=scores,
        labels_csv=labels,
        split_csv=split,
        probe_scores_csv=probe_scores,
        prototype_spec_json=spec_json,
        bootstrap_n=20,
    )

    assert payload["status"] == "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked"
    assert payload["prototype_variant"] == mod.VARIANT
    assert payload["canonical_runner_status"] == "shadow_ready_claim_locked"
    assert payload["canonical_runner_shadow_only_active_locked"] is True
    assert payload["score_matches_probe"] is True
    assert payload["max_abs_score_diff_vs_probe"] == 0.0
    assert payload["runner_replay_closure_gate_pass"] is True
    assert payload["runner_replay_target_heldout"]["ranking_pr_auc_ci_low"] >= 0.45
    assert payload["runner_replay_target_heldout"]["top20_hit_rate"] >= 0.20
    assert payload["claim_promotion_allowed"] is False
    assert mod.SCORE_COL in scores_out.columns
    assert json.loads(spec_json.read_text(encoding="utf-8"))["summary"]["prototype_variant"] == mod.VARIANT


def test_preregistered_replay_writes_outputs(tmp_path: Path) -> None:
    scores, labels, split, probe_scores = _fixture(tmp_path)
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"

    rc = mod.main(
        [
            "--scores-csv",
            str(scores),
            "--labels-csv",
            str(labels),
            "--split-csv",
            str(split),
            "--probe-scores-csv",
            str(probe_scores),
            "--prototype-spec-json",
            str(tmp_path / "spec.json"),
            "--bootstrap-n",
            "20",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-scores-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == mod.PACKET_TYPE
    assert out_md.read_text(encoding="utf-8").startswith(
        "# GPCR Hard-Decoy ADORA2A Pre-Registered Replay"
    )
    assert mod.SCORE_COL in pd.read_csv(out_csv).columns
