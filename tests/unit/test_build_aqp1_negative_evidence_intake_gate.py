from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_evidence_intake_gate as mod


ROOT = Path(__file__).resolve().parents[2]


def _request_payload() -> dict[str, object]:
    return {
        "summary": {
            "evidence_request_ready": True,
            "packet_artifact": "runs/aqp1_negative_evidence_request_packet_current.md",
            "target_id": "AQP1",
            "target_uniprot_accession": "P29972",
            "target_chembl_id": "CHEMBL4523210",
            "request_row_count": 3,
            "required_assignable_negative_row_count": 3,
            "public_reinterpretation_exhausted": True,
            "internal_wetlab_or_primary_source_required": True,
        },
        "rows": [
            {
                "request_rank": 1,
                "slot_queue_id": "AQP1__core_non_binder_01",
                "packet_step": "core_non_binder_01",
                "target_id": "AQP1",
                "target_uniprot_accession": "P29972",
                "target_chembl_id": "CHEMBL4523210",
                "candidate_scope": "sodium nitroprusside",
            },
            {
                "request_rank": 2,
                "slot_queue_id": "AQP1__core_non_binder_02",
                "packet_step": "core_non_binder_02",
                "target_id": "AQP1",
                "target_uniprot_accession": "P29972",
                "target_chembl_id": "CHEMBL4523210",
                "candidate_scope": "independent_exact_aqp1_nonbinder_candidate_01",
            },
            {
                "request_rank": 3,
                "slot_queue_id": "AQP1__core_non_binder_03",
                "packet_step": "core_non_binder_03",
                "target_id": "AQP1",
                "target_uniprot_accession": "P29972",
                "target_chembl_id": "CHEMBL4523210",
                "candidate_scope": "independent_exact_aqp1_nonbinder_candidate_02",
            },
        ],
    }


def _valid_row(slot_id: str, idx: int) -> dict[str, str]:
    return {
        "slot_queue_id": slot_id,
        "request_rank": str(idx),
        "packet_step": f"core_non_binder_0{idx}",
        "target_id": "AQP1",
        "target_accession": "P29972",
        "target_chembl_id": "CHEMBL4523210",
        "target_organism": "Homo sapiens",
        "candidate_scope": f"independent_exact_aqp1_nonbinder_candidate_0{idx}",
        "candidate_name": f"Internal AQP1 weak-effect control {idx}",
        "molecule_id": f"INT-AQP1-NEG-{idx:03d}",
        "assay_context": "human AQP1 proteoliposome water-flux assay",
        "endpoint": "water_permeability_inhibition_percent",
        "standard_type": "Activity",
        "standard_relation": "<=",
        "standard_value": "5",
        "standard_units": "percent",
        "concentration_or_curve_range": "1-100 uM",
        "replicate_or_error_model": "n=3; mean with replicate SD retained in source packet",
        "primary_source": "internal_wetlab_assay",
        "source_id": f"INT:AQP1-NEG-2026-{idx:03d}",
        "split_id": f"aqp1_negative_validation_split_v1_row_{idx}",
        "reference_meta_id": f"aqp1_negative_reference_meta_v1_row_{idx}",
        "negative_semantics": "no_effect",
        "curator_decision": "ready_for_authoritative_negative_review",
        "curator_notes": "Synthetic unit-test row; not a repo evidence claim.",
    }


