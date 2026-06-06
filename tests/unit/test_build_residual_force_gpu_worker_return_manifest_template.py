from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_residual_force_gpu_worker_return_manifest_template as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_return_manifest_template_prefills_identity_locked_rows(tmp_path: Path) -> None:
    queue_csv = tmp_path / "queue.csv"
    queue_csv.write_text(
        "\n".join(
            [
                "queue_id,expected_regenerated_trajectory_npz,target,ligand_id,replica_idx,simulation_seed,native_pdb_path",
                "q1,runs/out/q1.npz,kinase,lig1,0,11,inputs/a.pdb",
                "q2,runs/out/q2.npz,kinase,lig2,1,12,inputs/b.pdb",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_force_gpu_worker_return_manifest_template(
        regeneration_queue_packet=_packet(
            {
                "regeneration_queue_execution_ready": True,
                "queue_rows": 2,
                "regeneration_queue_csv": str(queue_csv),
            }
        ),
        template_csv_path=str(tmp_path / "template.csv"),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_gpu_worker_return_manifest_template_ready"
    assert summary["return_manifest_template_ready"] is True
    assert summary["template_row_count"] == 2
    assert summary["template_status_placeholder_count"] == 2
    assert summary["allowed_ok_status_values"] == [
        "ok",
        "ok_npz_bundle",
        "ok_regenerated_npz",
        "ok_full_regeneration",
    ]
    assert summary["template_verification_placeholder_count"] == 2
    assert summary["unique_queue_id_count"] == 2
    assert summary["unique_expected_npz_count"] == 2
    assert summary["unique_queue_row_fingerprint_count"] == 2
    assert summary["duplicate_queue_row_fingerprint_count"] == 0
    assert payload["rows"][0]["queue_id"] == "q1"
    assert len(payload["rows"][0]["queue_row_fingerprint"]) == 64
    assert payload["rows"][0]["source_queue_id"] == "q1"
    assert payload["rows"][0]["regeneration_queue_id"] == "q1"
    assert payload["rows"][0]["generated_npz"] == "runs/out/q1.npz"
    assert payload["rows"][0]["status"] == mod.STATUS_PLACEHOLDER


def test_return_manifest_template_blocks_without_identity_columns(tmp_path: Path) -> None:
    queue_csv = tmp_path / "queue.csv"
    queue_csv.write_text("ligand_id\nlig1\n", encoding="utf-8")

    payload = mod.build_residual_force_gpu_worker_return_manifest_template(
        regeneration_queue_packet=_packet(
            {
                "regeneration_queue_execution_ready": True,
                "queue_rows": 1,
                "regeneration_queue_csv": str(queue_csv),
            }
        )
    )

    summary = payload["summary"]
    assert summary["return_manifest_template_ready"] is False
    assert "queue_identity_columns" in summary["blockers"]
    assert "template_rows" in summary["blockers"]


def test_return_manifest_template_cli_writes_outputs(tmp_path: Path) -> None:
    queue_json = tmp_path / "queue.json"
    queue_csv = tmp_path / "queue.csv"
    out_json = tmp_path / "template.json"
    out_csv = tmp_path / "template.csv"
    out_md = tmp_path / "template.md"
    queue_csv.write_text("queue_id,expected_regenerated_trajectory_npz,target,ligand_id\nq1,a.npz,t,l\n", encoding="utf-8")
    queue_json.write_text(
        json.dumps(
            _packet(
                {
                    "regeneration_queue_execution_ready": True,
                    "queue_rows": 1,
                    "regeneration_queue_csv": str(queue_csv),
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )

    mod.main(
        [
            "--regeneration-queue-json",
            str(queue_json),
            "--out-template-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["return_manifest_template_ready"] is True
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == mod.STATUS_PLACEHOLDER
    assert len(rows[0]["queue_row_fingerprint"]) == 64
    assert rows[0]["expected_regenerated_trajectory_npz"] == "a.npz"
    md = out_md.read_text(encoding="utf-8")
    assert "Residual Force GPU Worker Return Manifest Template" in md
    assert "ok_npz_bundle" in md
