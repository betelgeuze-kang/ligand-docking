import json
from pathlib import Path

from tools import build_casp17_target_object_model_review_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_object(root: Path, *, hosted_viewer: bool = False) -> dict:
    target_folder = root / "T9001_Example_protein"
    object_folder = target_folder / "objects" / "chain_A"
    model_path = object_folder / "models" / "T9001_chain_A.pdb"
    projection_path = object_folder / "renders" / "T9001_chain_A_projection.svg"
    viewer_path = object_folder / "viewer.html"
    manifest_path = object_folder / "metadata" / "T9001_chain_A_manifest.json"
    readme_path = object_folder / "README.md"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    projection_path.parent.mkdir(parents=True, exist_ok=True)
    viewer_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        "\n".join(
            [
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 70.00           C",
                "ATOM      2  CA  GLY A   2       3.000   4.000   0.000  1.00 70.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    projection_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>\n', encoding="utf-8")
    hosted = '<script src="https://example.test/viewer.js"></script>' if hosted_viewer else ""
    viewer_path.write_text(
        f'<canvas id="viewer"></canvas>{hosted}<script>const atoms = []; requestAnimationFrame(() => {{}});</script>',
        encoding="utf-8",
    )
    manifest_path.write_text("{}\n", encoding="utf-8")
    readme_path.write_text("T9001 chain_A\n", encoding="utf-8")
    return {
        "target_id": "T9001",
        "protein_name": "Example protein",
        "object_id": "chain_A",
        "chain_id": "A",
        "target_folder": str(target_folder),
        "object_folder": str(object_folder),
        "model_path": str(model_path),
        "projection_svg_path": str(projection_path),
        "viewer_html_path": str(viewer_path),
        "manifest_path": str(manifest_path),
        "readme_path": str(readme_path),
        "atom_count": 2,
        "protein_atom_count": 2,
        "residue_count": 2,
        "coordinate_status": "valid",
    }


def _args(tmp_path: Path, target_json: Path) -> list[str]:
    return [
        "--target-model-folders-json",
        str(target_json),
        "--out-json",
        str(tmp_path / "review.json"),
        "--out-csv",
        str(tmp_path / "review.csv"),
        "--out-md",
        str(tmp_path / "review.md"),
    ]


def test_target_object_model_review_passes_local_object(tmp_path: Path) -> None:
    object_row = _write_object(tmp_path)
    target_json = tmp_path / "target_model_folders.json"
    _write_json(
        target_json,
        {
            "summary": {"blocked_count": 0},
            "object_rows": [object_row],
        },
    )
    args = mod.parse_args(_args(tmp_path, target_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    row = payload["rows"][0]
    assert payload["summary"]["object_model_review_status"] == "pass"
    assert payload["summary"]["object_count"] == 1
    assert payload["summary"]["pass_count"] == 1
    assert payload["summary"]["review_md_count"] == 1
    assert payload["summary"]["viewer_local_pass_count"] == 1
    assert row["ca_atom_count"] == 2
    assert row["radius_of_gyration"] > 0
    assert Path(row["review_md_path"]).is_file()
    assert "OBJECT_MODEL_REVIEW" in str(row["review_md_path"])
    assert (tmp_path / "review.csv").is_file()
    assert (tmp_path / "review.md").is_file()


def test_target_object_model_review_blocks_hosted_viewer(tmp_path: Path) -> None:
    object_row = _write_object(tmp_path, hosted_viewer=True)
    target_json = tmp_path / "target_model_folders.json"
    _write_json(target_json, {"summary": {"blocked_count": 0}, "object_rows": [object_row]})
    args = mod.parse_args(_args(tmp_path, target_json))

    payload = mod.build_payload(args)

    row = payload["rows"][0]
    assert payload["summary"]["object_model_review_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert row["review_status"] == "blocked"
    assert "viewer_hosted_dependency" in row["blockers"]
