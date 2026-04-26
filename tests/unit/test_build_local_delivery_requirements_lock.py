import json
from pathlib import Path

from tools import build_local_delivery_requirements_lock as b


def _patch_workspace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "RUNS", tmp_path / "runs")


def test_include_resolution_and_installed_version_mapping(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    (tmp_path / "requirements.txt").write_text(
        "\n".join(
            [
                "# base requirements",
                "numpy",
                "-r requirements-dev.txt",
                "uvicorn[standard]>=0.29",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text("pytest==8.1.1\n", encoding="utf-8")

    payload = b.build_payload(
        ["requirements.txt"],
        installed_versions={"numpy": "2.0.0", "pytest": "8.2.0", "uvicorn": "0.30.0"},
        generated_at="2026-04-25T00:00:00+09:00",
    )

    assert [Path(row["path"]).name for row in payload["requirement_files"]] == [
        "requirements.txt",
        "requirements-dev.txt",
    ]
    assert payload["summary"]["declared_count"] == 3
    assert payload["summary"]["installed_count"] == 3
    assert payload["summary"]["missing_count"] == 0
    assert payload["summary"]["installed_distribution_count"] == 3
    assert payload["summary"]["python_version"]
    assert len(payload["summary"]["normalized_lock_text_sha256"]) == 64
    assert payload["lock_lines"] == [
        "numpy==2.0.0",
        "pytest==8.2.0",
        "uvicorn[standard]==0.30.0",
    ]
    assert [row["normalized_name"] for row in payload["frozen_distributions"]] == ["numpy", "pytest", "uvicorn"]


def test_missing_package_handling_and_default_non_enforcing_exit(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("present-package\nmissing-package\n", encoding="utf-8")

    payload = b.build_payload([req], installed_versions={"present-package": "1.2.3"})

    assert payload["summary"]["declared_count"] == 2
    assert payload["summary"]["installed_count"] == 1
    assert payload["summary"]["missing_count"] == 1
    assert payload["lock_lines"] == ["present-package==1.2.3"]
    assert [row["display_name"] for row in payload["missing_packages"]] == ["missing-package"]
    assert payload["summary"]["missing_package_install_targets"] == ["missing-package"]
    assert "missing-package" in payload["summary"]["next_required_step"]
    assert payload["summary"]["status_line"].startswith("incomplete:")

    assert (
        b.main(
            [
                "--requirements-file",
                str(req),
                "--out-json",
                str(tmp_path / "out.json"),
                "--out-md",
                str(tmp_path / "out.md"),
                "--out-txt",
                str(tmp_path / "out.txt"),
            ]
        )
        == 0
    )


def test_loose_source_requirements_are_recorded(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text(
        "\n".join(
            [
                "fastapi",
                "git+https://example.invalid/custom/project.git#egg=custom-project",
                "./local-package",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = b.build_payload([req], installed_versions={"fastapi": "0.115.0"})

    assert payload["summary"]["declared_count"] == 1
    assert payload["summary"]["loose_source_requirement_count"] == 2
    assert payload["lock_lines"] == ["fastapi==0.115.0"]
    assert [row["raw"] for row in payload["loose_source_requirements"]] == [
        "git+https://example.invalid/custom/project.git#egg=custom-project",
        "./local-package",
    ]
    assert payload["summary"]["loose_source_requirements"] == [
        "git+https://example.invalid/custom/project.git#egg=custom-project",
        "./local-package",
    ]


def test_full_line_comments_are_not_recorded_as_loose_sources(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("# API and client\nnumpy\n  # Optional modules\n", encoding="utf-8")

    payload = b.build_payload([req], installed_versions={"numpy": "2.0.0"})

    assert payload["summary"]["declared_count"] == 1
    assert payload["summary"]["loose_source_requirement_count"] == 0
    assert payload["loose_source_requirements"] == []


def test_unpinned_pin_suggestions_are_actionable(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("uvicorn[standard]>=0.29\n", encoding="utf-8")

    payload = b.build_payload([req], installed_versions={"uvicorn": "0.30.0"})

    assert payload["summary"]["unpinned_requirement_names"] == ["uvicorn[standard]"]
    assert payload["summary"]["unpinned_pin_suggestions"] == [
        {
            "name": "uvicorn[standard]",
            "source": "requirements.txt:1",
            "current_requirement": "uvicorn[standard]>=0.29",
            "installed_version": "0.30.0",
            "suggested_requirement": "uvicorn[standard]==0.30.0",
        }
    ]


def test_optional_profiles_are_reported_without_blocking_delivery_lock(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    api_req = tmp_path / "requirements-api.txt"
    opt_req = tmp_path / "requirements-optional.txt"
    req.write_text("numpy\n", encoding="utf-8")
    api_req.write_text("fastapi\nuvicorn[standard]\n", encoding="utf-8")
    opt_req.write_text("GPUtil\n", encoding="utf-8")

    payload = b.build_payload(
        [req],
        optional_requirement_profiles={"api": [api_req], "optional": [opt_req]},
        installed_versions={"numpy": "2.0.0", "uvicorn": "0.30.0"},
    )

    assert payload["summary"]["requirements_lock_complete"] is True
    assert payload["summary"]["missing_count"] == 0
    assert payload["summary"]["optional_missing_count"] == 2
    assert payload["summary"]["optional_deferred_install_targets"] == ["fastapi", "GPUtil"]
    assert payload["lock_lines"] == ["numpy==2.0.0"]
    assert payload["optional_profiles"]["api"]["missing_package_install_targets"] == ["fastapi"]
    assert payload["optional_profiles"]["api"]["lock_lines"] == ["uvicorn[standard]==0.30.0"]
    assert {row["display_name"] for row in payload["optional_missing_packages"]} == {"fastapi", "GPUtil"}
    assert all(row["blocking"] is False for row in payload["optional_missing_packages"])


def test_output_writing(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("pandas\nmissing-pkg\n", encoding="utf-8")
    out_json = tmp_path / "runs" / "lock.json"
    out_md = tmp_path / "runs" / "lock.md"
    out_txt = tmp_path / "runs" / "lock.txt"

    payload = b.build_payload([req], installed_versions={"pandas": "2.2.2"}, generated_at="fixed")
    b.write_outputs(payload, out_json=out_json, out_md=out_md, out_txt=out_txt)

    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["generated_at"] == "fixed"
    assert written["summary"]["lock_line_count"] == 1
    assert "# Local Delivery Requirements Lock" in out_md.read_text(encoding="utf-8")
    lock_text = out_txt.read_text(encoding="utf-8")
    assert "pandas==2.2.2" in lock_text
    assert "# MISSING missing-pkg" in lock_text
    assert "# INPUT pandas" in lock_text


def test_enforce_complete_exits_nonzero_for_missing_package(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("definitely-missing-package\n", encoding="utf-8")

    def missing_version(name):
        raise b.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(b.importlib.metadata, "version", missing_version)

    rc = b.main(
        [
            "--requirements-file",
            str(req),
            "--out-json",
            str(tmp_path / "lock.json"),
            "--out-md",
            str(tmp_path / "lock.md"),
            "--out-txt",
            str(tmp_path / "lock.txt"),
            "--enforce-complete",
        ]
    )

    assert rc == 1
