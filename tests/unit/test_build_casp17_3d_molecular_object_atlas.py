import json
from pathlib import Path

from tools.casp17 import build_casp17_3d_molecular_object_atlas as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _source_object(tmp_path: Path, protein_key: str, object_id: str) -> dict:
    source_object = tmp_path / "source_current" / protein_key / object_id
    source_protein = source_object.parent
    _touch(source_protein / "README.md")
    _write_json(source_protein / "protein_manifest.json", {"summary": {"protein_key": protein_key}})
    _touch(source_object / "README.md")
    _write_json(source_object / "object_manifest.json", {"summary": {"object_id": object_id}})
    return {
        "target_id": protein_key.split("_", 1)[0],
        "protein_key": protein_key,
        "protein_name": "Shared complex",
        "object_id": object_id,
        "chain_id": object_id[-1],
        "library_status": "pass",
        "library_protein_folder": str(source_protein),
        "library_object_folder": str(source_object),
        "model_path": _touch(tmp_path / "models" / f"{object_id}.pdb", "ATOM\n"),
        "viewer_html_path": _touch(tmp_path / "viewers" / f"{object_id}.html"),
        "projection_svg_path": _touch(tmp_path / "renders" / f"{object_id}.svg"),
    }


def _freeze_object(tmp_path: Path, protein_key: str, target_id: str, protein_name: str) -> dict:
    source_object = tmp_path / "source_freeze" / protein_key / "model1_candidate"
    source_protein = source_object.parent
    _touch(source_protein / "README.md")
    _write_json(source_protein / "protein_manifest.json", {"summary": {"protein_key": protein_key}})
    _touch(source_object / "README.md")
    _write_json(source_object / "object_manifest.json", {"summary": {"object_id": "model1_candidate"}})
    return {
        "target_id": target_id,
        "target_group": "protein_complex",
        "protein_key": protein_key,
        "protein_name": protein_name,
        "object_id": "model1_candidate",
        "library_status": "pass",
        "library_protein_folder": str(source_protein),
        "library_object_folder": str(source_object),
        "protein_readme": str(source_protein / "README.md"),
        "protein_manifest": str(source_protein / "protein_manifest.json"),
        "object_readme": str(source_object / "README.md"),
        "object_manifest": str(source_object / "object_manifest.json"),
        "model_path": _touch(tmp_path / "freeze" / target_id / "model.cif", "ATOM\n"),
        "model_sha256": f"sha-{target_id}",
        "viewer_html": _touch(tmp_path / "freeze" / target_id / "viewer.html"),
        "projection_svg": _touch(tmp_path / "freeze" / target_id / "projection.svg"),
        "top5_manifest_csv": _touch(tmp_path / "freeze" / target_id / "top5.csv"),
        "top5_manifest_sha256": f"top5-{target_id}",
        "escrow_md": _touch(tmp_path / "freeze" / target_id / "FREEZE_ESCROW.md"),
        "native_status": "official_native_release_pending",
    }


def test_3d_molecular_object_atlas_unifies_current_and_massivefold_objects(
    tmp_path: Path,
) -> None:
    current_json = tmp_path / "current.json"
    freeze_json = tmp_path / "freeze.json"
    out_dir = tmp_path / "atlas"
    shared_key = "H2319_Shared_complex"
    freeze_only_key = "H2335_Freeze_only_complex"

    _write_json(
        current_json,
        {
            "summary": {"protein_object_library_status": "pass"},
            "rows": [
                _source_object(tmp_path, shared_key, "chain_A"),
                _source_object(tmp_path, shared_key, "chain_B"),
            ],
        },
    )
    _write_json(
        freeze_json,
        {
            "summary": {
                "massivefold_freeze_candidate_protein_library_status": (
                    "massivefold_freeze_candidate_protein_library_ready_external_only"
                )
            },
            "rows": [
                _freeze_object(tmp_path, shared_key, "H2319", "Shared complex"),
                _freeze_object(tmp_path, freeze_only_key, "H2335", "Freeze only complex"),
            ],
        },
    )

    args = mod.parse_args(
        [
            "--current-object-library-json",
            str(current_json),
            "--massivefold-freeze-protein-library-json",
            str(freeze_json),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "atlas.json"),
            "--out-csv",
            str(tmp_path / "atlas.csv"),
            "--out-md",
            str(tmp_path / "ATLAS.md"),
            "--out-html",
            str(tmp_path / "atlas.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {(row["atlas_protein_key"], row["atlas_object_key"]): row for row in payload["rows"]}
    assert summary["casp17_3d_molecular_object_atlas_status"] == (
        "casp17_3d_molecular_object_atlas_ready_review_only"
    )
    assert summary["protein_count"] == 2
    assert summary["object_count"] == 4
    assert summary["current_object_count"] == 2
    assert summary["massivefold_freeze_object_count"] == 2
    assert summary["current_protein_count"] == 1
    assert summary["massivefold_freeze_protein_count"] == 2
    assert summary["overlap_protein_count"] == 1
    assert summary["model_link_count"] == 4
    assert summary["viewer_link_count"] == 4
    assert summary["projection_link_count"] == 4
    assert summary["top5_link_count"] == 2
    assert summary["escrow_link_count"] == 2
    assert summary["model_sha256_count"] == 2
    assert summary["top5_sha256_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert rows[(shared_key, "current_chain_A")]["source_lane"] == "current_object_library"
    assert rows[(shared_key, "massivefold_model1_candidate")]["source_lane"] == (
        "massivefold_freeze_candidate"
    )

    shared_folder = out_dir / shared_key
    assert (shared_folder / "README.md").is_file()
    assert (shared_folder / "protein_manifest.json").is_file()
    assert (shared_folder / "current_chain_A" / "README.md").is_file()
    assert (shared_folder / "current_chain_A" / "object_manifest.json").is_file()
    assert (shared_folder / "massivefold_model1_candidate" / "README.md").is_file()
    assert not (shared_folder / "current_chain_A" / "chain_A.pdb").exists()
    assert "AUTHOR " not in (tmp_path / "atlas.json").read_text(encoding="utf-8")


def test_3d_molecular_object_atlas_blocks_missing_source_links(tmp_path: Path) -> None:
    current_json = tmp_path / "current.json"
    freeze_json = tmp_path / "freeze.json"
    _write_json(
        current_json,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "protein_key": "T9999_Missing",
                    "protein_name": "Missing",
                    "object_id": "chain_A",
                    "library_status": "blocked",
                    "library_protein_folder": str(tmp_path / "missing_protein"),
                    "library_object_folder": str(tmp_path / "missing_object"),
                    "model_path": str(tmp_path / "missing.pdb"),
                    "viewer_html_path": str(tmp_path / "missing.html"),
                    "projection_svg_path": str(tmp_path / "missing.svg"),
                }
            ]
        },
    )
    _write_json(freeze_json, {"rows": []})
    args = mod.parse_args(
        [
            "--current-object-library-json",
            str(current_json),
            "--massivefold-freeze-protein-library-json",
            str(freeze_json),
            "--out-dir",
            str(tmp_path / "atlas"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["casp17_3d_molecular_object_atlas_status"] == (
        "casp17_3d_molecular_object_atlas_blocked"
    )
    assert payload["summary"]["object_blocked_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "source_library_status_not_pass" in blockers
    assert "source_protein_folder_missing" in blockers
    assert "model_file_missing" in blockers
    assert "viewer_html_missing" in blockers
