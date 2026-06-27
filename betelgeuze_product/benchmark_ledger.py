"""Authoritative benchmark claim ledger (source of truth for claim scope).

The repository intentionally holds both strong evidence (e.g. GPCR A1 PR-AUC
0.8719) and blocked/reject evidence (e.g. broad GPCR PR-AUC 0.0328) at the same
time. Externally this looks contradictory ("PR-AUC 1.0 but blocked?"). The cause
is that they live at different *claim layers*.

This module is the single, dependency-free source of truth that pins every
headline benchmark number to:

- a stable ``claim_scope`` (what layer the number belongs to),
- ``allowed_external_wording`` / ``disallowed_wording``,
- a ``claim_boundary``,
- the metric provenance (``score_col``, ``dataset``, ``family``,
  ``leakage_status``, ``ci_low``, ``topk``, ``gate_status``, ``artifact_sha256``).

It computes nothing scientific; it governs *how results may be described*. Keep
it stdlib-only so it is trivially testable and importable anywhere.
"""

from __future__ import annotations

from typing import Any

LEDGER_SCHEMA_VERSION = "benchmark_ledger_v1"

# --- Claim scopes (fixed taxonomy; do not invent new values ad hoc) ---
SCOPE_RESTRICTED_LOCAL_DELIVERY = "restricted_local_delivery"
SCOPE_TRACKED_RANKING_PARITY = "tracked_ranking_parity"
SCOPE_DIAGNOSTIC_SCALEUP = "diagnostic_scaleup"
SCOPE_TARGET_SPECIFIC_SUCCESS = "target_specific_success"
SCOPE_BROAD_FAMILY_LOCKED = "broad_family_locked"
SCOPE_REJECT_EVIDENCE = "reject_evidence"
SCOPE_SCAFFOLD_ONLY = "scaffold_only"
SCOPE_FULL_COMMERCIAL_BLOCKED = "full_commercial_blocked"

CLAIM_SCOPES: dict[str, str] = {
    SCOPE_RESTRICTED_LOCAL_DELIVERY: "Claim that may be stated in the product alpha (restricted local-delivery scope).",
    SCOPE_TRACKED_RANKING_PARITY: "Ranking evidence for a specific tracked lane; not a broad-family claim.",
    SCOPE_DIAGNOSTIC_SCALEUP: "Scale / speed / diagnostic evidence; not an accuracy or external benchmark claim.",
    SCOPE_TARGET_SPECIFIC_SUCCESS: "Target-specific success (e.g. ADRB2/A1); not a family or router claim.",
    SCOPE_BROAD_FAMILY_LOCKED: "Broad family / router generalization; currently locked (gate not cleared).",
    SCOPE_REJECT_EVIDENCE: "Failed/negative evidence kept for comparison; never a product claim.",
    SCOPE_SCAFFOLD_ONLY: "Scaffold / preflight only; not competitive proof.",
    SCOPE_FULL_COMMERCIAL_BLOCKED: "Broad commercial / general parity; blocked until public + prospective evidence closes.",
}

# Scopes that may appear in external (customer/investor) messaging.
EXTERNAL_SAFE_SCOPES = frozenset(
    {
        SCOPE_RESTRICTED_LOCAL_DELIVERY,
        SCOPE_TRACKED_RANKING_PARITY,
        SCOPE_TARGET_SPECIFIC_SUCCESS,
        SCOPE_DIAGNOSTIC_SCALEUP,
    }
)

# Scopes that must never be presented as a positive product claim.
NON_CLAIM_SCOPES = frozenset(
    {
        SCOPE_BROAD_FAMILY_LOCKED,
        SCOPE_REJECT_EVIDENCE,
        SCOPE_SCAFFOLD_ONLY,
        SCOPE_FULL_COMMERCIAL_BLOCKED,
    }
)

REQUIRED_ENTRY_FIELDS = (
    "entry_id",
    "claim_scope",
    "dataset",
    "family",
    "score_col",
    "leakage_status",
    "gate_status",
    "claim_boundary",
    "allowed_external_wording",
    "disallowed_wording",
)

GATE_STATUSES = frozenset({"green", "blocked", "reject", "diagnostic", "scaffold"})


class BenchmarkLedgerError(ValueError):
    """Raised when a ledger entry is malformed or violates the claim taxonomy."""


