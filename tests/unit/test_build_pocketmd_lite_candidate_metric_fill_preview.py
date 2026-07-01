from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_candidate_metric_fill_preview as mod
from tools.product import build_pocketmd_lite_report


def _write_candidate_csv(path: Path) -> None:
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
                "clash_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "entry_id": "T:L",
                "family": "gpcr",
                "rank_pct": "0.0001",
                "selected_for_refine": "true",
                "local_min_ligand_rmsd_a": "",
                "hbond_persistence": "",
                "contact_persistence": "1.0",
                "clash_count": "0",
            }
        )


def _write_rank_selected_candidate_csv(path: Path) -> None:
    _write_candidate_csv(path)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[0]["selected_for_refine"] = ""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_probe(path: Path, *, claim_ready: bool) -> None:
    row = {
        "entry_id": "T:L",
        "claim_grade_metric_ready": claim_ready,
        "trajectory_probe_status": (
            "pocketmd_lite_metric_collection_probe_ready"
            if claim_ready
            else "blocked_pocketmd_lite_metric_collection_probe_proxy_only"
        ),
        "selected_trajectory_npz": "runs/trajectory.npz",
    }
    if claim_ready:
        row.update(
            {
                "exact_local_min_ligand_rmsd_a": 1.1,
                "exact_hbond_persistence": 0.7,
                "exact_initial_clash_count": 2,
            }
        )
    path.write_text(
        json.dumps(
            {
                "summary": {"status": row["trajectory_probe_status"]},
                "rows": [row],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_candidate_metric_fill_preview_blocks_proxy_only_probe(tmp_path: Path) -> None:
    candidate_csv = tmp_path / "candidates.csv"
    probe_json = tmp_path / "probe.json"
    _write_candidate_csv(candidate_csv)
    _write_probe(probe_json, claim_ready=False)

    payload = mod.build_pocketmd_lite_candidate_metric_fill_preview(
        candidate_csv=candidate_csv,
        probe_json=probe_json,
        out_candidate_csv=tmp_path / "preview.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_candidate_metric_fill_preview"
    assert summary["fill_ready_row_count"] == 0
    assert summary["blocked_fill_row_count"] == 1
    assert summary["canonical_candidate_csv_mutated"] is False
    row = payload["rows"][0]
    assert row["fill_ready"] is False
    assert row["blocked_metric_names"] == [
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "initial_clash_count",
    ]
    assert "claim_grade_probe_metric_ready_false" in row["blockers"]


def test_candidate_metric_fill_preview_uses_rank_pct_selection(tmp_path: Path) -> None:
    candidate_csv = tmp_path / "candidates.csv"
    probe_json = tmp_path / "probe.json"
    _write_rank_selected_candidate_csv(candidate_csv)
    _write_probe(probe_json, claim_ready=False)

    payload = mod.build_pocketmd_lite_candidate_metric_fill_preview(
        candidate_csv=candidate_csv,
        probe_json=probe_json,
        out_candidate_csv=tmp_path / "preview.csv",
    )

    assert payload["summary"]["selected_top_k_count"] == 1
    assert payload["summary"]["blocked_fill_row_count"] == 1


def test_candidate_metric_fill_preview_writes_report_ready_candidate_csv(tmp_path: Path) -> None:
    candidate_csv = tmp_path / "candidates.csv"
    probe_json = tmp_path / "probe.json"
    out_json = tmp_path / "preview.json"
    out_md = tmp_path / "preview.md"
    out_csv = tmp_path / "preview.rows.csv"
    out_candidate_csv = tmp_path / "preview.candidates.csv"
    _write_candidate_csv(candidate_csv)
    _write_probe(probe_json, claim_ready=True)

    payload = mod.build_pocketmd_lite_candidate_metric_fill_preview(
        candidate_csv=candidate_csv,
        probe_json=probe_json,
        out_candidate_csv=out_candidate_csv,
    )
    mod.write_outputs(
        payload,
        out_json=out_json,
        out_md=out_md,
        out_csv=out_csv,
        out_candidate_csv=out_candidate_csv,
    )

    assert payload["summary"]["status"] == "pocketmd_lite_candidate_metric_fill_preview_ready"
    assert payload["summary"]["fill_ready_row_count"] == 1
    preview_rows = list(csv.DictReader(out_candidate_csv.open(encoding="utf-8")))
    assert preview_rows[0]["local_min_ligand_rmsd_a"] == "1.1"
    assert preview_rows[0]["hbond_persistence"] == "0.7"
    assert preview_rows[0]["initial_clash_count"] == "2"
    assert preview_rows[0]["pocketmd_lite_metric_fill_status"] == "filled_from_claim_grade_probe"

    report = build_pocketmd_lite_report.build_pocketmd_lite_report_artifact(out_candidate_csv)
    assert report["summary"]["status"] == "pocketmd_lite_report_ready"
    assert report["rows"][0]["band"] == "green"


def test_candidate_metric_fill_preview_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_csv = tmp_path / "candidates.csv"
    probe_json = tmp_path / "probe.json"
    out_json = tmp_path / "preview.json"
    out_md = tmp_path / "preview.md"
    out_csv = tmp_path / "preview.rows.csv"
    out_candidate_csv = tmp_path / "preview.candidates.csv"
    _write_candidate_csv(candidate_csv)
    _write_probe(probe_json, claim_ready=False)

    rc = mod.main(
        [
            "--candidate-csv",
            str(candidate_csv),
            "--probe-json",
            str(probe_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
            "--out-candidate-csv",
            str(out_candidate_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["packet_type"] == (
        "pocketmd_lite_candidate_metric_fill_preview"
    )
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Candidate Metric Fill Preview")
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["entry_id"] == "T:L"
    assert out_candidate_csv.exists()
