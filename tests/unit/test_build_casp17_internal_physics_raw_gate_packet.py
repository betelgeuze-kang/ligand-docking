from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_internal_predictor(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    fasta = tmp_path / "T9200.fasta"
    job_dir = tmp_path / "job/T9200"
    raw_pdb = job_dir / "T9200_model_1.pdb"
    runtime_json = job_dir / "backend_runtime.json"
    metrics_json = job_dir / "metrics.json"
    fasta.write_text(">T9200\nACDEFGHIKLMN\n", encoding="utf-8")
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_internal_physics_baseline_predictor.py"),
            "--target-id",
            "T9200",
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
    return fasta, job_dir, raw_pdb, runtime_json


def test_casp17_internal_physics_raw_gate_passes_smoke_artifact(tmp_path: Path) -> None:
    fasta, job_dir, raw_pdb, runtime_json = _run_internal_predictor(tmp_path)
    launch = tmp_path / "launch.json"
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T9200",
                    "target_kind": "protein_monomer_homomer",
                    "sequence_path": str(fasta),
                    "launch_status": "ready_to_launch",
                    "recommended_backend": "internal_physics",
                    "command": (
                        "python3 tools/run_casp17_internal_physics_baseline_predictor.py "
                        f"--target-id T9200 --fasta {fasta} --out-dir {job_dir} "
                        f"--raw-pdb {raw_pdb} --runtime-json {runtime_json}"
                    ),
                }
            ]
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_internal_physics_raw_gate_packet.py"),
            "--launch-packet-json",
            str(launch),
            "--no-require-gpu",
            "--out-dir",
            str(tmp_path / "raw_validations"),
            "--out-json",
            str(tmp_path / "raw_gate.json"),
            "--out-csv",
            str(tmp_path / "raw_gate.csv"),
            "--out-md",
            str(tmp_path / "raw_gate.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "raw_gate.json").read_text(encoding="utf-8"))
    assert payload["summary"]["raw_gate_status"] == "pass"
    assert payload["summary"]["pass_count"] == 1
    row = payload["rows"][0]
    assert row["contract_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"


def test_casp17_internal_physics_raw_gate_blocks_missing_raw_pdb(tmp_path: Path) -> None:
    fasta = tmp_path / "T9201.fasta"
    runtime_json = tmp_path / "job/T9201/backend_runtime.json"
    raw_pdb = tmp_path / "job/T9201/T9201_model_1.pdb"
    launch = tmp_path / "launch.json"
    fasta.write_text(">T9201\nACDE\n", encoding="utf-8")
    runtime_json.parent.mkdir(parents=True, exist_ok=True)
    runtime_json.write_text(json.dumps({"summary": {"backend_kind": "internal_physics", "gpu_detected": True}}), encoding="utf-8")
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T9201",
                    "target_kind": "protein_monomer_homomer",
                    "sequence_path": str(fasta),
                    "launch_status": "ready_to_launch",
                    "recommended_backend": "internal_physics",
                    "command": (
                        "python3 tools/run_casp17_internal_physics_baseline_predictor.py "
                        f"--target-id T9201 --fasta {fasta} --raw-pdb {raw_pdb} --runtime-json {runtime_json}"
                    ),
                }
            ]
        },
    )

    run = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_internal_physics_raw_gate_packet.py"),
            "--launch-packet-json",
            str(launch),
            "--out-dir",
            str(tmp_path / "raw_validations"),
            "--out-json",
            str(tmp_path / "raw_gate.json"),
            "--out-csv",
            str(tmp_path / "raw_gate.csv"),
            "--out-md",
            str(tmp_path / "raw_gate.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    assert run.returncode == 2
    payload = json.loads((tmp_path / "raw_gate.json").read_text(encoding="utf-8"))
    assert payload["summary"]["raw_gate_status"] == "fail"
    assert "contract:raw_prediction_pdb_missing" in payload["rows"][0]["blockers"]
