from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_builder(tmp_path: Path, *extra: str, env: dict[str, str] | None = None) -> dict:
    out_json = tmp_path / "profile.json"
    command = [
        "python3",
        str(ROOT / "tools/casp17/build_casp17_backend_profile_packet.py"),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "profile.csv"),
        "--out-md",
        str(tmp_path / "profile.md"),
        *extra,
    ]
    subprocess.run(command, cwd=ROOT, check=True, env=env)
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_backend_profile_blocks_without_multimer_or_predictor_template(tmp_path: Path) -> None:
    payload = _run_builder(tmp_path)

    summary = payload["summary"]
    assert summary["execution_status"] == "blocked"
    assert "backend_multimer_support_not_declared" in summary["blockers"]
    assert "operator_predictor_command_template_missing" in summary["blockers"]
    assert "casp17/run_casp17_external_structure_predictor_adapter.py" in summary["custom_backend_command"]


def test_backend_profile_ready_with_multimer_and_embedded_template(tmp_path: Path) -> None:
    payload = _run_builder(
        tmp_path,
        "--supports-multimer",
        "--predictor-command-template",
        "predictor --fasta {fasta} --raw-pdb {raw_pdb}",
        "--embed-predictor-template",
    )

    summary = payload["summary"]
    assert summary["execution_status"] == "ready"
    assert summary["blockers"] == []
    assert summary["operator_predictor_template_source"] == "embedded_argument"
    launch = next(row for row in payload["rows"] if row["name"] == "all_protein_launch_command")
    assert "--backend-supports-multimer" in launch["value"]
    assert "predictor --fasta {fasta} --raw-pdb {raw_pdb}" in launch["value"]


def test_backend_profile_ready_with_env_predictor_template(tmp_path: Path) -> None:
    env = {
        **__import__("os").environ,
        "CASP17_STRUCTURE_PREDICTOR_COMMAND": "predictor --fasta {fasta} --raw-pdb {raw_pdb}",
    }
    payload = _run_builder(tmp_path, "--supports-multimer", env=env)

    summary = payload["summary"]
    assert summary["execution_status"] == "ready"
    assert summary["operator_predictor_template_source"] == "environment"
    assert summary["operator_predictor_template_sha256"] == ""
