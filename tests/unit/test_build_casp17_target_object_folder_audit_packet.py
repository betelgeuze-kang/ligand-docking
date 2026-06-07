from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _object_row(target_folder: Path, *, chain_id: str = "A", object_id: str = "chain_A") -> dict[str, str | int]:
    object_folder = target_folder / "objects" / object_id
    model_path = object_folder / "models" / f"T9001_{object_id}.pdb"
    projection_path = object_folder / "renders" / f"T9001_{object_id}_projection.svg"
    viewer_path = object_folder / "viewer.html"
    manifest_path = object_folder / "metadata" / f"T9001_{object_id}_manifest.json"
    readme_path = object_folder / "README.md"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    projection_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        f"REMARK test object\nATOM      1  CA  ALA {chain_id}   1       0.000   1.000   2.000  1.00 70.00           C  \nTER\nEND\n",
        encoding="utf-8",
    )
    projection_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>\n',
        encoding="utf-8",
    )
    viewer_path.write_text(
        '<!doctype html><canvas id="viewer"></canvas><script>const atoms = [{"x":0,"y":0,"z":0}]; requestAnimationFrame(()=>{});</script>\n',
        encoding="utf-8",
    )
    row = {
        "target_id": "T9001",
        "protein_name": "Example Protein",
        "object_id": object_id,
        "chain_id": chain_id,
        "target_folder": str(target_folder),
        "object_folder": str(object_folder),
        "model_path": str(model_path),
        "projection_svg_path": str(projection_path),
        "viewer_html_path": str(viewer_path),
        "manifest_path": str(manifest_path),
        "readme_path": str(readme_path),
        "atom_count": 1,
        "protein_atom_count": 1,
        "residue_count": 1,
        "coordinate_status": "valid",
    }
    _write_json(manifest_path, {"summary": row, "claim_boundary": "local test boundary"})
    readme_path.write_text(
        f"# T9001 {object_id}\n\n{row['target_id']}\n{row['object_id']}\n{row['model_path']}\n{row['viewer_html_path']}\n",
        encoding="utf-8",
    )
    return row


def test_target_object_folder_audit_passes_independent_object_folder(tmp_path: Path) -> None:
    target_folder = tmp_path / "T9001_Example_Protein"
    row = _object_row(target_folder)
    target_json = tmp_path / "target_folders.json"
    _write_json(target_json, {"summary": {"blocked_count": 0}, "object_rows": [row]})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_object_folder_audit_packet.py"),
            "--target-model-folders-json",
            str(target_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))

    assert payload["summary"]["folder_audit_status"] == "pass"
    assert payload["summary"]["protein_named_folder_pass_count"] == 1
    assert payload["summary"]["chain_isolation_pass_count"] == 1
    assert payload["summary"]["protein_atom_pass_count"] == 1
    assert payload["summary"]["coordinate_valid_pass_count"] == 1
    assert payload["summary"]["total_protein_atom_count"] == 1
    assert payload["summary"]["viewer_local_only_pass_count"] == 1
    assert payload["rows"][0]["folder_audit_status"] == "pass"
    assert payload["rows"][0]["protein_atom_count"] == 1
    assert payload["rows"][0]["coordinate_status"] == "valid"


def test_target_object_folder_audit_blocks_wrong_chain_and_hosted_viewer(tmp_path: Path) -> None:
    target_folder = tmp_path / "T9001_Example_Protein"
    row = _object_row(target_folder, chain_id="B", object_id="chain_A")
    Path(str(row["viewer_html_path"])).write_text(
        '<!doctype html><script src="https://cdn.example.invalid/viewer.js"></script>\n',
        encoding="utf-8",
    )
    row["chain_id"] = "A"
    target_json = tmp_path / "target_folders.json"
    _write_json(target_json, {"summary": {"blocked_count": 0}, "object_rows": [row]})

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_object_folder_audit_packet.py"),
            "--target-model-folders-json",
            str(target_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    blockers = payload["rows"][0]["blockers"]

    assert result.returncode == 2
    assert payload["summary"]["folder_audit_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert "object_pdb_chain_isolation_failed" in blockers
    assert "viewer_hosted_dependency" in blockers


def test_target_object_folder_audit_blocks_hetatm_only_and_invalid_coordinates(tmp_path: Path) -> None:
    target_folder = tmp_path / "T9001_Example_Protein"
    hetatm_row = _object_row(target_folder, chain_id="A", object_id="chain_A")
    Path(str(hetatm_row["model_path"])).write_text(
        "REMARK ligand-only object\n"
        "HETATM    1  C1  LIG A   1       0.000   1.000   2.000  1.00 70.00           C  \n"
        "TER\nEND\n",
        encoding="utf-8",
    )
    hetatm_row["protein_atom_count"] = 0
    hetatm_row["residue_count"] = 0

    invalid_row = _object_row(target_folder, chain_id="B", object_id="chain_B")
    Path(str(invalid_row["model_path"])).write_text(
        "REMARK invalid coordinate object\n"
        "ATOM      1  CA  ALA B   1       BADVAL   1.000   2.000  1.00 70.00           C  \n"
        "TER\nEND\n",
        encoding="utf-8",
    )
    invalid_row["coordinate_status"] = "invalid"

    target_json = tmp_path / "target_folders.json"
    _write_json(target_json, {"summary": {"blocked_count": 0}, "object_rows": [hetatm_row, invalid_row]})

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_object_folder_audit_packet.py"),
            "--target-model-folders-json",
            str(target_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    blockers_by_object = {row["object_id"]: row["blockers"] for row in payload["rows"]}

    assert result.returncode == 2
    assert payload["summary"]["folder_audit_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 2
    assert payload["summary"]["protein_atom_pass_count"] == 1
    assert payload["summary"]["coordinate_valid_pass_count"] == 1
    assert payload["summary"]["total_protein_atom_count"] == 1
    assert "object_pdb_protein_atom_records_missing" in blockers_by_object["chain_A"]
    assert "object_pdb_coordinates_invalid" in blockers_by_object["chain_B"]
