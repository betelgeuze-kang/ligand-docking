from pathlib import Path

import pandas as pd

from tools import audit_ligand_leakage as mod


def test_leakage_audit_pass_no_overlap(tmp_path: Path):
    split = pd.DataFrame(
        [
            {"target": "Tfit", "ligand_id": "A", "role": "fit"},
            {"target": "Tfit", "ligand_id": "B", "role": "fit"},
            {"target": "Tfar", "ligand_id": "C", "role": "far_ood_eval"},
            {"target": "Tfar", "ligand_id": "D", "role": "far_ood_eval"},
        ]
    )
    tmeta = pd.DataFrame(
        [
            {"target": "Tfit", "target_family": "F1", "sequence": "AAAA", "pocket_fingerprint": "p1|p2"},
            {"target": "Tfar", "target_family": "F2", "sequence": "BBBB", "pocket_fingerprint": "q1|q2"},
        ]
    )
    lmeta = pd.DataFrame(
        [
            {"ligand_id": "A", "smiles": "CC", "scaffold": "s1"},
            {"ligand_id": "B", "smiles": "CCC", "scaffold": "s2"},
            {"ligand_id": "C", "smiles": "O", "scaffold": "s3"},
            {"ligand_id": "D", "smiles": "N", "scaffold": "s4"},
        ]
    )

    split_csv = tmp_path / "split.csv"
    tmeta_csv = tmp_path / "tmeta.csv"
    lmeta_csv = tmp_path / "lmeta.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    split.to_csv(split_csv, index=False)
    tmeta.to_csv(tmeta_csv, index=False)
    lmeta.to_csv(lmeta_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--split-csv",
            str(split_csv),
            "--fit-roles",
            "fit",
            "--eval-roles",
            "far_ood_eval",
            "--target-meta-csv",
            str(tmeta_csv),
            "--ligand-meta-csv",
            str(lmeta_csv),
            "--max-key-overlap",
            "0",
            "--max-target-overlap",
            "0",
            "--max-family-overlap-ratio",
            "0.0",
            "--max-scaffold-overlap-ratio",
            "0.0",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )
    payload = mod.run_audit(args)
    assert bool(payload["pass"]) is True
    assert int(payload["key_overlap_count"]) == 0


def test_leakage_audit_fail_key_overlap(tmp_path: Path):
    split = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "role": "fit"},
            {"target": "T", "ligand_id": "A", "role": "eval"},
        ]
    )
    split_csv = tmp_path / "split.csv"
    split.to_csv(split_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--split-csv",
            str(split_csv),
            "--fit-roles",
            "fit",
            "--eval-roles",
            "eval",
            "--max-key-overlap",
            "0",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
        ]
    )
    payload = mod.run_audit(args)
    assert bool(payload["pass"]) is False
    assert int(payload["key_overlap_count"]) == 1
