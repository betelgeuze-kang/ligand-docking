from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_ts(path: Path, target_id: str, ca_coords: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PFRMAT TS\n",
        f"TARGET {target_id}\n",
        "AUTHOR 0000-0000-0000\n",
        "MODEL 1\n",
        "PARENT N/A\n",
    ]
    serial = 1
    for index, (x, y, z) in enumerate(ca_coords, start=1):
        lines.append(
            f"ATOM  {serial:5d}  CA  ALA A{index:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 80.00           C  \n"
        )
        serial += 1
    lines.extend(["TER\n", "ENDMDL\n", "END\n"])
    path.write_text("".join(lines), encoding="utf-8")


def test_build_casp17_structure_shape_sanity_packet_passes_compact_trace(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    coords: list[tuple[float, float, float]] = []
    for z in range(4):
        y_values = range(4) if z % 2 == 0 else range(3, -1, -1)
        for y in y_values:
            x_values = range(4) if (y + z) % 2 == 0 else range(3, -1, -1)
            for x in x_values:
                coords.append((3.8 * x, 3.8 * y, 3.8 * z))
    _write_ts(prediction_dir / "T0001TS.pdb", "T0001", coords)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_shape_sanity_packet.py"),
            "--prediction-dir",
            str(prediction_dir),
            "--out-json",
            str(tmp_path / "shape.json"),
            "--out-csv",
            str(tmp_path / "shape.csv"),
            "--out-md",
            str(tmp_path / "shape.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "shape.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["shape_sanity_status"] == "pass"
    assert summary["pass_count"] == 1
    assert row["shape_sanity_status"] == "pass"
    assert row["blockers"] == ""
    assert "Local CA-shape sanity gate only" in summary["claim_boundary"]


def test_build_casp17_structure_shape_sanity_packet_blocks_overextended_trace(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    coords = [(float(index) * 12.0, 0.0, 0.0) for index in range(8)]
    _write_ts(prediction_dir / "T9999TS.pdb", "T9999", coords)

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_shape_sanity_packet.py"),
            "--prediction-dir",
            str(prediction_dir),
            "--out-json",
            str(tmp_path / "shape.json"),
            "--out-csv",
            str(tmp_path / "shape.csv"),
            "--out-md",
            str(tmp_path / "shape.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "shape.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    row = payload["rows"][0]

    assert result.returncode == 2
    assert summary["shape_sanity_status"] == "blocked"
    assert summary["blocked_targets"] == "T9999"
    assert row["shape_sanity_status"] == "blocked"
    assert "ca_span_per_residue_above_threshold" in row["blockers"]
    assert "max_ca_gap_above_threshold" in row["blockers"]
