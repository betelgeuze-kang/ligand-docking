from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tools.product.build_dude_z_product_smoke_inputs import build_inputs


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, *, native_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        target="AA2AR",
        dataset_dir=str(tmp_path / "dude"),
        native_pdb_path=str(native_path),
        pdb_id="3EML",
        pocket_x="1.0",
        pocket_y="2.0",
        pocket_z="3.0",
        role="eval",
        max_actives=1,
        max_decoys=2,
        min_ligands=2,
        out_ligand_csv=str(tmp_path / "ligands.csv"),
        out_labels_csv=str(tmp_path / "labels.csv"),
        out_split_csv=str(tmp_path / "split.csv"),
        out_target_native_csv=str(tmp_path / "native.csv"),
        out_json=str(tmp_path / "inputs.json"),
        out_md=str(tmp_path / "inputs.md"),
    )


def test_build_dude_z_product_smoke_inputs_blocks_without_native(tmp_path: Path) -> None:
    target_dir = tmp_path / "dude" / "AA2AR"
    target_dir.mkdir(parents=True)
    (target_dir / "ligands.smi").write_text("CC active1\n", encoding="utf-8")
    (target_dir / "decoys.smi").write_text("CCC decoy1\nCCCC decoy2\n", encoding="utf-8")

    payload = build_inputs(_args(tmp_path, native_path=tmp_path / "missing.pdb"))

    assert payload["summary"]["status"] == "blocked_dude_z_product_smoke_inputs"
    assert "native_pdb_path_missing" in payload["summary"]["blockers"]
    assert payload["summary"]["approval_token_required"] == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    assert len(_rows(tmp_path / "ligands.csv")) == 3


def test_build_dude_z_product_smoke_inputs_ready_with_native(tmp_path: Path) -> None:
    target_dir = tmp_path / "dude" / "AA2AR"
    target_dir.mkdir(parents=True)
    (target_dir / "ligands.smi").write_text("CC active1\n", encoding="utf-8")
    (target_dir / "decoys.smi").write_text("CCC decoy1\n", encoding="utf-8")
    native = tmp_path / "aa2ar.pdb"
    native.write_text("ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n", encoding="utf-8")

    payload = build_inputs(_args(tmp_path, native_path=native))

    assert payload["summary"]["status"] == "dude_z_product_smoke_inputs_ready"
    assert payload["summary"]["native_pdb_path_present"] is True
    assert json.loads((tmp_path / "inputs.json").read_text(encoding="utf-8"))["summary"]["selected_rows"] == 2
    assert _rows(tmp_path / "native.csv")[0]["pdb_id"] == "3EML"
