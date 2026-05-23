from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_primary_functional_evidence as aqp1_mod
from tools import build_transporter_negative_authoritative_apply_gate as mod


ROOT = Path(__file__).resolve().parents[2]


def _negative_queue() -> dict[str, object]:
    rows = []
    for idx in range(1, 4):
        rows.append(
            {
                "queue_rank": idx,
                "queue_id": f"AQP1__core_non_binder_0{idx}",
                "target_id": "AQP1",
                "packet_step": f"core_non_binder_0{idx}",
            }
        )
    for idx in range(1, 4):
        rows.append(
            {
                "queue_rank": idx + 3,
                "queue_id": f"GLUT1__core_non_binder_0{idx}",
                "target_id": "GLUT1",
                "packet_step": f"core_non_binder_0{idx}",
            }
        )
    return {"rows": rows}


def _intake_gate() -> dict[str, object]:
    return {"summary": {"intake_gate_complete": True}}


def _glut1_curation() -> dict[str, object]:
    rows = []
    for idx, molecule_id in enumerate(["CHEMBL322952", "CHEMBL324463", "CHEMBL326703"], start=1):
        rows.append(
            {
                "curation_rank": idx,
                "slot_queue_id": f"GLUT1__core_non_binder_0{idx}",
                "slot_packet_step": f"core_non_binder_0{idx}",
                "target_id": "GLUT1",
                "target_chembl_id": "CHEMBL2535",
                "molecule_chembl_id": molecule_id,
                "canonical_smiles": f"SMILES-{idx}",
                "document_chembl_id": "CHEMBL1125913",
                "assay_chembl_id": "CHEMBL684234",
                "assay_description": "Inhibition of [125I]7-IHPP-Fsk binding to glucose transporter of human erythrocyte membrane",
                "standard_type": "Kd",
                "standard_relation": ">",
                "standard_value": "100000.0",
                "standard_units": "nM",
            }
        )
    return {"rows": rows}


def test_build_transporter_negative_authoritative_apply_gate_closes_aqp1_and_glut1_slots() -> None:
    payload = mod.build_payload(_negative_queue(), aqp1_mod.build_payload(), _intake_gate(), _glut1_curation())

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["negative_apply_gate_ready"] is True
    assert summary["required_negative_slot_count"] == 6
    assert summary["apply_allowed_count"] == 6
    assert summary["all_negative_slots_apply_allowed"] is True
    assert summary["aqp1_apply_allowed_count"] == 3
    assert summary["glut1_apply_allowed_count"] == 3
    assert summary["negative_evidence_closure_allowed"] is True
    assert summary["claim_promotion_allowed"] is False
    assert rows[0]["evidence_basis"] == "primary_functional_no_effect"
    assert rows[-1]["evidence_basis"] == "chembl_exact_target_quantitative_lower_bound"
    assert all(row["authoritative_negative_apply_allowed"] is True for row in rows)


def test_build_transporter_negative_authoritative_apply_gate_blocks_glut1_until_aqp1_complete() -> None:
    intake_gate = {"summary": {"intake_gate_complete": False}}

    payload = mod.build_payload(_negative_queue(), aqp1_mod.build_payload(), intake_gate, _glut1_curation())

    summary = payload["summary"]
    assert summary["aqp1_apply_allowed_count"] == 0
    assert summary["glut1_apply_allowed_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is False
    assert any(row["promotion_blocker"] for row in payload["rows"])


def test_build_transporter_negative_authoritative_apply_gate_cli(tmp_path: Path) -> None:
    negative_queue = tmp_path / "queue.json"
    aqp1 = tmp_path / "aqp1.json"
    intake = tmp_path / "intake.json"
    glut1 = tmp_path / "glut1.json"
    out_json = tmp_path / "apply.json"
    out_csv = tmp_path / "apply.csv"
    out_md = tmp_path / "apply.md"
    negative_queue.write_text(json.dumps(_negative_queue()), encoding="utf-8")
    aqp1.write_text(json.dumps(aqp1_mod.build_payload()), encoding="utf-8")
    intake.write_text(json.dumps(_intake_gate()), encoding="utf-8")
    glut1.write_text(json.dumps(_glut1_curation()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_negative_authoritative_apply_gate.py",
            "--negative-queue-json",
            str(negative_queue),
            "--aqp1-primary-evidence-json",
            str(aqp1),
            "--aqp1-intake-gate-json",
            str(intake),
            "--glut1-curation-queue-json",
            str(glut1),
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
    assert payload["summary"]["apply_allowed_count"] == 6
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter Negative Authoritative Apply Gate")
