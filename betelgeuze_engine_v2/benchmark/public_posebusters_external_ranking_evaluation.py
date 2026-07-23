"""Evaluate frozen external-engine PoseBusters ranking policies.

This module consumes the exact failure-inclusive Vina/GNINA/Smina
``split_role=test`` partitions.  It evaluates only score policies already
fixed by each source execution: Vina total energy, GNINA CNN pose score, and
Smina minimized affinity.  The policies must reproduce source pose order
before labels are evaluated.

The result is actual descriptive public external-reference evidence.  It is
not a fitted internal scorer result: 290/291 cases per engine remain explicit
failures, external-model training leakage has not been audited, and no
independent rerun or scientific review is bundled.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import stat
import tempfile
from typing import Any

import betelgeuze_engine_v2.docking.calibration as calibration_module
from betelgeuze_engine_v2.docking.calibration import (
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
)

from . import public_posebusters_pose_ranking_test_partition as partition_module
from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_pose_ranking_intake import (
    POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
    POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES,
    POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS,
    PoseBustersPoseRankingIntakeError,
    _LoadedReceipt,
    _load_receipt,
)
from .public_posebusters_pose_ranking_test_partition import (
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID,
)


POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_evaluation_input/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_score_policy/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_case/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_metric/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_CURVE_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_curve_metric/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_family/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_engine/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_evaluation/1.0.0"
)

POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_INPUT_BYTES = 40 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_RECEIPT_BYTES = 48 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_Z = 1.959963984540054
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES = 2_000
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SEED = 91_337

POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256 = {
    "vina": "0333d699f561e73b6b9032b0bfe7ff48dc60a9b6c32723d2fa6b027b74610296",
    "gnina": "dc77bf4001446dfeae734fb85f99c441f99a7fa4b4073f5e9faa429e0d8c42e1",
    "smina": "29a4b2085947b44294d5e08019fff9797403293a1a472513e46ea353d42c74c6",
}

POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES = {
    "vina": {
        "source_term_id": "vina.total",
        "source_direction": "minimize",
        "ascending_evaluation_transform": "identity",
        "source_pose_sort_order": "vina_total_energy",
    },
    "gnina": {
        "source_term_id": "gnina.cnn_pose_score",
        "source_direction": "maximize",
        "ascending_evaluation_transform": "negate",
        "source_pose_sort_order": "CNNscore",
    },
    "smina": {
        "source_term_id": "smina.minimized_affinity_kcal_per_mol",
        "source_direction": "minimize",
        "ascending_evaluation_transform": "identity",
        "source_pose_sort_order": "minimized_affinity",
    },
}

POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION = {
    "all_case_denominator": 308,
    "bootstrap_sample_count": (
        POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES
    ),
    "bootstrap_seed": POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SEED,
    "bootstrap_unit": "case",
    "confidence_interval_level": (
        POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL
    ),
    "curve_metric": "tie_invariant_average_precision_pr_auc",
    "family_scopes": [
        "observed_sequence_proxy",
        "exact_pfam_set_or_missing",
        "pfam_multi_label_or_missing",
    ],
    "fixed_score_policies": POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES,
    "policy_origin": "source_engine_sort_policy_fixed_before_label_evaluation",
    "ratio_interval": "wilson_score_binomial",
    "source_order_requirement": "fixed_policy_scores_must_be_monotonic",
    "split_role": "test",
    "test_label_fit_policy": "forbidden",
    "top_k_tie_policy": "include_all_scores_tied_at_kth_boundary",
}
POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION
)

POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_SCIENTIFIC_BLOCKERS = (
    "external_engines_are_offline_references_not_the_internal_product_scorer",
    "only_strictly_prepared_chemistry_subset_has_scored_poses",
    "all_case_execution_coverage_is_incomplete",
    "physical_validity_is_source_metric_only_in_this_ranking_projection",
    "observed_sequence_proxy_is_not_a_biological_target_family",
    "pfam_annotation_is_missing_for_part_of_the_all_case_denominator",
    "external_model_training_overlap_audit_missing",
    "independent_external_host_rerun_missing",
    "independent_scientific_review_missing",
    "public_docking_product_claim_not_authorized",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_PFAM_MISSING_ID = "pfam_missing"


class PoseBustersExternalRankingEvaluationError(ValueError):
    """External ranking source, metric, or claim evidence is invalid."""


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersExternalRankingEvaluationError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersExternalRankingEvaluationError(f"{name} must be a list")
    return value


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
    allow_empty: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not value and not allow_empty)
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{name} must be bounded single-line text"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersExternalRankingEvaluationError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersExternalRankingEvaluationError(f"{name} must be boolean")
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PoseBustersExternalRankingEvaluationError(
            f"{name} must be a finite number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersExternalRankingEvaluationError(
            f"{name} must be a finite number"
        )
    return number


def _engine(value: object) -> str:
    engine = _text(value, name="engine ID")
    if engine not in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        raise PoseBustersExternalRankingEvaluationError(
            "engine ID must be vina, gnina, or smina"
        )
    return engine


def _case_id(value: object) -> str:
    case = _text(value, name="case ID", maximum=64)
    if (
        case.count("_") != 1
        or case != case.upper()
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
            for character in case
        )
    ):
        raise PoseBustersExternalRankingEvaluationError(
            "PoseBusters case ID is invalid"
        )
    return case


def _binary64_hex(value: float) -> str:
    number = _finite(value, name="binary64 value")
    return number.hex()


def _policy_document(engine: str) -> dict[str, Any]:
    source = POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES[engine]
    document = {
        "schema_id": POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICY_SCHEMA_ID,
        "engine_id": engine,
        "source_term_id": source["source_term_id"],
        "source_direction": source["source_direction"],
        "ascending_evaluation_transform": source["ascending_evaluation_transform"],
        "source_pose_sort_order": source["source_pose_sort_order"],
        "scoring_protocol_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256[engine]
        ),
        "policy_fixed_before_test_label_evaluation": True,
        "test_labels_used_to_select_policy": False,
        "fit_or_calibration_performed": False,
    }
    document["policy_sha256"] = _canonical_sha256(document)
    return document


def _ordering_score(engine: str, source_score: float) -> float:
    policy = POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES[engine]
    if policy["ascending_evaluation_transform"] == "identity":
        return source_score
    if policy["ascending_evaluation_transform"] == "negate":
        return -source_score
    raise AssertionError("unsupported frozen score transform")


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0 or not 0 <= numerator <= denominator:
        raise PoseBustersExternalRankingEvaluationError(
            "metric numerator/denominator is invalid"
        )
    estimate = numerator / denominator
    z = POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_Z
    z_squared = z * z
    scale = 1.0 + z_squared / denominator
    center = (estimate + z_squared / (2.0 * denominator)) / scale
    margin = (
        z
        * math.sqrt(
            (estimate * (1.0 - estimate) + z_squared / (4.0 * denominator))
            / denominator
        )
        / scale
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _ratio_metric(
    metric_id: str,
    numerator: int,
    denominator: int,
    *,
    denominator_scope: str,
) -> dict[str, Any]:
    if denominator < 0 or numerator < 0 or numerator > denominator:
        raise PoseBustersExternalRankingEvaluationError(
            "ratio metric counts are invalid"
        )
    if denominator == 0:
        return {
            "schema_id": POSEBUSTERS_EXTERNAL_RANKING_METRIC_SCHEMA_ID,
            "metric_id": metric_id,
            "denominator_scope": denominator_scope,
            "numerator": numerator,
            "denominator": denominator,
            "estimate": None,
            "estimate_binary64_hex": None,
            "confidence_level": (
                POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL
            ),
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": None,
            "confidence_interval_low_binary64_hex": None,
            "confidence_interval_high": None,
            "confidence_interval_high_binary64_hex": None,
            "available": False,
            "blockers": ["metric_denominator_zero"],
        }
    estimate = numerator / denominator
    low, high = _wilson_interval(numerator, denominator)
    return {
        "schema_id": POSEBUSTERS_EXTERNAL_RANKING_METRIC_SCHEMA_ID,
        "metric_id": metric_id,
        "denominator_scope": denominator_scope,
        "numerator": numerator,
        "denominator": denominator,
        "estimate": estimate,
        "estimate_binary64_hex": _binary64_hex(estimate),
        "confidence_level": (POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL),
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_interval_low": low,
        "confidence_interval_low_binary64_hex": _binary64_hex(low),
        "confidence_interval_high": high,
        "confidence_interval_high_binary64_hex": _binary64_hex(high),
        "available": True,
        "blockers": [],
    }


def _average_precision(
    scored_labels: Sequence[tuple[float, bool]],
) -> float | None:
    positive_count = sum(label for _, label in scored_labels)
    negative_count = len(scored_labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None
    ordered = sorted(
        (
            (_finite(score, name="ordering score"), bool(label))
            for score, label in scored_labels
        ),
        key=lambda row: row[0],
    )
    true_positive = 0
    false_positive = 0
    previous_recall = 0.0
    area = 0.0
    index = 0
    while index < len(ordered):
        score = ordered[index][0]
        group_positive = 0
        group_negative = 0
        while index < len(ordered) and ordered[index][0] == score:
            if ordered[index][1]:
                group_positive += 1
            else:
                group_negative += 1
            index += 1
        true_positive += group_positive
        false_positive += group_negative
        recall = true_positive / positive_count
        precision = true_positive / (true_positive + false_positive)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return float(area)


def _curve_metric(
    cases: Sequence[dict[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    per_case: list[list[tuple[float, bool]]] = []
    successful_count = 0
    failure_count = 0
    for case in cases:
        case_rows = [
            (
                float.fromhex(
                    _text(
                        row.get("ordering_score_binary64_hex"),
                        name="ordering score",
                        maximum=128,
                    )
                ),
                _boolean(row.get("native_like"), name="native-like label"),
            )
            for row in _list(
                case.get("ranked_pose_rows"),
                name="case ranked pose rows",
            )
        ]
        successful_count += len(case_rows)
        failure_count += _integer(
            case.get("failure_observation_count"),
            name="case failure observation count",
        )
        per_case.append(case_rows)
    scored_labels = [row for case_rows in per_case for row in case_rows]
    positive_count = sum(label for _, label in scored_labels)
    negative_count = len(scored_labels) - positive_count
    value = _average_precision(scored_labels)
    blockers: list[str] = []
    if positive_count == 0:
        blockers.append("positive_successful_pose_class_missing")
    if negative_count == 0:
        blockers.append("negative_successful_pose_class_missing")

    valid_samples: list[float] = []
    if value is not None:
        seed = int.from_bytes(
            hashlib.sha256(
                (
                    f"{POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SEED}:"
                    f"{scope}:average_precision_pr_auc"
                ).encode("utf-8")
            ).digest()[:8],
            "big",
        )
        generator = random.Random(seed)
        case_count = len(per_case)
        for _ in range(POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES):
            sampled = [
                row
                for _ in range(case_count)
                for row in per_case[generator.randrange(case_count)]
            ]
            estimate = _average_precision(sampled)
            if estimate is not None:
                valid_samples.append(estimate)
        if not valid_samples:
            blockers.append("case_cluster_bootstrap_two_class_replicates_missing")
        elif len(valid_samples) != (
            POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES
        ):
            blockers.append("case_cluster_bootstrap_dropped_single_class_replicates")

    low: float | None = None
    high: float | None = None
    if valid_samples:
        ordered = sorted(valid_samples)
        alpha = (1.0 - POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL) / 2.0
        low_index = min(
            len(ordered) - 1,
            int(math.floor(alpha * len(ordered))),
        )
        high_index = min(
            len(ordered) - 1,
            int(math.ceil((1.0 - alpha) * len(ordered))) - 1,
        )
        low = float(ordered[low_index])
        high = float(ordered[high_index])

    return {
        "schema_id": POSEBUSTERS_EXTERNAL_RANKING_CURVE_METRIC_SCHEMA_ID,
        "metric_id": "average_precision_pr_auc",
        "value": value,
        "value_binary64_hex": None if value is None else _binary64_hex(value),
        "confidence_level": (POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIDENCE_LEVEL),
        "confidence_interval_low": low,
        "confidence_interval_low_binary64_hex": (
            None if low is None else _binary64_hex(low)
        ),
        "confidence_interval_high": high,
        "confidence_interval_high_binary64_hex": (
            None if high is None else _binary64_hex(high)
        ),
        "all_case_denominator": len(cases),
        "all_pose_observation_denominator": successful_count + failure_count,
        "successful_labeled_pose_count": successful_count,
        "positive_pose_count": positive_count,
        "negative_pose_count": negative_count,
        "failure_observation_count": failure_count,
        "successful_pose_observation_coverage": (
            successful_count / (successful_count + failure_count)
        ),
        "bootstrap_unit": "case",
        "bootstrap_requested_sample_count": (
            POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES
        ),
        "bootstrap_valid_sample_count": len(valid_samples),
        "tie_policy": "equal_scores_evaluated_as_one_threshold_group",
        "available": value is not None,
        "blockers": blockers,
    }


def _calibration_row(document: Mapping[str, Any]) -> PoseRankingCalibrationRow:
    row = _mapping(document, name="calibration row")
    term_values = {
        _text(key, name="term ID"): _finite(value, name=f"{key} value")
        for key, value in _mapping(
            row.get("term_values"),
            name="term values",
        ).items()
    }
    try:
        candidate = PoseRankingCalibrationRow(
            suite_id=row.get("suite_id"),
            case_id=row.get("case_id"),
            pose_id=row.get("pose_id"),
            target_id=row.get("target_id"),
            target_family=row.get("target_family"),
            split_role=row.get("split_role"),
            scoring_protocol_sha256=row.get("scoring_protocol_sha256"),
            preparation_profile_sha256=row.get("preparation_profile_sha256"),
            receptor_sha256=row.get("receptor_sha256"),
            ligand_sha256=row.get("ligand_sha256"),
            scaffold_sha256=row.get("scaffold_sha256"),
            pose_sha256=row.get("pose_sha256"),
            status=row.get("status"),
            term_values=term_values,
            native_like=row.get("native_like"),
            error_code=row.get("error_code"),
            schema_id=row.get("schema_id"),
        )
    except (TypeError, ValueError) as exc:
        raise PoseBustersExternalRankingEvaluationError(
            "calibration row violates its exact contract"
        ) from exc
    if candidate.to_dict() != row:
        raise PoseBustersExternalRankingEvaluationError(
            "calibration row is not in canonical form"
        )
    return candidate


def _calibration_partition(
    document: Mapping[str, Any],
) -> PoseRankingCalibrationPartition:
    source = _mapping(document, name="calibration partition")
    rows = tuple(
        _calibration_row(_mapping(row, name="calibration row"))
        for row in _list(source.get("rows"), name="calibration rows")
    )
    try:
        partition = PoseRankingCalibrationPartition(
            dataset_id=source.get("dataset_id"),
            dataset_version=source.get("dataset_version"),
            split_role=source.get("split_role"),
            rows=rows,
            schema_id=source.get("schema_id"),
        )
    except (TypeError, ValueError) as exc:
        raise PoseBustersExternalRankingEvaluationError(
            "calibration partition violates its exact contract"
        ) from exc
    if partition.to_dict() != source:
        raise PoseBustersExternalRankingEvaluationError(
            "calibration partition is not in canonical form"
        )
    return partition


def _load_source(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
) -> _LoadedReceipt:
    try:
        return _load_receipt(
            receipt_path,
            expected_schema_id=(
                POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID
            ),
            expected_receipt_sha256=expected_receipt_sha256,
        )
    except PoseBustersPoseRankingIntakeError as exc:
        raise PoseBustersExternalRankingEvaluationError(
            "test-partition source receipt is invalid"
        ) from exc


def _source_case_metadata(
    payload: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    rows = _list(payload.get("case_rows"), name="source case rows")
    if len(rows) != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR:
        raise PoseBustersExternalRankingEvaluationError(
            "source case rows must retain all 308 cases"
        )
    parsed: list[tuple[str, dict[str, Any]]] = []
    for raw in rows:
        row = _mapping(raw, name="source case row")
        case = _case_id(row.get("case_id"))
        proxy = _text(
            row.get("observed_sequence_proxy_id"),
            name="observed sequence proxy ID",
        )
        pfam_ids = tuple(
            _text(value, name="Pfam ID", maximum=32)
            for value in _list(row.get("pfam_ids"), name="Pfam IDs")
        )
        if pfam_ids != tuple(sorted(set(pfam_ids))):
            raise PoseBustersExternalRankingEvaluationError(
                "Pfam IDs must be unique and sorted"
            )
        pfam_set = row.get("pfam_set_id")
        if pfam_set is not None:
            pfam_set = _text(pfam_set, name="Pfam set ID")
        if (pfam_set is None) != (not pfam_ids):
            raise PoseBustersExternalRankingEvaluationError(
                "Pfam set identity and Pfam IDs disagree"
            )
        parsed.append(
            (
                case,
                {
                    "case_id": case,
                    "target_id": _text(row.get("target_id"), name="target ID"),
                    "observed_sequence_proxy_id": proxy,
                    "pfam_ids": pfam_ids,
                    "pfam_set_id": pfam_set,
                    "biological_annotation_status": _text(
                        row.get("biological_annotation_status"),
                        name="biological annotation status",
                    ),
                },
            )
        )
    case_ids = tuple(case for case, _ in parsed)
    if case_ids != tuple(sorted(case_ids)) or len(set(case_ids)) != len(case_ids):
        raise PoseBustersExternalRankingEvaluationError(
            "source case IDs must be unique and sorted"
        )
    return case_ids, dict(parsed)


def _source_rank(engine: str, case: str, pose_id: str) -> int:
    prefix = f"{engine}:{case}:pose:"
    if not pose_id.startswith(prefix):
        raise PoseBustersExternalRankingEvaluationError(
            "successful pose ID does not retain its source rank"
        )
    suffix = pose_id[len(prefix) :]
    if not suffix.isdigit() or int(suffix) < 1:
        raise PoseBustersExternalRankingEvaluationError(
            "successful pose ID source rank is invalid"
        )
    return int(suffix)


def _evaluate_case(
    engine: str,
    case: str,
    rows: Sequence[PoseRankingCalibrationRow],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    successful = [row for row in rows if row.status == "success"]
    failures = [row for row in rows if row.status == "failure"]
    policy = POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES[engine]
    term_id = policy["source_term_id"]

    source_ranked: list[tuple[int, PoseRankingCalibrationRow, float, float]] = []
    for row in successful:
        if term_id not in row.term_values:
            raise PoseBustersExternalRankingEvaluationError(
                f"{engine} source policy term is missing"
            )
        source_score = _finite(
            row.term_values[term_id],
            name=f"{engine} source score",
        )
        ordering_score = _ordering_score(engine, source_score)
        source_ranked.append(
            (
                _source_rank(engine, case, row.pose_id),
                row,
                source_score,
                ordering_score,
            )
        )
    source_ranked.sort(key=lambda item: item[0])
    if tuple(item[0] for item in source_ranked) != tuple(
        range(1, len(source_ranked) + 1)
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} source pose ranks are not contiguous"
        )
    ordering_scores = tuple(item[3] for item in source_ranked)
    if ordering_scores != tuple(sorted(ordering_scores)):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} fixed policy does not reproduce source pose ordering"
        )

    ranked = sorted(source_ranked, key=lambda item: (item[3], item[1].pose_id))
    ranked_rows: list[dict[str, Any]] = []
    for source_rank, row, source_score, ordering_score in ranked:
        ranked_rows.append(
            {
                "pose_id": row.pose_id,
                "pose_coordinate_sha256": row.pose_sha256,
                "source_pose_rank": source_rank,
                "source_score_binary64_hex": _binary64_hex(source_score),
                "ordering_score_binary64_hex": _binary64_hex(ordering_score),
                "native_like": bool(row.native_like),
            }
        )

    top1_rows: list[dict[str, Any]] = []
    top5_rows: list[dict[str, Any]] = []
    if ranked_rows:
        best = ranked[0][3]
        top1_rows = [
            row
            for item, row in zip(ranked, ranked_rows, strict=True)
            if item[3] == best
        ]
        fifth_index = min(4, len(ranked) - 1)
        fifth_score = ranked[fifth_index][3]
        top5_rows = [
            row
            for item, row in zip(ranked, ranked_rows, strict=True)
            if item[3] <= fifth_score
        ]

    failure_rows = sorted(failures, key=lambda row: row.pose_id)
    return {
        "schema_id": POSEBUSTERS_EXTERNAL_RANKING_CASE_SCHEMA_ID,
        "engine_id": engine,
        "case_id": case,
        "target_id": metadata["target_id"],
        "observed_sequence_proxy_id": metadata["observed_sequence_proxy_id"],
        "pfam_ids": list(metadata["pfam_ids"]),
        "pfam_set_id": metadata["pfam_set_id"],
        "biological_annotation_status": metadata["biological_annotation_status"],
        "status": "scored" if successful else "failure",
        "pose_observation_count": len(rows),
        "successful_pose_count": len(successful),
        "failure_observation_count": len(failures),
        "failure_observation_ids": [row.pose_id for row in failure_rows],
        "failure_codes": [row.error_code for row in failure_rows],
        "ranked_pose_rows": ranked_rows,
        "top1_tie_inclusive_pose_count": len(top1_rows),
        "top5_tie_inclusive_pose_count": len(top5_rows),
        "top1_native_like": any(row["native_like"] for row in top1_rows),
        "top5_native_like": any(row["native_like"] for row in top5_rows),
        "source_order_reproduced": bool(successful),
    }


def _case_metrics(cases: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    denominator = len(cases)
    scored = sum(case["status"] == "scored" for case in cases)
    top1 = sum(case["top1_native_like"] for case in cases)
    top5 = sum(case["top5_native_like"] for case in cases)
    return [
        _ratio_metric(
            "scored_case_coverage",
            scored,
            denominator,
            denominator_scope="all_retained_cases",
        ),
        _ratio_metric(
            "top1_native_like_rate_all_cases",
            top1,
            denominator,
            denominator_scope="all_retained_cases",
        ),
        _ratio_metric(
            "top5_native_like_rate_all_cases",
            top5,
            denominator,
            denominator_scope="all_retained_cases",
        ),
        _ratio_metric(
            "top1_native_like_rate_scored_cases",
            top1,
            scored,
            denominator_scope="cases_with_at_least_one_scored_pose",
        ),
        _ratio_metric(
            "top5_native_like_rate_scored_cases",
            top5,
            scored,
            denominator_scope="cases_with_at_least_one_scored_pose",
        ),
    ]


def _family_groups(
    cases: Sequence[dict[str, Any]],
    *,
    family_kind: str,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if family_kind == "observed_sequence_proxy":
            family_ids = (case["observed_sequence_proxy_id"],)
        elif family_kind == "exact_pfam_set_or_missing":
            family_ids = (case["pfam_set_id"] or _PFAM_MISSING_ID,)
        elif family_kind == "pfam_multi_label_or_missing":
            family_ids = tuple(case["pfam_ids"]) or (_PFAM_MISSING_ID,)
        else:
            raise AssertionError("unsupported frozen family kind")
        for family_id in family_ids:
            groups[family_id].append(case)
    return groups


def _family_scope(
    cases: Sequence[dict[str, Any]],
    *,
    engine: str,
    family_kind: str,
) -> dict[str, Any]:
    groups = _family_groups(cases, family_kind=family_kind)
    rows: list[dict[str, Any]] = []
    for family_id in sorted(groups):
        members = sorted(groups[family_id], key=lambda row: row["case_id"])
        rows.append(
            {
                "schema_id": POSEBUSTERS_EXTERNAL_RANKING_FAMILY_SCHEMA_ID,
                "engine_id": engine,
                "family_kind": family_kind,
                "family_id": family_id,
                "family_semantics": (
                    "not_a_biological_target_family"
                    if family_kind == "observed_sequence_proxy"
                    else (
                        "missing_biological_annotation_bucket"
                        if family_id == _PFAM_MISSING_ID
                        else (
                            "exact_disjoint_pfam_set"
                            if family_kind == "exact_pfam_set_or_missing"
                            else "overlapping_pfam_multi_label_family"
                        )
                    )
                ),
                "member_case_count": len(members),
                "case_ids": [row["case_id"] for row in members],
                "metrics": _case_metrics(members)[:3],
                "pose_curve_metric": _curve_metric(
                    members,
                    scope=f"{engine}:{family_kind}:{family_id}",
                ),
            }
        )
    return {
        "family_kind": family_kind,
        "family_count": len(rows),
        "all_case_membership_complete": True,
        "memberships_are_disjoint": family_kind != "pfam_multi_label_or_missing",
        "biological_annotation_complete": family_kind == "observed_sequence_proxy"
        or all(row["pfam_set_id"] is not None for row in cases),
        "family_rows": rows,
    }


def _source_summary(
    payload: Mapping[str, Any],
    engine: str,
) -> dict[str, Any]:
    validation = _mapping(
        payload.get("ranking_metric_validation"),
        name="ranking metric validation",
    )
    if (
        validation.get("validated") is not True
        or validation.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersExternalRankingEvaluationError(
            "source ranking metric validation is incomplete"
        )
    rows = {
        _engine(row.get("engine_id")): row
        for row in (
            _mapping(item, name="source engine summary")
            for item in _list(
                validation.get("engine_summaries"),
                name="source engine summaries",
            )
        )
    }
    if set(rows) != set(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES):
        raise PoseBustersExternalRankingEvaluationError(
            "source engine summaries are incomplete"
        )
    source = rows[engine]
    return {
        "source_metric_root_sha256": _digest(
            validation.get("source_metric_root_sha256"),
            name="source metric root",
        ),
        "successful_pose_row_count": _integer(
            source.get("successful_pose_row_count"),
            name="source successful pose count",
        ),
        "failure_row_count": _integer(
            source.get("failure_row_count"),
            name="source failure row count",
        ),
        "evaluated_case_count": _integer(
            source.get("evaluated_case_count"),
            name="source evaluated case count",
        ),
        "physically_valid_pose_count": _integer(
            source.get("physically_valid_pose_count"),
            name="source physically valid pose count",
        ),
        "top_1_valid_native_like_case_count": _integer(
            source.get("top_1_valid_native_like_case_count"),
            name="source Top-1 valid native-like count",
        ),
        "top_5_valid_native_like_case_count": _integer(
            source.get("top_5_valid_native_like_case_count"),
            name="source Top-5 valid native-like count",
        ),
    }


def _source_validity_metrics(
    source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    successful = int(source["successful_pose_row_count"])
    return [
        _ratio_metric(
            "physically_valid_pose_rate_scored_poses",
            int(source["physically_valid_pose_count"]),
            successful,
            denominator_scope="successfully_scored_pose_rows",
        ),
        _ratio_metric(
            "top1_valid_native_like_rate_all_cases",
            int(source["top_1_valid_native_like_case_count"]),
            POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            denominator_scope="all_308_cases",
        ),
        _ratio_metric(
            "top5_valid_native_like_rate_all_cases",
            int(source["top_5_valid_native_like_case_count"]),
            POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            denominator_scope="all_308_cases",
        ),
    ]


def _engine_evaluation(
    engine_document: Mapping[str, Any],
    *,
    metadata: Mapping[str, Mapping[str, Any]],
    source_payload: Mapping[str, Any],
) -> dict[str, Any]:
    document = _mapping(engine_document, name="source engine partition")
    engine = _engine(document.get("engine_id"))
    if (
        document.get("split_role") != "test"
        or document.get("calibration_fit_performed") is not False
        or document.get("test_labels_used_for_fit") is not False
        or document.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} source partition violates the test-only contract"
        )
    expected_term_order = [
        f"{engine}.{term}"
        for term in POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
    ]
    if document.get("source_term_order") != expected_term_order:
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} source term order changed"
        )
    protocol = _digest(
        document.get("scoring_protocol_sha256"),
        name=f"{engine} scoring protocol",
    )
    if protocol != POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256[engine]:
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} scoring protocol changed"
        )

    partition = _calibration_partition(
        _mapping(document.get("partition"), name=f"{engine} partition")
    )
    if (
        partition.split_role != "test"
        or partition.fingerprint_sha256
        != _digest(
            document.get("partition_fingerprint_sha256"),
            name=f"{engine} partition fingerprint",
        )
        or partition.identity_fingerprint_sha256
        != _digest(
            document.get("partition_identity_fingerprint_sha256"),
            name=f"{engine} partition identity fingerprint",
        )
        or partition.case_ids != tuple(sorted(metadata))
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} partition identity or denominator is invalid"
        )
    expected_terms = set(expected_term_order)
    if set(partition.term_ids) != expected_terms:
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} partition term schema changed"
        )

    grouped: dict[str, list[PoseRankingCalibrationRow]] = defaultdict(list)
    for row in partition.rows:
        if row.scoring_protocol_sha256 != protocol:
            raise PoseBustersExternalRankingEvaluationError(
                f"{engine} row scoring protocol changed"
            )
        grouped[row.case_id].append(row)
    cases = [
        _evaluate_case(engine, case, grouped[case], metadata[case])
        for case in sorted(metadata)
    ]
    successful_count = sum(case["successful_pose_count"] for case in cases)
    failure_count = sum(case["failure_observation_count"] for case in cases)
    if (
        successful_count
        != _integer(
            document.get("successful_pose_row_count"),
            name=f"{engine} successful pose count",
        )
        or failure_count
        != _integer(
            document.get("failure_observation_row_count"),
            name=f"{engine} failure observation count",
        )
        or successful_count + failure_count
        != _integer(
            document.get("partition_row_count"),
            name=f"{engine} partition row count",
        )
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} partition row counts are invalid"
        )
    source_summary = _source_summary(source_payload, engine)
    scored_count = sum(case["status"] == "scored" for case in cases)
    top1_count = sum(case["top1_native_like"] for case in cases)
    top5_count = sum(case["top5_native_like"] for case in cases)
    if (
        source_summary["successful_pose_row_count"] != successful_count
        or source_summary["failure_row_count"] != failure_count
        or source_summary["evaluated_case_count"] != scored_count
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} source metric counts disagree with the partition"
        )
    source_engine_rows = {
        _engine(row.get("engine_id")): row
        for row in (
            _mapping(item, name="ranking validation engine summary")
            for item in _list(
                _mapping(
                    source_payload.get("ranking_metric_validation"),
                    name="ranking validation",
                ).get("engine_summaries"),
                name="ranking validation engine summaries",
            )
        )
    }
    source_engine = source_engine_rows[engine]
    if (
        _integer(
            source_engine.get("top_1_native_like_case_count"),
            name="source Top-1 count",
        )
        != top1_count
        or _integer(
            source_engine.get("top_5_native_like_case_count"),
            name="source Top-5 count",
        )
        != top5_count
    ):
        raise PoseBustersExternalRankingEvaluationError(
            f"{engine} fixed policy does not reproduce source Top-K results"
        )

    all_case_metrics = _case_metrics(cases)
    all_case_metrics.extend(
        (
            _ratio_metric(
                "successful_pose_observation_coverage",
                successful_count,
                successful_count + failure_count,
                denominator_scope="success_and_failure_observation_rows",
            ),
            _ratio_metric(
                "native_like_pose_prevalence_scored_poses",
                sum(
                    row["native_like"]
                    for case in cases
                    for row in case["ranked_pose_rows"]
                ),
                successful_count,
                denominator_scope="successfully_scored_pose_rows",
            ),
        )
    )
    all_case_metrics.extend(_source_validity_metrics(source_summary))
    family_scopes = [
        _family_scope(cases, engine=engine, family_kind=kind)
        for kind in (
            "observed_sequence_proxy",
            "exact_pfam_set_or_missing",
            "pfam_multi_label_or_missing",
        )
    ]
    return {
        "schema_id": POSEBUSTERS_EXTERNAL_RANKING_ENGINE_SCHEMA_ID,
        "engine_id": engine,
        "score_policy": _policy_document(engine),
        "source_partition_fingerprint_sha256": partition.fingerprint_sha256,
        "source_partition_identity_fingerprint_sha256": (
            partition.identity_fingerprint_sha256
        ),
        "source_metric_root_sha256": source_summary["source_metric_root_sha256"],
        "all_case_denominator": len(cases),
        "scored_case_count": scored_count,
        "failure_case_count": len(cases) - scored_count,
        "successful_pose_count": successful_count,
        "failure_observation_count": failure_count,
        "source_order_reproduced_case_count": sum(
            case["status"] == "scored" and case["source_order_reproduced"]
            for case in cases
        ),
        "case_rows": cases,
        "metrics": all_case_metrics,
        "pose_curve_metric": _curve_metric(cases, scope=f"{engine}:overall"),
        "family_scopes": family_scopes,
        "source_physical_validity_evidence": {
            "per_pose_validity_rows_present_in_this_projection": False,
            "source_summary_counts_bound": True,
            **source_summary,
        },
        "score_policy_fit_performed": False,
        "test_labels_used_to_select_score_policy": False,
        "test_labels_used_for_evaluation": True,
    }


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    calibration_path = getattr(calibration_module, "__file__", None)
    partition_path = getattr(partition_module, "__file__", None)
    if not isinstance(calibration_path, str) or not isinstance(partition_path, str):
        raise PoseBustersExternalRankingEvaluationError(
            "ranking implementation source identity is unavailable"
        )
    return (
        (
            "posebusters_external_ranking_evaluation",
            _source_file_sha256(Path(__file__).resolve()),
        ),
        (
            "posebusters_pose_ranking_test_partition",
            _source_file_sha256(Path(partition_path).resolve()),
        ),
        (
            "pose_ranking_calibration_contract",
            _source_file_sha256(Path(calibration_path).resolve()),
        ),
    )


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    source: bytes,
) -> Path:
    if len(source) > POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_RECEIPT_BYTES:
        raise PoseBustersExternalRankingEvaluationError(
            "external ranking receipt exceeds its byte bound"
        )
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersExternalRankingEvaluationError(
                "external ranking output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


class PoseBustersExternalRankingEvaluationReceipt:
    """Canonical failure-inclusive external-engine ranking result."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersExternalRankingEvaluationError(
                "external ranking payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID
            or normalized.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or normalized.get("engine_count")
            != len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES)
            or normalized.get("split_role") != "test"
            or normalized.get("external_reference_result_materialized") is not True
            or normalized.get("complete_public_benchmark_result") is not False
            or normalized.get("score_policy_fit_performed") is not False
            or normalized.get("test_labels_used_for_fit") is not False
            or normalized.get("test_labels_used_to_select_score_policy") is not False
            or normalized.get("test_labels_used_for_evaluation") is not True
            or normalized.get("external_model_training_leakage_audit_present")
            is not False
            or normalized.get("leakage_control_passed") is not False
            or normalized.get("independent_external_rerun_present") is not False
            or normalized.get("scientifically_validated") is not False
            or normalized.get("public_docking_claim_authorized") is not False
            or normalized.get("claim_safe") is not False
        ):
            raise PoseBustersExternalRankingEvaluationError(
                "external ranking payload violates its result boundary"
            )
        self._payload_bytes = source

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(output_path, self.canonical_bytes())


