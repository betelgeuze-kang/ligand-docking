from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_raw_ranked_model_quarantine_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _raw_pdb(*, author: bool = False, atom_count: int = 2) -> str:
    lines = []
    if author:
        lines.append("AUTHOR    INTERNAL TEST AUTHOR")
    lines.append("MODEL        1")
    for index in range(1, atom_count + 1):
        lines.append(
            f"ATOM  {index:5d}  CA  ALA A{index:4d}    "
            f"{float(index):8.3f}{1.0:8.3f}{2.0:8.3f}  1.00 70.00           C  "
        )
    lines.append("TER")
    return "\n".join(lines) + "\n"


def test_raw_ranked_model_quarantine_audit_links_top5_without_copying_raw_pdb(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    target_folder = tmp_path / "casp17/targets_current/H2001_Test_complex"
    raw_dir = target_folder / "metadata/internal_physics_job/ranked_raw_models"
    for rank in range(1, 6):
        (raw_dir / f"H2001_model_{rank}.pdb").parent.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"H2001_model_{rank}.pdb").write_text(
            _raw_pdb(author=(rank == 1), atom_count=rank),
            encoding="utf-8",
        )
    _write_json(
        tmp_path / "target_folders.json",
        {
            "object_rows": [
                {
                    "target_id": "H2001",
                    "protein_name": "Test complex",
                    "target_folder": "casp17/targets_current/H2001_Test_complex",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "protein_object_library.json",
        {
            "rows": [
                {
                    "target_id": "H2001",
                    "protein_name": "Test complex",
                    "library_protein_folder": "casp17/protein_object_library_current/H2001_Test_complex",
                },
                {
                    "target_id": "H2001",
                    "protein_name": "Test complex",
                    "library_protein_folder": "casp17/protein_object_library_current/H2001_Test_complex",
                },
            ]
        },
    )
    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(tmp_path / "target_folders.json"),
            "--protein-object-library-json",
            str(tmp_path / "protein_object_library.json"),
            "--raw-glob",
            "casp17/targets_current/*/metadata/internal_physics_job/ranked_raw_models/*_model_*.pdb",
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["raw_ranked_model_quarantine_status"] == "pass"
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["raw_ranked_model_count"] == 5
    assert payload["summary"]["complete_top5_target_count"] == 1
    assert payload["summary"]["linked_object_library_count"] == 5
    assert payload["summary"]["author_record_present_count"] == 1
    assert payload["rows"][0]["quarantine_status"] == "quarantined_do_not_commit_raw_pdb"
    assert "author_record_present_do_not_commit_raw_pdb" in payload["rows"][0]["blockers"]
    assert _read_csv(tmp_path / "audit.csv")[0]["target_id"] == "H2001"
    assert (tmp_path / "AUDIT.md").is_file()


def test_raw_ranked_model_quarantine_audit_blocks_missing_object_library(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    raw = tmp_path / "casp17/targets_current/H2002_Test/metadata/internal_physics_job/ranked_raw_models/H2002_model_1.pdb"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(_raw_pdb(), encoding="utf-8")
    _write_json(
        tmp_path / "target_folders.json",
        {
            "object_rows": [
                {
                    "target_id": "H2002",
                    "protein_name": "Test",
                    "target_folder": "casp17/targets_current/H2002_Test",
                }
            ]
        },
    )
    _write_json(tmp_path / "protein_object_library.json", {"rows": []})
    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(tmp_path / "target_folders.json"),
            "--protein-object-library-json",
            str(tmp_path / "protein_object_library.json"),
            "--raw-glob",
            "casp17/targets_current/*/metadata/internal_physics_job/ranked_raw_models/*_model_*.pdb",
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["raw_ranked_model_quarantine_status"] == "blocked"
    assert payload["summary"]["linked_object_library_count"] == 0
    assert "protein_object_library_missing" in payload["rows"][0]["blockers"]
