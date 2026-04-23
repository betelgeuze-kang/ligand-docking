from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_source_exclusion_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _fake_activity_lookup(molecule_chembl_id: str, target_chembl_id: str) -> dict[str, object]:
    count = 0 if molecule_chembl_id in {"CHEMBL20", "CHEMBL9324"} and target_chembl_id == "CHEMBL4523210" else 1
    return {
        "activity_url": f"https://example.test/activity?molecule_chembl_id={molecule_chembl_id}&target_chembl_id={target_chembl_id}",
        "activity_count": count,
        "activities": [],
    }


def test_build_aqp1_negative_source_exclusion_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_candidate_verdict_sheet_current.json").read_text(encoding="utf-8")),
        activity_lookup=_fake_activity_lookup,
        as_of_date="2026-04-20",
        throttle_sec=0.0,
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 2
    assert summary["exact_target_pair_absent_count"] == 2
    assert summary["unexpected_exact_target_pair_activity_present_count"] == 0
    assert summary["primary_focus_ligand"] == "tetraethylammonium"
    assert rows[0]["candidate_name"] == "tetraethylammonium"
    assert rows[0]["molecule_chembl_id"] == "CHEMBL9324"
    assert rows[0]["exact_target_pair_activity_count"] == 0
    assert rows[0]["exclusion_status"] == "exact_human_aqp1_target_pair_absent_keep_excluded"
    assert rows[1]["candidate_name"] == "acetazolamide"
    assert rows[1]["molecule_chembl_id"] == "CHEMBL20"


def test_build_aqp1_negative_source_exclusion_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_source_exclusion.json"
    out_csv = tmp_path / "aqp1_negative_source_exclusion.csv"
    out_md = tmp_path / "aqp1_negative_source_exclusion.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_source_exclusion_packet.py",
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
    assert payload["summary"]["family"] == "aqp1"
    assert payload["summary"]["row_count"] == 2
    assert out_csv.exists()
    assert out_md.exists()
