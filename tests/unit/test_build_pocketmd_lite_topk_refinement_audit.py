from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_topk_refinement_audit as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _proxy_only_report() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_pocketmd_lite_report",
            "selected_top_k_count": 1,
            "top_k_only_policy_enforced": True,
            "top_k_refinement_evidence_ready": False,
            "local_min_survival_reported_count": 0,
            "hbond_persistence_reported_count": 0,
            "contact_persistence_reported_count": 1,
            "initial_clash_reported_count": 0,
            "final_clash_reported_count": 1,
            "clash_relief_reported_count": 0,
            "high_uncertainty_count": 1,
        },
        "rows": [
            {
                "entry_id": "T:L",
                "selected_for_refine": True,
                "band": "abstain",
                "claim_safe": False,
                "missing_evidence_fields": [
                    "local_min_ligand_rmsd_a",
                    "hbond_persistence",
                    "initial_clash_count",
                ],
                "contact_persistence": 1.0,
                "clash_count": 0,
                "uncertainty_score": 1.0,
                "uncertainty_posture": "missing_refinement_evidence_high_uncertainty",
            }
        ],
    }


def _proxy_probe() -> dict[str, object]:
    return {
        "summary": {"status": "blocked_pocketmd_lite_metric_collection_probe_proxy_only"},
        "rows": [
            {
                "entry_id": "T:L",
                "coarse_local_min_ligand_rmsd_a": 1.4,
                "coarse_local_min_survival_proxy": True,
                "coarse_hbond_persistence_proxy": 0.25,
                "coarse_contact_persistence_proxy": 1.0,
                "coarse_clash_frame_fraction_proxy": 0.0,
                "trajectory_probe_status": "blocked_pocketmd_lite_metric_collection_probe_proxy_only",
                "claim_grade_metric_ready": False,
                "recommended_next_local_action": "generate_claim_grade_metrics",
                "blockers": [
                    "claim_grade_metric_fields_missing:local_min_ligand_rmsd_a,hbond_persistence,initial_clash_count"
                ],
            }
        ],
    }


def _queue() -> dict[str, object]:
    return {
        "summary": {"status": "blocked_pocketmd_lite_remaining_evidence_queue"},
        "rows": [
            {
                "entry_id": "T:L",
                "missing_metrics": "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count",
            }
        ],
    }


def _source_audit() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_pocketmd_lite_claim_grade_metric_source_partial_atomized",
            "exact_metric_source_ready_count": 0,
            "claim_grade_collection_input_ready_count": 0,
            "atomized_protein_source_candidate_count": 1,
            "ligand_atom_source_candidate_count": 0,
            "partial_atomized_protein_only_candidate_count": 1,
            "selected_proxy_only_count": 1,
            "next_required_step": (
                "Recover ligand atom frames for partial atomized inputs and generate exact local-min/H-bond/"
                "initial-clash metrics for every selected top-k row."
            ),
        },
    }


def _fill_preview_ready() -> dict[str, object]:
    return {
        "summary": {
            "status": "pocketmd_lite_candidate_metric_fill_preview_ready",
            "fill_ready_row_count": 1,
            "blocked_fill_row_count": 0,
            "candidate_csv_update_allowed": False,
            "canonical_candidate_csv_mutated": False,
            "preview_candidate_csv": "runs/preview.candidates.csv",
        },
        "preview_candidate_rows": [
            {
                "entry_id": "T:L",
                "selected_for_refine": True,
                "pocketmd_lite_metric_fill_status": "filled_from_claim_grade_probe",
                "local_min_ligand_rmsd_a": "1.1",
                "hbond_persistence": "0.8",
                "contact_persistence": "0.9",
                "initial_clash_count": "2",
                "clash_count": "0",
            }
        ],
    }


