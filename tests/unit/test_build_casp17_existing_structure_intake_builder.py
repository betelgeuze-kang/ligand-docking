from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, resname: str, resseq: int, x: float, b_factor: float) -> str:
    return (
        f"ATOM  {serial:5d} {'CA':^4} {resname:>3} A{resseq:4d}    "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


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
        "prediction_import_status",
        "prediction_candidate_path",
        "prediction_import_blockers",
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


def _write_provenance(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "candidate_path",
        "provenance_status",
        "source_class",
        "target_specific",
        "public_or_external_source_used",
        "other_team_structure_used",
        "post_release_structure_used",
        "operator",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _cleared_provenance_row(target_id: str, candidate_path: Path) -> dict[str, str]:
    return {
        "target_id": target_id,
        "candidate_path": str(candidate_path),
        "provenance_status": "cleared",
        "source_class": "internal_target_specific_prediction",
        "target_specific": "true",
        "public_or_external_source_used": "false",
        "other_team_structure_used": "false",
        "post_release_structure_used": "false",
        "operator": "unit-test",
    }


def _base_artifacts(root: Path) -> dict[str, Path]:
    paths = {
        "local_delivery_verdict_json": root / "runs/local_delivery_verdict_gate_current.json",
        "local_engine_queue_json": root / "runs/local_engine_commercialization_queue_current.json",
        "accuracy_scorecard_json": root / "runs/accuracy_parity_scorecard_current.json",
        "pde_local_min_json": root / "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json",
        "selected_allatom_json": root / "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
    }
    _write_json(paths["local_delivery_verdict_json"], {"summary": {"delivery_ready": True, "verdict": "delivery_ready"}})
    _write_json(paths["local_engine_queue_json"], {"summary": {"queue_clear": True, "blocked_count": 0}})
    _write_json(paths["accuracy_scorecard_json"], {"summary": {"status": "green", "pass_row_count": 5}})
    _write_json(
        paths["pde_local_min_json"],
        {"summary": {"parameterization_ready_count": 7, "protein_local_minimization_ready_count": 7}},
    )
    _write_json(paths["selected_allatom_json"], {"summary": {"hard_block_count": 0}})
    return paths


def _run_builder(
    tmp_path: Path,
    *,
    intake_csv: Path,
    structure_dir: Path,
    stop_after: str,
    author_code: str = "",
    provenance_csv: Path | None = None,
) -> dict:
    out_json = tmp_path / "runs/existing_builder.json"
    cmd = [
        "python3",
        str(ROOT / "tools/build_casp17_existing_structure_intake_builder.py"),
        "--intake-csv",
        str(intake_csv),
        "--structure-dir",
        str(structure_dir),
        "--prediction-dir",
        str(tmp_path / "runs/predictions"),
        "--provenance-csv",
        str(provenance_csv or tmp_path / "runs/missing_provenance.csv"),
        "--stop-after",
        stop_after,
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "runs/existing_builder.csv"),
        "--out-md",
        str(tmp_path / "runs/existing_builder.md"),
        "--out-intake-csv",
        str(tmp_path / "runs/intake_existing.csv"),
        "--import-json",
        str(tmp_path / "runs/import.json"),
        "--import-csv",
        str(tmp_path / "runs/import.csv"),
        "--import-md",
        str(tmp_path / "runs/import.md"),
        "--imported-intake-csv",
        str(tmp_path / "runs/intake_imported.csv"),
        "--validation-dir",
        str(tmp_path / "runs/validations"),
        "--validation-json",
        str(tmp_path / "runs/validation_batch.json"),
        "--validation-csv",
        str(tmp_path / "runs/validation_batch.csv"),
        "--validation-md",
        str(tmp_path / "runs/validation_batch.md"),
        "--validated-intake-csv",
        str(tmp_path / "runs/intake_validated.csv"),
        "--scorecard-dir",
        str(tmp_path / "runs/scorecards"),
        "--scorecard-json",
        str(tmp_path / "runs/scorecard_batch.json"),
        "--scorecard-csv",
        str(tmp_path / "runs/scorecard_batch.csv"),
        "--scorecard-md",
        str(tmp_path / "runs/scorecard_batch.md"),
        "--scored-intake-csv",
        str(tmp_path / "runs/intake_scored.csv"),
        "--submission-gate-json",
        str(tmp_path / "runs/submission_gate.json"),
        "--submission-gate-csv",
        str(tmp_path / "runs/submission_gate.csv"),
        "--submission-gate-md",
        str(tmp_path / "runs/submission_gate.md"),
    ]
    if author_code:
        cmd.extend(["--author-code", author_code])
    artifacts = _base_artifacts(tmp_path)
    cmd.extend(
        [
            "--local-delivery-verdict-json",
            str(artifacts["local_delivery_verdict_json"]),
            "--local-engine-queue-json",
            str(artifacts["local_engine_queue_json"]),
            "--accuracy-scorecard-json",
            str(artifacts["accuracy_scorecard_json"]),
            "--pde-local-min-json",
            str(artifacts["pde_local_min_json"]),
            "--selected-allatom-json",
            str(artifacts["selected_allatom_json"]),
        ]
    )
    subprocess.run(cmd, cwd=ROOT, check=True)
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_existing_structure_builder_attaches_ts_and_runs_submission_gate(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    structures = tmp_path / "existing"
    inputs.mkdir()
    structures.mkdir()
    (inputs / "T9100.fasta").write_text(">T9100\nACD\n", encoding="utf-8")
    candidate = structures / "T9100TS.pdb"
    candidate.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T9100",
                "AUTHOR TEST-AUTHOR",
                "METHOD existing TS smoke.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "ALA", 1, 0.0, 80.0),
                _atom(2, "CYS", 2, 3.8, 70.0),
                _atom(3, "ASP", 3, 7.6, 60.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    provenance_csv = tmp_path / "runs/provenance.csv"
    _write_provenance(provenance_csv, [_cleared_provenance_row("T9100", candidate)])
    _write_intake(
        intake,
        [
            {
                "target_id": "T9100",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T9100.fasta"),
            }
        ],
    )

    payload = _run_builder(
        tmp_path,
        intake_csv=intake,
        structure_dir=structures,
        stop_after="submission_gate",
        provenance_csv=provenance_csv,
    )

    assert payload["summary"]["attached_ts_count"] == 1
    assert payload["summary"]["provenance_cleared_count"] == 1
    assert payload["rows"][0]["attach_status"] == "attached_ts"
    assert payload["rows"][0]["provenance_status"] == "cleared"
    assert payload["rows"][0]["sequence_check_status"] == "pass"
    stages = {stage["stage"]: stage for stage in payload["pipeline_stages"]}
    assert stages["import"]["summary"]["imported_count"] == 1
    assert stages["validation"]["summary"]["format_pass_count"] == 1
    assert stages["validation"]["summary"]["geometry_pass_count"] == 1
    assert stages["validation"]["summary"]["confidence_pass_count"] == 1
    assert stages["scorecard"]["summary"]["internal_scorecard_pass_count"] == 1
    assert stages["submission_gate"]["summary"]["submission_go_count"] == 1


def test_existing_structure_builder_converts_raw_pdb_before_import(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    structures = tmp_path / "existing"
    inputs.mkdir()
    structures.mkdir()
    (inputs / "T9101.fasta").write_text(">T9101\nACD\n", encoding="utf-8")
    candidate = structures / "T9101_model.pdb"
    candidate.write_text(
        "\n".join(
            [
                _atom(1, "ALA", 1, 0.0, 80.0),
                _atom(2, "CYS", 2, 3.8, 70.0),
                _atom(3, "ASP", 3, 7.6, 60.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    provenance_csv = tmp_path / "runs/provenance.csv"
    _write_provenance(provenance_csv, [_cleared_provenance_row("T9101", candidate)])
    _write_intake(
        intake,
        [
            {
                "target_id": "T9101",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T9101.fasta"),
            }
        ],
    )

    payload = _run_builder(
        tmp_path,
        intake_csv=intake,
        structure_dir=structures,
        stop_after="import",
        author_code="1234-5678-ABCD",
        provenance_csv=provenance_csv,
    )

    assert payload["summary"]["converted_raw_count"] == 1
    assert payload["rows"][0]["attach_status"] == "converted_raw"
    assert payload["rows"][0]["conversion_status"] == "pass"
    canonical = tmp_path / "runs/predictions/T9101TS.pdb"
    assert canonical.read_text(encoding="utf-8").startswith("PFRMAT TS\nTARGET T9101\nAUTHOR 1234-5678-ABCD\n")
    stages = {stage["stage"]: stage for stage in payload["pipeline_stages"]}
    assert stages["import"]["summary"]["imported_count"] == 1


def test_existing_structure_builder_blocks_sequence_mismatch_before_attach(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    structures = tmp_path / "existing"
    inputs.mkdir()
    structures.mkdir()
    (inputs / "T9102.fasta").write_text(">T9102\nACD\n", encoding="utf-8")
    candidate = structures / "T9102_model.pdb"
    candidate.write_text(
        "\n".join(
            [
                _atom(1, "ALA", 1, 0.0, 80.0),
                _atom(2, "CYS", 2, 3.8, 70.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    provenance_csv = tmp_path / "runs/provenance.csv"
    _write_provenance(provenance_csv, [_cleared_provenance_row("T9102", candidate)])
    _write_intake(
        intake,
        [
            {
                "target_id": "T9102",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T9102.fasta"),
            }
        ],
    )

    payload = _run_builder(
        tmp_path,
        intake_csv=intake,
        structure_dir=structures,
        stop_after="attach",
        provenance_csv=provenance_csv,
    )

    row = payload["rows"][0]
    assert row["attach_status"] == "blocked"
    assert row["sequence_check_status"] == "blocked"
    assert "structure_sequence_mismatch" in row["blockers"]
    assert not (tmp_path / "runs/predictions/T9102TS.pdb").exists()
    with (tmp_path / "runs/intake_existing.csv").open("r", encoding="utf-8", newline="") as handle:
        enriched = list(csv.DictReader(handle))[0]
    assert enriched["prediction_file_path"] == ""
    assert "structure_sequence_mismatch" in enriched["prediction_import_blockers"]


def test_existing_structure_builder_blocks_missing_provenance_before_attach(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    structures = tmp_path / "existing"
    inputs.mkdir()
    structures.mkdir()
    (inputs / "T9103.fasta").write_text(">T9103\nACD\n", encoding="utf-8")
    (structures / "T9103_model.pdb").write_text(
        "\n".join(
            [
                _atom(1, "ALA", 1, 0.0, 80.0),
                _atom(2, "CYS", 2, 3.8, 70.0),
                _atom(3, "ASP", 3, 7.6, 60.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T9103",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T9103.fasta"),
            }
        ],
    )

    payload = _run_builder(tmp_path, intake_csv=intake, structure_dir=structures, stop_after="attach")

    row = payload["rows"][0]
    assert row["attach_status"] == "blocked"
    assert row["provenance_status"] == "blocked"
    assert "provenance_csv_missing" in row["blockers"]
    assert not (tmp_path / "runs/predictions/T9103TS.pdb").exists()


def test_existing_structure_builder_blocks_public_or_external_provenance(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    structures = tmp_path / "existing"
    inputs.mkdir()
    structures.mkdir()
    candidate = structures / "T9104_model.pdb"
    (inputs / "T9104.fasta").write_text(">T9104\nACD\n", encoding="utf-8")
    candidate.write_text(
        "\n".join(
            [
                _atom(1, "ALA", 1, 0.0, 80.0),
                _atom(2, "CYS", 2, 3.8, 70.0),
                _atom(3, "ASP", 3, 7.6, 60.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    provenance_csv = tmp_path / "runs/provenance.csv"
    row = _cleared_provenance_row("T9104", candidate)
    row["source_class"] = "public_pdb_template"
    row["public_or_external_source_used"] = "true"
    _write_provenance(provenance_csv, [row])
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T9104",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T9104.fasta"),
            }
        ],
    )

    payload = _run_builder(
        tmp_path,
        intake_csv=intake,
        structure_dir=structures,
        stop_after="attach",
        provenance_csv=provenance_csv,
    )

    row = payload["rows"][0]
    assert row["attach_status"] == "blocked"
    assert row["provenance_status"] == "blocked"
    assert "provenance_source_class_public_or_external" in row["blockers"]
    assert "public_or_external_source_used_not_false" in row["blockers"]
