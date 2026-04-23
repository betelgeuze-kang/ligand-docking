import types

import torch

from core.rust_hip_backend import RustHipBackend, probe_rust_hip_backend


class _Device:
    def __init__(self, device_type):
        self.type = device_type


def test_probe_import_failure(monkeypatch):
    def _raise_import(_name):
        raise ImportError("missing")

    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", _raise_import)
    status = probe_rust_hip_backend(module_name="missing_mod", device=_Device("cuda"))
    assert status.enabled is False
    assert "module import failed" in status.reason


def test_probe_no_kernel_symbol(monkeypatch):
    fake_module = types.SimpleNamespace(__file__="/tmp/fake.so", hip_add=lambda a, b: a)
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    status = probe_rust_hip_backend(device=_Device("cuda"))
    assert status.enabled is False
    assert "no supported nonbonded HIP kernel symbol" in status.reason


def test_probe_cpu_device_disables_backend(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        hip_nonbonded_kernel=lambda c, n, p: (c, torch.zeros((c.shape[0], 1), device=c.device)),
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    status = probe_rust_hip_backend(device=_Device("cpu"))
    assert status.enabled is False
    assert "device.type is 'cpu'" in status.reason


def test_probe_enabled_when_all_conditions_met(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        hip_nonbonded_kernel=lambda c, n, p: (c, torch.zeros((c.shape[0], 1), device=c.device)),
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    status = probe_rust_hip_backend(device=_Device("cuda"))
    assert status.enabled is True
    assert status.kernel_name == "hip_nonbonded_kernel"


def test_probe_enabled_for_compute_nonbonded_gpu_symbol(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        compute_nonbonded_gpu=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    status = probe_rust_hip_backend(device=_Device("cuda"))
    assert status.enabled is True
    assert status.kernel_name == "compute_nonbonded_gpu"


def test_probe_prefers_compute_nonbonded_celllist_gpu_symbol(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        compute_nonbonded_gpu=lambda *args, **kwargs: None,
        compute_nonbonded_nblist_gpu=lambda *args, **kwargs: None,
        compute_nonbonded_celllist_gpu=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)
    monkeypatch.setenv("RUST_HIP_USE_FUSED_CELL", "1")

    status = probe_rust_hip_backend(device=_Device("cuda"))
    assert status.enabled is True
    assert status.kernel_name == "compute_nonbonded_celllist_gpu"


def test_probe_prefers_compute_nonbonded_nblist_gpu_symbol(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        compute_nonbonded_gpu=lambda *args, **kwargs: None,
        compute_nonbonded_nblist_gpu=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    status = probe_rust_hip_backend(device=_Device("cuda"))
    assert status.enabled is True
    assert status.kernel_name == "compute_nonbonded_nblist_gpu"


def test_backend_compute_returns_tensors(monkeypatch):
    def _kernel(coords, _nb_data, _params):
        return coords.clone(), torch.ones((coords.shape[0], 1), device=coords.device)

    fake_module = types.SimpleNamespace(__file__="/tmp/fake.so", hip_nonbonded_kernel=_kernel)
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    backend = RustHipBackend(device=_Device("cuda"))
    coords = torch.zeros((1, 5, 3), dtype=torch.float32)
    nb_data = (
        torch.zeros((1, 5, 4), dtype=torch.long),
        torch.ones((1, 5, 4), dtype=torch.float32),
        torch.ones((1, 5, 4), dtype=torch.float32),
    )
    f_core, pe = backend.compute_nonbonded(coords, nb_data, {"sigma": 3.8})
    assert isinstance(f_core, torch.Tensor)
    assert isinstance(pe, torch.Tensor)
    assert f_core.shape == coords.shape
    assert pe.shape == (1, 1)


def test_compute_nonbonded_gpu_requires_cuda_tensor(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        compute_nonbonded_gpu=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    backend = RustHipBackend(device=_Device("cuda"))
    coords = torch.zeros((1, 5, 3), dtype=torch.float32)  # CPU tensor
    nb_data = (
        torch.zeros((1, 5, 4), dtype=torch.long),
        torch.ones((1, 5, 4), dtype=torch.float32),
        torch.ones((1, 5, 4), dtype=torch.float32),
    )

    try:
        backend.compute_nonbonded(coords, nb_data, {"sigma": 3.8})
    except RuntimeError as exc:
        assert "requires CUDA tensor" in str(exc)
        return
    assert False, "Expected RuntimeError for CPU tensor in compute_nonbonded_gpu path"


def test_export_cached_buffers_dlpack(monkeypatch):
    fake_module = types.SimpleNamespace(
        __file__="/tmp/fake.so",
        compute_nonbonded_gpu=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("core.rust_hip_backend.importlib.import_module", lambda _name: fake_module)
    monkeypatch.setattr("core.rust_hip_backend._check_kfd_access", lambda: (True, None))
    monkeypatch.setattr("core.rust_hip_backend.torch.cuda.is_available", lambda: True)

    backend = RustHipBackend(device=_Device("cuda"))
    backend._cached_force = torch.randn(2, 4, 3, dtype=torch.float32)
    backend._cached_energy = torch.randn(2, 1, dtype=torch.float32)
    force_cap = backend.export_cached_force_dlpack()
    energy_cap = backend.export_cached_energy_dlpack()
    force_tensor = torch.utils.dlpack.from_dlpack(force_cap)
    energy_tensor = torch.utils.dlpack.from_dlpack(energy_cap)
    assert force_tensor.shape == (2, 4, 3)
    assert energy_tensor.shape == (2, 1)
