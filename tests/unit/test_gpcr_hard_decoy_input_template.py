from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_product.gpcr_hard_decoy_suite import DECOY_CLASSES
from tools.product import build_gpcr_hard_decoy_suite_report as mod

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_CSV = ROOT / "config" / "gpcr_hard_decoy_suite_input_template.csv"
RUNBOOK_MD = ROOT / "docs" / "gpcr_hard_decoy_suite_operator_runbook.md"


def _read_template_rows() -> tuple[list[str], list[dict[str, str]]]:
    with TEMPLATE_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def test_template_has_builder_input_columns() -> None:
    fieldnames, _ = _read_template_rows()
    expected = [
        *mod.REQUIRED_INPUT_COLUMNS,
        *mod.OPTIONAL_NUMERIC_COLUMNS,
        mod.DECOY_CLASS_COUNTS_COLUMN,
    ]
    assert fieldnames == expected


def test_template_pins_required_targets_with_valid_decoy_cells() -> None:
    _, rows = _read_template_rows()
    target_ids = [row["target_id"] for row in rows]
    assert target_ids == ["DRD2", "HTR2A", "OPRM1"]
    for row in rows:
        # decoy_class_counts must be a JSON object using only allowed classes.
        parsed = json.loads(row[mod.DECOY_CLASS_COUNTS_COLUMN])
        assert isinstance(parsed, dict)
        assert set(parsed).issubset(DECOY_CLASSES)


def test_unfilled_template_materializes_fail_closed_locked() -> None:
    artifact = mod.build_gpcr_hard_decoy_suite_report_artifact(TEMPLATE_CSV)
    summary = artifact["summary"]
    # The template is a valid backmapping-shaped input (materializes), but with
    # empty metrics every target is blocked -> the family stays locked.
    assert artifact["materializer_status"] == mod.STATUS_MATERIALIZED
    assert summary["status"] == "broad_family_locked"
    assert summary["family_claim_safe"] is False
    assert summary["missing_required_target_ids"] == []
    assert set(summary["blocked_target_ids"]) == {"DRD2", "HTR2A", "OPRM1"}
    # Read-only accounting flags preserved.
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["docking_results_emitted"] is False


def test_runbook_documents_gate_and_claim_safe_default() -> None:
    text = RUNBOOK_MD.read_text(encoding="utf-8")
    assert "ranking_pr_auc_ci_low >= 0.45" in text
    assert "top20_hit_rate >= 0.20" in text
    assert "broad_family_locked" in text
    # Must flag the illustrative example as non-evidence.
    assert "NOT real results" in text
