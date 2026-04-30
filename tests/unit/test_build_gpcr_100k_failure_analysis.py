from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_100k_failure_analysis as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "ligand_id",
                "is_binder",
                "reference_binding_kcal_mol",
                "binding_score_composite_v7",
                "mean_min_distance_A",
                "role",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_stage3_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target",
        "ligand_id",
        "binding_score_composite_v6",
        "binding_score_composite_v7",
        "ligand_h_donors",
        "ligand_h_acceptors",
        "ligand_rot_bonds",
        "ligand_logp",
        "ligand_mw",
        "ligand_affinity_hint",
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "contact_fraction",
        "stability_score",
        "mean_min_distance_A",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_100k_failure_analysis(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline.csv"
    scaleup = tmp_path / "runs" / "scaleup.csv"
    _write_rows(
        baseline,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-7.0", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
        ],
    )
    _write_rows(
        scaleup,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.5", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d2", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.4", "mean_min_distance_A": "4.3", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
        ],
    )
    out_json = tmp_path / "runs" / "analysis.json"
    out_csv = tmp_path / "runs" / "analysis.csv"
    out_md = tmp_path / "runs" / "analysis.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_100k_failure_analysis.py"),
            "--baseline-csv",
            str(baseline),
            "--scaleup-csv",
            str(scaleup),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["baseline_positive_ranks"] == [1, 2]
    assert payload["summary"]["scaleup_positive_ranks"] == [1, 4]
    assert payload["summary"]["scaleup_top20_binder_count"] == 2


def test_build_gpcr_100k_failure_analysis_with_stage3_score_diagnostics(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline.csv"
    scaleup = tmp_path / "runs" / "scaleup.csv"
    scaleup_stage3 = tmp_path / "runs" / "scaleup_stage3.csv"
    _write_rows(
        baseline,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-7.0", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
        ],
    )
    _write_rows(
        scaleup,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.5", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d2", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.4", "mean_min_distance_A": "4.3", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
        ],
    )
    _write_stage3_rows(
        scaleup_stage3,
        [
            {"target": "ADRB2", "ligand_id": "b1", "binding_score_composite_v6": "-10.0", "binding_score_composite_v7": "-9.0", "ligand_h_donors": "2", "ligand_h_acceptors": "3", "ligand_rot_bonds": "6", "ligand_logp": "3.0", "ligand_mw": "310", "ligand_affinity_hint": "0.6", "binding_energy_mmpbsa_kcal_mol_proxy": "-0.25", "contact_fraction": "0.005", "stability_score": "0.004", "mean_min_distance_A": "4.0"},
            {"target": "ADRB2", "ligand_id": "d1", "binding_score_composite_v6": "-7.0", "binding_score_composite_v7": "-8.5", "ligand_h_donors": "5", "ligand_h_acceptors": "6", "ligand_rot_bonds": "9", "ligand_logp": "0.5", "ligand_mw": "260", "ligand_affinity_hint": "0.5", "binding_energy_mmpbsa_kcal_mol_proxy": "-0.05", "contact_fraction": "0.002", "stability_score": "0.002", "mean_min_distance_A": "4.3"},
            {"target": "ADRB2", "ligand_id": "d2", "binding_score_composite_v6": "-6.5", "binding_score_composite_v7": "-8.4", "ligand_h_donors": "5", "ligand_h_acceptors": "5", "ligand_rot_bonds": "8", "ligand_logp": "0.6", "ligand_mw": "255", "ligand_affinity_hint": "0.5", "binding_energy_mmpbsa_kcal_mol_proxy": "-0.04", "contact_fraction": "0.002", "stability_score": "0.002", "mean_min_distance_A": "4.4"},
            {"target": "ADRB2", "ligand_id": "b2", "binding_score_composite_v6": "-9.5", "binding_score_composite_v7": "-8.0", "ligand_h_donors": "2", "ligand_h_acceptors": "3", "ligand_rot_bonds": "6", "ligand_logp": "3.2", "ligand_mw": "300", "ligand_affinity_hint": "0.55", "binding_energy_mmpbsa_kcal_mol_proxy": "-0.22", "contact_fraction": "0.004", "stability_score": "0.003", "mean_min_distance_A": "4.1"},
        ],
    )

    payload = mod.build_payload(
        mod._read_csv(baseline),
        mod._read_csv(scaleup),
        scaleup_stage3_rows=mod._read_csv(scaleup_stage3),
        topk_k=2,
        pr_auc_min=0.9,
        topk_hit_rate_min=1.0,
    )

    diagnostics = payload["score_diagnostics"]
    assert diagnostics["available"] is True
    assert diagnostics["best_existing_score_col"] == "binding_score_composite_v6"
    assert diagnostics["existing_score_recovery_status"] == "existing_score_column_passes_gate"
    assert diagnostics["best_existing_metrics"]["positive_ranks"] == [1, 2]
    assert "donor_prior_decoy_intrusion" in diagnostics["root_cause_tags"]


def test_missing_input_payload_is_actionable_without_fake_pass(tmp_path: Path) -> None:
    baseline = tmp_path / "missing_baseline.csv"
    scaleup = tmp_path / "missing_scaleup.csv"

    payload = mod.build_missing_input_payload(baseline, scaleup)

    assert payload["summary"]["status"] == "blocked_missing_csv_inputs"
    assert payload["summary"]["source_rows_available"] is False
    assert payload["summary"]["claim_safe"] is False
    assert payload["summary"]["missing_input_count"] == 2
    assert str(baseline) in payload["summary"]["missing_input_paths"]
    assert payload["baseline"]["row_count"] == 0
    assert payload["scaleup"]["row_count"] == 0
    assert "rerun or restore" in payload["summary"]["next_required_step"]


def test_missing_input_payload_preserves_previous_snapshot_summary(tmp_path: Path) -> None:
    previous_payload = {
        "summary": {
            "scaleup_positive_ranks": [1, 2, 15, 78, 107, 128],
            "scaleup_top20_binder_count": 3,
            "last_positive_rank_shift": 122,
        }
    }

    payload = mod.build_missing_input_payload(
        tmp_path / "missing_baseline.csv",
        tmp_path / "missing_scaleup.csv",
        previous_payload=previous_payload,
    )

    assert payload["summary"]["previous_snapshot_available"] is True
    assert payload["summary"]["previous_scaleup_positive_ranks"] == [1, 2, 15, 78, 107, 128]
    assert payload["summary"]["previous_scaleup_top20_binder_count"] == 3
    assert payload["summary"]["previous_last_positive_rank_shift"] == 122
