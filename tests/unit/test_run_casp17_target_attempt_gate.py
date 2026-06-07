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


def _base_attempt_command(tmp_path: Path, launch: Path, *, execute: bool = False, stop_after: str = "submission_gate") -> list[str]:
    command = [
        "python3",
        str(ROOT / "tools/casp17/run_casp17_target_attempt_gate.py"),
        "--target-id",
        "T8300",
        "--launch-packet-json",
        str(launch),
        "--stop-after",
        stop_after,
        "--out-json",
        str(tmp_path / "attempt.json"),
        "--out-csv",
        str(tmp_path / "attempt.csv"),
        "--out-md",
        str(tmp_path / "attempt.md"),
    ]
    if execute:
        command.append("--execute")
    return command


def test_casp17_target_attempt_gate_blocks_nonready_launch_row(tmp_path: Path) -> None:
    launch = tmp_path / "launch.json"
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T8300",
                    "launch_status": "blocked",
                    "blockers": "no_supported_prediction_backend_detected",
                }
            ]
        },
    )

    subprocess.run(_base_attempt_command(tmp_path, launch), cwd=ROOT, check=True)

    payload = json.loads((tmp_path / "attempt.json").read_text(encoding="utf-8"))
    assert payload["summary"]["attempt_status"] == "blocked_by_launch_packet"
    assert payload["summary"]["blockers"] == ["no_supported_prediction_backend_detected"]
    assert payload["steps"][0]["step"] == "launch_packet"


def test_casp17_target_attempt_gate_plans_ready_launch_row(tmp_path: Path) -> None:
    launch = tmp_path / "launch.json"
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T8300",
                    "launch_status": "ready_to_launch",
                    "command": "predictor --target T8300",
                    "contract_command": "python3 contract.py",
                    "conversion_command": "python3 convert.py --author-code <CASP_AUTHOR_CODE>",
                }
            ]
        },
    )

    subprocess.run(_base_attempt_command(tmp_path, launch), cwd=ROOT, check=True)

    payload = json.loads((tmp_path / "attempt.json").read_text(encoding="utf-8"))
    assert payload["summary"]["attempt_status"] == "ready_not_executed"
    assert [row["step"] for row in payload["steps"]] == [
        "backend_job",
        "contract",
        "conversion",
        "import",
        "validation",
        "scorecard",
        "shape_sanity",
        "submission_gate",
    ]
    assert all(row["status"] == "planned" for row in payload["steps"])
    shape_step = next(row for row in payload["steps"] if row["step"] == "shape_sanity")
    submission_step = next(row for row in payload["steps"] if row["step"] == "submission_gate")
    assert "casp17/build_casp17_structure_shape_sanity_packet.py" in shape_step["command"]
    assert "--shape-sanity-json" in submission_step["command"]


def test_casp17_target_attempt_gate_executes_to_conversion(tmp_path: Path) -> None:
    backend = tmp_path / "dummy_backend.py"
    fasta = tmp_path / "T8300.fasta"
    probe = tmp_path / "gpu.json"
    job_dir = tmp_path / "job"
    raw_pdb = job_dir / "T8300_model_1.pdb"
    runtime_json = job_dir / "backend_runtime.json"
    ts_pdb = tmp_path / "predictions/T8300TS.pdb"
    launch = tmp_path / "launch.json"
    _write_dummy_backend(backend)
    fasta.write_text(">T8300\nA\n", encoding="utf-8")
    probe.write_text(json.dumps({"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}), encoding="utf-8")
    command = (
        f"python3 tools/run_casp17_custom_backend_job.py --target-id T8300 --sequence-path {fasta} "
        f"--out-dir {job_dir} --raw-pdb {raw_pdb} --runtime-json {runtime_json} --gpu-probe-json {probe} "
        f"--command-template 'python3 {backend} --raw-pdb {{raw_pdb}}'"
    )
    contract = (
        f"python3 tools/validate_casp17_backend_contract.py --target-id T8300 --sequence-path {fasta} "
        f"--raw-pdb {raw_pdb} --runtime-json {runtime_json} --require-gpu"
    )
    conversion = (
        f"python3 tools/convert_casp17_ts_prediction_from_pdb.py --target-id T8300 --input-pdb {raw_pdb} "
        f"--sequence-path {fasta} --author-code <CASP_AUTHOR_CODE> --out-pdb {ts_pdb}"
    )
    _write_json(
        launch,
        {
            "rows": [
                {
                    "target_id": "T8300",
                    "launch_status": "ready_to_launch",
                    "command": command,
                    "contract_command": contract,
                    "conversion_command": conversion,
                }
            ]
        },
    )

    subprocess.run(
        _base_attempt_command(tmp_path, launch, execute=True, stop_after="conversion")
        + ["--author-code", "1234-5678-ABCD"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "attempt.json").read_text(encoding="utf-8"))
    assert payload["summary"]["attempt_status"] == "completed_to_conversion"
    assert [row["status"] for row in payload["steps"]] == ["pass", "pass", "pass"]
    assert ts_pdb.exists()
    assert "AUTHOR 1234-5678-ABCD" in ts_pdb.read_text(encoding="utf-8")
