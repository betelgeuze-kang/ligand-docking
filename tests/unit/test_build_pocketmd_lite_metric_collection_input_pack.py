from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_metric_collection_input_pack as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _queue_payload() -> dict[str, object]:
    return {
        "summary": {"status": "blocked_pocketmd_lite_remaining_evidence_queue"},
        "rows": [
            {
                "entry_id": "T:L",
                "target": "T",
                "ligand_id": "L",
                "missing_metrics": "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count",
                "trajectory_npz": "/missing/T__L.npz",
                "alternate_trajectory_npz_candidates": "/alt/T__L.npz",
                "alternate_trajectory_npz_candidate_count": 1,
                "protein_structure_source_path": "data/native/t.pdb",
                "protein_structure_source_path_available": True,
                "ligand_smiles": "CCO",
                "ligand_smiles_present": True,
            }
        ],
    }


def _recovery_payload() -> dict[str, object]:
    return {
        "summary": {"status": "blocked_pocketmd_lite_evidence_recovery_manifest"},
        "rows": [
            {
                "entry_id": "T:L",
                "trajectory_npz": "/missing/T__L.npz",
                "exact_npz_status": "missing",
                "exact_basename_restore_npz_paths": "/restore/T__L.npz",
                "exact_basename_restore_readable_count": 1,
                "exact_basename_restore_claim_grade_metric_field_count": 0,
            }
        ],
    }


def test_metric_collection_pack_prefers_exact_basename_restore_candidate(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    recovery = tmp_path / "recovery.json"
    _write_json(queue, _queue_payload())
    _write_json(recovery, _recovery_payload())

    payload = mod.build_pocketmd_lite_metric_collection_input_pack(
        queue_json=queue,
        recovery_json=recovery,
    )

    summary = payload["summary"]
    assert summary["status"] == "pocketmd_lite_metric_collection_input_pack_ready"
    assert summary["collection_input_ready_count"] == 1
    assert summary["selected_exact_basename_restore_count"] == 1
    row = payload["rows"][0]
    assert row["selected_trajectory_npz"] == "/restore/T__L.npz"
    assert row["selected_trajectory_source"] == "exact_basename_restore_candidate"
    assert row["collection_input_ready"] is True
    assert row["ligand_smiles"] == "CCO"
    assert row["claim_grade_metrics_already_present"] is False
    assert row["recommended_next_local_action"] == (
        "run_pocketmd_lite_local_min_hbond_clash_relief_collector_for_selected_input"
    )
    assert row["claim_promotion_allowed"] is False


def test_metric_collection_pack_blocks_missing_protein_input(tmp_path: Path) -> None:
    queue_payload = _queue_payload()
    queue_payload["rows"][0]["protein_structure_source_path_available"] = False
    queue = tmp_path / "queue.json"
    recovery = tmp_path / "recovery.json"
    _write_json(queue, queue_payload)
    _write_json(recovery, _recovery_payload())

    payload = mod.build_pocketmd_lite_metric_collection_input_pack(
        queue_json=queue,
        recovery_json=recovery,
    )

    assert payload["summary"]["status"] == "blocked_pocketmd_lite_metric_collection_input_pack"
    row = payload["rows"][0]
    assert row["collection_input_ready"] is False
    assert "protein_structure_source_path_unavailable" in row["blockers"]


def test_main_writes_metric_collection_pack_artifacts(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    recovery = tmp_path / "recovery.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(queue, _queue_payload())
    _write_json(recovery, _recovery_payload())

    rc = mod.main(
        [
            "--queue-json",
            str(queue),
            "--recovery-json",
            str(recovery),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["collection_input_pack_ready"] is True
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Metric Collection Input Pack")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["entry_id"] == "T:L"
