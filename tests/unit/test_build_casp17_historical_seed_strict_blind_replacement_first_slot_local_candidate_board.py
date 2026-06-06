from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    return str(path)


def _args(tmp_path: Path) -> list[str]:
    return [
        "--first-slot-kit-json",
        str(tmp_path / "first_slot.json"),
        "--native-candidates-json",
        str(tmp_path / "native.json"),
        "--top5-json",
        str(tmp_path / "top5.json"),
        "--no-leak-json",
        str(tmp_path / "no_leak.json"),
        "--chronology-json",
        str(tmp_path / "chronology.json"),
        "--lane-decision-json",
        str(tmp_path / "lane.json"),
        "--ablation-json",
        str(tmp_path / "ablation.json"),
        "--calibration-json",
        str(tmp_path / "calibration.json"),
        "--board-dir",
        str(tmp_path / "board"),
        "--out-json",
        str(tmp_path / "candidate_board.json"),
        "--out-csv",
        str(tmp_path / "candidate_board.csv"),
        "--out-md",
        str(tmp_path / "CANDIDATE_BOARD.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    pred_a = _pdb(tmp_path / "pred" / "A.pdb")
    native_a = _pdb(tmp_path / "native" / "A.pdb")
    pred_b = _pdb(tmp_path / "pred" / "B.pdb")
    native_b = _pdb(tmp_path / "native" / "B.pdb")
    _write_json(
        tmp_path / "first_slot.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_kit_status": "awaiting_first_slot_evidence_files",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
            }
        },
    )
    _write_json(
        tmp_path / "top5.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "scope": "monomer",
                    "selected_source_pdb": pred_a,
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "scope": "monomer",
                    "selected_source_pdb": pred_b,
                },
            ]
        },
    )
    _write_json(
        tmp_path / "native.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "scope": "monomer",
                    "candidate_pdb": native_a,
                    "native_authority_ref": "rcsb:1AAA",
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "scope": "monomer",
                    "candidate_pdb": native_b,
                    "native_authority_ref": "rcsb:1BBB",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "no_leak.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "dossier_status": "operator_provenance_review_required",
                    "operator_required_open_count": 10,
                    "dossier_md": "casp17/no_leak/A.md",
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "dossier_status": "ready_for_no_leak_clearance",
                    "operator_required_open_count": 0,
                    "dossier_md": "casp17/no_leak/B.md",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "chronology.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "native_authority_status": "authority_pass",
                    "native_authority_date": "2020-01-01",
                    "prediction_created_candidate": "2021-01-01",
                    "prediction_before_or_on_native_authority": False,
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "native_authority_status": "authority_pass",
                    "native_authority_date": "2020-01-01",
                    "prediction_created_candidate": "2019-01-01",
                    "prediction_before_or_on_native_authority": True,
                },
            ]
        },
    )
    _write_json(
        tmp_path / "lane.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "strict_blind_eligible": False,
                    "competitive_proof_allowed": False,
                    "operator_decision_required": True,
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "strict_blind_eligible": True,
                    "competitive_proof_allowed": True,
                    "operator_decision_required": False,
                },
            ]
        },
    )
    _write_json(
        tmp_path / "ablation.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "candidate_manifest_status": "operator_ablation_layer_evidence_missing",
                    "candidate_manifest_csv": "casp17/ablation/A.csv",
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "candidate_manifest_status": "ready_for_operator_reference",
                    "candidate_manifest_csv": "casp17/ablation/B.csv",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "calibration.json",
        {
            "rows": [
                {
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "ledger_status": "operator_calibration_review_required",
                    "candidate_ledger_csv": "casp17/calibration/A.csv",
                },
                {
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "ledger_status": "ready_for_calibration_fill",
                    "candidate_ledger_csv": "casp17/calibration/B.csv",
                },
            ]
        },
    )


def test_local_candidate_board_aggregates_fail_closed_candidates(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_local_candidate_board_status"] == (
        "first_slot_local_candidate_ready_for_operator_clearance"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_for_first_slot_count"] == 1
    assert summary["strict_blind_eligible_count"] == 1
    assert summary["material_present_count"] == 2
    assert summary["blocked_chronology_count"] == 1
    assert summary["blocked_no_leak_count"] == 1

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["HIST_A"]["candidate_status"] == "blocked_chronology_not_strict_blind"
    assert "prediction_not_before_native" in rows["HIST_A"]["blockers"]
    assert rows["HIST_B"]["candidate_status"] == "ready_for_first_slot_operator_clearance"
    assert rows["HIST_B"]["blockers"] == ""

    written_rows = _read_csv(tmp_path / "candidate_board.csv")
    assert len(written_rows) == 2
    assert (tmp_path / "board" / "01_hist_a" / "CANDIDATE.md").is_file()
    assert (tmp_path / "board" / "02_hist_b" / "candidate_summary.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "CANDIDATE_BOARD.md").read_text(encoding="utf-8")


def test_local_candidate_board_reports_review_only_when_no_candidate_is_strict_blind(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    lane = json.loads((tmp_path / "lane.json").read_text(encoding="utf-8"))
    for row in lane["rows"]:
        row["strict_blind_eligible"] = False
        row["competitive_proof_allowed"] = False
    _write_json(tmp_path / "lane.json", lane)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_local_candidate_board_status"] == (
        "first_slot_local_candidates_review_only"
    )


def test_local_candidate_board_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_local_candidate_board_status"] == (
        "blocked_missing_input"
    )
    assert "first_slot_kit_json_missing" in payload["summary"]["input_blockers"]
