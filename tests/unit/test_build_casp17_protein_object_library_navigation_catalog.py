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


def _completion_payload(tmp_path: Path) -> dict:
    protein_folder = tmp_path / "library" / "H9001_Example_Fab_Complex"
    object_folder = protein_folder / "chain_A"
    source_object = tmp_path / "objects" / "H9001" / "chain_A"
    model = source_object / "model.pdb"
    projection = source_object / "projection.svg"
    viewer = source_object / "viewer.html"
    for path in [protein_folder, object_folder, source_object]:
        path.mkdir(parents=True, exist_ok=True)
    (protein_folder / "README.md").write_text("# Example Fab Complex\n", encoding="utf-8")
    model.write_text(
        "ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    projection.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
    viewer.write_text("<!doctype html><canvas id=\"viewer\"></canvas>\n", encoding="utf-8")
    object_row = {
        "target_id": "H9001",
        "protein_name": "Example Fab Complex",
        "protein_key": "H9001_Example_Fab_Complex",
        "object_id": "chain_A",
        "chain_id": "A",
        "audit_status": "pass",
        "library_status": "pass",
        "library_protein_folder": str(protein_folder),
        "library_object_folder": str(object_folder),
        "protein_readme": str(protein_folder / "README.md"),
        "protein_manifest": str(protein_folder / "protein_manifest.json"),
        "object_readme": str(object_folder / "README.md"),
        "object_manifest": str(object_folder / "object_manifest.json"),
        "model_path": str(model),
        "projection_svg_path": str(projection),
        "viewer_html_path": str(viewer),
        "source_object_folder": str(source_object),
        "coordinate_status": "valid",
        "protein_atom_count": 1,
        "residue_count": 1,
        "blockers": "",
    }
    protein_row = {
        "protein_key": "H9001_Example_Fab_Complex",
        "target_id": "H9001",
        "protein_name": "Example Fab Complex",
        "library_protein_folder": str(protein_folder),
        "object_count": 1,
        "pass_count": 1,
        "blocked_count": 0,
        "protein_status": "pass",
        "protein_readme": str(protein_folder / "README.md"),
        "protein_manifest": str(protein_folder / "protein_manifest.json"),
        "blockers": "",
    }
    _write_json(protein_folder / "protein_manifest.json", {"summary": {"protein_key": protein_row["protein_key"]}})
    (object_folder / "README.md").write_text("# chain A\n", encoding="utf-8")
    _write_json(object_folder / "object_manifest.json", {"summary": {"object_id": "chain_A"}})
    return {
        "summary": {"completion_audit_status": "pass"},
        "protein_rows": [protein_row],
        "rows": [object_row],
    }


def test_navigation_catalog_builds_protein_name_links(tmp_path: Path) -> None:
    completion_json = tmp_path / "completion.json"
    _write_json(completion_json, _completion_payload(tmp_path))

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library_navigation_catalog.py"),
            "--completion-audit-json",
            str(completion_json),
            "--out-json",
            str(tmp_path / "catalog.json"),
            "--out-csv",
            str(tmp_path / "catalog.csv"),
            "--out-md",
            str(tmp_path / "CATALOG.md"),
            "--out-html",
            str(tmp_path / "catalog.html"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["navigation_catalog_status"] == "protein_object_library_navigation_catalog_ready"
    assert summary["protein_count"] == 1
    assert summary["object_count"] == 1
    assert summary["protein_readme_link_count"] == 1
    assert summary["protein_manifest_link_count"] == 1
    assert payload["rows"][0]["chain_ids"] == "A"
    assert payload["rows"][0]["first_object_id"] == "chain_A"
    assert _read_csv(tmp_path / "catalog.csv")[0]["catalog_status"] == "pass"
    assert "Example Fab Complex" in (tmp_path / "catalog.html").read_text(encoding="utf-8")
    assert "CASP17 Protein Object Library Navigation Catalog" in (tmp_path / "CATALOG.md").read_text(
        encoding="utf-8"
    )


def test_navigation_catalog_blocks_when_completion_audit_is_not_pass(tmp_path: Path) -> None:
    payload = _completion_payload(tmp_path)
    payload["summary"]["completion_audit_status"] = "blocked"
    completion_json = tmp_path / "completion.json"
    _write_json(completion_json, payload)

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library_navigation_catalog.py"),
            "--completion-audit-json",
            str(completion_json),
            "--out-json",
            str(tmp_path / "catalog.json"),
            "--out-csv",
            str(tmp_path / "catalog.csv"),
            "--out-md",
            str(tmp_path / "CATALOG.md"),
            "--out-html",
            str(tmp_path / "catalog.html"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["summary"]["navigation_catalog_status"] == "blocked_completion_audit_not_pass"
