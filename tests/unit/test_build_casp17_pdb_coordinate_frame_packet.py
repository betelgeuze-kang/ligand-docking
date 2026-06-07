from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_coordinate_frame_packet_translates_negative_overflow_without_geometry_change(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    out_dir = tmp_path / "normalized"
    prediction_dir.mkdir()
    source = prediction_dir / "T9999TS.pdb"
    source.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T9999",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                "ATOM      1  N   ALA A   1    -1072.610  -2.164  -1.259  1.00 49.92           N  ",
                "ATOM      2  CA  ALA A   1    -1070.320  -1.904  -1.316  1.00 49.92           C  ",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_pdb_coordinate_frame_packet.py"),
            "--prediction-dir",
            str(prediction_dir),
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
    row = payload["rows"][0]
    normalized = (out_dir / "T9999TS.pdb").read_text(encoding="utf-8")
    atom_lines = [line for line in normalized.splitlines() if line.startswith("ATOM")]
    xs = [float(line[30:38]) for line in atom_lines]

    assert payload["summary"]["coordinate_frame_status"] == "pass"
    assert row["pre_fixed_width_parse_error_count"] == 2
    assert row["post_fixed_width_parse_error_count"] == 0
    assert row["x_shift"] > 0
    assert min(xs) >= -999.0
    assert round(xs[1] - xs[0], 3) == 2.29
