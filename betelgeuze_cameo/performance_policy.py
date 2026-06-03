from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO performance threshold policy only; it defines local acceptance thresholds for future official CAMEO "
    "model1 evidence. It does not fetch official results, use local native accuracy, generate predictions, send email, "
    "register servers, or mutate external state."
)

PRODUCT_GRADE_MODEL1_THRESHOLDS = {
    "min_model1_lddt": 0.70,
    "min_model1_tm_score": 0.50,
    "min_model1_qs_score": 0.0,
    "max_model1_rmsd_A": 5.0,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _row(check: str, passed: bool, observed: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "reason": reason,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def build_cameo_performance_threshold_policy(
    *,
    profile_name: str = "product_grade_model1",
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = dict(PRODUCT_GRADE_MODEL1_THRESHOLDS)
    for key, value in (thresholds or {}).items():
        if key in values:
            values[key] = _float(value, values[key])

    min_lddt = _float(values["min_model1_lddt"])
    min_tm = _float(values["min_model1_tm_score"])
    min_qs = _float(values["min_model1_qs_score"])
    max_rmsd = _float(values["max_model1_rmsd_A"])
    rows = [
        _row(
            "profile_name_present",
            bool(_text(profile_name)),
            _text(profile_name) or "missing",
            "non-empty profile name",
            "Threshold policy needs a stable profile identifier for release evidence.",
        ),
        _row(
            "lddt_threshold_product_grade",
            min_lddt >= 0.70,
            str(min_lddt),
            "min_model1_lddt >= 0.70",
            "Model1 lDDT threshold should be explicit and non-trivial for product validation.",
        ),
        _row(
            "tm_score_threshold_product_grade",
            min_tm >= 0.50,
            str(min_tm),
            "min_model1_tm_score >= 0.50",
            "Model1 TM-score threshold should reject weak global-fold evidence.",
        ),
        _row(
            "qs_score_threshold_defined",
            min_qs >= 0.0,
            str(min_qs),
            "min_model1_qs_score >= 0.0",
            "QS-score threshold should be defined even when monomer targets make it non-binding.",
        ),
        _row(
            "rmsd_threshold_finite",
            0.0 < max_rmsd <= 5.0,
            str(max_rmsd),
            "0 < max_model1_rmsd_A <= 5.0",
            "RMSD acceptance threshold must be finite rather than a placeholder upper bound.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    summary = {
        "packet_type": "cameo_performance_threshold_policy",
        "status": "cameo_performance_threshold_policy_ready" if not blockers else "blocked_cameo_performance_threshold_policy",
        "profile_name": _text(profile_name),
        "threshold_count": len(values),
        "check_count": len(rows),
        "blocker_count": len(blockers),
        "threshold_policy_ready": not blockers,
        "min_model1_lddt": min_lddt,
        "min_model1_tm_score": min_tm,
        "min_model1_qs_score": min_qs,
        "max_model1_rmsd_A": max_rmsd,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Use this policy when evaluating official CAMEO model1 result rows.",
    }
    return {"summary": summary, "thresholds": values, "rows": rows, "blockers": blockers}
