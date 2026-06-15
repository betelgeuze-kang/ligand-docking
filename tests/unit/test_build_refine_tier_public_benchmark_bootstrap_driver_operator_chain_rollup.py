from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup as mod


def _write_json(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}) + "\n", encoding="utf-8")


def test_bootstrap_driver_operator_chain_rollup_summarizes_current_blocker() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup()
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
    assert summary["stage_count"] == 5
    assert summary["stage_artifact_present_count"] == 5
    assert summary["operator_chain_surface_ready"] is True
    assert summary["operator_chain_closure_ready"] is False
    assert summary["source_staging_operator_manual_pending_field_count"] == 66
    assert summary["machine_supported_pending_field_count"] == 36
    assert summary["machine_supported_prefilled_field_count"] == 36
    assert summary["operator_only_pending_field_count"] == 30
    assert summary["machine_gap_pending_field_count"] == 0
    assert summary["attestation_blocked_row_count"] == 6
    assert summary["merge_preview_blocked_row_count"] == 6
    assert summary["prefill_row_fingerprint_verified_count"] == 6
    assert summary["prefill_row_fingerprint_mismatch_count"] == 0
    assert summary["merged_candidate_row_count"] == 0
    assert summary["final_blocker_stage_id"] == "attestation_merge_preview"
    assert summary["final_blocker"] == "operator_only_placeholders_unfilled"
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert "operator_chain_closure_not_ready" in summary["blockers"]


def test_bootstrap_driver_operator_chain_rollup_ready_fixture(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    triage = tmp_path / "triage.json"
    prefill = tmp_path / "prefill.json"
    attestation = tmp_path / "attestation.json"
    merge = tmp_path / "merge.json"
    _write_json(
        staging,
        {
            "status": "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply",
            "worksheet_row_count": 1,
            "operator_manual_pending_field_count": 5,
        },
    )
    _write_json(
        triage,
        {
            "status": "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready",
            "row_count": 1,
            "machine_supported_pending_field_count": 6,
            "machine_gap_pending_field_count": 0,
        },
    )
    _write_json(
        prefill,
        {
            "status": "refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_ready",
            "prefill_row_count": 1,
            "machine_supported_prefilled_field_count": 6,
            "machine_remaining_field_count": 0,
        },
    )
    _write_json(
        attestation,
        {
            "status": "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready",
            "attestation_row_count": 1,
            "attestation_pass_row_count": 1,
            "attestation_blocked_row_count": 0,
            "operator_only_pending_field_count": 0,
            "prefill_row_fingerprint_count": 1,
        },
    )
    _write_json(
        merge,
        {
            "status": "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_ready",
            "prefill_row_count": 1,
            "attestation_merge_ready": True,
            "merge_preview_row_count": 1,
            "merge_preview_pass_row_count": 1,
            "merge_preview_blocked_row_count": 0,
            "prefill_row_fingerprint_verified_count": 1,
            "prefill_row_fingerprint_mismatch_count": 0,
            "merged_candidate_row_count": 1,
        },
    )

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup(
        staging_apply_json=staging,
        field_triage_json=triage,
        machine_prefill_json=prefill,
        attestation_json=attestation,
        merge_preview_json=merge,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_ready"
    assert summary["operator_chain_closure_ready"] is True
    assert summary["attestation_merge_ready"] is True
    assert summary["merged_candidate_row_count"] == 1
    assert summary["blocker_count"] == 0
    assert summary["payload_write_allowed"] is False
    assert summary["canonical_receipt_write_allowed"] is False


def test_bootstrap_driver_operator_chain_rollup_cli_writes_outputs(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    triage = tmp_path / "triage.json"
    prefill = tmp_path / "prefill.json"
    attestation = tmp_path / "attestation.json"
    merge = tmp_path / "merge.json"
    out_json = tmp_path / "rollup.json"
    out_csv = tmp_path / "rollup.csv"
    out_md = tmp_path / "rollup.md"
    for path, status in [
        (staging, "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply"),
        (triage, "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready"),
        (prefill, "refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_ready"),
        (attestation, "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready"),
        (merge, "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview"),
    ]:
        _write_json(path, {"status": status})

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--staging-apply-json",
            str(staging),
            "--field-triage-json",
            str(triage),
            "--machine-prefill-json",
            str(prefill),
            "--attestation-json",
            str(attestation),
            "--merge-preview-json",
            str(merge),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["stage_count"] == len(rows)
    assert "R9 Bootstrap Driver Operator Chain Rollup" in out_md.read_text(encoding="utf-8")
