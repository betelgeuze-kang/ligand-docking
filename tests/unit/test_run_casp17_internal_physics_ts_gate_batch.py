from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_intake(path: Path, sequence_path: Path) -> None:
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
        "prediction_file_path",
        "prediction_import_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "target_id": "T9300",
                "target_name": "fixture",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "release_date": "2026-05-20",
                "due_date": "2026-05-26",
                "sequence_path": str(sequence_path),
                "stoichiometry": "A1",
                "prediction_file_path": "",
                "prediction_import_status": "missing",
            }
        )


def _prepare_internal_raw(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    fasta = tmp_path / "T9300.fasta"
    job_dir = tmp_path / "job/T9300"
    raw_pdb = job_dir / "T9300_model_1.pdb"
    runtime_json = job_dir / "backend_runtime.json"
    metrics_json = job_dir / "metrics.json"
    launch_json = tmp_path / "launch.json"
    raw_gate_json = tmp_path / "raw_gate.json"
    fasta.write_text(">T9300\nACDEFGHIKLMNPQRST\n", encoding="utf-8")
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_internal_physics_baseline_predictor.py"),
            "--target-id",
            "T9300",
            "--fasta",
            str(fasta),
            "--out-dir",
            str(job_dir),
            "--raw-pdb",
            str(raw_pdb),
            "--runtime-json",
            str(runtime_json),
            "--metrics-json",
            str(metrics_json),
            "--quality-preset",
            "smoke",
            "--device",
            "cpu",
            "--allow-cpu",
            "--out-json",
            str(job_dir / "predictor.json"),
            "--out-csv",
            str(job_dir / "predictor.csv"),
            "--out-md",
            str(job_dir / "predictor.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    launch_row = {
        "target_id": "T9300",
        "target_kind": "protein_monomer_homomer",
        "sequence_path": str(fasta),
        "launch_status": "ready_to_launch",
        "recommended_backend": "internal_physics",
        "command": (
            "python3 tools/run_casp17_internal_physics_baseline_predictor.py "
            f"--target-id T9300 --fasta {fasta} --out-dir {job_dir} "
            f"--raw-pdb {raw_pdb} --runtime-json {runtime_json}"
        ),
    }
    _write_json(launch_json, {"rows": [launch_row]})
    _write_json(
        raw_gate_json,
        {
            "summary": {"raw_gate_status": "pass", "target_count": 1},
            "rows": [
                {
                    "target_id": "T9300",
                    "target_kind": "protein_monomer_homomer",
                    "raw_gate_status": "pass",
                    "raw_pdb": str(raw_pdb),
                    "runtime_json": str(runtime_json),
                }
            ],
        },
    )
    return fasta, raw_pdb, runtime_json, launch_json, raw_gate_json


def test_internal_physics_ts_gate_blocks_without_author_code(tmp_path: Path) -> None:
    _fasta, _raw_pdb, _runtime_json, launch_json, raw_gate_json = _prepare_internal_raw(tmp_path)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/run_casp17_internal_physics_ts_gate_batch.py"),
            "--raw-gate-json",
            str(raw_gate_json),
            "--launch-packet-json",
            str(launch_json),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--out-dir",
            str(tmp_path / "ts_gate"),
            "--out-json",
            str(tmp_path / "ts_gate.json"),
            "--out-csv",
            str(tmp_path / "ts_gate.csv"),
            "--out-md",
            str(tmp_path / "ts_gate.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "ts_gate.json").read_text(encoding="utf-8"))
    assert payload["summary"]["batch_status"] == "blocked"
    assert payload["rows"][0]["ts_conversion_status"] == "blocked"
    assert "missing_or_placeholder_author_code" in payload["rows"][0]["blockers"]
    assert not (tmp_path / "predictions/T9300TS.pdb").exists()


def test_internal_physics_ts_gate_executes_to_validation(tmp_path: Path) -> None:
    fasta, _raw_pdb, _runtime_json, launch_json, raw_gate_json = _prepare_internal_raw(tmp_path)
    intake_csv = tmp_path / "intake.csv"
    _write_intake(intake_csv, fasta)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/run_casp17_internal_physics_ts_gate_batch.py"),
            "--raw-gate-json",
            str(raw_gate_json),
            "--launch-packet-json",
            str(launch_json),
            "--intake-csv",
            str(intake_csv),
            "--prediction-dir",
            str(tmp_path / "predictions"),
            "--execute",
            "--author-code",
            "1234-5678-ABCD",
            "--stop-after",
            "validation",
            "--out-dir",
            str(tmp_path / "ts_gate"),
            "--import-json",
            str(tmp_path / "import.json"),
            "--import-csv",
            str(tmp_path / "import.csv"),
            "--import-md",
            str(tmp_path / "import.md"),
            "--imported-intake-csv",
            str(tmp_path / "imported.csv"),
            "--validation-dir",
            str(tmp_path / "validations"),
            "--validation-json",
            str(tmp_path / "validation.json"),
            "--validation-csv",
            str(tmp_path / "validation.csv"),
            "--validation-md",
            str(tmp_path / "validation.md"),
            "--validated-intake-csv",
            str(tmp_path / "validated.csv"),
            "--out-json",
            str(tmp_path / "ts_gate.json"),
            "--out-csv",
            str(tmp_path / "ts_gate.csv"),
            "--out-md",
            str(tmp_path / "ts_gate.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "ts_gate.json").read_text(encoding="utf-8"))
    assert payload["summary"]["batch_status"] == "completed_to_validation"
    assert payload["summary"]["converted_count"] == 1
    assert payload["rows"][0]["ts_conversion_status"] == "converted"
    assert (tmp_path / "predictions/T9300TS.pdb").exists()
    validation = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert validation["summary"]["format_pass_count"] == 1
    assert validation["summary"]["geometry_pass_count"] == 1
    assert validation["summary"]["confidence_pass_count"] == 1
