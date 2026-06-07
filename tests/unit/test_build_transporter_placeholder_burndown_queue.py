from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_follow_on_source_confirmation_packet as follow_on_source_mod
from tools import build_glut1_second_wave_source_confirmation_packet as glut1_source_mod
from tools import build_transporter_placeholder_burndown_queue as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_transporter_placeholder_burndown_queue_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_authoritative_apply_blocker_decomposition_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_apply_draft_status_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text()),
        follow_on_source_mod.build_payload(
            json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
            json.loads((ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json").read_text()),
            json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
        ),
        glut1_source_mod.build_payload(
            json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text())
        ),
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["queue_row_count"] == 12
    assert summary["seed_row_count"] == 3
    assert summary["binder_row_count"] == 6
    assert summary["negative_row_count"] == 6
    assert summary["staged_non_authoritative_rows"] == 6
    assert summary["placeholder_driven_rows"] == 6
    assert summary["reducible_now_placeholder_rows"] == 0
    assert summary["evidence_blocked_placeholder_rows"] == 6
    assert summary["glut1_staging_surface_missing_rows"] == 0
    assert summary["negative_evidence_missing_rows"] == 6
    assert summary["immediate_reduction_target"] == ""
    assert summary["immediate_reduction_target_queue_start"] == 0
    assert summary["immediate_reduction_target_queue_end"] == 0
    assert summary["immediate_reduction_delta_if_completed"] == 0
    assert summary["top_queue_id"] == "AQP1__core_binder_01"
    assert summary["queue_order_signal"] == "AQP1 binder seed rows, then GLUT1 binder rows, then AQP1 negative slots, then GLUT1 negative slots"
    assert "AQP1 core_binder_01 through core_binder_03 first" in summary["next_required_step"]
    assert "GLUT1 core_binder_01 through core_binder_03" in summary["next_required_step"]
    assert "reducible-now GLUT1 staging slice is already parked" in summary["next_required_step"]
    assert summary["aqp1_follow_on_source_confirmation_row_count"] == 2
    assert summary["aqp1_follow_on_source_confirmation_primary_focus_ligand"] == "AqB011"
    assert summary["aqp1_follow_on_exact_human_guardrail_ligand"] == "AqB013"
    assert summary["glut1_second_wave_source_confirmation_ready"] is True
    assert summary["glut1_second_wave_source_confirmation_row_count"] == 3
    assert summary["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_second_wave_direct_quantitative_binding_count"] == 1

    assert rows[0]["queue_id"] == "AQP1__core_binder_01"
    assert rows[0]["reduction_track"] == "already_staged"
    assert rows[0]["reduction_potential"] == "already_counted_elsewhere"
    assert rows[1]["queue_id"] == "AQP1__core_binder_02"
    assert rows[2]["queue_id"] == "AQP1__core_binder_03"
    assert rows[3]["queue_id"] == "GLUT1__core_binder_01"
    assert rows[3]["burndown_class"] == "staged_non_authoritative"
    assert rows[3]["reduction_track"] == "glut1_staged"
    assert rows[3]["reduction_potential"] == "already_counted_elsewhere"
    assert rows[5]["queue_id"] == "GLUT1__core_binder_03"
    assert rows[6]["queue_id"] == "AQP1__core_non_binder_01"
    assert rows[6]["reduction_track"] == "negative_evidence_missing"
    assert rows[6]["reduction_potential"] == "requires_new_negative_evidence"
    assert rows[-1]["queue_id"] == "GLUT1__core_non_binder_03"
    assert rows[1]["source_artifact"] == "runs/aqp1_first_seed_row_packet_core_binder_02_current.md"
    assert rows[2]["source_artifact"] == "runs/aqp1_first_seed_row_packet_core_binder_03_current.md"
    assert rows[3]["source_artifact"] == "runs/glut1_second_wave_seed_row_packet_current.md"
    assert rows[4]["source_artifact"] == "runs/glut1_second_wave_seed_row_packet_core_binder_02_current.md"
    assert rows[5]["source_artifact"] == "runs/glut1_second_wave_seed_row_packet_core_binder_03_current.md"
    assert rows[3]["source_anchor"] == "PMID 1716731"
    assert rows[4]["source_anchor"] == "PMID 27836974"
    assert rows[5]["source_anchor"] == "PMID 21813754"


def test_build_transporter_placeholder_burndown_queue_burns_down_negative_rows_with_apply_gate() -> None:
    apply_gate = {
        "rows": [
            {
                "slot_queue_id": f"{target}__core_non_binder_0{idx}",
                "authoritative_negative_apply_allowed": True,
            }
            for target in ("AQP1", "GLUT1")
            for idx in range(1, 4)
        ]
    }

    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_authoritative_apply_blocker_decomposition_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_apply_draft_status_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text()),
        follow_on_source_mod.build_payload(
            json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
            json.loads((ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json").read_text()),
            json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
        ),
        glut1_source_mod.build_payload(
            json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text())
        ),
        apply_gate,
    )

    summary = payload["summary"]
    negative_rows = [row for row in payload["rows"] if row["row_kind"] == "negative"]
    assert summary["placeholder_driven_rows"] == 0
    assert summary["evidence_blocked_placeholder_rows"] == 0
    assert summary["negative_evidence_missing_rows"] == 0
    assert summary["ready_for_apply_rows"] == 6
    assert all(row["burndown_class"] == "evidence_curated" for row in negative_rows)
    assert all(row["reduction_track"] == "negative_evidence_curated" for row in negative_rows)


def test_build_transporter_placeholder_burndown_queue_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "transporter_placeholder_burndown_queue.json"
    out_csv = tmp_path / "transporter_placeholder_burndown_queue.csv"
    out_md = tmp_path / "transporter_placeholder_burndown_queue.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_placeholder_burndown_queue.py",
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
    assert payload["summary"]["queue_row_count"] == 12
    assert payload["summary"]["queue_order_signal"] == "AQP1 binder seed rows, then GLUT1 binder rows, then AQP1 negative slots, then GLUT1 negative slots"
    assert payload["rows"][0]["queue_id"] == "AQP1__core_binder_01"
    assert out_csv.read_text(encoding="utf-8").splitlines()[0].startswith("queue_rank,")
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter Placeholder Burndown Queue")
