from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4} ALA {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.0:6.2f}           {atom[0]:>2}  "
    )


def _write_pdb(path: Path, target_id: str, coords: list[tuple[float, float, float]]) -> None:
    lines = ["PFRMAT TS", f"TARGET {target_id}", "AUTHOR 0000-0000-0000", "MODEL 1", "PARENT N/A"]
    serial = 1
    for index, (x, y, z) in enumerate(coords, start=1):
        lines.append(_atom(serial, "N", "A", index, x - 0.3, y, z))
        serial += 1
        lines.append(_atom(serial, "CA", "A", index, x, y, z))
        serial += 1
        lines.append(_atom(serial, "C", "A", index, x + 0.3, y, z))
        serial += 1
        lines.append(_atom(serial, "O", "A", index, x + 0.4, y, z))
        serial += 1
        lines.append(_atom(serial, "CB", "A", index, x, y + 1.5, z))
        serial += 1
    lines.extend(["TER", "END", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 220), color).save(path)


def _packet(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"summary": {"packet_type": "fixture"}, "rows": rows}


def test_build_casp17_model_selected_refinement_comparison_packet_blocks_promotion_but_writes_boards(
    tmp_path: Path,
) -> None:
    target_id = "T9999"
    active_dir = tmp_path / "active"
    selected_dir = tmp_path / "selected"
    _write_pdb(active_dir / f"{target_id}TS.pdb", target_id, [(i * 3.8, 0.0, 0.0) for i in range(1, 7)])
    _write_pdb(selected_dir / f"{target_id}TS.pdb", target_id, [(i * 3.8, 0.4, 0.0) for i in range(1, 7)])

    active_turntable = tmp_path / "active_turntable.png"
    selected_turntable = tmp_path / "selected_turntable.png"
    active_plate = tmp_path / "active_plate.png"
    selected_plate = tmp_path / "selected_plate.png"
    _write_png(active_turntable, (40, 90, 210))
    _write_png(selected_turntable, (30, 170, 120))
    _write_png(active_plate, (80, 120, 220))
    _write_png(selected_plate, (80, 180, 130))

    active_all = tmp_path / "active_all.json"
    selected_all = tmp_path / "selected_all.json"
    active_side = tmp_path / "active_side.json"
    selected_side = tmp_path / "selected_side.json"
    active_render = tmp_path / "active_render.json"
    selected_render = tmp_path / "selected_render.json"
    selection = tmp_path / "selection.json"

    active_all.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "all_atom_quality_status": "pass",
                        "soft_clash_count": 5,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    selected_all.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "all_atom_quality_status": "pass",
                        "soft_clash_count": 0,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    active_side.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "sidechain_quality_status": "pass",
                        "complete_sidechain_residue_fraction": 1.0,
                        "rotamer_proxy_pass_fraction": 1.0,
                        "mean_rotamer_angle_deviation_deg": 20.0,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    selected_side.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "sidechain_quality_status": "pass",
                        "complete_sidechain_residue_fraction": 1.0,
                        "rotamer_proxy_pass_fraction": 1.0,
                        "mean_rotamer_angle_deviation_deg": 15.0,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    active_render.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "render_status": "pass",
                        "turntable_png_path": str(active_turntable),
                        "presentation_plate_png_path": str(active_plate),
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    selected_render.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "render_status": "pass",
                        "turntable_png_path": str(selected_turntable),
                        "presentation_plate_png_path": str(selected_plate),
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    selection.write_text(
        json.dumps(
            _packet(
                [
                    {
                        "target_id": target_id,
                        "selection_status": "recommended_model_1",
                        "rank": 3,
                        "selection_score": 0.7,
                        "consensus_score": 0.6,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selected_refinement_comparison_packet.py"),
            "--active-prediction-dir",
            str(active_dir),
            "--model-selected-prediction-dir",
            str(selected_dir),
            "--selection-json",
            str(selection),
            "--active-all-atom-json",
            str(active_all),
            "--model-selected-all-atom-json",
            str(selected_all),
            "--active-sidechain-json",
            str(active_side),
            "--model-selected-sidechain-json",
            str(selected_side),
            "--active-render-json",
            str(active_render),
            "--model-selected-render-json",
            str(selected_render),
            "--out-dir",
            str(tmp_path / "boards"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
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

    assert payload["summary"]["comparison_status"] == "pass"
    assert payload["summary"]["promotion_status"] == "blocked_pending_no_leak_historical_calibration"
    assert payload["summary"]["model_selected_internal_candidate_count"] == 1
    assert row["lane_decision"] == "model_selected_internal_candidate"
    assert row["promotion_status"] == "blocked_pending_no_leak_historical_calibration"
    assert "historical_native_calibration_missing" in row["promotion_blockers"]
    assert Path(row["comparison_board_png_path"]).exists()
    assert (tmp_path / "contact.png").exists()
