from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_seed_row_sync_apply_preview_only_stages_source() -> None:
    subprocess.run(
        [sys.executable, "tools/build_aqp1_seed_row_sync_apply_preview.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/aqp1_seed_row_sync_apply_preview_current.json").read_text())
    summary = payload["summary"]
    row = payload["row"]

    assert summary["target_id"] == "AQP1"
    assert summary["packet_step"] == "core_binder_01"
    assert summary["safe_staged_field_count"] == 1
    assert summary["unresolved_field_count"] == 4
    assert summary["manual_verdict_status"] == "completed_manual_verdict"
    assert summary["authoritative_apply_allowed"] is False

    assert row["staged_replacement_source"] == "https://pubmed.ncbi.nlm.nih.gov/27474162/"
    assert row["staged_replacement_ligand_id"] == ""
    assert row["staged_replacement_reference_binding_kcal_mol"] == ""
    assert row["staged_replacement_smiles"] == ""
    assert row["staged_replacement_scaffold"] == ""
    assert row["sync_preview_status"] == "non_authoritative_partial_stage_only"


def test_build_aqp1_seed_row_sync_apply_preview_can_target_core_binder_03() -> None:
    seed_json = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_03_current.json"
    seed_csv = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_03_current.csv"
    seed_md = ROOT / "runs/aqp1_first_seed_row_packet_core_binder_03_current.md"
    fill_json = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_03_current.json"
    fill_csv = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_03_current.csv"
    fill_md = ROOT / "runs/aqp1_seed_row_fill_draft_core_binder_03_current.md"
    out_json = ROOT / "runs/aqp1_seed_row_sync_apply_preview_core_binder_03_current.json"
    out_csv = ROOT / "runs/aqp1_seed_row_sync_apply_preview_core_binder_03_current.csv"
    out_md = ROOT / "runs/aqp1_seed_row_sync_apply_preview_core_binder_03_current.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_first_seed_row_packet.py",
            "--packet-step",
            "core_binder_03",
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
            "core_binder_03",
            "--out-json",
            str(fill_json),
            "--out-csv",
            str(fill_csv),
            "--out-md",
            str(fill_md),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_seed_row_sync_apply_preview.py",
            "--seed-fill-draft-json",
            str(fill_json),
            "--seed-packet-json",
            str(seed_json),
            "--packet-step",
            "core_binder_03",
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
    assert payload["summary"]["packet_step"] == "core_binder_03"
    assert payload["summary"]["candidate_name"] == "AqB011"
    assert payload["row"]["staged_replacement_source"] == "https://pubmed.ncbi.nlm.nih.gov/26467039/"
