# train/trainer.py (Auto-Tuning 전략 2 적용 예시)

# ... (기존 imports 유지) ...
from core.config import config, logger
from core.tracking import ExperimentTracker # MLflow tracking
# ... 기타 필요한 imports ...

# [MODIFIED] AIRouterTrainer 클래스: Curriculum Learning (Warm-up) 적용
class AIRouterTrainer:
    def __init__(self, model, train_loader, val_loader, optimizer, loss_fn, epochs, device, tracker=None):
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

        # [EXISTING] Checkpointing and other initializations ...

    def train_epoch(self):
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        for batch_idx, (coords_batch, target_forces_batch, residue_types_batch) in enumerate(self.train_loader):
            coords_batch, target_forces_batch = coords_batch.to(self.device), target_forces_batch.to(self.device)

            self.optimizer.zero_grad()

            # [NEW] Calculate AI Influence based on Curriculum Learning (Warm-up)
            # This assumes the model's forward method accepts 'ai_influence' as an argument
            if self.global_step < self.warmup_steps:
                 # Cosine annealing schedule for smooth transition
                 ai_influence = 0.5 * (1.0 - torch.cos(torch.pi * self.global_step / self.warmup_steps))
                 # This goes from 0.0 (no AI) up to 1.0 (full AI influence) at step warmup_steps
            else:
                 ai_influence = 1.0 # After warmup, full AI influence (modulated by balance_weight)

            # Prepare dummy inputs for aux_outputs, sim_params (as per model requirement)
            B, N, _ = coords_batch.shape
            top_dummy = type('MockTop', (), {'residue_types': residue_types_batch.to(self.device)})()
            nb_data_dummy = (torch.randint(0, N, (B, N, 10), device=self.device), torch.randn(B, N, 10, device=self.device), torch.ones(B, N, 10, device=self.device))
            pe_batch_dummy = torch.randn(B, 1, device=self.device)
            sim_params_batch_dummy = {'temp': 300.0, 'salt_conc': 0.1, 'pH': 7.0, 'ionic_strength': 0.15}

            # Forward pass (with ai_influence)
            f_pred, aux_out = self.model(coords_batch, top_dummy, nb_data_dummy, pe_batch_dummy, sim_params_batch_dummy, ai_influence=ai_influence) # Pass ai_influence
            # f_pred should be the final force prediction from the orchestrator

            # Calculate loss (using target_forces)
            loss, loss_components = self.loss_fn(f_pred, target_forces_batch, coords_batch)

            loss.backward()
            self.optimizer.step()

            total_loss += loss_components['total']
            num_batches += 1

            self.global_step += 1 # Increment global step counter

        avg_loss = total_loss / num_batches if num_batches > 0 else float('inf')
        return avg_loss

    # [EXISTING] validate_epoch, train, etc. 메서드 유지 ...

    def train(self):
        console.print(f"[bold yellow]Starting training for {self.epochs} epochs[/bold yellow]")
        for epoch in range(self.epochs):
            train_loss = self.train_epoch()
            val_loss = self.validate_epoch()

            console.print(f"Epoch {epoch+1}/{self.epochs}, Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")

            # Log metrics to MLflow
            if self.tracker:
                self.tracker.log_metrics({'train_loss': train_loss, 'val_loss': val_loss}, step=epoch)

            # [EXISTING] Checkpointing and Early Stopping logic ...

        console.print(f"[bold green]Training completed. Best validation loss: {self.best_val_loss:.4f}[/bold green]")

