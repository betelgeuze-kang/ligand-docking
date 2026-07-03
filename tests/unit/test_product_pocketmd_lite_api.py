from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def _claim_grade_preview_rows() -> list[dict[str, object]]:
    return [
        {
            "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
            "band": "green",
            "claim_safe": True,
            "local_min_ligand_rmsd_a": "1.1",
            "hbond_persistence": "1.0",
            "contact_persistence": "1.0",
            "initial_clash_count": "9",
            "clash_count": "0",
            "clash_relief_count": "9",
        },
        {
            "entry_id": "ADRB2_GPCR_BLIND:timolol",
            "band": "green",
            "claim_safe": True,
            "local_min_ligand_rmsd_a": "1.2",
            "hbond_persistence": "1.0",
            "contact_persistence": "1.0",
            "initial_clash_count": "7",
            "clash_count": "0",
            "clash_relief_count": "7",
        },
        {
            "entry_id": "ADRB2_GPCR_BLIND:carazolol",
            "band": "green",
            "claim_safe": True,
            "local_min_ligand_rmsd_a": "1.3",
            "hbond_persistence": "1.0",
            "contact_persistence": "1.0",
            "initial_clash_count": "8",
            "clash_count": "0",
            "clash_relief_count": "8",
        },
        {
            "entry_id": "CHEMBL234_DRD3_HUMAN:CHEMBL5841759",
            "band": "green",
            "claim_safe": True,
            "local_min_ligand_rmsd_a": "1.4",
            "hbond_persistence": "1.0",
            "contact_persistence": "1.0",
            "initial_clash_count": "6",
            "clash_count": "0",
            "clash_relief_count": "6",
        },
        {
            "entry_id": "CHEMBL236_OPRD1_HUMAN:CHEMBL67192",
            "band": "green",
            "claim_safe": True,
            "local_min_ligand_rmsd_a": "1.5",
            "hbond_persistence": "1.0",
            "contact_persistence": "1.0",
            "initial_clash_count": "5",
            "clash_count": "0",
            "clash_relief_count": "5",
        },
    ]


