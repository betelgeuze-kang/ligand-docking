from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_replacement_scorecard as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--source-repair-json",
        str(tmp_path / "source_repair.json"),
        "--out-dir",
        str(tmp_path / "scorecards"),
        "--out-json",
        str(tmp_path / "scorecard.json"),
        "--out-csv",
        str(tmp_path / "scorecard.csv"),
        "--out-md",
        str(tmp_path / "SCORECARD.md"),
    ]


def _pass_artifacts(root: Path, target_id: str) -> None:
    _write_text(root / "casp17" / "replacement_source_fasta" / f"{target_id}.fasta", f">{target_id}\nACDE\n")
    _write_json(
        root / "casp17" / "replacement_source_fasta" / f"{target_id}.provenance.json",
        {"target_id": target_id, "total_residue_count": 4},
    )
    _write_text(root / "runs" / "casp17_prediction_jobs_current" / target_id / f"{target_id}_model_1.pdb", "ATOM\n")
    _write_json(
        root / "runs" / "casp17_prediction_jobs_current" / target_id / f"{target_id}_predictor.json",
        {"summary": {"target_id": target_id, "predictor_status": "pass", "chain_count": 1, "residue_count": 4}},
    )
    _write_json(
        root / "runs" / "casp17_internal_physics_raw_validations_current" / f"{target_id}_backend_contract.json",
        {"summary": {"target_id": target_id, "contract_status": "pass", "pdb_ca_chain_count": 1, "residue_count": 4}},
    )
    _write_json(
        root / "runs" / "casp17_internal_physics_raw_validations_current" / f"{target_id}_raw_geometry_sanity.json",
        {"summary": {"target_id": target_id, "geometry_sanity_status": "pass"}},
    )
    _write_json(
        root / "runs" / "casp17_internal_physics_raw_validations_current" / f"{target_id}_raw_confidence_calibration.json",
        {"summary": {"target_id": target_id, "confidence_calibration_status": "pass", "sequence_residue_count": 4}},
    )


def test_replacement_scorecard_writes_only_source_complete_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _pass_artifacts(tmp_path, "H2001")
    _pass_artifacts(tmp_path, "H2002")
    _write_json(
        tmp_path / "source_repair.json",
        {
            "rows": [
                {
                    "candidate_target_id": "H2001",
                    "candidate_target_name": "Ready candidate",
                    "source_repair_status": "ready_for_validation_scorecard",
                    "replace_target_ids": "H1001;H1002",
                    "fasta_path": "casp17/replacement_source_fasta/H2001.fasta",
                    "prediction_pdb": "runs/casp17_prediction_jobs_current/H2001/H2001_model_1.pdb",
                    "raw_validation_json": "runs/casp17_internal_physics_raw_validations_current/H2001_raw_confidence_calibration.json",
                },
                {
                    "candidate_target_id": "H2002",
                    "candidate_target_name": "Collision candidate",
                    "source_repair_status": "blocked_current_target_collision",
                    "replace_target_ids": "H1001",
                },
                {
                    "candidate_target_id": "H2003",
                    "candidate_target_name": "Missing candidate",
                    "source_repair_status": "ready_for_validation_scorecard",
                    "replace_target_ids": "H1001",
                },
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["replacement_scorecard_status"] == "replacement_scorecard_blocked"
    assert summary["candidate_count"] == 3
    assert summary["pass_count"] == 1
    assert summary["blocked_count"] == 2
    by_id = {row["candidate_target_id"]: row for row in payload["rows"]}
    assert by_id["H2001"]["replacement_scorecard_status"] == "replacement_source_scorecard_pass"
    assert by_id["H2001"]["output_scorecard_json"] == "scorecards/H2001_internal_scorecard.json"
    assert (tmp_path / "scorecards/H2001_internal_scorecard.json").is_file()
    assert by_id["H2002"]["replacement_scorecard_status"] == "replacement_source_scorecard_blocked"
    assert "blocked_current_target_collision" in by_id["H2002"]["blockers"]
    assert by_id["H2003"]["replacement_scorecard_status"] == "replacement_source_scorecard_blocked"
    assert "fasta_missing" in by_id["H2003"]["blockers"]
    assert not (tmp_path / "scorecards/H2002_internal_scorecard.json").exists()
    assert (tmp_path / "SCORECARD.md").is_file()
