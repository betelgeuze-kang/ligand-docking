from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_refinement_work_order as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_candidates(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entry_id",
                "family",
                "rank_pct",
                "selected_for_refine",
                "local_min_ligand_rmsd_a",
                "hbond_persistence",
                "contact_persistence",
                "initial_clash_count",
                "clash_count",
            ],
        )
        writer.writeheader()
        writer.writerow({"entry_id": "top-a", "family": "gpcr", "rank_pct": "0.001"})


def _report(rows: list[dict]) -> dict:
    return {
        "summary": {
            "status": "blocked_pocketmd_lite_report",
            "pocketmd_lite_claim_safe": False,
            "top_k_only_policy_enforced": True,
        },
        "rows": rows,
    }


def test_work_order_blocks_missing_top_k_refinement_evidence(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.csv"
    _write_candidates(candidates)
    _write_json(
        report,
        _report(
            [
                {
                    "entry_id": "top-a",
                    "family": "gpcr",
                    "selected_for_refine": True,
                    "band": "abstain",
                    "reason_code": "missing_refinement_evidence",
                    "local_min_ligand_rmsd_a": None,
                    "hbond_persistence": None,
                    "contact_persistence": None,
                    "initial_clash_count": None,
                    "clash_count": None,
                }
            ]
        ),
    )

    payload = mod.build_pocketmd_lite_refinement_work_order(report_json=report, candidate_csv=candidates)

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_refinement_evidence_missing"
    assert summary["selected_top_k_count"] == 1
    assert summary["missing_evidence_candidate_count"] == 1
    assert summary["missing_required_metric_count"] == 5
    assert summary["missing_metric_names"] == [
        "clash_count",
        "contact_persistence",
        "hbond_persistence",
        "initial_clash_count",
        "local_min_ligand_rmsd_a",
    ]
    row = payload["rows"][0]
    assert row["action_type"] == "fill_refinement_evidence"
    assert row["missing_metrics"] == (
        "local_min_ligand_rmsd_a;hbond_persistence;contact_persistence;initial_clash_count;clash_count"
    )
    assert row["execution_enabled"] is False
    assert row["external_state_mutated"] is False


def test_work_order_ready_when_green_top_k_evidence_complete(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.csv"
    _write_candidates(candidates)
    _write_json(
        report,
        {
            "summary": {
                "status": "pocketmd_lite_report_ready",
                "pocketmd_lite_claim_safe": True,
                "top_k_only_policy_enforced": True,
            },
            "rows": [
                {
                    "entry_id": "top-a",
                    "family": "gpcr",
                    "selected_for_refine": True,
                    "band": "green",
                    "reason_code": "",
                    "local_min_ligand_rmsd_a": 1.1,
                    "hbond_persistence": 0.75,
                    "contact_persistence": 0.8,
                    "initial_clash_count": 2,
                    "clash_count": 0,
                }
            ],
        },
    )

    payload = mod.build_pocketmd_lite_refinement_work_order(report_json=report, candidate_csv=candidates)

    assert payload["summary"]["status"] == "pocketmd_lite_refinement_work_order_ready"
    assert payload["summary"]["missing_required_metric_count"] == 0
    assert payload["summary"]["missing_metric_names"] == []
    assert payload["rows"][0]["action_type"] == "no_action_required"


def test_work_order_summary_names_only_remaining_partial_metrics(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.csv"
    _write_candidates(candidates)
    _write_json(
        report,
        _report(
            [
                {
                    "entry_id": "top-a",
                    "family": "gpcr",
                    "selected_for_refine": True,
                    "band": "abstain",
                    "reason_code": "missing_refinement_evidence",
                    "contact_persistence": 1.0,
                    "clash_count": 0,
                }
            ]
        ),
    )

    payload = mod.build_pocketmd_lite_refinement_work_order(report_json=report, candidate_csv=candidates)

    assert payload["summary"]["missing_required_metric_count"] == 3
    assert payload["summary"]["missing_metric_names"] == [
        "hbond_persistence",
        "initial_clash_count",
        "local_min_ligand_rmsd_a",
    ]
    assert "hbond_persistence, initial_clash_count, local_min_ligand_rmsd_a" in payload["summary"][
        "next_required_step"
    ]


def test_work_order_requires_review_for_complete_non_green_band(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.csv"
    _write_candidates(candidates)
    _write_json(
        report,
        {
            "summary": {"status": "blocked_pocketmd_lite_report", "top_k_only_policy_enforced": True},
            "rows": [
                {
                    "entry_id": "top-a",
                    "family": "gpcr",
                    "selected_for_refine": True,
                    "band": "yellow",
                    "reason_code": "weak_hbond_persistence",
                    "local_min_ligand_rmsd_a": 1.1,
                    "hbond_persistence": 0.45,
                    "contact_persistence": 0.8,
                    "initial_clash_count": 2,
                    "clash_count": 0,
                }
            ],
        },
    )

    payload = mod.build_pocketmd_lite_refinement_work_order(report_json=report, candidate_csv=candidates)

    assert payload["summary"]["status"] == "blocked_pocketmd_lite_refinement_review_required"
    assert payload["rows"][0]["action_type"] == "review_uncertainty_band"


def test_work_order_fail_closed_on_missing_report(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    _write_candidates(candidates)

    payload = mod.build_pocketmd_lite_refinement_work_order(
        report_json=tmp_path / "missing.json",
        candidate_csv=candidates,
    )

    assert payload["summary"]["status"] == "blocked_missing_pocketmd_lite_report"
    assert payload["summary"]["materializer_status"] == "blocked_missing_report_json"
    assert payload["rows"][0]["action_type"] == "fill_refinement_evidence"


def test_main_writes_work_order_artifacts(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_candidates(candidates)
    _write_json(
        report,
        _report(
            [
                {
                    "entry_id": "top-a",
                    "family": "gpcr",
                    "selected_for_refine": True,
                    "band": "abstain",
                    "reason_code": "missing_refinement_evidence",
                }
            ]
        ),
    )

    rc = mod.main(
        [
            "--report-json",
            str(report),
            "--candidate-csv",
            str(candidates),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == (
        "blocked_pocketmd_lite_refinement_evidence_missing"
    )
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Refinement Work Order")
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["action_type"] == "fill_refinement_evidence"