def test_build_aqp1_negative_evidence_intake_gate_blank_template_waits_for_evidence() -> None:
    template_rows = mod.build_template_rows(_request_payload())

    payload = mod.build_payload(_request_payload(), template_rows)

    summary = payload["summary"]
    assert summary["intake_gate_ready"] is True
    assert summary["request_artifact"] == "runs/aqp1_negative_evidence_request_packet_current.md"
    assert summary["target_id"] == "AQP1"
    assert summary["target_uniprot_accession"] == "P29972"
    assert summary["target_chembl_id"] == "CHEMBL4523210"
    assert summary["intake_row_count"] == 3
    assert summary["intake_row_with_data_count"] == 0
    assert summary["valid_intake_row_count"] == 0
    assert summary["exact_negative_quantitative_row_count"] == 0
    assert summary["primary_source_verified_count"] == 0
    assert summary["required_assignable_negative_row_count"] == 3
    assert summary["missing_valid_intake_row_count"] == 3
    assert summary["product_scope_evidence_status"] == "blocked_product_scope_transporter_negative_quantitative_evidence"
    assert summary["transporter_negative_quantitative_evidence_ready"] is False
    assert summary["primary_source_negative_evidence_ready"] is False
    assert summary["exact_negative_quantitative_value_ready"] is False
    assert summary["negative_evidence_gap_open"] is True
    assert summary["functional_surrogate_promoted_to_negative"] is False
    assert summary["intake_gate_complete"] is False
    assert summary["negative_evidence_closure_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert "missing_candidate_name" in payload["rows"][0]["issue_codes"]


def test_build_aqp1_negative_evidence_intake_gate_accepts_three_exact_rows_for_review_only() -> None:
    rows = [_valid_row(f"AQP1__core_non_binder_0{idx}", idx) for idx in range(1, 4)]

    payload = mod.build_payload(_request_payload(), rows)

    summary = payload["summary"]
    assert summary["valid_intake_row_count"] == 3
    assert summary["exact_negative_quantitative_row_count"] == 3
    assert summary["primary_source_verified_count"] == 3
    assert summary["missing_valid_intake_row_count"] == 0
    assert summary["review_ready_row_count"] == 3
    assert summary["intake_gate_complete"] is True
    assert summary["product_scope_evidence_status"] == "product_scope_transporter_negative_quantitative_evidence_ready"
    assert summary["transporter_negative_quantitative_evidence_ready"] is True
    assert summary["primary_source_negative_evidence_ready"] is True
    assert summary["exact_negative_quantitative_value_ready"] is True
    assert summary["negative_evidence_gap_open"] is False
    assert summary["functional_surrogate_promoted_to_negative"] is False
    assert summary["split_reference_meta_update_required"] is True
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert all(row["row_valid_for_authoritative_negative_review"] is True for row in payload["rows"])


def test_build_aqp1_negative_evidence_intake_gate_rejects_review_only_and_shortcut_context() -> None:
    row = _valid_row("AQP1__core_non_binder_01", 1)
    row["candidate_name"] = "tetraethylammonium"
    row["primary_source"] = "PMID:23123479 review-only context"
    row["source_id"] = "PMID:23123479"

    payload = mod.build_payload(_request_payload(), [row])

    summary = payload["summary"]
    assert summary["valid_intake_row_count"] == 0
    assert summary["missing_valid_intake_row_count"] == 3
    assert "excluded_shortcut_context" in payload["rows"][0]["issue_codes"]
    assert "review_only_source_context" in payload["rows"][0]["issue_codes"]


def test_build_aqp1_negative_evidence_intake_gate_accepts_primary_pmid_23123479_acetazolamide_row() -> None:
    row = _valid_row("AQP1__core_non_binder_03", 3)
    row["candidate_name"] = "acetazolamide"
    row["molecule_id"] = "CHEMBL20|PubChem:1986"
    row["assay_context"] = "human erythrocyte pressure-induced hemolysis attributed to AQP1 water transport"
    row["endpoint"] = "pressure_induced_hemolysis_percent_at_200_mpa"
    row["standard_type"] = "Hemolysis"
    row["standard_relation"] = "="
    row["standard_value"] = "39.0"
    row["standard_units"] = "percent"
    row["primary_source"] = "primary_journal_article:Biol Pharm Bull 2012; PMID:23123479"
    row["source_id"] = "PMID:23123479; DOI:10.1248/bpb.b12-00581"
    row["negative_semantics"] = "no_transport_effect"

    payload = mod.build_payload(_request_payload(), [row])

    assert payload["summary"]["valid_intake_row_count"] == 1
    assert payload["summary"]["exact_negative_quantitative_row_count"] == 1
    assert payload["summary"]["primary_source_verified_count"] == 1
    assert payload["summary"]["transporter_negative_quantitative_evidence_ready"] is False
    assert payload["summary"]["primary_source_negative_evidence_ready"] is True
    assert payload["summary"]["exact_negative_quantitative_value_ready"] is True
    assert payload["summary"]["negative_evidence_gap_open"] is False
    assert payload["rows"][0]["issue_codes"] == ""


def test_build_aqp1_negative_evidence_intake_gate_cli(tmp_path: Path) -> None:
    request_json = tmp_path / "request.json"
    intake_csv = tmp_path / "intake.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    request_json.write_text(json.dumps(_request_payload()), encoding="utf-8")
    rows = [_valid_row(f"AQP1__core_non_binder_0{idx}", idx) for idx in range(1, 4)]
    with intake_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_evidence_intake_gate.py",
            "--request-json",
            str(request_json),
            "--intake-csv",
            str(intake_csv),
            "--template-csv",
            str(template_csv),
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

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["valid_intake_row_count"] == 3
    assert template_csv.exists()
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Negative Evidence Intake Gate")
