from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_seeded_metric_payload_receipt_backfill_validates_existing_payloads(tmp_path: Path) -> None:
    ligand = tmp_path / "ligand.sdf"
    receptor = tmp_path / "receptor.pdb"
    ligand.write_text("ligand\n", encoding="utf-8")
    receptor.write_text("ATOM\n", encoding="utf-8")
    metric_path = tmp_path / "metric.json"
    _write_json(
        metric_path,
        {
            "metric_name": "dockq",
            "target_id": "2j7h",
            "pose_id": "2j7h_48",
            "value": 0.7,
            "method": "internal_proxy",
            "input_artifacts": [str(ligand), str(receptor)],
            "input_artifact_sha256s": [_sha(ligand), _sha(receptor)],
            "operator_id": "local",
            "reviewed_at_utc": "2026-06-14T00:00:00Z",
            "license_ok": True,
            "external_engine_calls": 0,
        },
    )
    priority_json = tmp_path / "priority.json"
    _write_json(
        priority_json,
        {
            "summary": {"locked_cv_model_id": "m", "locked_cv_bootstrap_p05": 0.4},
            "priority_rows": [
                {
                    "payload_priority_rank": 4,
                    "target_id": "2j7h",
                    "pose_id": "2j7h_48",
                    "work_order_id": "seeded_005",
                    "split": "fit",
                    "metric_name": "dockq",
                    "metric_source_artifact": str(metric_path),
                    "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
                }
            ],
        },
    )

    payload = mod.build_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet(
        payload_priority_json=priority_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    row = payload["backfill_template_rows"][0]
    assert summary["status"] == "refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_ready"
    assert summary["seeded_backfill_row_count"] == 1
    assert summary["payload_schema_valid_count"] == 1
    assert summary["input_artifact_sha256_verified_row_count"] == 1
    assert summary["operator_receipt_backfill_ready"] is False
    assert row["payload_validation_status"] == "pass"
    assert row["operator_decision"] == "OPERATOR_FILL_ACCEPT_OR_REJECT"
    assert row["approval_token_required"] == mod.APPROVAL_TOKEN
    assert row["claim_promotion_allowed"] is False


def test_seeded_metric_payload_receipt_backfill_cli_writes_outputs(tmp_path: Path) -> None:
    metric_path = tmp_path / "metric.json"
    _write_json(metric_path, {"metric_name": "dockq"})
    priority_json = tmp_path / "priority.json"
    _write_json(
        priority_json,
        {
            "priority_rows": [
                {
                    "payload_priority_rank": 1,
                    "target_id": "x",
                    "pose_id": "x_1",
                    "metric_name": "dockq",
                    "metric_source_artifact": str(metric_path),
                    "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
                }
            ]
        },
    )
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--payload-priority-json",
            str(priority_json),
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
    assert payload["summary"]["seeded_backfill_row_count"] == len(rows)
    assert "R9 Seeded Metric Payload Receipt Backfill Packet" in out_md.read_text(encoding="utf-8")
