from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]


def _write_panel(path: Path, size: tuple[int, int] = (420, 260), seed: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, "#020617")
    draw = ImageDraw.Draw(image)
    for x in range(size[0]):
        color = ((x * (seed + 3)) % 255, (80 + x * (seed + 5)) % 255, (180 + x * (seed + 7)) % 255)
        draw.line((x, 0, x, size[1]), fill=color)
    for y in range(0, size[1], 14):
        draw.line((0, y, size[0], y), fill=(240, 248, 255), width=1)
    image.save(path)


def test_build_casp17_publication_figure_packet_composes_high_res_figures(tmp_path: Path) -> None:
    renders = tmp_path / "renders"
    paths: dict[str, str] = {}
    for index, key in enumerate(
        [
            "pymol_png_path",
            "pymol_confidence_png_path",
            "pymol_surface_png_path",
            "pymol_qc_png_path",
            "residue_class_png_path",
            "interface_map_png_path",
            "atlas_panel_png_path",
        ],
        start=1,
    ):
        path = renders / f"{key}.png"
        _write_panel(path, seed=index)
        paths[key] = str(path)

    render_json = tmp_path / "render.json"
    render_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "T9999",
                        "chain_count": 2,
                        "ca_count": 32,
                        "atom_count": 96,
                        "confidence_b_factor_median": 74.2,
                        "interface_contacts_12a_total": 18,
                        **paths,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_publication_figure_packet.py"),
            "--render-json",
            str(render_json),
            "--out-dir",
            str(tmp_path / "figures"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
            "--inspection-contact-sheet",
            str(tmp_path / "inspection_contact.png"),
            "--scene-contact-sheet",
            str(tmp_path / "scene_contact.png"),
            "--review-board-contact-sheet",
            str(tmp_path / "review_board_contact.png"),
            "--showcase-contact-sheet",
            str(tmp_path / "showcase_contact.png"),
            "--out-html",
            str(tmp_path / "gallery.html"),
            "--figure-width",
            "1200",
            "--figure-height",
            "720",
            "--min-width",
            "1000",
            "--min-height",
            "600",
            "--min-colorful-pixels",
            "20000",
            "--min-unique-colors",
            "40",
            "--min-luminance-range",
            "40",
            "--min-inset-count",
            "4",
            "--min-scene-panel-count",
            "4",
            "--min-review-board-panel-count",
            "6",
            "--sample-step",
            "2",
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

    assert payload["summary"]["publication_figure_status"] == "pass"
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["pass_count"] == 1
    assert row["publication_figure_status"] == "pass"
    assert row["hero_image_key"] == "pymol_png_path"
    assert row["inset_count"] >= 4
    assert row["inspection_panel_count"] >= 5
    assert row["scene_panel_count"] >= 4
    assert row["review_board_panel_count"] >= 6
    assert row["showcase_panel_count"] >= 4
    assert Path(row["publication_figure_png_path"]).exists()
    assert Path(row["inspection_poster_png_path"]).exists()
    assert Path(row["scene_poster_png_path"]).exists()
    assert Path(row["review_board_png_path"]).exists()
    assert Path(row["molecular_showcase_png_path"]).exists()
    assert (tmp_path / "contact.png").exists()
    assert (tmp_path / "inspection_contact.png").exists()
    assert (tmp_path / "scene_contact.png").exists()
    assert (tmp_path / "review_board_contact.png").exists()
    assert (tmp_path / "showcase_contact.png").exists()
    assert payload["summary"]["inspection_poster_count"] == 1
    assert payload["summary"]["scene_poster_count"] == 1
    assert payload["summary"]["review_board_count"] == 1
    assert payload["summary"]["molecular_showcase_count"] == 1
    assert "scene_contact_sheet_path" in payload["summary"]
    assert "inspection_contact_sheet_path" in payload["summary"]
    assert "review_board_contact_sheet_path" in payload["summary"]
    assert "showcase_contact_sheet_path" in payload["summary"]
    assert payload["summary"]["gallery_html_path"].endswith("gallery.html")
    assert (tmp_path / "gallery.html").exists()
    assert "native accuracy" in payload["summary"]["claim_boundary"]
    assert "http://" not in (tmp_path / "packet.md").read_text(encoding="utf-8")
    assert "https://" not in (tmp_path / "packet.md").read_text(encoding="utf-8")
    gallery = (tmp_path / "gallery.html").read_text(encoding="utf-8")
    assert "CASP17 Molecular Inspection Gallery" in gallery
    assert "T9999" in gallery
    assert "molecular scene poster" in gallery
    assert "molecular review board" in gallery
    assert "molecular showcase" in gallery
    assert "http://" not in gallery
    assert "https://" not in gallery


def test_build_casp17_publication_figure_packet_blocks_missing_hero(tmp_path: Path) -> None:
    render_json = tmp_path / "render.json"
    render_json.write_text(
        json.dumps({"rows": [{"target_id": "T9999", "pymol_png_path": str(tmp_path / "missing.png")}]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_publication_figure_packet.py"),
            "--render-json",
            str(render_json),
            "--out-dir",
            str(tmp_path / "figures"),
            "--contact-sheet",
            str(tmp_path / "contact.png"),
            "--inspection-contact-sheet",
            str(tmp_path / "inspection_contact.png"),
            "--scene-contact-sheet",
            str(tmp_path / "scene_contact.png"),
            "--review-board-contact-sheet",
            str(tmp_path / "review_board_contact.png"),
            "--showcase-contact-sheet",
            str(tmp_path / "showcase_contact.png"),
            "--out-html",
            str(tmp_path / "gallery.html"),
            "--min-width",
            "100",
            "--min-height",
            "100",
            "--min-colorful-pixels",
            "1",
            "--min-unique-colors",
            "1",
            "--min-luminance-range",
            "1",
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
    blockers = payload["rows"][0]["blockers"]

    assert result.returncode == 2
    assert payload["summary"]["publication_figure_status"] == "blocked"
    assert "hero_image_missing_or_unreadable" in blockers
