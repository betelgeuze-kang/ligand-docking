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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _base_artifacts(root: Path) -> None:
    runs = root / "runs"
    _write_json(runs / "local_delivery_verdict_gate_current.json", {"summary": {"delivery_ready": True, "verdict": "delivery_ready"}})
    _write_json(runs / "local_engine_commercialization_queue_current.json", {"summary": {"queue_clear": True, "blocked_count": 0}})
    _write_json(runs / "accuracy_parity_scorecard_current.json", {"summary": {"status": "green", "pass_row_count": 5}})
    _write_json(
        runs / "wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json",
        {"summary": {"parameterization_ready_count": 7, "protein_local_minimization_ready_count": 7}},
    )
    _write_json(runs / "wetlab_selected_allatom_gate_burndown_packet_current.json", {"summary": {"hard_block_count": 0}})


def _run_builder(root: Path, extra_args: list[str] | None = None) -> dict:
    out_json = root / "runs/casp17_submission_gate_packet_current.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_submission_gate_packet.py"),
            "--root",
            str(root),
            *(extra_args or []),
        ],
        cwd=root,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_casp17_ligand_target_go_when_all_target_and_framework_gates_pass(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/T2000TS.pdb").write_text("PFRMAT TS\nTARGET T2000\n", encoding="utf-8")
    (tmp_path / "inputs/T2000.fasta").parent.mkdir(parents=True)
    (tmp_path / "inputs/T2000.fasta").write_text(">T2000\nACDEFGHIK\n", encoding="utf-8")
    (tmp_path / "inputs/T2000_ligands.smi").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "inputs/T2000_ligands.smi").write_text("CCO ligand1\n", encoding="utf-8")
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "T2000",
                "target_name": "example ligand target",
                "lane": "organic_ligand_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/T2000.fasta",
                "ligand_info_path": "inputs/T2000_ligands.smi",
                "prediction_file_path": "outputs/T2000TS.pdb",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "parameterization_status": "pass",
                "protein_local_minimization_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    assert payload["summary"]["framework_gate_pass"] is True
    assert payload["summary"]["registration_action"] == "user_register_regular_group_now_submission_gated"
    assert payload["summary"]["submission_go_count"] == 1
    assert payload["target_rows"][0]["submission_decision"] == "submission_go"