def _build_posebusters_external_ranking_evaluation(
    test_partition_receipt_path: str | os.PathLike[str],
    *,
    expected_test_partition_receipt_sha256: str,
) -> PoseBustersExternalRankingEvaluationReceipt:
    expected = _digest(
        expected_test_partition_receipt_sha256,
        name="expected test-partition receipt",
    )
    source = _load_source(
        test_partition_receipt_path,
        expected_receipt_sha256=expected,
    )
    payload = source.payload
    if (
        payload.get("configuration_sha256") is None
        or payload.get("split_role") != "test"
        or payload.get("test_partition_materialized") is not True
        or payload.get("calibration_partition_materialized") is not True
        or payload.get("fit_partition_present") is not False
        or payload.get("calibration_fit_performed") is not False
        or payload.get("test_labels_used_for_fit") is not False
        or payload.get("all_case_denominator")
        != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersExternalRankingEvaluationError(
            "source test-partition result boundary is invalid"
        )
    case_ids, metadata = _source_case_metadata(payload)
    engine_documents = [
        _mapping(row, name="source engine partition")
        for row in _list(
            payload.get("engine_partitions"),
            name="source engine partitions",
        )
    ]
    if tuple(_engine(row.get("engine_id")) for row in engine_documents) != (
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ):
        raise PoseBustersExternalRankingEvaluationError(
            "source engine partitions must be complete and ordered"
        )
    evaluations = [
        _engine_evaluation(
            row,
            metadata=metadata,
            source_payload=payload,
        )
        for row in engine_documents
    ]
    source_members = _implementation_source_members()
    result = {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID),
        "dataset_id": _text(payload.get("dataset_id"), name="dataset ID"),
        "dataset_version": _text(
            payload.get("dataset_version"),
            name="dataset version",
        ),
        "configuration": POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION_SHA256
        ),
        "implementation_source_members": [
            {"role": role, "sha256": digest} for role, digest in source_members
        ],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "input_receipt": {
            "schema_id": POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_INPUT_SCHEMA_ID,
            "role": "posebusters_failure_inclusive_test_partitions",
            "source_schema_id": source.schema_id,
            "source_receipt_sha256": source.receipt_sha256,
            "source_file_sha256": source.file_sha256,
            "source_configuration_sha256": _digest(
                payload.get("configuration_sha256"),
                name="source configuration",
            ),
            "source_implementation_sha256": _digest(
                payload.get("implementation_source_sha256"),
                name="source implementation",
            ),
        },
        "all_case_denominator": len(case_ids),
        "engine_count": len(evaluations),
        "split_role": "test",
        "score_policies": [evaluation["score_policy"] for evaluation in evaluations],
        "engine_results": evaluations,
        "total_successful_pose_count": sum(
            evaluation["successful_pose_count"] for evaluation in evaluations
        ),
        "total_failure_observation_count": sum(
            evaluation["failure_observation_count"] for evaluation in evaluations
        ),
        "external_reference_result_materialized": True,
        "complete_public_benchmark_result": False,
        "score_policy_fit_performed": False,
        "test_labels_used_for_fit": False,
        "test_labels_used_to_select_score_policy": False,
        "test_labels_used_for_evaluation": True,
        "external_model_training_leakage_audit_present": False,
        "leakage_control_passed": False,
        "independent_external_rerun_present": False,
        "independent_scientific_review_present": False,
        "scientific_blockers": list(
            POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "public_docking_claim_authorized": False,
        "claim_safe": False,
    }
    return PoseBustersExternalRankingEvaluationReceipt(result)


