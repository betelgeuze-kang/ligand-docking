from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _atom(serial: int, atom: str, resseq: int, b_factor: float = 70.0) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}ALA A{resseq:4d}    "
        f"{float(serial):8.3f}{1.000:8.3f}{1.000:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


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
                f"    {_atom(1, 'N', 1, 80.0)!r} + '\\n' +",
                f"    {_atom(2, 'CA', 1, 75.0)!r} + '\\n' +",
                "    'END\\n',",
                "    encoding='utf-8'",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_casp17_prediction_batch_gate_plans_ready_and_blocked_rows(tmp_path: Path) -> None:
    launch = tmp_path / "launch.json"
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T8400",
                    "target_kind": "protein_monomer_homomer",
                    "launch_status": "ready_to_launch",
                    "command": "predictor --target T8400",
                    "contract_command": "python3 contract.py",
                    "conversion_command": "python3 convert.py --author-code <CASP_AUTHOR_CODE>",
                },
                {
                    "target_id": "H8401",
                    "target_kind": "protein_complex",
                    "launch_status": "blocked",
                    "blockers": "backend_multimer_support_not_declared",
                },
            ]
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_prediction_batch_gate.py"),
            "--launch-packet-json",
            str(launch),
            "--out-json",
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "batch.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "batch.json").read_text(encoding="utf-8"))
    assert payload["summary"]["batch_status"] == "blocked_by_launch_packet"
    assert payload["summary"]["planned_count"] == 1
    assert payload["summary"]["blocked_count"] == 1
    assert payload["rows"][0]["batch_status"] == "planned"
    assert payload["rows"][1]["batch_status"] == "blocked_by_launch_packet"


def test_casp17_prediction_batch_gate_executes_ready_row_to_conversion(tmp_path: Path) -> None:
    backend = tmp_path / "dummy_backend.py"
    fasta = tmp_path / "T8400.fasta"
    probe = tmp_path / "gpu.json"
    job_dir = tmp_path / "job"
    raw_pdb = job_dir / "T8400_model_1.pdb"
    runtime_json = job_dir / "backend_runtime.json"
    ts_pdb = tmp_path / "predictions/T8400TS.pdb"
    launch = tmp_path / "launch.json"
    _write_dummy_backend(backend)
    fasta.write_text(">T8400\nA\n", encoding="utf-8")
    probe.write_text(json.dumps({"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}), encoding="utf-8")
    command = (
        f"python3 tools/run_casp17_custom_backend_job.py --target-id T8400 --sequence-path {fasta} "
        f"--out-dir {job_dir} --raw-pdb {raw_pdb} --runtime-json {runtime_json} --gpu-probe-json {probe} "
        f"--command-template 'python3 {backend} --raw-pdb {{raw_pdb}}'"
    )
    contract = (
        f"python3 tools/validate_casp17_backend_contract.py --target-id T8400 --sequence-path {fasta} "
        f"--raw-pdb {raw_pdb} --runtime-json {runtime_json} --require-gpu"
    )
    conversion = (
        f"python3 tools/convert_casp17_ts_prediction_from_pdb.py --target-id T8400 --input-pdb {raw_pdb} "
        f"--sequence-path {fasta} --author-code <CASP_AUTHOR_CODE> --out-pdb {ts_pdb}"
    )
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T8400",
                    "target_kind": "protein_monomer_homomer",
                    "launch_status": "ready_to_launch",
                    "command": command,
                    "contract_command": contract,
                    "conversion_command": conversion,
                }
            ]
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_prediction_batch_gate.py"),
            "--launch-packet-json",
            str(launch),
            "--execute",
            "--stop-after",
            "conversion",
            "--author-code",
            "1234-5678-ABCD",
            "--attempt-dir",
            str(tmp_path / "attempts"),
            "--out-json",
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "batch.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "batch.json").read_text(encoding="utf-8"))
    assert payload["summary"]["batch_status"] == "completed_to_conversion"
    assert payload["summary"]["completed_count"] == 1
    assert payload["rows"][0]["batch_status"] == "completed"
    assert payload["rows"][0]["attempt_status"] == "completed_to_conversion"
    assert ts_pdb.exists()