def test_casp17_target_no_go_when_server_deadline_or_ligand_checks_missing(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/T2001TS.pdb").write_text("PFRMAT TS\nTARGET T2001\n", encoding="utf-8")
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "T2001",
                "lane": "organic_ligand_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "server",
                "prediction_file_path": "outputs/T2001TS.pdb",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "parameterization_status": "missing",
                "protein_local_minimization_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    row = payload["target_rows"][0]
    assert row["submission_decision"] == "submission_no_go"
    assert "deadline_class_not_regular" in row["blockers"]
    assert "parameterization_status_not_pass" in row["blockers"]
    assert "missing_ligand_info_path" in row["blockers"]
    assert "missing_sequence_path" in row["blockers"]


def test_casp17_framework_blocker_blocks_otherwise_ready_target(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    _write_json(tmp_path / "runs/accuracy_parity_scorecard_current.json", {"summary": {"status": "blocked"}})
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/H2002TS.pdb").write_text("PFRMAT TS\nTARGET H2002\n", encoding="utf-8")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/H2002.fasta").write_text(">H2002\nACDEFGHIK\n", encoding="utf-8")
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "H2002",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/H2002.fasta",
                "prediction_file_path": "outputs/H2002TS.pdb",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    assert payload["summary"]["framework_gate_pass"] is False
    assert "accuracy_parity_scorecard_not_green" in payload["summary"]["framework_blockers"]
    assert payload["target_rows"][0]["submission_decision"] == "submission_no_go"
    assert "framework_gate_not_green" in payload["target_rows"][0]["blockers"]


def test_casp17_validation_json_hard_blocker_overrides_csv_pass(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/H2003TS.pdb").write_text("PFRMAT TS\nTARGET H2003\n", encoding="utf-8")
    (tmp_path / "inputs/H2003.fasta").write_text(">H2003\nACDEFGHIK\n", encoding="utf-8")
    _write_json(
        tmp_path / "runs/H2003_validation.json",
        {
            "summary": {"target_id": "H2003", "format_check_status": "fail"},
            "blockers": [{"code": "uniform_b_factor_confidence", "severity": "hard", "reason": "bad confidence"}],
        },
    )
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "H2003",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/H2003.fasta",
                "prediction_file_path": "outputs/H2003TS.pdb",
                "validation_json_path": "runs/H2003_validation.json",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    row = payload["target_rows"][0]
    assert row["submission_decision"] == "submission_no_go"
    assert "validation:uniform_b_factor_confidence" in row["blockers"]


def test_casp17_missing_validation_json_path_is_fail_closed(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/H2004TS.pdb").write_text("PFRMAT TS\nTARGET H2004\n", encoding="utf-8")
    (tmp_path / "inputs/H2004.fasta").write_text(">H2004\nACDEFGHIK\n", encoding="utf-8")
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "H2004",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/H2004.fasta",
                "prediction_file_path": "outputs/H2004TS.pdb",
                "validation_json_path": "runs/missing_validation.json",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    row = payload["target_rows"][0]
    assert row["submission_decision"] == "submission_no_go"
    assert "validation:validation_artifact_missing_or_invalid" in row["blockers"]


def test_casp17_internal_scorecard_json_hard_blocker_overrides_csv_pass(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/H2005TS.pdb").write_text("PFRMAT TS\nTARGET H2005\n", encoding="utf-8")
    (tmp_path / "inputs/H2005.fasta").write_text(">H2005\nACDEFGHIK\n", encoding="utf-8")
    _write_json(
        tmp_path / "runs/H2005_internal_scorecard.json",
        {
            "summary": {"target_id": "H2005", "internal_scorecard_status": "fail"},
            "blockers": [{"code": "accuracy_parity_scorecard_not_green", "severity": "hard", "reason": "not green"}],
        },
    )
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "H2005",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/H2005.fasta",
                "prediction_file_path": "outputs/H2005TS.pdb",
                "internal_scorecard_json_path": "runs/H2005_internal_scorecard.json",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path)

    row = payload["target_rows"][0]
    assert row["submission_decision"] == "submission_no_go"
    assert "validation:internal_scorecard:accuracy_parity_scorecard_not_green" in row["blockers"]


def test_casp17_shape_sanity_json_blocks_otherwise_ready_target(tmp_path: Path) -> None:
    _base_artifacts(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "inputs").mkdir()
    (tmp_path / "outputs/H2006TS.pdb").write_text("PFRMAT TS\nTARGET H2006\n", encoding="utf-8")
    (tmp_path / "inputs/H2006.fasta").write_text(">H2006\nACDEFGHIK\n", encoding="utf-8")
    _write_json(
        tmp_path / "runs/shape_sanity.json",
        {
            "summary": {
                "shape_sanity_status": "blocked",
                "pass_count": 0,
                "target_count": 1,
                "blocked_count": 1,
                "blocked_targets": "H2006",
            },
            "rows": [
                {
                    "target_id": "H2006",
                    "shape_sanity_status": "blocked",
                    "blockers": "ca_span_per_residue_above_threshold,shape_penalty_above_threshold",
                }
            ],
        },
    )
    _write_intake(
        tmp_path / "config/casp17_target_intake_template.csv",
        [
            {
                "target_id": "H2006",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": "inputs/H2006.fasta",
                "prediction_file_path": "outputs/H2006TS.pdb",
                "format_check_status": "pass",
                "model_generation_status": "pass",
                "geometry_sanity_status": "pass",
                "confidence_calibration_status": "pass",
                "internal_scorecard_status": "pass",
            }
        ],
    )

    payload = _run_builder(tmp_path, ["--shape-sanity-json", "runs/shape_sanity.json"])

    row = payload["target_rows"][0]
    assert payload["summary"]["shape_sanity_required"] is True
    assert payload["summary"]["shape_sanity_status"] == "blocked"
    assert payload["summary"]["submission_no_go_count"] == 1
    assert row["submission_decision"] == "submission_no_go"
    assert "shape_sanity:ca_span_per_residue_above_threshold" in row["blockers"]
    assert "shape_sanity:shape_penalty_above_threshold" in row["blockers"]
