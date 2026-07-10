# train/trainer.py

import math
import os
import time
from contextlib import nullcontext
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from core.config import config, logger
from core.tracking import ExperimentTracker # MLflow tracking
from train.checkpoint_contracts import canonical_model_state_dict
from train.runtime_inputs import build_runtime_inputs, runtime_input_schema_metadata
# ... 기타 필요한 imports ...

console = Console()


def _unpack_batch(batch):
    if not isinstance(batch, (tuple, list)):
        raise TypeError(f"Unsupported batch type: {type(batch)}")
    if len(batch) == 3:
        coords_batch, target_forces_batch, residue_types_batch = batch
        quality_batch = None
        sim_params_batch = None
        return coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch
    if len(batch) == 4:
        coords_batch, target_forces_batch, residue_types_batch, quality_batch = batch
        sim_params_batch = None
        return coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch
    if len(batch) == 5:
        coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch = batch
        return coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch
    raise ValueError(f"Unsupported batch size: {len(batch)}")


# [MODIFIED] AIRouterTrainer 클래스: Curriculum Learning (Warm-up) 적용
class AIRouterTrainer:
    def __init__(
        self,
        model,
        train_loader,
        val_loader,
        optimizer,
        loss_fn,
        epochs,
        device,
        tracker=None,
        checkpoint_path=None,
        early_stop_patience=10,
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.epochs = epochs
        self.device = device
        self.tracker = tracker # MLflow tracker instance

        # [NEW] Curriculum Learning (Warm-up) parameters
        self.warmup_steps = 1000 # 예: 처음 1000 스텝 동안은 AI 영향력 증가
        self.total_training_steps = epochs * len(train_loader) # 총 훈련 스텝 수 (approximate)
        self.global_step = 0 # Global step counter

        # Checkpointing
        self.best_val_loss = float('inf')
        self.early_stop_counter = 0
        self.early_stop_patience = int(early_stop_patience)
        os.makedirs("models", exist_ok=True)
        self.checkpoint_path = str(
            checkpoint_path or f"models/best_airouter_model_{self.model.__class__.__name__}.pth"
        )
        self.train_neighbor_k = int(max(config.get("training.neighbor_k", 10), 1))
        self.train_neighbor_cutoff = float(config.get("training.neighbor_cutoff_angstrom", 12.0))
        self.train_max_neighbor_candidates = int(config.get("training.max_neighbor_candidates", 64))
        self.train_max_atoms_per_cell = int(config.get("training.max_atoms_per_cell", 64))
        self.runtime_input_schema = runtime_input_schema_metadata(
            neighbor_k=self.train_neighbor_k,
            cutoff_angstrom=self.train_neighbor_cutoff,
            max_neighbor_candidates=self.train_max_neighbor_candidates,
            max_atoms_per_cell=self.train_max_atoms_per_cell,
        )
        self.max_grad_norm = float(config.get("training.max_grad_norm", 1.0))
        amp_enabled_cfg = bool(config.get("training.use_amp", True))
        self.use_amp = bool(amp_enabled_cfg and getattr(self.device, "type", "cpu") == "cuda")
        amp_dtype_raw = str(config.get("training.amp_dtype", "bf16")).strip().lower()
        self.amp_dtype = torch.bfloat16 if amp_dtype_raw in ("bf16", "bfloat16") else torch.float16
        scaler_enabled = bool(self.use_amp and self.amp_dtype == torch.float16)
        if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
            self.grad_scaler = torch.amp.GradScaler("cuda", enabled=scaler_enabled)
        else:
            self.grad_scaler = torch.cuda.amp.GradScaler(enabled=scaler_enabled)
        self.non_blocking = bool(config.get("training.non_blocking_transfer", True))

        # Compile model if specified in config
        if config.get('torch_compile.enabled', False):
            compile_kwargs = {k: v for k, v in config.get('torch_compile', {}).items() if k != 'enabled'}
            try:
                import torch._dynamo as _dynamo  # type: ignore
                _dynamo.config.suppress_errors = True
                try:
                    _dynamo.config.capture_scalar_outputs = True
                except Exception:
                    pass
            except Exception:
                pass
            try:
                self.model = torch.compile(self.model, **compile_kwargs)
                console.print("[blue]Model compiled with torch.compile[/blue]")
            except Exception as exc:
                console.print(f"[yellow]torch.compile init failed; fallback eager: {exc}[/yellow]")
        if self.use_amp:
            console.print(f"[blue]AMP enabled (dtype={self.amp_dtype})[/blue]")

    def train_epoch(self):
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        sample_count = 0
        t_start = time.perf_counter()
        for batch_idx, batch in enumerate(self.train_loader):
            (
                coords_batch,
                target_forces_batch,
                residue_types_batch,
                _quality_batch,
                sim_params_batch,
            ) = _unpack_batch(batch)
            coords_batch = coords_batch.to(self.device, non_blocking=self.non_blocking)
            target_forces_batch = target_forces_batch.to(self.device, non_blocking=self.non_blocking)

            self.optimizer.zero_grad(set_to_none=True)

            # [NEW] Calculate AI Influence based on Curriculum Learning (Warm-up)
            # This assumes the model's forward method accepts 'ai_influence' as an argument
            if self.global_step < self.warmup_steps:
                 # Cosine annealing schedule for smooth transition
                 ai_influence = 0.5 * (1.0 - math.cos(math.pi * self.global_step / self.warmup_steps))
                 # This goes from 0.0 (no AI) up to 1.0 (full AI influence) at step warmup_steps
            else:
                 ai_influence = 1.0 # After warmup, full AI influence (modulated by balance_weight)

            top_dummy, nb_data_dummy, pe_batch_dummy, sim_params_batch_dummy = build_runtime_inputs(
                coords_batch=coords_batch,
                residue_types_batch=residue_types_batch,
                sim_params_batch=sim_params_batch,
                neighbor_k=self.train_neighbor_k,
                neighbor_cutoff_angstrom=self.train_neighbor_cutoff,
                max_neighbor_candidates=self.train_max_neighbor_candidates,
                max_atoms_per_cell=self.train_max_atoms_per_cell,
            )

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
                # Forward pass (with ai_influence)
                f_pred, _aux_out = self.model(
                    coords_batch,
                    top_dummy,
                    nb_data_dummy,
                    pe_batch_dummy,
                    sim_params_batch_dummy,
                    ai_influence=ai_influence,
                )
                # Calculate loss (using target_forces)
                loss, loss_components = self.loss_fn(f_pred, target_forces_batch, coords_batch)

            if self.grad_scaler.is_enabled():
                self.grad_scaler.scale(loss).backward()
                self.grad_scaler.unscale_(self.optimizer)
                if self.max_grad_norm > 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.max_grad_norm)
                self.grad_scaler.step(self.optimizer)
                self.grad_scaler.update()
            else:
                loss.backward()
                if self.max_grad_norm > 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.max_grad_norm)
                self.optimizer.step()

            batch_total = loss_components['total']
            if isinstance(batch_total, torch.Tensor):
                batch_total = batch_total.item()
            total_loss += float(batch_total)
            num_batches += 1
            sample_count += int(coords_batch.shape[0])

            self.global_step += 1 # Increment global step counter

        avg_loss = total_loss / num_batches if num_batches > 0 else float('inf')
        elapsed = max(time.perf_counter() - t_start, 1e-8)
        self.last_train_epoch_stats = {
            "elapsed_sec": float(elapsed),
            "samples_per_sec": float(sample_count / elapsed),
            "batches_per_sec": float(num_batches / elapsed),
            "samples": int(sample_count),
            "batches": int(num_batches),
        }
        return avg_loss

    def validate_epoch(self):
        self.model.eval()
        total_loss = 0.0
        num_batches = 0
        with torch.no_grad():
            for batch_idx, batch in enumerate(self.val_loader):
                (
                    coords_batch,
                    target_forces_batch,
                    residue_types_batch,
                    _quality_batch,
                    sim_params_batch,
                ) = _unpack_batch(batch)
                coords_batch = coords_batch.to(self.device, non_blocking=self.non_blocking)
                target_forces_batch = target_forces_batch.to(self.device, non_blocking=self.non_blocking)

                top_dummy, nb_data_dummy, pe_batch_dummy, sim_params_batch_dummy = build_runtime_inputs(
                    coords_batch=coords_batch,
                    residue_types_batch=residue_types_batch,
                    sim_params_batch=sim_params_batch,
                    neighbor_k=self.train_neighbor_k,
                    neighbor_cutoff_angstrom=self.train_neighbor_cutoff,
                    max_neighbor_candidates=self.train_max_neighbor_candidates,
                    max_atoms_per_cell=self.train_max_atoms_per_cell,
                )

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
                    # Forward pass (with ai_influence=1.0 for validation)
                    f_pred, _aux_out = self.model(
                        coords_batch,
                        top_dummy,
                        nb_data_dummy,
                        pe_batch_dummy,
                        sim_params_batch_dummy,
                        ai_influence=1.0,
                    )
                    loss, loss_components = self.loss_fn(f_pred, target_forces_batch, coords_batch)

                batch_total = loss_components['total']
                if isinstance(batch_total, torch.Tensor):
                    batch_total = batch_total.item()
                total_loss += float(batch_total)
                num_batches += 1

        avg_loss = total_loss / num_batches if num_batches > 0 else float('inf')
        return avg_loss

    def train(self):
        console.print(f"[bold yellow]Starting training for {self.epochs} epochs[/bold yellow]")
        epochs_ran = 0
        for epoch in range(self.epochs):
            train_loss = self.train_epoch()
            val_loss = self.validate_epoch()
            epochs_ran = epoch + 1

            train_stats = getattr(self, "last_train_epoch_stats", {})
            console.print(
                f"Epoch {epoch+1}/{self.epochs}, Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}, "
                f"Train Throughput: {float(train_stats.get('samples_per_sec', 0.0)):.1f} samples/s"
            )

            # Log metrics to MLflow
            if self.tracker:
                metrics = {'train_loss': train_loss, 'val_loss': val_loss}
                if train_stats:
                    metrics.update(
                        {
                            "train_samples_per_sec": float(train_stats.get("samples_per_sec", 0.0)),
                            "train_batches_per_sec": float(train_stats.get("batches_per_sec", 0.0)),
                        }
                    )
                self.tracker.log_metrics(metrics, step=epoch)

            # Checkpointing and Early Stopping
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.early_stop_counter = 0
                # Save best model
                torch.save(
                    {
                        "checkpoint_format": "airouter_runtime_checkpoint/2.1.0",
                        "state_dict_key_space": "canonical_unwrapped_model",
                        "state_dict": canonical_model_state_dict(self.model),
                        "runtime_input_schema": dict(self.runtime_input_schema),
                        "epoch": int(epoch + 1),
                        "best_validation_loss": float(val_loss),
                    },
                    self.checkpoint_path,
                )
                console.print(f"[green]✅ Best model saved at epoch {epoch+1}[/green]")
            else:
                self.early_stop_counter += 1
                if self.early_stop_counter >= self.early_stop_patience:
                    console.print(f"[yellow]Early stopping triggered at epoch {epoch+1}[/yellow]")
                    break

        console.print(f"[bold green]Training completed. Best validation loss: {self.best_val_loss:.4f}[/bold green]")
        return {
            "best_val_loss": float(self.best_val_loss),
            "best_checkpoint_path": str(self.checkpoint_path),
            "epochs_trained": int(epochs_ran),
        }
