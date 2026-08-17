#!/usr/bin/env python3
"""Build a repeatable, development-only Engine V2 D1 scorecard.

The tool consumes exactly 32 pre-existing per-case result documents.  It does
not launch docking, access Fresh-128 data, mutate ranking, or grant benchmark,
scientific, product, or customer authority.  The same manifest may be analyzed
repeatedly while algorithms are developed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Any, Iterable

PROFILE_SCHEMA_ID = "betelgeuze.engine_v2_d1_development_profile/1.0.0"
PROFILE_ID = "engine_v2_d1_repeatable_development_v1"
MANIFEST_SCHEMA_ID = "betelgeuze.engine_v2_d1_manifest/1.0.0"
FRESH_REGISTRY_SCHEMA_ID = "betelgeuze.engine_v2_fresh_case_registry/1.0.0"
CASE_RESULT_SCHEMA_ID = "betelgeuze.engine_v2_d1_case_result/1.0.0"
REPORT_SCHEMA_ID = "betelgeuze.engine_v2_d1_development_report/1.0.0"
CASE_COUNT = 32
FRESH_CASE_COUNT = 128
CANDIDATE_DENOMINATOR = 64
RMSD_THRESHOLD_ANGSTROM = 2.0
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class D1DevelopmentError(ValueError):
    """The repeatable D1 development input is invalid or crosses authority."""


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise D1DevelopmentError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise D1DevelopmentError("value is not canonical JSON") from exc


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_object_no_duplicates
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise D1DevelopmentError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise D1DevelopmentError(f"{path} must contain one JSON object")
    return value


def _exact_int(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise D1DevelopmentError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return value


def _finite(
    value: Any, *, name: str, minimum: float = -math.inf, maximum: float = math.inf
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise D1DevelopmentError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise D1DevelopmentError(
            f"{name} must be finite in [{minimum},{maximum}]"
        )
    return result


def _optional_finite(
    value: Any, *, name: str, minimum: float = -math.inf, maximum: float = math.inf
) -> float | None:
    if value is None:
        return None
    return _finite(value, name=name, minimum=minimum, maximum=maximum)


def _exact_optional_bool(value: Any, *, name: str) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise D1DevelopmentError(f"{name} must be true, false, or null")


def _case_id(value: Any, *, name: str) -> str:
    if type(value) is not str or CASE_ID_RE.fullmatch(value) is None:
        raise D1DevelopmentError(f"{name} is not a valid case identifier")
    return value


def _relative_regular_file(root: Path, value: Any, *, name: str) -> Path:
    if type(value) is not str or not value:
        raise D1DevelopmentError(f"{name} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise D1DevelopmentError(f"{name} must remain under the result root")
    candidate = root / relative
    if candidate.is_symlink():
        raise D1DevelopmentError(f"{name} cannot be a symlink")
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_root != resolved_candidate and resolved_root not in resolved_candidate.parents:
        raise D1DevelopmentError(f"{name} escaped the result root")
    if not resolved_candidate.is_file():
        raise D1DevelopmentError(f"{name} does not name a regular file")
    return resolved_candidate


def _verify_profile(profile_path: Path) -> dict[str, Any]:
    profile = _load_json(profile_path)
    if profile.get("schema_id") != PROFILE_SCHEMA_ID:
        raise D1DevelopmentError("D1 development profile schema changed")
    if profile.get("profile_id") != PROFILE_ID:
        raise D1DevelopmentError("D1 development profile id changed")
    if profile.get("case_count") != CASE_COUNT:
        raise D1DevelopmentError("D1 case count must be exactly 32")
    if profile.get("candidate_denominator") != CANDIDATE_DENOMINATOR:
        raise D1DevelopmentError("candidate denominator must be exactly 64")
    if _finite(
        profile.get("rmsd_threshold_angstrom"),
        name="rmsd_threshold_angstrom",
        minimum=0.0,
        maximum=10.0,
    ) != RMSD_THRESHOLD_ANGSTROM:
        raise D1DevelopmentError("D1 RMSD threshold changed")
    if profile.get("top_k") != [1, 5] or profile.get("score_direction") != "lower_is_better":
        raise D1DevelopmentError("D1 ranking policy changed")

    policy = profile.get("development_policy")
    if type(policy) is not dict:
        raise D1DevelopmentError("development_policy must be an object")
    expected_policy = {
        "repeatable_execution_allowed": True,
        "result_informed_iteration_allowed": True,
        "fresh_holdout_overlap_allowed": False,
        "fresh_holdout_execution_allowed": False,
        "stage0_admission_allowed": False,
        "public_benchmark_claim_allowed": False,
        "scientific_claim_allowed": False,
        "product_promotion_allowed": False,
        "customer_pose_emission_allowed": False,
    }
    if policy != expected_policy:
        raise D1DevelopmentError("development authority boundary changed")

    authority = profile.get("authority")
    if type(authority) is not dict or not authority:
        raise D1DevelopmentError("authority map must be non-empty")
    if any(type(value) is not bool or value for value in authority.values()):
        raise D1DevelopmentError("every D1 authority field must remain false")
    return profile


def _load_fresh_case_ids(path: Path) -> tuple[str, ...]:
    document = _load_json(path)
    if document.get("schema_id") != FRESH_REGISTRY_SCHEMA_ID:
        raise D1DevelopmentError("fresh case registry schema changed")
    values = document.get("case_ids")
    if type(values) is not list or len(values) != FRESH_CASE_COUNT:
        raise D1DevelopmentError("fresh case registry must contain exactly 128 IDs")
    case_ids = tuple(_case_id(value, name="fresh case id") for value in values)
    if len(set(case_ids)) != len(case_ids):
        raise D1DevelopmentError("fresh case registry contains duplicates")
    return case_ids


def _load_manifest(path: Path) -> tuple[dict[str, Any], tuple[tuple[str, str], ...]]:
    document = _load_json(path)
    if document.get("schema_id") != MANIFEST_SCHEMA_ID:
        raise D1DevelopmentError("D1 manifest schema changed")
    if document.get("profile_id") != PROFILE_ID:
        raise D1DevelopmentError("D1 manifest profile changed")
    rows = document.get("cases")
    if type(rows) is not list or len(rows) != CASE_COUNT:
        raise D1DevelopmentError("D1 manifest must contain exactly 32 cases")
    result: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"case_id", "result_path"}:
            raise D1DevelopmentError(f"manifest row {index} has an invalid shape")
        result.append(
            (
                _case_id(row["case_id"], name=f"manifest case {index}"),
                str(row["result_path"]),
            )
        )
    case_ids = [case_id for case_id, _ in result]
    if len(set(case_ids)) != CASE_COUNT:
        raise D1DevelopmentError("D1 manifest case IDs must be unique")
    return document, tuple(result)


def _load_case_result(path: Path, expected_case_id: str) -> dict[str, Any]:
    document = _load_json(path)
    if document.get("schema_id") != CASE_RESULT_SCHEMA_ID:
        raise D1DevelopmentError(f"{expected_case_id}: case-result schema changed")
    if document.get("case_id") != expected_case_id:
        raise D1DevelopmentError(f"{expected_case_id}: result case_id is cross-wired")
    status = document.get("preparation_status")
    if status not in {"success", "failure"}:
        raise D1DevelopmentError(f"{expected_case_id}: invalid preparation_status")
    failure_code = document.get("preparation_failure_code")
    candidates = document.get("candidates")
    if type(candidates) is not list:
        raise D1DevelopmentError(f"{expected_case_id}: candidates must be a list")

    if status == "failure":
        if type(failure_code) is not str or not failure_code:
            raise D1DevelopmentError(
                f"{expected_case_id}: preparation failure requires a code"
            )
        if document.get("candidate_denominator") != 0 or candidates:
            raise D1DevelopmentError(
                f"{expected_case_id}: preparation failure cannot contain candidates"
            )
        return {
            "case_id": expected_case_id,
            "preparation_status": "failure",
            "preparation_failure_code": failure_code,
            "candidate_denominator": 0,
            "candidates": [],
            "source_sha256": _sha256_path(path),
        }

    if failure_code not in {None, ""}:
        raise D1DevelopmentError(
            f"{expected_case_id}: successful preparation cannot have a failure code"
        )
    if document.get("candidate_denominator") != CANDIDATE_DENOMINATOR:
        raise D1DevelopmentError(
            f"{expected_case_id}: candidate denominator must be exactly 64"
        )
    if len(candidates) != CANDIDATE_DENOMINATOR:
        raise D1DevelopmentError(
            f"{expected_case_id}: all 64 candidate rows must be retained"
        )

    normalized: list[dict[str, Any]] = []
    for expected_slot, candidate in enumerate(candidates):
        if type(candidate) is not dict:
            raise D1DevelopmentError(
                f"{expected_case_id}: candidate {expected_slot} must be an object"
            )
        slot = _exact_int(
            candidate.get("slot_index"),
            name=f"{expected_case_id}.slot_index",
            minimum=0,
            maximum=CANDIDATE_DENOMINATOR - 1,
        )
        if slot != expected_slot:
            raise D1DevelopmentError(
                f"{expected_case_id}: candidate rows are reordered or incomplete"
            )
        lane = candidate.get("lane")
        if type(lane) is not str or not lane or len(lane) > 128:
            raise D1DevelopmentError(f"{expected_case_id}: invalid lane at slot {slot}")
        candidate_status = candidate.get("status")
        if candidate_status not in {"scored", "typed_failure"}:
            raise D1DevelopmentError(
                f"{expected_case_id}: invalid candidate status at slot {slot}"
            )
        candidate_failure = candidate.get("failure_code")
        if candidate_status == "typed_failure":
            if type(candidate_failure) is not str or not candidate_failure:
                raise D1DevelopmentError(
                    f"{expected_case_id}: typed failure at slot {slot} needs a code"
                )
            for key in (
                "score",
                "proposal_rmsd_angstrom",
                "final_rmsd_angstrom",
                "proposal_valid",
                "pose_valid",
            ):
                if candidate.get(key) is not None:
                    raise D1DevelopmentError(
                        f"{expected_case_id}: failed slot {slot} contains {key}"
                    )
            normalized.append(
                {
                    "slot_index": slot,
                    "lane": lane,
                    "status": "typed_failure",
                    "failure_code": candidate_failure,
                    "score": None,
                    "proposal_rmsd_angstrom": None,
                    "final_rmsd_angstrom": None,
                    "proposal_valid": None,
                    "pose_valid": None,
                }
            )
            continue

        if candidate_failure not in {None, ""}:
            raise D1DevelopmentError(
                f"{expected_case_id}: scored slot {slot} has a failure code"
            )
        normalized.append(
            {
                "slot_index": slot,
                "lane": lane,
                "status": "scored",
                "failure_code": None,
                "score": _finite(
                    candidate.get("score"),
                    name=f"{expected_case_id}.score[{slot}]",
                ),
                "proposal_rmsd_angstrom": _finite(
                    candidate.get("proposal_rmsd_angstrom"),
                    name=f"{expected_case_id}.proposal_rmsd[{slot}]",
                    minimum=0.0,
                    maximum=1_000_000.0,
                ),
                "final_rmsd_angstrom": _finite(
                    candidate.get("final_rmsd_angstrom"),
                    name=f"{expected_case_id}.final_rmsd[{slot}]",
                    minimum=0.0,
                    maximum=1_000_000.0,
                ),
                "proposal_valid": _exact_optional_bool(
                    candidate.get("proposal_valid"),
                    name=f"{expected_case_id}.proposal_valid[{slot}]",
                ),
                "pose_valid": _exact_optional_bool(
                    candidate.get("pose_valid"),
                    name=f"{expected_case_id}.pose_valid[{slot}]",
                ),
            }
        )

    return {
        "case_id": expected_case_id,
        "preparation_status": "success",
        "preparation_failure_code": None,
        "candidate_denominator": CANDIDATE_DENOMINATOR,
        "candidates": normalized,
        "source_sha256": _sha256_path(path),
    }


def _summarize_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    if case["preparation_status"] == "failure":
        return {
            "case_id": case_id,
            "preparation_success": False,
            "preparation_failure_code": case["preparation_failure_code"],
            "scored_candidate_count": 0,
            "typed_failure_count": 0,
            "proposal_oracle_recovered": False,
            "valid_proposal_oracle_recovered": False,
            "top1_recovered": False,
            "top5_recovered": False,
            "top1_valid": None,
            "top1_lane": None,
            "top1_slot_index": None,
            "top1_final_rmsd_angstrom": None,
            "best_final_rmsd_angstrom": None,
            "scoring_regret_angstrom": None,
            "source_sha256": case["source_sha256"],
        }

    candidates = case["candidates"]
    scored = [candidate for candidate in candidates if candidate["status"] == "scored"]
    ranked = sorted(scored, key=lambda row: (row["score"], row["slot_index"]))
    proposal_oracle = any(
        row["proposal_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM for row in scored
    )
    valid_proposal_oracle = any(
        row["proposal_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM
        and row["proposal_valid"] is True
        for row in scored
    )
    top1 = ranked[0] if ranked else None
    top5 = ranked[:5]
    top1_recovered = bool(
        top1 is not None
        and top1["final_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM
    )
    top5_recovered = any(
        row["final_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM for row in top5
    )
    best_rmsd = min(
        (row["final_rmsd_angstrom"] for row in scored), default=None
    )
    top1_rmsd = top1["final_rmsd_angstrom"] if top1 is not None else None
    regret = (
        top1_rmsd - best_rmsd
        if top1_rmsd is not None and best_rmsd is not None
        else None
    )
    if regret is not None and regret < -1.0e-12:
        raise D1DevelopmentError(f"{case_id}: scoring regret became negative")

    return {
        "case_id": case_id,
        "preparation_success": True,
        "preparation_failure_code": None,
        "scored_candidate_count": len(scored),
        "typed_failure_count": CANDIDATE_DENOMINATOR - len(scored),
        "proposal_oracle_recovered": proposal_oracle,
        "valid_proposal_oracle_recovered": valid_proposal_oracle,
        "top1_recovered": top1_recovered,
        "top5_recovered": top5_recovered,
        "top1_valid": top1["pose_valid"] if top1 is not None else None,
        "top1_lane": top1["lane"] if top1 is not None else None,
        "top1_slot_index": top1["slot_index"] if top1 is not None else None,
        "top1_final_rmsd_angstrom": top1_rmsd,
        "best_final_rmsd_angstrom": best_rmsd,
        "scoring_regret_angstrom": regret,
        "source_sha256": case["source_sha256"],
    }


def _aggregate(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    case_list = list(cases)
    summaries = [_summarize_case(case) for case in case_list]
    prepared = [summary for summary in summaries if summary["preparation_success"]]
    scored = [summary for summary in prepared if summary["scored_candidate_count"] > 0]
    regrets = [
        float(summary["scoring_regret_angstrom"])
        for summary in scored
        if summary["scoring_regret_angstrom"] is not None
    ]

    lanes: dict[str, Counter[str]] = defaultdict(Counter)
    failure_counts: Counter[str] = Counter()
    preparation_failures: Counter[str] = Counter()
    for case, summary in zip(case_list, summaries, strict=True):
        if not summary["preparation_success"]:
            preparation_failures[str(summary["preparation_failure_code"])] += 1
            continue
        top5_slots: set[int] = set()
        ranked = sorted(
            (row for row in case["candidates"] if row["status"] == "scored"),
            key=lambda row: (row["score"], row["slot_index"]),
        )
        for row in ranked[:5]:
            if row["final_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM:
                top5_slots.add(row["slot_index"])
        for row in case["candidates"]:
            lane = row["lane"]
            lanes[lane]["candidate_count"] += 1
            if row["status"] == "typed_failure":
                lanes[lane]["typed_failure_count"] += 1
                failure_counts[str(row["failure_code"])] += 1
                continue
            lanes[lane]["scored_count"] += 1
            if row["proposal_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM:
                lanes[lane]["proposal_oracle_candidate_count"] += 1
                if row["proposal_valid"] is True:
                    lanes[lane]["valid_proposal_oracle_candidate_count"] += 1
            if row["final_rmsd_angstrom"] <= RMSD_THRESHOLD_ANGSTROM:
                lanes[lane]["final_native_like_candidate_count"] += 1
            if row["pose_valid"] is True:
                lanes[lane]["exact_valid_candidate_count"] += 1
            if row["slot_index"] == summary["top1_slot_index"]:
                lanes[lane]["top1_case_count"] += 1
            if row["slot_index"] in top5_slots:
                lanes[lane]["top5_native_like_candidate_count"] += 1

    def count_true(key: str) -> int:
        return sum(summary[key] is True for summary in summaries)

    invalid_top1 = sum(summary["top1_valid"] is False for summary in scored)
    unavailable_top1 = sum(summary["top1_valid"] is None for summary in scored)
    aggregate = {
        "case_count": len(summaries),
        "preparation_success_count": len(prepared),
        "preparation_failure_count": len(summaries) - len(prepared),
        "scored_case_count": len(scored),
        "proposal_oracle_recovery_count": count_true("proposal_oracle_recovered"),
        "valid_proposal_oracle_recovery_count": count_true(
            "valid_proposal_oracle_recovered"
        ),
        "top1_recovery_count": count_true("top1_recovered"),
        "top5_recovery_count": count_true("top5_recovered"),
        "invalid_top1_count": invalid_top1,
        "top1_validity_unavailable_count": unavailable_top1,
        "mean_scoring_regret_angstrom": (
            sum(regrets) / len(regrets) if regrets else None
        ),
        "preparation_failure_distribution": dict(sorted(preparation_failures.items())),
        "typed_failure_distribution": dict(sorted(failure_counts.items())),
        "lane_contribution": {
            lane: dict(sorted(counter.items())) for lane, counter in sorted(lanes.items())
        },
    }
    return {"cases": summaries, "aggregate": aggregate}


def _load_run(
    manifest_path: Path,
    result_root: Path,
    fresh_case_ids: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest, rows = _load_manifest(manifest_path)
    overlap = sorted(case_id for case_id, _ in rows if case_id in fresh_case_ids)
    if overlap:
        raise D1DevelopmentError(
            "D1 manifest overlaps the protected fresh registry: " + ",".join(overlap)
        )
    cases = [
        _load_case_result(
            _relative_regular_file(result_root, path, name=f"result_path[{case_id}]"),
            case_id,
        )
        for case_id, path in rows
    ]
    return manifest, cases


def _case_id_set(summary: dict[str, Any], key: str) -> set[str]:
    return {
        str(row["case_id"])
        for row in summary["cases"]
        if row.get(key) is True
    }


def build_report(
    *,
    profile_path: Path,
    manifest_path: Path,
    fresh_registry_path: Path,
    result_root: Path,
    baseline_manifest_path: Path | None = None,
    baseline_result_root: Path | None = None,
) -> dict[str, Any]:
    profile = _verify_profile(profile_path)
    fresh_ids = set(_load_fresh_case_ids(fresh_registry_path))
    manifest, cases = _load_run(manifest_path, result_root, fresh_ids)
    current = _aggregate(cases)

    baseline_section: dict[str, Any] | None = None
    if baseline_manifest_path is not None:
        baseline_root = baseline_result_root or result_root
        baseline_manifest, baseline_cases = _load_run(
            baseline_manifest_path, baseline_root, fresh_ids
        )
        current_ids = [row["case_id"] for row in current["cases"]]
        baseline_ids = [row["case_id"] for row in _aggregate(baseline_cases)["cases"]]
        if current_ids != baseline_ids:
            raise D1DevelopmentError(
                "baseline manifest must preserve the same ordered 32-case cohort"
            )
        baseline_summary = _aggregate(baseline_cases)
        comparisons: dict[str, list[str]] = {}
        for metric in (
            "proposal_oracle_recovered",
            "valid_proposal_oracle_recovered",
            "top1_recovered",
            "top5_recovered",
        ):
            current_set = _case_id_set(current, metric)
            baseline_set = _case_id_set(baseline_summary, metric)
            comparisons[f"new_{metric}_case_ids"] = sorted(current_set - baseline_set)
            comparisons[f"lost_{metric}_case_ids"] = sorted(baseline_set - current_set)
        baseline_section = {
            "manifest_sha256": _sha256_path(baseline_manifest_path),
            "manifest_projection_sha256": _sha256_value(baseline_manifest),
            "summary": baseline_summary,
            "comparison": comparisons,
        }

    report: dict[str, Any] = {
        "schema_id": REPORT_SCHEMA_ID,
        "profile_id": PROFILE_ID,
        "profile_sha256": _sha256_path(profile_path),
        "profile_projection_sha256": _sha256_value(profile),
        "manifest_sha256": _sha256_path(manifest_path),
        "manifest_projection_sha256": _sha256_value(manifest),
        "fresh_registry_sha256": _sha256_path(fresh_registry_path),
        "development_repeatable": True,
        "result_informed_iteration_allowed": True,
        "candidate_denominator": CANDIDATE_DENOMINATOR,
        "rmsd_threshold_angstrom": RMSD_THRESHOLD_ANGSTROM,
        "current": current,
        "baseline": baseline_section,
        "authority": {
            "reservation_authorized": False,
            "molecular_holdout_execution_authorized": False,
            "fresh_128_execution_authorized": False,
            "stage0_admission_authorized": False,
            "benchmark_claim_authorized": False,
            "scientific_claim_authorized": False,
            "product_authorized": False,
            "customer_pose_emission_authorized": False,
        },
    }
    report["report_sha256"] = _sha256_value(report)
    return report


def _write_absent(path: Path, document: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document, allow_nan=False, indent=2, ensure_ascii=True, sort_keys=True
    ) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise D1DevelopmentError(f"output already exists: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--profile",
        type=Path,
        default=root / "config/engine_v2_d1_development_profile_v1.json",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fresh-case-registry", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--baseline-result-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(
            profile_path=args.profile,
            manifest_path=args.manifest,
            fresh_registry_path=args.fresh_case_registry,
            result_root=args.result_root,
            baseline_manifest_path=args.baseline_manifest,
            baseline_result_root=args.baseline_result_root,
        )
        _write_absent(args.output, report)
    except D1DevelopmentError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output.resolve()),
                "report_sha256": report["report_sha256"],
                "authority_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
