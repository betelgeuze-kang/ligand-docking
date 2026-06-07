from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _source_row(tmp_path: Path, *, target_id: str = "H9001", protein_name: str = "Example Fab Complex") -> dict[str, str]:
    object_folder = tmp_path / "targets_current" / f"{target_id}_Example_Fab_Complex" / "objects" / "chain_A"
    model_path = object_folder / "models" / f"{target_id}_chain_A.pdb"
    projection_path = object_folder / "renders" / f"{target_id}_chain_A_projection.svg"
    viewer_path = object_folder / "viewer.html"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    projection_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        "ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    projection_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
    viewer_path.write_text("<!doctype html><canvas id=\"viewer\"></canvas>\n", encoding="utf-8")
    return {
        "target_id": target_id,
        "object_id": "chain_A",
        "chain_id": "A",
        "object_folder": str(object_folder),
        "model_path": str(model_path),
        "projection_svg_path": str(projection_path),
        "viewer_html_path": str(viewer_path),
        "atom_count": "1",
        "protein_atom_count": "1",
        "residue_count": "1",
        "coordinate_status": "valid",
        "protein_name": protein_name,
    }


def test_build_casp17_protein_object_library_creates_protein_named_object_folders(tmp_path: Path) -> None:
    source_csv = tmp_path / "objects.csv"
    out_dir = tmp_path / "protein_object_library_current"
    _write_csv(source_csv, [_source_row(tmp_path)])

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library.py"),
            "--target-object-csv",
            str(source_csv),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "library.json"),
            "--out-csv",
            str(tmp_path / "library.csv"),
            "--out-md",
            str(tmp_path / "library.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "library.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["protein_object_library_status"] == "pass"
    assert payload["summary"]["protein_folder_count"] == 1
    assert payload["summary"]["object_folder_count"] == 1
    assert payload["summary"]["model_pointer_count"] == 1
    assert row["library_protein_folder"].endswith("H9001_Example_Fab_Complex")
    assert Path(row["library_object_folder"], "README.md").is_file()
    assert Path(row["library_object_folder"], "object_manifest.json").is_file()


def test_build_casp17_protein_object_library_blocks_missing_model(tmp_path: Path) -> None:
    row = _source_row(tmp_path)
    Path(row["model_path"]).unlink()
    source_csv = tmp_path / "objects.csv"
    _write_csv(source_csv, [row])

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_protein_object_library.py"),
            "--target-object-csv",
            str(source_csv),
            "--out-dir",
            str(tmp_path / "library"),
            "--out-json",
            str(tmp_path / "library.json"),
            "--out-csv",
            str(tmp_path / "library.csv"),
            "--out-md",
            str(tmp_path / "library.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "library.json").read_text(encoding="utf-8"))

    assert result.returncode == 2
    assert payload["summary"]["protein_object_library_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert "model_pdb_missing" in payload["rows"][0]["blockers"]
