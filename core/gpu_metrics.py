import json
import os
import re
import subprocess
import threading
import time
from typing import Dict, Optional

import torch

try:
    import GPUtil
except ImportError:  # pragma: no cover - optional dependency
    GPUtil = None


def _extract_number(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", text)
    if not match:
        return None
    return float(match.group(0))


def _sample_rocm_smi() -> Optional[Dict[str, float]]:
    cmd = os.environ.get("ROCM_SMI_CMD", "rocm-smi")
    try:
        proc = subprocess.run(
            [cmd, "--showuse", "--showmemuse", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        payload = json.loads(proc.stdout.strip() or "{}")
        card_keys = sorted(k for k in payload.keys() if str(k).lower().startswith("card"))
        if not card_keys:
            return None
        card = payload[card_keys[0]]
        gpu_use = _extract_number(card.get("GPU use (%)", card.get("GPU use")))
        mem_use = _extract_number(
            card.get("GPU memory use (%)", card.get("VRAM use (%)", card.get("GPU memory use")))
        )
        if gpu_use is None and mem_use is None:
            return None
        return {
            "util_percent": float(gpu_use or 0.0),
            "mem_util_percent": float(mem_use or 0.0),
            "backend": "rocm-smi",
            "ok": True,
        }
    except Exception:
        return None


def _sample_gputil() -> Optional[Dict[str, float]]:
    if GPUtil is None:
        return None
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return None
        gpu = gpus[0]
        return {
            "util_percent": float(gpu.load * 100.0),
            "mem_util_percent": float(gpu.memoryUtil * 100.0),
            "backend": "gputil",
            "ok": True,
        }
    except Exception:
        return None


def _sample_torch_memory() -> Optional[Dict[str, float]]:
    if not torch.cuda.is_available():
        return None
    try:
        device_idx = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device_idx)
        total_mem = float(getattr(props, "total_memory", 0))
        alloc = float(torch.cuda.memory_allocated(device_idx))
        mem_util = (alloc / total_mem * 100.0) if total_mem > 0 else 0.0
        return {
            "util_percent": 0.0,
            "mem_util_percent": float(mem_util),
            "backend": "torch-memory",
            "ok": True,
        }
    except Exception:
        return None


def sample_gpu_metrics() -> Dict[str, float]:
    for sampler in (_sample_rocm_smi, _sample_gputil, _sample_torch_memory):
        metrics = sampler()
        if metrics is not None:
            return metrics
    return {
        "util_percent": 0.0,
        "mem_util_percent": 0.0,
        "backend": "none",
        "ok": False,
    }


class AsyncGpuSampler:
    def __init__(self, interval_sec: float = 0.25):
        self.interval_sec = max(float(interval_sec), 0.05)
        self._stop = threading.Event()
        self._thread = None
        self._util_samples = []
        self._mem_samples = []
        self._backend_samples = []

    def _append_sample(self):
        m = sample_gpu_metrics()
        self._util_samples.append(float(m.get("util_percent", 0.0)))
        self._mem_samples.append(float(m.get("mem_util_percent", 0.0)))
        self._backend_samples.append(str(m.get("backend", "none")))

    def _worker(self):
        while not self._stop.is_set():
            self._append_sample()
            time.sleep(self.interval_sec)

    def start(self):
        if self._thread is not None:
            return
        self._append_sample()
        self._thread = threading.Thread(target=self._worker, name="gpu-metrics-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> Dict[str, float]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._append_sample()
        if self._backend_samples:
            counts = {}
            for name in self._backend_samples:
                counts[name] = counts.get(name, 0) + 1
            backend = max(counts, key=counts.get)
        else:
            backend = "none"
        return {
            "avg_util_percent": (sum(self._util_samples) / len(self._util_samples)) if self._util_samples else 0.0,
            "avg_mem_util_percent": (sum(self._mem_samples) / len(self._mem_samples)) if self._mem_samples else 0.0,
            "backend": backend,
            "num_samples": len(self._util_samples),
        }
