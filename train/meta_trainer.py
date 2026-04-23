# train/meta_trainer.py

from contextlib import nullcontext
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from core.config import config, logger
from train.dataset import AIRouterHDF5Dataset
from theory.strategy import StrategicOrchestrator
from train.trainer import AIRouterTrainer # Re-use basic training logic for inner loop
import numpy as np
from copy import deepcopy

class MetaAIRouterTrainer:
    """
    Implements Reptile meta-learning algorithm for the AIRouter model.
    """
    def __init__(self, model, meta_optimizer, inner_optimizer_lr, inner_epochs, device):
        self.model = model
        self.meta_optimizer = meta_optimizer
        self.inner_optimizer_lr = inner_optimizer_lr
        self.inner_epochs = inner_epochs
        self.device = device
        self.max_grad_norm = float(config.get("training.max_grad_norm", 1.0))
        amp_enabled_cfg = bool(config.get("training.use_amp", True))
        self.use_amp = bool(amp_enabled_cfg and getattr(self.device, "type", "cpu") == "cuda")
        amp_dtype_raw = str(config.get("training.amp_dtype", "bf16")).strip().lower()
        self.amp_dtype = torch.bfloat16 if amp_dtype_raw in ("bf16", "bfloat16") else torch.float16
        scaler_enabled = bool(self.use_amp and self.amp_dtype == torch.float16)
        if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
            self.inner_scaler = torch.amp.GradScaler("cuda", enabled=scaler_enabled)
        else:
            self.inner_scaler = torch.cuda.amp.GradScaler(enabled=scaler_enabled)
        self.non_blocking = bool(config.get("training.non_blocking_transfer", True))

    def inner_loop_train(self, model, train_loader, loss_fn, optimizer):
        """
        Perform inner loop training on a single task.
        """
        model.train()
        for epoch in range(self.inner_epochs):
            for batch_idx, (coords_batch, target_forces_batch, residue_types_batch) in enumerate(train_loader):
                coords_batch = coords_batch.to(self.device, non_blocking=self.non_blocking)
                target_forces_batch = target_forces_batch.to(self.device, non_blocking=self.non_blocking)
                B, N, _ = coords_batch.shape

                # Prepare dummy inputs
                top_dummy = type('MockTop', (), {'residue_types': residue_types_batch.to(self.device)})()
                nb_data_dummy = (torch.randint(0, N, (B, N, 10), device=self.device), torch.randn(B, N, 10, device=self.device), torch.ones(B, N, 10, device=self.device))
                pe_batch_dummy = torch.randn(B, 1, device=self.device)
                sim_params_batch_dummy = {'temp': 300.0, 'salt_conc': 0.1, 'pH': 7.0, 'ionic_strength': 0.15}

                optimizer.zero_grad(set_to_none=True)
                autocast_ctx = (
                    torch.autocast(
                        device_type=self.device.type,
                        dtype=self.amp_dtype,
                        enabled=True,
                    )
                    if self.use_amp
                    else nullcontext()
                )
                with autocast_ctx:
                    f_pred, _aux_out = model(
                        coords_batch,
                        top_dummy,
                        nb_data_dummy,
                        pe_batch_dummy,
                        sim_params_batch_dummy,
                        ai_influence=1.0,
                    )
                    loss, _loss_components = loss_fn(f_pred, target_forces_batch, coords_batch)

                if self.inner_scaler.is_enabled():
                    self.inner_scaler.scale(loss).backward()
                    self.inner_scaler.unscale_(optimizer)
                    if self.max_grad_norm > 0:
                        torch.nn.utils.clip_grad_norm_(model.parameters(), self.max_grad_norm)
                    self.inner_scaler.step(optimizer)
                    self.inner_scaler.update()
                else:
                    loss.backward()
                    if self.max_grad_norm > 0:
                        torch.nn.utils.clip_grad_norm_(model.parameters(), self.max_grad_norm)
                    optimizer.step()

    def meta_update(self, meta_model, task_specific_models_params):
        """
        Reptile meta-update rule: theta <- theta + lr * (theta_task - theta)
        """
        meta_state_dict = meta_model.state_dict()
        for name, param in meta_state_dict.items():
            # Calculate average difference across tasks
            diff = torch.zeros_like(param)
            for task_params in task_specific_models_params:
                diff += (task_params[name] - param)
            diff /= len(task_specific_models_params)
            # Update meta model
            param.data += self.meta_optimizer.param_groups[0]['lr'] * diff

    def train_meta(self, meta_train_tasks, epochs, loss_fn):
        """
        Args:
            meta_train_tasks (list): List of (train_loader, val_loader) tuples for different tasks/targets.
            epochs (int): Number of meta-training epochs.
        """
        logger.info(f"Starting Meta-Training for {epochs} epochs")
        for epoch in range(epochs):
            epoch_loss = 0.0
            num_tasks_processed = 0

            for task_idx, (train_loader_task, val_loader_task) in enumerate(meta_train_tasks):
                # 1. Create a copy of the meta-model for this task
                task_model = deepcopy(self.model)
                task_model_optimizer = optim.Adam(task_model.parameters(), lr=self.inner_optimizer_lr)

                # 2. Inner loop training on the specific task
                self.inner_loop_train(task_model, train_loader_task, loss_fn, task_model_optimizer)

                # 3. Collect updated parameters for meta-update
                task_specific_params = task_model.state_dict()

                # 4. Perform meta-update (Reptile step)
                self.meta_update(self.model, [task_specific_params])

                num_tasks_processed += 1

            logger.info(f"Meta-Epoch {epoch+1}/{epochs} completed. Processed {num_tasks_processed} tasks.")

        logger.info("Meta-Training completed.")
