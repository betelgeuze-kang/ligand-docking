import json
from pathlib import Path

from tools.casp17 import build_casp17_3d_molecular_object_coordinate_materialized_library as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _plan_row(tmp_path: Path, protein: str, obj: str, source: str) -> dict:
    return {
        "atlas_protein_key": protein,
        "atlas_object_key": obj,
        "source_lane": "current_object_library",
        "target_id": protein.split("_", 1)[0],
        "protein_name": protein.split("_", 1)[-1],
        "object_id": obj,
        "materialization_status": mod.READY_PLAN_STATUS,
        "source_coordinate_path": source,
        "source_coordinate_format": Path(source).suffix.lstrip("."),
        "source_coordinate_present": "true",
        "proposed_coordinate_copy_path": str(tmp_path / "atlas" / protein / obj / "coordinates" / Path(source).name),
    }


def test_coordinate_materialized_library_symlinks_and_verifies_rows(tmp_path: Path) -> None:
    plan_json = tmp_path / "plan.json"
    source_a = _source(tmp_path / "sources" / "chain_A.pdb", "ATOM A\n")
    source_b = _source(tmp_path / "sources" / "chain_B.cif", "data_B\n")
    _write_json(
        plan_json,
        {
            "summary": {
                "coordinate_materialization_plan_status": "coordinate_materialization_plan_ready_dry_run",
            },
            "rows": [
                _plan_row(tmp_path, "H9001_Test_complex", "current_chain_A", source_a),
                _plan_row(tmp_path, "H9001_Test_complex", "current_chain_B", source_b),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--coordinate-materialization-plan-json",
            str(plan_json),
            "--out-dir",
            str(tmp_path / "materialized"),
            "--out-json",
            str(tmp_path / "library.json"),
            "--out-csv",
            str(tmp_path / "library.csv"),
            "--out-md",
            str(tmp_path / "LIBRARY.md"),
            "--mode",
            "symlink",
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["coordinate_materialized_library_status"] == (
        "casp17_3d_molecular_object_coordinate_materialized_library_pass"
    )
    assert summary["protein_count"] == 1
    assert summary["object_count"] == 2
    assert summary["object_materialized_count"] == 2
    assert summary["source_present_count"] == 2
    assert summary["materialized_present_count"] == 2
    assert summary["sha256_match_count"] == 2
    assert summary["symlink_count"] == 2
    assert summary["copy_count"] == 0
    assert summary["protein_folder_count"] == 1
    assert summary["object_folder_count"] == 2
    assert summary["coordinate_folder_count"] == 2
    assert {row["materialization_status"] for row in payload["rows"]} == {"coordinate_materialized"}
    assert all(Path(row["materialized_coordinate_path"]).is_symlink() for row in payload["rows"])
    assert all(row["sha256_match"] == "true" for row in payload["rows"])
    assert (tmp_path / "library.json").is_file()
    assert (tmp_path / "LIBRARY.md").is_file()
    assert (tmp_path / "materialized" / ".gitignore").read_text(encoding="utf-8") == (
        "# CASP17 materialized coordinate files are local review artifacts.\n"
        "**/coordinates/*.pdb\n"
        "**/coordinates/*.cif\n"
    )
    assert (tmp_path / "materialized" / "H9001_Test_complex" / "protein_coordinate_manifest.json").is_file()


def test_coordinate_materialized_library_blocks_destination_conflict(tmp_path: Path) -> None:
    plan_json = tmp_path / "plan.json"
    source = _source(tmp_path / "sources" / "chain_A.pdb", "ATOM source\n")
    row = _plan_row(tmp_path, "H9002_Test_complex", "current_chain_A", source)
    dest = tmp_path / "materialized" / "H9002_Test_complex" / "current_chain_A" / "coordinates" / "chain_A.pdb"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("ATOM conflict\n", encoding="utf-8")
    _write_json(
        plan_json,
        {
            "summary": {
                "coordinate_materialization_plan_status": "coordinate_materialization_plan_ready_dry_run",
            },
            "rows": [row],
        },
    )
    args = mod.parse_args(
        [
            "--coordinate-materialization-plan-json",
            str(plan_json),
            "--out-dir",
            str(tmp_path / "materialized"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["coordinate_materialized_library_status"] == (
        "casp17_3d_molecular_object_coordinate_materialized_library_blocked"
    )
    assert payload["summary"]["object_blocked_count"] == 1
    assert "materialized_coordinate_conflict" in payload["rows"][0]["blockers"]
    assert "materialized_sha256_mismatch" in payload["rows"][0]["blockers"]
