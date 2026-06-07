from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_p0_closure_readiness_matrix as mod


ROOT = Path(__file__).resolve().parents[2]


def _closure_row(target: str, step: str, artifact: str) -> dict[str, object]:
    return {
        "target_id": target,
        "step_id": step,
        "artifact": artifact,
        "repo_path": f"config/{step}.csv",
        "blocker": "placeholder_rows",
        "remaining_placeholder_rows_after_apply": 5,
        "authoritative_apply_allowed": False,
        "close_when": "no placeholders remain",
        "evidence_required": "exact target evidence",
        "next_action": "curate exact evidence",
    }


def _slot(target: str, step: str, mode: str) -> dict[str, str]:
    return {
        "target_id": target,
        "packet_step": step,
        "request_mode": mode,
        "next_required_action": f"resolve {target} {step}",
    }


def test_transporter_p0_closure_readiness_matrix_classifies_open_artifacts() -> None:
    payload = mod.build_payload(
        closure_packet={
            "summary": {
                "current_membrane_p0_open_count": 2,
                "aqp1_core_p0_open_count": 1,
                "glut1_core_p0_open_count": 1,
            },
            "rows": [
                _closure_row("Aquaporin_1", "aqp1_ligand_reference", "ligand_reference_csv"),
                _closure_row("GLUT1_4PYP", "glut1_ligand_reference", "ligand_reference_csv"),
            ],
        },
        acquisition_packet={
            "summary": {"unresolved_slot_count": 2, "exact_evidence_request_slot_count": 1},
            "rows": [
                _slot("AQP1", "core_binder_01", "exact_target_pair_quantitative_binder_kcal_required"),
                _slot("GLUT1_4PYP", "core_non_binder_01", "sync_exact_negative_evidence_into_workbook_required"),
            ],
        },
    )

    summary = payload["summary"]
    assert summary["readiness_matrix_ready"] is True
    assert summary["closure_row_count"] == 2
    assert summary["auto_close_ready_artifact_count"] == 0
    assert summary["manual_or_external_required_artifact_count"] == 1
    assert summary["unresolved_slot_count"] == 2
    assert summary["auto_close_ready_slot_count"] == 1
    assert summary["external_exact_evidence_required_slot_count"] == 1
    assert summary["first_manual_or_external_required_target_id"] == "Aquaporin_1"
    assert summary["first_manual_or_external_required_slot_step"] == "core_binder_01"
    assert payload["rows"][0]["manual_or_external_required"] is True
    assert payload["rows"][1]["local_sync_ready_slot_count"] == 1
    assert summary["scope_promotion_allowed"] is False


def test_transporter_p0_closure_readiness_matrix_cli_writes_outputs(tmp_path: Path) -> None:
    closure = tmp_path / "closure.json"
    acquisition = tmp_path / "acquisition.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    closure.write_text(
        json.dumps({"summary": {"current_membrane_p0_open_count": 1}, "rows": [_closure_row("Aquaporin_1", "aqp1_ligand_reference", "ligand_reference_csv")]}),
        encoding="utf-8",
    )
    acquisition.write_text(
        json.dumps(
            {
                "summary": {"unresolved_slot_count": 1, "exact_evidence_request_slot_count": 1},
                "rows": [_slot("AQP1", "core_binder_01", "exact_target_pair_quantitative_binder_kcal_required")],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_p0_closure_readiness_matrix.py",
            "--closure-json",
            str(closure),
            "--acquisition-json",
            str(acquisition),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["closure_row_count"] == 1
    assert "target_id" in out_csv.read_text(encoding="utf-8")
    assert "Transporter P0 Closure Readiness Matrix" in out_md.read_text(encoding="utf-8")
