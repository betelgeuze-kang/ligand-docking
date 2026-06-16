from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_energy_force_label_validation as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def _write_stage3(path: Path, values: list[float]) -> None:
    path.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy\n"
        + "\n".join(f"ADRB2_GPCR_BLIND,lig{i},{value}" for i, value in enumerate(values))
        + "\n",
        encoding="utf-8",
    )


def _supervised_rows(stage5: Path, refs: list[float]) -> list[dict[str, object]]:
    return [
        {
            "target": "ADRB2_GPCR_BLIND",
            "ligand_id": f"lig{i}",
            "family": "gpcr",
            "reference_binding_kcal_mol": value,
            "source_csv": str(stage5),
        }
        for i, value in enumerate(refs)
    ]


def test_energy_force_validation_blocks_uncalibrated_energy_proxy(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(tmp_path / "a_stage3_scores.csv", [-2.0, -8.0, -4.0, -7.0])
    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 4},
            _supervised_rows(stage5, [-8.0, -7.0, -6.0, -5.0]),
        ),
        min_pairs=4,
        min_targets=1,
        min_pearson=0.8,
        min_spearman=0.8,
        max_rmse=1.0,
        calibration_enabled=False,
    )

    summary = payload["summary"]
    assert summary["delta_energy_proxy_validation_ready"] is False
    assert "pearson_reference_vs_energy_proxy" in summary["blockers"]
    assert "delta_force_derivation_validation" in summary["blockers"]
    assert payload["rows"][2]["metric"] == "pearson_reference_vs_energy_proxy"
    assert payload["rows"][2]["status"] == "fail"


def test_energy_force_validation_accepts_calibrated_energy_proxy_but_keeps_force_blocked(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    refs = [-8.0, -7.0, -6.0, -5.0]
    _write_stage3(tmp_path / "a_stage3_scores.csv", refs)
    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 4}, _supervised_rows(stage5, refs)),
        min_pairs=4,
        min_targets=1,
        min_pearson=0.99,
        min_spearman=0.99,
        max_rmse=0.01,
        calibration_enabled=False,
    )

    assert payload["summary"]["delta_energy_proxy_validation_ready"] is True
    assert payload["summary"]["delta_force_derivation_validation_ready"] is False
    assert payload["summary"]["status"] == "blocked_residual_energy_force_label_validation"
    assert payload["summary"]["blockers"] == ["delta_force_derivation_validation"]


def test_energy_force_validation_uses_embedded_supervised_stage3_proxy_when_source_missing(tmp_path: Path) -> None:
    stage5 = tmp_path / "missing_stage5_ranking_rows.csv"
    refs = [-8.0, -7.0, -6.0, -5.0]
    supervised_rows = _supervised_rows(stage5, refs)
    for row, ref in zip(supervised_rows, refs):
        row["delta_energy"] = ref
        row["delta_energy_label_source"] = "stage3_energy_proxy:binding_energy_mmpbsa_kcal_mol_proxy"

    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 4}, supervised_rows),
        min_pairs=4,
        min_targets=1,
        min_pearson=0.99,
        min_spearman=0.99,
        max_rmse=0.01,
        calibration_enabled=False,
    )

    summary = payload["summary"]
    assert summary["delta_energy_proxy_validation_ready"] is True
    assert summary["status"] == "blocked_residual_energy_force_label_validation"
    assert summary["joined_energy_proxy_pair_count"] == 4
    assert summary["stage3_energy_proxy_pair_count"] == 0
    assert summary["embedded_delta_energy_proxy_pair_count"] == 4
    assert summary["energy_proxy_source_mode"] == "embedded_supervised_delta_energy_proxy"
    assert payload["detail_rows"][0]["energy_proxy_source_kind"] == "embedded_supervised_delta_energy_proxy"
    assert payload["sources"][-1]["status"] == "embedded_supervised_delta_energy_proxy"


