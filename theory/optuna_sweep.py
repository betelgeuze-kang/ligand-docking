# train/optuna_sweep.py

try:
    import optuna
except ImportError:
    optuna = None
import torch
import numpy as np
from core.config import config
from theory.strategy import StrategicOrchestrator
from train.dataset import AIRouterHDF5Dataset
from torch.utils.data import DataLoader, Subset
from train.trainer import AIRouterTrainer # Assuming this trainer is compatible or adapted
from train.evaluator import evaluate_model
from run_validation import run_target # Assuming this returns a metric like RMSD
from core.definitions import ResearchConstants
import tempfile
import os
from rich.console import Console

console = Console()

def objective(trial):
    """
    Optuna Objective Function for hyperparameter optimization.
    """
    # --- 1. Suggest Hyperparameters ---
    # Example: Learning rate, batch size, specific module strengths
    lr = trial.suggest_float('lr', 1e-5, 1e-2, log=True)
    batch_size = trial.suggest_categorical('batch_size', [16, 32, 64])
    hydrophobic_strength = trial.suggest_float('hydrophobic_strength', 0.0, 1.0)
    # Add more parameters as needed (e.g., salt_bridge_strength, hbond_strength, etc.)
    # These parameters would typically be part of the Specialist modules or passed during initialization

    # --- 2. Setup Model and Data ---
    device = config.DEVICE
    model = StrategicOrchestrator(device).to(device)

    # Modify Specialist parameters based on trial suggestions
    # Example: Directly modify a parameter in a specific specialist
    # In practice, you might need to access parameters differently or pass them during initialization
    # For now, let's assume there's a way to set it after creation, perhaps via a method
    # model.core_specialists['hydrophobic'].set_strength(hydrophobic_strength)
    # Or, if it's an nn.Parameter, we can directly assign
    # param_name = 'some_param_name'
    # if hasattr(model.core_specialists['hydrophobic'], param_name):
    #     getattr(model.core_specialists['hydrophobic'], param_name).data.fill_(hydrophobic_strength)
    # Or, if parameters are passed during initialization of the model/orchestrator, this would require
    # creating the model inside the objective function with the trial parameters.
    # For this example, let's assume a method exists or parameters are accessible via a standard mechanism
    # Let's focus on parameters that are easier to modify post-init, like the balance_weight in the orchestrator
    # Or, let's suggest parameters for the trainer itself (e.g., warmup_steps)
    warmup_steps = trial.suggest_int('warmup_steps', 100, 2000)

    # Load data
    # Use a small subset or a specific target for the sweep
    target_for_sweep = 'Chignolin' # Example target
    data_path = f"data/{target_for_sweep.lower()}_airouter_train_data.h5" # Assuming HDF5 format
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file for sweep target {target_for_sweep} not found at {data_path}")
    dataset = AIRouterHDF5Dataset(data_path)
    # For speed, use a smaller subset
    subset_size = min(len(dataset), 1000) # Use first 1000 samples
    subset_indices = list(range(subset_size))
    from torch.utils.data import Subset
    subset_dataset = Subset(dataset, subset_indices)
    train_loader = DataLoader(subset_dataset, batch_size=batch_size, shuffle=True)

    # Validation data
    val_data_path = f"data/{target_for_sweep.lower()}_airouter_val_data.h5"
    if os.path.exists(val_data_path):
        val_dataset = AIRouterHDF5Dataset(val_data_path)
        val_subset_size = min(len(val_dataset), 200)
        val_subset_indices = list(range(val_subset_size))
        val_subset_dataset = Subset(val_dataset, val_subset_indices)
        val_loader = DataLoader(val_subset_dataset, batch_size=batch_size, shuffle=False)
    else:
        val_loader = None # Fallback if no validation data

    # --- 3. Setup Trainer (with modified parameters) ---
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    from train_router import CompositeRouterLoss # Assuming this is the loss
    loss_fn = CompositeRouterLoss(
        mse_weight=config.get('training.loss_weights.mse', 1.0),
        div_weight=config.get('training.loss_weights.div_penalty', 0.05),
        clamp_weight=config.get('training.loss_weights.clamp_penalty', 0.001)
    )
    tracker = None # Or create a tracker instance if needed for the sweep

    # Modify trainer's warmup_steps based on trial suggestion
    trainer = AIRouterTrainer(model, train_loader, val_loader, optimizer, loss_fn, epochs=5, device=device, tracker=tracker) # Short epochs for sweep
    trainer.warmup_steps = warmup_steps # Override warmup_steps

    # --- 4. Train for a few epochs ---
    trainer.train() # This trains with the current hyperparams

    # --- 5. Evaluate Model (on a short trajectory or validation set) ---
    # Option B: Evaluate on validation set using evaluate_model
    if val_loader:
        eval_metrics = evaluate_model(model, val_loader, device, metrics=['rmse', 'mae'])
        # Choose a metric to minimize (e.g., rmse)
        metric_to_minimize = eval_metrics.get('rmse', float('inf'))
    else:
        # Fallback: Use training loss or a dummy metric
        # This is less ideal but allows the sweep to run
        metric_to_minimize = float('inf') # Indicate failure or use a default high value if evaluation fails

    # --- 6. Report Metric to Optuna ---
    # Optuna minimizes by default, so return the metric directly
    console.print(f"Trial {trial.number}: lr={lr}, bs={batch_size}, warmup={warmup_steps} -> Metric: {metric_to_minimize}")
    return metric_to_minimize # e.g., RMSD, Validation Loss, etc.

def run_optimization(n_trials=50):
    """
    Run the Optuna optimization study.
    """
    if optuna is None:
        raise ImportError("optuna is required for optimization. Install optuna first.")
    study = optuna.create_study(direction='minimize') # Minimize the chosen metric (e.g., RMSD, Loss)
    study.optimize(objective, n_trials=n_trials)

    console.print("[bold green]Optimization completed.[/bold green]")
    console.print("Best trial:")
    trial = study.best_trial

    console.print(f"  Value: {trial.value}")
    console.print("  Params: ")
    for key, value in trial.params.items():
        console.print(f"    {key}: {value}")

    return study

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run Optuna hyperparameter sweep.')
    parser.add_argument('--n_trials', type=int, default=50, help='Number of Optuna trials to run')

    args = parser.parse_args()

    study = run_optimization(n_trials=args.n_trials)
    console.print(f"\n[bold]Best parameters saved in study.best_trial.[/bold]")
