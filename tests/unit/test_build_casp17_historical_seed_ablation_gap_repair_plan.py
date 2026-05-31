from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_ablation_gap_repair_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest_row(target_id: str, role: str, exists: bool) -> dict[str, object]:
    return {
        "target_id": target_id,
        "benchmark_id": f"hist_seed_{target_id.lower()}",
        "scope": "monomer",
        "role": role,
        "path": f"data/{target_id}/{role}.pdb",
        "exists": exists,
        "atom_count": 10 if exists else 0,
        "coordinate_valid": exists,
        "sha256_16": "abc123" if exists else "",
        "notes": f"{role} notes",
    }


def _top5_row(target_id: str, rank: int, role: str) -> dict[str, object]:
    return {
        "target_id": target_id,
        "benchmark_id": f"hist_seed_{target_id.lower()}",
        "scope": "monomer",
        "role": role,
        "path": f"casp17/top5/{target_id}/model_{rank}.pdb",
        "exists": True,
        "atom_count": 10,
        "coordinate_valid": True,
        "sha256_16": f"sha{rank}",
        "candidate_rank": rank,
        "generation_method": "copy_selected" if rank == 1 else "deterministic_coordinate_perturbation",
        "source_path": f"data/{target_id}/selected.pdb",
    }


def _args(tmp_path: Path, ablation_json: Path, top5_json: Path) -> list[str]:
    return [
        "--ablation-candidates-json",
        str(ablation_json),
        "--top5-candidate-pools-json",
        str(top5_json),
        "--repair-dir",
        str(tmp_path / "repair"),
        "--out-json",
        str(tmp_path / "repair.json"),
        "--out-csv",
        str(tmp_path / "repair.csv"),
        "--out-md",
        str(tmp_path / "REPAIR.md"),
    ]


def test_ablation_gap_repair_plan_separates_real_layers_from_top5_decoys(tmp_path: Path) -> None:
    ablation_json = tmp_path / "ablation.json"
    top5_json = tmp_path / "top5.json"
    _write_json(
        ablation_json,
        {
            "rows": [
                {
                    "target_id": "HIST_READY",
                    "benchmark_id": "hist_seed_ready",
                    "scope": "monomer",
                    "selected_prediction_present": True,
                    "native_reference_present": True,
                    "baseline_candidate_count": 1,
                },
                {
                    "target_id": "HIST_GAP",
                    "benchmark_id": "hist_seed_gap",
                    "scope": "monomer",
                    "selected_prediction_present": True,
                    "native_reference_present": True,
                    "baseline_candidate_count": 0,
                },
            ],
            "manifest_rows_by_target": {
                "HIST_READY": [
                    _manifest_row("HIST_READY", "selected_prediction", True),
                    _manifest_row("HIST_READY", "native_reference", True),
                    _manifest_row("HIST_READY", "same_run_step_candidate", True),
                    _manifest_row("HIST_READY", "same_run_step_candidate", False),
                ],
                "HIST_GAP": [
                    _manifest_row("HIST_GAP", "selected_prediction", True),
                    _manifest_row("HIST_GAP", "native_reference", True),
                    _manifest_row("HIST_GAP", "same_run_step_candidate", False),
                ],
            },
        },
    )
    _write_json(
        top5_json,
        {
            "candidate_rows_by_target": {
                "HIST_READY": [
                    _top5_row("HIST_READY", 1, "selected_prediction_copy"),
                    _top5_row("HIST_READY", 2, "deterministic_perturbation_2"),
                ],
                "HIST_GAP": [
                    _top5_row("HIST_GAP", 1, "selected_prediction_copy"),
                    _top5_row("HIST_GAP", 2, "deterministic_perturbation_2"),
                ],
            }
        },
    )

    args = mod.parse_args(_args(tmp_path, ablation_json, top5_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["ablation_gap_repair_status"] == "ablation_gap_repair_required"
    assert payload["summary"]["seed_row_count"] == 2
    assert payload["summary"]["real_ablation_candidate_count"] == 1
    assert payload["summary"]["missing_real_ablation_candidate_count"] == 2
    assert payload["summary"]["top5_review_decoy_count"] == 2
    assert payload["summary"]["top5_selected_copy_count"] == 2
    assert payload["summary"]["ready_for_operator_review_count"] == 1
    assert payload["summary"]["gap_repair_required_count"] == 1
    assert payload["rows"][0]["repair_status"] == "ablation_reference_candidate_ready_for_operator_review"
    assert payload["rows"][1]["repair_status"] == "ablation_gap_repair_required"
    assert "top5_decoys_not_clearance_evidence" in payload["rows"][1]["blockers"]

    repair_csv = Path(payload["rows"][1]["repair_csv"])
    if not repair_csv.is_absolute():
        repair_csv = mod.ROOT / repair_csv
    with repair_csv.open("r", encoding="utf-8", newline="") as handle:
        repair_rows = list(csv.DictReader(handle))
    assert {row["candidate_kind"] for row in repair_rows} == {
        "missing_real_ablation_layer_candidate",
        "top5_selected_copy",
        "top5_review_decoy",
    }
    assert all(row["can_satisfy_ablation_manifest_ref"] == "False" for row in repair_rows)

    written = json.loads((tmp_path / "repair.json").read_text(encoding="utf-8"))
    assert written["summary"]["claim_boundary"].startswith("Local CASP17 historical seed ablation")


def test_ablation_gap_repair_plan_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_ablation.json", tmp_path / "missing_top5.json"))
    )

    assert payload["summary"]["ablation_gap_repair_status"] == "blocked_missing_input"
    assert "ablation_candidates_json_missing" in payload["summary"]["input_blockers"]
    assert "top5_candidate_pools_json_missing" in payload["summary"]["input_blockers"]