def materialize_posebusters_external_ranking_evaluation(
    test_partition_receipt_path: str | os.PathLike[str],
    *,
    expected_test_partition_receipt_sha256: str,
) -> PoseBustersExternalRankingEvaluationReceipt:
    """Build the exact three-engine external ranking result."""

    return _build_posebusters_external_ranking_evaluation(
        test_partition_receipt_path,
        expected_test_partition_receipt_sha256=(expected_test_partition_receipt_sha256),
    )


def verify_posebusters_external_ranking_evaluation_receipt(
    evaluation_receipt_path: str | os.PathLike[str],
    test_partition_receipt_path: str | os.PathLike[str],
    *,
    expected_test_partition_receipt_sha256: str,
) -> PoseBustersExternalRankingEvaluationReceipt:
    """Require byte equality with a fresh reconstruction from the test receipt."""

    try:
        source = _read_exact_regular_file(
            evaluation_receipt_path,
            maximum_bytes=(POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_RECEIPT_BYTES),
        )
        metadata = Path(evaluation_receipt_path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersExternalRankingEvaluationError(
            "external ranking output could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersExternalRankingEvaluationError(
            "external ranking output must be a bounded mode-0600 regular file"
        )
    expected = _build_posebusters_external_ranking_evaluation(
        test_partition_receipt_path,
        expected_test_partition_receipt_sha256=(expected_test_partition_receipt_sha256),
    )
    if source != expected.canonical_bytes():
        raise PoseBustersExternalRankingEvaluationError(
            "external ranking output differs from exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-external-ranking-evaluate",
        description=(
            "Evaluate fixed Vina/GNINA/Smina source ranking policies over the "
            "failure-inclusive PoseBusters test partitions without fitting."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--test-partition-receipt", required=True)
        subparser.add_argument(
            "--expected-test-partition-receipt-sha256",
            required=True,
        )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--evaluation-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "test_partition_receipt_path": args.test_partition_receipt,
        "expected_test_partition_receipt_sha256": (
            args.expected_test_partition_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_external_ranking_evaluation(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_external_ranking_evaluation_receipt(
            evaluation_receipt_path=args.evaluation_receipt,
            **common,
        )
    payload = receipt.to_dict()
    summaries = {}
    for row in payload["engine_results"]:
        curve = row["pose_curve_metric"]
        summaries[row["engine_id"]] = {
            "scored_case_count": row["scored_case_count"],
            "top1_all_case": next(
                metric["estimate"]
                for metric in row["metrics"]
                if metric["metric_id"] == "top1_native_like_rate_all_cases"
            ),
            "top5_all_case": next(
                metric["estimate"]
                for metric in row["metrics"]
                if metric["metric_id"] == "top5_native_like_rate_all_cases"
            ),
            "average_precision_pr_auc": curve["value"],
            "average_precision_ci_low": curve["confidence_interval_low"],
            "average_precision_ci_high": curve["confidence_interval_high"],
        }
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "total_successful_pose_count": payload["total_successful_pose_count"],
                "total_failure_observation_count": payload[
                    "total_failure_observation_count"
                ],
                "engine_summaries": summaries,
                "score_policy_fit_performed": False,
                "test_labels_used_for_fit": False,
                "external_reference_result_materialized": True,
                "complete_public_benchmark_result": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_EXTERNAL_RANKING_CASE_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_CURVE_METRIC_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_ENGINE_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_BOOTSTRAP_SAMPLES",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION_SHA256",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_INPUT_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_INPUT_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_EXTERNAL_RANKING_FAMILY_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_METRIC_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICIES",
    "POSEBUSTERS_EXTERNAL_RANKING_SCORE_POLICY_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256",
    "PoseBustersExternalRankingEvaluationError",
    "PoseBustersExternalRankingEvaluationReceipt",
    "materialize_posebusters_external_ranking_evaluation",
    "verify_posebusters_external_ranking_evaluation_receipt",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
