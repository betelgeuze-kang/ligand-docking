import json
from pathlib import Path

from tools import build_casp17_3d_molecular_object_coordinate_materialization_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _audit_row(tmp_path: Path, protein_key: str, object_key: str, source_name: str, lane: str) -> dict:
    atlas_protein = tmp_path / "atlas" / protein_key
    atlas_object = atlas_protein / object_key
    _touch(atlas_protein / "README.md")
    _write_json(atlas_protein / "protein_manifest.json", {"summary": {"protein_key": protein_key}})
    _touch(atlas_object / "README.md")
    _write_json(atlas_object / "object_manifest.json", {"summary": {"object_key": object_key}})
    return {
        "atlas_protein_key": protein_key,
        "atlas_object_key": object_key,
        "source_lane": lane,
        "target_id": protein_key.split("_", 1)[0],
        "protein_name": "Materialization complex",
        "object_id": object_key,
        "audit_status": "pass",
        "atlas_protein_folder": str(atlas_protein),
        "atlas_protein_readme": str(atlas_protein / "README.md"),
        "atlas_protein_manifest": str(atlas_protein / "protein_manifest.json"),
        "atlas_object_folder": str(atlas_object),
        "atlas_object_readme": str(atlas_object / "README.md"),
        "atlas_object_manifest": str(atlas_object / "object_manifest.json"),
        "model_path": _touch(tmp_path / "models" / source_name, "ATOM\n"),
    }


def test_coordinate_materialization_plan_is_ready_for_green_atlas_audit(tmp_path: Path) -> None:
    audit_json = tmp_path / "atlas_completion_audit.json"
    row_a = _audit_row(
        tmp_path,
        "H2319_Materialization_complex",
        "current_chain_A",
        "H2319_chain_A.pdb",
        "current_object_library",
    )
    row_b = _audit_row(
        tmp_path,
        "H2321_Materialization_complex",
        "massivefold_model1_candidate",
        "H2321_model1.cif",
        "massivefold_freeze_candidate",
    )
    _write_json(
        audit_json,
        {
            "summary": {
                "atlas_completion_audit_status": "casp17_3d_molecular_object_atlas_completion_audit_pass"
            },
            "rows": [row_a, row_b],
        },
    )
    args = mod.parse_args(
        [
            "--atlas-completion-audit-json",
            str(audit_json),
            "--out-dir",
            str(tmp_path / "materialization"),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "PLAN.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["coordinate_materialization_plan_status"] == "coordinate_materialization_plan_ready_dry_run"
    assert summary["protein_count"] == 2
    assert summary["object_count"] == 2
    assert summary["ready_object_count"] == 2
    assert summary["blocked_object_count"] == 0
    assert summary["source_coordinate_present_count"] == 2
    assert summary["source_coordinate_missing_count"] == 0
    assert summary["pdb_source_count"] == 1
    assert summary["cif_source_count"] == 1
    assert summary["proposed_coordinate_copy_count"] == 2
    assert summary["existing_coordinate_copy_count"] == 0
    assert summary["coordinate_copy_policy"] == "dry_run_no_copy"
    assert {row["materialization_status"] for row in payload["rows"]} == {
        "coordinate_materialization_ready_dry_run"
    }
    assert all("coordinates/" in row["proposed_coordinate_copy_path"] for row in payload["rows"])
    assert (tmp_path / "plan.json").is_file()
    assert (tmp_path / "PLAN.md").is_file()
    assert (
        tmp_path
        / "materialization"
        / "H2319_Materialization_complex"
        / "MATERIALIZATION_PLAN.md"
    ).is_file()
    assert (
        tmp_path
        / "materialization"
        / "H2321_Materialization_complex"
        / "object_coordinate_rows.csv"
    ).is_file()


def test_coordinate_materialization_plan_blocks_missing_source_and_atlas_inputs(tmp_path: Path) -> None:
    audit_json = tmp_path / "atlas_completion_audit.json"
    row = _audit_row(
        tmp_path,
        "H9999_Blocked_complex",
        "current_chain_A",
        "H9999_chain_A.pdb",
        "current_object_library",
    )
    Path(row["model_path"]).unlink()
    Path(row["atlas_object_manifest"]).unlink()
    _write_json(
        audit_json,
        {
            "summary": {
                "atlas_completion_audit_status": "casp17_3d_molecular_object_atlas_completion_audit_blocked"
            },
            "rows": [row],
        },
    )
    args = mod.parse_args(["--atlas-completion-audit-json", str(audit_json)])
    payload = mod.build_payload(args)

    assert payload["summary"]["coordinate_materialization_plan_status"] == (
        "blocked_coordinate_materialization_inputs_missing"
    )
    assert payload["summary"]["blocked_object_count"] == 1
    assert payload["summary"]["source_coordinate_missing_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "source_coordinate_file_missing" in blockers
    assert "atlas_object_manifest_missing" in blockers


def test_coordinate_materialization_plan_blocks_missing_input_json(tmp_path: Path) -> None:
    args = mod.parse_args(["--atlas-completion-audit-json", str(tmp_path / "missing.json")])
    payload = mod.build_payload(args)

    assert payload["summary"]["coordinate_materialization_plan_status"] == (
        "blocked_coordinate_materialization_no_atlas_objects"
    )
    assert payload["summary"]["object_count"] == 0
