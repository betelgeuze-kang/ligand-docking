from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_seed_row_fill_draft_only_prefills_safe_field() -> None:
    subprocess.run(
        [sys.executable, "tools/build_aqp1_seed_row_fill_draft.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/aqp1_seed_row_fill_draft_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["target_id"] == "AQP1"
    assert summary["packet_step"] == "core_binder_01"
    assert summary["safe_prefill_field_count"] == 1
    assert summary["blocked_field_count"] == 4
    assert summary["manual_verdict_status"] == "completed_manual_verdict"

    row_map = {row["field_name"]: row for row in rows}
    assert row_map["replacement_source"]["staged_fill_value"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert row_map["replacement_source"]["reviewer_safe_now"] == "yes"
    assert row_map["replacement_ligand_id"]["staged_fill_value"] == ""
    assert row_map["replacement_reference_binding_kcal_mol"]["staged_fill_value"] == ""
    assert row_map["replacement_smiles"]["staged_fill_value"] == ""
    assert row_map["replacement_scaffold"]["staged_fill_value"] == ""


def test_build_aqp1_seed_row_fill_draft_can_target_core_binder_02() -> None:
    seed_json = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_02_current.json"
    seed_csv = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_02_current.csv"
    seed_md = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_02_current.md"
    out_json = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_02_current.json"
    out_csv = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_02_current.csv"
    out_md = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_02_current.md"
    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_first_seed_row_packet.py",
            "--packet-step",
            "core_binder_02",
            "--out-json",
            str(seed_json),
            "--out-csv",
            str(seed_csv),
            "--out-md",
            str(seed_md),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_seed_row_fill_draft.py",
            "--seed-packet-json",
            str(seed_json),
            "--packet-step",
            "core_binder_02",
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

    payload = json.loads(out_json.read_text())
    assert payload["summary"]["packet_step"] == "core_binder_02"
    assert payload["summary"]["candidate_name"] == "AqB013"
    row_map = {row["field_name"]: row for row in payload["rows"]}
    assert row_map["replacement_source"]["staged_fill_value"] == "https://pubmed.ncbi.nlm.nih.gov/22427546/"
