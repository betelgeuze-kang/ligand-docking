from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_remaining_evidence_queue as mod


_COLUMNS = [
    "entry_id",
    "family",
    "rank_pct",
    "selected_for_refine",
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
]


def _write_candidates(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in _COLUMNS})


def _write_stage3(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"topk": rows}) + "\n", encoding="utf-8")


def test_remaining_queue_records_missing_local_min_hbond_and_clash_baseline(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    protein = tmp_path / "protein.pdb"
    protein.write_text("ATOM\n", encoding="utf-8")
    missing_npz = tmp_path / "missing.npz"
    _write_candidates(
        candidates,
        [
            {
                "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                "family": "gpcr",
                "rank_pct": 0.001,
                "contact_persistence": 1,
                "clash_count": 0,
            }
        ],
    )
    _write_stage3(
        stage3,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "trajectory_npz": str(missing_npz),
                "protein_structure_source_path": str(protein),
                "ligand_smiles": "CCO",
                "frame_contact_presence_fraction": 1.0,
                "clash_count_mean_per_frame": 0.0,
                "clash_frame_fraction": 0.0,
            }
        ],
    )

    payload = mod.build_pocketmd_lite_remaining_evidence_queue(
        candidate_csv=candidates,
        stage3_json=stage3,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_remaining_evidence_queue"
    assert summary["selected_top_k_count"] == 1
    assert summary["remaining_candidate_count"] == 1
    assert summary["remaining_metric_count"] == 3
    assert summary["contact_clash_ready_count"] == 1
    assert summary["clash_relief_baseline_ready_count"] == 0
    assert summary["missing_metric_names"] == [
        "hbond_persistence",
        "initial_clash_count",
        "local_min_ligand_rmsd_a",
    ]
    assert summary["trajectory_npz_unavailable_count"] == 1
    assert summary["protein_structure_source_path_unavailable_count"] == 0
    row = payload["rows"][0]
    assert row["missing_metrics"] == "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count"
    assert row["trajectory_npz_available"] is False
    assert row["protein_structure_source_path_available"] is True
    assert row["ligand_smiles"] == "CCO"
    assert row["contact_persistence"] == "1"
    assert row["clash_count"] == "0"
    assert "trajectory_npz_unavailable" in row["blockers"]
    assert row["execution_enabled"] is False
    assert row["external_state_mutated"] is False


def test_remaining_queue_exposes_alternate_trajectory_restore_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    protein = tmp_path / "protein.pdb"
    protein.write_text("ATOM\n", encoding="utf-8")
    missing_npz = tmp_path / "missing_mount" / "stage2_trajectory_frames" / "shard_00000" / "T__rep0000__L.npz"
    alternate_root = tmp_path / "archive"
    alternate_npz = alternate_root / "old_run" / "stage2_trajectory_frames" / "shard_00000" / missing_npz.name
    alternate_npz.parent.mkdir(parents=True, exist_ok=True)
    alternate_npz.write_bytes(b"npz")
    _write_candidates(
        candidates,
        [
            {
                "entry_id": "T:L",
                "family": "gpcr",
                "rank_pct": 0.001,
                "contact_persistence": 1,
                "clash_count": 0,
            }
        ],
    )
    _write_stage3(
        stage3,
        [
            {
                "target": "T",
                "ligand_id": "L",
                "trajectory_npz": str(missing_npz),
                "protein_structure_source_path": str(protein),
                "ligand_smiles": "CCO",
                "frame_contact_presence_fraction": 1.0,
                "clash_count_mean_per_frame": 0.0,
                "clash_frame_fraction": 0.0,
            }
        ],
    )

    payload = mod.build_pocketmd_lite_remaining_evidence_queue(
        candidate_csv=candidates,
        stage3_json=stage3,
        trajectory_search_roots=[alternate_root],
    )

    summary = payload["summary"]
    assert summary["trajectory_npz_unavailable_count"] == 1
    assert summary["candidates_with_alternate_trajectory_count"] == 1
    assert summary["alternate_trajectory_npz_candidate_count"] == 1
    row = payload["rows"][0]
    assert row["trajectory_npz_available"] is False
    assert row["alternate_trajectory_npz_candidate_count"] == 1
    assert row["alternate_trajectory_npz_candidates"] == str(alternate_npz)
    assert "trajectory_npz_unavailable" in row["blockers"]


def test_remaining_queue_ready_when_selected_evidence_complete(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    npz = tmp_path / "traj.npz"
    npz.write_bytes(b"placeholder")
    protein = tmp_path / "protein.pdb"
    protein.write_text("ATOM\n", encoding="utf-8")
    _write_candidates(
        candidates,
        [
            {
                "entry_id": "T:L",
                "family": "gpcr",
                "rank_pct": 0.01,
                "local_min_ligand_rmsd_a": 1.1,
                "hbond_persistence": 0.7,
                "contact_persistence": 0.8,
                "initial_clash_count": 2,
                "clash_count": 0,
            }
        ],
    )
    _write_stage3(
        stage3,
        [
            {
                "target": "T",
                "ligand_id": "L",
                "trajectory_npz": str(npz),
                "protein_structure_source_path": str(protein),
                "ligand_smiles": "CCN",
            }
        ],
    )

    payload = mod.build_pocketmd_lite_remaining_evidence_queue(
        candidate_csv=candidates,
        stage3_json=stage3,
    )

    assert payload["summary"]["status"] == "pocketmd_lite_remaining_evidence_queue_ready"
    assert payload["summary"]["remaining_metric_count"] == 0
    assert payload["summary"]["clash_relief_baseline_ready_count"] == 1
    assert payload["rows"][0]["missing_metrics"] == ""
    assert payload["rows"][0]["recommended_next_local_action"] == "rerun_pocketmd_lite_report_and_review_band"


def test_remaining_queue_does_not_count_coarse_only_rows(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    _write_candidates(candidates, [{"entry_id": "T:L", "family": "gpcr", "rank_pct": 0.7}])
    _write_stage3(stage3, [{"target": "T", "ligand_id": "L"}])

    payload = mod.build_pocketmd_lite_remaining_evidence_queue(
        candidate_csv=candidates,
        stage3_json=stage3,
    )

    assert payload["summary"]["selected_top_k_count"] == 0
    assert payload["summary"]["remaining_metric_count"] == 0
    assert payload["rows"][0]["selected_for_refine"] is False


def test_main_writes_remaining_queue_artifacts(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_candidates(candidates, [{"entry_id": "T:L", "family": "gpcr", "rank_pct": 0.001}])
    _write_stage3(stage3, [{"target": "T", "ligand_id": "L", "ligand_smiles": "CC"}])

    rc = mod.main(
        [
            "--candidate-csv",
            str(candidates),
            "--stage3-json",
            str(stage3),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["remaining_metric_count"] == 5
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Remaining Evidence Queue")
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["entry_id"] == "T:L"
