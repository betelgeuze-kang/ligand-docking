from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "target_name",
        "lane",
        "submission_format",
        "deadline_class",
        "release_date",
        "due_date",
        "sequence_path",
        "stoichiometry",
        "ligand_info_path",
        "prediction_file_path",
        "validation_json_path",
        "geometry_validation_json_path",
        "confidence_validation_json_path",
        "internal_scorecard_json_path",
        "format_check_status",
        "model_generation_status",
        "parameterization_status",
        "protein_local_minimization_status",
        "geometry_sanity_status",
        "confidence_calibration_status",
        "internal_scorecard_status",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _restricted_claim_lock_scorecard() -> dict:
    return {
        "summary": {
            "status": "blocked_accuracy_parity",
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
            "top_blockers": ["ligand_ranking:broad_gpcr_claim_not_allowed"],
        }
    }


def _framework_artifacts(root: Path, *, accuracy_status: str = "green", accuracy_payload: dict | None = None) -> None:
    _write_json(root / "runs/local_delivery_verdict_gate_current.json", {"summary": {"delivery_ready": True}})
    _write_json(root / "runs/local_engine_commercialization_queue_current.json", {"summary": {"queue_clear": True, "blocked_count": 0}})
    _write_json(
        root / "runs/accuracy_parity_scorecard_current.json",
        accuracy_payload or {"summary": {"status": accuracy_status}},
    )


def _run_builder(root: Path, intake_csv: Path) -> dict:
    out_json = root / "runs/scorecard_batch.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_internal_scorecard_batch.py"),
            "--intake-csv",
            str(intake_csv),
            "--out-dir",
            str(root / "runs/scorecards"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(root / "runs/scorecard_batch.csv"),
            "--out-md",
            str(root / "runs/scorecard_batch.md"),
            "--out-intake-csv",
            str(root / "runs/intake_scored.csv"),
            "--local-delivery-verdict-json",
            str(root / "runs/local_delivery_verdict_gate_current.json"),
            "--local-engine-queue-json",
            str(root / "runs/local_engine_commercialization_queue_current.json"),
            "--accuracy-scorecard-json",
            str(root / "runs/accuracy_parity_scorecard_current.json"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_casp17_internal_scorecard_passes_complete_non_ligand_row(tmp_path: Path) -> None:
    _framework_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/T6000TS.pdb").write_text("PFRMAT TS\nTARGET T6000\n", encoding="utf-8")
    (tmp_path / "inputs/T6000.fasta").write_text(">T6000\nACDE\n", encoding="utf-8")
    for name, status_key in [
        ("format.json", "format_check_status"),
        ("geometry.json", "geometry_sanity_status"),
        ("confidence.json", "confidence_calibration_status"),
    ]:
        _write_json(tmp_path / "runs" / name, {"summary": {"target_id": "T6000", status_key: "pass"}, "blockers": []})
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T6000",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(tmp_path / "inputs/T6000.fasta"),
                "prediction_file_path": str(tmp_path / "outputs/T6000TS.pdb"),
                "validation_json_path": str(tmp_path / "runs/format.json"),
                "geometry_validation_json_path": str(tmp_path / "runs/geometry.json"),
                "confidence_validation_json_path": str(tmp_path / "runs/confidence.json"),
                "format_check_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path, intake)

    assert payload["summary"]["internal_scorecard_pass_count"] == 1
    row = payload["rows"][0]
    assert row["model_generation_status"] == "pass"
    assert row["internal_scorecard_status"] == "pass"
    with (tmp_path / "runs/intake_scored.csv").open("r", encoding="utf-8", newline="") as handle:
        scored = list(csv.DictReader(handle))[0]
    assert scored["internal_scorecard_status"] == "pass"
    assert scored["internal_scorecard_json_path"].endswith("T6000_internal_scorecard.json")


def test_casp17_internal_scorecard_accepts_accuracy_claim_scope_lock_only(tmp_path: Path) -> None:
    _framework_artifacts(tmp_path, accuracy_payload=_restricted_claim_lock_scorecard())
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/T6000TS.pdb").write_text("PFRMAT TS\nTARGET T6000\n", encoding="utf-8")
    (tmp_path / "inputs/T6000.fasta").write_text(">T6000\nACDE\n", encoding="utf-8")
    for name, status_key in [
        ("format.json", "format_check_status"),
        ("geometry.json", "geometry_sanity_status"),
        ("confidence.json", "confidence_calibration_status"),
    ]:
        _write_json(tmp_path / "runs" / name, {"summary": {"target_id": "T6000", status_key: "pass"}, "blockers": []})
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T6000",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(tmp_path / "inputs/T6000.fasta"),
                "prediction_file_path": str(tmp_path / "outputs/T6000TS.pdb"),
                "validation_json_path": str(tmp_path / "runs/format.json"),
                "geometry_validation_json_path": str(tmp_path / "runs/geometry.json"),
                "confidence_validation_json_path": str(tmp_path / "runs/confidence.json"),
                "format_check_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path, intake)

    assert payload["summary"]["framework"]["framework_gate_pass"] is True
    assert payload["summary"]["framework"]["accuracy_parity_claim_scope_lock_only"] is True
    assert payload["rows"][0]["internal_scorecard_status"] == "pass"


def test_casp17_internal_scorecard_missing_prediction_stays_missing(tmp_path: Path) -> None:
    _framework_artifacts(tmp_path)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/T6001.fasta").write_text(">T6001\nACDE\n", encoding="utf-8")
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T6001",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(tmp_path / "inputs/T6001.fasta"),
            }
        ],
    )

    payload = _run_builder(tmp_path, intake)

    row = payload["rows"][0]
    assert row["model_generation_status"] == "missing"
    assert row["internal_scorecard_status"] == "missing"
    assert "missing_prediction_file_path" in row["top_blockers"]


def test_casp17_internal_scorecard_blocks_failed_validation_artifact(tmp_path: Path) -> None:
    _framework_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/T6002TS.pdb").write_text("PFRMAT TS\nTARGET T6002\n", encoding="utf-8")
    (tmp_path / "inputs/T6002.fasta").write_text(">T6002\nACDE\n", encoding="utf-8")
    _write_json(
        tmp_path / "runs/format.json",
        {
            "summary": {"target_id": "T6002", "format_check_status": "pass"},
            "blockers": [{"code": "model_1_missing", "severity": "hard", "reason": "bad model"}],
        },
    )
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T6002",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(tmp_path / "inputs/T6002.fasta"),
                "prediction_file_path": str(tmp_path / "outputs/T6002TS.pdb"),
                "validation_json_path": str(tmp_path / "runs/format.json"),
                "format_check_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path, intake)

    row = payload["rows"][0]
    assert row["internal_scorecard_status"] == "fail"
    assert "format_validation:model_1_missing" in row["top_blockers"]
