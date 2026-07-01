from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_stage3_contact_clash_intake as mod


def _write_candidates(path: Path, rows: list[dict[str, object]]) -> None:
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_stage3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target": "ADRB2_GPCR_BLIND",
                        "ligand_id": "carvedilol",
                        "frame_contact_presence_fraction": 1.0,
                        "clash_count_mean_per_frame": 0.0,
                        "clash_frame_fraction": 0.0,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_stage3_intake_fills_only_contact_and_no_clash(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    _write_candidates(
        candidates,
        [
            {
                "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                "family": "gpcr",
                "rank_pct": 0.001,
            }
        ],
    )
    _write_stage3(stage3)

    payload = mod.build_pocketmd_lite_stage3_contact_clash_intake(
        input_csv=candidates,
        stage3_json=stage3,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_stage3_partial_intake_missing_local_min_hbond"
    assert summary["stage3_matched_candidate_count"] == 1
    assert summary["contact_persistence_filled_count"] == 1
    assert summary["clash_count_filled_count"] == 1
    assert summary["local_min_missing_count"] == 1
    assert summary["hbond_missing_count"] == 1
    row = payload["rows"][0]
    assert row["contact_persistence"] == "1"
    assert row["clash_count"] == "0"
    assert "local_min_ligand_rmsd_a_missing" in row["blockers"]
    assert "hbond_persistence_missing" in row["blockers"]
    candidate = payload["candidate_rows"][0]
    assert candidate["contact_persistence"] == "1"
    assert candidate["clash_count"] == "0"
    assert candidate["local_min_ligand_rmsd_a"] == ""
    assert candidate["hbond_persistence"] == ""


def test_stage3_intake_does_not_clear_nonzero_clash(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    _write_candidates(candidates, [{"entry_id": "T:L", "family": "gpcr", "rank_pct": 0.001}])
    stage3.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target": "T",
                        "ligand_id": "L",
                        "frame_contact_presence_fraction": 0.75,
                        "clash_count_mean_per_frame": 0.2,
                        "clash_frame_fraction": 0.1,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_pocketmd_lite_stage3_contact_clash_intake(
        input_csv=candidates,
        stage3_json=stage3,
    )

    row = payload["rows"][0]
    assert row["contact_persistence"] == "0.75"
    assert row["clash_count"] == ""
    assert "stage3_nonzero_clash_observed" in row["blockers"]


def test_stage3_intake_fail_closed_on_missing_candidate_csv(tmp_path: Path) -> None:
    payload = mod.build_pocketmd_lite_stage3_contact_clash_intake(
        input_csv=tmp_path / "missing.csv",
        stage3_json=tmp_path / "stage3.json",
    )

    assert payload["summary"]["status"] == "blocked_missing_pocketmd_lite_candidate_csv"
    assert payload["rows"] == []


def test_stage3_intake_main_writes_candidate_csv_and_receipt(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    stage3 = tmp_path / "stage3.json"
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    _write_candidates(candidates, [{"entry_id": "ADRB2_GPCR_BLIND:carvedilol", "family": "gpcr", "rank_pct": 0.001}])
    _write_stage3(stage3)

    rc = mod.main(
        [
            "--input-csv",
            str(candidates),
            "--stage3-json",
            str(stage3),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    assert list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]["contact_persistence"] == "1"
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["clash_count_filled_count"] == 1
    assert out_md.read_text(encoding="utf-8").startswith("# PocketMD Lite Stage3 Contact/Clash Intake")
