from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_suite_report as mod

_INPUT_COLUMNS = [
    "target_id",
    "positive_count",
    "ranking_pr_auc",
    "ranking_pr_auc_ci_low",
    "top20_hit_rate",
    "decoys_above_positive_count",
    "positive_target_rank",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "decoy_class_counts",
]


def _write_input_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_INPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in _INPUT_COLUMNS})


def _green_row(target_id: str) -> dict[str, object]:
    return {
        "target_id": target_id,
        "positive_count": 3,
        "ranking_pr_auc": 0.72,
        "ranking_pr_auc_ci_low": 0.55,
        "top20_hit_rate": 0.30,
        "decoys_above_positive_count": 0,
        "positive_target_rank": 1,
        "positive_anchor_distance_a": 3.10,
        "top_decoy_anchor_distance_a": 3.40,
        "decoy_class_counts": json.dumps({}),
    }


def _drd2_over_anchored() -> dict[str, object]:
    return {
        "target_id": "DRD2",
        "positive_count": 1,
        "ranking_pr_auc": 0.30,
        "ranking_pr_auc_ci_low": 0.02,
        "top20_hit_rate": 0.10,
        "decoys_above_positive_count": 5314,
        "positive_target_rank": 5315,
        "positive_anchor_distance_a": 3.25,
        "top_decoy_anchor_distance_a": 2.48,
        "decoy_class_counts": json.dumps({"over_anchored": 10}),
    }


def _oprm1_same_signature() -> dict[str, object]:
    return {
        "target_id": "OPRM1",
        "positive_count": 1,
        "ranking_pr_auc": 0.40,
        "ranking_pr_auc_ci_low": 0.12,
        "top20_hit_rate": 0.15,
        "decoys_above_positive_count": 157,
        "positive_target_rank": 158,
        "decoy_class_counts": json.dumps({"same_signature": 157}),
    }


def test_all_green_family_ready(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    _write_input_csv(csv_path, [_green_row("DRD2"), _green_row("HTR2A"), _green_row("OPRM1")])

    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)

    assert artifact["materializer_status"] == mod.STATUS_MATERIALIZED
    summary = artifact["summary"]
    assert summary["status"] == "gpcr_hard_decoy_family_ready"
    assert summary["family_claim_safe"] is True
    assert set(summary["green_target_ids"]) == {"DRD2", "HTR2A", "OPRM1"}
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["docking_results_emitted"] is False


def test_drd2_over_anchored_blocked(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    _write_input_csv(
        csv_path, [_drd2_over_anchored(), _green_row("HTR2A"), _green_row("OPRM1")]
    )

    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)
    summary = artifact["summary"]
    assert summary["status"] == "broad_family_locked"
    assert summary["family_claim_safe"] is False
    drd2 = next(t for t in artifact["targets"] if t["target_id"] == "DRD2")
    assert "decoy_over_anchored_vs_positive" in drd2["blockers"]
    assert "anchor_separation_insufficient" in drd2["root_cause_tags"]


def test_oprm1_same_signature_blocked(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    _write_input_csv(
        csv_path, [_green_row("DRD2"), _green_row("HTR2A"), _oprm1_same_signature()]
    )

    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)
    oprm1 = next(t for t in artifact["targets"] if t["target_id"] == "OPRM1")
    assert oprm1["claim_safe"] is False
    assert "same_signature_no_discriminator" in oprm1["root_cause_tags"]
    assert "decoys_above_positive_present" in oprm1["blockers"]


def test_missing_required_target_locks_family(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    _write_input_csv(csv_path, [_green_row("DRD2"), _green_row("HTR2A")])

    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)
    summary = artifact["summary"]
    # Materialization succeeds; the gate honestly reports the family locked.
    assert artifact["materializer_status"] == mod.STATUS_MATERIALIZED
    assert summary["family_claim_safe"] is False
    assert summary["missing_required_target_ids"] == ["OPRM1"]


def test_bad_decoy_class_fail_closed(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    bad = _green_row("DRD2")
    bad["decoy_class_counts"] = json.dumps({"teleport_decoy": 3})
    _write_input_csv(csv_path, [bad])

    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)
    assert artifact["materializer_status"] == mod.STATUS_BLOCKED_INVALID_ROW
    assert artifact["targets"] == []
    assert artifact["summary"]["family_claim_safe"] is False


def test_fail_closed_on_missing_csv(tmp_path: Path) -> None:
    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(tmp_path / "nope.csv")
    assert artifact["materializer_status"] == mod.STATUS_BLOCKED_MISSING


def test_fail_closed_on_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "wrong.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target_id", "score"])
        writer.writeheader()
        writer.writerow({"target_id": "DRD2", "score": 1})
    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(csv_path)
    assert artifact["materializer_status"] == mod.STATUS_BLOCKED_SCHEMA


def test_main_writes_artifacts_and_exit_codes(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    _write_input_csv(csv_path, [_green_row("DRD2"), _green_row("HTR2A"), _green_row("OPRM1")])
    out_json = tmp_path / "o.json"
    out_md = tmp_path / "o.md"
    out_csv = tmp_path / "o.csv"

    rc = mod.main(
        [
            "--input-csv", str(csv_path),
            "--out-json", str(out_json),
            "--out-md", str(out_md),
            "--out-csv", str(out_csv),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "gpcr_hard_decoy_family_ready"
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Suite Report")
    csv_rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert len(csv_rows) == 3

    # Fail-closed input -> non-zero exit.
    rc_blocked = mod.main(
        [
            "--input-csv", str(tmp_path / "missing.csv"),
            "--out-json", str(tmp_path / "b.json"),
            "--out-md", str(tmp_path / "b.md"),
            "--out-csv", str(tmp_path / "b.csv"),
        ]
    )
    assert rc_blocked == 1
