from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_product_scope_breadth_evidence_acquisition_queue as mod


ROOT = Path(__file__).resolve().parents[2]


def _transporter() -> dict[str, object]:
    return {
        "summary": {
            "unresolved_slot_count": 2,
            "next_slot_completion_packet": {
                "packet_ready": True,
                "completion_contract_version": "transporter_next_slot_exact_evidence_v2",
                "slot_id": "AQP1.core_binder_01",
                "expected_evidence_type": "direct_or_claim_safe_binding_kcal",
                "required_exact_evidence_field_count": 3,
                "required_exact_evidence_fields": [
                    "target_uniprot_accession",
                    "source_pmid_or_document_id",
                    "evidence_sentence_or_table_locator",
                ],
                "required_operator_intake_columns": [
                    "target_id",
                    "candidate_ligand_id",
                    "reference_binding_kcal_mol",
                ],
                "required_claim_guardrails": [
                    "functional_surrogate_does_not_authorize_direct_binding_claim",
                    "scope_promotion_allowed_false_until_all_transporter_p0_slots_green",
                ],
                "operator_review_artifact": "runs/transporter_manual_review_intake_template_current.csv",
                "post_intake_synchronization_targets": [
                    "config/ligand_binding_reference_blind_aqp1_v1.csv",
                    "config/ligand_eval_splits_blind_aqp1_v1.csv",
                ],
                "acceptance_gate_commands": [
                    "python3 tools/build_transporter_binder_promotion_gate.py",
                    "python3 tools/build_product_scope_breadth_contract.py",
                ],
            },
        },
        "rows": [
            {
                "target_id": "AQP1",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "ligand_a",
                "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "next_required_action": "acquire binder evidence",
            },
            {
                "target_id": "GLUT1_4PYP",
                "packet_step": "core_non_binder_01",
                "current_ligand_id": "placeholder",
                "request_mode": "exact_target_pair_quantitative_negative_evidence_required",
                "required_missing_fields": "replacement_ligand_id",
                "next_required_action": "acquire negative evidence",
            },
        ],
    }


def _pxr() -> dict[str, object]:
    return {
        "summary": {"reconciled_blocked_row_count": 1},
        "rows": [
            {
                "packet_step": "ood_fit_binder_01",
                "candidate_name": "bexarotene",
                "request_mode": "exact_human_pxr_quantitative_binder_value_required",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "next_required_action": "resolve pxr row",
            }
        ],
    }


def _pxr_exact_review() -> dict[str, object]:
    return {
        "summary": {
            "pxr_exact_review_intake_ready": True,
            "review_template_row_count": 1,
            "next_review_candidate_name": "bexarotene",
        },
        "rows": [
            {
                "review_row_id": "pxr_review_bexarotene",
                "packet_step": "ood_fit_binder_01",
                "candidate_name": "bexarotene",
                "required_evidence_mode": "exact_human_nr1i2_pxr_binder_value_required",
                "target_species": "human",
                "target_gene": "NR1I2",
                "target_alias": "PXR",
                "target_match_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
                "replacement_reference_binding_kcal_mol": (
                    "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED"
                ),
                "replacement_source_url_or_doi": "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED",
                "assay_type_and_endpoint": "OPERATOR_FILL_ASSAY_TYPE_AND_ENDPOINT",
                "conflict_resolution_required": False,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
            }
        ],
    }


def _general() -> dict[str, object]:
    return {
        "summary": {"blocker_count": 2},
        "rows": [
            {
                "check_id": "domain_ready.transporter",
                "check_type": "breadth_domain",
                "release_blocker": True,
                "current_value": "blocked",
                "required_value": "ready",
                "next_action": "finish transporter",
            },
            {
                "check_id": "api_surface_ready",
                "check_type": "product_surface",
                "release_blocker": False,
                "current_value": "True",
                "required_value": "True",
                "next_action": "keep green",
            },
            {
                "check_id": "explicit_general_platform_flag",
                "check_type": "product_claim_flag",
                "release_blocker": True,
                "current_value": "False",
                "required_value": "True",
                "next_action": "set after domains green",
            },
        ],
    }


