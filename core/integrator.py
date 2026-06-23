# core/integrator.py

from __future__ import annotations

import torch
import torch.nn as nn


class LangevinIntegrator(nn.Module):
    """Euler-Maruyama Langevin integrator for coarse-grained states.

    The integrator keeps the historical ``noise`` argument semantics: when
    supplied, ``noise`` is treated as an already-scaled velocity increment.
    When omitted, the increment is sampled with variance
    ``2 * gamma * kT * dt / mass``.
    """

    SUPPORTED_COARSE_MASS_POLICIES = frozenset({"explicit_unit_mass", "explicit_mass_tensor"})

    def __init__(
        self,
        dt: float = 0.002,
        friction: float = 1.0,
        kT: float = 0.001987 * 300.0,
        adaptive_dt: bool = False,
        dt_min: float = 0.0005,
        dt_max: float = 0.005,
        force_threshold: float = 100.0,
        use_mixed_precision: bool = False,
        mass: float | torch.Tensor = 1.0,
        coarse_mass_policy: str = "explicit_unit_mass",
        seed: int | None = None,
    ) -> None:
        super().__init__()
        if float(dt) <= 0.0:
            raise ValueError("dt must be positive")
        if float(friction) < 0.0:
            raise ValueError("friction must be non-negative")
        if float(kT) < 0.0:
            raise ValueError("kT must be non-negative")
        if float(dt_min) <= 0.0:
            raise ValueError("dt_min must be positive")
        if float(dt_max) < float(dt_min):
            raise ValueError("dt_max must be greater than or equal to dt_min")
        if float(force_threshold) <= 0.0:
            raise ValueError("force_threshold must be positive")

        self.register_buffer("dt", torch.tensor(float(dt), dtype=torch.float32))
        self.register_buffer("gamma", torch.tensor(float(friction), dtype=torch.float32))
        self.register_buffer("kT", torch.tensor(float(kT), dtype=torch.float32))
        # Retain the legacy state-dict key for backward compatibility. The
        # stochastic increment now correctly uses the full kT value.
        self.register_buffer("kT_half", torch.tensor(float(kT) * 0.5, dtype=torch.float32))
        policy = str(coarse_mass_policy)
        if policy not in self.SUPPORTED_COARSE_MASS_POLICIES:
            raise ValueError(f"unsupported coarse_mass_policy: {policy}")
        self.register_buffer("mass", torch.as_tensor(mass, dtype=torch.float32).clone().detach())

        self.adaptive_dt = bool(adaptive_dt)
        self.dt_min = float(dt_min)
        self.dt_max = float(dt_max)
        self.force_threshold = float(force_threshold)
        self.use_mixed_precision = bool(use_mixed_precision)
        self.coarse_mass_policy = policy
        self.last_dt: torch.Tensor | None = None
        self.seed = int(seed) if seed is not None else None
        self._generators: dict[str, torch.Generator] = {}

    def set_seed(self, seed: int) -> LangevinIntegrator:
        self.seed = int(seed)
        self._generators = {}
        return self

    def _generator_for(self, device: torch.device) -> torch.Generator | None:
        if self.seed is None:
            return None
        key = str(device)
        if key not in self._generators:
            gen = torch.Generator(device=device)
            gen.manual_seed(int(self.seed))
            self._generators[key] = gen
        return self._generators[key]

    @staticmethod
    def _validate_state(c: torch.Tensor, v: torch.Tensor, f: torch.Tensor) -> None:
        for name, value in (("c", c), ("v", v), ("f", f)):
            if not isinstance(value, torch.Tensor):
                raise TypeError(f"{name} must be a torch.Tensor")
            if not value.is_floating_point():
                raise TypeError(f"{name} must be floating point")
        if c.ndim != 3 or c.shape[-1] != 3:
            raise ValueError("c must have shape [B, N, 3]")
        if c.shape[0] < 1 or c.shape[1] < 1:
            raise ValueError("c batch and atom dimensions must be non-empty")
        if v.shape != c.shape:
            raise ValueError("v shape must match c shape")
        if f.shape != c.shape:
            raise ValueError("f shape must match c shape")
        if v.device != c.device or f.device != c.device:
            raise ValueError("c, v, and f must be on the same device")

    @staticmethod
    def _broadcast_mass(mass: float | torch.Tensor, like: torch.Tensor) -> torch.Tensor:
        mass_t = torch.as_tensor(mass, device=like.device, dtype=like.dtype)
        if mass_t.ndim == 0:
            mass_t = mass_t.view(1, 1, 1)
        elif mass_t.ndim == 1:
            mass_t = mass_t.view(1, -1, 1)
        elif mass_t.ndim == 2:
            mass_t = mass_t.unsqueeze(-1)
        elif mass_t.ndim != 3:
            raise ValueError("mass must be scalar, [N], [B,N], or [B,N,1]")
        if mass_t.shape[0] not in (1, like.shape[0]):
            raise ValueError("mass batch dimension must be 1 or match coordinates")
        if mass_t.shape[1] not in (1, like.shape[1]):
            raise ValueError("mass atom dimension must be 1 or match coordinates")
        if mass_t.shape[2] not in (1, like.shape[2]):
            raise ValueError("mass coordinate dimension must be 1 or match coordinates")
        if torch.any(mass_t <= 0):
            raise ValueError("mass values must be positive")
        return mass_t

    def _current_timestep(self, f: torch.Tensor, *, dtype: torch.dtype) -> torch.Tensor:
        device = f.device
        dt = self.dt.to(device=device, dtype=dtype)
        if not self.adaptive_dt:
            return dt.view(1, 1, 1)

        # Keep adaptive timesteps independent across batch members. The prior
        # implementation reduced over the batch dimension and let one sample's
        # largest force alter every trajectory in the batch.
        max_force_magnitude = f.norm(dim=-1).amax(dim=-1)  # [B]
        threshold = torch.as_tensor(self.force_threshold, device=device, dtype=dtype)
        adjustment_factor = torch.clamp(
            threshold / (max_force_magnitude + torch.finfo(dtype).eps),
            min=0.1,
            max=2.0,
        )
        adjusted_dt = torch.clamp(
            dt * adjustment_factor,
            min=self.dt_min,
            max=self.dt_max,
        )
        return adjusted_dt.view(-1, 1, 1)

    def step(
        self,
        c: torch.Tensor,
        v: torch.Tensor,
        f: torch.Tensor,
        noise: torch.Tensor | None = None,
        mass: float | torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Advance coordinates and velocities by one Langevin step.

        Args:
            c: Coordinates with shape ``[B, N, 3]``.
            v: Velocities with shape ``[B, N, 3]``.
            f: Forces with shape ``[B, N, 3]``.
            noise: Optional pre-scaled velocity increment matching ``v``.
            mass: Optional scalar, ``[N]``, ``[B,N]``, or ``[B,N,1]`` positive mass tensor.

        Returns:
            ``(v_new, c_new)`` with the same shape as the inputs. Historical
            mixed-precision behavior is retained by returning FP32 outputs.
        """
        self._validate_state(c, v, f)
        output_dtype = torch.float32 if self.use_mixed_precision else c.dtype
        compute_dtype = torch.float16 if self.use_mixed_precision else c.dtype
        device = c.device

        c_work = c.to(dtype=compute_dtype)
        v_work = v.to(dtype=compute_dtype)
        f_work = f.to(dtype=compute_dtype)
        mass_work = self._broadcast_mass(self.mass if mass is None else mass, v_work)
        current_dt = self._current_timestep(f_work, dtype=compute_dtype)
        self.last_dt = current_dt.detach().to(dtype=torch.float32)

        gamma = self.gamma.to(device=device, dtype=compute_dtype)
        kT = self.kT.to(device=device, dtype=compute_dtype)

        friction_term = -gamma * v_work * current_dt

        if noise is None:
            variance = torch.clamp(2.0 * gamma * kT * current_dt / mass_work, min=0.0)
            noise_std = torch.sqrt(variance)
            generator = self._generator_for(device)
            random_force = torch.randn(
                v_work.shape,
                device=device,
                dtype=compute_dtype,
                generator=generator,
            ) * noise_std
        else:
            if not isinstance(noise, torch.Tensor):
                raise TypeError("noise must be a torch.Tensor or None")
            if noise.shape != v.shape:
                raise ValueError("noise shape must match velocity tensor shape")
            random_force = noise.to(device=device, dtype=compute_dtype)

        v_new = v_work + (f_work * current_dt / mass_work) + friction_term + random_force
        c_new = c_work + v_new * current_dt
        return v_new.to(dtype=output_dtype), c_new.to(dtype=output_dtype)
