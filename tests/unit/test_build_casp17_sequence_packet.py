from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_intake(path: Path) -> None:
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
        "format_check_status",
        "model_generation_status",
        "parameterization_status",
        "protein_local_minimization_status",
        "geometry_sanity_status",
        "confidence_calibration_status",
        "internal_scorecard_status",
        "notes",
    ]
    rows = [
        {
            "target_id": "T1400",
            "target_name": "Kinase inhibitor complex",
            "lane": "organic_ligand_protein_complexes",
            "submission_format": "TS",
            "deadline_class": "regular",
        },
        {
            "target_id": "H1340",
            "target_name": "Parahenipavirus F protein /antibody complex",
            "lane": "difficult_protein_complexes",
            "submission_format": "TS",
            "deadline_class": "regular",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_casp17_sequence_packet_materializes_and_enriches_intake(tmp_path: Path) -> None:
    intake_csv = tmp_path / "runs/intake.csv"
    source_dir = tmp_path / "fixtures"
    source_dir.mkdir()
    _write_intake(intake_csv)
    (source_dir / "T1400.fasta").write_text(">T1400 chain A\nACDEFGHIKLMNPQRSTVWY\n", encoding="utf-8")
    (source_dir / "H1340.fasta").write_text(">H1340 chain A\nMSTNPKPQR\n>H1340 chain B\nQVQLVQSG\n", encoding="utf-8")

    out_json = tmp_path / "runs/sequence.json"
    out_csv = tmp_path / "runs/sequence.csv"
    out_md = tmp_path / "runs/sequence.md"
    out_dir = tmp_path / "runs/sequences"
    out_intake = tmp_path / "runs/intake_with_sequences.csv"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sequence_packet.py"),
            "--intake-csv",
            str(intake_csv),
            "--sequence-source-dir",
            str(source_dir),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-intake-csv",
            str(out_intake),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["sequence_ready_count"] == 2
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T1400"]["entry_count"] == 1
    assert rows["H1340"]["entry_count"] == 2
    assert (out_dir / "T1400.fasta").exists()

    with out_intake.open("r", encoding="utf-8", newline="") as handle:
        intake_rows = list(csv.DictReader(handle))
    assert all(row["sequence_path"] for row in intake_rows)
    assert "Sequence materialized" in intake_rows[0]["notes"]

    md_text = out_md.read_text(encoding="utf-8")
    assert "CASP17 Sequence Packet" in md_text
