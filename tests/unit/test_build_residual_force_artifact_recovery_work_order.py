from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_force_artifact_recovery_work_order as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def _write_stage3(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["target", "ligand_id", "trajectory_npz"]
    path.write_text(
        ",".join(fields)
        + "\n"
        + "\n".join(",".join(str(row.get(field, "")) for field in fields) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def test_force_artifact_recovery_groups_missing_trajectory_prefixes(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": "/missing/runA/shard/a.npz"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "trajectory_npz": "/missing/runA/shard/b.npz"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig2", "trajectory_npz": "nan"},
        ],
    )

    payload = mod.build_residual_force_artifact_recovery_work_order(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 3},
            [
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)},
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "source_csv": str(stage5)},
                {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig2", "source_csv": str(stage5)},
            ],
        ),
        force_validation_packet=_packet({"delta_force_derivation_validation_ready": False}),
        prefix_depth=4,
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_artifact_recovery_work_order_ready"
    assert summary["force_artifact_recovery_required"] is True
    assert summary["raw_trajectory_path_rows"] == 3
    assert summary["valid_trajectory_path_rows"] == 2
    assert summary["missing_trajectory_npz_rows"] == 2
    assert summary["existing_trajectory_npz_rows"] == 0
    assert summary["top_missing_prefix"] == "/missing/runA/shard"
    assert payload["missing_prefixes"][0]["missing_trajectory_npz_rows"] == 2
    assert payload["rows"][0]["check_id"].startswith("restore_or_regenerate_missing_trajectory_npz_prefix")


def test_force_artifact_recovery_not_required_when_validation_ready(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    npz = tmp_path / "traj.npz"
    npz.write_bytes(b"placeholder")
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": str(npz)}],
    )

    payload = mod.build_residual_force_artifact_recovery_work_order(
        supervised_dataset_packet=_packet(
            {"rows_emitted": 1},
            [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)}],
        ),
        force_validation_packet=_packet({"delta_force_derivation_validation_ready": True}),
    )

    assert payload["summary"]["status"] == "residual_force_artifact_recovery_not_required"
    assert payload["summary"]["force_artifact_recovery_required"] is False
    assert payload["rows"][-1]["status"] == "pass"


def test_force_artifact_recovery_cli_writes_outputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(
        tmp_path / "a_stage3_scores.csv",
        [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "trajectory_npz": "/missing/runA/a.npz"}],
    )
    supervised = tmp_path / "supervised.json"
    validation = tmp_path / "validation.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    supervised.write_text(
        json.dumps(
            _packet(
                {"rows_emitted": 1},
                [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)}],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(json.dumps(_packet({"delta_force_derivation_validation_ready": False})) + "\n", encoding="utf-8")

    mod.main(
        [
            "--supervised-dataset-json",
            str(supervised),
            "--force-validation-json",
            str(validation),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["missing_trajectory_npz_rows"] == 1
    assert "restore_or_regenerate_missing_trajectory_npz_prefix" in out_csv.read_text(encoding="utf-8")
    assert "Residual Force Artifact Recovery Work Order" in out_md.read_text(encoding="utf-8")