def test_energy_force_validation_maps_embedded_raw_score_for_calibration(tmp_path: Path) -> None:
    stage5 = tmp_path / "missing_stage5_ranking_rows.csv"
    refs = [-9.0, -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0]
    supervised_rows = _supervised_rows(stage5, refs)
    for index, (row, ref) in enumerate(zip(supervised_rows, refs)):
        row["delta_energy"] = -0.2 * index
        row["delta_energy_label_source"] = "stage3_energy_proxy:binding_energy_mmpbsa_kcal_mol_proxy"
        row["raw_score"] = ref
        row["mean_min_distance_A"] = 3.0 + index * 0.1

    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 8}, supervised_rows),
        min_pairs=8,
        min_targets=1,
        min_pearson=0.9,
        min_spearman=0.9,
        max_rmse=0.2,
        calibration_enabled=True,
        calibration_holdout_percent=50,
    )

    summary = payload["summary"]
    assert summary["energy_proxy_metric_mode"] == "hash_holdout_ridge_calibrated"
    assert summary["delta_energy_proxy_validation_ready"] is True
    assert summary["embedded_delta_energy_proxy_pair_count"] == 8
    assert summary["blockers"] == ["delta_force_derivation_validation"]


def test_energy_force_validation_accepts_force_derivation_artifact(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    refs = [-8.0, -7.0, -6.0, -5.0]
    _write_stage3(tmp_path / "a_stage3_scores.csv", refs)
    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 4}, _supervised_rows(stage5, refs)),
        force_derivation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "valid_trajectory_path_rows": 4,
                "existing_trajectory_npz_rows": 4,
                "trajectory_remap_rows": 4,
                "trajectory_remap_candidate_rows": 4,
                "existing_remapped_trajectory_npz_rows": 4,
                "effective_min_existing_npz_rows": 4,
                "existing_npz_floor_capped_by_available_paths": True,
            }
        ),
        min_pairs=4,
        min_targets=1,
        min_pearson=0.0,
        min_spearman=0.0,
        max_rmse=2.0,
        calibration_enabled=True,
        calibration_holdout_percent=50,
    )

    assert payload["summary"]["delta_energy_proxy_validation_ready"] is True
    assert payload["summary"]["delta_force_derivation_validation_ready"] is True
    assert payload["summary"]["force_derivation_effective_min_existing_npz_rows"] == 4
    assert payload["summary"]["force_derivation_existing_npz_floor_capped_by_available_paths"] is True
    assert payload["summary"]["force_derivation_existing_remapped_trajectory_npz_rows"] == 4
    assert payload["summary"]["status"] == "residual_energy_force_label_validation_ready"
    assert payload["summary"]["blockers"] == []


def test_energy_force_validation_can_use_hash_holdout_ridge_calibration(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    refs = [-9.0, -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0]
    _write_stage3(tmp_path / "a_stage3_scores.csv", refs)
    payload = mod.build_residual_energy_force_label_validation(
        supervised_dataset_packet=_packet({"rows_emitted": 8}, _supervised_rows(stage5, refs)),
        min_pairs=8,
        min_targets=1,
        min_pearson=0.9,
        min_spearman=0.9,
        max_rmse=1.0,
        calibration_enabled=True,
        calibration_holdout_percent=50,
        calibration_ridge_lambda=1.0,
    )

    assert payload["summary"]["energy_proxy_metric_mode"] == "hash_holdout_ridge_calibrated"
    assert payload["summary"]["calibration_train_rows"] > 0
    assert payload["summary"]["calibration_eval_rows"] > 0
    assert payload["summary"]["delta_energy_proxy_validation_ready"] is True


def test_energy_force_validation_cli_writes_outputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    refs = [-8.0, -7.0, -6.0]
    _write_stage3(tmp_path / "a_stage3_scores.csv", refs)
    supervised = tmp_path / "supervised.json"
    supervised.write_text(json.dumps(_packet({"rows_emitted": 3}, _supervised_rows(stage5, refs))) + "\n", encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--supervised-dataset-json",
            str(supervised),
            "--min-pairs",
            "3",
            "--min-targets",
            "1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["joined_energy_proxy_pair_count"] == 3
    assert "delta_energy_proxy_kcal_mol" in out_csv.read_text(encoding="utf-8")
    assert "Residual Energy/Force Label Validation" in out_md.read_text(encoding="utf-8")