def _num_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkLedgerError(f"non-numeric metric value: {value!r}") from exc


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a single ledger entry (fail-closed)."""

    for field in REQUIRED_ENTRY_FIELDS:
        if field not in entry:
            raise BenchmarkLedgerError(f"entry missing required field: {field}")
    scope = str(entry["claim_scope"])
    if scope not in CLAIM_SCOPES:
        raise BenchmarkLedgerError(f"unknown claim_scope: {scope}")
    gate = str(entry["gate_status"])
    if gate not in GATE_STATUSES:
        raise BenchmarkLedgerError(f"unknown gate_status: {gate}")
    # A non-claim scope must not be marked green (prevents accidental promotion).
    if scope in NON_CLAIM_SCOPES and gate == "green":
        raise BenchmarkLedgerError(
            f"entry {entry['entry_id']!r} has non-claim scope {scope} but gate_status=green"
        )
    disallowed = entry.get("disallowed_wording") or []
    if not isinstance(disallowed, (list, tuple)):
        raise BenchmarkLedgerError("disallowed_wording must be a list")
    return {
        "entry_id": str(entry["entry_id"]),
        "claim_scope": scope,
        "external_safe": scope in EXTERNAL_SAFE_SCOPES,
        "dataset": str(entry["dataset"]),
        "family": str(entry["family"]),
        "score_col": str(entry["score_col"]),
        "leakage_status": str(entry["leakage_status"]),
        "gate_status": gate,
        "pr_auc": _num_or_none(entry.get("pr_auc")),
        "ci_low": _num_or_none(entry.get("ci_low")),
        "topk": _num_or_none(entry.get("topk")),
        "roc_auc": _num_or_none(entry.get("roc_auc")),
        "ef1": _num_or_none(entry.get("ef1")),
        "bedroc": _num_or_none(entry.get("bedroc")),
        "positives": entry.get("positives"),
        "artifact_sha256": str(entry.get("artifact_sha256", "")),
        "artifact_path": str(entry.get("artifact_path", "")),
        "claim_boundary": str(entry["claim_boundary"]),
        "allowed_external_wording": str(entry["allowed_external_wording"]),
        "disallowed_wording": [str(item) for item in disallowed],
    }


def build_benchmark_ledger(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate all entries and return ``{summary, entries}``."""

    normalized = [normalize_entry(entry) for entry in entries]
    seen: set[str] = set()
    for row in normalized:
        if row["entry_id"] in seen:
            raise BenchmarkLedgerError(f"duplicate entry_id: {row['entry_id']}")
        seen.add(row["entry_id"])

    scope_counts: dict[str, int] = {scope: 0 for scope in CLAIM_SCOPES}
    for row in normalized:
        scope_counts[row["claim_scope"]] += 1

    summary = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "entry_count": len(normalized),
        "external_safe_count": sum(1 for r in normalized if r["external_safe"]),
        "locked_or_reject_count": sum(1 for r in normalized if r["claim_scope"] in NON_CLAIM_SCOPES),
        "scope_counts": scope_counts,
        "claim_boundary": (
            "Benchmark claim ledger governs how results may be described. External messaging may only cite "
            "entries with external_safe=true and must stay within each entry's claim_boundary. Locked/reject/"
            "scaffold entries are never product claims."
        ),
    }
    return {"summary": summary, "entries": normalized}


def external_safe_entries(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in ledger.get("entries", []) if row.get("external_safe")]


def assert_external_claim_allowed(ledger: dict[str, Any], entry_id: str) -> dict[str, Any]:
    """Return the entry if it may be cited externally, else raise (fail-closed)."""

    for row in ledger.get("entries", []):
        if row["entry_id"] == entry_id:
            if not row["external_safe"]:
                raise BenchmarkLedgerError(
                    f"entry {entry_id!r} has scope {row['claim_scope']} and is not external-safe"
                )
            return row
    raise BenchmarkLedgerError(f"unknown ledger entry_id: {entry_id}")


