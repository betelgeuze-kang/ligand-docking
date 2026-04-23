from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_pxr_ligand_packet_fill_workbook(tmp_path: Path) -> None:
    config = tmp_path / "config"
    runs = tmp_path / "runs"

    _write_csv(
        config / "ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["PXR_NR1I2_BLIND", "pxr_fit_ligand_01", "TODO_BINDING_KCAL", "1", "pxr_blind_proxy_v1"],
            ["PXR_NR1I2_BLIND", "pxr_decoy_ligand_01", "TODO_BINDING_KCAL", "0", "pxr_blind_proxy_v1"],
        ],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        ["target", "ligand_id", "role"],
        [
            ["PXR_NR1I2_BLIND", "pxr_fit_ligand_01", "fit"],
            ["PXR_NR1I2_BLIND", "pxr_decoy_ligand_01", "far_ood_eval"],
        ],
    )
    _write_csv(
        config / "ligand_meta_blind_pxr_nr1i2_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["pxr_fit_ligand_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"],
            ["pxr_decoy_ligand_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"],
        ],
    )
    _write_csv(
        config / "ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"],
        [
            ["PXR_NR1I2_BLIND", "pxr_ood_ligand_01", "TODO_BINDING_KCAL", "1", "pxr_ood_proxy_v1"],
            ["PXR_NR1I2_BLIND", "pxr_ood_decoy_01", "TODO_BINDING_KCAL", "0", "pxr_ood_proxy_v1"],
        ],
    )
    _write_csv(
        config / "ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        ["target", "ligand_id", "role"],
        [
            ["PXR_NR1I2_BLIND", "pxr_ood_ligand_01", "far_ood_eval"],
            ["PXR_NR1I2_BLIND", "pxr_ood_decoy_01", "far_ood_eval"],
        ],
    )
    _write_csv(
        config / "ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"],
        [
            ["pxr_ood_ligand_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"],
            ["pxr_ood_decoy_01", "TODO_SMILES", "0.0", "0.0", "0", "0", "0", "TODO_SCAFFOLD"],
        ],
    )
    _write_json(
        config / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
        {
            "placeholder_policies": {
                "fit_donor_target": "EGFR_KINASE",
                "fit_donor_policy_state": "frozen_external_donor_egfr_until_pxr_family_fit_packet_exists",
            }
        },
    )

    out_json = runs / "pxr_ligand_packet_fill_workbook_current.json"
    out_csv = runs / "pxr_ligand_packet_fill_workbook_current.csv"
    out_md = runs / "pxr_ligand_packet_fill_workbook_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_pxr_ligand_packet_fill_workbook.py"),
            "--template-json",
            "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["target"] == "PXR_NR1I2_BLIND"
    assert payload["summary"]["packet_count"] == 2
    assert payload["summary"]["ligand_row_count"] == 4
    assert payload["summary"]["packets_blocked"] == 2
    assert payload["summary"]["placeholder_row_count"] == 4

    packet_status = {row["packet"]: row["status"] for row in payload["packet_summaries"]}
    assert packet_status["core"] == "placeholder_only"
    assert packet_status["ood"] == "placeholder_only"

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 4
    assert any(row["packet"] == "core" for row in rows)
    assert any(row["packet"] == "ood" for row in rows)
    assert all(row["reference_placeholder"] == "yes" for row in rows)
    assert all(row["meta_placeholder"] == "yes" for row in rows)

    md_text = out_md.read_text(encoding="utf-8")
    _contains_tokens(md_text, "pxr", "ligand", "packet", "fill", "workbook")
    _contains_tokens(md_text, "curate", "ligand", "ledger")
    _contains_tokens(md_text, "replace", "core", "placeholder", "reference", "curated", "pxr", "evidence")
