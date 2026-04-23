import random
from collections import deque

from core.definitions import ResearchConstants


class FoldBalancedTargetScheduler:
    """
    Fold-class 균형을 유지하는 소형 단백질 타깃 스케줄러.
    """

    def __init__(self, challenges=None):
        self.challenges = challenges or ResearchConstants.CHALLENGES
        self._fold_to_targets = {}
        for target, cfg in self.challenges.items():
            fold = cfg.get("fold_class")
            if not fold:
                raise ValueError(f"fold_class is required for target: {target}")
            self._fold_to_targets.setdefault(fold, []).append(target)

        self.fold_names = sorted(self._fold_to_targets.keys())
        for fold in self.fold_names:
            self._fold_to_targets[fold] = sorted(self._fold_to_targets[fold])

    def get_all_targets(self):
        return sorted(self.challenges.keys())

    def get_targets_by_fold(self):
        return {fold: list(targets) for fold, targets in self._fold_to_targets.items()}

    def build_unique_fold_balanced_targets(self, seed=42, shuffle=True):
        """
        모든 타깃을 정확히 한 번씩 포함하면서 fold별로 interleave한 순서 반환.
        """
        rng = random.Random(seed)
        fold_order = list(self.fold_names)
        if shuffle:
            rng.shuffle(fold_order)

        fold_queues = {}
        for fold in fold_order:
            targets = list(self._fold_to_targets[fold])
            if shuffle:
                rng.shuffle(targets)
            fold_queues[fold] = deque(targets)

        ordered_targets = []
        has_remaining = True
        while has_remaining:
            has_remaining = False
            for fold in fold_order:
                if fold_queues[fold]:
                    ordered_targets.append(fold_queues[fold].popleft())
                    has_remaining = True
        return ordered_targets

    def build_target_sequence(self, num_steps, seed=42, shuffle=True):
        """
        길이 num_steps의 fold-balanced 순환 시퀀스 생성.
        """
        if num_steps <= 0:
            return []

        rng = random.Random(seed)
        fold_order = list(self.fold_names)
        if shuffle:
            rng.shuffle(fold_order)

        fold_targets = {}
        fold_cursor = {}
        for fold in fold_order:
            targets = list(self._fold_to_targets[fold])
            if shuffle:
                rng.shuffle(targets)
            fold_targets[fold] = targets
            fold_cursor[fold] = 0

        sequence = []
        while len(sequence) < num_steps:
            for fold in fold_order:
                if len(sequence) >= num_steps:
                    break
                targets = fold_targets[fold]
                idx = fold_cursor[fold] % len(targets)
                sequence.append(targets[idx])
                fold_cursor[fold] += 1
        return sequence

    def allocate_samples(self, total_samples, min_per_target=1):
        """
        총 샘플 수를 fold-class 균형 기준으로 타깃별 분배.
        """
        all_targets = self.get_all_targets()
        num_targets = len(all_targets)
        min_required = min_per_target * num_targets
        if total_samples < min_required:
            raise ValueError(
                f"total_samples={total_samples} is smaller than required minimum={min_required}"
            )

        plan = {target: min_per_target for target in all_targets}
        remaining = total_samples - min_required
        if remaining == 0:
            return plan

        num_folds = len(self.fold_names)
        fold_budget = {fold: remaining // num_folds for fold in self.fold_names}
        rem = remaining % num_folds
        for i, fold in enumerate(self.fold_names):
            if i < rem:
                fold_budget[fold] += 1

        for fold in self.fold_names:
            targets = self._fold_to_targets[fold]
            base = fold_budget[fold] // len(targets)
            fold_rem = fold_budget[fold] % len(targets)
            for i, target in enumerate(targets):
                plan[target] += base + (1 if i < fold_rem else 0)
        return plan


def resolve_targets(target="all", schedule="fold_balanced", max_targets=None, seed=42, challenges=None):
    """
    학습/데이터 생성에서 사용할 타깃 순서 해석 함수.
    """
    scheduler = FoldBalancedTargetScheduler(challenges=challenges)

    if target is not None and str(target).lower() != "all":
        return [target]

    if schedule == "fold_balanced":
        targets = scheduler.build_unique_fold_balanced_targets(seed=seed, shuffle=True)
    elif schedule == "round_robin":
        steps = max_targets or len(scheduler.get_all_targets())
        targets = scheduler.build_target_sequence(num_steps=steps, seed=seed, shuffle=True)
    elif schedule == "alphabetical":
        targets = sorted(scheduler.get_all_targets())
    elif schedule == "size_ascending":
        targets = sorted(
            scheduler.get_all_targets(),
            key=lambda t: int(scheduler.challenges[t].get("n_res", 0)),
        )
    elif schedule == "size_descending":
        targets = sorted(
            scheduler.get_all_targets(),
            key=lambda t: int(scheduler.challenges[t].get("n_res", 0)),
            reverse=True,
        )
    elif schedule == "defined":
        targets = list(scheduler.challenges.keys())
    else:
        raise ValueError(f"Unsupported schedule: {schedule}")

    if max_targets is not None:
        targets = targets[:max_targets]
    return targets
