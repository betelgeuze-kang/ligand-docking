from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_negative_evidence_target_packets as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_transporter_negative_evidence_target_packets_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_negative_reviewer_day_plan_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_review_handoff_packet_current.json").read_text(encoding="utf-8")),
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
                "primary_focus_ligand": "tetraethylammonium",
                "exact_target_pair_absent_count": 2,
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
                "row_count": 3,
                "top_packet_step": "core_non_binder_01",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                "row_count": 3,
                "primary_query_label": "pressure_induced_hemolysis_reinvestigation",
                "primary_anchor_pmid": "23123479",
            }
        },
        json.loads((ROOT / "runs/glut1_second_wave_source_confirmation_packet_current.json").read_text(encoding="utf-8")),
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "row_count": 3,
                "primary_anchor_pmid": "23123479",
                "boundary_positive_pmid": "40359885",
                "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md",
                "row_count": 3,
                "top_packet_step": "core_non_binder_01",
                "primary_anchor_pmid": "23123479",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md",
                "row_count": 4,
                "primary_frontier_candidate": "sodium nitroprusside",
                "exact_target_pair_absent_count": 4,
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
                "row_count": 2,
                "primary_frontier_candidate": "sodium nitroprusside",
                "solvent_fallback_candidate": "dimethyl sulfoxide",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                "row_count": 1,
                "primary_probe_candidate": "sodium nitroprusside",
                "source_anchor_pmid": "23123479",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_exact_source_outcome_packet_current.md",
                "row_count": 4,
                "almost_unaffected_candidate_count": 2,
                "primary_negative_probe_candidate": "sodium nitroprusside",
                "small_inhibitor_signal_candidate": "dimethyl sulfoxide",
                "source_pmid": "23123479",
                "direct_negative_quantitative_row_found_count": 0,
                "authoritative_negative_apply_allowed_count": 0,
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "row_count": 1,
                "primary_probe_candidate": "sodium nitroprusside",
                "solvent_fallback_candidate": "dimethyl sulfoxide",
                "source_anchor_hemolysis_outcome": "almost_unaffected_at_200_mpa",
                "source_anchor_direct_negative_quantitative_row_found": False,
                "resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_direct_evidence_audit_packet_current.md",
                "pubmed_exact_ligand_target_hit_count": 8,
                "chembl_exact_target_pair_activity_count": 0,
                "direct_negative_quantitative_row_found_count": 0,
                "no_direct_negative_source_row_count": 3,
                "audit_decision": "keep_review_only_no_authoritative_negative_promotion",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/glut1_negative_direct_evidence_audit_packet_current.md",
                "placeholder_negative_candidate_count": 3,
                "source_context_positive_or_binder_candidate_count": 3,
                "positive_exact_target_pair_activity_record_count": 5,
                "direct_negative_quantitative_row_found_count": 0,
                "audit_decision": "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion",
            }
        },
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["target_count"] == 2
    assert summary["queue_row_count"] == 6
    assert summary["top_target_id"] == "AQP1"
    assert summary["top_queue_rank_start"] == 1
    assert summary["top_queue_rank_end"] == 3
    assert summary["aqp1_negative_slot_count"] == 3
    assert summary["glut1_negative_slot_count"] == 3
    assert summary["aqp1_source_context_artifact"] == "runs/aqp1_negative_source_exclusion_packet_current.md"
    assert summary["aqp1_exact_target_pair_absent_count"] == 2
    assert summary["aqp1_slot_closure_artifact"] == "runs/aqp1_negative_slot_closure_packet_current.md"
    assert summary["aqp1_slot_closure_row_count"] == 3
    assert summary["aqp1_slot_closure_top_packet_step"] == "core_non_binder_01"
    assert summary["aqp1_negative_acquisition_artifact"] == "runs/aqp1_negative_evidence_acquisition_packet_current.md"
    assert summary["aqp1_negative_acquisition_row_count"] == 3
    assert summary["aqp1_negative_acquisition_primary_query_label"] == "pressure_induced_hemolysis_reinvestigation"
    assert summary["aqp1_negative_acquisition_primary_anchor_pmid"] == "23123479"
    assert summary["aqp1_negative_confirmation_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert summary["aqp1_negative_confirmation_row_count"] == 3
    assert summary["aqp1_negative_confirmation_primary_anchor_pmid"] == "23123479"
    assert summary["aqp1_negative_confirmation_boundary_positive_pmid"] == "40359885"
    assert summary["aqp1_negative_confirmation_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert summary["aqp1_negative_slot_resolution_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert summary["aqp1_negative_slot_resolution_row_count"] == 3
    assert summary["aqp1_negative_slot_resolution_top_packet_step"] == "core_non_binder_01"
    assert summary["aqp1_negative_slot_resolution_primary_anchor_pmid"] == "23123479"
    assert summary["aqp1_negative_candidate_frontier_artifact"] == "runs/aqp1_negative_candidate_frontier_packet_current.md"
    assert summary["aqp1_negative_candidate_frontier_row_count"] == 4
    assert summary["aqp1_negative_candidate_frontier_primary_frontier_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_candidate_frontier_exact_target_pair_absent_count"] == 4
    assert summary["aqp1_negative_frontier_resolution_artifact"] == "runs/aqp1_negative_frontier_resolution_packet_current.md"
    assert summary["aqp1_negative_frontier_resolution_row_count"] == 2
    assert summary["aqp1_negative_frontier_resolution_primary_frontier_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_frontier_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert summary["aqp1_negative_primary_probe_artifact"] == "runs/aqp1_negative_primary_probe_packet_current.md"
    assert summary["aqp1_negative_primary_probe_row_count"] == 1
    assert summary["aqp1_negative_primary_probe_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_primary_probe_source_anchor_pmid"] == "23123479"
    assert summary["aqp1_negative_exact_source_outcome_artifact"] == "runs/aqp1_negative_exact_source_outcome_packet_current.md"
    assert summary["aqp1_negative_exact_source_outcome_row_count"] == 4
    assert summary["aqp1_negative_exact_source_almost_unaffected_candidate_count"] == 2
    assert summary["aqp1_negative_exact_source_primary_probe_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_exact_source_small_inhibitor_signal_candidate"] == "dimethyl sulfoxide"
    assert summary["aqp1_negative_exact_source_source_pmid"] == "23123479"
    assert summary["aqp1_negative_exact_source_direct_negative_quantitative_row_found_count"] == 0
    assert summary["aqp1_negative_exact_source_authoritative_negative_apply_allowed_count"] == 0
    assert summary["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert summary["aqp1_negative_primary_probe_resolution_row_count"] == 1
    assert summary["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert summary["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert (
        summary["aqp1_negative_primary_probe_resolution_source_anchor_hemolysis_outcome"]
        == "almost_unaffected_at_200_mpa"
    )
    assert summary["aqp1_negative_primary_probe_resolution_source_anchor_direct_negative_quantitative_row_found"] is False
    assert summary["aqp1_negative_direct_evidence_audit_artifact"] == "runs/aqp1_negative_direct_evidence_audit_packet_current.md"
    assert summary["aqp1_negative_direct_evidence_audit_pubmed_exact_ligand_target_hit_count"] == 8
    assert summary["aqp1_negative_direct_evidence_audit_chembl_exact_target_pair_activity_count"] == 0
    assert summary["aqp1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count"] == 0
    assert summary["aqp1_negative_direct_evidence_audit_no_direct_negative_source_row_count"] == 3
    assert summary["aqp1_negative_direct_evidence_audit_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert summary["glut1_source_context_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_negative_direct_evidence_audit_artifact"] == "runs/glut1_negative_direct_evidence_audit_packet_current.md"
    assert summary["glut1_negative_direct_evidence_audit_placeholder_negative_candidate_count"] == 3
    assert summary["glut1_negative_direct_evidence_audit_source_context_positive_or_binder_candidate_count"] == 3
    assert summary["glut1_negative_direct_evidence_audit_positive_exact_target_pair_activity_record_count"] == 5
    assert summary["glut1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count"] == 0
    assert summary["glut1_negative_direct_evidence_audit_decision"] == "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion"
    assert rows[0]["target_id"] == "AQP1"
    assert rows[0]["primary_artifact"] == "runs/aqp1_negative_slot_closure_packet_current.md"
    assert rows[0]["secondary_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert rows[0]["source_context_artifact"] == "runs/aqp1_negative_source_exclusion_packet_current.md"
    assert rows[0]["queue_rank_start"] == 1
    assert rows[0]["queue_rank_end"] == 3
    assert rows[1]["target_id"] == "GLUT1"
    assert rows[1]["primary_artifact"] == "runs/glut1_negative_review_handoff_packet_current.md"
    assert rows[1]["source_context_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"


def test_build_transporter_negative_evidence_target_packets_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "target_packets.json"
    out_csv = tmp_path / "target_packets.csv"
    out_md = tmp_path / "target_packets.md"
    aqp1_source_exclusion_json = tmp_path / "aqp1_negative_source_exclusion.json"
    aqp1_slot_closure_json = tmp_path / "aqp1_negative_slot_closure.json"
    aqp1_acquisition_json = tmp_path / "aqp1_negative_evidence_acquisition.json"
    aqp1_confirmation_json = tmp_path / "aqp1_negative_evidence_confirmation.json"
    aqp1_slot_resolution_json = tmp_path / "aqp1_negative_slot_resolution.json"
    aqp1_candidate_frontier_json = tmp_path / "aqp1_negative_candidate_frontier.json"
    aqp1_frontier_resolution_json = tmp_path / "aqp1_negative_frontier_resolution.json"
    aqp1_primary_probe_json = tmp_path / "aqp1_negative_primary_probe.json"
    aqp1_exact_source_outcome_json = tmp_path / "aqp1_negative_exact_source_outcome.json"
    aqp1_primary_probe_resolution_json = tmp_path / "aqp1_negative_primary_probe_resolution.json"
    aqp1_direct_evidence_audit_json = tmp_path / "aqp1_negative_direct_evidence_audit.json"
    glut1_direct_evidence_audit_json = tmp_path / "glut1_negative_direct_evidence_audit.json"
    aqp1_source_exclusion_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
                    "primary_focus_ligand": "tetraethylammonium",
                    "exact_target_pair_absent_count": 2,
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_slot_closure_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
                    "row_count": 3,
                    "top_packet_step": "core_non_binder_01",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_acquisition_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                    "row_count": 3,
                    "primary_query_label": "pressure_induced_hemolysis_reinvestigation",
                    "primary_anchor_pmid": "23123479",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_confirmation_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                    "row_count": 3,
                    "primary_anchor_pmid": "23123479",
                    "boundary_positive_pmid": "40359885",
                    "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_slot_resolution_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md",
                    "row_count": 3,
                    "top_packet_step": "core_non_binder_01",
                    "primary_anchor_pmid": "23123479",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_candidate_frontier_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md",
                    "row_count": 4,
                    "primary_frontier_candidate": "sodium nitroprusside",
                    "exact_target_pair_absent_count": 4,
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_frontier_resolution_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
                    "row_count": 2,
                    "primary_frontier_candidate": "sodium nitroprusside",
                    "solvent_fallback_candidate": "dimethyl sulfoxide",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_primary_probe_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                    "row_count": 1,
                    "primary_probe_candidate": "sodium nitroprusside",
                    "source_anchor_pmid": "23123479",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_exact_source_outcome_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_exact_source_outcome_packet_current.md",
                    "row_count": 4,
                    "almost_unaffected_candidate_count": 2,
                    "primary_negative_probe_candidate": "sodium nitroprusside",
                    "small_inhibitor_signal_candidate": "dimethyl sulfoxide",
                    "source_pmid": "23123479",
                    "direct_negative_quantitative_row_found_count": 0,
                    "authoritative_negative_apply_allowed_count": 0,
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_primary_probe_resolution_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                    "row_count": 1,
                    "primary_probe_candidate": "sodium nitroprusside",
                    "solvent_fallback_candidate": "dimethyl sulfoxide",
                    "source_anchor_hemolysis_outcome": "almost_unaffected_at_200_mpa",
                    "source_anchor_direct_negative_quantitative_row_found": False,
                    "resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_direct_evidence_audit_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_direct_evidence_audit_packet_current.md",
                    "pubmed_exact_ligand_target_hit_count": 8,
                    "chembl_exact_target_pair_activity_count": 0,
                    "direct_negative_quantitative_row_found_count": 0,
                    "no_direct_negative_source_row_count": 3,
                    "audit_decision": "keep_review_only_no_authoritative_negative_promotion",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    glut1_direct_evidence_audit_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/glut1_negative_direct_evidence_audit_packet_current.md",
                    "placeholder_negative_candidate_count": 3,
                    "source_context_positive_or_binder_candidate_count": 3,
                    "positive_exact_target_pair_activity_record_count": 5,
                    "direct_negative_quantitative_row_found_count": 0,
                    "audit_decision": "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_negative_evidence_target_packets.py",
            "--aqp1-negative-source-exclusion-json",
            str(aqp1_source_exclusion_json),
            "--aqp1-negative-slot-closure-json",
            str(aqp1_slot_closure_json),
            "--aqp1-negative-acquisition-json",
            str(aqp1_acquisition_json),
            "--aqp1-negative-confirmation-json",
            str(aqp1_confirmation_json),
            "--aqp1-negative-slot-resolution-json",
            str(aqp1_slot_resolution_json),
            "--aqp1-negative-candidate-frontier-json",
            str(aqp1_candidate_frontier_json),
            "--aqp1-negative-frontier-resolution-json",
            str(aqp1_frontier_resolution_json),
            "--aqp1-negative-primary-probe-json",
            str(aqp1_primary_probe_json),
            "--aqp1-negative-exact-source-outcome-json",
            str(aqp1_exact_source_outcome_json),
            "--aqp1-negative-primary-probe-resolution-json",
            str(aqp1_primary_probe_resolution_json),
            "--aqp1-negative-direct-evidence-audit-json",
            str(aqp1_direct_evidence_audit_json),
            "--glut1-negative-direct-evidence-audit-json",
            str(glut1_direct_evidence_audit_json),
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
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["aqp1_negative_candidate_frontier_row_count"] == 4
    assert payload["summary"]["aqp1_negative_frontier_resolution_row_count"] == 2
    assert payload["summary"]["aqp1_negative_primary_probe_row_count"] == 1
    assert payload["summary"]["aqp1_negative_exact_source_outcome_row_count"] == 4
    assert payload["summary"]["aqp1_negative_exact_source_almost_unaffected_candidate_count"] == 2
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_row_count"] == 1
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_source_anchor_hemolysis_outcome"] == "almost_unaffected_at_200_mpa"
    assert payload["summary"]["aqp1_negative_direct_evidence_audit_artifact"] == "runs/aqp1_negative_direct_evidence_audit_packet_current.md"
    assert payload["summary"]["aqp1_negative_direct_evidence_audit_no_direct_negative_source_row_count"] == 3
    assert payload["summary"]["glut1_negative_direct_evidence_audit_artifact"] == "runs/glut1_negative_direct_evidence_audit_packet_current.md"
    assert payload["summary"]["glut1_negative_direct_evidence_audit_placeholder_negative_candidate_count"] == 3
    assert payload["rows"][0]["target_id"] == "AQP1"
    assert payload["rows"][0]["primary_artifact"] == "runs/aqp1_negative_slot_closure_packet_current.md"
    assert payload["rows"][0]["secondary_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert out_csv.exists()
    assert out_md.exists()
