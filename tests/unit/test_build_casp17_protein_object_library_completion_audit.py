from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _library_payload(tmp_path: Path) -> dict:
    protein_folder = tmp_path / "library" / "H9001_Example_Fab_Complex"
    object_folder = protein_folder / "chain_A"
    source_object = tmp_path / "targets" / "H9001_Example_Fab_Complex" / "objects" / "chain_A"
    model = source_object / "models" / "H9001_chain_A.pdb"
    projection = source_object / "renders" / "H9001_chain_A_projection.svg"
    viewer = source_object / "viewer.html"
    for path in [object_folder, source_object, model.parent, projection.parent]:
        path.mkdir(parents=True, exist_ok=True)
    model.write_text(
        "ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    projection.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
    viewer.write_text("<!doctype html><canvas id=\"viewer\"></canvas>\n", encoding="utf-8")
    (protein_folder / "README.md").write_text("# protein\n", encoding="utf-8")
    (object_folder / "README.md").write_text("# object\n", encoding="utf-8")
    row = {
        "target_id": "H9001",
        "protein_name": "Example Fab Complex",
        "protein_key": "H9001_Example_Fab_Complex",
        "object_id": "chain_A",
        "chain_id": "A",
        "library_status": "pass",
        "library_protein_folder": str(protein_folder),
        "library_object_folder": str(object_folder),
        "source_object_folder": str(source_object),
        "model_path": str(model),
        "projection_svg_path": str(projection),
        "viewer_html_path": str(viewer),
        "atom_count": 1,
        "protein_atom_count": 1,
        "residue_count": 1,
        "coordinate_status": "valid",
        "blockers": "",
    }
    _write_json(
        protein_folder / "protein_manifest.json",
        {
            "summary": {
                "target_id": "H9001",
                "protein_key": "H9001_Example_Fab_Complex",
                "object_count": 1,
            },
            "objects": [row],
        },
    )
    _write_json(object_folder / "object_manifest.json", {"summary": row})
    return {
        "summary": {
            "protein_object_library_status": "pass",
            "library_dir": str(tmp_path / "library"),
        },
        "rows": [row],
    }


def test_completion_audit_passes_when_all_3d_object_assets_exist(tmp_path: Path) -> None:
    library_json = tmp_path / "library.json"
    _write_json(library_json, _library_payload(tmp_path))

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library_completion_audit.py"),
            "--protein-object-library-json",
            str(library_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["completion_audit_status"] == "pass"
    assert summary["protein_folder_count"] == 1
    assert summary["object_folder_count"] == 1
    assert summary["object_pass_count"] == 1
    assert summary["model_file_present_count"] == 1
    assert summary["projection_file_present_count"] == 1
    assert summary["viewer_file_present_count"] == 1
    assert summary["object_manifest_present_count"] == 1
    assert summary["protein_manifest_present_count"] == 1
    assert payload["rows"][0]["audit_status"] == "pass"
    assert payload["protein_rows"][0]["protein_status"] == "pass"
    assert _read_csv(tmp_path / "audit.csv")[0]["audit_status"] == "pass"
    assert (tmp_path / "casp17_protein_object_library_completion_audit_proteins_current.csv").is_file()
    assert "CASP17 Protein Object Library Completion Audit" in (tmp_path / "AUDIT.md").read_text(encoding="utf-8")


def test_completion_audit_blocks_missing_viewer(tmp_path: Path) -> None:
    payload = _library_payload(tmp_path)
    viewer = Path(payload["rows"][0]["viewer_html_path"])
    viewer.unlink()
    library_json = tmp_path / "library.json"
    _write_json(library_json, payload)

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library_completion_audit.py"),
            "--protein-object-library-json",
            str(library_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["summary"]["completion_audit_status"] == "blocked"
    assert payload["summary"]["object_blocked_count"] == 1
    assert "viewer_html_missing" in payload["rows"][0]["blockers"]
