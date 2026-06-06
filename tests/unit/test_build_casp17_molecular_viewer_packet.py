from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float, b: float) -> str:
    element = atom[0]
    return (
        f"ATOM  {serial:5d} {atom:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b:6.2f}           {element:<2} "
    )


def _write_fixture_prediction(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PFRMAT TS",
        "TARGET T9999",
        "AUTHOR SECRET-AUTHOR-CODE",
        "METHOD internal molecular viewer fixture",
        "MODEL 1",
        "PARENT N/A",
    ]
    serial = 1
    for chain, offset, residues in [("A", 0.0, ["GLY", "HIS", "LYS"]), ("B", 12.0, ["ALA", "PHE"])]:
        for index, resname in enumerate(residues, start=1):
            x = offset + index * 3.8
            lines.append(_atom(serial, "N", resname, chain, index, x - 1.1, 0.0, 0.0, 40.0 + index))
            serial += 1
            lines.append(_atom(serial, "CA", resname, chain, index, x, 0.5, 0.2, 45.0 + index))
            serial += 1
            lines.append(_atom(serial, "C", resname, chain, index, x + 1.0, 0.0, 0.3, 50.0 + index))
            serial += 1
            lines.append(_atom(serial, "O", resname, chain, index, x + 1.4, -0.6, 0.2, 55.0 + index))
            serial += 1
        lines.extend(["TER", "PARENT N/A"])
    lines.extend(["END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_fixture_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR42mP8z8Dwn4GBgYGJgQkAABQ2A/0xk4lPAAAAAElFTkSuQmCC"
        )
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_molecular_viewer_packet_embeds_redacted_interactive_viewer(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    prediction_dir = tmp_path / "predictions"
    render_dir = tmp_path / "renders"
    render_json = tmp_path / "render.json"
    review_json = tmp_path / "review.json"
    all_atom_json = tmp_path / "all_atom.json"
    sidechain_json = tmp_path / "sidechain.json"
    _write_fixture_prediction(prediction_dir / "T9999TS.pdb")
    _write_fixture_png(render_dir / "T9999_structure_pymol.png")
    _write_json(
        render_json,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "pymol_qc_hotspot_raw_count": 9,
                    "pymol_qc_rendered_hotspot_count": 4,
                    "pymol_qc_low_confidence_hotspot_raw_count": 5,
                    "pymol_qc_rendered_low_confidence_hotspot_count": 3,
                    "pymol_qc_soft_hotspot_raw_count": 2,
                    "pymol_qc_rendered_soft_hotspot_count": 1,
                    "pymol_qc_hotspot_truncated": True,
                    "atlas_panel_png_path": "runs/casp17_structure_renders_current/T9999_structure_atlas_panel.png",
                }
            ]
        },
    )
    _write_json(
        review_json,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "qc_hotspots_raw": 11,
                    "qc_rendered_hotspots": 6,
                    "low_confidence_hotspots_raw": 7,
                    "low_confidence_rendered_hotspots": 4,
                    "soft_hotspots_raw": 3,
                    "soft_rendered_hotspots": 2,
                    "qc_hotspot_truncated": True,
                    "review_rank": 1,
                    "review_priority_score": 42.5,
                    "atlas_panel_png_path": "runs/casp17_structure_renders_current/T9999_structure_atlas_panel.png",
                }
            ]
        },
    )
    _write_json(
        all_atom_json,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "severe_clash_count": 0,
                    "soft_clash_count": 2,
                    "heavy_atom_completion_fraction": 0.98,
                }
            ]
        },
    )
    _write_json(
        sidechain_json,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "complete_sidechain_residue_fraction": 0.96,
                    "rotamer_proxy_pass_fraction": 0.94,
                }
            ]
        },
    )
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
            str(ROOT / "tools/casp17/build_casp17_molecular_viewer_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--prediction-dir",
            str(prediction_dir),
            "--render-dir",
            str(render_dir),
            "--render-json",
            str(render_json),
            "--review-queue-json",
            str(review_json),
            "--all-atom-quality-json",
            str(all_atom_json),
            "--sidechain-quality-json",
            str(sidechain_json),
            "--out-html",
            str(tmp_path / "viewer.html"),
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
    html = (tmp_path / "viewer.html").read_text(encoding="utf-8")

    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["blocked_count"] == 0
    assert payload["summary"]["author_redacted_in_embedded_pdb"] is True
    assert payload["summary"]["external_network_default"] == "disabled"
    assert payload["summary"]["webgl_runtime"] == "internal_canvas_runtime"
    assert payload["summary"]["internal_canvas_runtime_enabled"] is True
    assert payload["summary"]["static_preview_fallback_enabled"] is True
    assert payload["summary"]["viewer_runtime_order"] == "local_3dmol_bundle,internal_canvas_runtime,static_preview_fallback"
    assert payload["summary"]["external_molstar_link_enabled"] is False
    assert payload["summary"]["raw_qc_hotspot_count"] == 11
    assert payload["summary"]["all_atom_soft_clash_count"] == 2
    assert "hydrophobic" in payload["summary"]["residue_class_coloring"]
    assert "fixed B-factor confidence" in payload["summary"]["confidence_coloring"]
    assert row["viewer_status"] == "ready"
    assert row["chain_count"] == 2
    assert row["residue_count"] == 5
    assert row["atom_count"] == 20
    assert row["ca_count"] == 5
    assert row["chain_ids"] == "A,B"
    assert row["b_factor_mean"] > 0
    assert row["ca_gap_count"] == 0
    assert row["ca_clash_count"] == 0
    assert row["issue_marker_count"] == 0
    assert row["raw_qc_hotspot_count"] == 11
    assert row["rendered_qc_hotspot_count"] == 6
    assert row["raw_low_confidence_hotspot_count"] == 7
    assert row["raw_soft_hotspot_count"] == 3
    assert row["qc_hotspot_truncated"] is True
    assert row["all_atom_soft_clash_count"] == 2
    assert row["heavy_atom_completion_fraction"] == 0.98
    assert row["sidechain_complete_fraction"] == 0.96
    assert row["rotamer_proxy_pass_fraction"] == 0.94
    assert row["interface_pair_count"] == 1
    assert row["interface_contact_12a_total"] > 0
    residue_classes = json.loads(row["residue_class_counts_json"])
    assert residue_classes["hydrophobic"] == 1
    assert residue_classes["aromatic"] == 1
    assert residue_classes["positive"] == 2
    assert residue_classes["special"] == 1
    confidence_bins = json.loads(row["confidence_bins_json"])
    assert confidence_bins["very_low"] == 4
    assert confidence_bins["low"] == 1
    assert row["fallback_preview_png_path"].endswith("T9999_structure_pymol.png")

    assert "https://3Dmol.org/build/3Dmol-min.js" not in html
    assert "https://molstar.org/viewer/" not in html
    assert "T9999" in html
    assert "AUTHOR REDACTED_FOR_LOCAL_VIEWER" in html
    assert "SECRET-AUTHOR-CODE" not in html
    assert "external_molstar_link_enabled" in html
    assert "residue_class_by_resname" in html
    assert "Internal QC Overlay" in html
    assert "Confidence Bins" in html
    assert "Interface Contacts" in html
    assert "Low Confidence Residues" in html
    assert "raw_qc_hotspot_count" in html
    assert "all_atom_soft_clash_count" in html
    assert "id=\"internalCanvas\"" in html
    assert "parsePdbAtoms" in html
    assert "drawInternalScene" in html
    assert "renderInternalCanvas" in html
    assert "Internal canvas runtime active" in html
    assert "$3Dmol.createViewer" in html
    assert "data-repr=\"cartoon\"" in html
    assert "data-color=\"confidence\"" in html
    assert "data-color=\"residue\"" in html
    assert "Residue Classes" in html
    assert "residueClassColor" in html
    assert "residue_class_counts" in html
    assert "residue_class_colors" in html
    assert "id=\"issuesButton\"" in html
    assert "id=\"labelsButton\"" in html
    assert "id=\"darkButton\"" in html
    assert "id=\"fallbackPreview\"" in html
    assert "showFallbackPreview" in html
    assert "artifactUrl" in html
    assert "local static preview" in html
    assert "metricGaps" in html
    assert "metricClashes" in html
    assert "renderIssues" in html
    assert "setBackgroundColor" in html