def _aqp1_functional() -> dict[str, object]:
    return {
        "summary": {
            "functional_kcal_surrogate_ready_count": 1,
            "direct_binding_gap_still_open": True,
        },
        "rows": [
            {
                "packet_step": "core_binder_01",
                "candidate_name": "bacopaside II",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "source_anchor": "PMID 27474162",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "target_uniprot": "P29972",
                "public_provenance_status": "compound_publicly_resolved_target_activity_absent",
                "functional_measure_kind": "IC50",
                "functional_measure_value": "18",
                "functional_measure_units": "uM",
                "functional_delta_g_surrogate_kcal_mol": "-6.47",
                "assay_type_honesty": "functional_ic50_derived_surrogate_not_direct_binding",
                "direct_binding_claim_allowed": "no",
                "binding_kcal_claim_allowed": "no",
                "replacement_reference_binding_kcal_mol_must_remain_blank": "yes",
                "claim_safe_functional_kcal_ready": "yes",
            }
        ],
    }


def _aqp1_ledger() -> dict[str, object]:
    return {
        "summary": {"row_count": 1},
        "rows": [
            {
                "proposed_packet_step": "core_binder_01",
                "candidate_name": "bacopaside II",
                "anchor": "PMID 27474162",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "review_bucket": "review_only_first_wave",
                "promotion_policy": "draft_first_wave_manual_review",
                "caution": "Functional AQP1 inhibition is shown, but this is not direct binding.",
            }
        ],
    }


def test_scope_breadth_evidence_acquisition_queue_merges_science_and_claim_gate_items() -> None:
    payload = mod.build_payload(
        transporter_payload=_transporter(),
        pxr_payload=_pxr(),
        general_payload=_general(),
        pxr_exact_review_payload=_pxr_exact_review(),
        aqp1_functional_payload=_aqp1_functional(),
        aqp1_ledger_payload=_aqp1_ledger(),
    )

    summary = payload["summary"]
    assert summary["queue_item_count"] == 5
    assert summary["scientific_evidence_request_count"] == 3
    assert summary["claim_gate_prerequisite_count"] == 2
    assert summary["transporter_unresolved_slot_count"] == 2
    assert summary["pxr_reconciled_blocked_row_count"] == 1
    assert summary["general_claim_blocker_count"] == 2
    assert summary["next_operator_completion_packet_ready"] is True
    assert summary["next_operator_completion_slot_id"] == "AQP1.core_binder_01"
    assert summary["next_operator_completion_expected_evidence_type"] == "direct_or_claim_safe_binding_kcal"
    assert summary["next_operator_completion_required_exact_evidence_field_count"] == 3
    assert "target_uniprot_accession" in summary["next_operator_completion_required_exact_evidence_fields"]
    assert "reference_binding_kcal_mol" in summary["next_operator_completion_required_operator_intake_columns"]
    assert (
        "functional_surrogate_does_not_authorize_direct_binding_claim"
        in summary["next_operator_completion_required_claim_guardrails"]
    )
    assert (
        summary["next_operator_completion_operator_review_artifact"]
        == "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert (
        "config/ligand_binding_reference_blind_aqp1_v1.csv"
        in summary["next_operator_completion_post_intake_synchronization_targets"]
    )
    assert "build_product_scope_breadth_contract.py" in summary["next_operator_completion_acceptance_gate_commands"]
    assert summary["next_operator_completion_aqp1_review_sidecar_ready"] is True
    assert summary["next_operator_completion_aqp1_review_candidate_name"] == "bacopaside II"
    assert summary["next_operator_completion_aqp1_review_source_anchor"] == "PMID 27474162"
    assert summary["next_operator_completion_aqp1_review_source_url"].endswith("27474162/")
    assert summary["next_operator_completion_aqp1_review_target_uniprot"] == "P29972"
    assert summary["next_operator_completion_aqp1_review_functional_measure"] == "IC50;18;uM"
    assert summary["next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"] == "-6.47"
    assert summary["next_operator_completion_aqp1_review_assay_type_honesty"] == (
        "functional_ic50_derived_surrogate_not_direct_binding"
    )
    assert summary["next_operator_completion_aqp1_review_direct_binding_claim_allowed"] == "no"
    assert (
        summary[
            "next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
        ]
        == "yes"
    )
    assert summary["next_operator_completion_aqp1_review_ledger_review_bucket"] == (
        "review_only_first_wave"
    )
    assert summary["aqp1_review_sidecar_row_count"] == 1
    assert summary["pxr_exact_review_sidecar_row_count"] == 1
    assert summary["next_pxr_exact_review_sidecar_ready"] is True
    assert summary["next_pxr_exact_review_row_id"] == "pxr_review_bexarotene"
    assert summary["next_pxr_exact_review_candidate_name"] == "bexarotene"
    assert summary["next_pxr_exact_review_required_evidence_mode"] == (
        "exact_human_nr1i2_pxr_binder_value_required"
    )
    assert summary["next_pxr_exact_review_target_match_confirmed"] == "OPERATOR_FILL_TRUE_OR_FALSE"
    assert summary["next_pxr_exact_review_replacement_reference_binding_kcal_mol"].startswith(
        "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL"
    )
    assert summary["next_pxr_exact_review_authoritative_apply_allowed"] is False
    assert summary["next_pxr_exact_review_scope_promotion_allowed"] is False
    assert summary["scope_promotion_allowed"] is False
    assert payload["rows"][0]["domain"] == "transporter"
    assert payload["rows"][0]["operator_completion_packet_ready"] is True
    assert payload["rows"][0]["aqp1_review_sidecar_ready"] is True
    assert payload["rows"][0]["aqp1_review_candidate_name"] == "bacopaside II"
    assert payload["rows"][0]["aqp1_review_direct_binding_claim_allowed"] == "no"
    assert payload["rows"][0]["operator_completion_contract_version"] == "transporter_next_slot_exact_evidence_v2"
    assert "target_uniprot_accession" in payload["rows"][0]["operator_completion_required_exact_evidence_fields"]
    assert (
        "functional_surrogate_does_not_authorize_direct_binding_claim"
        in payload["rows"][0]["operator_completion_required_claim_guardrails"]
    )
    assert "build_product_scope_breadth_contract.py" in payload["rows"][0]["operator_completion_acceptance_gate_commands"]
    pxr_row = next(row for row in payload["rows"] if row["domain"] == "pxr")
    assert pxr_row["pxr_exact_review_sidecar_ready"] is True
    assert pxr_row["pxr_exact_review_row_id"] == "pxr_review_bexarotene"
    assert pxr_row["pxr_exact_review_target_gene"] == "NR1I2"
    assert pxr_row["pxr_exact_review_scope_promotion_allowed"] is False
    assert payload["rows"][-1]["item_id"] == "explicit_general_platform_flag"