def test_pocketmd_lite_report_endpoint_exposes_operator_panel_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    canonical = tmp_path / "pocketmd_lite_report_current.json"
    preview = tmp_path / "pocketmd_lite_candidate_metric_fill_preview_report_current.json"
    review_packet = tmp_path / "pocketmd_lite_canonical_report_review_packet_current.json"
    canonical.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pocketmd_lite_report",
                    "schema_version": "pocketmd_lite_contract_v1",
                    "candidate_count": 2,
                    "selected_top_k_count": 2,
                    "refinement_blocker_count": 1,
                    "top_k_refinement_evidence_ready": False,
                    "pocketmd_lite_claim_safe": False,
                    "claim_grade_metric_ready_row_count": 1,
                    "band_counts": {"green": 1, "yellow": 0, "red": 0, "abstain": 1},
                    "green_row_count": 1,
                    "yellow_row_count": 0,
                    "red_row_count": 0,
                    "abstain_row_count": 1,
                    "missing_refinement_metric_names": [
                        "local_min_ligand_rmsd_a",
                        "hbond_persistence",
                    ],
                    "missing_refinement_metric_counts": {
                        "local_min_ligand_rmsd_a": 1,
                        "hbond_persistence": 1,
                    },
                    "green_band_condition_text": "green requires exact recovered metrics",
                },
                "rows": [
                    {
                        "entry_id": "ADRB2.compound_001",
                        "family": "gpcr",
                        "selected_for_refine": True,
                        "band": "abstain",
                        "claim_safe": False,
                        "local_min_ligand_rmsd_a": None,
                        "local_min_survived": None,
                        "hbond_persistence": None,
                        "contact_persistence": "0.9",
                        "initial_clash_count": None,
                        "clash_count": "0",
                        "clash_relief_count": None,
                        "evidence_completeness": "0.4",
                        "uncertainty_score": "1.0",
                        "uncertainty_posture": "missing_refinement_evidence_high_uncertainty",
                        "reason_code": "missing_refinement_evidence",
                        "missing_evidence_fields": [
                            "local_min_ligand_rmsd_a",
                            "hbond_persistence",
                        ],
                        "review_flags": [],
                    },
                    {
                        "entry_id": "ADRB2.compound_002",
                        "family": "gpcr",
                        "selected_for_refine": True,
                        "band": "green",
                        "claim_safe": True,
                        "local_min_ligand_rmsd_a": "1.4",
                        "local_min_survived": True,
                        "hbond_persistence": "0.7",
                        "contact_persistence": "0.95",
                        "initial_clash_count": "11",
                        "clash_count": "0",
                        "clash_relief_count": "11",
                        "evidence_completeness": "1.0",
                        "uncertainty_score": "0.2",
                        "uncertainty_posture": "green_low_uncertainty",
                        "reason_code": "",
                        "missing_evidence_fields": [],
                        "review_flags": [],
                    },
                ],
                "claim_boundary": "PocketMD Lite report boundary.",
            }
        ),
        encoding="utf-8",
    )
    preview.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pocketmd_lite_report_ready",
                    "candidate_count": 5,
                    "selected_top_k_count": 5,
                    "top_k_refinement_evidence_ready": True,
                    "pocketmd_lite_claim_safe": True,
                    "claim_grade_metric_ready_row_count": 5,
                    "green_row_count": 5,
                    "yellow_row_count": 0,
                    "red_row_count": 0,
                    "abstain_row_count": 0,
                },
                "rows": _claim_grade_preview_rows(),
            }
        ),
        encoding="utf-8",
    )
    review_packet.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pocketmd_lite_canonical_report_review_packet_ready",
                    "operator_approval_required": True,
                    "approval_token_required": "APPROVE_POCKETMD_LITE_CANONICAL_METRIC_FILL",
                    "candidate_csv_update_allowed": True,
                    "canonical_candidate_csv_mutated": False,
                    "canonical_candidate_csv": "config/pocketmd_lite_candidates_current.csv",
                    "preview_candidate_csv": (
                        "runs/pocketmd_lite_candidate_metric_fill_preview_current.candidates.csv"
                    ),
                    "review_row_count": 5,
                    "ready_review_row_count": 5,
                    "blocked_review_row_count": 0,
                    "selected_top_k_count": 5,
                    "preview_report_ready": True,
                    "preview_claim_safe": True,
                    "preview_green_row_count": 5,
                    "preview_abstain_row_count": 0,
                    "canonical_report_ready": False,
                    "canonical_claim_safe": False,
                    "canonical_green_row_count": 0,
                    "canonical_abstain_row_count": 5,
                    "canonical_missing_refinement_metric_names": [
                        "local_min_ligand_rmsd_a",
                        "hbond_persistence",
                        "initial_clash_count",
                    ],
                    "metric_source_audit_ready": True,
                    "candidate_fill_preview_ready": True,
                    "next_required_step": (
                        "Operator review required before canonical candidate CSV update."
                    ),
                    "claim_promotion_allowed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
                "rows": [
                    {
                        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                        "review_ready": True,
                        "review_action": (
                            "operator_review_preview_metrics_before_canonical_candidate_csv_update"
                        ),
                        "metric_fill_status": "filled_from_claim_grade_probe",
                        "metric_source_npz": (
                            "runs/pocketmd_lite_bounded_metric_collector_current/"
                            "ADRB2_GPCR_BLIND__carvedilol__bounded_metrics.npz"
                        ),
                        "canonical_band": "abstain",
                        "preview_band": "green",
                        "canonical_claim_safe": False,
                        "preview_claim_safe": True,
                        "canonical_missing_metric_names": (
                            "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count"
                        ),
                        "preview_missing_metric_names": [],
                        "canonical_update_candidate": True,
                        "canonical_local_min_ligand_rmsd_a": None,
                        "preview_local_min_ligand_rmsd_a": "1.298",
                        "canonical_hbond_persistence": None,
                        "preview_hbond_persistence": "1.0",
                        "canonical_contact_persistence": "1.0",
                        "preview_contact_persistence": "1.0",
                        "canonical_initial_clash_count": None,
                        "preview_initial_clash_count": "57",
                        "canonical_clash_count": "0",
                        "preview_clash_count": "0",
                        "canonical_clash_relief_count": None,
                        "preview_clash_relief_count": "57",
                        "blockers": [],
                        "claim_promotion_allowed": True,
                        "candidate_csv_update_allowed": True,
                        "refinement_execution_enabled": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "POCKETMD_LITE_REPORT_ARTIFACT", canonical)
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT",
        preview,
    )
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANONICAL_REPORT_REVIEW_PACKET_ARTIFACT",
        review_packet,
    )

    payload = asyncio.run(mod.get_product_pocketmd_lite_report())

    assert payload["status"] == "blocked_pocketmd_lite_report"
    assert payload["report_panel_ready"] is True
    assert payload["preview_report_ready"] is True
    assert payload["preview_pocketmd_lite_claim_safe"] is True
    assert payload["preview_claim_grade_metric_ready_row_count"] == 5
    assert payload["preview_green_row_count"] == 5
    assert payload["canonical_review_required"] is True
    assert payload["claim_promotion_allowed"] is False
    assert payload["candidate_csv_update_allowed"] is False
    assert payload["report_row_count"] == 2
    assert payload["local_min_ligand_rmsd_a_max"] == 1.4
    assert payload["hbond_persistence_min"] == 0.7
    assert payload["contact_persistence_min"] == 0.9
    assert payload["initial_clash_count_total"] == 11
    assert payload["final_clash_count_total"] == 0
    assert payload["clash_relief_count_total"] == 11
    assert payload["report_rows"][0] == {
        "entry_id": "ADRB2.compound_001",
        "family": "gpcr",
        "selected_for_refine": True,
        "band": "abstain",
        "claim_safe": False,
        "local_min_ligand_rmsd_a": None,
        "local_min_survived": None,
        "hbond_persistence": None,
        "contact_persistence": 0.9,
        "initial_clash_count": None,
        "final_clash_count": 0,
        "clash_relief_count": None,
        "evidence_completeness": 0.4,
        "uncertainty_score": 1.0,
        "uncertainty_posture": "missing_refinement_evidence_high_uncertainty",
        "reason_code": "missing_refinement_evidence",
        "missing_evidence_fields": ["local_min_ligand_rmsd_a", "hbond_persistence"],
        "review_flags": [],
        "operator_action_required": True,
        "recommended_next_action": "recover_exact_refinement_metric_fields",
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    assert payload["report_rows"][1]["operator_action_required"] is False
    assert payload["report_rows"][1]["recommended_next_action"] == (
        "review_and_promote_to_canonical_report_if_approved"
    )
    assert {
        row["blocker_id"]
        for row in payload["blocker_rows"]
    } >= {
        "pocketmd_lite_top_k_refinement_evidence_not_ready",
        "pocketmd_lite_claim_safe_false",
        "missing_refinement_metric:local_min_ligand_rmsd_a",
        "missing_refinement_metric:hbond_persistence",
        "candidate_refinement_evidence:ADRB2.compound_001",
        "preview_metrics_require_canonical_review",
    }
    assert payload["blocker_row_count"] == len(payload["blocker_rows"])
    assert all(row["claim_promotion_allowed"] is False for row in payload["blocker_rows"])
    assert payload["claim_grade_readiness_row_count"] == 9
    assert payload["claim_grade_readiness_ready_row_count"] == 8
    assert payload["claim_grade_readiness_blocked_row_count"] == 1
    readiness = {
        row["requirement_id"]: row for row in payload["claim_grade_readiness_rows"]
    }
    assert readiness["preview_claim_grade_metric_report_ready"]["ready"] is True
    assert readiness["adrb2_three_collection_ready_rows"]["ready"] is True
    assert readiness["drd3_oprd1_atom_frame_recovery"]["ready"] is True
    assert readiness["local_min_ligand_rmsd_ready"]["ready"] is True
    assert readiness["hbond_persistence_ready"]["ready"] is True
    assert readiness["contact_persistence_ready"]["ready"] is True
    assert readiness["clash_relief_ready"]["ready"] is True
    assert readiness["green_yellow_red_abstain_banding_ready"]["ready"] is True
    assert readiness["canonical_report_review_closed"]["ready"] is False
    assert readiness["canonical_report_review_closed"]["blocker"] == (
        "preview_metrics_require_canonical_review"
    )
    assert payload["canonical_review_packet_present"] is True
    assert payload["canonical_review_packet_ready"] is True
    assert payload["canonical_review_operator_approval_required"] is True
    assert payload["canonical_review_approval_token_required"] == (
        "APPROVE_POCKETMD_LITE_CANONICAL_METRIC_FILL"
    )
    assert payload["canonical_review_candidate_csv_update_allowed"] is False
    assert payload["canonical_review_canonical_candidate_csv_mutated"] is False
    assert payload["canonical_review_review_row_count"] == 5
    assert payload["canonical_review_ready_review_row_count"] == 5
    assert payload["canonical_review_blocked_review_row_count"] == 0
    assert payload["canonical_review_preview_report_ready"] is True
    assert payload["canonical_review_preview_claim_safe"] is True
    assert payload["canonical_review_preview_green_row_count"] == 5
    assert payload["canonical_review_canonical_report_ready"] is False
    assert payload["canonical_review_canonical_claim_safe"] is False
    assert payload["canonical_review_canonical_abstain_row_count"] == 5
    assert payload["canonical_review_metric_source_audit_ready"] is True
    assert payload["canonical_review_candidate_fill_preview_ready"] is True
    assert payload["canonical_review_next_required_step"] == (
        "Operator review required before canonical candidate CSV update."
    )
    assert payload["canonical_review_rows"][0] == {
        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
        "review_ready": True,
        "review_action": (
            "operator_review_preview_metrics_before_canonical_candidate_csv_update"
        ),
        "metric_fill_status": "filled_from_claim_grade_probe",
        "metric_source_npz": (
            "runs/pocketmd_lite_bounded_metric_collector_current/"
            "ADRB2_GPCR_BLIND__carvedilol__bounded_metrics.npz"
        ),
        "canonical_band": "abstain",
        "preview_band": "green",
        "canonical_claim_safe": False,
        "preview_claim_safe": True,
        "canonical_missing_metric_names": [
            "local_min_ligand_rmsd_a",
            "hbond_persistence",
            "initial_clash_count",
        ],
        "preview_missing_metric_names": [],
        "canonical_update_candidate": True,
        "canonical_local_min_ligand_rmsd_a": None,
        "preview_local_min_ligand_rmsd_a": 1.298,
        "canonical_hbond_persistence": None,
        "preview_hbond_persistence": 1.0,
        "canonical_contact_persistence": 1.0,
        "preview_contact_persistence": 1.0,
        "canonical_initial_clash_count": None,
        "preview_initial_clash_count": 57,
        "canonical_final_clash_count": 0,
        "preview_final_clash_count": 0,
        "canonical_clash_relief_count": None,
        "preview_clash_relief_count": 57,
        "blockers": [],
        "operator_action_required": False,
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "refinement_execution_enabled": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    assert payload["canonical_review_claim_promotion_allowed"] is False
    assert payload["canonical_review_refinement_execution_enabled"] is False
    assert payload["canonical_review_execution_enabled"] is False
    assert payload["canonical_review_external_state_mutated"] is False
    assert all(
        row["claim_promotion_allowed"] is False
        and row["candidate_csv_update_allowed"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        for row in payload["claim_grade_readiness_rows"]
    )
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_pocketmd_lite_report_endpoint_is_fail_closed_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    monkeypatch.setattr(mod, "POCKETMD_LITE_REPORT_ARTIFACT", tmp_path / "missing.json")
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT",
        tmp_path / "missing-preview.json",
    )
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANONICAL_REPORT_REVIEW_PACKET_ARTIFACT",
        tmp_path / "missing-review-packet.json",
    )

    payload = asyncio.run(mod.get_product_pocketmd_lite_report())

    assert payload["status"] == "missing_pocketmd_lite_report"
    assert payload["report_panel_ready"] is False
    assert payload["preview_report_ready"] is False
    assert payload["canonical_review_required"] is False
    assert payload["report_row_count"] == 0
    assert payload["report_rows"] == []
    assert payload["blocker_row_count"] == 1
    assert payload["blocker_rows"][0]["blocker_id"] == "pocketmd_lite_report_missing"
    assert payload["claim_grade_readiness_row_count"] == 9
    assert payload["claim_grade_readiness_ready_row_count"] == 0
    assert payload["claim_grade_readiness_blocked_row_count"] == 9
    assert payload["claim_grade_readiness_blocked_rows"] == payload[
        "claim_grade_readiness_rows"
    ]
    assert payload["canonical_review_packet_present"] is False
    assert payload["canonical_review_packet_ready"] is False
    assert payload["canonical_review_review_row_count"] == 0
    assert payload["canonical_review_rows"] == []
    assert payload["claim_promotion_allowed"] is False
    assert payload["candidate_csv_update_allowed"] is False
    assert payload["local_min_ligand_rmsd_a_max"] == 0.0
    assert payload["hbond_persistence_min"] == 0.0
    assert payload["contact_persistence_min"] == 0.0
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_pocketmd_lite_candidate_metric_fill_preview_report_endpoint_reads_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    artifact = tmp_path / "pocketmd_lite_candidate_metric_fill_preview_report_current.json"
    canonical = tmp_path / "pocketmd_lite_report_current.json"
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pocketmd_lite_report_ready",
                    "schema_version": "pocketmd_lite_contract_v1",
                    "candidate_count": 2,
                    "selected_top_k_count": 2,
                    "top_k_refinement_evidence_ready": True,
                    "pocketmd_lite_claim_safe": True,
                    "claim_grade_metric_ready_row_count": 2,
                    "band_counts": {"green": 2, "yellow": 0, "red": 0, "abstain": 0},
                    "green_row_count": 2,
                    "yellow_row_count": 0,
                    "red_row_count": 0,
                    "abstain_row_count": 0,
                    "green_band_condition_text": "green requires exact recovered metrics",
                },
                "rows": [
                    {
                        "entry_id": "ADRB2.compound_001",
                        "local_min_ligand_rmsd_a": "1.2",
                        "hbond_persistence": "0.8",
                        "contact_persistence": "0.9",
                        "initial_clash_count": "10",
                        "clash_count": "1",
                        "clash_relief_count": "9",
                    },
                    {
                        "entry_id": "ADRB2.compound_002",
                        "local_min_ligand_rmsd_a": "1.4",
                        "hbond_persistence": "0.7",
                        "contact_persistence": "0.95",
                        "initial_clash_count": "11",
                        "clash_count": "0",
                        "clash_relief_count": "11",
                    },
                ],
                "claim_boundary": "Preview metrics require canonical report review.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT",
        artifact,
    )
    monkeypatch.setattr(mod, "POCKETMD_LITE_REPORT_ARTIFACT", canonical)

    payload = asyncio.run(mod.get_product_pocketmd_lite_candidate_metric_fill_preview_report())

    assert payload["status"] == "pocketmd_lite_report_ready"
    assert payload["preview_report_ready"] is True
    assert payload["preview_requires_canonical_review"] is True
    assert payload["preview_pocketmd_lite_claim_safe"] is True
    assert payload["pocketmd_lite_claim_safe"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["claim_grade_metric_ready_row_count"] == 2
    assert payload["band_counts"]["green"] == 2
    assert payload["green_row_count"] == 2
    assert payload["local_min_ligand_rmsd_a_max"] == 1.4
    assert payload["hbond_persistence_min"] == 0.7
    assert payload["contact_persistence_min"] == 0.9
    assert payload["initial_clash_count_total"] == 21
    assert payload["final_clash_count_total"] == 1
    assert payload["clash_relief_count_total"] == 20
    assert payload["green_band_condition_text"] == "green requires exact recovered metrics"
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
    assert payload["candidates"][0]["entry_id"] == "ADRB2.compound_001"


def test_pocketmd_lite_candidate_metric_fill_preview_report_endpoint_is_fail_closed_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT",
        tmp_path / "missing.json",
    )

    payload = asyncio.run(mod.get_product_pocketmd_lite_candidate_metric_fill_preview_report())

    assert payload["status"] == "missing_pocketmd_lite_candidate_metric_fill_preview_report"
    assert payload["preview_report_ready"] is False
    assert payload["preview_requires_canonical_review"] is False
    assert payload["preview_pocketmd_lite_claim_safe"] is False
    assert payload["pocketmd_lite_claim_safe"] is False
    assert payload["claim_grade_metric_ready_row_count"] == 0
    assert payload["local_min_ligand_rmsd_a_max"] == 0.0
    assert payload["hbond_persistence_min"] == 0.0
    assert payload["contact_persistence_min"] == 0.0
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_pocketmd_lite_claim_grade_metric_source_audit_endpoint_reads_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    artifact = tmp_path / "pocketmd_lite_claim_grade_metric_source_audit_current.json"
    canonical = tmp_path / "pocketmd_lite_report_current.json"
    preview = tmp_path / "pocketmd_lite_candidate_metric_fill_preview_report_current.json"
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pocketmd_lite_claim_grade_metric_source_audit_ready",
                    "schema_version": "pocketmd_lite_claim_grade_metric_source_audit_v1",
                    "candidate_count": 2,
                    "searched_npz_candidate_count": 5,
                    "exact_metric_source_ready_count": 2,
                    "missing_exact_metric_source_count": 0,
                    "claim_grade_collection_input_ready_count": 2,
                    "selected_proxy_only_count": 2,
                    "atomized_protein_source_candidate_count": 2,
                    "ligand_atom_source_candidate_count": 2,
                    "partial_atomized_protein_only_candidate_count": 1,
                    "probe_status": "pocketmd_lite_metric_collection_probe_ready",
                    "next_required_step": "Extract exact metric fields into the preview CSV.",
                    "claim_promotion_allowed": True,
                    "candidate_csv_update_allowed": True,
                    "refinement_execution_enabled": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
                "rows": [
                    {
                        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                        "target": "ADRB2_GPCR_BLIND",
                        "ligand_id": "carvedilol",
                        "required_metrics": [
                            "local_min_ligand_rmsd_a",
                            "hbond_persistence",
                            "initial_clash_count",
                        ],
                        "selected_npz_status": "proxy_only_trajectory",
                        "selected_npz_schema": "coarse_two_bead_ca",
                        "selected_exact_metric_ready": False,
                        "selected_missing_exact_metric_fields": [
                            "local_min_ligand_rmsd_a",
                            "hbond_persistence",
                        ],
                        "selected_protein_atom_frame_count": 0,
                        "selected_ligand_atom_frame_count": 0,
                        "searched_npz_candidate_count": 3,
                        "exact_metric_source_candidate_count": 1,
                        "atomized_protein_candidate_count": 1,
                        "ligand_atom_candidate_count": 1,
                        "claim_grade_collection_input_candidate_count": 1,
                        "best_candidate_npz": "runs/bounded_metrics.npz",
                        "best_candidate_status": "exact_metric_source_ready",
                        "best_candidate_blockers": ["ligand_trajectory_is_two_bead_proxy"],
                        "recommended_next_local_action": (
                            "extract_exact_metric_fields_into_candidate_fill_preview_then_rerun_report"
                        ),
                        "claim_promotion_allowed": True,
                        "candidate_csv_update_allowed": True,
                        "refinement_execution_enabled": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                    },
                    {
                        "entry_id": "CHEMBL236_OPRD1_HUMAN:CHEMBL67192",
                        "target": "CHEMBL236_OPRD1_HUMAN",
                        "ligand_id": "CHEMBL67192",
                        "required_metrics": "local_min_ligand_rmsd_a;hbond_persistence",
                        "selected_npz_status": "exact_metric_source_ready",
                        "selected_npz_schema": "bounded_atomized",
                        "selected_exact_metric_ready": True,
                        "selected_missing_exact_metric_fields": [],
                        "searched_npz_candidate_count": 2,
                        "exact_metric_source_candidate_count": 1,
                        "atomized_protein_candidate_count": 1,
                        "ligand_atom_candidate_count": 1,
                        "claim_grade_collection_input_candidate_count": 1,
                        "best_candidate_npz": "runs/oprd1_bounded_metrics.npz",
                        "best_candidate_status": "exact_metric_source_ready",
                    },
                ],
                "claim_boundary": "metric source audit boundary",
            }
        ),
        encoding="utf-8",
    )
    canonical.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pocketmd_lite_report",
                    "top_k_refinement_evidence_ready": False,
                    "pocketmd_lite_claim_safe": False,
                }
            }
        ),
        encoding="utf-8",
    )
    preview.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pocketmd_lite_report_ready",
                    "top_k_refinement_evidence_ready": True,
                    "pocketmd_lite_claim_safe": True,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT",
        artifact,
    )
    monkeypatch.setattr(mod, "POCKETMD_LITE_REPORT_ARTIFACT", canonical)
    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT",
        preview,
    )

    payload = asyncio.run(mod.get_product_pocketmd_lite_claim_grade_metric_source_audit())

    assert payload["status"] == "pocketmd_lite_claim_grade_metric_source_audit_ready"
    assert payload["audit_panel_ready"] is True
    assert payload["claim_grade_metric_source_audit_ready"] is True
    assert payload["metric_source_extraction_ready"] is True
    assert payload["canonical_report_ready"] is False
    assert payload["preview_report_ready"] is True
    assert payload["canonical_review_required"] is True
    assert payload["candidate_count"] == 2
    assert payload["searched_npz_candidate_count"] == 5
    assert payload["exact_metric_source_ready_count"] == 2
    assert payload["missing_exact_metric_source_count"] == 0
    assert payload["claim_grade_collection_input_ready_count"] == 2
    assert payload["selected_proxy_only_count"] == 2
    assert payload["probe_status"] == "pocketmd_lite_metric_collection_probe_ready"
    assert payload["metric_source_row_count"] == 2
    assert payload["metric_source_operator_action_row_count"] == 1
    assert payload["metric_source_rows"][0] == {
        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
        "target": "ADRB2_GPCR_BLIND",
        "ligand_id": "carvedilol",
        "required_metrics": [
            "local_min_ligand_rmsd_a",
            "hbond_persistence",
            "initial_clash_count",
        ],
        "selected_npz_status": "proxy_only_trajectory",
        "selected_npz_schema": "coarse_two_bead_ca",
        "selected_exact_metric_ready": False,
        "selected_missing_exact_metric_fields": [
            "local_min_ligand_rmsd_a",
            "hbond_persistence",
        ],
        "selected_protein_atom_frame_count": 0,
        "selected_ligand_atom_frame_count": 0,
        "searched_npz_candidate_count": 3,
        "exact_metric_source_candidate_count": 1,
        "atomized_protein_candidate_count": 1,
        "ligand_atom_candidate_count": 1,
        "claim_grade_collection_input_candidate_count": 1,
        "best_candidate_npz": "runs/bounded_metrics.npz",
        "best_candidate_status": "exact_metric_source_ready",
        "best_candidate_blockers": ["ligand_trajectory_is_two_bead_proxy"],
        "recommended_next_local_action": (
            "extract_exact_metric_fields_into_candidate_fill_preview_then_rerun_report"
        ),
        "operator_action_required": True,
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "refinement_execution_enabled": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    assert payload["metric_source_rows"][1]["operator_action_required"] is False
    assert {
        row["blocker_id"]
        for row in payload["blocker_rows"]
    } == {
        "metric_source_extraction_required",
        "canonical_report_review_required",
    }
    assert all(row["claim_promotion_allowed"] is False for row in payload["blocker_rows"])
    assert payload["claim_promotion_allowed"] is False
    assert payload["candidate_csv_update_allowed"] is False
    assert payload["refinement_execution_enabled"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
    assert payload["claim_boundary"] == "metric source audit boundary"


def test_pocketmd_lite_claim_grade_metric_source_audit_endpoint_is_fail_closed_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    monkeypatch.setattr(
        mod,
        "POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT",
        tmp_path / "missing.json",
    )

    payload = asyncio.run(mod.get_product_pocketmd_lite_claim_grade_metric_source_audit())

    assert payload["status"] == "missing_pocketmd_lite_claim_grade_metric_source_audit"
    assert payload["audit_panel_ready"] is False
    assert payload["claim_grade_metric_source_audit_ready"] is False
    assert payload["metric_source_extraction_ready"] is False
    assert payload["canonical_report_ready"] is False
    assert payload["preview_report_ready"] is False
    assert payload["canonical_review_required"] is False
    assert payload["metric_source_row_count"] == 0
    assert payload["metric_source_rows"] == []
    assert payload["blocker_row_count"] == 1
    assert payload["blocker_rows"][0]["blocker_id"] == (
        "pocketmd_lite_claim_grade_metric_source_audit_missing"
    )
    assert payload["claim_promotion_allowed"] is False
    assert payload["candidate_csv_update_allowed"] is False
    assert payload["refinement_execution_enabled"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_pocketmd_lite_topk_refinement_audit_endpoint_reads_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    artifact = tmp_path / "pocketmd_lite_topk_refinement_audit_current.json"
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported",
                    "schema_version": "pocketmd_lite_topk_refinement_audit_v1",
                    "candidate_count": 5,
                    "selected_top_k_count": 5,
                    "claim_grade_refinement_evidence_ready": False,
                    "claim_grade_report_evidence_ready": False,
                    "proxy_topk_telemetry_ready": True,
                    "claim_grade_metric_ready_count": 0,
                    "claim_grade_missing_candidate_count": 5,
                    "claim_grade_band_counts": {
                        "green": 0,
                        "yellow": 0,
                        "red": 0,
                        "abstain": 5,
                    },
                    "green_row_count": 0,
                    "yellow_row_count": 0,
                    "red_row_count": 0,
                    "abstain_row_count": 5,
                    "claim_grade_fill_preview_evidence_ready": False,
                    "claim_grade_local_min_reported_count": 1,
                    "claim_grade_local_min_survival_count": 1,
                    "claim_grade_hbond_reported_count": 1,
                    "claim_grade_contact_reported_count": 1,
                    "claim_grade_initial_clash_reported_count": 1,
                    "claim_grade_final_clash_reported_count": 1,
                    "claim_grade_clash_relief_reported_count": 1,
                    "missing_refinement_metric_names": ["hbond_persistence"],
                    "missing_refinement_metric_counts": {"hbond_persistence": 5},
                    "green_band_condition_text": "green requires exact metrics",
                    "top_k_only_policy_enforced": True,
                    "claim_promotion_allowed": False,
                },
                "rows": [
                    {
                        "entry_id": "ADRB2.compound_001",
                        "local_min_ligand_rmsd_a": "1.2",
                        "hbond_persistence": "0.8",
                        "contact_persistence": "0.9",
                        "initial_clash_count": "10",
                        "clash_count": "1",
                        "clash_relief_count": "9",
                    }
                ],
                "claim_boundary": "Proxy telemetry cannot satisfy claim-grade refinement evidence.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT", artifact)

    payload = asyncio.run(mod.get_product_pocketmd_lite_topk_refinement_audit())

    assert payload["status"] == "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported"
    assert payload["selected_top_k_count"] == 5
    assert payload["claim_grade_refinement_evidence_ready"] is False
    assert payload["proxy_topk_telemetry_ready"] is True
    assert payload["claim_grade_band_counts"]["abstain"] == 5
    assert payload["abstain_row_count"] == 5
    assert payload["claim_grade_local_min_reported_count"] == 1
    assert payload["claim_grade_clash_relief_reported_count"] == 1
    assert payload["local_min_ligand_rmsd_a_max"] == 1.2
    assert payload["hbond_persistence_min"] == 0.8
    assert payload["contact_persistence_min"] == 0.9
    assert payload["initial_clash_count_total"] == 10
    assert payload["final_clash_count_total"] == 1
    assert payload["clash_relief_count_total"] == 9
    assert payload["green_band_condition_text"] == "green requires exact metrics"
    assert payload["top_k_only_policy_enforced"] is True
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
    assert payload["rows"][0]["entry_id"] == "ADRB2.compound_001"


def test_pocketmd_lite_topk_refinement_audit_endpoint_is_fail_closed_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    monkeypatch.setattr(mod, "POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT", tmp_path / "missing.json")

    payload = asyncio.run(mod.get_product_pocketmd_lite_topk_refinement_audit())

    assert payload["status"] == "missing_pocketmd_lite_topk_refinement_audit"
    assert payload["claim_grade_refinement_evidence_ready"] is False
    assert payload["proxy_topk_telemetry_ready"] is False
    assert payload["claim_grade_band_counts"] == {}
    assert payload["green_row_count"] == 0
    assert payload["local_min_ligand_rmsd_a_max"] == 0.0
    assert payload["hbond_persistence_min"] == 0.0
    assert payload["contact_persistence_min"] == 0.0
    assert payload["initial_clash_count_total"] == 0.0
    assert payload["final_clash_count_total"] == 0.0
    assert payload["clash_relief_count_total"] == 0.0
    assert payload["green_band_condition_text"] == ""
    assert payload["top_k_only_policy_enforced"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
