from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_eval_panel_repair_profile as mod


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fixture_profile(tmp_path: Path) -> tuple[dict, str]:
    reference = tmp_path / "config/reference_v1.csv"
    split = tmp_path / "config/split_v1.csv"
    meta = tmp_path / "config/meta_v1.csv"
    profile_path = tmp_path / "config/profile_v1.json"
    reference_rows = [
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "active1", "reference_binding_kcal_mol": "-8.0", "is_binder": "1", "source": "fixture"},
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "active2", "reference_binding_kcal_mol": "-7.0", "is_binder": "1", "source": "fixture"},
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "inactive1", "reference_binding_kcal_mol": "-0.2", "is_binder": "0", "source": "fixture"},
    ]
    split_rows = [
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "active1", "role": "eval"},
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "active2", "role": "eval"},
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "inactive1", "role": "eval"},
    ]
    meta_rows = [
        {"ligand_id": "active1", "smiles": "CCO", "molecular_weight": "46.0", "logp": "0.1", "h_donors": "1", "h_acceptors": "1", "rot_bonds": "0", "scaffold": "fixture"},
        {"ligand_id": "active2", "smiles": "CCN", "molecular_weight": "45.0", "logp": "0.2", "h_donors": "1", "h_acceptors": "1", "rot_bonds": "0", "scaffold": "fixture"},
        {"ligand_id": "inactive1", "smiles": "CCCl", "molecular_weight": "64.0", "logp": "1.0", "h_donors": "0", "h_acceptors": "0", "rot_bonds": "0", "scaffold": "fixture"},
    ]
    _write_csv(reference, reference_rows)
    _write_csv(split, split_rows)
    _write_csv(meta, meta_rows)
    profile = {
        "version": "profile_v1",
        "description": "fixture profile",
        "targets": "ADRB2_GPCR_BLIND",
        "ligand_csv": str(reference),
        "ranking_labels_csv": str(reference),
        "calibration_reference_csv": str(reference),
        "eval_split_csv": str(split),
        "leakage_ligand_meta_csv": str(meta),
        "hard_decoy_ligand_meta_csv": str(meta),
        "ranking_eval_roles": "eval",
        "gate": {"min_eval_unique_keys": 8, "ef1_min": 1.2},
    }
    profile_path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
    return profile, str(profile_path)


def test_product_eval_panel_repair_profile_materializes_negative_decoys(tmp_path: Path) -> None:
    profile, profile_path = _fixture_profile(tmp_path)
    payload = mod.build_product_eval_panel_repair_profile(
        base_profile=profile,
        repair_work_order={"summary": {"additional_eval_unique_keys_needed": 5}},
        base_profile_path=profile_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_eval_panel_repair_profile_ready"
    assert summary["current_eval_unique_keys"] == 3
    assert summary["added_negative_decoy_count"] == 5
    assert summary["repaired_eval_unique_keys"] == 8
    assert summary["repaired_eval_positive_keys"] == 2
    assert summary["repaired_eval_negative_keys"] == 6
    assert summary["operational_gate_feasible"] is True
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False

    reference_rows = list(csv.DictReader(open(summary["reference_csv"], encoding="utf-8")))
    split_rows = list(csv.DictReader(open(summary["eval_split_csv"], encoding="utf-8")))
    meta_rows = list(csv.DictReader(open(summary["ligand_meta_csv"], encoding="utf-8")))
    assert len(reference_rows) == 8
    assert len(split_rows) == 8
    assert len(meta_rows) == 8
    assert sum(1 for row in reference_rows if row["is_binder"] == "0") == 6

    repaired_profile = json.loads(Path(summary["profile_json"]).read_text(encoding="utf-8"))
    assert repaired_profile["ranking_labels_csv"] == summary["reference_csv"]
    assert repaired_profile["eval_split_csv"] == summary["eval_split_csv"]
    assert repaired_profile["leakage_ligand_meta_csv"] == summary["ligand_meta_csv"]
    assert repaired_profile["product_eval_panel_repair"]["synthetic_negative_decoy_count"] == 5


def test_product_eval_panel_repair_profile_tool_writes_report_outputs(tmp_path: Path) -> None:
    profile, profile_path = _fixture_profile(tmp_path)
    repair_json = tmp_path / "repair.json"
    out_json = tmp_path / "report.json"
    out_csv = tmp_path / "report.csv"
    out_md = tmp_path / "report.md"
    repair_json.write_text(json.dumps({"summary": {"additional_eval_unique_keys_needed": 5}}) + "\n", encoding="utf-8")

    mod.main(
        [
            "--base-profile-json",
            profile_path,
            "--repair-work-order-json",
            str(repair_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["added_negative_decoy_count"] == 5
    assert out_csv.read_text(encoding="utf-8").startswith("artifact_type,path,")
    assert "Product Eval Panel Repair Profile" in out_md.read_text(encoding="utf-8")
