from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_evidence_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_files(tmp_path: Path, target: str) -> tuple[list[str], list[str]]:
    paths = []
    for name in ("pose.sdf", "receptor.pdb", "reference.sdf"):
        path = tmp_path / "inputs" / target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{target}:{name}\n", encoding="utf-8")
        paths.append(path)
    return [str(path.relative_to(tmp_path)) for path in paths], [_sha256(path) for path in paths]


def _candidate_rows(tmp_path: Path) -> list[dict]:
    artifacts, hashes = _input_files(tmp_path, "3f3e")
    rows = []
    for metric, value in (("dockq", "0.7"), ("lddt_pli", "1.0"), ("internal_deltaG", "-2.3")):
        rows.append(
            {
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "metric_name": metric,
                "metric_value_candidate": value,
                "method_candidate": f"candidate_{metric}",
                "candidate_status": "pass",
                "candidate_input_artifacts": ";".join(artifacts),
                "candidate_input_artifact_sha256s": ";".join(hashes),
                "expected_metric_source_artifact": f"runs/3f3e_{metric}.json",
                "expected_metric_source_artifact_present": False,
            }
        )
    return rows


def _priority_rows() -> list[dict]:
    rows = []
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=1):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "metric_name": metric,
                "metric_source_artifact": f"runs/3f3e_{metric}.json",
                "operator_gap_class": "operator_receipt_blocked_placeholders",
                "operator_manual_pending_field_count": 10,
            }
        )
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=4):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "metric_name": metric,
                "metric_source_artifact": f"runs/2j7h_{metric}.json",
                "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
                "operator_manual_pending_field_count": 0,
            }
        )
    return rows


def _backfill_rows(tmp_path: Path) -> list[dict]:
    artifacts, hashes = _input_files(tmp_path, "2j7h")
    rows = []
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=4):
        source = tmp_path / "runs" / f"2j7h_{metric}.json"
        _write_json(
            source,
            {
                "metric_name": metric,
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "value": 1.0,
                "method": f"method_{metric}",
                "input_artifacts": artifacts,
                "input_artifact_sha256s": hashes,
                "operator_id": "local",
                "reviewed_at_utc": "2026-06-14T00:00:00Z",
                "license_ok": True,
                "external_engine_calls": 0,
            },
        )
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "metric_name": metric,
                "metric_source_artifact": str(source.relative_to(tmp_path)),
                "payload_validation_status": "pass",
                "operator_manual_pending_field_count": 11,
            }
        )
    return rows


def _fixture_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "recovery": tmp_path / "recovery.json",
        "candidate": tmp_path / "candidate.json",
        "priority": tmp_path / "priority.json",
        "backfill": tmp_path / "backfill.json",
        "dossier": tmp_path / "dossier.json",
    }
    _write_json(
        paths["recovery"],
        {
            "recovery_rows": [
                {
                    "recovery_priority_rank": 1,
                    "target_id": "3f3e",
                    "pose_id": "3f3e_197",
                    "work_order_id": "wo_3f3e",
                    "source_class": "candidate_fill_preview",
                    "split": "holdout",
                    "review_class": "bootstrap_p05_fragility_driver",
                    "bootstrap_p05_delta_if_removed": "0.12",
                    "rank_abs_error": 18,
                    "deltaG_proxy_kcal_mol": "-2.3",
                    "deltaG_experimental_kcal_mol": "-10.5",
                },
                {
                    "recovery_priority_rank": 2,
                    "target_id": "2j7h",
                    "pose_id": "2j7h_48",
                    "work_order_id": "wo_2j7h",
                    "source_class": "existing_materialized",
                    "split": "fit",
                    "review_class": "bootstrap_p05_fragility_driver",
                    "bootstrap_p05_delta_if_removed": "0.08",
                    "rank_abs_error": 16,
                    "deltaG_proxy_kcal_mol": "-2.1",
                    "deltaG_experimental_kcal_mol": "-9.8",
                },
            ]
        },
    )
    _write_json(paths["candidate"], {"rows": _candidate_rows(tmp_path)})
    _write_json(paths["priority"], {"priority_rows": _priority_rows()})
    _write_json(paths["backfill"], {"backfill_template_rows": _backfill_rows(tmp_path)})
    _write_json(
        paths["dossier"],
        {
            "dossier_rows": [
                {
                    "target_id": "3f3e",
                    "pose_id": "3f3e_197",
                    "next_review_lane": "descriptor_coverage_target_heldout_evidence",
                    "feature_extrapolation_residual_class": "high_error_feature_extrapolation",
                }
            ]
        },
    )
    return paths


def test_bootstrap_driver_evidence_audit_splits_candidate_and_existing_payload_drivers(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_evidence_audit(
        recovery_queue_json=paths["recovery"],
        candidate_fill_json=paths["candidate"],
        priority_json=paths["priority"],
        backfill_json=paths["backfill"],
        dossier_json=paths["dossier"],
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["audit_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_evidence_audit_ready"
    assert summary["driver_audit_row_count"] == 2
    assert summary["candidate_preview_payload_not_written_count"] == 1
    assert summary["existing_payload_receipt_backfill_pending_count"] == 1
    assert summary["source_payload_schema_valid_count"] == 3
    assert summary["source_payload_input_artifact_sha256_verified_count"] == 3
    by_target = {row["target_id"]: row for row in rows}
    assert by_target["3f3e"]["audit_class"] == "candidate_preview_payload_not_written"
    assert by_target["3f3e"]["candidate_input_artifact_sha256_verified_count"] == 3
    assert by_target["3f3e"]["operator_manual_pending_field_count"] == 30
    assert by_target["2j7h"]["audit_class"] == "existing_payload_receipt_backfill_pending"
    assert by_target["2j7h"]["source_payload_schema_valid_count"] == 3
    assert by_target["2j7h"]["operator_manual_pending_field_count"] == 33
    assert by_target["2j7h"]["claim_promotion_allowed"] is False


def test_bootstrap_driver_evidence_audit_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--recovery-queue-json",
            str(paths["recovery"]),
            "--candidate-fill-json",
            str(paths["candidate"]),
            "--priority-json",
            str(paths["priority"]),
            "--backfill-json",
            str(paths["backfill"]),
            "--dossier-json",
            str(paths["dossier"]),
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
    assert payload["summary"]["driver_audit_row_count"] == len(rows)
    assert "R9 Bootstrap Driver Evidence Audit" in out_md.read_text(encoding="utf-8")
