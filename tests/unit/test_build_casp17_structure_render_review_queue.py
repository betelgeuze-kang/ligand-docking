from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 360), color).save(path)


def test_build_casp17_structure_render_review_queue_prioritizes_hotspots(tmp_path: Path) -> None:
    render = tmp_path / "render.json"
    panel_a = tmp_path / "renders/T0001_review.png"
    panel_b = tmp_path / "renders/T0002_review.png"
    surface_a = tmp_path / "renders/T0001_surface.png"
    surface_b = tmp_path / "renders/T0002_surface.png"
    qc_a = tmp_path / "renders/T0001_qc.png"
    qc_b = tmp_path / "renders/T0002_qc.png"
    atlas_a = tmp_path / "renders/T0001_atlas.png"
    atlas_b = tmp_path / "renders/T0002_atlas.png"
    interface_a = tmp_path / "renders/T0001_interface.png"
    interface_b = tmp_path / "renders/T0002_interface.png"
    for path, color in [
        (panel_a, (10, 20, 40)),
        (panel_b, (40, 20, 10)),
        (surface_a, (20, 50, 80)),
        (surface_b, (80, 50, 20)),
        (qc_a, (80, 20, 60)),
        (qc_b, (60, 80, 20)),
        (atlas_a, (20, 80, 120)),
        (atlas_b, (120, 80, 20)),
        (interface_a, (30, 110, 180)),
        (interface_b, (180, 110, 30)),
    ]:
        _write_image(path, color)
    render.write_text(
        json.dumps(
            {
                "summary": {"generated_at_local": "2026-05-23T00:00:00+09:00"},
                "rows": [
                    {
                        "target_id": "T0001",
                        "pymol_qc_hotspot_count": 36,
                        "pymol_qc_soft_hotspot_count": 1,
                        "pymol_qc_low_confidence_hotspot_count": 35,
                        "pymol_qc_total_hotspot_count": 120,
                        "pymol_qc_total_soft_hotspot_count": 50,
                        "pymol_qc_total_low_confidence_hotspot_count": 100,
                        "pymol_qc_display_hotspot_count": 36,
                        "pymol_qc_display_soft_hotspot_count": 1,
                        "pymol_qc_display_low_confidence_hotspot_count": 35,
                        "pymol_qc_hotspot_truncated": True,
                        "pymol_qc_hotspot_top_details": [{"chain_id": "A", "resseq": 1, "hotspot_type": "soft_contact"}],
                        "interface_pair_count": 1,
                        "interface_contacts_8a_total": 4,
                        "interface_contacts_12a_total": 9,
                        "interface_min_ca_distance_A": 4.5,
                        "interface_map_png_path": str(interface_a),
                        "atom_count": 100,
                        "chain_count": 1,
                        "review_panel_png_path": str(panel_a),
                        "atlas_panel_png_path": str(atlas_a),
                        "pymol_surface_png_path": str(surface_a),
                        "pymol_qc_png_path": str(qc_a),
                        "pymol_png_path": str(panel_a),
                        "prediction_file_path": str(tmp_path / "T0001TS.pdb"),
                    },
                    {
                        "target_id": "T0002",
                        "pymol_qc_hotspot_count": 36,
                        "pymol_qc_soft_hotspot_count": 10,
                        "pymol_qc_low_confidence_hotspot_count": 20,
                        "pymol_qc_total_hotspot_count": 36,
                        "pymol_qc_total_soft_hotspot_count": 10,
                        "pymol_qc_total_low_confidence_hotspot_count": 20,
                        "pymol_qc_display_hotspot_count": 36,
                        "pymol_qc_display_soft_hotspot_count": 10,
                        "pymol_qc_display_low_confidence_hotspot_count": 20,
                        "pymol_qc_hotspot_truncated": False,
                        "pymol_qc_hotspot_top_details": [{"chain_id": "A", "resseq": 2, "hotspot_type": "soft_contact"}],
                        "interface_pair_count": 3,
                        "interface_contacts_8a_total": 20,
                        "interface_contacts_12a_total": 100,
                        "interface_min_ca_distance_A": 3.4,
                        "interface_map_png_path": str(interface_b),
                        "atom_count": 120,
                        "chain_count": 2,
                        "review_panel_png_path": str(panel_b),
                        "atlas_panel_png_path": str(atlas_b),
                        "pymol_surface_png_path": str(surface_b),
                        "pymol_qc_png_path": str(qc_b),
                        "pymol_png_path": str(panel_b),
                        "prediction_file_path": str(tmp_path / "T0002TS.pdb"),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_render_review_queue.py"),
            "--render-json",
            str(render),
            "--top-n",
            "2",
            "--contact-sheet",
            str(tmp_path / "priority.png"),
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "queue.md"),
            "--out-html",
            str(tmp_path / "queue.html"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "queue.json").read_text(encoding="utf-8"))

    assert payload["summary"]["review_queue_status"] == "ready"
    assert payload["summary"]["ready_count"] == 2
    assert payload["summary"]["total_qc_hotspots_raw"] == 156
    assert payload["summary"]["total_qc_hotspots_rendered"] == 72
    assert payload["summary"]["interface_map_ready_count"] == 2
    assert payload["summary"]["total_interface_pair_count"] == 4
    assert payload["summary"]["total_interface_contacts_12a"] == 109
    assert payload["summary"]["top_interface_target_id"] == "T0002"
    assert payload["summary"]["qc_hotspot_truncated_target_count"] == 1
    assert payload["rows"][0]["target_id"] == "T0001"
    assert payload["rows"][0]["soft_hotspots"] == 50
    assert payload["rows"][0]["interface_contacts_12a_total"] == 9
    assert payload["rows"][0]["interface_map_png_path"] == str(interface_a)
    assert payload["rows"][0]["qc_hotspots_raw"] == 120
    assert payload["rows"][0]["qc_rendered_hotspots"] == 36
    assert payload["rows"][0]["qc_hotspot_truncated"] is True
    assert payload["rows"][0]["atlas_panel_png_path"] == str(atlas_a)
    assert payload["rows"][1]["target_id"] == "T0002"
    assert (tmp_path / "priority.png").exists()
    assert (tmp_path / "queue.html").exists()
    md_text = (tmp_path / "queue.md").read_text(encoding="utf-8")
    html_text = (tmp_path / "queue.html").read_text(encoding="utf-8")
    assert "raw/rendered" in md_text
    assert "predicted CA interface pairs/contacts12A" in md_text
    assert "interface map" in html_text
    assert "not official CASP accuracy evidence" in html_text