# --- Curated current ledger (headline records pinned to their claim layer) ---
# Numbers are transcribed from BENCHMARKS.md / runs artifacts. They are claim
# *governance*, not recomputation. Update entries when source artifacts change.
CURRENT_LEDGER_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "gpcr_a1_independent_repeat_2026-05-13",
        "claim_scope": SCOPE_TRACKED_RANKING_PARITY,
        "dataset": "gpcr_core_full (A1 independent repeat + out-of-fold crossfit)",
        "family": "gpcr",
        "score_col": "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow",
        "leakage_status": "family_held_out_pass",
        "gate_status": "green",
        "pr_auc": 0.8718530390764964,
        "ci_low": 0.7611678630724843,
        "topk": 1.00,
        "positives": 34,
        "artifact_path": "runs/external_validation_2026-05-13_gpcr_a1_independent_repeat_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json",
        "claim_boundary": "Restricted GPCR A1 ranking lane only. Not broad GPCR/router, not docking pose/free-energy parity.",
        "allowed_external_wording": "On a frozen evaluator with an out-of-fold repeat, the restricted GPCR A1 ranking lane reached PR-AUC 0.8719, CI-low 0.7612, top20 1.00.",
        "disallowed_wording": ["broad GPCR parity", "commercial-tool parity", "router-level ranking"],
    },
    {
        "entry_id": "scaleup_1m_core_blind_quality",
        "claim_scope": SCOPE_RESTRICTED_LOCAL_DELIVERY,
        "dataset": "1M scale-up package, set1_core_blind",
        "family": "gpcr,ion_channel,kinase",
        "score_col": "binding_score_composite_v7_residual_active",
        "leakage_status": "blind_set_pass",
        "gate_status": "green",
        "pr_auc": 0.8958,
        "claim_boundary": "Restricted scale-up package quality (GPCR core 0.8958, TRPV1 0.9585, kinase 1.0). Quality only; throughput is separate diagnostic.",
        "allowed_external_wording": "In the restricted 1M scale-up package, core-blind ranking quality passed across kinase, selected GPCR, and ion-channel lanes.",
        "disallowed_wording": ["broad commercial discovery parity", "throughput claim"],
    },
    {
        "entry_id": "scaleup_1m_speed",
        "claim_scope": SCOPE_DIAGNOSTIC_SCALEUP,
        "dataset": "1M scale-up package speed guardrail",
        "family": "gpcr,ion_channel,kinase",
        "score_col": "n/a",
        "leakage_status": "n/a",
        "gate_status": "diagnostic",
        "claim_boundary": "1M throughput is diagnostic scale evidence (measured end-to-end speedup 0.792x slowest task). Throughput wording belongs to equal-size speedpack A/B, not here.",
        "allowed_external_wording": "1M-scale runs are retained as diagnostic scale evidence; throughput is reported separately with its benchmark manifest.",
        "disallowed_wording": ["fast at 1M", "production throughput proven"],
    },
    {
        "entry_id": "biorxiv_v7r1_frozen_evaluator",
        "claim_scope": SCOPE_TRACKED_RANKING_PARITY,
        "dataset": "bioRxiv blind validation v7r1 (core blind + expanded OOD + operational smoke)",
        "family": "gpcr,ion_channel,kinase,idp",
        "score_col": "binding_score_composite_v7",
        "leakage_status": "preregistered_frozen",
        "gate_status": "green",
        "claim_boundary": "Preregistered, frozen-evaluator computational blind-validation package. Not a prospective wet-lab hit claim.",
        "allowed_external_wording": "A preregistered, frozen-evaluator blind-validation package (v7r1) preserved all set passes with zero regressions.",
        "disallowed_wording": ["wet-lab hit discovery", "prospective validation"],
    },
    {
        "entry_id": "adrb2_beta_blocker_pharmacophore",
        "claim_scope": SCOPE_TARGET_SPECIFIC_SUCCESS,
        "dataset": "ADRB2 beta-blocker pharmacophore guarded apply (core + ChEMBL50)",
        "family": "gpcr (ADRB2)",
        "score_col": "binding_score_composite_v7_residual_active",
        "leakage_status": "target_specific_guarded",
        "gate_status": "green",
        "pr_auc": 1.0,
        "ci_low": 1.0,
        "topk": 0.30,
        "positives": 6,
        "claim_boundary": "ADRB2 beta-blocker/aryloxypropanolamine target-specific reward only. Must not be promoted to broad GPCR or basic-amine wording.",
        "allowed_external_wording": "A target-specific ADRB2 pharmacophore lane passes its guarded audit.",
        "disallowed_wording": ["broad GPCR success", "basic-amine generalization"],
    },
    {
        "entry_id": "openmm_structure_restricted_parity",
        "claim_scope": SCOPE_RESTRICTED_LOCAL_DELIVERY,
        "dataset": "OpenMM 11-target strict + structure deterministic true-metric + PDE selected all-atom",
        "family": "multi",
        "score_col": "internal_deterministic_ca_true_metrics",
        "leakage_status": "tracked_scorecard",
        "gate_status": "green",
        "claim_boundary": "Tracked restricted accuracy-parity scorecard is green. Broad all-atom/solvent/FEP parity is NOT claimed.",
        "allowed_external_wording": "The tracked restricted accuracy-parity scorecard (OpenMM 11-target, structure true-metric, PDE selected all-atom) is green.",
        "disallowed_wording": ["OpenMM-grade general MD parity", "FEP parity"],
    },
    {
        "entry_id": "nightly_internal_smoke_signal",
        "claim_scope": SCOPE_DIAGNOSTIC_SCALEUP,
        "dataset": "nightly ranking signal (internal smoke / regression guardrail)",
        "family": "internal",
        "score_col": "n/a",
        "leakage_status": "internal_regression_guardrail",
        "gate_status": "diagnostic",
        "roc_auc": 1.000,
        "pr_auc": 1.000,
        "ef1": 2.000,
        "bedroc": 1.000,
        "topk": 0.500,
        "claim_boundary": "Internal smoke / regression guardrail at its maxima. NOT an external hard-benchmark claim.",
        "allowed_external_wording": "Internal nightly regression guardrails are green.",
        "disallowed_wording": ["EF1 of 2.0 vs commercial tools", "perfect AUC benchmark"],
    },
    {
        "entry_id": "broad_gpcr_frozen_non_adrb2_100k",
        "claim_scope": SCOPE_BROAD_FAMILY_LOCKED,
        "dataset": "frozen non-ADRB2 guarded 100k",
        "family": "gpcr",
        "score_col": "binding_score_composite_v7",
        "leakage_status": "family_held_out_pass",
        "gate_status": "blocked",
        "pr_auc": 0.22869872098030358,
        "ci_low": 0.0019312183264511504,
        "topk": 0.10,
        "positives": 9,
        "claim_boundary": "Coverage/leakage/family-held-out pass, but CI-low and top20 fail the claim-review gate. Broad GPCR/router claim forbidden.",
        "allowed_external_wording": "Broad GPCR family generalization remains an open, gated research lane (not claimed).",
        "disallowed_wording": ["broad GPCR works", "family-general ranking"],
    },
    {
        "entry_id": "fixed_reference_decoy_intrusion_100k",
        "claim_scope": SCOPE_REJECT_EVIDENCE,
        "dataset": "fixed_family_reference + decoy intrusion full 100k",
        "family": "gpcr",
        "score_col": "binding_score_composite_v7_residual_active",
        "leakage_status": "guarded_comparison",
        "gate_status": "reject",
        "pr_auc": 0.0328,
        "ci_low": 0.0045,
        "topk": 0.05,
        "positives": 6,
        "claim_boundary": "Reject/negative evidence retained for comparison only.",
        "allowed_external_wording": "(none — internal reject evidence)",
        "disallowed_wording": ["any positive claim"],
    },
    {
        "entry_id": "casp17_win_tier_proof",
        "claim_scope": SCOPE_SCAFFOLD_ONLY,
        "dataset": "CASP17 strict-blind competitive proof",
        "family": "structure",
        "score_col": "n/a",
        "leakage_status": "strict_blind_pending_native",
        "gate_status": "scaffold",
        "claim_boundary": "Preflight/scaffold ready (19/19 targets) but competitive proof is fail-closed (0/40 slots) until native structures publish.",
        "allowed_external_wording": "A CASP17 internal-physics participation scaffold is prepared; competitive proof is pending native release.",
        "disallowed_wording": ["CASP17 top-tier proof", "CASP17 win"],
    },
    {
        "entry_id": "broad_commercial_allatom_fep_parity",
        "claim_scope": SCOPE_FULL_COMMERCIAL_BLOCKED,
        "dataset": "broad all-atom MD / FEP / general commercial parity",
        "family": "multi",
        "score_col": "n/a",
        "leakage_status": "n/a",
        "gate_status": "blocked",
        "claim_boundary": "Internal united-atom/proxy refine tier exists (internal_proxy_uncalibrated); calibrated all-atom/FEP/general parity is blocked until public + prospective evidence closes.",
        "allowed_external_wording": "Calibrated all-atom MD, FEP, and general commercial parity are on the roadmap and not yet claimed.",
        "disallowed_wording": ["AMBER/CHARMM-grade MD", "FEP+ parity", "Schrodinger replacement"],
    },
]


def current_ledger() -> dict[str, Any]:
    """Build the curated current benchmark ledger."""

    return build_benchmark_ledger(CURRENT_LEDGER_ENTRIES)


__all__ = [
    "LEDGER_SCHEMA_VERSION",
    "CLAIM_SCOPES",
    "EXTERNAL_SAFE_SCOPES",
    "NON_CLAIM_SCOPES",
    "GATE_STATUSES",
    "REQUIRED_ENTRY_FIELDS",
    "BenchmarkLedgerError",
    "normalize_entry",
    "build_benchmark_ledger",
    "external_safe_entries",
    "assert_external_claim_allowed",
    "CURRENT_LEDGER_ENTRIES",
    "current_ledger",
    "SCOPE_RESTRICTED_LOCAL_DELIVERY",
    "SCOPE_TRACKED_RANKING_PARITY",
    "SCOPE_DIAGNOSTIC_SCALEUP",
    "SCOPE_TARGET_SPECIFIC_SUCCESS",
    "SCOPE_BROAD_FAMILY_LOCKED",
    "SCOPE_REJECT_EVIDENCE",
    "SCOPE_SCAFFOLD_ONLY",
    "SCOPE_FULL_COMMERCIAL_BLOCKED",
]
