from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]


def _write_colorful_image(path: Path, size: tuple[int, int] = (80, 60)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, "#07111f")
    draw = ImageDraw.Draw(image)
    for x in range(size[0]):
        color = (x * 3 % 255, 40 + x * 5 % 180, 210 - x * 2 % 180)
        draw.line([(x, 0), (x, size[1])], fill=color)
    image.save(path)


def test_build_casp17_structure_image_quality_packet_passes_colorful_images(tmp_path: Path) -> None:
    render_json = tmp_path / "render.json"
    publication_json = tmp_path / "publication.json"
    plate = tmp_path / "renders" / "T9999_structure_molecular_plate.png"
    turntable = tmp_path / "renders" / "T9999_structure_turntable.png"
    stereo_depth = tmp_path / "renders" / "T9999_structure_stereo_depth.png"
    atlas = tmp_path / "renders" / "T9999_structure_atlas_panel.png"
    figure = tmp_path / "figures" / "T9999_publication_figure.png"
    inspection = tmp_path / "figures" / "T9999_molecular_inspection_poster.png"
    scene = tmp_path / "figures" / "T9999_molecular_scene_poster.png"
    review_board = tmp_path / "figures" / "T9999_molecular_review_board.png"
    showcase = tmp_path / "figures" / "T9999_molecular_showcase.png"
    _write_colorful_image(plate)
    _write_colorful_image(turntable)
    _write_colorful_image(stereo_depth)
    _write_colorful_image(atlas)
    _write_colorful_image(figure)
    _write_colorful_image(inspection)
    _write_colorful_image(scene)
    _write_colorful_image(review_board)
    _write_colorful_image(showcase)
    render_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "molecular_plate_png_path": str(plate),
                        "turntable_png_path": str(turntable),
                        "stereo_depth_png_path": str(stereo_depth),
                        "atlas_panel_png_path": str(atlas),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    publication_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "publication_figure_png_path": str(figure),
                        "inspection_poster_png_path": str(inspection),
                        "scene_poster_png_path": str(scene),
                        "review_board_png_path": str(review_board),
                        "molecular_showcase_png_path": str(showcase),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_image_quality_packet.py"),
            "--render-json",
            str(render_json),
            "--publication-figure-json",
            str(publication_json),
            "--image-key",
            "molecular_plate_png_path",
            "--image-key",
            "turntable_png_path",
            "--image-key",
            "stereo_depth_png_path",
            "--image-key",
            "atlas_panel_png_path",
            "--min-width",
            "40",
            "--min-height",
            "40",
            "--min-molecular-plate-width",
            "40",
            "--min-molecular-plate-height",
            "40",
            "--min-panel-width",
            "40",
            "--min-panel-height",
            "40",
            "--min-publication-width",
            "40",
            "--min-publication-height",
            "40",
            "--min-molecular-plate-colorful-pixels",
            "200",
            "--min-publication-colorful-pixels",
            "200",
            "--min-colorful-pixels",
            "200",
            "--sample-step",
            "1",
            "--edge-threshold",
            "1",
            "--min-edge-pixels",
            "10",
            "--min-publication-edge-pixels",
            "10",
            "--min-molecular-plate-edge-pixels",
            "10",
            "--min-luminance-range",
            "10",
            "--min-publication-luminance-range",
            "10",
            "--min-molecular-plate-luminance-range",
            "10",
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

    assert payload["summary"]["image_quality_status"] == "pass"
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["image_count"] == 9
    assert payload["summary"]["pass_count"] == 9
    assert payload["summary"]["target_complete_count"] == 1
    assert payload["summary"]["molecular_plate_pass_count"] == 1
    assert payload["summary"]["turntable_pass_count"] == 1
    assert payload["summary"]["turntable_count"] == 1
    assert payload["summary"]["stereo_depth_pass_count"] == 1
    assert payload["summary"]["stereo_depth_count"] == 1
    assert payload["summary"]["publication_image_pass_count"] == 5
    assert payload["summary"]["publication_image_count"] == 5
    assert payload["summary"]["min_estimated_edge_pixel_count"] >= 10
    assert payload["summary"]["min_luminance_range"] >= 10
    assert all(row["estimated_colorful_pixel_count"] >= 200 for row in payload["rows"])
    assert all(row["estimated_edge_pixel_count"] >= 10 for row in payload["rows"])
    assert "native accuracy" in payload["summary"]["claim_boundary"]


def test_build_casp17_structure_image_quality_packet_blocks_blank_or_missing_images(tmp_path: Path) -> None:
    render_json = tmp_path / "render.json"
    blank = tmp_path / "renders" / "T9999_structure_molecular_plate.png"
    blank.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 60), "#111111").save(blank)
    render_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "molecular_plate_png_path": str(blank),
                        "atlas_panel_png_path": str(tmp_path / "renders" / "missing.png"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_structure_image_quality_packet.py"),
            "--render-json",
            str(render_json),
            "--publication-figure-json",
            str(tmp_path / "missing_publication.json"),
            "--image-key",
            "molecular_plate_png_path",
            "--image-key",
            "atlas_panel_png_path",
            "--min-molecular-plate-width",
            "40",
            "--min-molecular-plate-height",
            "40",
            "--min-panel-width",
            "40",
            "--min-panel-height",
            "40",
            "--min-molecular-plate-colorful-pixels",
            "200",
            "--min-colorful-pixels",
            "200",
            "--sample-step",
            "1",
            "--edge-threshold",
            "1",
            "--min-edge-pixels",
            "10",
            "--min-molecular-plate-edge-pixels",
            "10",
            "--min-luminance-range",
            "10",
            "--min-molecular-plate-luminance-range",
            "10",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    blockers = ",".join(row["blockers"] for row in payload["rows"])

    assert result.returncode == 2
    assert payload["summary"]["image_quality_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 2
    assert "colorful_pixel_count_below_threshold" in blockers
    assert "edge_pixel_count_below_threshold" in blockers
    assert "luminance_range_below_threshold" in blockers
    assert "image_missing" in blockers
