from __future__ import annotations

from typing import Any

POSE_VALIDATION_VERSION = "pose_validation_v1"
DEFAULT_POSE_PRESERVATION_RMSD_MAX = 2.50
DEFAULT_BACKMAPPING_CONSISTENCY_MIN = 0.60
DEFAULT_STRONG_POSE_PRESERVATION_RMSD_MAX = 1.80
DEFAULT_STRONG_BACKMAPPING_CONSISTENCY_MIN = 0.72
DEFAULT_SCORE_GOOD_POSE_PRESERVATION_RMSD = 1.80
DEFAULT_SCORE_BAD_POSE_PRESERVATION_RMSD = 3.00
DEFAULT_SCORE_GOOD_BACKMAPPING_CONSISTENCY = 0.78
DEFAULT_SCORE_BAD_BACKMAPPING_CONSISTENCY = 0.45


def _text(value: Any) -> str:
    if value in {None, ""}:
        return ""
    return str(value).strip()


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except Exception:
        return None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _score_lower_better(value: Any, *, good: float, bad: float) -> float | None:
    numeric = _safe_optional_float(value)
    if numeric is None:
        return None
    if numeric <= good:
        return 1.0
    if numeric >= bad:
        return 0.0
    if bad <= good:
        return 0.0
    return _clamp((bad - numeric) / (bad - good))


def _score_higher_better(value: Any, *, good: float, bad: float) -> float | None:
    numeric = _safe_optional_float(value)
    if numeric is None:
        return None
    if numeric >= good:
        return 1.0
    if numeric <= bad:
        return 0.0
    if good <= bad:
        return 0.0
    return _clamp((numeric - bad) / (good - bad))


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if _text(value)})


def _prefixed(prefix: str, key: str) -> str:
    base = _text(prefix)
    return f"{base}_{key}" if base else key


def _metric_thresholds_from_summary(
    summary: dict[str, Any],
    *,
    threshold_key: str = "commercial_score_thresholds_v2",
    default_pose_preservation_rmsd_max: float = DEFAULT_POSE_PRESERVATION_RMSD_MAX,
    default_backmapping_consistency_min: float = DEFAULT_BACKMAPPING_CONSISTENCY_MIN,
) -> tuple[float, float]:
    thresholds = dict(summary.get(threshold_key, {}) or {})
    pose_preservation_rmsd_max = _safe_optional_float(
        thresholds.get("pose_preservation_rmsd_A_max")
    )
    backmapping_consistency_min = _safe_optional_float(
        thresholds.get("backmapping_consistency_score_min")
    )
    return (
        pose_preservation_rmsd_max
        if pose_preservation_rmsd_max is not None
        else default_pose_preservation_rmsd_max,
        backmapping_consistency_min
        if backmapping_consistency_min is not None
        else default_backmapping_consistency_min,
    )


