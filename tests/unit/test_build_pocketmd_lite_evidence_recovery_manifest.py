from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from tools.product import build_pocketmd_lite_evidence_recovery_manifest as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _trajectory_npz(path: Path, *, include_metric_fields: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "protein_ca": np.zeros((3, 3), dtype=np.float32),
        "ligand_frames": np.zeros((4, 2, 3), dtype=np.float32),
        "frame_indices": np.arange(4, dtype=np.int32),
    }
    if include_metric_fields:
        payload["local_min_ligand_rmsd_a"] = np.array(1.2, dtype=np.float32)
        payload["hbond_persistence"] = np.array(0.75, dtype=np.float32)
    np.savez(path, **payload)


def _queue_payload(*, exact_npz: Path, alternate_npz: Path | None = None) -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_pocketmd_lite_remaining_evidence_queue",
            "remaining_candidate_count": 1,
            "remaining_metric_count": 2,
        },
        "rows": [
            {
                "entry_id": "T:L",
                "missing_metrics": "local_min_ligand_rmsd_a;hbond_persistence",
                "trajectory_npz": str(exact_npz),
                "alternate_trajectory_npz_candidates": "" if alternate_npz is None else str(alternate_npz),
            }
        ],
    }


def test_manifest_marks_readable_alternate_trajectory_as_proxy_only(tmp_path: Path) -> None:
    exact_npz = tmp_path / "missing" / "T__rep0000__L.npz"
    alternate_npz = tmp_path / "archive" / "T__rep0000__L.npz"
    _trajectory_npz(alternate_npz)
    queue = tmp_path / "queue.json"
    _write_json(queue, _queue_payload(exact_npz=exact_npz, alternate_npz=alternate_npz))

    payload = mod.build_pocketmd_lite_evidence_recovery_manifest(
        remaining_queue_json=queue,
        restore_search_roots=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_evidence_recovery_manifest"
    assert summary["exact_trajectory_missing_count"] == 1
    assert summary["exact_claim_grade_metric_source_ready_count"] == 0
    assert summary["alternate_npz_readable_count"] == 1
    assert summary["alternate_npz_proxy_only_count"] == 1
    row = payload["rows"][0]
    assert row["exact_npz_status"] == "missing"
    assert row["first_alternate_npz_status"] == "proxy_only_trajectory_schema"
    assert row["first_alternate_npz_reason"] == (
        "trajectory_schema_readable_but_missing_claim_grade_local_min_hbond_fields"
    )
    assert row["recommended_next_local_action"] == (
        "restore_exact_current_trajectory_or_rerun_pocketmd_lite_local_min_hbond_collection"
    )
    assert row["execution_enabled"] is False


def test_manifest_finds_exact_basename_restore_candidate_as_proxy_only(tmp_path: Path) -> None:
    exact_npz = tmp_path / "missing" / "T__rep0000__L.npz"
    restore_npz = tmp_path / "trash" / "spill" / "T__rep0000__L.npz"
    _trajectory_npz(restore_npz)
    queue = tmp_path / "queue.json"
    _write_json(queue, _queue_payload(exact_npz=exact_npz))

    payload = mod.build_pocketmd_lite_evidence_recovery_manifest(
        remaining_queue_json=queue,
        restore_search_roots=[tmp_path / "trash"],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_evidence_recovery_manifest"
    assert summary["exact_basename_restore_candidate_count"] == 1
    assert summary["exact_basename_restore_readable_count"] == 1
    assert summary["exact_basename_restore_proxy_only_count"] == 1
    assert summary["exact_basename_restore_claim_grade_metric_field_count"] == 0
    row = payload["rows"][0]
    assert row["first_exact_basename_restore_npz_status"] == "proxy_only_trajectory_schema"
    assert row["first_exact_basename_restore_npz_reason"] == (
        "trajectory_schema_readable_but_missing_claim_grade_local_min_hbond_fields"
    )
    assert row["recommended_next_local_action"] == (
        "restore_exact_basename_trajectory_candidate_then_collect_local_min_hbond"
    )


def test_manifest_accepts_exact_npz_with_claim_grade_metric_fields(tmp_path: Path) -> None:
    exact_npz = tmp_path / "current" / "T__rep0000__L.npz"
    _trajectory_npz(exact_npz, include_metric_fields=True)
    queue = tmp_path / "queue.json"
    _write_json(queue, _queue_payload(exact_npz=exact_npz))

    payload = mod.build_pocketmd_lite_evidence_recovery_manifest(
        remaining_queue_json=queue,
        restore_search_roots=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "pocketmd_lite_evidence_recovery_manifest_ready"
    assert summary["exact_trajectory_available_count"] == 1
    assert summary["exact_claim_grade_metric_source_ready_count"] == 1
    row = payload["rows"][0]
    assert row["exact_npz_status"] == "claim_grade_metric_source_ready"
    assert row["exact_npz_claim_grade_metric_source_ready"] is True
    assert row["exact_local_min_ligand_rmsd_a"] == np.float32(1.2)
    assert row["exact_hbond_persistence"] == np.float32(0.75)
    assert row["recommended_next_local_action"] == (
        "extract_claim_grade_metrics_from_exact_trajectory_npz_then_rerun_pocketmd_lite_report"
    )


def test_main_writes_recovery_manifest_artifacts(tmp_path: Path) -> None:
    exact_npz = tmp_path / "missing" / "T__rep0000__L.npz"
    alternate_npz = tmp_path / "archive" / "T__rep0000__L.npz"
    _trajectory_npz(alternate_npz)
    queue = tmp_path / "queue.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(queue, _queue_payload(exact_npz=exact_npz, alternate_npz=alternate_npz))

    rc = mod.main(
        [
            "--remaining-queue-json",
            str(queue),
            "--restore-search-root",
            str(tmp_path / "trash"),
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
    assert payload["summary"]["status"] == "blocked_pocketmd_lite_evidence_recovery_manifest"
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Evidence Recovery Manifest")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["entry_id"] == "T:L"
    assert rows[0]["alternate_npz_proxy_only_count"] == "1"
