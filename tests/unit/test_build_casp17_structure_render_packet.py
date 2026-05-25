from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, chain: str, resseq: int, x: float, y: float, z: float, b_factor: float = 70.0) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4} ALA {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def _write_fixture_prediction(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PFRMAT TS",
        "TARGET T9999",
        "AUTHOR 1234-5678-ABCD",
        "METHOD internal render fixture",
        "MODEL 1",
        "PARENT N/A",
    ]
    serial = 1
    for index in range(1, 12):
        b_factor = 35.0 if index <= 2 else 76.0
        lines.append(_atom(serial, "CA", "A", index, index * 3.8, 0.2 * index, 0.1 * index, b_factor))
        serial += 1
        lines.append(_atom(serial, "CB", "A", index, index * 3.8, 1.6 + 0.2 * index, 0.2 * index, b_factor))
        serial += 1
    lines.append("TER")
    lines.append("PARENT N/A")
    for index in range(1, 9):
        b_factor = 38.0 if index == 1 else 72.0
        lines.append(_atom(serial, "CA", "B", index, index * 3.2, 7.0 + index * 0.3, 2.0 * index, b_factor))
        serial += 1
        lines.append(_atom(serial, "CB", "B", index, index * 3.2, 8.6 + index * 0.3, 2.0 * index + 0.2, b_factor))
        serial += 1
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_dense_qc_prediction(path: Path, *, residue_count: int = 50) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PFRMAT TS",
        "TARGET T9998",
        "AUTHOR 1234-5678-ABCD",
        "METHOD dense internal render fixture",
        "MODEL 1",
        "PARENT N/A",
    ]
    serial = 1
    for index in range(1, residue_count + 1):
        b_factor = 72.0
        lines.append(_atom(serial, "CA", "A", index, 0.0, 0.0, 0.0, b_factor))
        serial += 1
        lines.append(_atom(serial, "CB", "A", index, 0.0, 0.0, 0.0, b_factor))
        serial += 1
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_fake_pymol(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from PIL import Image

script = Path(sys.argv[-1])
text = script.read_text(encoding="utf-8")
match = re.search(r'png "([^"]+)"', text) or re.search(r"png ([^,\\s]+)", text)
if not match:
    raise SystemExit(2)
out = Path(match.group(1))
if not out.is_absolute():
    out = Path.cwd() / out
out.parent.mkdir(parents=True, exist_ok=True)
Image.new("RGB", (360, 240), (8, 17, 31)).save(out)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_build_casp17_structure_render_packet_outputs_nonblank_images(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    prediction_dir = tmp_path / "predictions"
    _write_fixture_prediction(prediction_dir / "T9999TS.pdb")
    watchlist.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_render_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--prediction-dir",
            str(prediction_dir),
            "--out-dir",
            str(tmp_path / "renders"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
            "--qc-contact-sheet",
            str(tmp_path / "qc_contact.png"),
            "--surface-contact-sheet",
            str(tmp_path / "surface_contact.png"),
            "--confidence-contact-sheet",
            str(tmp_path / "confidence_contact.png"),
            "--residue-class-contact-sheet",
            str(tmp_path / "residue_class_contact.png"),
            "--interface-contact-sheet",
            str(tmp_path / "interface_contact.png"),
            "--review-contact-sheet",
            str(tmp_path / "review_contact.png"),
            "--atlas-contact-sheet",
            str(tmp_path / "atlas_contact.png"),
            "--molecular-plate-contact-sheet",
            str(tmp_path / "molecular_plate_contact.png"),
            "--presentation-plate-contact-sheet",
            str(tmp_path / "presentation_plate_contact.png"),
            "--stereo-contact-sheet",
            str(tmp_path / "stereo_depth_contact.png"),
            "--turntable-contact-sheet",
            str(tmp_path / "turntable_contact.png"),
            "--out-html",
            str(tmp_path / "gallery.html"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--dpi",
            "80",
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    png = ROOT / row["png_path"] if not Path(row["png_path"]).is_absolute() else Path(row["png_path"])
    if not png.exists():
        png = tmp_path / "renders/T9999_structure.png"
    assert payload["summary"]["rendered_count"] == 1
    assert payload["summary"]["molecular_plate_count"] == 1
    assert payload["summary"]["stereo_depth_count"] == 1
    assert payload["summary"]["turntable_count"] == 1
    assert "internal CASP17 predicted coordinates" in payload["summary"]["claim_boundary"]
    assert "not official CASP accuracy evidence" in payload["summary"]["claim_boundary"]
    assert row["render_status"] == "rendered"
    assert row["chain_count"] == 2
    assert row["ca_count"] == 19
    assert row["atom_count"] == 38
    assert row["sidechain_atom_count"] == 19
    assert png.exists()
    publication_png = ROOT / row["publication_png_path"] if not Path(row["publication_png_path"]).is_absolute() else Path(row["publication_png_path"])
    if not publication_png.exists():
        publication_png = tmp_path / "renders/T9999_structure_publication.png"
    assert row["publication_png_path"]
    assert publication_png.exists()
    studio_png = ROOT / row["studio_png_path"] if not Path(row["studio_png_path"]).is_absolute() else Path(row["studio_png_path"])
    if not studio_png.exists():
        studio_png = tmp_path / "renders/T9999_structure_studio.png"
    assert row["studio_png_path"]
    assert studio_png.exists()
    residue_class_png = ROOT / row["residue_class_png_path"] if not Path(row["residue_class_png_path"]).is_absolute() else Path(row["residue_class_png_path"])
    if not residue_class_png.exists():
        residue_class_png = tmp_path / "renders/T9999_structure_residue_class.png"
    assert row["residue_class_png_path"]
    assert residue_class_png.exists()
    interface_png = ROOT / row["interface_map_png_path"] if not Path(row["interface_map_png_path"]).is_absolute() else Path(row["interface_map_png_path"])
    if not interface_png.exists():
        interface_png = tmp_path / "renders/T9999_structure_interface_map.png"
    assert row["interface_map_png_path"]
    assert interface_png.exists()
    assert row["interface_pair_count"] == 1
    assert row["interface_contacts_12a_total"] > 0
    assert row["interface_min_ca_distance_A"] > 0
    stereo_depth_png = ROOT / row["stereo_depth_png_path"] if not Path(row["stereo_depth_png_path"]).is_absolute() else Path(row["stereo_depth_png_path"])
    if not stereo_depth_png.exists():
        stereo_depth_png = tmp_path / "renders/T9999_structure_stereo_depth.png"
    assert row["stereo_depth_png_path"]
    assert stereo_depth_png.exists()
    turntable_png = ROOT / row["turntable_png_path"] if not Path(row["turntable_png_path"]).is_absolute() else Path(row["turntable_png_path"])
    if not turntable_png.exists():
        turntable_png = tmp_path / "renders/T9999_structure_turntable.png"
    assert row["turntable_png_path"]
    assert turntable_png.exists()
    atlas_png = ROOT / row["atlas_panel_png_path"] if not Path(row["atlas_panel_png_path"]).is_absolute() else Path(row["atlas_panel_png_path"])
    if not atlas_png.exists():
        atlas_png = tmp_path / "renders/T9999_structure_atlas_panel.png"
    assert row["atlas_panel_png_path"]
    assert atlas_png.exists()
    molecular_plate_png = ROOT / row["molecular_plate_png_path"] if not Path(row["molecular_plate_png_path"]).is_absolute() else Path(row["molecular_plate_png_path"])
    if not molecular_plate_png.exists():
        molecular_plate_png = tmp_path / "renders/T9999_structure_molecular_plate.png"
    assert row["molecular_plate_png_path"]
    assert molecular_plate_png.exists()
    presentation_plate_png = ROOT / row["presentation_plate_png_path"] if not Path(row["presentation_plate_png_path"]).is_absolute() else Path(row["presentation_plate_png_path"])
    if not presentation_plate_png.exists():
        presentation_plate_png = tmp_path / "renders/T9999_structure_presentation_plate.png"
    assert row["presentation_plate_png_path"]
    assert presentation_plate_png.exists()
    assert (tmp_path / "renders/T9999_structure.svg").exists()
    assert (tmp_path / "contact.png").exists()
    assert (tmp_path / "residue_class_contact.png").exists()
    assert (tmp_path / "interface_contact.png").exists()
    assert (tmp_path / "atlas_contact.png").exists()
    assert (tmp_path / "molecular_plate_contact.png").exists()
    assert (tmp_path / "presentation_plate_contact.png").exists()
    assert (tmp_path / "stereo_depth_contact.png").exists()
    assert (tmp_path / "turntable_contact.png").exists()
    assert (tmp_path / "gallery.html").exists()
    gallery_text = (tmp_path / "gallery.html").read_text(encoding="utf-8")
    assert "Publication PNG" in gallery_text
    assert "Studio PNG" in gallery_text
    assert "Residue Class PNG" in gallery_text
    assert "Interface Map PNG" in gallery_text
    assert "Stereo depth" in gallery_text
    assert "Turntable review" in gallery_text
    assert "Molecular plate" in gallery_text
    assert "Presentation plate" in gallery_text
    assert "Atlas PNG" in gallery_text
    assert "predicted CA interface contacts <=12A" in gallery_text
    assert "not official CASP accuracy evidence" in gallery_text
    assert "http://" not in gallery_text
    assert "https://" not in gallery_text

    image = Image.open(png).convert("RGB")
    extrema = image.getextrema()
    assert any(channel_min != channel_max for channel_min, channel_max in extrema)
    publication_image = Image.open(publication_png).convert("RGB")
    assert publication_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in publication_image.getextrema())
    studio_image = Image.open(studio_png).convert("RGB")
    assert studio_image.size[0] > image.size[0]
    studio_extrema = studio_image.getextrema()
    assert any(channel_min != channel_max for channel_min, channel_max in studio_extrema)
    assert studio_extrema[0][0] < 20
    residue_class_image = Image.open(residue_class_png).convert("RGB")
    assert residue_class_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in residue_class_image.getextrema())
    interface_image = Image.open(interface_png).convert("RGB")
    assert interface_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in interface_image.getextrema())
    stereo_depth_image = Image.open(stereo_depth_png).convert("RGB")
    assert stereo_depth_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in stereo_depth_image.getextrema())
    turntable_image = Image.open(turntable_png).convert("RGB")
    assert turntable_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in turntable_image.getextrema())
    atlas_image = Image.open(atlas_png).convert("RGB")
    assert atlas_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in atlas_image.getextrema())
    molecular_plate_image = Image.open(molecular_plate_png).convert("RGB")
    assert molecular_plate_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in molecular_plate_image.getextrema())
    presentation_plate_image = Image.open(presentation_plate_png).convert("RGB")
    assert presentation_plate_image.size[0] > image.size[0]
    assert any(channel_min != channel_max for channel_min, channel_max in presentation_plate_image.getextrema())


