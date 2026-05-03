from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_family_heldout_scorecard as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_adrb2_only_rows_fail_family_heldout_gate(tmp_path: Path) -> None:
    rows = tmp_path / "runs" / "adrb2_rows.csv"
    summary = tmp_path / "runs" / "adrb2_summary.json"
    _write_csv(
        rows,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "is_binder": "1",
                "binding_score_composite_v7": "-12.0",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "timolol",
                "is_binder": "1",
                "binding_score_composite_v7": "-11.0",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "binding_score_composite_v7": "-3.0",
            },
        ],
    )
    _write_json(summary, {"metrics": {"pr_auc": 0.5, "positive_count": 2}})

    payload = mod.build_scorecard(rows_csvs=[rows], summary_jsons=[summary])

    assert payload["summary"]["scorecard_level_status"] == "fail"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["router_claim_allowed"] is False
    assert payload["families"]["gpcr"]["positive_count"] == 2
    reasons = {row["reason"] for row in payload["warnings"]}
    assert "insufficient_gpcr_positive_count" in reasons
    assert "insufficient_distinct_gpcr_positive_targets" in reasons
    assert "target_specific_adrb2_bias_risk" in reasons


def test_non_adrb2_second_positive_target_can_make_scorecard_green_but_not_claim_safe(tmp_path: Path) -> None:
    rows = tmp_path / "runs" / "family_rows.csv"
    _write_csv(
        rows,
        [
            *[
                {
                    "target": "ADRB2_GPCR_BLIND",
                    "ligand_id": f"adrb2_pos_{idx}",
                    "is_binder": "1",
                    "binding_score_composite_v7": str(-12.0 - idx),
                }
                for idx in range(6)
            ],
            *[
                {
                    "target": "DRD2_GPCR_BLIND",
                    "ligand_id": f"drd2_pos_{idx}",
                    "is_binder": "1",
                    "binding_score_composite_v7": str(-10.0 - idx),
                }
                for idx in range(3)
            ],
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.0",
            },
            {
                "target": "DRD2_GPCR_BLIND",
                "ligand_id": "decoy_b",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.5",
            },
        ],
    )

    payload = mod.build_scorecard(rows_csvs=[rows], summary_jsons=[])

    assert payload["summary"]["scorecard_level_status"] == "pass"
    assert payload["summary"]["acceptance_overall_pass"] is True
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["scorecard_alone_does_not_make_claim_safe"] is True
    assert payload["families"]["gpcr"]["positive_count"] == 9
    assert payload["families"]["gpcr"]["family_held_out_gate_pass"] is True
    assert payload["warnings"] == []


def test_chembl_gpcr_family_targets_are_not_treated_as_unknown(tmp_path: Path) -> None:
    rows = tmp_path / "runs" / "chembl_family_rows.csv"
    _write_csv(
        rows,
        [
            *[
                {
                    "target": "ADRB2_GPCR_BLIND",
                    "ligand_id": f"adrb2_pos_{idx}",
                    "is_binder": "1",
                    "binding_score_composite_v7": str(-12.0 - idx),
                }
                for idx in range(6)
            ],
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7": "-9.0",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "is_binder": "1",
                "binding_score_composite_v7": "-8.5",
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "CHEMBL331883",
                "is_binder": "1",
                "binding_score_composite_v7": "-8.0",
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "kinase_decoy",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "drd2_decoy",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.5",
            },
        ],
    )

    payload = mod.build_scorecard(rows_csvs=[rows], summary_jsons=[])
    gpcr = payload["families"]["gpcr"]

    assert payload["summary"]["scorecard_level_status"] == "pass"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert gpcr["positive_count"] == 9
    assert gpcr["distinct_positive_target_count"] == 4
    assert "CHEMBL217_DRD2_HUMAN" in gpcr["distinct_positive_targets"]
    assert "CHEMBL224_HTR2A_HUMAN" in gpcr["distinct_positive_targets"]
    assert "CHEMBL233_OPRM1_HUMAN" in gpcr["distinct_positive_targets"]
    assert payload["warnings"] == []


def test_cli_writes_scorecard_json_and_markdown(tmp_path: Path) -> None:
    rows = tmp_path / "runs" / "rows.csv"
    out_json = tmp_path / "runs" / "scorecard.json"
    out_md = tmp_path / "runs" / "scorecard.md"
    _write_csv(
        rows,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "is_binder": "1",
                "binding_score_composite_v7": "-12.0",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.0",
            },
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_family_heldout_scorecard.py"),
            "--rows-csv",
            str(rows),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["packet_type"] == "gpcr_family_heldout_scorecard"
    assert payload["summary"]["scorecard_level_status"] == "fail"
    assert "GPCR Family-Held-Out Scorecard" in markdown
    assert "claim_promotion_allowed" in markdown