def build_pose_validation_fields(
    *,
    pose_preservation_rmsd_A: Any,
    backmapping_consistency_score: Any,
    prefix: str = "pose_validation",
    version: str = POSE_VALIDATION_VERSION,
    pose_preservation_rmsd_A_max: float = DEFAULT_POSE_PRESERVATION_RMSD_MAX,
    backmapping_consistency_score_min: float = DEFAULT_BACKMAPPING_CONSISTENCY_MIN,
    strong_pose_preservation_rmsd_A_max: float = DEFAULT_STRONG_POSE_PRESERVATION_RMSD_MAX,
    strong_backmapping_consistency_score_min: float = DEFAULT_STRONG_BACKMAPPING_CONSISTENCY_MIN,
    score_good_pose_preservation_rmsd_A: float = DEFAULT_SCORE_GOOD_POSE_PRESERVATION_RMSD,
    score_bad_pose_preservation_rmsd_A: float = DEFAULT_SCORE_BAD_POSE_PRESERVATION_RMSD,
    score_good_backmapping_consistency_score: float = DEFAULT_SCORE_GOOD_BACKMAPPING_CONSISTENCY,
    score_bad_backmapping_consistency_score: float = DEFAULT_SCORE_BAD_BACKMAPPING_CONSISTENCY,
) -> dict[str, Any]:
    pose_rmsd = _safe_optional_float(pose_preservation_rmsd_A)
    backmapping = _safe_optional_float(backmapping_consistency_score)
    pose_rmsd_score = _score_lower_better(
        pose_rmsd,
        good=score_good_pose_preservation_rmsd_A,
        bad=score_bad_pose_preservation_rmsd_A,
    )
    backmapping_score = _score_higher_better(
        backmapping,
        good=score_good_backmapping_consistency_score,
        bad=score_bad_backmapping_consistency_score,
    )
    scores = [score for score in (pose_rmsd_score, backmapping_score) if score is not None]
    pose_validation_score = round(100.0 * sum(scores) / len(scores), 1) if scores else 0.0

    passed_checks: list[str] = []
    failed_checks: list[str] = []
    missing_checks: list[str] = []
    action_codes: list[str] = []
    blocker_codes: list[str] = []

    if pose_rmsd is None:
        missing_checks.append("pose_preservation_rmsd_missing")
        action_codes.append("measure_pose_preservation_rmsd")
    elif pose_rmsd <= pose_preservation_rmsd_A_max:
        passed_checks.append("pose_preservation_rmsd_within_gate")
        if pose_rmsd <= strong_pose_preservation_rmsd_A_max:
            passed_checks.append("pose_preservation_rmsd_strong")
    else:
        failed_checks.append("pose_preservation_rmsd_above_gate")
        action_codes.append("improve_pose_preservation_rmsd")
        blocker_codes.append("pose_validation_pose_preservation_rmsd_failed")

    if backmapping is None:
        missing_checks.append("backmapping_consistency_missing")
        action_codes.append("measure_backmapping_consistency")
    elif backmapping >= backmapping_consistency_score_min:
        passed_checks.append("backmapping_consistency_within_gate")
        if backmapping >= strong_backmapping_consistency_score_min:
            passed_checks.append("backmapping_consistency_strong")
    else:
        failed_checks.append("backmapping_consistency_below_gate")
        action_codes.append("stabilize_backmapping_consistency")
        blocker_codes.append("pose_validation_backmapping_consistency_failed")

    metrics_reported_count = sum(1 for value in (pose_rmsd, backmapping) if value is not None)
    if failed_checks:
        status = "fail"
        reason = "Pose preservation or backmapping consistency fails the pose-validation gate."
        blocker_codes.append("pose_validation_gate_not_ready")
    elif metrics_reported_count == 2:
        status = "pass"
        reason = "Pose preservation and backmapping consistency satisfy the pose-validation gate."
    else:
        status = "watch"
        reason = (
            "Pose-validation metrics are partially reported but do not show an explicit pose failure."
            if metrics_reported_count
            else "Pose-validation metrics are not yet reported."
        )

    if status == "pass" and pose_validation_score >= 85.0:
        soft_status = "strong"
    elif status == "fail":
        soft_status = "weak"
    else:
        soft_status = "watch"

    thresholds = {
        "pose_preservation_rmsd_A_max": round(pose_preservation_rmsd_A_max, 3),
        "backmapping_consistency_score_min": round(backmapping_consistency_score_min, 3),
        "strong_pose_preservation_rmsd_A_max": round(strong_pose_preservation_rmsd_A_max, 3),
        "strong_backmapping_consistency_score_min": round(
            strong_backmapping_consistency_score_min,
            3,
        ),
    }

    return {
        _prefixed(prefix, "version"): _text(version),
        _prefixed(prefix, "reported"): metrics_reported_count > 0,
        _prefixed(prefix, "score"): pose_validation_score,
        _prefixed(prefix, "status"): status,
        _prefixed(prefix, "soft_status"): soft_status,
        _prefixed(prefix, "pass"): status == "pass",
        _prefixed(prefix, "metrics_reported_count"): metrics_reported_count,
        _prefixed(prefix, "metrics_required_count"): 2,
        _prefixed(prefix, "pose_preservation_rmsd_A"): (
            round(pose_rmsd, 3) if pose_rmsd is not None else None
        ),
        _prefixed(prefix, "backmapping_consistency_score"): (
            round(backmapping, 3) if backmapping is not None else None
        ),
        _prefixed(prefix, "thresholds"): thresholds,
        _prefixed(prefix, "failed_checks"): _sorted_unique(failed_checks),
        _prefixed(prefix, "missing_checks"): _sorted_unique(missing_checks),
        _prefixed(prefix, "passed_checks"): _sorted_unique(passed_checks),
        _prefixed(prefix, "action_codes"): _sorted_unique(action_codes),
        _prefixed(prefix, "blocker_codes"): _sorted_unique(blocker_codes),
        _prefixed(prefix, "reason"): reason,
    }


