import json
from pathlib import Path

from tools import build_casp17_3d_molecular_object_atlas_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _atlas_object(tmp_path: Path, protein_key: str, object_key: str, lane: str) -> dict:
    atlas_protein = tmp_path / "atlas" / protein_key
    atlas_object = atlas_protein / object_key
    source_object = tmp_path / "source" / protein_key / object_key
    _touch(atlas_protein / "README.md")
    _write_json(atlas_protein / "protein_manifest.json", {"summary": {"protein_key": protein_key}})
    _touch(atlas_object / "README.md")
    _write_json(atlas_object / "object_manifest.json", {"summary": {"object_key": object_key}})
    _touch(source_object / "README.md")
    _write_json(source_object / "object_manifest.json", {"summary": {"object_key": object_key}})
    row = {
        "atlas_protein_key": protein_key,
        "atlas_object_key": object_key,
        "source_lane": lane,
        "target_id": protein_key.split("_", 1)[0],
        "protein_name": "Audit complex",
        "object_id": object_key,
        "atlas_status": "pass",
        "atlas_protein_folder": str(atlas_protein),
        "atlas_object_folder": str(atlas_object),
        "atlas_protein_readme": str(atlas_protein / "README.md"),
        "atlas_protein_manifest": str(atlas_protein / "protein_manifest.json"),
        "atlas_object_readme": str(atlas_object / "README.md"),
        "atlas_object_manifest": str(atlas_object / "object_manifest.json"),
        "source_object_readme": str(source_object / "README.md"),
        "source_object_manifest": str(source_object / "object_manifest.json"),
        "model_path": _touch(tmp_path / "models" / f"{object_key}.pdb", "ATOM\n"),
        "viewer_html": _touch(tmp_path / "viewers" / f"{object_key}.html"),
        "projection_svg": _touch(tmp_path / "renders" / f"{object_key}.svg"),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }
    if lane == "massivefold_freeze_candidate":
        row.update(
            {
                "model_sha256": "model-sha",
                "top5_manifest_csv": _touch(tmp_path / "top5" / f"{object_key}.csv"),
                "top5_manifest_sha256": "top5-sha",
                "escrow_md": _touch(tmp_path / "escrow" / f"{object_key}.md"),
            }
        )
    return row


def test_3d_molecular_object_atlas_completion_audit_passes_green_atlas(tmp_path: Path) -> None:
    atlas_json = tmp_path / "atlas.json"
    current = _atlas_object(tmp_path, "H2319_Audit_complex", "current_chain_A", "current_object_library")
    freeze = _atlas_object(
        tmp_path,
        "H2319_Audit_complex",
        "massivefold_model1_candidate",
        "massivefold_freeze_candidate",
    )
    _write_json(
        atlas_json,
        {
            "summary": {
                "casp17_3d_molecular_object_atlas_status": (
                    "casp17_3d_molecular_object_atlas_ready_review_only"
                ),
                "atlas_dir": str(tmp_path / "atlas"),
            },
            "protein_rows": [
                {
                    "atlas_protein_key": "H2319_Audit_complex",
                    "atlas_protein_folder": str(tmp_path / "atlas" / "H2319_Audit_complex"),
                    "atlas_protein_readme": str(tmp_path / "atlas" / "H2319_Audit_complex" / "README.md"),
                    "atlas_protein_manifest": str(
                        tmp_path / "atlas" / "H2319_Audit_complex" / "protein_manifest.json"
                    ),
                }
            ],
            "rows": [current, freeze],
        },
    )
    args = mod.parse_args(
        [
            "--atlas-json",
            str(atlas_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
            "--out-html",
            str(tmp_path / "audit.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["atlas_completion_audit_status"] == (
        "casp17_3d_molecular_object_atlas_completion_audit_pass"
    )
    assert summary["protein_count"] == 1
    assert summary["protein_folder_present_count"] == 1
    assert summary["object_pass_count"] == 2
    assert summary["object_blocked_count"] == 0
    assert summary["current_object_count"] == 1
    assert summary["massivefold_freeze_object_count"] == 1
    assert summary["atlas_object_folder_present_count"] == 2
    assert summary["atlas_object_readme_present_count"] == 2
    assert summary["atlas_object_manifest_present_count"] == 2
    assert summary["source_object_manifest_present_count"] == 2
    assert summary["model_link_present_count"] == 2
    assert summary["viewer_link_present_count"] == 2
    assert summary["projection_link_present_count"] == 2
    assert summary["top5_link_present_count"] == 1
    assert summary["escrow_link_present_count"] == 1
    assert summary["object_coordinate_copy_count"] == 0
    assert summary["atlas_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert {row["audit_status"] for row in payload["rows"]} == {"pass"}
    assert (tmp_path / "audit.json").is_file()
    assert (tmp_path / "AUDIT.md").is_file()
    assert "AUTHOR " not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_3d_molecular_object_atlas_completion_audit_blocks_missing_and_copied_coordinates(
    tmp_path: Path,
) -> None:
    atlas_json = tmp_path / "atlas.json"
    row = _atlas_object(tmp_path, "T9999_Blocked", "current_chain_A", "current_object_library")
    Path(row["viewer_html"]).unlink()
    _touch(Path(row["atlas_object_folder"]) / "copied_model.pdb", "ATOM copied\n")
    _write_json(
        atlas_json,
        {
            "summary": {
                "casp17_3d_molecular_object_atlas_status": (
                    "casp17_3d_molecular_object_atlas_ready_review_only"
                ),
                "atlas_dir": str(tmp_path / "atlas"),
            },
            "protein_rows": [],
            "rows": [row],
        },
    )
    args = mod.parse_args(["--atlas-json", str(atlas_json)])
    payload = mod.build_payload(args)

    assert payload["summary"]["atlas_completion_audit_status"] == (
        "casp17_3d_molecular_object_atlas_completion_audit_blocked"
    )
    assert payload["summary"]["object_blocked_count"] == 1
    assert payload["summary"]["object_coordinate_copy_count"] == 1
    assert payload["summary"]["atlas_coordinate_copy_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "viewer_html_missing" in blockers
    assert "atlas_coordinate_copy_present" in blockers
