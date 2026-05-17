from __future__ import annotations

import numpy as np
from PIL import Image

from tools import render_readme_molecular_figures as mod


def test_build_viewer_url_pins_tcruzi_surface_and_rank() -> None:
    url = mod.build_viewer_url(8765)

    assert url.startswith("http://127.0.0.1:8765/viewer/index.html?")
    assert mod.build_viewer_url_template().startswith("http://127.0.0.1:<port>/viewer/index.html?")
    assert "surface-label=tcruzi_pde_allatom_review_packet" in url
    assert "rank=1" in url
    assert "repr=cartoon" in url
    assert "pocket=true" in url


def test_write_ca_multistate_pdb_preserves_frame_and_ca_counts(tmp_path) -> None:
    pdb = tmp_path / "chain_b.pdb"
    pdb.write_text(
        "\n".join(
            [
                "ATOM      1  N   MET B 277     -39.534 -45.171 -74.955  1.00 58.25           N",
                "ATOM      2  CA  MET B 277     -40.620 -44.164 -74.742  1.00 60.04           C",
                "ATOM      3  C   MET B 277     -41.754 -44.773 -73.912  1.00 61.17           C",
                "ATOM      4  CA  ILE B 278     -44.090 -44.699 -73.238  1.00 60.03           C",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    trajectory = tmp_path / "ca.npy"
    np.save(
        trajectory,
        np.array(
            [
                [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
                [[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
            ],
            dtype=np.float32,
        ),
    )
    out = tmp_path / "ca_multistate.pdb"

    result = mod.write_ca_multistate_pdb(source_pdb=pdb, trajectory_npy=trajectory, out_pdb=out)

    text = out.read_text(encoding="utf-8")
    assert result["frame_count"] == 2
    assert result["ca_count"] == 2
    assert text.count("MODEL") == 2
    assert text.count("ATOM") == 4
    assert "   1.000   2.000   3.000" in text
    assert "  10.000  11.000  12.000" in text


def test_build_pymol_script_references_actual_inputs_and_panels() -> None:
    script = mod.build_pymol_script()

    assert "data/public_structures/selected_allatom_native_v1/t_cruzi_pde_pdb_3V94.pdb" in script
    assert "tmp/render_inputs/tcruzi_pde_chain_B_openmm_ca_md_multistate.pdb" in script
    assert "create ligB, full and chain B and resn WYQ" in script
    assert "create metalB, full and chain B and (resn ZN or resn MG)" in script
    assert "tcruzi_domain_panel_readme.png" in script
    assert "tcruzi_pocket_panel_readme.png" in script


def test_write_manifest_uses_stable_viewer_url_template(monkeypatch, tmp_path) -> None:
    png = tmp_path / "figure.png"
    Image.new("RGB", (7, 5), (255, 255, 255)).save(png)
    manifest_json = tmp_path / "manifest.json"

    monkeypatch.setattr(mod, "VIEWER_IMAGE", png)
    monkeypatch.setattr(mod, "STRUCTURE_IMAGE", png)
    monkeypatch.setattr(mod, "MANIFEST_JSON", manifest_json)

    manifest = mod.write_manifest(
        viewer_url=mod.build_viewer_url(32123),
        ca_info={"out_pdb": "tmp/ca.pdb", "frame_count": 2, "ca_count": 2},
        skipped=[],
    )

    manifest_text = manifest_json.read_text(encoding="utf-8")
    assert manifest["viewer"]["captured_url"] == mod.build_viewer_url_template()
    assert "32123" not in manifest_text
    assert manifest["viewer"]["output_png"]["size"] == [7, 5]
    assert manifest["structure_render"]["output_png"]["mode"] == "RGB"