def test_scope_breadth_evidence_acquisition_queue_cli_writes_outputs(tmp_path: Path) -> None:
    transporter = tmp_path / "transporter.json"
    pxr = tmp_path / "pxr.json"
    pxr_exact_review = tmp_path / "pxr_exact_review.json"
    general = tmp_path / "general.json"
    aqp1_functional = tmp_path / "aqp1_functional.json"
    aqp1_ledger = tmp_path / "aqp1_ledger.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    transporter.write_text(json.dumps(_transporter()), encoding="utf-8")
    pxr.write_text(json.dumps(_pxr()), encoding="utf-8")
    pxr_exact_review.write_text(json.dumps(_pxr_exact_review()), encoding="utf-8")
    general.write_text(json.dumps(_general()), encoding="utf-8")
    aqp1_functional.write_text(json.dumps(_aqp1_functional()), encoding="utf-8")
    aqp1_ledger.write_text(json.dumps(_aqp1_ledger()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_product_scope_breadth_evidence_acquisition_queue.py",
            "--transporter-json",
            str(transporter),
            "--pxr-json",
            str(pxr),
            "--pxr-exact-review-json",
            str(pxr_exact_review),
            "--general-json",
            str(general),
            "--aqp1-functional-json",
            str(aqp1_functional),
            "--aqp1-ledger-json",
            str(aqp1_ledger),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["queue_item_count"] == 5
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"][
        "next_operator_completion_aqp1_review_sidecar_ready"
    ] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"][
        "next_pxr_exact_review_sidecar_ready"
    ] is True
    md = out_md.read_text(encoding="utf-8")
    assert "Product Scope Breadth Evidence Acquisition Queue" in md
    assert "Next Operator Completion Contract" in md
    assert "next_operator_completion_required_exact_evidence_fields" in md
    assert "bacopaside II" in md
    assert "pxr_review_bexarotene" in md
    assert "priority" in out_csv.read_text(encoding="utf-8")
