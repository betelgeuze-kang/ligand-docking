from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.write_text(
        ",".join(fieldnames)
        + "\n"
        + "\n".join(",".join(row.get(key, "") for key in fieldnames) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def _run_gate(tmp_path: Path, intake: Path, launch: Path, profile: Path) -> dict:
    out_json = tmp_path / "coverage.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_prediction_coverage_gate.py"),
            "--intake-csv",
            str(intake),
            "--launch-packet-json",
            str(launch),
            "--backend-profile-json",
            str(profile),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "coverage.csv"),
            "--out-md",
            str(tmp_path / "coverage.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_prediction_coverage_gate_passes_when_all_protein_ready_and_profile_ready(tmp_path: Path) -> None:
    t_fasta = tmp_path / "T9000.fasta"
    h_fasta = tmp_path / "H9001.fasta"
    intake = tmp_path / "intake.csv"
    launch = tmp_path / "launch.json"
    profile = tmp_path / "profile.json"
    t_fasta.write_text(">T9000\nACDE\n", encoding="utf-8")
    h_fasta.write_text(">H9001_A\nACDE\n>H9001_B\nFGHI\n", encoding="utf-8")
    _write_intake(
        intake,
        [
            {"target_id": "T9000", "sequence_path": str(t_fasta)},
            {"target_id": "H9001", "sequence_path": str(h_fasta)},
            {"target_id": "R9002", "sequence_path": str(t_fasta)},
        ],
    )
    _write_json(
        launch,
        {
            "summary": {"target_scope": "all_protein"},
            "rows": [
                {"target_id": "T9000", "launch_status": "ready_to_launch", "target_kind": "protein_monomer_homomer"},
                {"target_id": "H9001", "launch_status": "ready_to_launch", "target_kind": "protein_complex"},
            ],
        },
    )
    _write_json(profile, {"summary": {"execution_status": "ready", "blockers": []}})

    payload = _run_gate(tmp_path, intake, launch, profile)

    summary = payload["summary"]
    assert summary["expected_protein_target_count"] == 2
    assert summary["launch_coverage_status"] == "pass"
    assert summary["prediction_tooling_status"] == "prediction_execution_ready"
    assert summary["blockers"] == []


def test_prediction_coverage_gate_blocks_missing_target_and_profile_blocker(tmp_path: Path) -> None:
    t_fasta = tmp_path / "T9000.fasta"
    h_fasta = tmp_path / "H9001.fasta"
    intake = tmp_path / "intake.csv"
    launch = tmp_path / "launch.json"
    profile = tmp_path / "profile.json"
    t_fasta.write_text(">T9000\nACDE\n", encoding="utf-8")
    h_fasta.write_text(">H9001_A\nACDE\n>H9001_B\nFGHI\n", encoding="utf-8")
    _write_intake(
        intake,
        [
            {"target_id": "T9000", "sequence_path": str(t_fasta)},
            {"target_id": "H9001", "sequence_path": str(h_fasta)},
        ],
    )
    _write_json(
        launch,
        {
            "summary": {"target_scope": "eligible"},
            "rows": [
                {"target_id": "T9000", "launch_status": "ready_to_launch", "target_kind": "protein_monomer_homomer"},
            ],
        },
    )
    _write_json(profile, {"summary": {"execution_status": "blocked", "blockers": ["operator_predictor_command_template_missing"]}})

    payload = _run_gate(tmp_path, intake, launch, profile)

    summary = payload["summary"]
    assert summary["prediction_tooling_status"] == "blocked"
    assert "launch_packet_not_all_protein_scope" in summary["blockers"]
    assert "operator_predictor_command_template_missing" in summary["blockers"]
    assert "all_protein_launch_coverage_not_ready" in summary["blockers"]
    by_target = {row["target_id"]: row for row in payload["rows"]}
    assert by_target["H9001"]["coverage_status"] == "blocked"
    assert by_target["H9001"]["blockers"] == "launch_row_missing"
