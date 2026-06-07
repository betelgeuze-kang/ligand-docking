from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_production_supervised_dataset as mod


def _write_stage5(path: Path, target: str, rows: int) -> None:
    path.write_text(
        "target,ligand_id,is_binder,reference_binding_kcal_mol,binding_score_composite_v7,mean_min_distance_A,role\n"
        + "\n".join(
            f"{target},lig{i},{1 if i % 2 == 0 else 0},{-9.0 if i % 2 == 0 else -2.0},{-7.0 + i * 0.01},3.{i % 10},fit"
            for i in range(rows)
        )
        + "\n",
        encoding="utf-8",
    )


def _write_stage3_energy_proxy(path: Path, target: str, rows: int) -> None:
    path.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy\n"
        + "\n".join(f"{target},lig{i},{-8.5 + i * 0.02}" for i in range(rows))
        + "\n",
        encoding="utf-8",
    )


def test_supervised_dataset_materializes_broad_labeled_rows(tmp_path: Path) -> None:
    _write_stage5(tmp_path / "a_stage5_ranking_rows.csv", "ADRB2_GPCR_BLIND", 10)
    _write_stage5(tmp_path / "b_stage5_ranking_rows.csv", "TRPV1_ION_CHANNEL_BLIND", 10)
    _write_stage5(tmp_path / "c_stage5_ranking_rows.csv", "EGFR_KINASE", 10)

    payload = mod.build_residual_production_supervised_dataset(
        stage5_glob=str(tmp_path / "*stage5_ranking_rows.csv"),
        max_sources=10,
        max_rows_per_source=10,
        min_rows=30,
        min_targets=3,
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_production_supervised_dataset_ready"
    assert summary["rows_emitted"] == 30
    assert summary["binder_rows"] == 15
    assert summary["negative_rows"] == 15
    assert summary["targets"] == 3
    assert payload["rows"][0]["delta_score"] == -2.0
    assert "delta_energy" in summary["missing_production_output_labels"]


def test_supervised_dataset_joins_stage3_delta_energy_proxy_labels(tmp_path: Path) -> None:
    _write_stage5(tmp_path / "a_stage5_ranking_rows.csv", "ADRB2_GPCR_BLIND", 10)
    _write_stage3_energy_proxy(tmp_path / "a_stage3_scores.csv", "ADRB2_GPCR_BLIND", 10)

    payload = mod.build_residual_production_supervised_dataset(
        stage5_glob=str(tmp_path / "*stage5_ranking_rows.csv"),
        max_sources=10,
        max_rows_per_source=10,
        min_rows=10,
        min_targets=1,
    )

    summary = payload["summary"]
    assert summary["production_supervised_dataset_ready"] is True
    assert summary["delta_energy_label_rows"] == 10
    assert summary["delta_energy_label_source"] == "stage3_energy_proxy"
    assert "delta_energy" in summary["label_fields"]
    assert "delta_energy" not in summary["missing_production_output_labels"]
    assert payload["rows"][0]["delta_energy"] == -8.5
    assert payload["rows"][0]["delta_energy_label_source"] == "stage3_energy_proxy:binding_energy_mmpbsa_kcal_mol_proxy"
    assert payload["sources"][0]["stage3_energy_proxy_status"] == "used"


def test_supervised_dataset_cli_writes_outputs(tmp_path: Path) -> None:
    _write_stage5(tmp_path / "a_stage5_ranking_rows.csv", "ADRB2_GPCR_BLIND", 4)
    out_csv = tmp_path / "dataset.csv"
    out_json = tmp_path / "dataset.json"
    out_md = tmp_path / "dataset.md"

    mod.main(
        [
            "--stage5-glob",
            str(tmp_path / "*stage5_ranking_rows.csv"),
            "--min-rows",
            "4",
            "--min-targets",
            "1",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["rows_emitted"] == 4
    assert "delta_score" in out_csv.read_text(encoding="utf-8")
    assert "Residual Production Supervised Dataset" in out_md.read_text(encoding="utf-8")
