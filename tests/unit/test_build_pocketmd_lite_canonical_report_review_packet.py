from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_canonical_report_review_packet as mod
from tools.product import build_pocketmd_lite_report


def _write_candidate_csv(path: Path, *, filled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_id",
        "family",
        "rank_pct",
        "selected_for_refine",
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "contact_persistence",
        "clash_count",
        "initial_clash_count",
        "pocketmd_lite_metric_fill_status",
        "pocketmd_lite_metric_fill_source_npz",
    ]
    row = {
        "entry_id": "T:L",
        "family": "gpcr",
        "rank_pct": "0.0001",
        "selected_for_refine": "true",
        "local_min_ligand_rmsd_a": "1.1" if filled else "",
        "hbond_persistence": "0.7" if filled else "",
        "contact_persistence": "1.0",
        "clash_count": "0",
        "initial_clash_count": "4" if filled else "",
        "pocketmd_lite_metric_fill_status": "filled_from_claim_grade_probe" if filled else "",
        "pocketmd_lite_metric_fill_source_npz": "runs/bounded_metrics.npz" if filled else "",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_report(path: Path, csv_path: Path) -> dict:
    payload = build_pocketmd_lite_report.build_pocketmd_lite_report_artifact(csv_path)
    _write_json(path, payload)
    return payload


def _fill_preview_payload(preview_csv: Path, *, ready: bool = True) -> dict:
    rows = list(csv.DictReader(preview_csv.open(encoding="utf-8")))
    return {
        "summary": {
            "status": (
                "pocketmd_lite_candidate_metric_fill_preview_ready"
                if ready
                else "blocked_pocketmd_lite_candidate_metric_fill_preview"
            ),
            "fill_ready_row_count": 1 if ready else 0,
            "blocked_fill_row_count": 0 if ready else 1,
            "candidate_csv_update_allowed": False,
            "canonical_candidate_csv_mutated": False,
        },
        "preview_candidate_rows": rows,
    }


def _metric_source_audit_payload(*, ready: bool = True) -> dict:
    return {
        "summary": {
            "status": (
                "pocketmd_lite_claim_grade_metric_source_audit_ready"
                if ready
                else "blocked_pocketmd_lite_claim_grade_metric_source_audit"
            ),
            "candidate_count": 1,
            "exact_metric_source_ready_count": 1 if ready else 0,
            "missing_exact_metric_source_count": 0 if ready else 1,
            "candidate_csv_update_allowed": False,
        }
    }


def test_canonical_report_review_packet_prepares_read_only_update_review(tmp_path: Path) -> None:
    canonical_csv = tmp_path / "canonical.csv"
    preview_csv = tmp_path / "preview.csv"
    canonical_report_json = tmp_path / "canonical_report.json"
    preview_report_json = tmp_path / "preview_report.json"
    fill_preview_json = tmp_path / "fill_preview.json"
    source_audit_json = tmp_path / "source_audit.json"
    _write_candidate_csv(canonical_csv, filled=False)
    _write_candidate_csv(preview_csv, filled=True)
    canonical_before = canonical_csv.read_text(encoding="utf-8")
    canonical_report = _write_report(canonical_report_json, canonical_csv)
    preview_report = _write_report(preview_report_json, preview_csv)
    _write_json(fill_preview_json, _fill_preview_payload(preview_csv))
    _write_json(source_audit_json, _metric_source_audit_payload())

    payload = mod.build_pocketmd_lite_canonical_report_review_packet(
        canonical_report_json=canonical_report_json,
        preview_report_json=preview_report_json,
        candidate_fill_preview_json=fill_preview_json,
        metric_source_audit_json=source_audit_json,
        canonical_candidate_csv=canonical_csv,
        preview_candidate_csv=preview_csv,
    )

    summary = payload["summary"]
    assert canonical_report["summary"]["status"] == "blocked_pocketmd_lite_report"
    assert preview_report["summary"]["status"] == "pocketmd_lite_report_ready"
    assert summary["status"] == "pocketmd_lite_canonical_report_review_packet_ready"
    assert summary["canonical_report_ready"] is False
    assert summary["preview_report_ready"] is True
    assert summary["metric_source_audit_ready"] is True
    assert summary["canonical_update_candidate_row_count"] == 1
    assert summary["operator_approval_required"] is True
    assert summary["candidate_csv_update_allowed"] is False
    assert summary["canonical_candidate_csv_mutated"] is False
    assert summary["claim_promotion_allowed"] is False
    assert canonical_csv.read_text(encoding="utf-8") == canonical_before

    row = payload["rows"][0]
    assert row["canonical_band"] == "abstain"
    assert row["preview_band"] == "green"
    assert row["canonical_missing_metric_names"] == [
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "initial_clash_count",
    ]
    assert row["metric_fill_status"] == "filled_from_claim_grade_probe"
    assert row["metric_source_npz"] == "runs/bounded_metrics.npz"
    assert row["preview_local_min_ligand_rmsd_a"] == 1.1
    assert row["review_ready"] is True
    assert row["candidate_csv_update_allowed"] is False


def test_canonical_report_review_packet_blocks_when_metric_source_audit_not_ready(tmp_path: Path) -> None:
    canonical_csv = tmp_path / "canonical.csv"
    preview_csv = tmp_path / "preview.csv"
    canonical_report_json = tmp_path / "canonical_report.json"
    preview_report_json = tmp_path / "preview_report.json"
    fill_preview_json = tmp_path / "fill_preview.json"
    source_audit_json = tmp_path / "source_audit.json"
    _write_candidate_csv(canonical_csv, filled=False)
    _write_candidate_csv(preview_csv, filled=True)
    _write_report(canonical_report_json, canonical_csv)
    _write_report(preview_report_json, preview_csv)
    _write_json(fill_preview_json, _fill_preview_payload(preview_csv))
    _write_json(source_audit_json, _metric_source_audit_payload(ready=False))

    payload = mod.build_pocketmd_lite_canonical_report_review_packet(
        canonical_report_json=canonical_report_json,
        preview_report_json=preview_report_json,
        candidate_fill_preview_json=fill_preview_json,
        metric_source_audit_json=source_audit_json,
        canonical_candidate_csv=canonical_csv,
        preview_candidate_csv=preview_csv,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_canonical_report_review_packet"
    assert summary["preview_report_ready"] is True
    assert summary["metric_source_audit_ready"] is False
    assert summary["operator_approval_required"] is False
    assert summary["canonical_candidate_csv_mutated"] is False


def test_canonical_report_review_packet_cli_writes_outputs(tmp_path: Path) -> None:
    canonical_csv = tmp_path / "canonical.csv"
    preview_csv = tmp_path / "preview.csv"
    canonical_report_json = tmp_path / "canonical_report.json"
    preview_report_json = tmp_path / "preview_report.json"
    fill_preview_json = tmp_path / "fill_preview.json"
    source_audit_json = tmp_path / "source_audit.json"
    out_json = tmp_path / "packet.json"
    out_md = tmp_path / "packet.md"
    out_csv = tmp_path / "packet.csv"
    _write_candidate_csv(canonical_csv, filled=False)
    _write_candidate_csv(preview_csv, filled=True)
    _write_report(canonical_report_json, canonical_csv)
    _write_report(preview_report_json, preview_csv)
    _write_json(fill_preview_json, _fill_preview_payload(preview_csv))
    _write_json(source_audit_json, _metric_source_audit_payload())

    rc = mod.main(
        [
            "--canonical-report-json",
            str(canonical_report_json),
            "--preview-report-json",
            str(preview_report_json),
            "--candidate-fill-preview-json",
            str(fill_preview_json),
            "--metric-source-audit-json",
            str(source_audit_json),
            "--canonical-candidate-csv",
            str(canonical_csv),
            "--preview-candidate-csv",
            str(preview_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["packet_type"] == (
        "pocketmd_lite_canonical_report_review_packet"
    )
    assert out_md.read_text(encoding="utf-8").startswith(
        "# PocketMD Lite Canonical Report Review Packet"
    )
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["review_ready"] == "true"
