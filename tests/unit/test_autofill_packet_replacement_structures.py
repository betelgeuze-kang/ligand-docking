from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "autofill_packet_replacement_structures.py"
SPEC = importlib.util.spec_from_file_location("autofill_packet_replacement_structures", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_payload_ca2_autofills_structure_fields() -> None:
    workbook_rows = [
        {
            "packet": "core",
            "packet_step": "core_binder_01",
            "target": "CA2",
            "current_ligand_id": "placeholder",
            "replacement_ligand_id": "",
            "replacement_reference_binding_kcal_mol": "",
            "replacement_is_binder": "1",
            "replacement_source": "",
            "replacement_role": "far_ood_eval",
            "replacement_smiles": "",
            "replacement_molecular_weight": "",
            "replacement_logp": "",
            "replacement_h_donors": "",
            "replacement_h_acceptors": "",
            "replacement_rot_bonds": "",
            "replacement_scaffold": "",
            "apply_reference_row": "yes",
            "apply_split_row": "yes",
            "apply_meta_row": "yes",
            "row_ready_for_apply": "no",
            "required_missing_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_source,replacement_smiles,replacement_scaffold",
            "notes": "seed",
        }
    ]
    draft_rows = [
        {
            "packet_step": "core_binder_01",
            "draft_candidate_ligand_name": "acetazolamide",
            "draft_candidate_source_kind": "known_ca2_inhibitor_seed",
        }
    ]

    def fake_resolver(_: str) -> dict[str, str]:
        return {
            "resolved_query_name": "acetazolamide",
            "replacement_pubchem_cid": "1986",
            "replacement_structure_resolution_status": "pubchem_name_resolved",
            "replacement_structure_resolution_url": "https://example.test/acetazolamide",
            "replacement_smiles": "CC(=O)NC1=NN=C(S1)S(=O)(=O)N",
            "replacement_molecular_weight": "222.0000",
            "replacement_logp": "-0.1000",
            "replacement_h_donors": "2",
            "replacement_h_acceptors": "5",
            "replacement_rot_bonds": "1",
            "replacement_scaffold": "S1C=NN=C1",
        }

    payload = MODULE.build_payload(workbook_rows, draft_rows, "ca2", fake_resolver)
    row = payload["workbook_rows"][0]
    assert row["replacement_ligand_id"] == "acetazolamide"
    assert row["replacement_source"] == "pubchem_name_resolve_pending::known_ca2_inhibitor_seed"
    assert row["replacement_smiles"] == "CC(=O)NC1=NN=C(S1)S(=O)(=O)N"
    assert row["replacement_scaffold"] == "S1C=NN=C1"
    assert row["required_missing_fields"] == "replacement_reference_binding_kcal_mol"
    assert row["row_ready_for_apply"] == "no"
    assert payload["summary"]["rows_missing_only_binding_after_autofill"] == 1


def test_build_payload_pxr_resolution_failure_keeps_binding_and_structure_missing() -> None:
    workbook_rows = [
        {
            "packet": "core",
            "packet_step": "core_eval_binder_01",
            "target": "PXR",
            "current_ligand_id": "pxr_eval_ligand_01",
            "current_binder_label": "binder",
            "current_role": "far_ood_eval",
            "replacement_ligand_id": "",
            "replacement_reference_binding_kcal_mol": "",
            "replacement_is_binder": "1",
            "replacement_source": "",
            "replacement_role": "far_ood_eval",
            "replacement_smiles": "",
            "replacement_molecular_weight": "",
            "replacement_logp": "",
            "replacement_h_donors": "",
            "replacement_h_acceptors": "",
            "replacement_rot_bonds": "",
            "replacement_scaffold": "",
            "apply_reference_row": "yes",
            "apply_split_row": "yes",
            "apply_meta_row": "yes",
            "row_ready_for_apply": "no",
            "required_missing_fields": "replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_source,replacement_smiles,replacement_scaffold",
            "notes": "seed",
        }
    ]
    draft_rows = [
        {
            "packet_step": "core_eval_binder_01",
            "draft_candidate_ligand_name": "rifampicin",
            "draft_candidate_source_kind": "known_pxr_ligand_seed",
        }
    ]

    def failing_resolver(_: str) -> dict[str, str]:
        raise ValueError("network unavailable")

    payload = MODULE.build_payload(workbook_rows, draft_rows, "pxr", failing_resolver)
    row = payload["workbook_rows"][0]
    assert row["replacement_ligand_id"] == ""
    assert row["replacement_source"] == ""
    assert "replacement_reference_binding_kcal_mol" in row["required_missing_fields"]
    assert "replacement_smiles" in row["required_missing_fields"]
    assert payload["summary"]["resolution_failed_row_count"] == 1


def test_smiles_features_uses_acyclic_fallback_scaffold() -> None:
    features = MODULE._smiles_features("N=C(N)NCCNC(N)=N")
    assert features["replacement_scaffold"].startswith("acyclic::")
