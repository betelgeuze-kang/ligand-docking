from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, chain: str, resseq: int, x: float, y: float, z: float, b_factor: float) -> str:
    return (
        f"ATOM  {serial:5d} CA   ALA {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def _write_candidate(path: Path, target_id: str, rank: int, coords: list[tuple[float, float, float]], b_factor: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PFRMAT TS",
        f"TARGET {target_id}",
        "AUTHOR 0000-0000-0000",
        "METHOD internal model selection fixture",
        f"MODEL {rank}",
        "PARENT N/A",
    ]
    for index, (x, y, z) in enumerate(coords, start=1):
        lines.append(_atom(index, "A", index, x, y, z, b_factor))
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_build_casp17_current_target_model_selection_packet_picks_consensus_candidate(tmp_path: Path) -> None:
    root = tmp_path / "top5"
    target_id = "T9999"
    linear = [(index * 3.8, 0.0, 0.0) for index in range(1, 9)]
    linear_near = [(index * 3.8, 0.2, 0.1) for index in range(1, 9)]
    outlier = [(index * 3.8, 9.0 if index % 2 else -9.0, 0.0) for index in range(1, 9)]
    _write_candidate(root / target_id / f"{target_id}_model_1TS.pdb", target_id, 1, outlier, 90.0)
    _write_candidate(root / target_id / f"{target_id}_model_2TS.pdb", target_id, 2, linear, 82.0)
    _write_candidate(root / target_id / f"{target_id}_model_3TS.pdb", target_id, 3, linear_near, 78.0)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_current_target_model_selection_packet.py"),
            "--ranked-prediction-dir",
            str(root),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--materialize-selected-dir",
            str(tmp_path / "selected"),
            "--require-materialized",
            "--max-span-per-residue",
            "99",
            "--max-radius-gyration-per-residue",
            "99",
            "--max-chain-linearity",
            "99",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    rows = payload["rows"]
    recommended = [row for row in rows if row["selection_status"] == "recommended_model_1"]

    assert payload["summary"]["selection_status"] == "pass"
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["candidate_count"] == 3
    assert payload["summary"]["recommended_non_rank1_count"] == 1
    assert payload["summary"]["materialization_status"] == "pass"
    assert payload["summary"]["materialized_count"] == 1
    assert payload["summary"]["materialized_non_rank1_count"] == 1
    assert recommended[0]["rank"] == 2
    assert recommended[0]["materialization_status"] == "materialized_selected_model_1"
    assert recommended[0]["materialized_selected_pdb"].endswith("selected/T9999TS.pdb")
    assert recommended[0]["consensus_score"] > rows[0]["consensus_score"]
    assert "no-leak historical calibration" in payload["summary"]["claim_boundary"]

    selected = (tmp_path / "selected" / "T9999TS.pdb").read_text(encoding="utf-8")
    assert "MODEL 1" in selected
    assert "MODEL 2" not in selected
    assert "REMARK INTERNAL_SELECTION_SOURCE_RANK 2" in selected


def test_build_casp17_current_target_model_selection_packet_blocks_overextended_recommendation(tmp_path: Path) -> None:
    root = tmp_path / "top5"
    target_id = "T9998"
    overextended = [(index * 30.0, 0.0, 0.0) for index in range(1, 9)]
    compact = [
        (0.0, 0.0, 0.0),
        (3.8, 0.0, 0.0),
        (3.8, 3.8, 0.0),
        (0.0, 3.8, 0.0),
        (0.0, 3.8, 3.8),
        (3.8, 3.8, 3.8),
        (3.8, 0.0, 3.8),
        (0.0, 0.0, 3.8),
    ]
    compact_near = [(x + 0.2, y - 0.1, z + 0.1) for x, y, z in compact]
    _write_candidate(root / target_id / f"{target_id}_model_1TS.pdb", target_id, 1, overextended, 95.0)
    _write_candidate(root / target_id / f"{target_id}_model_2TS.pdb", target_id, 2, compact, 80.0)
    _write_candidate(root / target_id / f"{target_id}_model_3TS.pdb", target_id, 3, compact_near, 80.0)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_current_target_model_selection_packet.py"),
            "--ranked-prediction-dir",
            str(root),
            "--out-json",
            str(tmp_path / "shape_packet.json"),
            "--out-csv",
            str(tmp_path / "shape_packet.csv"),
            "--out-md",
            str(tmp_path / "shape_packet.md"),
            "--max-span-per-residue",
            "1.0",
            "--max-radius-gyration-per-residue",
            "0.7",
            "--max-chain-linearity",
            "0.3",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "shape_packet.json").read_text(encoding="utf-8"))
    rows = payload["rows"]
    overextended_row = next(row for row in rows if row["rank"] == 1)
    recommended = [row for row in rows if row["selection_status"] == "recommended_model_1"]

    assert overextended_row["shape_status"] == "blocked_linear_or_overextended"
    assert overextended_row["shape_penalty"] > 0
    assert recommended
    assert recommended[0]["rank"] in {2, 3}
    assert recommended[0]["shape_status"] == "pass"
