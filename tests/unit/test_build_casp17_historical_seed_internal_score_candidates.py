from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_internal_score_candidates as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pdb(path: Path, b_factor: float = 55.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"ATOM  {index:5d}  CA  ALA A{index:4d}    {index:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00{b_factor:6.2f}           C\n"
        for index in range(1, 4)
    ]
    path.write_text("".join(lines), encoding="utf-8")
    return str(path)


def _candidate(target_id: str, path: str, rank: int, role: str) -> dict:
    return {
        "target_id": target_id,
        "benchmark_id": "hist_seed_test",
        "scope": "monomer",
        "candidate_rank": rank,
        "role": role,
        "path": path,
        "exists": True,
        "atom_count": 3,
        "coordinate_valid": True,
        "sha256_16": f"sha{rank}",
        "notes": role,
    }


def _args(tmp_path: Path, ledger_json: Path) -> list[str]:
    return [
        "--calibration-ledger-json",
        str(ledger_json),
        "--score-dir",
        str(tmp_path / "scores"),
        "--out-json",
        str(tmp_path / "scores.json"),
        "--out-csv",
        str(tmp_path / "scores.csv"),
        "--out-md",
        str(tmp_path / "SCORES.md"),
    ]


def test_internal_score_candidates_score_selected_and_top5_pool(tmp_path: Path) -> None:
    target_id = "HIST_TEST"
    candidates = [
        _candidate(
            target_id,
            _pdb(tmp_path / f"model_{rank}.pdb", b_factor=50.0 + rank),
            rank,
            "selected_prediction_copy" if rank == 1 else f"deterministic_perturbation_{rank}",
        )
        for rank in range(1, 6)
    ]
    ledger_json = tmp_path / "calibration.json"
    _write_json(ledger_json, {"candidate_rows_by_target": {target_id: candidates}})

    args = mod.parse_args(_args(tmp_path, ledger_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["internal_score_candidate_status"] == "internal_score_candidates_ready_for_review"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["candidate_count"] == 5
    assert payload["summary"]["scored_candidate_count"] == 5
    assert payload["summary"]["top5_scored_ready_count"] == 1
    assert payload["summary"]["selected_score_candidate_count"] == 1
    assert payload["summary"]["blocked_candidate_input_count"] == 0
    assert float(payload["rows"][0]["selected_score_candidate"]) > 0.0
    assert float(payload["rows"][0]["best_internal_score_candidate"]) > 0.0
    assert payload["rows"][0]["top5_scored_ready"] is True
    assert json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))["summary"]["claim_boundary"].startswith(
        "Local CASP17"
    )


def test_internal_score_candidates_block_missing_candidate_path(tmp_path: Path) -> None:
    target_id = "HIST_TEST"
    candidates = [
        _candidate(
            target_id,
            _pdb(tmp_path / f"model_{rank}.pdb"),
            rank,
            "selected_prediction_copy" if rank == 1 else f"deterministic_perturbation_{rank}",
        )
        for rank in range(1, 5)
    ]
    candidates.append(_candidate(target_id, str(tmp_path / "missing.pdb"), 5, "deterministic_perturbation_5"))
    ledger_json = tmp_path / "calibration.json"
    _write_json(ledger_json, {"candidate_rows_by_target": {target_id: candidates}})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, ledger_json)))

    assert payload["summary"]["internal_score_candidate_status"] == "blocked_internal_score_candidate_inputs"
    assert payload["summary"]["candidate_count"] == 5
    assert payload["summary"]["scored_candidate_count"] == 4
    assert payload["summary"]["blocked_candidate_input_count"] == 1
    assert payload["rows"][0]["score_status"] == "blocked_internal_score_candidate_inputs"
    assert "top5_scored_candidates_missing" in payload["rows"][0]["blockers"]
    assert "candidate_score_inputs_blocked" in payload["rows"][0]["blockers"]


def test_internal_score_candidates_block_missing_ledger_or_rows(tmp_path: Path) -> None:
    missing_payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing.json")))
    assert missing_payload["summary"]["internal_score_candidate_status"] == "blocked_missing_candidate_ledger"

    empty_json = tmp_path / "empty.json"
    _write_json(empty_json, {"candidate_rows_by_target": {}})
    empty_payload = mod.build_payload(mod.parse_args(_args(tmp_path, empty_json)))
    assert empty_payload["summary"]["internal_score_candidate_status"] == "blocked_missing_candidate_rows"
