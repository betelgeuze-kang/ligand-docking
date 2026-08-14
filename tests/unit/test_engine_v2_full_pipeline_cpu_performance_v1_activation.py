from __future__ import annotations

import hashlib
import importlib.machinery
import json
from pathlib import Path
import types

import pytest

from betelgeuze_engine_v2.docking import (
    full_pipeline_cpu_performance_v1_activation as activation,
)


def _module(name: str, *, origin: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name=name, loader=None)
    module.__spec__.origin = origin
    return module


def test_stdlib_import_closure_is_rederivable() -> None:
    modules = {
        "synthetic_builtin": _module("synthetic_builtin", origin="built-in"),
        "synthetic_frozen": _module("synthetic_frozen", origin="frozen"),
    }

    first = activation.derive_stdlib_import_closure(modules)
    second = activation.derive_stdlib_import_closure(modules)

    assert first == second
    assert first == {
        "schema_id": activation.STDLIB_CLOSURE_SCHEMA_ID,
        "module_count": 2,
        "file_backed_module_count": 0,
        "file_backed_total_bytes": 0,
        "rows_sha256": activation.manifest_rows_sha256(first["rows"]),
        "rows": [
            {"module": "synthetic_builtin", "origin": "built-in"},
            {"module": "synthetic_frozen", "origin": "frozen"},
        ],
    }


def test_dynamic_library_closure_is_rederivable(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    package = site_packages / "native"
    package.mkdir(parents=True)
    library = package / "native_fixture.so"
    library.write_bytes(b"exact-native-fixture")
    library.chmod(0o600)
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        f"1000-2000 r-xp 00000000 00:00 1 {library}\n",
        encoding="ascii",
    )
    process_maps.chmod(0o600)

    observed = activation.derive_dynamic_library_closure(
        site_packages=site_packages,
        process_maps_path=process_maps,
    )

    expected_row = {
        "path": "qualified_site_packages/native/native_fixture.so",
        "sha256": hashlib.sha256(b"exact-native-fixture").hexdigest(),
        "size_bytes": len(b"exact-native-fixture"),
    }
    assert observed == {
        "schema_id": activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        "library_count": 1,
        "total_bytes": len(b"exact-native-fixture"),
        "rows_sha256": activation.manifest_rows_sha256([expected_row]),
        "rows": [expected_row],
    }


def test_dynamic_library_closure_rejects_unavailable_mapping(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        "1000-2000 r-xp 00000000 00:00 1 /absent/native_fixture.so\n",
        encoding="ascii",
    )

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="mapped dynamic library is unavailable",
    ):
        activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            process_maps_path=process_maps,
        )


def test_exact_closure_rejects_semantic_drift() -> None:
    expected = {
        "schema_id": activation.STDLIB_CLOSURE_SCHEMA_ID,
        "rows": [{"module": "sys", "origin": "built-in"}],
    }
    changed = json.loads(json.dumps(expected))
    changed["rows"][0]["origin"] = "frozen"

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="standard-library import closure changed",
    ):
        activation.require_exact_closure(
            changed,
            expected,
            name="standard-library import closure",
        )


def test_preflight_evidence_remains_non_consuming() -> None:
    evidence = activation.ActivationPreflightEvidenceV1(
        activation_sha256="a" * 64,
        profile_sha256="b" * 64,
        stdlib_import_closure_manifest_sha256="c" * 64,
        dynamic_library_closure_manifest_sha256="d" * 64,
        host_preflight={"qualified": True, "blockers": []},
        blockers=(),
    ).to_dict()

    assert evidence["ready"] is True
    assert evidence["imports_performed"] is True
    assert evidence["native_extension_initialized"] is True
    for key in (
        "performance_measurement_performed",
        "qualification_attempt_created",
        "qualification_consumed",
        "reservation_created",
        "molecular_execution_performed",
        "public_benchmark_performed",
        "hip_device_execution_performed",
        "product_action_performed",
    ):
        assert evidence[key] is False
    assert evidence["all_authority_false"] is True