def test_build_casp17_structure_render_packet_can_emit_pymol_artifacts(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    prediction_dir = tmp_path / "predictions"
    fake_pymol = tmp_path / "fake_pymol"
    _write_fixture_prediction(prediction_dir / "T9999TS.pdb")
    watchlist.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_fake_pymol(fake_pymol)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_render_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--prediction-dir",
            str(prediction_dir),
            "--out-dir",
            str(tmp_path / "renders"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
            "--qc-contact-sheet",
            str(tmp_path / "qc_contact.png"),
            "--surface-contact-sheet",
            str(tmp_path / "surface_contact.png"),
            "--confidence-contact-sheet",
            str(tmp_path / "confidence_contact.png"),
            "--residue-class-contact-sheet",
            str(tmp_path / "residue_class_contact.png"),
            "--interface-contact-sheet",
            str(tmp_path / "interface_contact.png"),
            "--review-contact-sheet",
            str(tmp_path / "review_contact.png"),
            "--atlas-contact-sheet",
            str(tmp_path / "atlas_contact.png"),
            "--molecular-plate-contact-sheet",
            str(tmp_path / "molecular_plate_contact.png"),
            "--presentation-plate-contact-sheet",
            str(tmp_path / "presentation_plate_contact.png"),
            "--stereo-contact-sheet",
            str(tmp_path / "stereo_depth_contact.png"),
            "--turntable-contact-sheet",
            str(tmp_path / "turntable_contact.png"),
            "--out-html",
            str(tmp_path / "gallery.html"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--dpi",
            "80",
            "--pymol-render",
            "--require-pymol-render",
            "--pymol-qc-render",
            "--require-pymol-qc-render",
            "--pymol-surface-render",
            "--require-pymol-surface-render",
            "--pymol-confidence-render",
            "--require-pymol-confidence-render",
            "--pymol-executable",
            str(fake_pymol),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    pymol_png = Path(row["pymol_png_path"])
    pymol_script = Path(row["pymol_script_path"])
    pymol_surface_png = Path(row["pymol_surface_png_path"])
    pymol_surface_script = Path(row["pymol_surface_script_path"])
    pymol_confidence_png = Path(row["pymol_confidence_png_path"])
    pymol_confidence_script = Path(row["pymol_confidence_script_path"])
    pymol_qc_png = Path(row["pymol_qc_png_path"])
    pymol_qc_script = Path(row["pymol_qc_script_path"])
    residue_class_png = Path(row["residue_class_png_path"])
    interface_map_png = Path(row["interface_map_png_path"])
    review_panel = Path(row["review_panel_png_path"])
    atlas_panel = Path(row["atlas_panel_png_path"])
    molecular_plate = Path(row["molecular_plate_png_path"])
    presentation_plate = Path(row["presentation_plate_png_path"])
    stereo_depth = Path(row["stereo_depth_png_path"])
    turntable = Path(row["turntable_png_path"])

    assert payload["summary"]["pymol_rendered_count"] == 1
    assert payload["summary"]["pymol_qc_rendered_count"] == 1
    assert payload["summary"]["pymol_surface_rendered_count"] == 1
    assert payload["summary"]["pymol_confidence_rendered_count"] == 1
    assert payload["summary"]["review_panel_count"] == 1
    assert payload["summary"]["residue_class_panel_count"] == 1
    assert payload["summary"]["interface_map_panel_count"] == 1
    assert payload["summary"]["interface_contacts_12a_total"] > 0
    assert payload["summary"]["atlas_panel_count"] == 1
    assert payload["summary"]["molecular_plate_count"] == 1
    assert payload["summary"]["presentation_plate_count"] == 1
    assert payload["summary"]["stereo_depth_count"] == 1
    assert payload["summary"]["turntable_count"] == 1
    assert payload["summary"]["pymol_qc_hotspot_count"] > 0
    assert payload["summary"]["pymol_qc_total_hotspot_count"] == payload["summary"]["pymol_qc_hotspot_count"]
    assert payload["summary"]["pymol_qc_display_hotspot_count"] == payload["summary"]["pymol_qc_hotspot_count"]
    assert payload["summary"]["pymol_qc_hotspot_truncated_target_count"] == 0
    assert row["pymol_render_status"] == "rendered"
    assert row["pymol_qc_render_status"] == "rendered"
    assert row["pymol_qc_hotspot_count"] > 0
    assert row["pymol_qc_total_hotspot_count"] == row["pymol_qc_hotspot_count"]
    assert row["pymol_qc_hotspot_raw_count"] == row["pymol_qc_hotspot_count"]
    assert row["pymol_qc_display_hotspot_count"] == row["pymol_qc_hotspot_count"]
    assert row["pymol_qc_rendered_hotspot_count"] == row["pymol_qc_hotspot_count"]
    assert row["pymol_qc_hotspot_truncated"] is False
    assert row["pymol_qc_hotspot_top_details"]
    assert row["pymol_qc_low_confidence_hotspot_count"] > 0
    assert row["interface_pair_count"] == 1
    assert row["interface_contacts_12a_total"] > 0
    assert pymol_png.exists()
    assert pymol_script.exists()
    assert pymol_surface_png.exists()
    assert pymol_surface_script.exists()
    assert pymol_confidence_png.exists()
    assert pymol_confidence_script.exists()
    assert pymol_qc_png.exists()
    assert pymol_qc_script.exists()
    assert residue_class_png.exists()
    assert interface_map_png.exists()
    assert review_panel.exists()
    assert atlas_panel.exists()
    assert molecular_plate.exists()
    assert presentation_plate.exists()
    assert stereo_depth.exists()
    assert turntable.exists()
    assert "show cartoon" in pymol_script.read_text(encoding="utf-8")
    assert "show sticks" in pymol_script.read_text(encoding="utf-8")
    surface_script_text = pymol_surface_script.read_text(encoding="utf-8")
    assert "transparent surface" in surface_script_text
    assert "show surface" in surface_script_text
    confidence_script_text = pymol_confidence_script.read_text(encoding="utf-8")
    assert "confidence render" in confidence_script_text
    assert "set_color casp17_conf_" in confidence_script_text
    assert row["confidence_b_factor_min"] <= row["confidence_b_factor_median"] <= row["confidence_b_factor_max"]
    qc_script_text = pymol_qc_script.read_text(encoding="utf-8")
    assert "CASP17 QC overlay" in qc_script_text
    assert "casp17_qc_low" in qc_script_text
    gallery_text = (tmp_path / "gallery.html").read_text(encoding="utf-8")
    assert "PyMOL PNG" in gallery_text
    assert "PyMOL surface PNG" in gallery_text
    assert "Confidence PNG" in gallery_text
    assert "Residue Class PNG" in gallery_text
    assert "Interface Map PNG" in gallery_text
    assert "Stereo depth" in gallery_text
    assert "Turntable review" in gallery_text
    assert "PyMOL QC PNG" in gallery_text
    assert "Review panel" in gallery_text
    assert "Atlas PNG" in gallery_text
    assert "Molecular plate" in gallery_text
    assert "Presentation plate" in gallery_text
    assert "predicted CA interface contacts <=12A" in gallery_text
    assert "not official CASP accuracy evidence" in gallery_text
    assert (tmp_path / "qc_contact.png").exists()
    assert (tmp_path / "surface_contact.png").exists()
    assert (tmp_path / "confidence_contact.png").exists()
    assert (tmp_path / "residue_class_contact.png").exists()
    assert (tmp_path / "interface_contact.png").exists()
    assert (tmp_path / "review_contact.png").exists()
    assert (tmp_path / "atlas_contact.png").exists()
    assert (tmp_path / "molecular_plate_contact.png").exists()
    assert (tmp_path / "presentation_plate_contact.png").exists()
    assert (tmp_path / "stereo_depth_contact.png").exists()
    assert (tmp_path / "turntable_contact.png").exists()


def test_build_casp17_structure_render_packet_keeps_qc_markers_capped_but_tracks_raw_totals(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    prediction_dir = tmp_path / "predictions"
    fake_pymol = tmp_path / "fake_pymol"
    _write_dense_qc_prediction(prediction_dir / "T9998TS.pdb", residue_count=50)
    _write_fake_pymol(fake_pymol)
    watchlist.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9998",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_render_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--prediction-dir",
            str(prediction_dir),
            "--out-dir",
            str(tmp_path / "renders"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
            "--qc-contact-sheet",
            str(tmp_path / "qc_contact.png"),
            "--surface-contact-sheet",
            str(tmp_path / "surface_contact.png"),
            "--confidence-contact-sheet",
            str(tmp_path / "confidence_contact.png"),
            "--residue-class-contact-sheet",
            str(tmp_path / "residue_class_contact.png"),
            "--interface-contact-sheet",
            str(tmp_path / "interface_contact.png"),
            "--review-contact-sheet",
            str(tmp_path / "review_contact.png"),
            "--atlas-contact-sheet",
            str(tmp_path / "atlas_contact.png"),
            "--molecular-plate-contact-sheet",
            str(tmp_path / "molecular_plate_contact.png"),
            "--presentation-plate-contact-sheet",
            str(tmp_path / "presentation_plate_contact.png"),
            "--stereo-contact-sheet",
            str(tmp_path / "stereo_depth_contact.png"),
            "--turntable-contact-sheet",
            str(tmp_path / "turntable_contact.png"),
            "--out-html",
            str(tmp_path / "gallery.html"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--dpi",
            "60",
            "--pymol-qc-render",
            "--require-pymol-qc-render",
            "--pymol-executable",
            str(fake_pymol),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    qc_script_text = Path(row["pymol_qc_script_path"]).read_text(encoding="utf-8")

    assert row["pymol_qc_total_hotspot_count"] > 36
    assert row["pymol_qc_hotspot_raw_count"] == row["pymol_qc_total_hotspot_count"]
    assert row["pymol_qc_hotspot_count"] == 36
    assert row["pymol_qc_display_hotspot_count"] == 36
    assert row["pymol_qc_rendered_hotspot_count"] == 36
    assert row["pymol_qc_hotspot_marker_cap"] == 36
    assert row["pymol_qc_hotspot_truncated"] is True
    assert 0 < len(row["pymol_qc_hotspot_top_details"]) <= 10
    assert qc_script_text.count("select qc_hotspot_") == 36
    assert payload["summary"]["pymol_qc_total_hotspot_count"] == row["pymol_qc_total_hotspot_count"]
    assert payload["summary"]["pymol_qc_hotspot_count"] == 36
    assert payload["summary"]["pymol_qc_display_hotspot_count"] == 36
    assert payload["summary"]["pymol_qc_hotspot_truncated_target_count"] == 1
