from __future__ import annotations

import csv
from pathlib import Path

from tools import native_target_registry as mod


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_find_matching_target_row_honors_target_aliases() -> None:
    rows = [
        {
            "target": "Cathepsin K",
            "target_aliases": "CTSK;human cathepsin k",
            "native_pdb_path": "catk.pdb",
        }
    ]

    selected = mod.find_matching_target_row(rows, "ctsk")

    assert selected["target"] == "Cathepsin K"
    assert selected["native_pdb_path"] == "catk.pdb"


def test_load_repo_native_registry_prefers_ready_alias_matched_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "config"
    ready_native = tmp_path / "structures" / "tcruzi_native.pdb"
    ready_native.parent.mkdir(parents=True, exist_ok=True)
    ready_native.write_text(
        "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    _write_csv(
        config_dir / "real_drug_targets_native_v1.csv",
        [
            {
                "target": "T. cruzi PDE",
                "target_aliases": "t_cruzi_pde;TcrPDEC",
                "native_pdb_path": "missing/native.pdb",
                "pdb_id": "MISS",
                "notes": "missing candidate",
                "pocket_x": "1.0",
                "pocket_y": "2.0",
                "pocket_z": "3.0",
            },
            {
                "target": "T. cruzi PDE",
                "target_aliases": "Trypanosoma cruzi PDE",
                "native_pdb_path": str(ready_native.relative_to(tmp_path)),
                "pdb_id": "READY",
                "notes": "ready candidate",
                "pocket_x": "4.0",
                "pocket_y": "5.0",
                "pocket_z": "6.0",
            },
        ],
    )

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    mod.load_repo_native_registry.cache_clear()
    try:
        entry = mod.resolve_repo_native_entry("tcruzi_pde")
    finally:
        mod.load_repo_native_registry.cache_clear()

    assert entry["target"] == "T. cruzi PDE"
    assert entry["canonical_target"] == "T. cruzi PDE"
    assert entry["native_pdb_ready"] is True
    assert entry["native_pdb_path"] == str(ready_native)
    assert entry["pdb_id"] == "READY"
    assert entry["target_aliases"] == ["Trypanosoma cruzi PDE"]
    assert entry["pocket_x"] == "4.0"
    assert entry["pocket_y"] == "5.0"
    assert entry["pocket_z"] == "6.0"
