from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_closure_replay_spec as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sweep_payload() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_gpcr_hard_decoy_candidate_sweep_no_closure_candidate",
            "gpcr_actual_closure_ready": False,
            "required_target_count": 3,
        },
        "candidates": [
            {
                "candidate_path": "runs/a.csv",
                "metric_gate_ready": True,
                "target_green_count": 2,
                "target_blocker_count": 2,
                "targets": [
                    {
                        "target_id": "DRD2",
                        "target_status": "blocked",
                        "target_green": False,
                        "decoys_above_positive_count": 4,
                        "anchor_margin_a": -0.0289,
                        "positive_target_rank": 5,
                        "positive_anchor_distance_a": 5.0208,
                        "top_decoy_anchor_distance_a": 4.9919,
                        "top_decoy_ligand_id": "decoy_D",
                        "blockers": ["decoys_above_positive_present", "decoy_over_anchored_vs_positive"],
                    },
                    {
                        "target_id": "HTR2A",
                        "target_status": "green",
                        "target_green": True,
                        "decoys_above_positive_count": 0,
                        "anchor_margin_a": 0.04,
                        "blockers": [],
                    },
                    {
                        "target_id": "OPRM1",
                        "target_status": "green",
                        "target_green": True,
                        "decoys_above_positive_count": 0,
                        "anchor_margin_a": 0.01,
                        "blockers": [],
                    },
                ],
            }
        ],
    }


def test_closure_replay_spec_records_remaining_drd2_delta(tmp_path: Path) -> None:
    sweep = tmp_path / "sweep.json"
    _write_json(sweep, _sweep_payload())

    payload = mod.build_gpcr_hard_decoy_closure_replay_spec(sweep_json=sweep)

    summary = payload["summary"]
    assert summary["status"] == "gpcr_hard_decoy_closure_replay_spec_ready"
    assert summary["best_candidate_path"] == "runs/a.csv"
    assert summary["remaining_target_ids"] == ["DRD2"]
    drd2 = next(row for row in payload["rows"] if row["target_id"] == "DRD2")
    assert drd2["decoys_above_delta_needed"] == 4
    assert drd2["anchor_margin_delta_needed_a"] == 0.0289
    assert drd2["recommended_next_local_action"] == (
        "rerun_target_rescore_to_rank_positive_first_and_restore_positive_anchor_margin"
    )
    htr2a = next(row for row in payload["rows"] if row["target_id"] == "HTR2A")
    assert htr2a["recommended_next_local_action"] == "preserve_green_target_in_next_replay"
    assert summary["claim_promotion_allowed"] is False


def test_main_writes_closure_replay_spec_artifacts(tmp_path: Path) -> None:
    sweep = tmp_path / "sweep.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(sweep, _sweep_payload())

    rc = mod.main(
        [
            "--sweep-json",
            str(sweep),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["remaining_target_count"] == 1
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Closure Replay Spec")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["target_id"] for row in rows] == ["DRD2", "HTR2A", "OPRM1"]

