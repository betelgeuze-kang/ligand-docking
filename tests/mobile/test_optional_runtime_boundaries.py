from __future__ import annotations

import pytest


@pytest.mark.requires_torch
def test_torch_runtime_is_an_explicit_optional_lane() -> None:
    pytest.importorskip(
        "torch",
        reason="PyTorch execution is intentionally excluded from mobile-lite validation.",
    )


@pytest.mark.requires_rdkit
def test_rdkit_runtime_is_an_explicit_optional_lane() -> None:
    pytest.importorskip(
        "rdkit",
        reason="RDKit chemistry execution is intentionally excluded from mobile-lite validation.",
    )


@pytest.mark.requires_openmm
def test_openmm_runtime_is_an_explicit_optional_lane() -> None:
    pytest.importorskip(
        "openmm",
        reason="OpenMM execution is intentionally excluded from mobile-lite validation.",
    )


@pytest.mark.requires_h5py
def test_h5py_runtime_is_an_explicit_optional_lane() -> None:
    pytest.importorskip(
        "h5py",
        reason="HDF5 artifact execution is intentionally excluded from mobile-lite validation.",
    )
