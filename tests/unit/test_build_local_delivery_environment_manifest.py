from __future__ import annotations

import json

from tools import build_local_delivery_environment_manifest as mod


class _FakeDistribution:
    def __init__(self, name: str, version: str) -> None:
        self.metadata = {"Name": name}
        self.version = version


def _complete_requirements_lock(tmp_path=None) -> dict:
    base_path = str(tmp_path) if tmp_path is not None else "runs"
    return {
        "json_path": f"{base_path}/requirements_lock.json",
        "md_path": f"{base_path}/requirements_lock.md",
        "txt_path": f"{base_path}/requirements_lock.txt",
        "json_present": True,
        "md_present": True,
        "txt_present": True,
        "txt_sha256": "abc123",
        "summary": {
            "missing_count": 0,
            "loose_source_requirement_count": 0,
            "missing_input_file_count": 0,
            "status_line": "complete: lock_lines=2",
            "next_required_step": "Use the generated txt lock artifact for local delivery reproduction.",
        },
    }


def test_collect_requirements_snapshot_resolves_includes_and_versions(tmp_path, monkeypatch) -> None:
    requirements_txt = tmp_path / "requirements.txt"
    requirements_dev_txt = tmp_path / "requirements-dev.txt"
    requirements_txt.write_text("numpy\nuvicorn[standard]\n", encoding="utf-8")
    requirements_dev_txt.write_text("-r requirements.txt\npytest\nnumpy\n", encoding="utf-8")

    monkeypatch.setattr(
        mod.importlib.metadata,
        "distributions",
        lambda: [
            _FakeDistribution("numpy", "2.1.0"),
            _FakeDistribution("uvicorn", "0.30.6"),
            _FakeDistribution("pytest", "8.3.5"),
        ],
    )

    snapshot = mod._collect_requirements_snapshot([requirements_dev_txt])

    assert snapshot["declared_requirement_count"] == 3
    assert snapshot["installed_requirement_count"] == 3
    assert snapshot["missing_requirement_count"] == 0
    assert snapshot["pinned_requirement_count"] == 0
    assert snapshot["unpinned_requirement_count"] == 3
    assert len(snapshot["resolved_source_files"]) == 2
    rows = {row["name"]: row for row in snapshot["declared"]}
    assert rows["numpy"]["installed_version"] == "2.1.0"
    assert rows["uvicorn"]["requirement"] == "uvicorn[standard]"
    assert rows["pytest"]["source_file"] == str(requirements_dev_txt)


def test_build_payload_prioritizes_missing_requirements_in_next_step() -> None:
    args = mod.build_parser().parse_args(["--manifest-label", "delivery baseline"])

    payload = mod.build_payload(
        args,
        generated_at_local="2026-04-23T12:30:00+09:00",
        python_runtime={
            "executable": "/usr/bin/python3",
            "version": "3.12.2",
            "implementation": "CPython",
            "prefix": "/venv",
            "base_prefix": "/usr",
            "virtual_env_active": True,
        },
        platform_info={
            "platform": "Linux-6.8.0-x86_64-with-glibc2.39",
            "system": "Linux",
            "release": "6.8.0",
            "version": "#1 SMP",
            "machine": "x86_64",
            "processor": "x86_64",
        },
        accelerator_info={
            "detected_stack": "cuda_env_configured",
            "present_env": {"CUDA_VISIBLE_DEVICES": "0"},
            "status_line": "stack=cuda_env_configured | env=CUDA_VISIBLE_DEVICES",
            "command_probes": {},
        },
        git_info={
            "available": True,
            "commit": "abc123def456",
            "short_commit": "abc123d",
            "branch": "main",
            "dirty": True,
            "status_line": "git=available | commit=abc123d | branch=main | dirty=True",
        },
        requirements_snapshot={
            "source_files": ["requirements.txt", "requirements-dev.txt"],
            "declared_requirement_count": 3,
            "installed_requirement_count": 2,
            "missing_requirement_count": 1,
            "pinned_requirement_count": 1,
            "unpinned_requirement_count": 2,
            "missing_packages": ["torch"],
            "unpinned_packages": ["numpy", "pytest"],
            "declared": [],
        },
        requirements_lock=_complete_requirements_lock(),
    )

    summary = payload["summary"]
    assert summary["manifest_label"] == "delivery_baseline"
    assert summary["accelerator_env_var_count"] == 1
    assert "torch" in summary["next_required_step"]
    assert "run_local_delivery_preflight.py" in summary["next_required_step"]
    assert "python=3.12.2" in summary["status_line"]
    assert "git=abc123d:dirty" in summary["status_line"]
    assert summary["torch_blas_prefer_hipblaslt"] == ""


