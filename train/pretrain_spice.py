#!/usr/bin/env python3
"""
SPICE Dataset Pre-trainer — 공개 데이터셋을 사용한 사전 학습 스크립트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
과학적 목적: AIRouter가 기본적인 화학적 상호작용을 빠르게 핵심으로 익히도록 도움
핵심 최적화: SPICE 데이터셋의 정답 힘과 Rust 엔진 계산 힘의 차이 학습
성공 기준: 정답 힘과 예측 힘의 MSE < 0.1 kcal/mol/Å
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from core.definitions import Config
from theory.strategy import StrategicOrchestrator
from core.config import config as core_config, logger
from core.tracking import ExperimentTracker # MLflow tracking
import numpy as np
import h5py # SPICE 데이터셋은 일반적으로 HDF5 형식

console = Console()

class SPICEDataset(Dataset):
    """
    SPICE 데이터셋 로더.
    SPICE는 분자 구조와 정답 힘 정보를 포함하는 HDF5 파일로 제공됩니다.
    """
    def __init__(self, data_path, max_samples=None):
        """
        Args:
            data_path (str): SPICE 데이터셋 파일 경로
            max_samples (int, optional): 로드할 최대 샘플 수 (디버깅용)
        """
        self.data_path = data_path
        console.print(f"[bold blue]Loading SPICE data from...[/bold blue] {data_path}")
        # Load data using h5py
        with h5py.File(data_path, 'r') as f:
            self.coords = f['coordinates'][:] # [num_samples, num_atoms, 3]
            self.forces_gt = f['forces'][:]   # [num_samples, num_atoms, 3]
            self.energies_gt = f['energies'][:] # [num_samples, 1] (if available)
            # Other properties like atomic_numbers, smiles, etc. might be available

        self.length = len(self.coords)
        if max_samples:
            self.length = min(self.length, max_samples)
        console.print(f"[green]✅ Loaded {self.length} samples from SPICE[/green]")

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        # Return coordinates and ground truth forces
        c = torch.from_numpy(self.coords[idx]).float()
        f_gt = torch.from_numpy(self.forces_gt[idx]).float()
        return c, f_gt


def pretrain_air_router(target, spice_data_path, epochs=10, batch_size=64, lr=1e-4):
    """
    StrategicOrchestrator의 AIRouter를 SPICE 데이터셋으로 사전 학습합니다.
    """
    console.print(f"[bold yellow]AI Router SPICE Pre-training Started[/bold yellow] - Target: {target}")

    # 1. 데이터 로드
    dataset = SPICEDataset(spice_data_path, max_samples=5000) # Limit samples for initial run
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    # 2. 모델 설정 (AI Router만 학습)
    device = core_config.DEVICE
    orchestrator = StrategicOrchestrator(device).to(device)

    # Freeze core specialists, branch modules
    for param in orchestrator.core_specialists.parameters():
        param.requires_grad = False
    for param in orchestrator.branch_modules.parameters():
        param.requires_grad = False

    # Unfreeze AI Router parameters
    for param in orchestrator.ai_router.parameters():
        param.requires_grad = True

    # 3. 옵티마이저, 손실 함수 설정
    optimizer = optim.Adam(orchestrator.ai_router.parameters(), lr=lr)
    # Loss: Predicted Force Difference (ΔF = F_GT - F_Rust) vs Ground Truth Force Difference (Assuming F_Rust is computed elsewhere)
    # For now, let's assume the AI Router learns to predict the residual force (F_GT - F_Rust)
    # The trainer will compute F_Rust using the core physics engine
    # So, loss = || AI_output - (F_GT - F_Rust) ||
    # However, computing F_Rust in real-time during training is expensive.
    # A common approach is to pre-compute F_Rust for the SPICE dataset offline and store it.
    # Then, train AI to predict the difference.
    # For this example, let's assume we have pre-computed F_Rust and stored the difference F_DIFF = F_GT - F_RUST
    # So, the AI Router learns to predict F_DIFF.
    # If F_DIFF is not pre-computed, the trainer needs to compute F_Rust for each batch.
    # Let's proceed with the assumption that F_Rust is computed within the training loop using the core engine.

    # Define a loss function that compares AI output to (F_GT - F_Rust)
    def pretrain_loss(f_pred_from_ai, f_gt, c_batch, orchestrator):
        """
        Computes loss for pre-training.
        f_pred_from_ai: Force prediction from the AI Router part of the orchestrator
        f_gt: Ground truth forces from SPICE
        c_batch: Coordinates for computing F_Rust
        orchestrator: The full orchestrator model
        """
        # Compute core forces (F_Rust) using the orchestrator's core components
        # This requires mocking up top, nb_data, pe, sim_params for the batch
        B, N, _ = c_batch.shape
        # Mock topology (assuming same number of atoms)
        top_mock = type('MockTop', (), {'residue_types': torch.randint(0, 20, (B, N), device=device)})()
        # Mock neighbor data (compute using spatial hash)
        from core.spatial import GridSpatialHash
        sh_mock = GridSpatialHash([100.0, 100.0, 100.0], 12.0, device) # Use a standard box size or infer from data
        nb_data_mock = sh_mock.get_neighbor_data(c_batch)
        # Mock potential energy (can be zero or computed from core forces)
        pe_mock = torch.zeros(B, 1, device=device)
        # Mock sim_params
        sim_params_mock = {'temp': 300.0, 'salt_conc': 0.1, 'pH': 7.0, 'ionic_strength': 0.15}

        # Compute F_Rust using core specialists (without AI correction)
        f_core_total = torch.zeros_like(c_batch, device=device)
        for name, spec in orchestrator.core_specialists.items():
            f_spec, _ = spec(c_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
            f_core_total += f_spec
        for name, branch in orchestrator.branch_modules.items():
            try:
                f_branch, _ = branch(c_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
                f_core_total += f_branch
            except:
                pass # Ignore errors from branch modules during pre-training

        # The AI Router should predict the difference F_DIFF = F_GT - F_CORE
        f_diff_gt = f_gt - f_core_total.detach() # Detach F_core to stop gradients flowing back to core specialists

        # Compute loss between AI prediction and F_DIFF_GT
        loss = nn.MSELoss()(f_pred_from_ai, f_diff_gt)
        return loss


    # 4. 실험 추적 초기화
    tracker = ExperimentTracker(experiment_name="AIRouter_Pretraining_SPICE")
    tracker.start_run(run_name=f"pretrain_{target}")

    # 5. 하이퍼파라미터 로깅
    hparams = {
        'target': target,
        'spice_data_path': spice_data_path,
        'epochs': epochs,
        'batch_size': batch_size,
        'learning_rate': lr,
    }
    tracker.log_params(hparams)

    # 6. 학습 루프
    orchestrator.train()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(f"[cyan]Pre-training Router {target} on SPICE...", total=epochs)

        for epoch in range(epochs):
            epoch_loss = 0.0
            num_batches = 0

            for batch_idx, (coords_batch, forces_gt_batch) in enumerate(dataloader):
                coords_batch, forces_gt_batch = coords_batch.to(device), forces_gt_batch.to(device)

                optimizer.zero_grad()

                # --- Compute F_Rust and AI Prediction ---
                B, N, _ = coords_batch.shape
                top_mock = type('MockTop', (), {'residue_types': torch.randint(0, 20, (B, N), device=device)})()
                from core.spatial import GridSpatialHash
                sh_mock = GridSpatialHash([100.0, 100.0, 100.0], 12.0, device)
                nb_data_mock = sh_mock.get_neighbor_data(coords_batch)
                pe_mock = torch.zeros(B, 1, device=device)
                sim_params_mock = {'temp': 300.0, 'salt_conc': 0.1, 'pH': 7.0, 'ionic_strength': 0.15}

                # Forward pass through orchestrator (AI Router part will be updated)
                # We need to extract the AI Router's contribution
                # This is tricky because the orchestrator combines forces from all sources
                # A cleaner way is to isolate the AI Router's prediction
                # Or, modify the orchestrator to allow computing F_Rust and F_AI_Corr separately in one call

                # For this example, let's assume a method orchestrator.predict_ai_correction(c, top, nb, pe, sim_params)
                # that returns only the AI Router's prediction
                # f_ai_corr = orchestrator.predict_ai_correction(coords_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
                # Since this method doesn't exist, we'll use the full forward and subtract core forces later
                # This is less efficient but demonstrates the concept
                f_orchestrated_full, aux_out = orchestrator(coords_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
                # Calculate F_Core again inside the loop (inefficient, but for demo)
                f_core_total = torch.zeros_like(coords_batch, device=device)
                for name, spec in orchestrator.core_specialists.items():
                    f_spec, _ = spec(coords_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
                    f_core_total += f_spec
                for name, branch in orchestrator.branch_modules.items():
                    try:
                        f_branch, _ = branch(coords_batch, top_mock, nb_data_mock, pe_mock, sim_params_mock)
                        f_core_total += f_branch
                    except:
                        pass
                f_ai_corr = f_orchestrated_full - f_core_total # This is the AI's contribution

                # Calculate loss
                loss = pretrain_loss(f_ai_corr, forces_gt_batch, coords_batch, orchestrator)

                # Backpropagate
                loss.backward()

                # Update AI Router parameters
                optimizer.step()

                epoch_loss += loss.item()
                num_batches += 1

            avg_epoch_loss = epoch_loss / num_batches if num_batches > 0 else float('inf')
            scheduler.step(avg_epoch_loss)

            progress.update(task, advance=1, description=f"[cyan]Epoch {epoch+1}/{epochs}, Loss: {avg_epoch_loss:.4f}")

            # Epoch당 로그 출력 및 MLflow에 기록
            console.print(f"Epoch {epoch+1} | Total: {avg_epoch_loss:.4f}")
            tracker.log_metrics({'epoch_loss': avg_epoch_loss}, step=epoch)

    # [NEW] 최종 모델 로깅
    model_artifact_path = f"models/router_{target}_pretrained.pth"
    tracker.log_artifact(model_artifact_path) # 단순히 파일 저장
    # tracker.log_model(orchestrator.ai_router, "ai_router_pretrained_model") # MLflow 모델로 저장 (더 복잡한 구조 필요)

    # [NEW] Run 종료
    tracker.end_run()

    console.print(f"[bold green]✅ {target}에 대한 AI Router SPICE Pre-training 완료![/bold green]")
    # 모델 저장 (AI Router 파라미터만)
    save_path = f"models/router_{target}_pretrained.pth"
    os.makedirs("models", exist_ok=True) # 저장 디렉토리 확인
    torch.save(orchestrator.ai_router.state_dict(), save_path)
    console.print(f"📁 Pre-trained model saved: {save_path}")
    console.print(f"📊 MLflow Run ID: {tracker.get_run_id()}")


if __name__ == "__main__":
    # 예시 타겟 및 SPICE 데이터 경로
    TARGET_NAME = "SPICE_Pretrain"
    SPICE_DATA_PATH = "data/spice_train.h5" # 실제 경로로 수정 필요
    if not os.path.exists(SPICE_DATA_PATH):
        console.print(f"[bold red]에러: SPICE 데이터 파일이 존재하지 않습니다: {SPICE_DATA_PATH}[/bold red]")
        sys.exit(1)
    pretrain_air_router(TARGET_NAME, SPICE_DATA_PATH, epochs=5, batch_size=32, lr=1e-4)
    console.print("[bold cyan]" + "="*70 + "[/bold cyan]")
    console.print(f"[bold]다음 단계[/bold]: python run_refinement.py --use_router --target {TARGET_NAME} --pretrained_model_path {save_path}")
    console.print("[bold cyan]" + "="*70 + "[/bold cyan]")
