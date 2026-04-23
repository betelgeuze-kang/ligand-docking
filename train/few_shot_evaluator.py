# train/few_shot_evaluator.py

import torch
import numpy as np
from train.trainer import AIRouterTrainer # Re-use basic training logic for fine-tuning
from train.evaluator import evaluate_model

def evaluate_few_shot_performance(meta_trained_model, meta_test_tasks, fine_tune_epochs=5, eval_metrics=['rmse', 'mae']):
    """
    Evaluates the meta-trained model on few-shot tasks.
    Args:
        meta_trained_model (nn.Module): The model after meta-training.
        meta_test_tasks (list): List of (support_loader, query_loader) tuples for test targets.
        fine_tune_epochs (int): Number of epochs to fine-tune on support set before evaluating on query set.
        eval_metrics (list): List of metrics to compute.
    Returns:
        results (list): List of dictionaries containing results for each task.
    """
    results = []
    device = next(meta_trained_model.parameters()).device

    for task_idx, (support_loader, query_loader) in enumerate(meta_test_tasks):
        print(f"Evaluating task {task_idx+1}/{len(meta_test_tasks)}")

        # 1. Create a copy of the meta-trained model for this task
        task_model = meta_trained_model.clone() # Assuming a clone method exists, otherwise use deepcopy
        # task_model = deepcopy(meta_trained_model)

        # 2. Fine-tune on support set
        optimizer = torch.optim.Adam(task_model.parameters(), lr=1e-4) # Lower LR for fine-tuning
        loss_fn = torch.nn.MSELoss() # Use appropriate loss
        trainer = AIRouterTrainer(task_model, support_loader, support_loader, optimizer, loss_fn, epochs=fine_tune_epochs, device=device) # Use support as val for quick check
        trainer.train() # Fine-tune

        # 3. Evaluate on query set
        task_results = evaluate_model(task_model, query_loader, device, metrics=eval_metrics)
        task_results['task_id'] = task_idx
        results.append(task_results)
        print(f"  Task {task_idx} Results: {task_results}")

    return results

# Example usage:
# meta_model = load_meta_trained_model() # Load the model saved after meta-training
# test_tasks = generate_meta_tasks('data/', test_targets, ...) # Generate test tasks
# fs_results = evaluate_few_shot_performance(meta_model, test_tasks, fine_tune_epochs=5)
# avg_rmse = np.mean([r['rmse'] for r in fs_results])
# print(f"Average RMSE across {len(fs_results)} tasks: {avg_rmse:.4f}")