def build_pose_validation_fields_from_summary(
    summary: dict[str, Any],
    *,
    prefix: str = "pose_validation",
    version: str = POSE_VALIDATION_VERSION,
    pose_key: str = "commercial_pose_preservation_rmsd_A_v2",
    backmapping_key: str = "commercial_backmapping_consistency_score_v2",
    threshold_key: str = "commercial_score_thresholds_v2",
    default_pose_preservation_rmsd_max: float = DEFAULT_POSE_PRESERVATION_RMSD_MAX,
    default_backmapping_consistency_min: float = DEFAULT_BACKMAPPING_CONSISTENCY_MIN,
    strong_pose_preservation_rmsd_A_max: float = DEFAULT_STRONG_POSE_PRESERVATION_RMSD_MAX,
    strong_backmapping_consistency_score_min: float = DEFAULT_STRONG_BACKMAPPING_CONSISTENCY_MIN,
    score_good_pose_preservation_rmsd_A: float = DEFAULT_SCORE_GOOD_POSE_PRESERVATION_RMSD,
    score_bad_pose_preservation_rmsd_A: float = DEFAULT_SCORE_BAD_POSE_PRESERVATION_RMSD,
    score_good_backmapping_consistency_score: float = DEFAULT_SCORE_GOOD_BACKMAPPING_CONSISTENCY,
    score_bad_backmapping_consistency_score: float = DEFAULT_SCORE_BAD_BACKMAPPING_CONSISTENCY,
) -> dict[str, Any]:
    pose_preservation_rmsd_A_max, backmapping_consistency_score_min = _metric_thresholds_from_summary(
        dict(summary or {}),
        threshold_key=threshold_key,
        default_pose_preservation_rmsd_max=default_pose_preservation_rmsd_max,
        default_backmapping_consistency_min=default_backmapping_consistency_min,
    )
    return build_pose_validation_fields(
        pose_preservation_rmsd_A=summary.get(pose_key),
        backmapping_consistency_score=summary.get(backmapping_key),
        prefix=prefix,
        version=version,
        pose_preservation_rmsd_A_max=pose_preservation_rmsd_A_max,
        backmapping_consistency_score_min=backmapping_consistency_score_min,
        strong_pose_preservation_rmsd_A_max=strong_pose_preservation_rmsd_A_max,
        strong_backmapping_consistency_score_min=strong_backmapping_consistency_score_min,
        score_good_pose_preservation_rmsd_A=score_good_pose_preservation_rmsd_A,
        score_bad_pose_preservation_rmsd_A=score_bad_pose_preservation_rmsd_A,
        score_good_backmapping_consistency_score=score_good_backmapping_consistency_score,
        score_bad_backmapping_consistency_score=score_bad_backmapping_consistency_score,
    )


def summarize_pose_validation_rows(
    rows: list[dict[str, Any]],
    *,
    prefix: str = "pose_validation",
) -> dict[str, Any]:
    pass_count = 0
    watch_count = 0
    fail_count = 0
    action_counts: dict[str, int] = {}
    blocker_counts: dict[str, int] = {}

    for row in rows:
        status = _text(row.get(_prefixed(prefix, "status")))
        if status == "pass":
            pass_count += 1
        elif status == "fail":
            fail_count += 1
        else:
            watch_count += 1
        for code in list(row.get(_prefixed(prefix, "action_codes"), []) or []):
            text = _text(code)
            if text:
                action_counts[text] = action_counts.get(text, 0) + 1
        for code in list(row.get(_prefixed(prefix, "blocker_codes"), []) or []):
            text = _text(code)
            if text:
                blocker_counts[text] = blocker_counts.get(text, 0) + 1

    focus = rows[0] if rows else {}
    return {
        _prefixed(prefix, "version"): _text(focus.get(_prefixed(prefix, "version"))),
        _prefixed(prefix, "pass_count"): pass_count,
        _prefixed(prefix, "watch_count"): watch_count,
        _prefixed(prefix, "fail_count"): fail_count,
        _prefixed(prefix, "focus_reported"): bool(focus.get(_prefixed(prefix, "reported"), False)),
        _prefixed(prefix, "focus_score"): focus.get(_prefixed(prefix, "score")),
        _prefixed(prefix, "focus_status"): _text(focus.get(_prefixed(prefix, "status"))),
        _prefixed(prefix, "focus_soft_status"): _text(
            focus.get(_prefixed(prefix, "soft_status"))
        ),
        _prefixed(prefix, "focus_pass"): bool(focus.get(_prefixed(prefix, "pass"), False)),
        _prefixed(prefix, "focus_pose_preservation_rmsd_A"): focus.get(
            _prefixed(prefix, "pose_preservation_rmsd_A")
        ),
        _prefixed(prefix, "focus_backmapping_consistency_score"): focus.get(
            _prefixed(prefix, "backmapping_consistency_score")
        ),
        _prefixed(prefix, "focus_thresholds"): dict(
            focus.get(_prefixed(prefix, "thresholds"), {}) or {}
        ),
        _prefixed(prefix, "focus_failed_checks"): list(
            focus.get(_prefixed(prefix, "failed_checks"), []) or []
        ),
        _prefixed(prefix, "focus_missing_checks"): list(
            focus.get(_prefixed(prefix, "missing_checks"), []) or []
        ),
        _prefixed(prefix, "focus_passed_checks"): list(
            focus.get(_prefixed(prefix, "passed_checks"), []) or []
        ),
        _prefixed(prefix, "focus_action_codes"): list(
            focus.get(_prefixed(prefix, "action_codes"), []) or []
        ),
        _prefixed(prefix, "focus_blocker_codes"): list(
            focus.get(_prefixed(prefix, "blocker_codes"), []) or []
        ),
        _prefixed(prefix, "focus_reason"): _text(focus.get(_prefixed(prefix, "reason"))),
        _prefixed(prefix, "action_counts"): [
            {_prefixed(prefix, "action_code"): code, "candidate_count": count}
            for code, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        _prefixed(prefix, "blocker_counts"): [
            {_prefixed(prefix, "blocker_code"): code, "candidate_count": count}
            for code, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
