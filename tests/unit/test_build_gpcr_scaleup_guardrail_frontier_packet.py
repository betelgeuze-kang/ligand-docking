from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_scaleup_guardrail_frontier_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _write_ranking(path: Path, ranks: list[int], row_count: int = 40) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ligand_id", "is_binder"])
        writer.writeheader()
        rank_set = set(ranks)
        for rank in range(1, row_count + 1):
            writer.writerow({"ligand_id": f"lig_{rank}", "is_binder": "1" if rank in rank_set else "0"})


def test_build_gpcr_scaleup_guardrail_frontier_packet_prefers_family_balanced_candidate(tmp_path: Path) -> None:
    pharmacophore = (
        tmp_path
        / "external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_apply_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
    )
    balanced = (
        tmp_path
        / "external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
    )
    failed = (
        tmp_path
        / "external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
    )
    _write_ranking(pharmacophore, [1, 2, 3, 4, 5, 6])
    _write_ranking(balanced, [1, 2, 3, 4, 5, 30])
    _write_ranking(failed, [1, 30, 31, 32, 33, 34])

    payload = mod.build_payload(candidate_paths=[str(pharmacophore), str(balanced), str(failed)])

    summary = payload["summary"]
    assert summary["claim_safe"] is True
    assert summary["claim_safe_status"] == "guardrail_recovered_candidate_available"
    assert summary["top_candidate_promotion_tier"] == "family_balanced_recovery_candidate"
    assert "beta_blocker_rescue" in summary["top_candidate_id"]
    assert summary["claim_safe_candidate_count"] == 2


def test_build_gpcr_scaleup_guardrail_frontier_packet_cli(tmp_path: Path) -> None:
    candidate = (
        tmp_path
        / "external_validation_2026-05-10_coverage_v1_family_balanced100k_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
    )
    out_json = tmp_path / "frontier.json"
    out_csv = tmp_path / "frontier.csv"
    out_md = tmp_path / "frontier.md"
    _write_ranking(candidate, [1, 2, 3, 4, 30, 31])

    subprocess.run(
        [
            sys.executable,
            "tools/build_gpcr_scaleup_guardrail_frontier_packet.py",
            "--candidate-csv",
            str(candidate),
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
    assert payload["summary"]["claim_safe"] is True
    assert payload["summary"]["packet_artifact"] == "runs/gpcr_scaleup_guardrail_frontier_packet_current.md"
    assert out_csv.exists()
    assert out_md.exists()
