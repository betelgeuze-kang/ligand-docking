from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DockingGoldRow:
    complex_id: str
    pose_id: str
    pose_rank: int
    pose_rmsd_a: float | None = None
    score: float | None = None
    baseline_score: float | None = None
    affinity_label: float | None = None
    active_label: bool | None = None
    split_id: str = "heldout"
    abstained: bool = False
    chemistry_failures: tuple[str, ...] = ()
    chemistry_evidence_present: bool = False
    abstention_reasons: tuple[str, ...] = ()
    runtime_ms: float | None = None
    peak_memory_mb: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["chemistry_failures"] = list(self.chemistry_failures)
        payload["abstention_reasons"] = list(self.abstention_reasons)
        return payload


@dataclass(frozen=True)
class DockingGoldMetrics:
    schema_version: str
    status: str
    complex_count: int
    row_count: int
    pose_success_rmsd_threshold_a: float
    reference_pose_present: bool
    native_pose_present: bool
    top1_mean_rmsd_a: float | None
    top5_best_mean_rmsd_a: float | None
    top1_pose_success_rate: float
    top5_pose_success_rate: float
    ranking_spearman: float | None
    pr_auc: float | None
    topk_hit_rate: float | None
    decoy_rejection_rate: float | None
    baseline_ranking_spearman: float | None
    refine_ranking_spearman_delta: float | None
    refine_improvement_observed: bool
    heldout_complex_count: int
    chirality_failure_rate: float
    tautomer_failure_rate: float
    protonation_failure_rate: float
    chemistry_evidence_coverage: float
    abstention_precision: float | None
    mean_runtime_ms: float | None
    peak_memory_mb: float | None
    blockers: tuple[str, ...] = field(default_factory=tuple)
    claim_boundary: str = (
        "Restricted local docking gold-slice metric evaluator. It computes row-level pose, ranking, enrichment, "
        "chemistry-failure, abstention, runtime, and memory metrics from caller-provided rows. It does not download "
        "public datasets, run docking, calibrate affinity, claim CASF/PDBbind parity, or promote product claims."
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def _finite_float(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        average_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = average_rank
        i = j
    return ranks


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    den_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if den_a <= 0.0 or den_b <= 0.0:
        return None
    return float(num / (den_a * den_b))


def _spearman(labels: list[float], scores: list[float]) -> float | None:
    if len(set(labels)) < 2 or len(set(scores)) < 2:
        return None
    return _pearson(_rankdata(labels), _rankdata(scores))


def _average_precision(label_score_pairs: list[tuple[bool, float]]) -> float | None:
    positives = sum(1 for label, _score in label_score_pairs if label)
    negatives = len(label_score_pairs) - positives
    if positives <= 0 or negatives <= 0:
        return None
    ordered = sorted(label_score_pairs, key=lambda pair: pair[1])
    hit_count = 0
    precision_sum = 0.0
    for idx, (label, _score) in enumerate(ordered, start=1):
        if not label:
            continue
        hit_count += 1
        precision_sum += hit_count / idx
    return float(precision_sum / positives)


def _failure_rate(rows: list[DockingGoldRow], token: str) -> float:
    if not rows:
        return 0.0
    count = sum(1 for row in rows if any(token in reason for reason in row.chemistry_failures))
    return count / len(rows)


def evaluate_docking_gold_slice(
    rows: list[DockingGoldRow],
    *,
    pose_success_rmsd_a: float = 2.0,
    top_k: int = 5,
    require_baseline: bool = True,
) -> DockingGoldMetrics:
    blockers: list[str] = []
    threshold = float(pose_success_rmsd_a)
    k = int(max(1, top_k))
    by_complex: dict[str, list[DockingGoldRow]] = {}
    for row in rows:
        by_complex.setdefault(str(row.complex_id), []).append(row)
    if not rows:
        blockers.append("no_rows")
    if not by_complex:
        blockers.append("no_complexes")
    rmsd_present = any(_finite_float(row.pose_rmsd_a) is not None for row in rows)
    if rows and not rmsd_present:
        blockers.extend(["native_or_reference_pose_missing", "pose_rmsd_not_computable"])

    top1_successes = 0
    topk_successes = 0
    top1_rmsd_missing_complexes = 0
    topk_rmsd_missing_complexes = 0
    top1_rmsd_values: list[float] = []
    topk_best_rmsd_values: list[float] = []
    labeled_complexes = 0
    topk_hits = 0
    decoy_rejected = 0
    decoy_total = 0
    for complex_rows in by_complex.values():
        ordered = sorted(complex_rows, key=lambda row: (int(row.pose_rank or 10**9), _finite_float(row.score) or float("inf")))
        top1_rmsd = _finite_float(ordered[0].pose_rmsd_a) if ordered else None
        if top1_rmsd is not None:
            top1_rmsd_values.append(top1_rmsd)
            if top1_rmsd <= threshold:
                top1_successes += 1
        else:
            top1_rmsd_missing_complexes += 1
        topk_rmsd_values = [
            float(row.pose_rmsd_a)
            for row in ordered[:k]
            if _finite_float(row.pose_rmsd_a) is not None
        ]
        if topk_rmsd_values:
            topk_best_rmsd_values.append(min(topk_rmsd_values))
        else:
            topk_rmsd_missing_complexes += 1
        if any(value <= threshold for value in topk_rmsd_values):
            topk_successes += 1
        labeled_rows = [row for row in ordered if row.active_label is not None and _finite_float(row.score) is not None]
        if labeled_rows:
            labeled_complexes += 1
            score_ranked_labeled_rows = sorted(
                labeled_rows,
                key=lambda row: (_finite_float(row.score) or float("inf"), int(row.pose_rank or 10**9)),
            )
            if any(bool(row.active_label) for row in score_ranked_labeled_rows[:k]):
                topk_hits += 1
            active_scores = [float(row.score) for row in labeled_rows if row.active_label is True]
            if active_scores:
                best_active = min(active_scores)
                for row in labeled_rows:
                    if row.active_label is False:
                        decoy_total += 1
                        if float(row.score) > best_active:
                            decoy_rejected += 1

    label_score_pairs = [
        (bool(row.active_label), float(row.score))
        for row in rows
        if row.active_label is not None and _finite_float(row.score) is not None
    ]
    if not label_score_pairs:
        blockers.append("ranking_labels_missing")
    affinity_score_pairs = [
        (float(row.affinity_label), float(row.score))
        for row in rows
        if _finite_float(row.affinity_label) is not None and _finite_float(row.score) is not None
    ]
    score_for_spearman = [-score for _affinity, score in affinity_score_pairs]
    labels_for_spearman = [affinity for affinity, _score in affinity_score_pairs]
    ranking_spearman = _spearman(labels_for_spearman, score_for_spearman)
    if not affinity_score_pairs:
        blockers.append("affinity_labels_missing")
    if ranking_spearman is None:
        blockers.append("ranking_spearman_not_computable")
    pr_auc = _average_precision(label_score_pairs)
    if pr_auc is None:
        blockers.append("pr_auc_not_computable")
    if labeled_complexes <= 0:
        blockers.append("topk_hit_rate_not_computable")
    if decoy_total <= 0:
        blockers.append("decoy_rejection_not_computable")

    heldout_rows = [
        row
        for row in rows
        if str(row.split_id or "heldout") == "heldout"
        and _finite_float(row.affinity_label) is not None
    ]
    heldout_complex_count = len({str(row.complex_id) for row in heldout_rows})
    heldout_scored_rows = [
        row
        for row in heldout_rows
        if _finite_float(row.score) is not None
    ]
    heldout_baseline_rows = [
        row
        for row in heldout_rows
        if _finite_float(row.baseline_score) is not None
    ]
    heldout_paired_rows = [
        row
        for row in heldout_rows
        if _finite_float(row.score) is not None and _finite_float(row.baseline_score) is not None
    ]
    heldout_refine_rows = heldout_paired_rows if require_baseline else heldout_scored_rows
    heldout_refine_pairs = [
        (float(row.affinity_label), float(row.score))
        for row in heldout_refine_rows
    ]
    heldout_refine_score_for_spearman = [-score for _label, score in heldout_refine_pairs]
    heldout_refine_labels_for_spearman = [affinity for affinity, _score in heldout_refine_pairs]
    heldout_refine_ranking_spearman = _spearman(
        heldout_refine_labels_for_spearman,
        heldout_refine_score_for_spearman,
    )
    baseline_pairs = [
        (float(row.affinity_label), float(row.baseline_score))
        for row in heldout_paired_rows
    ]
    baseline_score_for_spearman = [-score for _label, score in baseline_pairs]
    baseline_labels_for_spearman = [affinity for affinity, _score in baseline_pairs]
    baseline_ranking_spearman = _spearman(baseline_labels_for_spearman, baseline_score_for_spearman)
    refine_ranking_spearman_delta = (
        float(heldout_refine_ranking_spearman - baseline_ranking_spearman)
        if heldout_refine_ranking_spearman is not None and baseline_ranking_spearman is not None
        else None
    )
    refine_improvement_observed = bool(
        refine_ranking_spearman_delta is not None and refine_ranking_spearman_delta > 0.0
    )
    if not heldout_rows:
        blockers.append("heldout_labels_missing")
    else:
        if len(heldout_scored_rows) != len(heldout_rows):
            blockers.append("heldout_refined_score_incomplete")
        if require_baseline and len(heldout_baseline_rows) != len(heldout_rows):
            blockers.append("heldout_baseline_score_incomplete")
    if require_baseline and baseline_ranking_spearman is None:
        blockers.append("baseline_ranking_spearman_not_computable")
    if heldout_refine_ranking_spearman is None:
        blockers.append("heldout_refine_ranking_spearman_not_computable")
    if require_baseline and refine_ranking_spearman_delta is None:
        blockers.append("refine_ranking_spearman_delta_not_computable")
    elif require_baseline and not refine_improvement_observed:
        blockers.append("heldout_refine_ranking_spearman_not_improved")
    rmsd_coverage_complete = bool(
        by_complex and top1_rmsd_missing_complexes == 0 and topk_rmsd_missing_complexes == 0
    )
    if by_complex and not rmsd_coverage_complete:
        blockers.extend(["native_or_reference_pose_missing", "reference_pose_coverage_incomplete"])

    abstained = [row for row in rows if row.abstained]
    abstention_evidence_rows = [
        row
        for row in abstained
        if row.active_label is not None or _finite_float(row.pose_rmsd_a) is not None or row.chemistry_failures
    ]
    failed_abstentions = [
        row
        for row in abstention_evidence_rows
        if row.chemistry_failures
        or (_finite_float(row.pose_rmsd_a) is not None and float(row.pose_rmsd_a) > threshold)
        or row.active_label is False
    ]
    if abstained and len(abstention_evidence_rows) != len(abstained):
        blockers.append("abstention_precision_evidence_incomplete")
    if not abstained:
        blockers.append("abstention_precision_not_computable")
    chemistry_evidence_rows = [row for row in rows if row.chemistry_evidence_present]
    chemistry_evidence_coverage = len(chemistry_evidence_rows) / len(rows) if rows else 0.0
    if len(chemistry_evidence_rows) != len(rows):
        blockers.append("chemistry_failure_evidence_incomplete")
    runtime_values = [float(row.runtime_ms) for row in rows if _finite_float(row.runtime_ms) is not None]
    memory_values = [float(row.peak_memory_mb) for row in rows if _finite_float(row.peak_memory_mb) is not None]
    if len(runtime_values) != len(rows):
        blockers.append("runtime_metric_incomplete")
    if len(memory_values) != len(rows):
        blockers.append("peak_memory_metric_incomplete")
    status = "pass" if not blockers else "blocked"
    return DockingGoldMetrics(
        schema_version="tier_beta_docking_gold_metrics_v1",
        status=status,
        complex_count=len(by_complex),
        row_count=len(rows),
        pose_success_rmsd_threshold_a=threshold,
        reference_pose_present=rmsd_coverage_complete,
        native_pose_present=rmsd_coverage_complete,
        top1_mean_rmsd_a=(sum(top1_rmsd_values) / len(top1_rmsd_values) if top1_rmsd_values else None),
        top5_best_mean_rmsd_a=(
            sum(topk_best_rmsd_values) / len(topk_best_rmsd_values) if topk_best_rmsd_values else None
        ),
        top1_pose_success_rate=(top1_successes / len(by_complex) if by_complex else 0.0),
        top5_pose_success_rate=(topk_successes / len(by_complex) if by_complex else 0.0),
        ranking_spearman=ranking_spearman,
        pr_auc=pr_auc,
        topk_hit_rate=(topk_hits / labeled_complexes if labeled_complexes else None),
        decoy_rejection_rate=(decoy_rejected / decoy_total if decoy_total else None),
        baseline_ranking_spearman=baseline_ranking_spearman,
        refine_ranking_spearman_delta=refine_ranking_spearman_delta,
        refine_improvement_observed=refine_improvement_observed,
        heldout_complex_count=heldout_complex_count,
        chirality_failure_rate=_failure_rate(rows, "chirality"),
        tautomer_failure_rate=_failure_rate(rows, "tautomer"),
        protonation_failure_rate=_failure_rate(rows, "protonation"),
        chemistry_evidence_coverage=chemistry_evidence_coverage,
        abstention_precision=(len(failed_abstentions) / len(abstention_evidence_rows) if abstention_evidence_rows else None),
        mean_runtime_ms=(sum(runtime_values) / len(runtime_values) if runtime_values else None),
        peak_memory_mb=(max(memory_values) if memory_values else None),
        blockers=tuple(sorted(set(blockers))),
    )
