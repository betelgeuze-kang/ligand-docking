from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, chain: str, resseq: int, x: float, y: float, b_factor: float) -> str:
    return f"ATOM  {serial:5d} CA   ALA {chain}{resseq:4d}    {x:8.3f}{y:8.3f}{0.0:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "


def _write_ts(path: Path, target_id: str, atom_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                f"TARGET {target_id}",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                *atom_lines,
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_add_casp17_internal_score_records_emits_conservative_score_copy(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    out_dir = tmp_path / "scored"
    _write_ts(
        source_dir / "T9999TS.pdb",
        "T9999",
        [_atom(index, "A", index, 3.8 * index, 0.0, 55.0 + index) for index in range(1, 5)],
    )
    _write_ts(
        source_dir / "H9998TS.pdb",
        "H9998",
        [
            _atom(1, "A", 1, 0.0, 0.0, 70.0),
            _atom(2, "A", 2, 3.8, 0.0, 72.0),
            _atom(3, "B", 1, 0.0, 7.0, 68.0),
            _atom(4, "B", 2, 3.8, 7.0, 71.0),
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/add_casp17_internal_score_records.py"),
            "--target-ids",
            "T9999,H9998",
            "--source-dir",
            str(source_dir),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    monomer = (out_dir / "T9999TS.pdb").read_text(encoding="utf-8")
    assembly = (out_dir / "H9998TS.pdb").read_text(encoding="utf-8")

    assert payload["summary"]["score_record_status"] == "pass"
    assert payload["summary"]["score_record_count"] == 2
    assert payload["summary"]["qscore_multichain_count"] == 1
    assert "MODEL 1\nSCORE " in monomer
    assert "QSCORE" not in monomer
    assert "MODEL 1\nSCORE " in assembly
    assert "QSCORE AB:" in assembly
    assert "not native-calibrated" in assembly


def test_add_casp17_internal_score_records_emits_low_qscore_for_no_contact_assembly(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    out_dir = tmp_path / "scored"
    _write_ts(
        source_dir / "H9997TS.pdb",
        "H9997",
        [
            _atom(1, "A", 1, 0.0, 0.0, 70.0),
            _atom(2, "A", 2, 3.8, 0.0, 72.0),
            _atom(3, "B", 1, 100.0, 0.0, 68.0),
            _atom(4, "B", 2, 103.8, 0.0, 71.0),
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/add_casp17_internal_score_records.py"),
            "--target-ids",
            "H9997",
            "--source-dir",
            str(source_dir),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assembly = (out_dir / "H9997TS.pdb").read_text(encoding="utf-8")

    assert payload["summary"]["score_record_status"] == "pass"
    assert payload["summary"]["qscore_multichain_count"] == 1
    assert "QSCORE AB:0.030" in assembly
