from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_native_dropzone_registry as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--primary-workorder-json",
        str(tmp_path / "primary.json"),
        "--replacement-workorder-json",
        str(tmp_path / "replacement.json"),
        "--out-json",
        str(tmp_path / "registry.json"),
        "--out-csv",
        str(tmp_path / "registry.csv"),
        "--out-md",
        str(tmp_path / "REGISTRY.md"),
    ]


def test_native_dropzone_registry_merges_primary_and_selected_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    primary_native = tmp_path / "workorders/H1001/native"
    replacement_native = tmp_path / "replacement/H1001_to_H2001/native"
    primary_native.mkdir(parents=True)
    replacement_native.mkdir(parents=True)
    (primary_native / "README.md").write_text("# H1001 native dropzone\n", encoding="utf-8")
    (replacement_native / "README.md").write_text("# H2001 native dropzone\n", encoding="utf-8")
    (replacement_native / "unexpected.cif").write_text("data_unexpected\n", encoding="utf-8")
    _write_json(
        tmp_path / "primary.json",
        {
            "rows": [
                {
                    "target_id": "H1001",
                    "target_name": "Example primary",
                    "workorder_status": "native_required",
                    "workorder_folder": "workorders/H1001",
                    "native_dropzone_folder": "workorders/H1001/native",
                    "native_dropzone_pdb": "workorders/H1001/native/H1001_native.pdb",
                    "native_dropzone_readme": "workorders/H1001/native/README.md",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "replacement.json",
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "target_id": "H2001",
                    "target_name": "Example replacement",
                    "selection_status": "selected_for_replacement_workorder",
                    "workorder_status": "native_and_provenance_required",
                    "workorder_folder": "replacement/H1001_to_H2001",
                    "native_dropzone_folder": "replacement/H1001_to_H2001/native",
                    "native_dropzone_pdb": "replacement/H1001_to_H2001/native/H2001_native.pdb",
                    "native_dropzone_readme": "replacement/H1001_to_H2001/native/README.md",
                },
                {
                    "replace_target_id": "H1002",
                    "target_id": "H2001",
                    "selection_status": "blocked_duplicate_candidate_assignment",
                    "native_dropzone_folder": "replacement/blocked/native",
                },
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["native_dropzone_registry_status"] == "awaiting_native_files"
    assert payload["summary"]["dropzone_count"] == 2
    assert payload["summary"]["primary_dropzone_count"] == 1
    assert payload["summary"]["replacement_dropzone_count"] == 1
    assert payload["summary"]["dropzone_readme_count"] == 2
    assert payload["summary"]["native_present_count"] == 0
    assert payload["summary"]["blocked_dropzone_count"] == 2
    assert payload["summary"]["unexpected_coordinate_count"] == 1
    assert payload["summary"]["proof_eligible_count"] == 0
    assert payload["summary"]["author_serialized_count"] == 0
    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert by_id["H1001"]["readme_status"] == "present"
    assert by_id["H1001"]["native_file_status"] == "missing"
    assert by_id["H2001"]["unexpected_coordinate_count"] == 1
    assert "unexpected_coordinate_copy_present" in by_id["H2001"]["blockers"]
    assert "does not fetch native structures" in payload["summary"]["claim_boundary"]
    assert (tmp_path / "registry.json").is_file()
    assert (tmp_path / "registry.csv").is_file()
    assert (tmp_path / "REGISTRY.md").is_file()


def test_native_dropzone_registry_reports_missing_workorders(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(tmp_path / "primary.json", {"rows": []})
    _write_json(tmp_path / "replacement.json", {"rows": []})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["native_dropzone_registry_status"] == "missing_workorder_dropzones"
    assert payload["summary"]["dropzone_count"] == 0
    assert payload["rows"] == []