def test_audit_reports_proxy_telemetry_but_keeps_claim_grade_blocked(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    probe = tmp_path / "probe.json"
    queue = tmp_path / "queue.json"
    source = tmp_path / "source.json"
    _write_json(report, _proxy_only_report())
    _write_json(probe, _proxy_probe())
    _write_json(queue, _queue())
    _write_json(source, _source_audit())

    payload = mod.build_pocketmd_lite_topk_refinement_audit(
        report_json=report,
        probe_json=probe,
        remaining_queue_json=queue,
        metric_source_audit_json=source,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported"
    assert summary["selected_top_k_count"] == 1
    assert summary["claim_grade_refinement_evidence_ready"] is False
    assert summary["proxy_topk_telemetry_ready"] is True
    assert summary["proxy_local_min_reported_count"] == 1
    assert summary["proxy_local_min_survival_count"] == 1
    assert summary["proxy_hbond_reported_count"] == 1
    assert summary["proxy_contact_reported_count"] == 1
    assert summary["proxy_final_clash_reported_count"] == 1
    assert summary["missing_refinement_metric_counts"] == {
        "hbond_persistence": 1,
        "initial_clash_count": 1,
        "local_min_ligand_rmsd_a": 1,
    }
    assert summary["claim_promotion_allowed"] is False
    assert (
        summary["claim_grade_metric_source_audit_status"]
        == "blocked_pocketmd_lite_claim_grade_metric_source_partial_atomized"
    )
    assert summary["claim_grade_metric_source_exact_ready_count"] == 0
    assert summary["claim_grade_metric_source_atomized_protein_candidate_count"] == 1
    assert summary["claim_grade_metric_source_ligand_atom_candidate_count"] == 0
    assert "Recover ligand atom frames" in summary["next_required_step"]
    row = payload["rows"][0]
    assert row["claim_grade_metric_ready"] is False
    assert row["proxy_local_min_ligand_rmsd_a"] == 1.4
    assert row["proxy_hbond_persistence"] == 0.25
    assert any("claim_grade_metrics_missing" in blocker for blocker in row["blockers"])


def test_audit_overlays_exact_fill_preview_metrics_without_mutating_report(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    probe = tmp_path / "probe.json"
    queue = tmp_path / "queue.json"
    fill_preview = tmp_path / "fill-preview.json"
    _write_json(report, _proxy_only_report())
    _write_json(
        probe,
        {
            "summary": {"status": "pocketmd_lite_metric_collection_probe_ready"},
            "rows": [
                {
                    "entry_id": "T:L",
                    "claim_grade_metric_ready": True,
                    "coarse_local_min_ligand_rmsd_a": 1.1,
                    "coarse_local_min_survival_proxy": True,
                    "coarse_hbond_persistence_proxy": 0.8,
                    "coarse_contact_persistence_proxy": 0.9,
                    "coarse_clash_frame_fraction_proxy": 0.0,
                    "trajectory_probe_status": "pocketmd_lite_metric_collection_probe_ready",
                }
            ],
        },
    )
    _write_json(queue, _queue())
    _write_json(fill_preview, _fill_preview_ready())

    payload = mod.build_pocketmd_lite_topk_refinement_audit(
        report_json=report,
        probe_json=probe,
        remaining_queue_json=queue,
        candidate_fill_preview_json=fill_preview,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported"
    assert summary["candidate_metric_fill_preview_ready"] is True
    assert summary["claim_grade_refinement_evidence_ready"] is True
    assert summary["claim_grade_report_evidence_ready"] is False
    assert summary["claim_grade_metric_ready_count"] == 1
    assert summary["claim_grade_missing_candidate_count"] == 0
    assert summary["missing_refinement_metric_names"] == []
    assert summary["claim_grade_local_min_reported_count"] == 1
    assert summary["claim_grade_local_min_survival_count"] == 1
    assert summary["claim_grade_hbond_reported_count"] == 1
    assert summary["claim_grade_initial_clash_reported_count"] == 1
    assert summary["claim_grade_clash_relief_reported_count"] == 1
    assert "Run the PocketMD Lite report against the metric fill preview candidate CSV" in summary["next_required_step"]

    row = payload["rows"][0]
    assert row["candidate_metric_fill_status"] == "filled_from_claim_grade_probe"
    assert row["claim_grade_metric_ready"] is True
    assert row["claim_grade_missing_metrics"] == []
    assert row["band"] == "green"
    assert row["claim_safe"] is True
    assert row["local_min_ligand_rmsd_a"] == 1.1
    assert row["local_min_survived"] is True
    assert row["hbond_persistence"] == 0.8
    assert row["initial_clash_count"] == 2
    assert row["clash_count"] == 0
    assert row["clash_relief_count"] == 2
    assert row["blockers"] == []

    original_report = json.loads(report.read_text(encoding="utf-8"))
    assert original_report["rows"][0]["missing_evidence_fields"] == [
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "initial_clash_count",
    ]


def test_audit_ready_when_claim_grade_evidence_is_present(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    probe = tmp_path / "probe.json"
    queue = tmp_path / "queue.json"
    _write_json(
        report,
        {
            "summary": {
                "status": "pocketmd_lite_report_ready",
                "selected_top_k_count": 1,
                "top_k_only_policy_enforced": True,
                "top_k_refinement_evidence_ready": True,
                "local_min_survival_reported_count": 1,
                "hbond_persistence_reported_count": 1,
                "contact_persistence_reported_count": 1,
                "initial_clash_reported_count": 1,
                "final_clash_reported_count": 1,
                "clash_relief_reported_count": 1,
            },
            "rows": [
                {
                    "entry_id": "T:L",
                    "selected_for_refine": True,
                    "band": "green",
                    "claim_safe": True,
                    "missing_evidence_fields": [],
                    "local_min_ligand_rmsd_a": 1.1,
                    "hbond_persistence": 0.8,
                    "contact_persistence": 0.9,
                    "initial_clash_count": 2,
                    "clash_count": 0,
                    "clash_relief_count": 2,
                    "uncertainty_score": 0.2,
                    "uncertainty_posture": "green_low_uncertainty",
                }
            ],
        },
    )
    _write_json(
        probe,
        {
            "summary": {"status": "pocketmd_lite_metric_collection_probe_ready"},
            "rows": [
                {
                    "entry_id": "T:L",
                    "claim_grade_metric_ready": True,
                    "coarse_local_min_ligand_rmsd_a": 1.1,
                    "coarse_local_min_survival_proxy": True,
                    "coarse_hbond_persistence_proxy": 0.8,
                    "coarse_contact_persistence_proxy": 0.9,
                    "coarse_clash_frame_fraction_proxy": 0.0,
                }
            ],
        },
    )
    _write_json(queue, {"summary": {"status": "pocketmd_lite_remaining_evidence_queue_ready"}, "rows": []})

    payload = mod.build_pocketmd_lite_topk_refinement_audit(
        report_json=report,
        probe_json=probe,
        remaining_queue_json=queue,
    )

    summary = payload["summary"]
    assert summary["status"] == "pocketmd_lite_topk_refinement_audit_ready"
    assert summary["claim_grade_refinement_evidence_ready"] is True
    assert summary["claim_grade_metric_ready_count"] == 1
    assert summary["missing_refinement_metric_names"] == []
    assert summary["claim_grade_clash_relief_reported_count"] == 1


def test_main_writes_audit_artifacts(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    probe = tmp_path / "probe.json"
    queue = tmp_path / "queue.json"
    source = tmp_path / "source.json"
    out_json = tmp_path / "audit.json"
    out_md = tmp_path / "audit.md"
    out_csv = tmp_path / "audit.csv"
    _write_json(report, _proxy_only_report())
    _write_json(probe, _proxy_probe())
    _write_json(queue, _queue())
    _write_json(source, _source_audit())

    rc = mod.main(
        [
            "--report-json",
            str(report),
            "--probe-json",
            str(probe),
            "--remaining-queue-json",
            str(queue),
            "--metric-source-audit-json",
            str(source),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["packet_type"] == "pocketmd_lite_topk_refinement_audit"
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Top-K Refinement Audit")
    row = list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]
    assert row["proxy_local_min_ligand_rmsd_a"] == "1.4"
