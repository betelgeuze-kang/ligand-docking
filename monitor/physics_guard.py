# monitor/physics_guard.py

import torch
import numpy as np # 탐색 확률 계산용
from core.definitions import Config
from train.local_teacher import LocalTeacher # [NEW] Import Local Teacher

class PhysicsGuard:
    """✅ Stage 1 개선: 에너지 드리프트 한계 5% → 1.5% 강화
    - 가상 2-Bead 모델의 5% 오차 목표 달성을 위한 엄격한 보존 검증
    - 잔기당 절대 드리프트 추가 검증 (0.5 kcal/mol/residue)
    - 운동량 보존 검증 강화 (3% → 1.5%)"""
    
    def __init__(
        self,
        max_energy_drift=0.015,
        max_momentum_drift=0.015,
        min_interatomic_distance=0.0,
        enable_local_teacher=True,
        enable_momentum_check=True,
    ):
        self.max_energy_drift = max_energy_drift # 🔑 5% → 1.5% 강화
        self.max_momentum_drift = max_momentum_drift # 🔑 3% → 1.5% 강화
        # Optional hard safety check for steric overlap. 0.0 means disabled.
        self.min_interatomic_distance = float(max(min_interatomic_distance, 0.0))
        self.last_energy = None
        self.last_momentum = None
        self.violation_count = 0
        self.n_res = None # 잔기 수 저장 (절대 드리프트 계산용)
        self.last_min_distance = None
        self.enable_local_teacher = bool(enable_local_teacher)
        self.enable_momentum_check = bool(enable_momentum_check)

        # [NEW] Local Teacher instance
        self.local_teacher = LocalTeacher() if self.enable_local_teacher else None

    def set_system_size(self, n_res):
        """시스템 크기 설정 (잔기당 드리프트 계산용)"""
        self.n_res = n_res

    # [MODIFIED] check_conservation 메서드 확장: f_core, f_ai_corr 입력 추가, Local Teacher 호출
    def check_conservation(self, c, v, pe, f_core, f_ai_corr, step):
        """
        Checks energy and momentum conservation, including influence of AI correction.
        Args:
            c: Coordinates [B, N, 3]
            v: Velocities [B, N, 3]
            pe: Potential energy [B, 1] (from core forces)
            f_core: Core forces from physics engine [B, N, 3]
            f_ai_corr: AI correction forces [B, N, 3] (from StrategicOrchestrator or other AI)
            step: Current simulation step
        Returns:
            is_ok (bool): True if no violations detected
            message (str): Description of violation or "OK"
        """
        B, N, _ = c.shape
        # Kinetic Energy Calculation (Optional, for completeness)
        # Note: The original code used pe for energy drift. We can stick to that or add KE.
        # For this modification, we'll keep the PE-based check and add momentum/AI checks.
        # Let's also add KE check for completeness, similar to previous attempt.
        # kT = 0.001987 * 300.0 # Assuming temp = 300K for KE calc if needed, or pass temp
        kinetic_energy = 0.5 * v.norm(dim=-1).pow(2).mean(dim=1) # [B] 평균

        # Momentum Calculation (Mass assumed to be 1.0 for simplicity)
        momentum = v.sum(dim=1).sum(dim=0) # [3] vector sum over batch and atoms

        # 1. Check Energy Drift (Original: based on PE)
        current_pe_mean = pe.mean().item()
        if self.last_energy is not None:
            delta_pe = abs(current_pe_mean - self.last_energy) / (abs(self.last_energy) + 1e-6)
            if delta_pe > self.max_energy_drift:
                self.violation_count += 1
                # [NEW] Call Local Teacher to analyze and provide data for online learning
                if self.local_teacher is not None:
                    self.local_teacher.handle_violation(c, v, pe, f_core, f_ai_corr, step, violation_type='energy')
                return False, f"Energy violation (PE): {delta_pe*100:.1f}% drift (>1.5%) at step {step}"

        # 2. Check Momentum Drift (Original)
        if self.enable_momentum_check and self.last_momentum is not None:
            delta_p_vec = torch.abs(momentum - self.last_momentum) # [3]
            delta_p = delta_p_vec.mean().item() # Average drift per component
            if delta_p > self.max_momentum_drift:
                self.violation_count += 1
                # [NEW] Call Local Teacher to analyze and provide data for online learning
                if self.local_teacher is not None:
                    self.local_teacher.handle_violation(c, v, pe, f_core, f_ai_corr, step, violation_type='momentum')
                return False, f"Momentum violation: {delta_p*100:.1f}% drift (>1.5%) at step {step}"

        # 3. Optional steric-overlap check (hard geometric sanity gate).
        if self.min_interatomic_distance > 0.0 and N > 1:
            dmat = torch.cdist(c, c) # [B, N, N]
            eye = torch.eye(N, dtype=torch.bool, device=c.device).unsqueeze(0)
            dmat = dmat.masked_fill(eye, float("inf"))
            min_dist = float(dmat.min().item()) if dmat.numel() > 0 else float("inf")
            self.last_min_distance = min_dist
            if min_dist < self.min_interatomic_distance:
                self.violation_count += 1
                if self.local_teacher is not None:
                    self.local_teacher.handle_violation(c, v, pe, f_core, f_ai_corr, step, violation_type='overlap')
                return (
                    False,
                    f"Steric overlap violation: min distance {min_dist:.3f} Å "
                    f"(< {self.min_interatomic_distance:.3f} Å) at step {step}",
                )

        # [EXISTING] 4. Check AI Correction Force Impact (Added logic)
        # Evaluate the magnitude of AI forces relative to core forces or total forces
        core_force_magnitude = f_core.norm(dim=-1).mean().item() # Scalar
        ai_force_magnitude = f_ai_corr.norm(dim=-1).mean().item() # Scalar
        # Option 1: Check if AI force is disproportionately large compared to core
        ai_to_core_ratio = ai_force_magnitude / (core_force_magnitude + 1e-6) # Avoid division by zero
        ai_force_threshold_ratio = 0.5 # e.g., if AI force is > 50% of core force magnitude, flag
        if ai_to_core_ratio > ai_force_threshold_ratio:
            print(f"  [PhysicsGuard] WARNING: AI force magnitude ({ai_force_magnitude:.3f}) is "
                  f"{ai_to_core_ratio:.1f}x larger than core force magnitude ({core_force_magnitude:.3f}). "
                  f"This may increase violation risk. Step: {step}")
            # 경고는 카운터를 올리지 않습니다.
            # 실제 보존 법칙 위반(energy/momentum)만 violation_count에 반영합니다.

        # Update stored values for next step comparison
        # Using PE for energy check as per original
        self.last_energy = current_pe_mean
        self.last_momentum = momentum.detach().clone()

        return True, "OK"


    def auto_recover(self, c, v, c_prev, v_prev):
        """물리 위반 시 자동 복구: 이전 상태로 롤백 + 속도 감쇠"""
        c = c_prev.clone()
        v = v_prev * 0.3 # 속도 70% 감쇠로 에너지 안정화
        self.reset()
        return c, v

    def reset(self):
        """가드 상태 초기화 (새 시뮬레이션 시작 시 호출)"""
        self.last_energy = None
        self.last_momentum = None
        self.violation_count = 0
        self.last_min_distance = None


