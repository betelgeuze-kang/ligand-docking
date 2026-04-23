from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_wetlab_rescue_anchor_artifacts as mod
from tools import build_wetlab_hard_target_rescue_lane as rescue_lane_mod


def test_build_wetlab_rescue_anchor_artifacts_materializes_focus_anchor_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")

    with (summary_dir / "throughput_run_stage1_queue.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target", "ligand_id", "pocket_x", "pocket_y", "pocket_z", "native_pdb_path"])
        writer.writeheader()
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "lig1",
                "pocket_x": "1.0",
                "pocket_y": "2.0",
                "pocket_z": "3.0",
                "native_pdb_path": "/tmp/native.pdb",
            }
        )
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["ligand_id", "binding_energy_proxy", "stability_score", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerow({"ligand_id": "lig1", "binding_energy_proxy": "-0.5", "stability_score": "0.7", "mean_min_distance_A": "3.2"})
        writer.writerow({"ligand_id": "lig2", "binding_energy_proxy": "-0.4", "stability_score": "0.6", "mean_min_distance_A": "3.5"})

    payload = mod.build_payload(
        {
            "summary": {"focus_target_id": "T. cruzi PDE", "focus_shard_id": "20_of_20"},
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "summary_json": str(summary_json),
                }
            ],
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["ready_for_rescue"] is True
    assert summary["focus_target_id"] == "T. cruzi PDE"
    assert summary["top_n_anchor_ligands"] == 2
    assert Path(summary["rescue_target_pocket_csv"]).exists()
    assert Path(summary["rescue_target_native_csv"]).exists()
    assert Path(summary["rescue_target_ligand_csv"]).exists()


def test_rescue_anchor_artifacts_falls_back_to_stage6_and_retry_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "cathepsin_k" / "04_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")

    with (summary_dir / "throughput_run_stage1_queue.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target", "ligand_id", "pocket_x", "pocket_y", "pocket_z"])
        writer.writeheader()
        writer.writerow({"target": "Cathepsin K", "ligand_id": "lig1", "pocket_x": "0", "pocket_y": "0", "pocket_z": "0"})
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ligand_id", "binding_energy_proxy", "stability_score", "mean_min_distance_A"])
        writer.writeheader()
        writer.writerow({"ligand_id": "lig1", "binding_energy_proxy": "-1.0", "stability_score": "0.8", "mean_min_distance_A": "4.4"})

    def fake_load_json(path: str) -> dict:
        if path == "stage6.json":
            return {"summary": {"status": "wetlab_primary_stage6_failure_surface_ready"}}
        if path == "retry.json":
            return {"summary": {"status": "wetlab_target_retry_policy_templates_ready"}}
        return {}

    monkeypatch.setattr(mod, "load_json", fake_load_json)
    monkeypatch.setattr(
        rescue_lane_mod,
        "build_payload",
        lambda stage6_payload, retry_payload: {
            "summary": {"focus_target_id": "Cathepsin K", "focus_shard_id": "04_of_20"},
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "target_slug": "cathepsin_k",
                    "shard_id": "04_of_20",
                    "summary_json": str(summary_json),
                }
            ],
        },
    )

    resolved = mod._resolve_rescue_lane_payload(
        {},
        rescue_lane_json="rescue.json",
        stage6_failure_surface_json="stage6.json",
        retry_policy_templates_json="retry.json",
    )

    payload = mod.build_payload(resolved, top_n=1)
    assert payload["summary"]["focus_target_id"] == "Cathepsin K"
    assert payload["summary"]["ready_for_rescue"] is True


def test_tcruzi_pde_rescue_anchor_uses_stage3_centroid_when_queue_pocket_is_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")

    with (summary_dir / "throughput_run_stage1_queue.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "ligand_id",
                "pocket_x",
                "pocket_y",
                "pocket_z",
                "ligand_bead0_x",
                "ligand_bead0_y",
                "ligand_bead0_z",
                "ligand_bead1_x",
                "ligand_bead1_y",
                "ligand_bead1_z",
                "native_pdb_path",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "lig1",
                "pocket_x": "0.0",
                "pocket_y": "0.0",
                "pocket_z": "0.0",
                "ligand_bead0_x": "1.0",
                "ligand_bead0_y": "2.0",
                "ligand_bead0_z": "3.0",
                "ligand_bead1_x": "3.0",
                "ligand_bead1_y": "4.0",
                "ligand_bead1_z": "5.0",
                "native_pdb_path": "nan",
            }
        )
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "lig2",
                "pocket_x": "0.0",
                "pocket_y": "0.0",
                "pocket_z": "0.0",
                "ligand_bead0_x": "2.0",
                "ligand_bead0_y": "3.0",
                "ligand_bead0_z": "4.0",
                "ligand_bead1_x": "4.0",
                "ligand_bead1_y": "5.0",
                "ligand_bead1_z": "6.0",
                "native_pdb_path": "nan",
            }
        )
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["ligand_id", "binding_energy_proxy", "stability_score", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerow({"ligand_id": "lig1", "binding_energy_proxy": "-0.6", "stability_score": "0.8", "mean_min_distance_A": "5.1"})
        writer.writerow({"ligand_id": "lig2", "binding_energy_proxy": "-0.5", "stability_score": "0.7", "mean_min_distance_A": "5.2"})

    payload = mod.build_payload(
        {
            "summary": {"focus_target_id": "T. cruzi PDE", "focus_shard_id": "20_of_20"},
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "summary_json": str(summary_json),
                }
            ],
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["attach_rescue_target_pocket_csv"] is True
    assert summary["rescue_pocket_anchor_quality"] == "stage3_top_ligand_centroid_proxy"
    assert summary["rescue_native_anchor_quality"] == "stub_with_target_specific_centroid_proxy"
    with Path(summary["rescue_target_pocket_csv"]).open("r", encoding="utf-8", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["source"] == "stage3_top_ligand_centroid_proxy"
    assert float(row["pocket_x"]) == 2.5
    assert float(row["pocket_y"]) == 3.5
    assert float(row["pocket_z"]) == 4.5
