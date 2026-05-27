from __future__ import annotations

import csv
from pathlib import Path

from tools import build_casp17_historical_identity_seed_inventory as mod


def _write_pdb(path: Path, chains: str = "A") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    atom_id = 1
    for chain in chains:
        lines.append(
            f"ATOM  {atom_id:5d}  CA  ALA {chain}{atom_id:4d}    "
            f"{float(atom_id):8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C\n"
        )
        atom_id += 1
    path.write_text("".join(lines), encoding="utf-8")


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


def test_historical_identity_seed_inventory_builds_batch_seed_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    native_dir = tmp_path / "data/native"
    prediction_root = tmp_path / "data/internal_structures_refined"
    complex_root = tmp_path / "runs/complexes"
    current_csv = tmp_path / "current.csv"
    _write_csv(current_csv, [{"target_id": "T9999", "protein_name": "unrelated", "folder_name": "unrelated"}])

    for slug in ("crambin", "gb1_mini"):
        _write_pdb(native_dir / f"{slug}.pdb")
        _write_pdb(
            prediction_root / "nightly/r1" / f"visual_post_internal_post_{slug}_sample000_step00020.pdb"
        )
    for name in ("01_tcruzi_pde_external_pdeb1_010_chembl1", "02_tcruzi_pde_external_pdeb1_011_chembl2"):
        _write_pdb(complex_root / name / "protein_ligand_complex.pdb", chains="AB")
        _write_pdb(complex_root / name / "protein_ligand_complex_minimized.pdb", chains="AB")

    args = mod.parse_args(
        [
            "--current-target-csv",
            str(current_csv),
            "--monomer-native-dir",
            str(native_dir),
            "--monomer-prediction-root",
            str(prediction_root),
            "--complex-root",
            str(complex_root),
            "--batch-monomer-count",
            "2",
            "--batch-complex-count",
            "1",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--out-manifest-csv",
            str(tmp_path / "manifest.csv"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["seed_inventory_status"] == "batch_seed_shape_ready_operator_clearance_required"
    assert payload["summary"]["monomer_seed_candidate_count"] == 2
    assert payload["summary"]["complex_seed_candidate_count"] == 2
    assert payload["summary"]["batch_seed_slot_count"] == 3
    assert payload["summary"]["candidate_manifest_row_count"] == 3
    assert all(row["current_casp17_target"] == "false" for row in payload["manifest_rows"])
    assert all(row["leakage_clearance"] == "" for row in payload["manifest_rows"])
    assert (tmp_path / "out.md").is_file()


def test_historical_identity_seed_inventory_blocks_current_name_collision(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    native_dir = tmp_path / "data/native"
    prediction_root = tmp_path / "data/internal_structures_refined"
    current_csv = tmp_path / "current.csv"
    _write_csv(current_csv, [{"target_id": "T0001", "protein_name": "crambin", "folder_name": "T0001_crambin"}])
    _write_pdb(native_dir / "crambin.pdb")
    _write_pdb(prediction_root / "nightly/r1/visual_post_internal_post_crambin_sample000_step00020.pdb")

    args = mod.parse_args(
        [
            "--current-target-csv",
            str(current_csv),
            "--monomer-native-dir",
            str(native_dir),
            "--monomer-prediction-root",
            str(prediction_root),
            "--complex-root",
            str(tmp_path / "missing_complexes"),
            "--batch-monomer-count",
            "1",
            "--batch-complex-count",
            "0",
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["seed_inventory_status"] == "insufficient_seed_shape"
    assert payload["summary"]["blocked_seed_source_count"] == 1
    assert payload["rows"][0]["seed_status"] == "blocked_seed_source"
    assert "current_casp17_target_collision" in payload["rows"][0]["blockers"]
