# monitoring/performance_monitor.py

import psutil
import time
import logging
from core.config import config
from core.gpu_metrics import sample_gpu_metrics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    시뮬레이션 루프에서 주기적으로 성능 및 리소스 사용량을 모니터링합니다.
    """
    def __init__(self, log_interval_steps=1000, log_interval_seconds=10):
        self.log_interval_steps = log_interval_steps
        self.log_interval_seconds = log_interval_seconds
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.last_log_step = 0

        # Initialize GPU monitoring backend (ROCm-aware).
        self.gpu_available = True
        self._step_times: list = []
        self._max_step_times: int = 10000
        self._neighbor_saturation_total: int = 0

    def log_metrics(self, current_step, physics_guard_status=None, governance_status=None, **kwargs):
        """
        현재 스텝에서 성능 및 리소스 지표를 로깅합니다.
        Args:
            current_step (int): 현재 시뮬레이션 스텝
            physics_guard_status (dict): PhysicsGuard의 상태 (e.g., violation_count)
            governance_status (dict): RuntimeGovernanceLayer의 상태 (e.g., intervention_rate)
        """
        current_time = time.time()
        elapsed_since_start = current_time - self.start_time
        elapsed_since_last_log = current_time - self.last_log_time
        steps_since_last_log = current_step - self.last_log_step

        # Calculate throughput
        if elapsed_since_last_log > 0:
            steps_per_sec = steps_since_last_log / elapsed_since_last_log
        else:
            steps_per_sec = 0.0

        # Log every N steps or every M seconds
        if (current_step % self.log_interval_steps == 0) or (elapsed_since_last_log >= self.log_interval_seconds):
            # System CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent
            memory_used_gb = memory_info.used / (1024**3)

            # GPU
            gpu_metrics = sample_gpu_metrics()
            gpu_util = float(gpu_metrics.get("util_percent", 0.0))
            gpu_mem_util = float(gpu_metrics.get("mem_util_percent", 0.0))
            gpu_backend = str(gpu_metrics.get("backend", "none"))

            # Physics Guard / Governance
            violations = physics_guard_status.get('violation_count', 0) if physics_guard_status else 0
            int_rate = governance_status.get('intervention_rate', 0.0) if governance_status else 0.0

            # Step time 수집 및 tail latency 통계
            self._step_times.append(elapsed_since_last)
            if len(self._step_times) > self._max_step_times:
                self._step_times = self._step_times[-self._max_step_times:]
            import numpy as _np
            _arr = _np.array(self._step_times)
            p95_step_time = float(_np.percentile(_arr, 95))
            worst_step_time = float(_arr.max())
            mean_step_time = float(_arr.mean())

            # Neighbor saturation 누적
            nb_sat = kwargs.get("neighbor_saturation_count", 0)
            self._neighbor_saturation_total += int(nb_sat)

            # Log metrics
            logger.info(
                f"Step: {current_step:8d}, "
                f"Time: {elapsed_since_start:.2f}s, "
                f"Throughput: {steps_per_sec:.2f} steps/sec, "
                f"p95: {1.0/max(p95_step_time,1e-9):.1f} steps/s, "
                f"worst: {1.0/max(worst_step_time,1e-9):.1f} steps/s, "
                f"CPU: {cpu_percent:.1f}%, "
                f"Mem: {memory_percent:.1f}% ({memory_used_gb:.2f}GB), "
                f"GPU Util: {gpu_util:.1f}%, "
                f"GPU Mem: {gpu_mem_util:.1f}% ({gpu_backend}), "
                f"Violations: {violations}, "
                f"AI Int Rate: {int_rate:.3f}, "
                f"NB Sat: {self._neighbor_saturation_total}"
            )

            self.last_log_time = current_time
            self.last_log_step = current_step

    def reset_timer(self):
        """Monitor timer를 리셋합니다."""
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.last_log_step = 0
        self._step_times = []
        self._neighbor_saturation_total = 0
