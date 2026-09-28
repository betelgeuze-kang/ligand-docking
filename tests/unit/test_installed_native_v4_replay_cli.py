"""The installed v4 commands reject incompatible runtimes before intake work."""

import importlib.metadata
import sys

import pytest

from betelgeuze_product import installed_native_v4_replay_cli as replay


def test_replay_rejects_unsupported_python_before_dependency_lookup(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 11, 0))

    def unexpected_lookup(_name):
        pytest.fail("dependency lookup occurred before Python version check")

    monkeypatch.setattr(importlib.metadata, "version", unexpected_lookup)
    with pytest.raises(RuntimeError, match="native_v4_replay_requires_python_3_10"):
        replay.source_main([])


def test_replay_rejects_missing_rdkit_distribution_before_source_import(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 12))

    def missing(_name):
        raise importlib.metadata.PackageNotFoundError("rdkit-pypi")

    monkeypatch.setattr(importlib.metadata, "version", missing)
    with pytest.raises(RuntimeError, match="native_v4_replay_requires_rdkit_pypi_2022_9_5"):
        replay.source_main([])


def test_replay_rejects_incompatible_rdkit_runtime_before_comparison(monkeypatch):
    from rdkit import rdBase

    monkeypatch.setattr(sys, "version_info", (3, 10, 12))
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2022.9.5")
    monkeypatch.setattr(rdBase, "rdkitVersion", "2026.03.6")
    with pytest.raises(RuntimeError, match="native_v4_replay_requires_rdkit_2022_09_5"):
        replay.comparison_main([])