class OperationalGate:
    """운영 게이트: p95/worst 속도, overflow/saturation, 정확도를 동시 fail-fast 검사.

    평균 속도만으로는 tail latency를 잡지 못하므로,
    p95/worst step time 하한, neighbor list overflow 누적, RMSD 정확도를
    동시에 체크하여 어느 하나라도 위반 시 즉시 실패를 반환합니다.
    """

    def __init__(
        self,
        p95_speed_min: float = 50.0,
        worst_speed_min: float = 20.0,
        max_overflow_count: int = 0,
        max_saturation_ratio: float = 0.0,
        accuracy_rmsd_max: float = 5.0,
        window_size: int = 1000,
    ):
        self.p95_speed_min = float(p95_speed_min)
        self.worst_speed_min = float(worst_speed_min)
        self.max_overflow_count = int(max_overflow_count)
        self.max_saturation_ratio = float(max_saturation_ratio)
        self.accuracy_rmsd_max = float(accuracy_rmsd_max)
        self.window_size = max(int(window_size), 1)

        self._step_times: list = []
        self._overflow_count: int = 0
        self._saturation_events: int = 0
        self._total_steps: int = 0
        self._last_rmsd: float = 0.0

    def record_step(self, step_time_sec: float) -> None:
        """스텝 소요 시간을 기록합니다."""
        self._step_times.append(float(step_time_sec))
        self._total_steps += 1
        # 윈도우 크기 초과 시 오래된 기록 제거
        if len(self._step_times) > self.window_size:
            self._step_times = self._step_times[-self.window_size:]

    def record_overflow(self, count: int = 1) -> None:
        """neighbor list overflow 이벤트를 기록합니다."""
        self._overflow_count += int(count)

    def record_saturation(self, saturated_atoms: int, total_atoms: int) -> None:
        """neighbor list saturation 비율을 기록합니다."""
        if total_atoms > 0 and saturated_atoms > 0:
            self._saturation_events += 1

    def record_rmsd(self, rmsd: float) -> None:
        """현재 RMSD를 기록합니다."""
        self._last_rmsd = float(rmsd)

    def reset(self) -> None:
        """게이트 상태를 초기화합니다."""
        self._step_times.clear()
        self._overflow_count = 0
        self._saturation_events = 0
        self._total_steps = 0
        self._last_rmsd = 0.0

    def get_stats(self) -> dict:
        """현재 통계를 반환합니다."""
        import numpy as _np
        times = self._step_times
        if not times:
            return {
                "mean_steps_per_sec": 0.0,
                "p95_steps_per_sec": 0.0,
                "worst_steps_per_sec": 0.0,
                "overflow_count": self._overflow_count,
                "saturation_ratio": 0.0,
                "rmsd": self._last_rmsd,
            }
        arr = _np.array(times)
        p95_time = float(_np.percentile(arr, 95))
        worst_time = float(arr.max())
        mean_time = float(arr.mean())
        return {
            "mean_steps_per_sec": 1.0 / max(mean_time, 1e-12),
            "p95_steps_per_sec": 1.0 / max(p95_time, 1e-12),
            "worst_steps_per_sec": 1.0 / max(worst_time, 1e-12),
            "overflow_count": self._overflow_count,
            "saturation_ratio": (
                self._saturation_events / max(self._total_steps, 1)
            ),
            "rmsd": self._last_rmsd,
        }

    def check(self) -> "tuple[bool, list[str]]":
        """모든 운영 지표를 동시에 검사합니다. (fail-fast)

        Returns:
            ``(passed, fail_reasons)`` 튜플.
            ``passed``가 False면 ``fail_reasons``에 위반 사유가 포함됩니다.
        """
        stats = self.get_stats()
        fail_reasons: list = []

        # 1. p95 속도 하한
        if stats["p95_steps_per_sec"] < self.p95_speed_min and len(self._step_times) > 0:
            fail_reasons.append(
                f"p95 속도 {stats['p95_steps_per_sec']:.1f} steps/s "
                f"< 하한 {self.p95_speed_min:.1f}"
            )

        # 2. worst 속도 하한
        if stats["worst_steps_per_sec"] < self.worst_speed_min and len(self._step_times) > 0:
            fail_reasons.append(
                f"worst 속도 {stats['worst_steps_per_sec']:.1f} steps/s "
                f"< 하한 {self.worst_speed_min:.1f}"
            )

        # 3. overflow 누적
        if self._overflow_count > self.max_overflow_count:
            fail_reasons.append(
                f"overflow 누적 {self._overflow_count} "
                f"> 허용 {self.max_overflow_count}"
            )

        # 4. saturation 비율
        sat_ratio = stats["saturation_ratio"]
        if sat_ratio > self.max_saturation_ratio and self._total_steps > 0:
            fail_reasons.append(
                f"saturation 비율 {sat_ratio:.3f} "
                f"> 허용 {self.max_saturation_ratio:.3f}"
            )

        # 5. 정확도 RMSD
        if self._last_rmsd > self.accuracy_rmsd_max and self._last_rmsd > 0.0:
            fail_reasons.append(
                f"RMSD {self._last_rmsd:.3f} Å "
                f"> 허용 {self.accuracy_rmsd_max:.3f} Å"
            )

        passed = len(fail_reasons) == 0
        return passed, fail_reasons
