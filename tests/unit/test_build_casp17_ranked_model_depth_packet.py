from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, chain: str, resseq: int, x: float) -> str:
    return f"ATOM  {serial:5d} CA   ALA {chain}{resseq:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.00:6.2f}{60.0 + serial:6.2f}           C  "


def test_build_casp17_ranked_model_depth_packet_converts_top_models(tmp_path: Path) -> None:
    ranked_raw_root = tmp_path / "ranked_raw"
    target_raw = ranked_raw_root / "T9999"
    target_raw.mkdir(parents=True)
    for rank in range(1, 4):
        lines = [
            "REMARK fixture ranked raw model",
            *[_atom(index, "A", index, index * 3.8 + rank) for index in range(1, 5)],
            "END",
            "",
        ]
        (target_raw / f"T9999_model_{rank}.pdb").write_text("\n".join(lines), encoding="utf-8")

    sequence_dir = tmp_path / "seq"
    sequence_dir.mkdir()
    (sequence_dir / "T9999.fasta").write_text(">T9999\nAAAA\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_ranked_model_depth_packet.py"),
            "--target-ids",
            "T9999",
            "--ranked-raw-root",
            str(ranked_raw_root),
            "--sequence-dir",
            str(sequence_dir),
            "--out-dir",
            str(tmp_path / "top5_ts"),
            "--author-code",
            "TEST-AUTHOR",
            "--model-count",
            "3",
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
    row = payload["rows"][0]
    assert payload["summary"]["ranked_depth_status"] == "pass"
    assert payload["summary"]["candidate_gate_pass_count"] == 3
    assert payload["summary"]["candidate_gate_total_count"] == 3
    assert row["converted_count"] == 3
    assert row["candidate_gate_pass_count"] == 3
    assert row["ranked_depth_status"] == "pass"
    models = payload["models"]["T9999"]
    for rank in range(1, 4):
        ts_pdb = tmp_path / "top5_ts" / "T9999" / f"T9999_model_{rank}TS.pdb"
        text = ts_pdb.read_text(encoding="utf-8")
        assert f"MODEL {rank}" in text
        assert "PARENT N/A" in text
        assert "TER" in text
        assert models[rank - 1]["candidate_gate_status"] == "pass"
        assert models[rank - 1]["format_check_status"] == "pass"
        assert models[rank - 1]["geometry_sanity_status"] == "pass"
        assert models[rank - 1]["confidence_calibration_status"] == "pass"


def test_ranked_model_depth_keeps_converting_after_candidate_gate_failure(tmp_path: Path) -> None:
    ranked_raw_root = tmp_path / "ranked_raw"
    target_raw = ranked_raw_root / "T9998"
    target_raw.mkdir(parents=True)
    pass_lines = [
        "REMARK fixture ranked raw model",
        *[_atom(index, "A", index, index * 3.8) for index in range(1, 5)],
        "END",
        "",
    ]
    clash_lines = [
        "REMARK fixture ranked raw model with one nonlocal clash",
        _atom(1, "A", 1, 0.0),
        _atom(2, "A", 2, 3.8),
        _atom(3, "A", 3, 0.2),
        _atom(4, "A", 4, 4.0),
        "END",
        "",
    ]
    (target_raw / "T9998_model_1.pdb").write_text("\n".join(pass_lines), encoding="utf-8")
    (target_raw / "T9998_model_2.pdb").write_text("\n".join(clash_lines), encoding="utf-8")
    (target_raw / "T9998_model_3.pdb").write_text("\n".join(pass_lines), encoding="utf-8")

    sequence_dir = tmp_path / "seq"
    sequence_dir.mkdir()
    (sequence_dir / "T9998.fasta").write_text(">T9998\nAAAA\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_ranked_model_depth_packet.py"),
            "--target-ids",
            "T9998",
            "--ranked-raw-root",
            str(ranked_raw_root),
            "--sequence-dir",
            str(sequence_dir),
            "--out-dir",
            str(tmp_path / "top5_ts"),
            "--author-code",
            "TEST-AUTHOR",
            "--model-count",
            "3",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--allow-partial",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    models = payload["models"]["T9998"]

    assert row["converted_count"] == 3
    assert row["candidate_gate_pass_count"] == 2
    assert row["ranked_depth_status"] == "blocked"
    assert models[1]["candidate_gate_status"] == "blocked"
    assert models[2]["conversion_status"] == "pass"
    assert models[2]["candidate_gate_status"] == "pass"
