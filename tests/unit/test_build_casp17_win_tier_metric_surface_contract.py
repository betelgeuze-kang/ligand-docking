from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_win_tier_metric_surface_contract as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_metric_surface_contract_covers_win_tier_metrics_and_blocks_without_evidence(tmp_path: Path) -> None:
    goal = tmp_path / "scorecard.json"
    queue = tmp_path / "queue.json"
    scaffold = tmp_path / "scaffold.json"
    sidechain = tmp_path / "sidechain.json"
    baseline = tmp_path / "baseline.json"

    _write_json(
        goal,
        {
            "summary": {
                "required_metric_surface": [
                    "GDT_TS",
                    "lDDT",
                    "TM-score",
                    "RMSD",
                    "GDT_HA",
                    "MolProbity",
                    "DockQ",
                    "ICS",
                    "IPS",
                    "LDDT-PLI",
                    "BiSyRMSD",
                ]
            }
        },
    )
    _write_json(
        queue,
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "required_target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "replacement_queue_status": "awaiting_strict_blind_replacement",
                    "blockers": "strict_blind_replacement_identity_required,core_files_required",
                },
                {
                    "queue_rank": 2,
                    "required_benchmark_id": "hist_REQUIRED_COMPLEX_001",
                    "required_target_id": "REQUIRED_COMPLEX_001",
                    "scope": "complex",
                    "replacement_queue_status": "awaiting_strict_blind_replacement",
                    "blockers": "core_files_required,no_leak_required",
                },
            ]
        },
    )
    _write_json(
        scaffold,
        {
            "rows": [
                {
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "prediction_pdb": "runs/predictions/monomer.pdb",
                    "native_pdb": "runs/natives/monomer.pdb",
                    "blockers": "prediction_pdb_not_found,native_pdb_not_found",
                },
                {
                    "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                    "target_id": "REQUIRED_COMPLEX_001",
                    "scope": "complex",
                    "prediction_pdb": "runs/predictions/complex.pdb",
                    "native_pdb": "runs/natives/complex.pdb",
                    "blockers": "prediction_pdb_not_found,native_pdb_not_found",
                },
            ]
        },
    )
    _write_json(
        sidechain,
        {
            "rows": [
                {
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "sidechain_native_status": "blocked",
                    "blockers": "prediction_pdb_missing,native_pdb_missing",
                },
                {
                    "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                    "sidechain_native_status": "blocked",
                    "blockers": "prediction_pdb_missing,native_pdb_missing",
                },
            ]
        },
    )
    _write_json(
        baseline,
        {
            "summary": {
                "baseline_candidate_count": 24,
                "competitive_proof_eligible_count": 0,
            }
        },
    )

    args = mod.parse_args(
        [
            "--goal-scorecard-json",
            str(goal),
            "--strict-blind-queue-json",
            str(queue),
            "--input-scaffold-json",
            str(scaffold),
            "--sidechain-native-benchmark-json",
            str(sidechain),
            "--official-archive-baseline-lane-json",
            str(baseline),
            "--out-dir",
            str(tmp_path / "metric_contract"),
            "--out-json",
            str(tmp_path / "contract.json"),
            "--out-csv",
            str(tmp_path / "contract.csv"),
            "--out-md",
            str(tmp_path / "CONTRACT.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["metric_surface_contract_status"] == (
        "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
    )
    assert summary["required_metric_count"] == 11
    assert summary["covered_required_metric_count"] == 11
    assert summary["strict_blind_slot_count"] == 2
    assert summary["blocked_slot_count"] == 2
    assert summary["metric_surface_row_count"] == 22
    assert summary["blocked_metric_row_count"] == 22
    assert summary["core_metric_row_count"] == 15
    assert summary["organic_ligand_slot_count"] == 0
    assert summary["official_archive_baseline_policy"] == "excluded_from_competitive_proof"
    assert summary["official_archive_competitive_proof_eligible_count"] == 0

    rows = payload["rows"]
    assert {row["metric_name"] for row in rows} >= {"GDT_TS", "DockQ", "LDDT-PLI", "BiSyRMSD"}
    assert rows[0]["metric_status"] == "awaiting_strict_blind_evidence_files"
    assert rows[0]["competitive_proof_eligible"] == "False"
    ligand_rows = [row for row in rows if row["metric_name"] == "LDDT-PLI"]
    assert ligand_rows[0]["profile_fit"] == "organic_ligand_category_slot_required"

    written_rows = _read_csv(tmp_path / "contract.csv")
    assert len(written_rows) == 22
    manifest = Path(payload["slot_rows"][0]["slot_manifest"])
    assert manifest.is_file()
    assert "official_archive_baseline_policy" in manifest.read_text(encoding="utf-8")
    assert (tmp_path / "metric_contract" / "slot_contracts.csv").is_file()


def test_metric_surface_contract_blocks_missing_goal_scorecard(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--goal-scorecard-json",
            str(tmp_path / "missing_scorecard.json"),
            "--strict-blind-queue-json",
            str(tmp_path / "missing_queue.json"),
            "--input-scaffold-json",
            str(tmp_path / "missing_scaffold.json"),
            "--sidechain-native-benchmark-json",
            str(tmp_path / "missing_sidechain.json"),
            "--official-archive-baseline-lane-json",
            str(tmp_path / "missing_baseline.json"),
            "--out-dir",
            str(tmp_path / "metric_contract"),
            "--out-json",
            str(tmp_path / "contract.json"),
            "--out-csv",
            str(tmp_path / "contract.csv"),
            "--out-md",
            str(tmp_path / "CONTRACT.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["metric_surface_contract_status"] == "blocked_goal_scorecard_missing"
    assert payload["summary"]["strict_blind_slot_count"] == 0
    assert payload["summary"]["required_metric_count"] == 11
