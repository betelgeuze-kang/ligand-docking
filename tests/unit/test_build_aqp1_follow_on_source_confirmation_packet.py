from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_follow_on_source_confirmation_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_aqp1_follow_on_source_confirmation_packet_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
    )

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}

    assert summary["status"] == "aqp1_follow_on_source_confirmation_packet_ready"
    assert summary["row_count"] == 2
    assert summary["follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["follow_on_lane_label"] == "core_binder_02/03"
    assert summary["primary_confirmation_target"] == "core_binder_03"
    assert summary["primary_focus_ligand"] == "AqB011"
    assert summary["source_confirmation_primary_focus_ligand"] == "AqB011"
    assert summary["exact_human_reference_ligand"] == "AqB013"
    assert summary["exact_human_guardrail_ligand"] == "AqB013"
    assert summary["exact_human_activity_confirmation_count"] == 1
    assert summary["exact_target_pair_absent_confirmation_count"] == 1
    assert summary["review_only_follow_on_count"] == 2
    assert summary["claim_safe_kcal_ready_count"] == 0
    assert summary["primary_blocker_target"] == "core_binder_03"
    assert summary["primary_blocker_id"] == "no_local_aqp1_binder_evidence_curated"
    assert summary["follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert summary["blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["quantitative_provenance_packet_artifact"] == "runs/aqp1_quantitative_provenance_packet_current.md"
    assert summary["source_confirmation_packet_artifact"] == "runs/aqp1_follow_on_source_confirmation_packet_current.md"
    _contains_tokens(summary["blocking_signal"], "aqb013", "exact_human_activity_present_leave_kcal_blank", "aqb011")
    _contains_tokens(summary["next_required_step"], "aqb013", "aqb011", "replacement_reference_binding_kcal_mol", "blank")

    row_02 = rows["core_binder_02"]
    assert row_02["confirmation_scope"] == "exact_human_activity_source_confirmation"
    assert row_02["blocker_id"] == "no_claim_safe_aqp1_binding_kcal_curated"
    assert row_02["review_bucket"] == "defer_exact_human_activity_nonbinding"
    assert row_02["next_required_action"] == "carry_exact_human_activity_provenance_keep_kcal_blank"
    _contains_tokens(
        row_02["confirmation_checks"],
        "source_anchor=PMID 22427546",
        "public_provenance_status=exact_human_aqp1_quantitative_activity_present_nonbinding",
        "public_provenance_signal=exact_human_activity_present_leave_kcal_blank",
        "state_change_potential=medium",
        "claim_safe_binding_kcal_ready=no",
        "review_bucket=defer_exact_human_activity_nonbinding",
    )
    _contains_tokens(
        row_02["acceptance_gate"],
        "PMID 22427546",
        "AqB013",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    _contains_tokens(row_02["rejection_gate"], "AqB013", "claim-safe binding", "authoritative apply")
    assert "aqp1_first_wave_follow_on_packet_current.md" in row_02["supporting_artifacts"]
    assert "aqp1_follow_on_blocker_decomposition_current.md" in row_02["supporting_artifacts"]
    assert "aqp1_quantitative_provenance_packet_current.md" in row_02["supporting_artifacts"]

    row_03 = rows["core_binder_03"]
    assert row_03["confirmation_scope"] == "exact_target_pair_absence_source_confirmation"
    assert row_03["blocker_id"] == "no_local_aqp1_binder_evidence_curated"
    assert row_03["review_bucket"] == "defer_pending_target_specific_evidence"
    assert row_03["next_required_action"] == "manual_curated_search_or_defer"
    _contains_tokens(
        row_03["confirmation_checks"],
        "source_anchor=PMID 29755973",
        "public_provenance_status=pubchem_resolved_chembl_target_pair_absent",
        "public_provenance_signal=pubchem_resolved_target_pair_absent",
        "state_change_potential=low",
        "claim_safe_binding_kcal_ready=no",
        "review_bucket=defer_pending_target_specific_evidence",
    )
    _contains_tokens(
        row_03["acceptance_gate"],
        "PMID 29755973",
        "AqB011",
        "exact ChEMBL target-pair absent",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    _contains_tokens(
        row_03["rejection_gate"],
        "AqB011",
        "review-only",
        "exact ChEMBL target pair",
    )


def test_build_aqp1_follow_on_source_confirmation_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_follow_on_source_confirmation_packet.json"
    out_csv = tmp_path / "aqp1_follow_on_source_confirmation_packet.csv"
    out_md = tmp_path / "aqp1_follow_on_source_confirmation_packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_follow_on_source_confirmation_packet.py",
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
    assert payload["summary"]["status"] == "aqp1_follow_on_source_confirmation_packet_ready"
    assert payload["summary"]["row_count"] == 2
    assert payload["rows"][0]["packet_step"] == "core_binder_02"
    assert payload["rows"][1]["packet_step"] == "core_binder_03"
    assert out_csv.read_text(encoding="utf-8").splitlines()[0].startswith("confirmation_rank,")
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Follow-On Source Confirmation Packet")
