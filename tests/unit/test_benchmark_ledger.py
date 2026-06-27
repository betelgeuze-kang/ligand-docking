from __future__ import annotations

import pytest

from betelgeuze_product.benchmark_ledger import (
    EXTERNAL_SAFE_SCOPES,
    NON_CLAIM_SCOPES,
    SCOPE_BROAD_FAMILY_LOCKED,
    SCOPE_TRACKED_RANKING_PARITY,
    BenchmarkLedgerError,
    assert_external_claim_allowed,
    build_benchmark_ledger,
    current_ledger,
    external_safe_entries,
    normalize_entry,
)


def _entry(**overrides):
    base = {
        "entry_id": "x",
        "claim_scope": SCOPE_TRACKED_RANKING_PARITY,
        "dataset": "d",
        "family": "gpcr",
        "score_col": "s",
        "leakage_status": "pass",
        "gate_status": "green",
        "claim_boundary": "b",
        "allowed_external_wording": "ok",
        "disallowed_wording": ["bad"],
    }
    base.update(overrides)
    return base


def test_normalize_requires_fields() -> None:
    with pytest.raises(BenchmarkLedgerError):
        normalize_entry({"entry_id": "x"})


def test_unknown_scope_rejected() -> None:
    with pytest.raises(BenchmarkLedgerError):
        normalize_entry(_entry(claim_scope="made_up"))


def test_unknown_gate_rejected() -> None:
    with pytest.raises(BenchmarkLedgerError):
        normalize_entry(_entry(gate_status="sorta_green"))


def test_non_claim_scope_cannot_be_green() -> None:
    # A locked/reject/scaffold scope marked green is a promotion bug -> fail closed.
    with pytest.raises(BenchmarkLedgerError):
        normalize_entry(_entry(claim_scope=SCOPE_BROAD_FAMILY_LOCKED, gate_status="green"))


def test_external_safe_flag_derived_from_scope() -> None:
    row = normalize_entry(_entry(claim_scope=SCOPE_TRACKED_RANKING_PARITY))
    assert row["external_safe"] is True
    locked = normalize_entry(_entry(claim_scope=SCOPE_BROAD_FAMILY_LOCKED, gate_status="blocked"))
    assert locked["external_safe"] is False


def test_duplicate_entry_id_rejected() -> None:
    with pytest.raises(BenchmarkLedgerError):
        build_benchmark_ledger([_entry(entry_id="dup"), _entry(entry_id="dup")])


def test_numeric_metrics_parsed() -> None:
    row = normalize_entry(_entry(pr_auc="0.87", ci_low="0.76", topk="1.0"))
    assert row["pr_auc"] == 0.87
    assert row["ci_low"] == 0.76
    assert row["topk"] == 1.0


def test_non_numeric_metric_rejected() -> None:
    with pytest.raises(BenchmarkLedgerError):
        normalize_entry(_entry(pr_auc="high"))


def test_external_and_non_claim_scopes_are_disjoint() -> None:
    assert EXTERNAL_SAFE_SCOPES.isdisjoint(NON_CLAIM_SCOPES)


# --- current curated ledger ---


def test_current_ledger_builds_and_validates() -> None:
    ledger = current_ledger()
    assert ledger["summary"]["entry_count"] == len(ledger["entries"])
    assert ledger["summary"]["external_safe_count"] >= 1
    assert ledger["summary"]["locked_or_reject_count"] >= 1


def test_gpcr_a1_is_external_safe_and_within_scope() -> None:
    ledger = current_ledger()
    row = assert_external_claim_allowed(ledger, "gpcr_a1_independent_repeat_2026-05-13")
    assert row["claim_scope"] == SCOPE_TRACKED_RANKING_PARITY
    assert row["pr_auc"] == pytest.approx(0.8718530390764964)
    assert row["ci_low"] == pytest.approx(0.7611678630724843)
    assert "broad GPCR parity" in row["disallowed_wording"]


def test_broad_gpcr_is_not_external_claimable() -> None:
    ledger = current_ledger()
    with pytest.raises(BenchmarkLedgerError):
        assert_external_claim_allowed(ledger, "broad_gpcr_frozen_non_adrb2_100k")


def test_reject_and_scaffold_entries_present_and_locked() -> None:
    ledger = current_ledger()
    by_id = {row["entry_id"]: row for row in ledger["entries"]}
    assert by_id["fixed_reference_decoy_intrusion_100k"]["external_safe"] is False
    assert by_id["casp17_win_tier_proof"]["gate_status"] == "scaffold"
    assert by_id["broad_commercial_allatom_fep_parity"]["external_safe"] is False


def test_external_safe_entries_helper() -> None:
    ledger = current_ledger()
    safe = external_safe_entries(ledger)
    assert all(row["external_safe"] for row in safe)
    ids = {row["entry_id"] for row in safe}
    assert "gpcr_a1_independent_repeat_2026-05-13" in ids
    assert "broad_gpcr_frozen_non_adrb2_100k" not in ids
