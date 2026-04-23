# tools/generate_meta_tasks.py

import os
import numpy as np
from train.dataset import AIRouterHDF5Dataset
from train.target_scheduler import resolve_targets
from torch.utils.data import Subset, DataLoader

def generate_meta_tasks(
    base_data_path,
    targets_list=None,
    num_support_shots=5,
    num_query_shots=15,
    batch_size=32,
    schedule='fold_balanced',
    max_tasks=None,
    seed=42,
):
    """
    Generates support and query datasets for meta-learning evaluation.
    Args:
        base_data_path (str): Base path where target-specific HDF5 files are stored (e.g., 'data/')
        targets_list (list|None): 타깃 이름 리스트. None이면 schedule 기반 자동 선택.
        num_support_shots (int): Number of samples per class for support set.
        num_query_shots (int): Number of samples per class for query set.
        batch_size (int): Batch size for data loaders.
        schedule (str): 자동 선택 스케줄 ('fold_balanced', 'round_robin', 'alphabetical', 'defined')
        max_tasks (int|None): 생성할 최대 task 수
        seed (int): 랜덤 시드
    Returns:
        meta_tasks (list): List of (support_loader, query_loader) tuples.
    """
    if targets_list is None:
        selected_targets = resolve_targets(
            target='all',
            schedule=schedule,
            max_targets=max_tasks,
            seed=seed,
        )
    else:
        selected_targets = list(targets_list)
        if max_tasks is not None:
            selected_targets = selected_targets[:max_tasks]

    meta_tasks = []
    rng = np.random.default_rng(seed)
    for target in selected_targets:
        data_file_path = os.path.join(base_data_path, f"{target.lower()}_airouter_train_data.h5")
        if not os.path.exists(data_file_path):
            print(f"Warning: Data file for {target} not found at {data_file_path}. Skipping.")
            continue

        dataset = AIRouterHDF5Dataset(data_file_path)
        total_samples = len(dataset)

        if total_samples < (num_support_shots + num_query_shots):
            print(f"Warning: Not enough samples for {target} (need {num_support_shots + num_query_shots}, got {total_samples}). Skipping.")
            continue

        # Randomly sample indices for support and query
        all_indices = np.arange(total_samples)
        rng.shuffle(all_indices)
        support_indices = all_indices[:num_support_shots]
        query_indices = all_indices[num_support_shots:num_support_shots + num_query_shots]

        # Create subsets
        support_dataset = Subset(dataset, support_indices)
        query_dataset = Subset(dataset, query_indices)

        # Create data loaders
        support_loader = DataLoader(support_dataset, batch_size=batch_size, shuffle=True)
        query_loader = DataLoader(query_dataset, batch_size=batch_size, shuffle=False)

        meta_tasks.append((support_loader, query_loader))
        print(f"Generated meta-task for {target}: Support={num_support_shots}, Query={num_query_shots}")

    return meta_tasks

# Example usage:
# meta_tasks = generate_meta_tasks('data/', targets_list=None, schedule='fold_balanced', max_tasks=10)
