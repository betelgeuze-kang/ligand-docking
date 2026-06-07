from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_object_files(root: Path, object_id: str = "chain_A") -> dict[str, str]:
    object_dir = root / object_id
    model = object_dir / "models" / "T9001_chain_A.pdb"
    projection = object_dir / "renders" / "T9001_chain_A_projection.svg"
    viewer = object_dir / "viewer.html"
    model.parent.mkdir(parents=True, exist_ok=True)
    projection.parent.mkdir(parents=True, exist_ok=True)
    model.write_text(
        "ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    projection.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>\n',
        encoding="utf-8",
    )
    viewer.write_text(
        '<!doctype html><canvas id="viewer"></canvas><script>const atoms = [{"x":0,"y":0,"z":0}]; requestAnimationFrame(()=>{});</script>\n',
        encoding="utf-8",
    )
    return {
        "target_id": "T9001",
        "protein_name": "Example",
        "object_id": object_id,
        "chain_id": "A",
        "model_path": str(model),
        "projection_svg_path": str(projection),
        "viewer_html_path": str(viewer),
        "atom_count": 1,
        "residue_count": 1,
    }


def test_target_object_viewer_smoke_passes_local_artifacts(tmp_path: Path) -> None:
    target_json = tmp_path / "target_folders.json"
    _write_json(
        target_json,
        {
            "summary": {"blocked_count": 0},
            "object_rows": [_write_object_files(tmp_path / "objects")],
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_object_viewer_smoke_packet.py"),
            "--target-model-folders-json",
            str(target_json),
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

    assert payload["summary"]["smoke_status"] == "pass"
    assert payload["summary"]["pass_count"] == 1
    assert payload["summary"]["hosted_dependency_violation_count"] == 0
    assert payload["rows"][0]["viewer_status"] == "pass"
    assert "does not render a browser screenshot" in payload["summary"]["claim_boundary"]


def test_target_object_viewer_smoke_blocks_missing_viewer_and_hosted_dependency(tmp_path: Path) -> None:
    row = _write_object_files(tmp_path / "objects")
    Path(row["viewer_html_path"]).write_text(
        '<!doctype html><script src="https://cdn.example.invalid/viewer.js"></script>\n',
        encoding="utf-8",
    )
    target_json = tmp_path / "target_folders.json"
    _write_json(target_json, {"summary": {"blocked_count": 0}, "object_rows": [row]})

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_object_viewer_smoke_packet.py"),
            "--target-model-folders-json",
            str(target_json),
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
    blockers = payload["rows"][0]["blockers"]

    assert result.returncode == 2
    assert payload["summary"]["smoke_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["hosted_dependency_violation_count"] == 1
    assert "viewer_canvas_missing" in blockers
    assert "viewer_hosted_dependency" in blockers
