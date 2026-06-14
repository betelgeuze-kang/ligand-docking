import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fetch_plan_payload() -> dict:
    return {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready",
            "coordinate_fetch_plan_ready": True,
        },
        "rows": [
            {
                "candidate_queue_id": "candidate_001",
                "expansion_slot_id": "expansion_001",
                "suggested_work_order_id": "r9_stat_support_work_001",
                "target_id": "1ABC",
                "pose_id": "1abc_ligand_a_1",
                "required_split": "test",
                "source_url_primary": "https://files.rcsb.org/download/1ABC.pdb",
                "staging_destination_path": "data/public_benchmarks/refine_tier/r9/1abc.pdb",
            }
        ],
    }


def _fetch_apply_payload(*, post_fetch_validation_supported: bool = True) -> dict:
    return {
        "summary": {
            "status": "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply",
            "coordinate_fetch_apply_preview_ready": True,
            "post_fetch_validation_supported": post_fetch_validation_supported,
        },
        "rows": [],
    }


def test_coordinate_fetch_r4_preflight_builds_review_rows(tmp_path: Path) -> None:
    fetch_plan_json = tmp_path / "runs" / "fetch_plan.json"
    fetch_apply_json = tmp_path / "runs" / "fetch_apply.json"
    _write_json(fetch_plan_json, _fetch_plan_payload())
    _write_json(fetch_apply_json, _fetch_apply_payload())

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight(
        fetch_plan_json=fetch_plan_json,
        fetch_apply_json=fetch_apply_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    )
    assert summary["r4_preflight_ready"] is True
    assert summary["operator_approval_required"] is True
    assert summary["authorized_for_external_download"] is False
    assert summary["download_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["approval_token_required"] == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    assert summary["execute_command_count"] == 1
    assert "--run-post-fetch-validation" in summary["execute_command"]
    assert summary["r4_row_count"] == 1
    assert summary["ready_for_r4_review_row_count"] == 1
    assert summary["blocked_r4_row_count"] == 0
    assert summary["required_r4_fields"] == "target;action;impact;risk;rollback;verification"
    assert summary["required_r4_fields_present"] is True

    row = payload["rows"][0]
    assert row["r4_preflight_status"] == "ready_for_r4_operator_confirmation"
    assert row["target_id"] == "1abc"
    assert row["source_url_primary"] == "https://files.rcsb.org/download/1ABC.pdb"
    assert row["approval_token_required"] == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    assert row["operator_confirmation_required"] is True
    assert row["download_executed"] is False
    assert row["external_state_mutated"] is False


def test_coordinate_fetch_r4_preflight_blocks_without_post_fetch_validation(
    tmp_path: Path,
) -> None:
    fetch_plan_json = tmp_path / "runs" / "fetch_plan.json"
    fetch_apply_json = tmp_path / "runs" / "fetch_apply.json"
    _write_json(fetch_plan_json, _fetch_plan_payload())
    _write_json(fetch_apply_json, _fetch_apply_payload(post_fetch_validation_supported=False))

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight(
        fetch_plan_json=fetch_plan_json,
        fetch_apply_json=fetch_apply_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight"
    )
    assert summary["r4_preflight_ready"] is False
    assert summary["blockers"] == ["post_fetch_validation_not_supported"]


def test_coordinate_fetch_r4_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    fetch_plan_json = tmp_path / "runs" / "fetch_plan.json"
    fetch_apply_json = tmp_path / "runs" / "fetch_apply.json"
    out_json = tmp_path / "runs" / "preflight.json"
    out_csv = tmp_path / "runs" / "preflight.csv"
    out_md = tmp_path / "runs" / "preflight.md"
    _write_json(fetch_plan_json, _fetch_plan_payload())
    _write_json(fetch_apply_json, _fetch_apply_payload())

    mod.main(
        [
            "--fetch-plan-json",
            str(fetch_plan_json),
            "--fetch-apply-json",
            str(fetch_apply_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["r4_row_count"] == 1
    assert "ready_for_r4_operator_confirmation" in out_csv.read_text(encoding="utf-8")
    assert "R9 Statistical Support Coordinate Fetch R4 Preflight" in out_md.read_text(
        encoding="utf-8"
    )
