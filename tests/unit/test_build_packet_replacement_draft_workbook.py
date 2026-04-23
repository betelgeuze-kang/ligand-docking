from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_ca2_packet_replacement_draft_workbook(tmp_path: Path) -> None:
    workbook_csv = tmp_path / "runs" / "ca2_packet_replacement_workbook_current.csv"
    prefill_csv = tmp_path / "runs" / "ca2_packet_replacement_prefill_current.csv"
    _write_csv(
        workbook_csv,
        [
            "packet","packet_step","target","current_ligand_id","replacement_ligand_id","replacement_reference_binding_kcal_mol",
            "replacement_is_binder","replacement_source","replacement_role","replacement_smiles","replacement_molecular_weight",
            "replacement_logp","replacement_h_donors","replacement_h_acceptors","replacement_rot_bonds","replacement_scaffold",
            "apply_reference_row","apply_split_row","apply_meta_row","row_ready_for_apply","required_missing_fields","notes",
        ],
        [{
            "packet":"core","packet_step":"core_binder_01","target":"CA2","current_ligand_id":"x1","replacement_ligand_id":"",
            "replacement_reference_binding_kcal_mol":"","replacement_is_binder":"1","replacement_source":"","replacement_role":"far_ood_eval",
            "replacement_smiles":"","replacement_molecular_weight":"","replacement_logp":"","replacement_h_donors":"","replacement_h_acceptors":"",
            "replacement_rot_bonds":"","replacement_scaffold":"","apply_reference_row":"yes","apply_split_row":"yes","apply_meta_row":"yes",
            "row_ready_for_apply":"no","required_missing_fields":"replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_source,replacement_smiles,replacement_scaffold","notes":"seed",
        }],
    )
    _write_csv(
        prefill_csv,
        [
            "packet_step","candidate_ligand_name","candidate_source_kind","candidate_reference_hint","candidate_anchor_pdb_id",
            "candidate_anchor_native_path","candidate_manual_verification_required",
        ],
        [{
            "packet_step":"core_binder_01","candidate_ligand_name":"acetazolamide","candidate_source_kind":"known_ca2_inhibitor_seed",
            "candidate_reference_hint":"hint","candidate_anchor_pdb_id":"1CA2","candidate_anchor_native_path":"pdb","candidate_manual_verification_required":"yes",
        }],
    )
    out_json = tmp_path / "runs" / "ca2_packet_replacement_draft_current.json"
    out_csv = tmp_path / "runs" / "ca2_packet_replacement_draft_current.csv"
    out_md = tmp_path / "runs" / "ca2_packet_replacement_draft_current.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_packet_replacement_draft_workbook.py"),
            "--family","ca2",
            "--workbook-csv",str(workbook_csv),
            "--prefill-csv",str(prefill_csv),
            "--out-json",str(out_json),
            "--out-csv",str(out_csv),
            "--out-md",str(out_md),
        ],
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["draft_prefill_applied_count"] == 1
    row = payload["draft_rows"][0]
    assert row["replacement_ligand_id"] == ""
    assert row["replacement_source"] == ""
    assert row["draft_replacement_ligand_id"] == "acetazolamide"
    assert row["draft_replacement_source"] == "draft_seed::known_ca2_inhibitor_seed"
    assert row["row_ready_for_apply"] == "no"
    assert row["draft_claim_ready"] == "no"
    assert row["draft_authoritative_apply_approved"] == "no"
    assert "replacement_reference_binding_kcal_mol" in row["draft_missing_claim_fields"]


def test_build_pxr_packet_replacement_draft_workbook(tmp_path: Path) -> None:
    workbook_csv = tmp_path / "runs" / "pxr_packet_replacement_workbook_current.csv"
    prefill_csv = tmp_path / "runs" / "pxr_packet_replacement_prefill_current.csv"
    _write_csv(
        workbook_csv,
        [
            "packet","packet_step","target","current_ligand_id","current_binder_label","current_role","current_reference_binding_kcal_mol","current_source",
            "current_smiles","current_scaffold","placeholder_sources","replacement_ligand_id","replacement_reference_binding_kcal_mol","replacement_is_binder",
            "replacement_source","replacement_role","replacement_smiles","replacement_molecular_weight","replacement_logp","replacement_h_donors",
            "replacement_h_acceptors","replacement_rot_bonds","replacement_scaffold","apply_reference_row","apply_split_row","apply_meta_row",
            "row_ready_for_apply","notes","required_missing_fields",
        ],
        [{
            "packet":"core","packet_step":"core_eval_non_binder_02","target":"PXR","current_ligand_id":"pxr02","current_binder_label":"non_binder",
            "current_role":"far_ood_eval","current_reference_binding_kcal_mol":"","current_source":"seed","current_smiles":"","current_scaffold":"",
            "placeholder_sources":"reference,meta","replacement_ligand_id":"","replacement_reference_binding_kcal_mol":"","replacement_is_binder":"0",
            "replacement_source":"","replacement_role":"far_ood_eval","replacement_smiles":"","replacement_molecular_weight":"","replacement_logp":"",
            "replacement_h_donors":"","replacement_h_acceptors":"","replacement_rot_bonds":"","replacement_scaffold":"","apply_reference_row":"yes",
            "apply_split_row":"yes","apply_meta_row":"yes","row_ready_for_apply":"no","notes":"seed","required_missing_fields":"replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_source,replacement_smiles,replacement_scaffold",
        }],
    )
    _write_csv(
        prefill_csv,
        [
            "packet_step","candidate_ligand_name","candidate_source_kind","candidate_reference_hint","candidate_anchor_pdb_id",
            "candidate_anchor_native_path","candidate_manual_verification_required",
        ],
        [{
            "packet_step":"core_eval_non_binder_02","candidate_ligand_name":"caffeine","candidate_source_kind":"template_negative_seed",
            "candidate_reference_hint":"hint","candidate_anchor_pdb_id":"O75469","candidate_anchor_native_path":"native.pdb","candidate_manual_verification_required":"yes",
        }],
    )
    out_json = tmp_path / "runs" / "pxr_packet_replacement_draft_current.json"
    out_csv = tmp_path / "runs" / "pxr_packet_replacement_draft_current.csv"
    out_md = tmp_path / "runs" / "pxr_packet_replacement_draft_current.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_packet_replacement_draft_workbook.py"),
            "--family","pxr",
            "--workbook-csv",str(workbook_csv),
            "--prefill-csv",str(prefill_csv),
            "--out-json",str(out_json),
            "--out-csv",str(out_csv),
            "--out-md",str(out_md),
        ],
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    row = payload["draft_rows"][0]
    assert row["replacement_ligand_id"] == ""
    assert row["replacement_source"] == ""
    assert row["draft_replacement_ligand_id"] == "caffeine"
    assert row["draft_replacement_source"] == "draft_seed::template_negative_seed"
    assert row["draft_manual_verification_required"] == "yes"
    assert row["draft_claim_scope"] == "nonbinder_needs_manual_call"
    assert row["row_ready_for_apply"] == "no"
