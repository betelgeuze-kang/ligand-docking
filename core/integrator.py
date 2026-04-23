# core/integrator.py

import torch
import torch.nn as nn

class LangevinIntegrator(nn.Module):
    """
    Langevin Dynamics Integrator with optional Adaptive Timestepping and Mixed Precision.
    """
    def __init__(self, dt=0.002, friction=1.0, kT=0.001987*300.0, adaptive_dt=False, dt_min=0.0005, dt_max=0.005, force_threshold=100.0, use_mixed_precision=False):
        super(LangevinIntegrator, self).__init__()
        self.register_buffer('dt', torch.tensor(dt))
        self.register_buffer('gamma', torch.tensor(friction))
        self.register_buffer('kT', torch.tensor(kT))
        self.register_buffer('kT_half', torch.tensor(kT * 0.5))

        # Adaptive Timestepping parameters
        self.adaptive_dt = adaptive_dt
        self.dt_min = dt_min
        self.dt_max = dt_max
        self.force_threshold = force_threshold # Threshold for adjusting dt based on force magnitude

        # [NEW] Mixed Precision flag
        self.use_mixed_precision = use_mixed_precision

    def step(self, c, v, f, noise=None):
        """
        Performs one step of Langevin integration.
        If adaptive_dt is True, adjusts dt based on force magnitude.
        If use_mixed_precision is True, performs some calculations in FP16.
        Args:
            c: Coordinates [B, N, 3]
            v: Velocities [B, N, 3]
            f: Forces [B, N, 3]
        Returns:
            v_new: New velocities [B, N, 3]
            c_new: New coordinates [B, N, 3]
        """
        B, N, _ = c.shape
        device = c.device

        # [NEW] Cast to FP16 if mixed precision is enabled
        if self.use_mixed_precision:
            c = c.half()
            v = v.half()
            f = f.half()
            dt = self.dt.half()
            gamma = self.gamma.half()
            kT_half = self.kT_half.half()
        else:
            dt = self.dt
            gamma = self.gamma
            kT_half = self.kT_half

        # Adaptive Timestepping Logic
        current_dt = dt
        if self.adaptive_dt:
            # Calculate max force magnitude per batch
            max_force_magnitude = f.norm(dim=-1).max(dim=-1)[0].max(dim=-1)[0] # [B]
            # Adjust dt based on force (inverse relationship)
            # This is a simple heuristic; more sophisticated methods exist
            adjustment_factor = torch.clamp(self.force_threshold / (max_force_magnitude + 1e-8), 0.1, 2.0) # Prevent extreme changes
            adjusted_dt = torch.clamp(dt * adjustment_factor, self.dt_min, self.dt_max)
            current_dt = adjusted_dt.unsqueeze(-1).unsqueeze(-1) # [B, 1, 1] for broadcasting

        # Langevin Dynamics Equations
        # v(t+dt) = v(t) + dt * f(t) / m - gamma * v(t) * dt + R
        # c(t+dt) = c(t) + v(t+dt) * dt
        # Assuming m=1.0 for simplicity
        # R is random force ~ N(0, 2*gamma*kT*dt)

        # Friction term
        friction_term = - gamma * v * current_dt

        # Random force term
        if noise is None:
            noise_std = torch.sqrt(2.0 * gamma * kT_half * current_dt)
            random_force = torch.randn_like(v, device=device, dtype=v.dtype) * noise_std
        else:
            if not isinstance(noise, torch.Tensor):
                raise TypeError("noise must be a torch.Tensor or None")
            if noise.shape != v.shape:
                raise ValueError("noise shape must match velocity tensor shape")
            random_force = noise.to(device=device, dtype=v.dtype)

        # Update velocity
        v_new = v + (f * current_dt) + friction_term + random_force

        # Update position
        c_new = c + v_new * current_dt

        # [NEW] Cast back to FP32 if mixed precision was used
        if self.use_mixed_precision:
            v_new = v_new.float()
            c_new = c_new.float()

        return v_new, c_new
