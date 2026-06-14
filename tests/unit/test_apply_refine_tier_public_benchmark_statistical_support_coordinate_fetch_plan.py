from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan as mod


def _write_fetch_plan(path: Path, destination: Path) -> None:
    payload = {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready",
            "coordinate_fetch_plan_ready": True,
        },
        "rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "target_id": "new1",
                "pose_id": "new1_020",
                "required_split": "holdout",
                "suggested_split": "holdout",
                "source_url_primary": "https://files.rcsb.org/download/NEW1.pdb",
                "staging_destination_path": str(destination),
                "post_fetch_validation_command": (
                    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_intake.py"
                ),
                "canonical_intake_promotion_allowed": False,
                "external_state_mutated": False,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_candidate_queue(path: Path, destination: Path) -> None:
    payload = {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_candidate_queue_ready",
            "selected_candidate_count": 1,
            "experimental_deltaG_prefilled_count": 1,
        },
        "rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "target_id": "new1",
                "pose_id": "new1_020",
                "required_split": "holdout",
                "suggested_split": "holdout",
                "ligand_pose_artifact": "dataset/new1/new1_020.sdf",
                "ligand_pose_artifact_present": True,
                "receptor_coordinate_artifact": str(destination),
                "suggested_local_coordinate_paths": str(destination),
                "suggested_public_coordinate_urls": "https://files.rcsb.org/download/NEW1.pdb",
                "expected_archive_member_examples": "pdbbind/new1/new1_complex.pdb",
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _minimal_valid_receptor_pdb() -> str:
    lines = []
    serial = 1
    for residue in range(1, 7):
        for atom_name, element in (("N", "N"), ("CA", "C"), ("C", "C"), ("O", "O")):
            lines.append(
                f"ATOM  {serial:5d} {atom_name:<4} ALA A{residue:4d}"
                f"    {float(residue):8.3f}{float(serial % 7):8.3f}{0.0:8.3f}"
                "  1.00 20.00"
                f"           {element:>2}"
            )
            serial += 1
    return "\n".join(lines) + "\n"


def test_coordinate_fetch_apply_preview_validates_rows_without_download(tmp_path: Path) -> None:
    fetch_plan = tmp_path / "fetch_plan.json"
    destination = tmp_path / "dataset" / "new1" / "new1_complex.pdb"
    _write_fetch_plan(fetch_plan, destination)

    payload = mod.apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        fetch_plan_json=fetch_plan,
        mode="preview",
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply"
    )
    assert summary["coordinate_fetch_apply_preview_ready"] is True
    assert summary["coordinate_fetch_apply_live_ready"] is False
    assert summary["coordinate_fetch_apply_row_count"] == 1
    assert summary["coordinate_fetch_apply_preflight_pass_row_count"] == 1
    assert summary["coordinate_fetch_apply_preview_ready_row_count"] == 1
    assert summary["coordinate_fetch_apply_blocked_row_count"] == 0
    assert summary["post_fetch_validation_supported"] is True
    assert summary["post_fetch_validation_requested"] is False
    assert summary["post_fetch_validation_executed"] is False
    assert summary["post_fetch_validation_coordinate_validation_pass_row_count"] == 0
    assert summary["download_executed"] is False
    assert rows[0]["row_status"] == "fetch_apply_ready"
    assert rows[0]["destination_present_after"] is False
    assert not destination.exists()


def test_coordinate_fetch_apply_execute_requires_token_then_downloads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fetch_plan = tmp_path / "fetch_plan.json"
    destination = tmp_path / "dataset" / "new1" / "new1_complex.pdb"
    _write_fetch_plan(fetch_plan, destination)

    blocked = mod.apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        fetch_plan_json=fetch_plan,
        mode="execute",
        approval_token="WRONG",
        root=tmp_path,
    )
    assert blocked["summary"]["coordinate_fetch_apply_blocked_row_count"] == 1
    assert "approval_token_missing_or_invalid" in blocked["rows"][0]["row_blockers"]
    assert not destination.exists()

    def _fake_download(url: str, out_path: Path, *, timeout_seconds: int, overwrite: bool) -> tuple[bool, str]:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00 20.00           C\n",
            encoding="utf-8",
        )
        return True, "downloaded"

    monkeypatch.setattr(mod, "_download", _fake_download)
    allowed = mod.apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        fetch_plan_json=fetch_plan,
        mode="execute",
        approval_token=mod.APPROVAL_TOKEN,
        root=tmp_path,
    )

    assert allowed["summary"]["status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_ready"
    )
    assert allowed["summary"]["coordinate_fetch_apply_downloaded_row_count"] == 1
    assert allowed["summary"]["coordinate_fetch_apply_ready_for_validation_row_count"] == 1
    assert allowed["rows"][0]["download_executed"] is True
    assert destination.exists()


def test_coordinate_fetch_apply_execute_can_run_post_fetch_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fetch_plan = tmp_path / "fetch_plan.json"
    candidate_queue = tmp_path / "candidate_queue.json"
    destination = tmp_path / "dataset" / "new1" / "new1_complex.pdb"
    _write_fetch_plan(fetch_plan, destination)
    _write_candidate_queue(candidate_queue, destination)

    def _fake_download(url: str, out_path: Path, *, timeout_seconds: int, overwrite: bool) -> tuple[bool, str]:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_minimal_valid_receptor_pdb(), encoding="utf-8")
        return True, "downloaded"

    monkeypatch.setattr(mod, "_download", _fake_download)
    payload = mod.apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        fetch_plan_json=fetch_plan,
        mode="execute",
        approval_token=mod.APPROVAL_TOKEN,
        run_post_fetch_validation=True,
        candidate_queue_json=candidate_queue,
        root=tmp_path,
    )
    summary = payload["summary"]
    validation_summary = payload["post_fetch_validation"]["summary"]

    assert summary["post_fetch_validation_requested"] is True
    assert summary["post_fetch_validation_executed"] is True
    assert summary["post_fetch_validation_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
    )
    assert summary["post_fetch_validation_coordinate_validation_row_count"] == 1
    assert summary["post_fetch_validation_coordinate_validation_pass_row_count"] == 1
    assert summary["post_fetch_validation_coordinate_validation_blocked_row_count"] == 0
    assert summary["post_fetch_validation_candidate_ready_for_metric_materialization_count"] == 1
    assert validation_summary["coordinate_validation_pass_row_count"] == 1


def test_coordinate_fetch_apply_cli_writes_outputs(tmp_path: Path) -> None:
    fetch_plan = tmp_path / "fetch_plan.json"
    destination = tmp_path / "dataset" / "new1" / "new1_complex.pdb"
    out_json = tmp_path / "apply.json"
    out_csv = tmp_path / "apply.csv"
    out_md = tmp_path / "apply.md"
    _write_fetch_plan(fetch_plan, destination)

    mod.main(
        [
            "--fetch-plan-json",
            str(fetch_plan),
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
    assert payload["summary"]["coordinate_fetch_apply_row_count"] == 1
    assert len(rows) == 1
    assert "Coordinate Fetch Apply" in out_md.read_text(encoding="utf-8")
