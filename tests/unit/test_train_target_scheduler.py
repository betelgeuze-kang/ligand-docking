import collections

from core.definitions import ResearchConstants
from train.target_scheduler import FoldBalancedTargetScheduler, resolve_targets


def test_scheduler_covers_all_targets():
    scheduler = FoldBalancedTargetScheduler()
    all_targets = scheduler.get_all_targets()
    assert set(all_targets) == set(ResearchConstants.CHALLENGES.keys())
    assert len(all_targets) == 10


def test_unique_fold_balanced_order_contains_all_targets_once():
    scheduler = FoldBalancedTargetScheduler()
    ordered = scheduler.build_unique_fold_balanced_targets(seed=123, shuffle=True)
    assert len(ordered) == len(set(ordered))
    assert set(ordered) == set(scheduler.get_all_targets())


def test_round_robin_sequence_is_fold_balanced():
    scheduler = FoldBalancedTargetScheduler()
    seq = scheduler.build_target_sequence(num_steps=70, seed=7, shuffle=False)
    fold_counts = collections.Counter(ResearchConstants.CHALLENGES[t]["fold_class"] for t in seq)
    values = list(fold_counts.values())
    assert max(values) - min(values) <= 1


def test_allocate_samples_respects_sum_and_minimum():
    scheduler = FoldBalancedTargetScheduler()
    plan = scheduler.allocate_samples(total_samples=1000, min_per_target=5)
    assert sum(plan.values()) == 1000
    assert all(v >= 5 for v in plan.values())


def test_resolve_targets_fold_balanced_returns_requested_count():
    targets = resolve_targets(target="all", schedule="fold_balanced", max_targets=6, seed=42)
    assert len(targets) == 6
    for target in targets:
        assert target in ResearchConstants.CHALLENGES


def test_resolve_targets_size_ascending_orders_by_n_res():
    targets = resolve_targets(target="all", schedule="size_ascending", max_targets=None, seed=42)
    n_res = [int(ResearchConstants.CHALLENGES[t]["n_res"]) for t in targets]
    assert n_res == sorted(n_res)


def test_resolve_targets_size_descending_orders_by_n_res():
    targets = resolve_targets(target="all", schedule="size_descending", max_targets=None, seed=42)
    n_res = [int(ResearchConstants.CHALLENGES[t]["n_res"]) for t in targets]
    assert n_res == sorted(n_res, reverse=True)
