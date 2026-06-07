from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _viewer_data(*, fallback_path: str, pdb_text: str) -> dict:
    return {
        "summary": {
            "target_count": 1,
            "ready_count": 1,
            "webgl_runtime": "internal_canvas_runtime",
            "internal_canvas_runtime_enabled": True,
            "static_preview_fallback_enabled": True,
            "external_network_default": "disabled",
        },
        "targets": [
            {
                "target_id": "T9999",
                "chain_count": 1,
                "residue_count": 2,
                "atom_count": 8,
                "ca_count": 2,
                "fallback_preview_png_path": fallback_path,
                "pdb_text": pdb_text,
            }
        ],
    }


def _write_html(path: Path, data: dict, *, external_url: bool = False) -> None:
    external = '<script src="https://3Dmol.org/build/3Dmol-min.js"></script>' if external_url else ""
    html = f"""<!doctype html>
<html>
<head>{external}</head>
<body>
<div id="viewer"><canvas id="internalCanvas"></canvas></div>
<script type="application/json" id="viewerData">{json.dumps(data)}</script>
<script>
function parsePdbAtoms() {{}}
function setupInternalScene() {{}}
function bindInternalCanvasEvents() {{}}
function drawInternalScene() {{}}
function renderInternalCanvas() {{}}
function showFallbackPreview() {{}}
function artifactUrl() {{}}
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _pdb_text(author: str = "AUTHOR REDACTED_FOR_LOCAL_VIEWER") -> str:
    return "\n".join(
        [
            "PFRMAT TS",
            "TARGET T9999",
            author,
            "METHOD fixture",
            "MODEL 1",
            "ATOM      1 N    GLY A   1       0.000   0.000   0.000  1.00 50.00           N  ",
            "ATOM      2 CA   GLY A   1       1.000   0.000   0.000  1.00 50.00           C  ",
            "ATOM      3 C    GLY A   1       2.000   0.000   0.000  1.00 50.00           C  ",
            "ATOM      4 O    GLY A   1       3.000   0.000   0.000  1.00 50.00           O  ",
            "ATOM      5 N    ALA A   2       4.000   0.000   0.000  1.00 60.00           N  ",
            "ATOM      6 CA   ALA A   2       5.000   0.000   0.000  1.00 60.00           C  ",
            "ATOM      7 C    ALA A   2       6.000   0.000   0.000  1.00 60.00           C  ",
            "ATOM      8 O    ALA A   2       7.000   0.000   0.000  1.00 60.00           O  ",
            "END",
            "",
        ]
    )


def test_build_casp17_molecular_viewer_smoke_packet_passes_internal_canvas_viewer(tmp_path: Path) -> None:
    fallback = tmp_path / "renders" / "T9999_structure_presentation_plate.png"
    fallback.parent.mkdir(parents=True)
    fallback.write_bytes(b"not-empty")
    viewer_json = tmp_path / "viewer.json"
    viewer_html = tmp_path / "viewer.html"
    data = _viewer_data(fallback_path=str(fallback), pdb_text=_pdb_text())
    viewer_json.write_text(json.dumps({"summary": data["summary"]}), encoding="utf-8")
    _write_html(viewer_html, data)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_molecular_viewer_smoke_packet.py"),
            "--viewer-json",
            str(viewer_json),
            "--viewer-html",
            str(viewer_html),
            "--out-json",
            str(tmp_path / "smoke.json"),
            "--out-csv",
            str(tmp_path / "smoke.csv"),
            "--out-md",
            str(tmp_path / "smoke.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["viewer_smoke_status"] == "pass"
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["internal_symbol_count"] == 8
    assert payload["summary"]["hosted_molecular_url_violation_count"] == 0
    assert payload["summary"]["author_redaction_pass_count"] == 1
    assert row["embedded_pdb_atom_count"] == 8
    assert row["embedded_pdb_ca_count"] == 2
    assert row["fallback_is_presentation_plate"] is True
    assert "Static local viewer smoke only" in payload["summary"]["claim_boundary"]


def test_build_casp17_molecular_viewer_smoke_packet_blocks_external_runtime_and_author_leak(tmp_path: Path) -> None:
    fallback = tmp_path / "renders" / "T9999_structure_pymol.png"
    fallback.parent.mkdir(parents=True)
    fallback.write_bytes(b"not-empty")
    viewer_json = tmp_path / "viewer.json"
    viewer_html = tmp_path / "viewer.html"
    data = _viewer_data(fallback_path=str(fallback), pdb_text=_pdb_text("AUTHOR SECRET-AUTHOR-CODE"))
    viewer_json.write_text(json.dumps({"summary": data["summary"]}), encoding="utf-8")
    _write_html(viewer_html, data, external_url=True)

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_molecular_viewer_smoke_packet.py"),
            "--viewer-json",
            str(viewer_json),
            "--viewer-html",
            str(viewer_html),
            "--out-json",
            str(tmp_path / "smoke.json"),
            "--out-csv",
            str(tmp_path / "smoke.csv"),
            "--out-md",
            str(tmp_path / "smoke.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert result.returncode == 2
    assert payload["summary"]["viewer_smoke_status"] == "blocked"
    assert payload["summary"]["hosted_molecular_url_violation_count"] == 1
    assert "viewer_html_missing_or_invalid" in payload["summary"]["blockers"]
    assert "author_not_redacted" in row["blockers"]
    assert "fallback_not_presentation_plate" in row["blockers"]
