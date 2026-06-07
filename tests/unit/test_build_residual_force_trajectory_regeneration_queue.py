from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_residual_force_trajectory_regeneration_queue as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def _write_stage3(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [
        "queue_id",
        "target",
        "ligand_id",
        "ligand_smiles",
        "trajectory_npz",
        "protein_structure_source_explicit_native_path",
        "ligand_mw",
    ]
    path.write_text(
        ",".join(fields)
        + "\n"
        + "\n".join(",".join(str(row.get(field, "")) for field in fields) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def test_regeneration_queue_materializes_missing_npz_rows(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {
                "queue_id": "q1",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "ligand_smiles": "CCO",
                "trajectory_npz": "/missing/runA/shard/q1.npz",
                "protein_structure_source_explicit_native_path": "data/native/adrb2.pdb",
                "ligand_mw": "406.5",
            },
            {
                "queue_id": "q2",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "nan_row",
                "trajectory_npz": "nan",
            },
        ],
    )

    payload = mod.build_residual_force_trajectory_regeneration_queue(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 2},
            [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "carvedilol", "source_csv": str(stage5)}],
        ),
        recovery_work_order_packet={
            "summary": {"status": "residual_force_artifact_recovery_work_order_ready"},
            "missing_prefixes": [{"missing_prefix": "/missing/runA/shard"}],
        },
        regeneration_out_root="runs/regen/stage2_trajectory_frames",
        queue_csv_path="runs/queue.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_trajectory_regeneration_queue_ready"
    assert summary["queue_rows"] == 1
    assert summary["missing_trajectory_npz_rows"] == 1
    assert summary["native_pdb_path_present_rows"] == 1
    assert "--frame-output-format npz_bundle" in summary["engine_command"]
    assert payload["rows"][0]["original_queue_id"] == "q1"
    assert payload["rows"][0]["queue_id"].endswith("__q1")
    assert payload["rows"][0]["native_pdb_path"] == "data/native/adrb2.pdb"
    assert payload["rows"][0]["expected_regenerated_trajectory_npz"].endswith(f"shard_00000/{payload['rows'][0]['queue_id']}.npz")


def test_regeneration_queue_blocks_missing_native_path(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [{"queue_id": "q1", "target": "ADRB2_GPCR_BLIND", "ligand_id": "lig", "trajectory_npz": "/missing/runA/q1.npz"}],
    )

    payload = mod.build_residual_force_trajectory_regeneration_queue(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 1},
            [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig", "source_csv": str(stage5)}],
        ),
        recovery_work_order_packet={"summary": {}, "missing_prefixes": [{"missing_prefix": "/missing/runA"}]},
        prefix_depth=3,
    )

    assert payload["summary"]["status"] == "blocked_residual_force_trajectory_regeneration_queue"
    assert payload["summary"]["missing_native_pdb_path_rows"] == 1
    assert "native_pdb_path" in payload["summary"]["blockers"]


def test_regeneration_queue_cli_writes_outputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {
                "queue_id": "q1",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "lig",
                "ligand_smiles": "CC",
                "trajectory_npz": "/missing/runA/q1.npz",
                "protein_structure_source_explicit_native_path": "data/native/adrb2.pdb",
            }
        ],
    )
    supervised = tmp_path / "supervised.json"
    recovery = tmp_path / "recovery.json"
    out_queue = tmp_path / "queue.csv"
    out_json = tmp_path / "queue.json"
    out_md = tmp_path / "queue.md"
    supervised.write_text(
        json.dumps(_packet({"rows_emitted": 1}, [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig", "source_csv": str(stage5)}]))
        + "\n",
        encoding="utf-8",
    )
    recovery.write_text(json.dumps({"summary": {}, "missing_prefixes": [{"missing_prefix": "/missing/runA"}]}) + "\n", encoding="utf-8")

    mod.main(
        [
            "--supervised-dataset-json",
            str(supervised),
            "--recovery-work-order-json",
            str(recovery),
            "--prefix-depth",
            "3",
            "--out-queue-csv",
            str(out_queue),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    with out_queue.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["original_queue_id"] == "q1"
    assert rows[0]["queue_id"].endswith("__q1")
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["queue_rows"] == 1
    assert "Residual Force Trajectory Regeneration Queue" in out_md.read_text(encoding="utf-8")
