from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def test_materialize_curated_family_packets_only_writes_ready_rows(tmp_path: Path) -> None:
    workbook_csv = tmp_path / "workbook.csv"
    out_json = tmp_path / "materialized.json"
    out_csv = tmp_path / "materialized.csv"
    out_md = tmp_path / "materialized.md"
    core_reference_csv = tmp_path / "core_reference.csv"
    core_eval_split_csv = tmp_path / "core_eval_split.csv"
    core_ligand_meta_csv = tmp_path / "core_meta.csv"
    ood_reference_csv = tmp_path / "ood_reference.csv"
    ood_eval_split_csv = tmp_path / "ood_eval_split.csv"
    ood_ligand_meta_csv = tmp_path / "ood_meta.csv"

    _write_csv(
        workbook_csv,
        [
            {
                "packet": "core",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "replacement_reference_binding_kcal_mol": "-10.8",
                "replacement_is_binder": "1",
                "replacement_source": "chembl_direct_binding::example",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "CC",
                "replacement_molecular_weight": "100.0",
                "replacement_logp": "1.2",
                "replacement_h_donors": "1",
                "replacement_h_acceptors": "2",
                "replacement_rot_bonds": "0",
                "replacement_scaffold": "alkyl",
                "row_ready_for_apply": "yes",
                "required_missing_fields": "",
            },
            {
                "packet": "ood",
                "packet_step": "ood_non_binder_01",
                "replacement_ligand_id": "aspirin",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_is_binder": "0",
                "replacement_source": "pending_source",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "CCC",
                "replacement_molecular_weight": "180.0",
                "replacement_logp": "1.3",
                "replacement_h_donors": "1",
                "replacement_h_acceptors": "3",
                "replacement_rot_bonds": "2",
                "replacement_scaffold": "aryl",
                "row_ready_for_apply": "no",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
            },
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/materialize_curated_family_packets.py"),
            "--family",
            "ca2",
            "--workbook-csv",
            str(workbook_csv),
            "--core-reference-csv",
            str(core_reference_csv),
            "--core-eval-split-csv",
            str(core_eval_split_csv),
            "--core-ligand-meta-csv",
            str(core_ligand_meta_csv),
            "--ood-reference-csv",
            str(ood_reference_csv),
            "--ood-eval-split-csv",
            str(ood_eval_split_csv),
            "--ood-ligand-meta-csv",
            str(ood_ligand_meta_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["materialized_row_count"] == 1
    assert payload["summary"]["unresolved_row_count"] == 1

    core_ref_rows = _read_csv(core_reference_csv)
    assert core_ref_rows == [
        {
            "target": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
            "ligand_id": "acetazolamide",
            "reference_binding_kcal_mol": "-10.8",
            "is_binder": "1",
            "source": "chembl_direct_binding::example",
        }
    ]
    ood_ref_rows = _read_csv(ood_reference_csv)
    assert ood_ref_rows == []
