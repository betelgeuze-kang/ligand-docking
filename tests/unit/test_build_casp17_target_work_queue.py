from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_casp17_target_work_queue_prioritizes_tractable_open_target(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    sequence = tmp_path / "sequence.json"
    gate = tmp_path / "gate.json"
    out_json = tmp_path / "work_queue.json"
    out_csv = tmp_path / "work_queue.csv"
    out_md = tmp_path / "work_queue.md"
    _write_json(
        watchlist,
        {
            "rows": [
                {
                    "target_id": "H1319",
                    "human_open": True,
                    "lane_recommendation": "difficult_protein_complexes",
                    "days_to_human_expiration": 0,
                    "human_expiration": "2026-05-19",
                    "qa_expiration": "2026-05-22",
                    "description": "Human astrovirus antibody complex",
                    "residues": "497",
                },
                {
                    "target_id": "T1331",
                    "human_open": True,
                    "lane_recommendation": "difficult_protein_complexes",
                    "days_to_human_expiration": 7,
                    "human_expiration": "2026-05-26",
                    "qa_expiration": "2026-05-29",
                    "description": "5AT",
                    "residues": "281",
                },
                {
                    "target_id": "H1335",
                    "human_open": True,
                    "lane_recommendation": "difficult_protein_complexes",
                    "days_to_human_expiration": 8,
                    "human_expiration": "2026-05-27",
                    "qa_expiration": "2026-05-30",
                    "description": "HCMV Merlin gHgLgO-Fab complex",
                    "residues": "1820",
                },
            ]
        },
    )
    _write_json(
        sequence,
        {
            "rows": [
                {"target_id": "H1319", "sequence_status": "ready", "entry_count": 3, "residue_count": 497},
                {"target_id": "T1331", "sequence_status": "ready", "entry_count": 1, "residue_count": 281},
                {"target_id": "H1335", "sequence_status": "ready", "entry_count": 5, "residue_count": 1820},
            ]
        },
    )
    _write_json(
        gate,
        {
            "target_rows": [
                {"target_id": "H1319", "submission_decision": "submission_no_go", "blockers": "missing_prediction_file_path"},
                {"target_id": "T1331", "submission_decision": "submission_no_go", "blockers": "missing_prediction_file_path"},
                {"target_id": "H1335", "submission_decision": "submission_no_go", "blockers": "missing_prediction_file_path"},
            ]
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_target_work_queue.py"),
            "--watchlist-json",
            str(watchlist),
            "--sequence-packet-json",
            str(sequence),
            "--submission-gate-json",
            str(gate),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["selected_target_count"] == 3
    assert payload["summary"]["top_target_id"] == "T1331"
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T1331"]["recommended_action"] == "first_internal_attempt"
    assert rows["H1319"]["recommended_action"] == "dry_run_only_deadline_too_close"
    assert rows["H1335"]["recommended_action"] == "defer_high_complexity_complex"
    assert "CASP17 Target Work Queue" in out_md.read_text(encoding="utf-8")
