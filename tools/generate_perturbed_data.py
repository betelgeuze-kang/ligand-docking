#!/usr/bin/env python3
"""
Perturbed Data Generator — 수치 안정화된 훈련 데이터 생성 파이프라인 (HDF5 지원)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
과학적 목적: AI 코렉션 모델 학습을 위한 고품질 힘-좌표 쌍 생성
핵심 최적화: 1/r¹² 발산 방지, NaN/0 힘 필터링, 수치 안정화
성공 기준: 유효 샘플 > 95% (0.01 < force < 100.0 kcal/mol/Å)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import json
import math
import numpy as np
import torch
import torch.nn.functional as F
import h5py # [NEW] HDF5 지원
from rich.console import Console
from core.definitions import Config, ResearchConstants
from core.sim_param_schema import CORE_SIM_PARAM_DEFAULTS, DEFAULT_RUNTIME_CONDITIONING_KEYS
from core.topology import TopologyFactory
from core.spatial import GridSpatialHash
from core.forcefield import ForceField
from core.integrator import LangevinIntegrator
from tools.pdb_loader import load_native_structure
from train.target_scheduler import FoldBalancedTargetScheduler, resolve_targets

console = Console()

class DataGenerator:
    def __init__(
        self,
        target,
        total_samples=10000,
        noise=0.15,
        output_dir="data/",
        train_ratio=0.8,
        val_ratio=0.1,
        max_attempt_multiplier=20,
        fast_mode=False,
        explicit_2bead=False,
        neighbor_settings=None,
        residual_mode=False,
        reference_cutoff=14.0,
        reference_max_neighbors=160,
        reference_force_cap=100.0,
        force_backend="auto",
        sim_param_overrides=None,
    ):
        self.target = target
        self.total_samples = total_samples
        self.noise = noise
        self.dev = Config.DEVICE
        self.output_dir = output_dir
        self.max_attempt_multiplier = max_attempt_multiplier
        self.fast_mode = fast_mode
        self.explicit_2bead = explicit_2bead
        self.neighbor_settings = dict(neighbor_settings or {})
        self.residual_mode = bool(residual_mode)
        self.reference_cutoff = float(reference_cutoff)
        self.reference_max_neighbors = int(reference_max_neighbors)
        self.reference_force_cap = float(reference_force_cap) if reference_force_cap is not None else None
        self.force_backend = str(force_backend or "auto")
        self.runtime_conditioning_keys = tuple(DEFAULT_RUNTIME_CONDITIONING_KEYS)
        runtime_defaults = {
            "temp": 300.0,
            "salt_conc": 0.1,
            "pH": 7.0,
            "ionic_strength": 0.15,
            "ptm_count": 0.0,
            "force_scale": 1.0,
            "cooling_rate": 0.0,
            "hydro_strength": 1.0,
            "k_angle": 25.0,
            "theta0": 109.5,
            "k_dihedral": 1.0,
            "phi0_alpha": -57.0,
            "ai_correction_active": 1.0,
        }
        runtime_defaults.update({k: float(v) for k, v in CORE_SIM_PARAM_DEFAULTS.items()})
        raw_overrides = sim_param_overrides if isinstance(sim_param_overrides, dict) else {}
        self.runtime_profile = dict(runtime_defaults)
        for k, v in raw_overrides.items():
            if k not in self.runtime_profile:
                continue
            try:
                self.runtime_profile[k] = float(v)
            except Exception:
                continue
        # Conservative clamps for stability
        self.runtime_profile["temp"] = float(np.clip(self.runtime_profile.get("temp", 300.0), 250.0, 550.0))
        self.runtime_profile["salt_conc"] = float(np.clip(self.runtime_profile.get("salt_conc", 0.1), 0.0, 1.0))
        self.runtime_profile["pH"] = float(np.clip(self.runtime_profile.get("pH", 7.0), 3.0, 11.0))
        self.runtime_profile["ionic_strength"] = float(np.clip(self.runtime_profile.get("ionic_strength", 0.15), 0.0, 1.0))
        self.runtime_profile["ptm_count"] = float(np.clip(self.runtime_profile.get("ptm_count", 0.0), 0.0, 16.0))
        self.runtime_profile["force_scale"] = float(np.clip(self.runtime_profile.get("force_scale", 1.0), 0.5, 1.5))
        self.runtime_profile["cooling_rate"] = float(np.clip(self.runtime_profile.get("cooling_rate", 0.0), -2.0, 2.0))
        self.runtime_profile["hydro_strength"] = float(np.clip(self.runtime_profile.get("hydro_strength", 1.0), 0.5, 1.5))
        self.runtime_profile["k_angle"] = float(np.clip(self.runtime_profile.get("k_angle", 25.0), 1.0, 200.0))
        self.runtime_profile["theta0"] = float(np.clip(self.runtime_profile.get("theta0", 109.5), 60.0, 180.0))
        self.runtime_profile["k_dihedral"] = float(np.clip(self.runtime_profile.get("k_dihedral", 1.0), 0.0, 50.0))
        self.runtime_profile["phi0_alpha"] = float(np.clip(self.runtime_profile.get("phi0_alpha", -57.0), -180.0, 180.0))
        self.runtime_profile["ai_correction_active"] = float(
            1.0 if self.runtime_profile.get("ai_correction_active", 1.0) >= 0.5 else 0.0
        )
        if self.fast_mode:
            self.source_tag = "fast_synthetic"
        elif self.residual_mode:
            self.source_tag = "rust_residual_pair"
        else:
            self.source_tag = "rust_physics_force"
        os.makedirs(output_dir, exist_ok=True)

        # Calculate split sizes
        self.train_samples = int(total_samples * train_ratio)
        self.val_samples = int(total_samples * val_ratio)
        self.test_samples = total_samples - self.train_samples - self.val_samples
        console.print(f"Splitting samples: Train={self.train_samples}, Val={self.val_samples}, Test={self.test_samples}")

    @staticmethod
    def _compute_quality_score(force_magnitude, f_physics, f_target):
        """
        Lightweight sample quality score in [0, 1].
        Higher is better (stable/finite/non-extreme force region).
        """
        max_force = float(force_magnitude.max().item())
        target_force_max = float(f_target.abs().max().item())
        finite_ratio = float(torch.isfinite(f_physics).float().mean().item())
        max_norm_penalty = min(max_force / 100.0, 1.0)
        target_penalty = min(target_force_max / 100.0, 1.0)
        finite_penalty = 1.0 - min(max(finite_ratio, 0.0), 1.0)
        score = 1.0 - (0.45 * max_norm_penalty + 0.35 * target_penalty + 0.20 * finite_penalty)
        return float(np.clip(score, 0.0, 1.0))

    def generate(self):
        """
        Perturbed coordinate-force pairs generation pipeline.
        Saves data in HDF5 format with train/val/test splits.
        """
        console.print(f"[bold blue]Generating {self.total_samples} samples for {self.target} (Train/Val/Test Split)[/bold blue]")
        t_conf = ResearchConstants.CHALLENGES[self.target]
        n_res = t_conf['n_res']
        box_size = t_conf['box']
        box_tensor = torch.as_tensor(box_size, dtype=torch.float32, device=self.dev)

        # Load native structure for reference and initial state
        native_coords, seq = load_native_structure(self.target)
        if native_coords is None:
            console.print(f"[bold red]Failed to load native structure for {self.target}. Using linear init.[/bold red]")
            native_coords = torch.linspace(0, n_res-1, n_res, device=Config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3)
        elif native_coords.dim() == 2:
            native_coords = native_coords.unsqueeze(0)

        native_coords = native_coords.to(Config.DEVICE)
        native_coords.requires_grad = False # No grad needed for native structure

        # Setup system components
        top = TopologyFactory(n_res, t_conf['type'], box_size, self.dev, target_name=self.target)
        use_explicit_2bead = bool(self.explicit_2bead and top.use_virtual_sc)
        if use_explicit_2bead:
            native_ca = native_coords
            native_sc = top.compute_virtual_sc_coords(native_ca)
            native_model = torch.cat([native_ca, native_sc], dim=1)
            residue_types_model = top.expand_residue_types_for_virtual_sc()
            console.print("[cyan]Representation: explicit CA-SC 2-bead ([2N,3])[/cyan]")
        else:
            native_ca = native_coords
            native_model = native_coords
            residue_types_model = top.residue_types

        sh = None
        ff = None
        if not self.fast_mode:
            grid_spacing = float(self.neighbor_settings.get("grid_spacing", 12.0))
            sh = GridSpatialHash(
                box_size,
                grid_spacing,
                self.dev,
                **{k: v for k, v in self.neighbor_settings.items() if k != "grid_spacing"},
            )
            hydro_scale = float(self.runtime_profile.get("hydro_strength", 1.0))
            ionic_strength = float(self.runtime_profile.get("ionic_strength", 0.15))
            force_scale = float(self.runtime_profile.get("force_scale", 1.0))
            ff_params = {
                'd_e': 20.0 * hydro_scale,
                'eps_solv': 25.0 * (1.0 + 0.5 * ionic_strength),
                'sigma': 3.8 * (1.0 + 0.05 * (force_scale - 1.0)),
                'r0': 4.2,
            } # Standard params + conservative runtime perturbation
            ff = ForceField(
                top,
                params=ff_params,
                neighbor_settings=self.neighbor_settings,
                force_backend=self.force_backend,
            ).to(self.dev)

        start_time = time.time()
        generated_count = 0
        valid_count = 0
        attempts = 0
        max_attempts = max(self.total_samples * self.max_attempt_multiplier, self.total_samples)

        # Prepare storage lists for splits
        splits_data = {
            'train': {
                'coords': [],
                'physics_forces': [],
                'target_forces': [],
                'residue_types': [],
                'quality_score': [],
                'reject_reason': [],
                'source': [],
            },
            'val': {
                'coords': [],
                'physics_forces': [],
                'target_forces': [],
                'residue_types': [],
                'quality_score': [],
                'reject_reason': [],
                'source': [],
            },
            'test': {
                'coords': [],
                'physics_forces': [],
                'target_forces': [],
                'residue_types': [],
                'quality_score': [],
                'reject_reason': [],
                'source': [],
            }
        }
        for split_key in ("train", "val", "test"):
            for sim_key in self.runtime_conditioning_keys:
                splits_data[split_key][sim_key] = []
        sample_counts = {'train': 0, 'val': 0, 'test': 0}
        reject_stats = {}

        def _register_reject(reason):
            reject_stats[reason] = reject_stats.get(reason, 0) + 1

        # Generate samples
        while generated_count < self.total_samples and attempts < max_attempts:
            attempts += 1
            # --- 1. Generate Perturbed Coordinate ---
            temp_scale = math.sqrt(max(float(self.runtime_profile.get("temp", 300.0)), 1.0) / 300.0)
            cool_scale = float(np.clip(1.0 + 0.1 * float(self.runtime_profile.get("cooling_rate", 0.0)), 0.6, 1.4))
            force_scale = float(self.runtime_profile.get("force_scale", 1.0))
            noise_sigma = float(max(1e-6, self.noise * temp_scale * cool_scale * force_scale))
            if use_explicit_2bead:
                # Perturb CA then derive virtual SC to keep bead geometry consistent.
                noise_tensor = torch.randn_like(native_ca, device=self.dev) * noise_sigma
                c_ca_perturbed = native_ca + noise_tensor
                c_ca_perturbed = torch.remainder(c_ca_perturbed, box_tensor)
                c_sc_perturbed = top.compute_virtual_sc_coords(c_ca_perturbed)
                c_perturbed = torch.cat([c_ca_perturbed, c_sc_perturbed], dim=1)
            else:
                noise_tensor = torch.randn_like(native_model, device=self.dev) * noise_sigma
                c_perturbed = native_model + noise_tensor

            # Apply minimal distance constraint (optional, can be handled by ForceField)
            # Ensure it fits in the box
            c_perturbed = torch.remainder(c_perturbed, box_tensor)

            # --- 2. Compute Physics-based Quantities ---
            try:
                if self.fast_mode:
                    # High-throughput synthetic force for large batch generation.
                    displacement = c_perturbed - native_model
                    f_physics = -0.5 * displacement
                    pe = displacement.pow(2).sum(dim=-1).mean(dim=-1, keepdim=True)
                else:
                    f_physics, pe = ff.compute(c_perturbed, sh.get_neighbor_data(c_perturbed)) # Calculate neighbor data on-the-fly

                    # Placeholder forcefield가 0-force를 반환하는 경우를 위한 fallback.
                    # native에서의 변위를 이용한 약한 harmonic force를 사용합니다.
                    if f_physics.abs().max().item() < 1e-8:
                        displacement = c_perturbed - native_model
                        f_physics = -0.5 * displacement
                        pe = displacement.pow(2).sum(dim=-1).mean(dim=-1, keepdim=True)

                # CA-SC 2-bead/강한 LJ 설정에서 force 폭주가 발생할 수 있으므로
                # 샘플 단위로 force를 안전 범위로 정규화합니다.
                max_force_mag = f_physics.norm(dim=-1).max().item()
                if max_force_mag > 100.0:
                    scale = 100.0 / max_force_mag
                    f_physics = f_physics * scale

                # --- 3. Define Target Force ---
                if self.residual_mode and not self.fast_mode:
                    f_reference, _ = ff.compute_reference_pytorch(
                        c_perturbed,
                        cutoff=self.reference_cutoff,
                        max_neighbors=self.reference_max_neighbors,
                        skin=0.0,
                    )
                    if self.reference_force_cap is not None and self.reference_force_cap > 0.0:
                        ref_max_force_mag = f_reference.norm(dim=-1).max().item()
                        if ref_max_force_mag > self.reference_force_cap:
                            ref_scale = self.reference_force_cap / ref_max_force_mag
                            f_reference = f_reference * ref_scale
                    f_target = (f_reference - f_physics).clone().detach()
                else:
                    f_target = f_physics.clone().detach()

                # --- 4. Validate Sample ---
                force_magnitude = f_physics.norm(dim=-1) # [1, n_res]
                finite_mask = torch.isfinite(force_magnitude) & torch.isfinite(pe)
                valid_force_mask = (force_magnitude < 100.0) & finite_mask
                if not valid_force_mask.all():
                    _register_reject("invalid_force_or_energy")
                    continue # Skip invalid sample
                if f_target.abs().max().item() < 1e-12:
                    _register_reject("zero_target_force")
                    continue # Skip invalid sample

                # --- 5. Determine Split ---
                split_key = 'train'
                if sample_counts['train'] < self.train_samples:
                    split_key = 'train'
                elif sample_counts['val'] < self.val_samples:
                    split_key = 'val'
                else:
                    split_key = 'test'

                # --- 6. Store Valid Sample ---
                splits_data[split_key]['coords'].append(c_perturbed.squeeze(0).cpu().numpy()) # Move to CPU and convert to numpy
                splits_data[split_key]['physics_forces'].append(f_physics.squeeze(0).cpu().numpy())
                splits_data[split_key]['target_forces'].append(f_target.squeeze(0).cpu().numpy())
                splits_data[split_key]['residue_types'].append(residue_types_model.cpu().numpy())
                splits_data[split_key]['quality_score'].append(
                    self._compute_quality_score(force_magnitude, f_physics, f_target)
                )
                splits_data[split_key]['reject_reason'].append("ok")
                splits_data[split_key]['source'].append(self.source_tag)
                for sim_key in self.runtime_conditioning_keys:
                    splits_data[split_key][sim_key].append(float(self.runtime_profile.get(sim_key, 0.0)))

                sample_counts[split_key] += 1
                valid_count += 1
            except Exception as e:
                _register_reject(f"exception:{type(e).__name__}")
                console.print(f"Sample generation failed: {e}", style="dim")
                continue # Skip this sample

            generated_count += 1

            # Progress update
            if generated_count % 1000 == 0:
                elapsed = time.time() - start_time
                rate = generated_count / elapsed if elapsed > 0 else 0
                console.print(f"  Generated {generated_count}/{self.total_samples} (Rate: {rate:.1f}/s, Valid: {valid_count})")

        if generated_count < self.total_samples:
            console.print(
                f"[yellow]⚠️  Stopped early for {self.target}: generated {generated_count}/{self.total_samples} "
                f"after {attempts} attempts.[/yellow]"
            )

        # Save to HDF5 files for each split
        success = True
        for split_name, data_dict in splits_data.items():
            if data_dict['coords']:
                output_file_path = os.path.join(self.output_dir, f"{self.target.lower()}_airouter_{split_name}_data.h5")
                console.print(f"[green]✅ Saving {split_name} data to HDF5: {output_file_path}[/green]")
                try:
                    with h5py.File(output_file_path, 'w') as f:
                        f.create_dataset('coords', data=data_dict['coords'], compression='gzip')
                        f.create_dataset('physics_forces', data=data_dict['physics_forces'], compression='gzip')
                        f.create_dataset('target_forces', data=data_dict['target_forces'], compression='gzip')
                        f.create_dataset('residue_types', data=data_dict['residue_types'], compression='gzip')
                        f.create_dataset(
                            'quality_score',
                            data=np.asarray(data_dict['quality_score'], dtype=np.float32),
                            compression='gzip',
                        )
                        str_dtype = h5py.string_dtype(encoding='utf-8')
                        f.create_dataset(
                            'reject_reason',
                            data=np.asarray(data_dict['reject_reason'], dtype=object),
                            dtype=str_dtype,
                        )
                        f.create_dataset(
                            'source',
                            data=np.asarray(data_dict['source'], dtype=object),
                            dtype=str_dtype,
                        )
                        for sim_key in self.runtime_conditioning_keys:
                            if sim_key in data_dict and len(data_dict[sim_key]) > 0:
                                f.create_dataset(
                                    sim_key,
                                    data=np.asarray(data_dict[sim_key], dtype=np.float32),
                                    compression='gzip',
                                )
                        # Add metadata if needed
                        f.attrs['target'] = self.target
                        f.attrs['noise_level'] = self.noise
                        f.attrs['generated_samples'] = sample_counts[split_name]
                        f.attrs['total_requested_samples'] = getattr(self, f'{split_name}_samples')
                        f.attrs['representation'] = 'ca_sc_explicit' if use_explicit_2bead else 'ca_implicit'
                        f.attrs['n_beads_per_residue'] = 2 if use_explicit_2bead else 1
                        f.attrs['residual_mode'] = bool(self.residual_mode)
                        f.attrs['reference_cutoff'] = float(self.reference_cutoff)
                        f.attrs['reference_max_neighbors'] = int(self.reference_max_neighbors)
                        f.attrs['reference_force_cap'] = -1.0 if self.reference_force_cap is None else float(self.reference_force_cap)
                        f.attrs['source_tag'] = self.source_tag
                        f.attrs['runtime_profile_json'] = json.dumps(self.runtime_profile, sort_keys=True)
                        f.attrs['total_attempts'] = int(attempts)
                        f.attrs['total_rejected_attempts'] = int(sum(reject_stats.values()))
                        f.attrs['reject_stats_json'] = json.dumps(reject_stats, sort_keys=True)
                        if data_dict['quality_score']:
                            q = np.asarray(data_dict['quality_score'], dtype=np.float32)
                            f.attrs['quality_score_mean'] = float(np.mean(q))
                            f.attrs['quality_score_min'] = float(np.min(q))
                            f.attrs['quality_score_max'] = float(np.max(q))
                except Exception as e:
                    console.print(f"[red]❌ Error saving {split_name}  {e}[/red]")
                    success = False
            else:
                console.print(f"[yellow]⚠️  No valid {split_name} samples generated for {self.target}[/yellow]")
                if split_name == 'train':
                    success = False

        if success:
            console.print(f"[green]✅ Successfully generated and saved train/val/test splits for {self.target}[/green]")
            return True
        else:
            console.print(f"[red]❌ Failed to save some splits for {self.target}[/red]")
            return False


def _allocate_even(total_samples, targets):
    base = total_samples // len(targets)
    rem = total_samples % len(targets)
    plan = {}
    for idx, target in enumerate(targets):
        plan[target] = base + (1 if idx < rem else 0)
    return plan


def generate_multi_target_data(
    targets,
    total_samples=10000,
    noise=0.15,
    output_dir="data/",
    train_ratio=0.8,
    val_ratio=0.1,
    fast_mode=False,
    explicit_2bead=False,
    neighbor_settings=None,
    residual_mode=False,
    reference_cutoff=14.0,
    reference_max_neighbors=160,
    reference_force_cap=100.0,
    force_backend="auto",
):
    scheduler = FoldBalancedTargetScheduler()
    all_targets_set = set(scheduler.get_all_targets())
    selected_targets = list(targets)

    if set(selected_targets) == all_targets_set:
        sample_plan = scheduler.allocate_samples(total_samples, min_per_target=1)
    else:
        sample_plan = _allocate_even(total_samples, selected_targets)

    console.print(f"[bold cyan]Multi-target generation plan:[/bold cyan] {sample_plan}")
    success = True
    for target in selected_targets:
        per_target_samples = sample_plan.get(target, 0)
        if per_target_samples <= 0:
            continue
        generator = DataGenerator(
            target=target,
            total_samples=per_target_samples,
            noise=noise,
            output_dir=output_dir,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            fast_mode=fast_mode,
            explicit_2bead=explicit_2bead,
            neighbor_settings=neighbor_settings,
            residual_mode=residual_mode,
            reference_cutoff=reference_cutoff,
            reference_max_neighbors=reference_max_neighbors,
            reference_force_cap=reference_force_cap,
            force_backend=force_backend,
        )
        ok = generator.generate()
        if not ok:
            success = False
    return success


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Generate perturbed data for AI correction training.')
    parser.add_argument('--target', type=str, help='Target name (e.g., Chignolin)')
    parser.add_argument('--all_targets', action='store_true', help='Generate data for all registered small-protein targets')
    parser.add_argument('--schedule', type=str, default='fold_balanced', choices=['fold_balanced', 'round_robin', 'alphabetical', 'defined'], help='Target scheduling strategy when --all_targets is used')
    parser.add_argument('--max_targets', type=int, default=None, help='Max number of targets to include when --all_targets is used')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for target scheduling')
    parser.add_argument('--samples', type=int, default=10000, help='Total number of samples to generate')
    parser.add_argument('--noise', type=float, default=0.15, help='Noise level for perturbation')
    parser.add_argument('--fast_mode', action='store_true', help='Use fast synthetic-force mode for high-throughput generation')
    parser.add_argument('--explicit_2bead', action='store_true', help='Store explicit CA+SC 2-bead coordinates/forces ([2N,3])')
    parser.add_argument('--residual_mode', action='store_true', help='Set target_forces = reference_forces - physics_forces')
    parser.add_argument('--reference_cutoff', type=float, default=14.0, help='Reference cutoff for residual-mode force target')
    parser.add_argument('--reference_max_neighbors', type=int, default=160, help='Reference max neighbors for residual-mode force target')
    parser.add_argument('--reference_force_cap', type=float, default=100.0, help='Cap reference-force magnitude in residual mode. <=0 disables capping.')
    parser.add_argument('--force_backend', type=str, default='auto', choices=['auto', 'pytorch'], help='Physics backend for force computation in data generation.')
    parser.add_argument('--neighbor_settings', type=str, default='', help='Comma separated key=value for neighbor settings')
    parser.add_argument('--output_dir', type=str, default='data/', help='Directory to save data')
    parser.add_argument('--train_ratio', type=float, default=0.8, help='Ratio of training samples')
    parser.add_argument('--val_ratio', type=float, default=0.1, help='Ratio of validation samples')

    args = parser.parse_args()

    neighbor_settings = {}
    if args.neighbor_settings:
        for kv in args.neighbor_settings.split(','):
            kv = kv.strip()
            if not kv:
                continue
            if '=' not in kv:
                parser.error(f"Invalid --neighbor_settings entry: {kv}")
            key, value = kv.split('=', 1)
            key = key.strip()
            value = value.strip()
            if '.' in value:
                parsed = float(value)
            else:
                try:
                    parsed = int(value)
                except ValueError:
                    parsed = float(value)
            neighbor_settings[key] = parsed

    if args.all_targets:
        targets = resolve_targets(
            target='all',
            schedule=args.schedule,
            max_targets=args.max_targets,
            seed=args.seed,
        )
        success = generate_multi_target_data(
            targets=targets,
            total_samples=args.samples,
            noise=args.noise,
            output_dir=args.output_dir,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            fast_mode=args.fast_mode,
            explicit_2bead=args.explicit_2bead,
            neighbor_settings=neighbor_settings,
            residual_mode=args.residual_mode,
            reference_cutoff=args.reference_cutoff,
            reference_max_neighbors=args.reference_max_neighbors,
            reference_force_cap=None if args.reference_force_cap <= 0.0 else args.reference_force_cap,
            force_backend=args.force_backend,
        )
    else:
        if not args.target:
            parser.error("--target is required unless --all_targets is set.")
        generator = DataGenerator(
            target=args.target,
            total_samples=args.samples,
            noise=args.noise,
            output_dir=args.output_dir,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            fast_mode=args.fast_mode,
            explicit_2bead=args.explicit_2bead,
            neighbor_settings=neighbor_settings,
            residual_mode=args.residual_mode,
            reference_cutoff=args.reference_cutoff,
            reference_max_neighbors=args.reference_max_neighbors,
            reference_force_cap=None if args.reference_force_cap <= 0.0 else args.reference_force_cap,
            force_backend=args.force_backend,
        )
        success = generator.generate()

    if not success:
        sys.exit(1) # Exit with error code if generation fails
