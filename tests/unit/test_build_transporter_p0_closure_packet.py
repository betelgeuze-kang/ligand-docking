from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_p0_closure_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _plan(target_prefix: str) -> dict[str, object]:
    return {
        "summary": {"todo_count": 3},
        "rows": [
            {
                "step_id": f"{target_prefix}_ligand_reference",
                "artifact": "ligand_reference_csv",
                "status": "todo",
                "blocker": "placeholder_ligand_rows",
                "repo_path": f"config/{target_prefix}_ref.csv",
                "detail": "placeholder_rows=5",
                "next_action": "replace placeholder rows",
            },
            {
                "step_id": f"{target_prefix}_eval_split",
                "artifact": "eval_split_csv",
                "status": "todo",
                "blocker": "placeholder_split_roles",
                "repo_path": f"config/{target_prefix}_split.csv",
                "detail": "placeholder_rows=5",
                "next_action": "freeze split roles",
            },
            {
                "step_id": f"{target_prefix}_ligand_meta",
                "artifact": "ligand_meta_csv",
                "status": "todo",
                "blocker": "placeholder_meta_rows",
                "repo_path": f"config/{target_prefix}_meta.csv",
                "detail": "placeholder_rows=5",
                "next_action": "replace meta rows",
            },
            {
                "step_id": f"{target_prefix}_profile",
                "artifact": "profile_json",
                "status": "ready",
                "blocker": "",
                "repo_path": f"config/{target_prefix}.json",
                "detail": "dry_run=true",
                "next_action": "keep dry_run",
            },
        ],
    }


def test_transporter_p0_closure_packet_expands_aqp1_and_glut1_core_rows() -> None:
    payload = mod.build_payload(
        membrane_readiness_payload={"summary": {"p0_open_count": 6}},
        aqp1_plan_payload=_plan("aqp1"),
        glut1_plan_payload=_plan("glut1"),
        glut1_apply_payload={
            "summary": {
                "applied_row_count": 1,
                "already_applied_row_count": 1,
                "blocked_ready_row_count": 0,
                "after_reference_placeholder_rows": 5,
                "after_split_placeholder_rows": 5,
                "after_meta_placeholder_rows": 5,
                "full_packet_ready_after_apply": False,
            }
        },
        binder_gate_payload={"summary": {"claim_safe_kcal_ready_count": 1, "authoritative_binder_apply_allowed_count": 1}},
    )

    summary = payload["summary"]
    assert summary["current_membrane_p0_open_count"] == 6
    assert summary["closure_row_count"] == 6
    assert summary["p0_count_matches_readiness"] is True
    assert summary["aqp1_core_p0_open_count"] == 3
    assert summary["glut1_core_p0_open_count"] == 3
    assert summary["glut1_ready_workbook_apply_receipt_present"] is True
    assert summary["glut1_ready_workbook_applied_row_count"] == 1
    assert summary["glut1_reference_placeholder_rows_after_apply"] == 5
    assert summary["glut1_full_packet_ready_after_apply"] is False
    assert summary["scope_promotion_allowed"] is False
    assert all(row["authoritative_apply_allowed"] is False for row in payload["rows"])
    glut1_rows = [row for row in payload["rows"] if row["target_id"] == "GLUT1_4PYP"]
    assert all(row["authoritative_apply_receipt"] == "runs/glut1_ready_workbook_apply_current.json" for row in glut1_rows)
    assert {row["remaining_placeholder_rows_after_apply"] for row in glut1_rows} == {5}
    assert {row["artifact"] for row in payload["rows"]} == {
        "ligand_reference_csv",
        "eval_split_csv",
        "ligand_meta_csv",
    }


def test_transporter_p0_closure_packet_cli_writes_outputs(tmp_path: Path) -> None:
    membrane = tmp_path / "membrane.json"
    aqp1 = tmp_path / "aqp1.json"
    glut1 = tmp_path / "glut1.json"
    glut1_apply = tmp_path / "glut1_apply.json"
    binder = tmp_path / "binder.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    membrane.write_text(json.dumps({"summary": {"p0_open_count": 6}}), encoding="utf-8")
    aqp1.write_text(json.dumps(_plan("aqp1")), encoding="utf-8")
    glut1.write_text(json.dumps(_plan("glut1")), encoding="utf-8")
    glut1_apply.write_text(
        json.dumps(
            {
                "summary": {
                    "applied_row_count": 1,
                    "blocked_ready_row_count": 0,
                    "after_reference_placeholder_rows": 5,
                    "after_split_placeholder_rows": 5,
                    "after_meta_placeholder_rows": 5,
                }
            }
        ),
        encoding="utf-8",
    )
    binder.write_text(json.dumps({"summary": {"claim_safe_kcal_ready_count": 1}}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_p0_closure_packet.py",
            "--membrane-readiness-json",
            str(membrane),
            "--aqp1-plan-json",
            str(aqp1),
            "--glut1-plan-json",
            str(glut1),
            "--glut1-apply-json",
            str(glut1_apply),
            "--binder-gate-json",
            str(binder),
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
    assert payload["summary"]["closure_row_count"] == 6
    assert payload["summary"]["glut1_ready_workbook_applied_row_count"] == 1
    assert "Transporter P0 Closure Packet" in out_md.read_text(encoding="utf-8")
    assert "target_id" in out_csv.read_text(encoding="utf-8")
