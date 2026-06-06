from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tools.product.build_lit_pcba_product_smoke_inputs import build_inputs


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_lit_pcba_product_smoke_inputs_keeps_binders_first(tmp_path: Path) -> None:
    lit_dir = tmp_path / "lit"
    target_dir = lit_dir / "Gold" / "ADRB2"
    target_dir.mkdir(parents=True)
    (target_dir / "ligands_T_std.smi").write_text("CC active1\nCCC decoy1\nCCCC decoy2\n", encoding="utf-8")
    (target_dir / "ligands_V_std.smi").write_text("CCO active2\n", encoding="utf-8")
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "target,ligand_id,is_binder\nADRB2,decoy1,0\nADRB2,active1,1\nADRB2,active2,1\nADRB2,decoy2,0\n",
        encoding="utf-8",
    )
    native = tmp_path / "native.csv"
    native.write_text(
        "target,native_pdb_path,pdb_id,pocket_x,pocket_y,pocket_z,notes\nADRB2_GPCR_BLIND,data/native/adrb2_gpcr_blind.pdb,2RH1,1,2,3,ok\n",
        encoding="utf-8",
    )

    out_json = tmp_path / "inputs.json"
    build_inputs(
        argparse.Namespace(
            target="ADRB2",
            role="eval",
            max_ligands=3,
            min_binders=2,
            lit_pcba_dir=str(lit_dir),
            labels_csv=str(labels),
            source_target_native_csv=str(native),
            source_native_target="ADRB2_GPCR_BLIND",
            out_ligand_csv=str(tmp_path / "ligands.csv"),
            out_labels_csv=str(tmp_path / "out_labels.csv"),
            out_split_csv=str(tmp_path / "split.csv"),
            out_target_native_csv=str(tmp_path / "target_native.csv"),
            out_json=str(out_json),
            out_md=str(tmp_path / "inputs.md"),
        )
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "lit_pcba_product_smoke_inputs_ready"
    assert summary["selected_rows"] == 3
    assert summary["selected_binders"] == 2
    ligand_rows = _rows(tmp_path / "ligands.csv")
    assert [row["is_binder"] for row in ligand_rows[:2]] == ["1", "1"]
    assert _rows(tmp_path / "target_native.csv")[0]["target"] == "ADRB2"
