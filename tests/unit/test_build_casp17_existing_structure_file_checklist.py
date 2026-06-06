from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_builder(tmp_path: Path, *, intake_csv: Path, structure_dir: Path, provenance_csv: Path) -> dict:
    out_json = tmp_path / "runs/checklist.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_existing_structure_file_checklist.py"),
            "--intake-csv",
            str(intake_csv),
            "--work-queue-csv",
            str(tmp_path / "runs/work_queue.csv"),
            "--structure-dir",
            str(structure_dir),
            "--prediction-dir",
            str(tmp_path / "runs/predictions"),
            "--provenance-csv",
            str(provenance_csv),
            "--write-provenance-scaffold",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "runs/checklist.csv"),
            "--out-md",
            str(tmp_path / "runs/checklist.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_existing_structure_file_checklist_writes_fail_closed_provenance_scaffold(tmp_path: Path) -> None:
    intake = tmp_path / "runs/intake.csv"
    structures = tmp_path / "existing"
    provenance = tmp_path / "runs/provenance.csv"
    structures.mkdir()
    (structures / "T9200_model.pdb").write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C  \n", encoding="utf-8")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/T9200.fasta").write_text(">T9200\nA\n", encoding="utf-8")
    _write_csv(
        intake,
        [
            {
                "target_id": "T9200",
                "target_name": "target",
                "due_date": "2026-05-26",
                "sequence_path": str(tmp_path / "inputs/T9200.fasta"),
            }
        ],
        ["target_id", "target_name", "due_date", "sequence_path"],
    )
    _write_csv(
        tmp_path / "runs/work_queue.csv",
        [{"target_id": "T9200", "recommended_action": "first_internal_attempt", "work_priority": "260"}],
        ["target_id", "recommended_action", "work_priority"],
    )

    payload = _run_builder(tmp_path, intake_csv=intake, structure_dir=structures, provenance_csv=provenance)

    assert payload["summary"]["candidate_target_count"] == 1
    assert payload["summary"]["provenance_scaffold_status"] == "written"
    row = payload["rows"][0]
    assert row["candidate_count"] == 1
    assert row["provenance_cleared"] is False
    assert "cleared_provenance" in row["missing_items"]
    with provenance.open("r", encoding="utf-8", newline="") as handle:
        scaffold = list(csv.DictReader(handle))[0]
    assert scaffold["target_id"] == "T9200"
    assert scaffold["provenance_status"] == "needs_operator_clearance"
    assert scaffold["public_or_external_source_used"] == ""


def test_existing_structure_file_checklist_detects_cleared_provenance_and_canonical_gap(tmp_path: Path) -> None:
    intake = tmp_path / "runs/intake.csv"
    structures = tmp_path / "existing"
    provenance = tmp_path / "runs/provenance.csv"
    structures.mkdir()
    candidate = structures / "T9201TS.pdb"
    candidate.write_text("PFRMAT TS\nTARGET T9201\nATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C  \n", encoding="utf-8")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/T9201.fasta").write_text(">T9201\nA\n", encoding="utf-8")
    _write_csv(
        intake,
        [{"target_id": "T9201", "target_name": "target", "due_date": "2026-05-26", "sequence_path": str(tmp_path / "inputs/T9201.fasta")}],
        ["target_id", "target_name", "due_date", "sequence_path"],
    )
    _write_csv(tmp_path / "runs/work_queue.csv", [], ["target_id", "recommended_action", "work_priority"])
    _write_csv(
        provenance,
        [
            {
                "target_id": "T9201",
                "candidate_path": str(candidate),
                "provenance_status": "cleared",
                "source_class": "internal_target_specific_prediction",
                "target_specific": "true",
                "public_or_external_source_used": "false",
                "other_team_structure_used": "false",
                "post_release_structure_used": "false",
            }
        ],
        [
            "target_id",
            "candidate_path",
            "provenance_status",
            "source_class",
            "target_specific",
            "public_or_external_source_used",
            "other_team_structure_used",
            "post_release_structure_used",
        ],
    )

    payload = _run_builder(tmp_path, intake_csv=intake, structure_dir=structures, provenance_csv=provenance)

    row = payload["rows"][0]
    assert row["provenance_cleared"] is True
    assert row["ready_for_existing_structure_lane"] is True
    assert row["missing_items"] == "canonical_ts_prediction"
    with provenance.open("r", encoding="utf-8", newline="") as handle:
        existing = list(csv.DictReader(handle))[0]
    assert existing["provenance_status"] == "cleared"
