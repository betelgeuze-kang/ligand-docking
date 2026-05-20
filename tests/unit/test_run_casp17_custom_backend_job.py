from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_dummy_backend(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "p=argparse.ArgumentParser()",
                "p.add_argument('--raw-pdb', required=True)",
                "args=p.parse_args()",
                "Path(args.raw_pdb).parent.mkdir(parents=True, exist_ok=True)",
                "Path(args.raw_pdb).write_text(",
                "    'ATOM      1 N   ALA A   1       1.000   1.000   1.000  1.00 80.00           N  \\n'",
                "    'ATOM      2 CA  ALA A   1       2.000   1.000   1.000  1.00 70.00           C  \\n'",
                "    'END\\n',",
                "    encoding='utf-8'",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_casp17_custom_backend_job_writes_runtime_and_raw_pdb(tmp_path: Path) -> None:
    backend_script = tmp_path / "dummy_backend.py"
    fasta = tmp_path / "T8200.fasta"
    probe = tmp_path / "gpu.json"
    out_json = tmp_path / "job.json"
    raw_pdb = tmp_path / "job/T8200_model_1.pdb"
    runtime_json = tmp_path / "job/backend_runtime.json"
    _write_dummy_backend(backend_script)
    fasta.write_text(">T8200\nA\n", encoding="utf-8")
    probe.write_text(json.dumps({"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}), encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_custom_backend_job.py"),
            "--target-id",
            "T8200",
            "--sequence-path",
            str(fasta),
            "--raw-pdb",
            str(raw_pdb),
            "--runtime-json",
            str(runtime_json),
            "--gpu-probe-json",
            str(probe),
            "--command-template",
            f"python3 {backend_script} --raw-pdb {{raw_pdb}}",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "job.csv"),
            "--out-md",
            str(tmp_path / "job.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_json.read_text(encoding="utf-8"))
    assert payload["summary"]["job_status"] == "completed"
    assert payload["summary"]["gpu_detected"] is True
    assert payload["summary"]["raw_pdb_exists"] is True
    assert raw_pdb.exists()
    assert runtime["summary"]["target_id"] == "T8200"


def test_run_casp17_custom_backend_job_blocks_without_gpu_when_required(tmp_path: Path) -> None:
    backend_script = tmp_path / "dummy_backend.py"
    fasta = tmp_path / "T8201.fasta"
    probe = tmp_path / "gpu.json"
    out_json = tmp_path / "job.json"
    raw_pdb = tmp_path / "job/T8201_model_1.pdb"
    _write_dummy_backend(backend_script)
    fasta.write_text(">T8201\nA\n", encoding="utf-8")
    probe.write_text(json.dumps({"gpu_detected": False, "gpu_names": []}), encoding="utf-8")

    run = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_custom_backend_job.py"),
            "--target-id",
            "T8201",
            "--sequence-path",
            str(fasta),
            "--raw-pdb",
            str(raw_pdb),
            "--gpu-probe-json",
            str(probe),
            "--command-template",
            f"python3 {backend_script} --raw-pdb {{raw_pdb}}",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "job.csv"),
            "--out-md",
            str(tmp_path / "job.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert run.returncode == 2
    assert payload["summary"]["job_status"] == "blocked_no_gpu"
    assert raw_pdb.exists() is False


def test_run_casp17_custom_backend_job_fails_when_backend_omits_raw_pdb(tmp_path: Path) -> None:
    backend_script = tmp_path / "empty_backend.py"
    fasta = tmp_path / "T8202.fasta"
    probe = tmp_path / "gpu.json"
    out_json = tmp_path / "job.json"
    raw_pdb = tmp_path / "job/T8202_model_1.pdb"
    backend_script.write_text("print('done without pdb')\n", encoding="utf-8")
    fasta.write_text(">T8202\nA\n", encoding="utf-8")
    probe.write_text(json.dumps({"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}), encoding="utf-8")

    run = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_custom_backend_job.py"),
            "--target-id",
            "T8202",
            "--sequence-path",
            str(fasta),
            "--raw-pdb",
            str(raw_pdb),
            "--gpu-probe-json",
            str(probe),
            "--command-template",
            f"python3 {backend_script}",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "job.csv"),
            "--out-md",
            str(tmp_path / "job.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert run.returncode == 2
    assert payload["summary"]["job_status"] == "failed_missing_raw_pdb"
    assert payload["summary"]["raw_pdb_exists"] is False
