from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_split_review_packet as mod


def _write_task_specs(root: Path) -> None:
    for spec in mod._SLICE_SPECS:
        path = root / spec["task_spec_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Task\n\n## Verification\n\nRun focused tests.\n\n## Stop Conditions\n\nDo not promote claim text.\n",
            encoding="utf-8",
        )


def _write_name_status(root: Path, rows: list[tuple[str, str]]) -> Path:
    path = root / "name-status.txt"
    path.write_text("\n".join(f"{status}\t{file_path}" for status, file_path in rows) + "\n", encoding="utf-8")
    return path


def test_pr38_split_review_packet_assigns_each_slice_and_preserves_claim_boundaries(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "betelgeuze_product/public_benchmark.py"),
            ("A", "tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py"),
            ("A", "api/product_pocketmd_lite.py"),
            ("A", "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py"),
            ("M", "tools/product/build_product_release_source_of_truth_gate.py"),
        ],
    )

    payload = mod.build_pr38_split_review_packet(changed_files=changed_files, root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "pr38_split_review_packet_ready"
    assert summary["changed_file_count"] == 6
    assert summary["assigned_file_count"] == 6
    assert summary["unassigned_file_count"] == 0
    assert summary["integration_touchpoint_count"] == 1
    assert summary["hunk_split_review_required_count"] == 1
    assert summary["external_state_mutated"] is False
    assert summary["claim_promotion_allowed"] is False
    slices = {row["slice_id"]: row for row in payload["slices"]}
    assert set(slices) == {
        "source_of_truth_refresh",
        "public_benchmark_phase2",
        "gpcr_hard_decoy_closure",
        "pocketmd_lite_recovery",
        "f2g_f2h_preflight",
    }
    assert all(row["slice_ready_for_child_pr_review"] is True for row in payload["slices"])
    assert "paid-pilot" in slices["source_of_truth_refresh"]["claim_boundary"]
    assert "Broad GPCR" in slices["gpcr_hard_decoy_closure"]["claim_boundary"]
    assert "green-band" in slices["pocketmd_lite_recovery"]["claim_boundary"]


def test_pr38_split_review_packet_blocks_unassigned_files(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "unexpected/new_surface.py"),
        ],
    )

    payload = mod.build_pr38_split_review_packet(changed_files=changed_files, root=tmp_path)

    assert payload["summary"]["status"] == "blocked_pr38_split_review_packet"
    assert payload["summary"]["split_review_ready"] is False
    assert payload["summary"]["unassigned_file_count"] == 1
    assert payload["summary"]["unassigned_file_paths"] == ["unexpected/new_surface.py"]


def test_main_writes_pr38_split_review_packet_artifacts(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "betelgeuze_product/public_benchmark.py"),
            ("A", "tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py"),
            ("A", "api/product_pocketmd_lite.py"),
            ("A", "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py"),
        ],
    )
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--changed-files",
            str(changed_files),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pr38_split_review_packet_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert len(rows) == 5
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Split Review Packet")