def test_build_payload_surfaces_incomplete_lock_action_items() -> None:
    args = mod.build_parser().parse_args(["--manifest-label", "delivery baseline"])
    incomplete_lock = _complete_requirements_lock()
    incomplete_lock["summary"] = {
        **incomplete_lock["summary"],
        "missing_count": 2,
        "loose_source_requirement_count": 1,
        "status_line": "incomplete: installed=1/3 missing=2 loose_sources=1 missing_files=0",
        "missing_package_install_targets": ["fastapi", "uvicorn[standard]"],
        "loose_source_requirements": ["./local-package"],
        "unpinned_count": 1,
        "unpinned_pin_suggestions": [
            {
                "current_requirement": "numpy",
                "installed_version": "2.1.0",
                "suggested_requirement": "numpy==2.1.0",
                "source": "requirements.txt:1",
            }
        ],
    }

    payload = mod.build_payload(
        args,
        generated_at_local="2026-04-23T12:30:00+09:00",
        python_runtime={"executable": "/usr/bin/python3", "version": "3.12.2"},
        platform_info={"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
        accelerator_info={"detected_stack": "unspecified", "present_env": {}, "command_probes": {}},
        git_info={"available": True, "commit": "abc", "short_commit": "abc", "dirty": False},
        requirements_snapshot={
            "source_files": ["requirements.txt"],
            "declared_requirement_count": 3,
            "installed_requirement_count": 1,
            "missing_requirement_count": 2,
            "pinned_requirement_count": 0,
            "unpinned_requirement_count": 1,
            "missing_packages": ["fastapi", "uvicorn"],
            "unpinned_packages": ["numpy"],
            "declared": [],
        },
        requirements_lock=incomplete_lock,
    )

    summary = payload["summary"]
    assert summary["requirements_lock_complete"] is False
    assert summary["requirements_lock_state"] == "incomplete"
    assert summary["requirements_lock_missing_package_install_targets"] == ["fastapi", "uvicorn[standard]"]
    assert summary["requirements_lock_loose_source_requirements"] == ["./local-package"]
    assert "fastapi" in summary["next_required_step"]
    assert "./local-package" in summary["next_required_step"]


def test_build_payload_treats_optional_lock_missing_as_deferred() -> None:
    args = mod.build_parser().parse_args(["--manifest-label", "delivery baseline"])
    lock = _complete_requirements_lock()
    lock["summary"] = {
        **lock["summary"],
        "requirements_lock_complete": True,
        "optional_missing_count": 2,
        "optional_deferred_install_targets": ["fastapi", "GPUtil"],
        "optional_profiles": {
            "api": {
                "missing_count": 1,
                "missing_package_install_targets": ["fastapi"],
                "delivery_blocking": False,
            }
        },
    }

    payload = mod.build_payload(
        args,
        generated_at_local="2026-04-23T12:30:00+09:00",
        python_runtime={"executable": "/usr/bin/python3", "version": "3.12.2"},
        platform_info={"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
        accelerator_info={"detected_stack": "unspecified", "present_env": {}, "command_probes": {}},
        git_info={"available": True, "commit": "abc", "short_commit": "abc", "dirty": False},
        requirements_snapshot={
            "source_files": ["requirements.txt"],
            "declared_requirement_count": 1,
            "installed_requirement_count": 1,
            "missing_requirement_count": 0,
            "pinned_requirement_count": 0,
            "unpinned_requirement_count": 1,
            "missing_packages": [],
            "unpinned_packages": ["numpy"],
            "declared": [],
        },
        requirements_lock=lock,
    )

    summary = payload["summary"]
    assert summary["requirements_lock_complete"] is True
    assert summary["requirements_lock_state"] == "complete"
    assert summary["requirements_lock_optional_missing_count"] == 2
    assert summary["requirements_lock_optional_deferred_install_targets"] == ["fastapi", "GPUtil"]
    assert "Install or reconcile" not in summary["next_required_step"]


def test_collect_accelerator_info_records_torch_blas_prefer_hipblaslt() -> None:
    accelerator_info = mod._collect_accelerator_info(
        env={
            "ROCM_HOME": "/opt/rocm",
            "TORCH_BLAS_PREFER_HIPBLASLT": "0",
        },
        probe_commands=False,
    )

    assert accelerator_info["detected_stack"] == "rocm_env_configured"
    assert accelerator_info["present_env"]["TORCH_BLAS_PREFER_HIPBLASLT"] == "0"
    assert "TORCH_BLAS_PREFER_HIPBLASLT" in accelerator_info["status_line"]


def test_collect_accelerator_info_records_torch_blas_prefer_hipblaslt_without_overclassifying_stack() -> None:
    accelerator_info = mod._collect_accelerator_info(
        env={"TORCH_BLAS_PREFER_HIPBLASLT": "1"},
        probe_commands=False,
    )

    assert accelerator_info["detected_stack"] == "accelerator_env_present"
    assert accelerator_info["present_env"] == {"TORCH_BLAS_PREFER_HIPBLASLT": "1"}
    assert "stack=accelerator_env_present" in accelerator_info["status_line"]


def test_build_payload_exposes_torch_blas_prefer_hipblaslt_summary() -> None:
    args = mod.build_parser().parse_args(["--manifest-label", "delivery baseline"])

    payload = mod.build_payload(
        args,
        generated_at_local="2026-04-23T12:30:00+09:00",
        python_runtime={
            "executable": "/usr/bin/python3",
            "version": "3.12.2",
        },
        platform_info={
            "platform": "Linux-6.8.0-x86_64-with-glibc2.39",
            "system": "Linux",
            "release": "6.8.0",
            "machine": "x86_64",
        },
        accelerator_info={
            "detected_stack": "rocm_env_configured",
            "present_env": {
                "ROCM_HOME": "/opt/rocm",
                "TORCH_BLAS_PREFER_HIPBLASLT": "0",
            },
            "status_line": "stack=rocm_env_configured | env=ROCM_HOME,TORCH_BLAS_PREFER_HIPBLASLT",
            "command_probes": {},
        },
        git_info={
            "available": False,
            "commit": "",
            "short_commit": "",
            "dirty": False,
        },
        requirements_snapshot={
            "source_files": [],
            "declared_requirement_count": 0,
            "installed_requirement_count": 0,
            "missing_requirement_count": 0,
            "pinned_requirement_count": 0,
            "unpinned_requirement_count": 0,
            "missing_packages": [],
            "unpinned_packages": [],
            "declared": [],
        },
        requirements_lock=_complete_requirements_lock(),
    )

    summary = payload["summary"]
    assert summary["accelerator_env_var_count"] == 2
    assert summary["torch_blas_prefer_hipblaslt"] == "0"


def test_main_writes_json_and_markdown(monkeypatch, tmp_path) -> None:
    out_json = tmp_path / "environment_manifest.json"
    out_md = tmp_path / "environment_manifest.md"
    lock_json = tmp_path / "requirements_lock.json"
    lock_md = tmp_path / "requirements_lock.md"
    lock_txt = tmp_path / "requirements_lock.txt"
    lock_json.write_text(
        json.dumps({"summary": _complete_requirements_lock(tmp_path)["summary"]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lock_md.write_text("# lock\n", encoding="utf-8")
    lock_txt.write_text("numpy==2.1.0\npytest==8.3.5\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_now_local", lambda: "2026-04-23T13:00:00+09:00")
    monkeypatch.setattr(
        mod,
        "_collect_python_runtime",
        lambda: {
            "executable": "/usr/bin/python3",
            "version": "3.11.9",
            "implementation": "CPython",
            "prefix": "/venv",
            "base_prefix": "/usr",
            "virtual_env_active": True,
            "virtual_env": "/venv",
            "conda_prefix": "",
            "pythonpath": "",
        },
    )
    monkeypatch.setattr(
        mod,
        "_collect_platform_info",
        lambda: {
            "platform": "Linux-6.8.0-x86_64-with-glibc2.39",
            "system": "Linux",
            "release": "6.8.0",
            "version": "#1 SMP",
            "machine": "x86_64",
            "processor": "x86_64",
        },
    )
    monkeypatch.setenv("ROCM_HOME", "/opt/rocm")
    monkeypatch.setenv("TORCH_BLAS_PREFER_HIPBLASLT", "0")
    monkeypatch.setattr(
        mod,
        "_collect_git_info",
        lambda: {
            "available": True,
            "commit": "feedfacecafebeef",
            "short_commit": "feedfac",
            "branch": "feature/local-delivery",
            "dirty": False,
            "repository_root": "/repo",
            "status_line": "git=available | commit=feedfac | branch=feature/local-delivery | dirty=False",
        },
    )
    monkeypatch.setattr(
        mod,
        "_collect_requirements_snapshot",
        lambda files: {
            "source_files": [str(item) for item in files],
            "resolved_source_files": [str(item) for item in files],
            "missing_source_files": [],
            "declared_requirement_count": 2,
            "installed_requirement_count": 2,
            "missing_requirement_count": 0,
            "pinned_requirement_count": 2,
            "unpinned_requirement_count": 0,
            "missing_packages": [],
            "unpinned_packages": [],
            "resolution_source": "importlib.metadata",
            "status_line": "2/2 declared requirements installed | 0 unpinned",
            "declared": [
                {
                    "name": "numpy",
                    "requirement": "numpy==2.1.0",
                    "installed_version": "2.1.0",
                    "is_pinned": True,
                    "source_file": "requirements.txt",
                },
                {
                    "name": "pytest",
                    "requirement": "pytest==8.3.5",
                    "installed_version": "8.3.5",
                    "is_pinned": True,
                    "source_file": "requirements-dev.txt",
                },
            ],
        },
    )

    mod.main(
        [
            "--manifest-label",
            "delivery-baseline",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--requirements-files",
            "requirements.txt",
            "requirements-dev.txt",
            "--requirements-lock-json",
            str(lock_json),
            "--requirements-lock-md",
            str(lock_md),
            "--requirements-lock-txt",
            str(lock_txt),
            "--no-probe-accelerator-commands",
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["manifest_label"] == "delivery-baseline"
    assert payload["summary"]["git_short_commit"] == "feedfac"
    assert payload["summary"]["accelerator_stack"] == "rocm_env_configured"
    assert payload["summary"]["accelerator_env_var_count"] >= 2
    assert payload["summary"]["torch_blas_prefer_hipblaslt"] == "0"
    assert payload["accelerator_runtime"]["present_env"]["TORCH_BLAS_PREFER_HIPBLASLT"] == "0"
    assert payload["summary"]["missing_requirement_count"] == 0
    assert payload["summary"]["requirements_lock_complete"] is True
    assert payload["summary"]["requirements_lock_txt_sha256"]
    assert "environment frozen" not in payload["summary"]["next_required_step"]
    md_text = out_md.read_text(encoding="utf-8")
    assert "# Local Delivery Environment Manifest" in md_text
    assert "## Requirements Lock" in md_text
    assert "ROCM_HOME" in md_text
    assert "torch_blas_prefer_hipblaslt" in md_text
    assert "TORCH_BLAS_PREFER_HIPBLASLT" in md_text
    assert "numpy==2.1.0" in md_text
