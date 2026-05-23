from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, resseq: int, b_factor: float = 70.0) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}ALA A{resseq:4d}    "
        f"{float(serial):8.3f}{1.000:8.3f}{1.000:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def _run_validator(tmp_path: Path, *, runtime_payload: dict | None = None, pdb_text: str = "") -> tuple[int, dict]:
    sequence = tmp_path / "T8100.fasta"
    raw_pdb = tmp_path / "T8100_model_1.pdb"
    runtime_json = tmp_path / "backend_runtime.json"
    out_json = tmp_path / "contract.json"
    sequence.write_text(">T8100\nACDE\n", encoding="utf-8")
    raw_pdb.write_text(pdb_text or "\n".join([_atom(1, "N", 1), _atom(2, "CA", 2), "END", ""]), encoding="utf-8")
    if runtime_payload is not None:
        runtime_json.write_text(json.dumps(runtime_payload, indent=2), encoding="utf-8")
    command = [
        "python3",
        str(ROOT / "tools/validate_casp17_backend_contract.py"),
        "--target-id",
        "T8100",
        "--sequence-path",
        str(sequence),
        "--raw-pdb",
        str(raw_pdb),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "contract.csv"),
        "--out-md",
        str(tmp_path / "contract.md"),
    ]
    if runtime_payload is not None:
        command.extend(["--runtime-json", str(runtime_json)])
    run = subprocess.run(command, cwd=ROOT, check=False)
    return run.returncode, json.loads(out_json.read_text(encoding="utf-8"))


def test_validate_casp17_backend_contract_passes_with_gpu_runtime_evidence(tmp_path: Path) -> None:
    code, payload = _run_validator(
        tmp_path,
        runtime_payload={"summary": {"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}},
    )

    assert code == 0
    summary = payload["summary"]
    assert summary["contract_status"] == "pass"
    assert summary["gpu_evidence_detected"] is True
    assert summary["atom_count"] == 2
    assert summary["ca_count"] == 1


def test_validate_casp17_backend_contract_blocks_missing_gpu_evidence(tmp_path: Path) -> None:
    code, payload = _run_validator(tmp_path, runtime_payload={"summary": {"gpu_detected": False}})

    assert code == 2
    assert payload["summary"]["contract_status"] == "blocked"
    assert {blocker["code"] for blocker in payload["blockers"]} == {"backend_runtime_gpu_evidence_missing"}


def test_validate_casp17_backend_contract_blocks_atomless_pdb(tmp_path: Path) -> None:
    code, payload = _run_validator(
        tmp_path,
        runtime_payload={"summary": {"gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}},
        pdb_text="REMARK no atoms\nEND\n",
    )

    assert code == 2
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "raw_prediction_atom_records_missing" in codes
    assert "raw_prediction_ca_records_missing" in codes


def test_validate_casp17_backend_contract_enforces_internal_physics_sequence_exactness(tmp_path: Path) -> None:
    sequence = tmp_path / "T8101.fasta"
    raw_pdb = tmp_path / "T8101_model_1.pdb"
    runtime_json = tmp_path / "backend_runtime.json"
    out_json = tmp_path / "contract.json"
    sequence.write_text(">T8101\nACD\n", encoding="utf-8")
    raw_pdb.write_text(
        "\n".join(
            [
                _atom(1, "CA", 1, 70.0).replace("ALA", "ALA"),
                _atom(2, "CA", 2, 70.0).replace("ALA", "CYS"),
                _atom(3, "CA", 3, 70.0).replace("ALA", "GLU"),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    runtime_json.write_text(
        json.dumps({"summary": {"backend_kind": "internal_physics", "gpu_detected": True, "gpu_names": ["AMD Radeon RX 6900 XT"]}}),
        encoding="utf-8",
    )
    command = [
        "python3",
        str(ROOT / "tools/validate_casp17_backend_contract.py"),
        "--target-id",
        "T8101",
        "--sequence-path",
        str(sequence),
        "--raw-pdb",
        str(raw_pdb),
        "--runtime-json",
        str(runtime_json),
        "--backend-kind",
        "internal_physics",
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "contract.csv"),
        "--out-md",
        str(tmp_path / "contract.md"),
    ]

    run = subprocess.run(command, cwd=ROOT, check=False)

    assert run.returncode == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "internal_physics_sequence_mismatch" in {blocker["code"] for blocker in payload["blockers"]}
