from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_follow_on_blocker_decomposition as mod


ROOT = Path(__file__).resolve().parents[2]


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_aqp1_follow_on_blocker_decomposition_build_payload_reads_current_artifacts() -> None:
    subprocess.run(
        [sys.executable, "tools/build_aqp1_first_wave_follow_on_packet.py"],
        cwd=ROOT,
        check=True,
    )
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
    )

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}

    assert summary["status"] == "aqp1_follow_on_blocker_decomposition_ready"
    assert summary["row_count"] == 2
    assert summary["blocker_count"] == 2
    assert summary["blocker_row_count"] == 2
    assert summary["hard_blocker_count"] == 2
    assert summary["follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["follow_on_lane_label"] == "core_binder_02/03"
    assert summary["primary_blocker_target"] == "core_binder_02"
    assert summary["primary_blocker_id"] == "no_claim_safe_aqp1_binding_kcal_curated"
    assert summary["exact_human_activity_blocker_count"] == 1
    assert summary["local_binder_evidence_blocker_count"] == 1
    assert summary["exact_human_nonbinding_count"] == 1
    assert summary["exact_target_pair_absent_count"] == 1
    assert summary["high_or_medium_potential_count"] == 1
    assert summary["claim_safe_kcal_ready_count"] == 0
    assert summary["claim_safe_binding_kcal_missing_row_count"] == 2
    assert summary["primary_focus_ligand"] == "AqB013"
    assert summary["exact_human_guardrail_ligand"] == "AqB013"
    assert summary["blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["primary_blocker_reason"].startswith("AqB013 carries exact human AQP1 activity")
    _contains_tokens(summary["next_required_step"], "aqb013", "aqb011", "review-only")

    row1 = rows["core_binder_02"]
    assert row1["blocker_id"] == "no_claim_safe_aqp1_binding_kcal_curated"
    assert row1["claim_safe_binding_kcal_ready"] == "no"
    assert row1["seed_blocked_field_count"] == 1
    assert row1["fill_blocked_field_count"] == 1
    assert row1["sync_unresolved_field_count"] == 1
    _contains_tokens(
        row1["reason_components"],
        "exact_human_activity_present",
        "functional_not_direct_binding",
        "claim_safe_binding_kcal_missing",
    )
    _contains_tokens(row1["blocker_reason"], "exact human", "functional-only", "replacement_reference_binding_kcal_mol")
    _contains_tokens(
        row1["current_signal"],
        "public_provenance_status=exact_human_aqp1_quantitative_activity_present_nonbinding",
        "claim_safe_binding_kcal_ready=no",
        "state_change_potential=medium",
    )
    assert "aqp1_first_seed_row_packet_core_binder_02_current.md" in row1["supporting_artifacts"]
    assert "aqp1_quantitative_provenance_packet_current.md" in row1["supporting_artifacts"]

    row2 = rows["core_binder_03"]
    assert row2["blocker_id"] == "no_local_aqp1_binder_evidence_curated"
    assert row2["chembl_activity_record_count"] == 0
    assert row2["seed_blocked_field_count"] == 1
    assert row2["sync_unresolved_field_count"] == 1
    _contains_tokens(
        row2["reason_components"],
        "pubchem_resolved_only",
        "exact_chembl_pair_absent",
        "claim_safe_binding_kcal_missing",
    )
    _contains_tokens(row2["blocker_reason"], "pubchem", "exact chembl", "replacement_reference_binding_kcal_mol")
    _contains_tokens(
        row2["current_signal"],
        "public_provenance_status=pubchem_resolved_chembl_target_pair_absent",
        "claim_safe_binding_kcal_ready=no",
        "state_change_potential=low",
    )
    assert "aqp1_first_seed_row_packet_core_binder_03_current.md" in row2["supporting_artifacts"]
    assert "aqp1_quantitative_provenance_packet_current.md" in row2["supporting_artifacts"]


def test_build_aqp1_follow_on_blocker_decomposition_cli(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "tools/build_aqp1_first_wave_follow_on_packet.py"],
        cwd=ROOT,
        check=True,
    )
    out_json = tmp_path / "aqp1_follow_on_blocker_decomposition.json"
    out_csv = tmp_path / "aqp1_follow_on_blocker_decomposition.csv"
    out_md = tmp_path / "aqp1_follow_on_blocker_decomposition.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_follow_on_blocker_decomposition.py",
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
    assert payload["summary"]["status"] == "aqp1_follow_on_blocker_decomposition_ready"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["blocker_row_count"] == 2
    assert payload["rows"][0]["packet_step"] == "core_binder_02"
    assert payload["rows"][1]["packet_step"] == "core_binder_03"
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Follow-On Blocker Decomposition")
