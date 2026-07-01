from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from tools.product import build_gpcr_hard_decoy_adora2a_neutral_rescue_probe as mod


def test_adora2a_neutral_support_and_basic_pressure_are_target_scoped() -> None:
    df = pd.DataFrame(
        [
            {
                "target": "CHEMBL251_ADORA2A_HUMAN",
                "ligand_h_donors": 0,
                "ligand_h_acceptors": 5,
                "ligand_logp": 4.2,
                "ligand_rot_bonds": 4,
                "basic_amine_count": 0,
            },
            {
                "target": "CHEMBL251_ADORA2A_HUMAN",
                "ligand_h_donors": 2,
                "ligand_h_acceptors": 4,
                "ligand_logp": 3.7,
                "ligand_rot_bonds": 6,
                "basic_amine_count": 1,
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_h_donors": 0,
                "ligand_h_acceptors": 6,
                "ligand_logp": 4.0,
                "ligand_rot_bonds": 3,
                "basic_amine_count": 0,
            },
        ]
    )

    assert mod.adora2a_neutral_antagonist_support(df).tolist() == [True, False, False]
    assert mod.adora2a_basic_amine_intrusion_pressure(df).tolist() == [False, True, False]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def test_build_probe_writes_claim_locked_payload_on_tiny_fixture(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    labels = tmp_path / "labels.csv"
    split = tmp_path / "split.csv"
    score_fields = [
        "target",
        "ligand_id",
        "mean_min_distance_A",
        "ligand_h_donors",
        "ligand_h_acceptors",
        "ligand_logp",
        "ligand_rot_bonds",
        "basic_amine_count",
        "feature_a",
        "feature_b",
        "feature_c",
        "feature_d",
        "feature_e",
    ]
    label_fields = ["target", "ligand_id", "is_binder", "reference_binding_kcal_mol"]
    split_fields = ["target", "ligand_id", "role"]
    targets = ["CHEMBL251_ADORA2A_HUMAN", "CHEMBL217_DRD2_HUMAN"]
    score_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    for t_index, target in enumerate(targets):
        for i in range(8):
            ligand = f"{target}_{i}"
            is_binder = 1 if i == 0 else 0
            score_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand,
                    "mean_min_distance_A": 4.0 + i * 0.1,
                    "ligand_h_donors": 0 if target == "CHEMBL251_ADORA2A_HUMAN" and i == 0 else 2,
                    "ligand_h_acceptors": 5 if target == "CHEMBL251_ADORA2A_HUMAN" and i == 0 else 3,
                    "ligand_logp": 4.0,
                    "ligand_rot_bonds": 4,
                    "basic_amine_count": 0 if target == "CHEMBL251_ADORA2A_HUMAN" and i == 0 else 1,
                    "feature_a": i + t_index,
                    "feature_b": i * 2 + t_index,
                    "feature_c": i * 3 + t_index,
                    "feature_d": i * 4 + t_index,
                    "feature_e": i * 5 + t_index,
                }
            )
            label_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand,
                    "is_binder": is_binder,
                    "reference_binding_kcal_mol": -10 if is_binder else -2,
                }
            )
            split_rows.append({"target": target, "ligand_id": ligand, "role": "far_ood_eval"})
    _write_csv(scores, score_rows, score_fields)
    _write_csv(labels, label_rows, label_fields)
    _write_csv(split, split_rows, split_fields)

    scores_out, payload = mod.build_probe(
        scores_csv=scores,
        labels_csv=labels,
        split_csv=split,
        min_finite_ratio=0.5,
        bootstrap_n=0,
    )

    assert payload["packet_type"] == mod.PACKET_TYPE
    assert payload["claim_promotion_allowed"] is False
    assert payload["target_specific_rule_discovered_from_current_failure_slice"] is True
    assert payload["support_counts"]["row_count"] == 1
    assert payload["pressure_counts"]["positive_count"] == 0
    assert mod.SCORE_COL in scores_out.columns

    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    mod.write_outputs(scores_out, payload, out_scores_csv=out_csv, out_json=out_json, out_md=out_md)
    assert json.loads(out_json.read_text(encoding="utf-8"))["packet_type"] == mod.PACKET_TYPE
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy ADORA2A Neutral Rescue Probe")
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["target"] == "CHEMBL251_ADORA2A_HUMAN"
