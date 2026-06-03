from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_commercial_independence_gate as mod


def test_build_product_commercial_independence_gate_tool_writes_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "api").mkdir()
    (root / "api" / "product.py").write_text("# product API\n", encoding="utf-8")
    (root / "betelgeuze_product").mkdir()
    (root / "betelgeuze_product" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_product" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cleanup").mkdir()
    (root / "betelgeuze_cleanup" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cleanup" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        """
[project]
name = "betelgeuze-md-product"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
betelgeuze-product = "betelgeuze_product.cli:main"
betelgeuze-cameo = "betelgeuze_cameo.cli:main"
betelgeuze-cleanup = "betelgeuze_cleanup.cli:main"

[tool.setuptools.packages.find]
include = ["betelgeuze_product*", "betelgeuze_cameo*", "betelgeuze_cleanup*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("Proprietary\n", encoding="utf-8")
    (root / "requirements.txt").write_text("numpy==1.26.4\n", encoding="utf-8")
    for name in ("requirements-api.txt", "requirements-deploy.txt", "requirements-optional.txt", "requirements-train.txt"):
        (root / name).write_text("# optional profile\n", encoding="utf-8")
    runs = root / "runs"
    runs.mkdir()
    (runs / "local_delivery_requirements_lock_current.txt").write_text("numpy==1.26.4\n", encoding="utf-8")
    (runs / "local_delivery_requirements_lock_current.md").write_text("# Requirements Lock\n", encoding="utf-8")
    (runs / "local_delivery_requirements_lock_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "generated_at": "2026-06-03T00:00:00+09:00",
                    "declared_count": 1,
                    "missing_count": 0,
                    "loose_source_requirement_count": 0,
                    "missing_input_file_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "local_delivery_environment_manifest_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "python_version": "3.12.2",
                    "git_short_commit": "abc1234",
                    "requirements_lock_complete": True,
                    "requirements_lock_txt_sha256": "abc123",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_service_boundary_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_service_boundary_contract_ready",
                    "service_boundary_ready": True,
                    "api_route_count": 14,
                    "cli_command_count": 11,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_api_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_api_contract_ready",
                    "api_contract_ready": True,
                    "missing_route_count": 0,
                    "status_response_missing_key_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_bundle_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_bundle_contract_ready",
                    "bundle_assembled": True,
                    "bundle_validation_passed": True,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_delivery_evidence_contract_current.json").write_text(
        json.dumps({"summary": {"status": "product_delivery_evidence_contract_ready", "delivery_ready_claim_allowed": True}})
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_pilot_packet_contract_current.json").write_text(
        json.dumps({"summary": {"status": "product_pilot_packet_ready", "pilot_delivery_ready": True, "bundle_validation_passed": True}})
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_public_benchmark_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_public_benchmark_contract_ready",
                    "public_benchmark_validation_ready": True,
                    "required_suite_count": 5,
                    "ready_required_suite_count": 5,
                    "blocked_suite_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"

    mod.main(["--root", str(root), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_commercial_independence_gate_ready"
    assert payload["summary"]["product_cli_surface_present"] is True
    assert payload["summary"]["pyproject_packaging_metadata_present"] is True
    assert payload["summary"]["console_entrypoint_targets_present"] is True
    assert payload["summary"]["reproducible_install_manifest_ready"] is True
    assert payload["summary"]["product_service_boundary_ready"] is True
    assert payload["summary"]["product_api_contract_ready"] is True
    assert payload["summary"]["local_self_hosted_operation_ready"] is True
    assert payload["summary"]["external_saas_runtime_dependency_count"] == 0
    assert payload["summary"]["local_delivery_bundle_ready"] is True
    assert payload["summary"]["public_benchmark_evidence_ready"] is True
    csv_text = out_csv.read_text(encoding="utf-8")
    md_text = out_md.read_text(encoding="utf-8")
    assert csv_text.startswith("check,status,")
    assert "local_self_hosted_operation_ready" in csv_text
    assert "Product Commercial Independence Gate" in md_text
    assert "local_self_hosted_operation_ready" in md_text
