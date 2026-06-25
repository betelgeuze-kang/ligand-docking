from __future__ import annotations

import json
from pathlib import Path


def test_build_api_runner_profile_enablement_work_order_writes_templates(tmp_path: Path) -> None:
    from tools.product.build_api_runner_profile_enablement_work_order import build_work_order

    runner = tmp_path / "runner.py"
    runner.write_text("print('ok')\n", encoding="utf-8")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "operator_profile.json").write_text(
        json.dumps(
            {
                "profile_id": "operator_profile",
                "enabled": False,
                "runner_script": str(runner),
                "arguments": ["--out-json", "{result_file}"],
                "result_file_template": "{job_results_dir}/runner_result.json",
                "claim_boundary": "unit test disabled profile",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    import tools.product.build_api_runner_profile_enablement_work_order as work_order

    original_allowlist = set(work_order.ALLOWED_RUNNER_SCRIPTS)
    work_order.ALLOWED_RUNNER_SCRIPTS.add(str(runner))
    try:
        payload = build_work_order(
            profiles_dir,
            evidence_dir=tmp_path / "evidence",
            write_templates=True,
        )
    finally:
        work_order.ALLOWED_RUNNER_SCRIPTS.clear()
        work_order.ALLOWED_RUNNER_SCRIPTS.update(original_allowlist)

    assert payload["status"] == "ready"
    assert payload["work_order_only"] is True
    assert payload["native_evidence_bundle_required_profile_count"] == 0
    assert payload["native_evidence_bundle_missing_profile_count"] == 0
    assert payload["first_native_evidence_bundle_missing_profile_id"] == ""
    row = payload["rows"][0]
    assert row["profile_id"] == "operator_profile"
    assert row["enabled"] is False
    assert row["runner_exists"] is True
    assert row["runner_allowlisted"] is True
    assert row["runner_script_sha256"]
    assert row["ready_for_operator_review"] is True
    assert row["evidence_bundle_template"] == ""
    assert row["evidence_bundle_template_declared"] is False
    assert row["delivery_oriented"] is False
    assert row["requires_native_evidence_bundle"] is False
    assert "evidence_bundle_template" not in row["next_required_step"]

    template = json.loads(Path(row["evidence_template"]).read_text(encoding="utf-8"))
    assert template["profile_id"] == "operator_profile"
    assert template["input_contract_reviewed"] is False
    assert template["output_contract_reviewed"] is False
    assert template["claim_boundary_reviewed"] is False
    assert template["gate_policy_reviewed"] is False
    assert template["fake_result_emission_forbidden"] is False
    assert template["required_operator_action"]
    assert "evidence_bundle_template" not in template["required_operator_action"]


def test_repo_api_runner_profile_enablement_work_order_reflects_operator_approved_profiles(
    tmp_path: Path,
) -> None:
    from tools.product.build_api_runner_profile_enablement_work_order import build_work_order
    from tools.product.validate_api_runner_profiles import validate_profiles

    payload = build_work_order(
        Path("config/api_validated_runner_profiles"),
        evidence_dir=tmp_path / "evidence",
        write_templates=True,
    )

    assert payload["profile_count"] >= 3
    example_rows = [row for row in payload["rows"] if "example" in row["profile_id"]]
    assert example_rows
    assert all(row["enabled"] is False for row in example_rows)
    enabled_rows = [row for row in payload["rows"] if row["enabled"]]
    assert len(enabled_rows) == 4
    assert payload["native_evidence_bundle_required_profile_count"] == 4
    assert payload["native_evidence_bundle_missing_profile_count"] == 0
    assert payload["first_native_evidence_bundle_missing_profile_id"] == ""
    assert all(row["runner_allowlisted"] and row["runner_exists"] for row in enabled_rows)
    assert sum(1 for row in enabled_rows if row["delivery_oriented"] is True) == 3
    assert all(row["requires_native_evidence_bundle"] is True for row in enabled_rows)
    assert all(row["evidence_bundle_template_declared"] is True for row in enabled_rows)
    assert all(
        "evidence_bundle_template" not in row["next_required_step"] for row in enabled_rows
    )

    validation = validate_profiles(Path("config/api_validated_runner_profiles"))
    assert validation["status"] == "pass"
    assert validation["enabled_profile_count"] == 4


def test_build_work_order_marks_native_bundle_action_for_delivery_oriented_disabled_profile(
    tmp_path: Path,
) -> None:
    from tools.product.build_api_runner_profile_enablement_work_order import build_work_order

    runner = tmp_path / "runner.py"
    runner.write_text("print('ok')\n", encoding="utf-8")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "delivery_proxy.json").write_text(
        json.dumps(
            {
                "profile_id": "delivery_proxy",
                "enabled": False,
                "runner_script": str(runner),
                "arguments": ["--out-json", "{result_file}"],
                "result_file_template": "{job_results_dir}/runner_result.json",
                "claim_boundary": "delivery scope",
                "claim_scope": "restricted_local_delivery_proxy_refinement_only",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    import tools.product.build_api_runner_profile_enablement_work_order as work_order

    original_allowlist = set(work_order.ALLOWED_RUNNER_SCRIPTS)
    work_order.ALLOWED_RUNNER_SCRIPTS.add(str(runner))
    try:
        payload = build_work_order(
            profiles_dir,
            evidence_dir=tmp_path / "evidence",
            write_templates=True,
        )
    finally:
        work_order.ALLOWED_RUNNER_SCRIPTS.clear()
        work_order.ALLOWED_RUNNER_SCRIPTS.update(original_allowlist)

    row = payload["rows"][0]
    assert payload["native_evidence_bundle_required_profile_count"] == 1
    assert payload["native_evidence_bundle_missing_profile_count"] == 1
    assert payload["first_native_evidence_bundle_missing_profile_id"] == "delivery_proxy"
    assert row["enabled"] is False
    assert row["delivery_oriented"] is True
    assert row["requires_native_evidence_bundle"] is True
    assert row["evidence_bundle_template_declared"] is False
    assert "evidence_bundle_template" in row["next_required_step"]
    assert "evidence_bundle_template_missing" in row["next_required_step"]

    template = json.loads(Path(row["evidence_template"]).read_text(encoding="utf-8"))
    assert template["delivery_oriented"] is True
    assert template["requires_native_evidence_bundle"] is True
    assert template["evidence_bundle_template_declared"] is False
    assert "evidence_bundle_template" in template["required_operator_action"]


def test_build_work_order_reports_declared_native_bundle_for_enabled_delivery_profile(
    tmp_path: Path,
) -> None:
    from tools.product.build_api_runner_profile_enablement_work_order import build_work_order

    runner = tmp_path / "runner.py"
    runner.write_text("print('ok')\n", encoding="utf-8")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "delivery_native.json").write_text(
        json.dumps(
            {
                "profile_id": "delivery_native",
                "enabled": True,
                "runner_script": str(runner),
                "arguments": [
                    "--request-json",
                    "{request_json_path}",
                    "--out-json",
                    "{result_file}",
                    "--evidence-bundle",
                    "{evidence_bundle}",
                ],
                "result_file_template": "{job_results_dir}/runner_result.json",
                "claim_boundary": "delivery scope",
                "evidence_bundle_template": "{job_results_dir}/evidence_bundle.json",
                "claim_scope": "restricted_local_delivery_proxy_refinement_only",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    import tools.product.build_api_runner_profile_enablement_work_order as work_order

    original_allowlist = set(work_order.ALLOWED_RUNNER_SCRIPTS)
    work_order.ALLOWED_RUNNER_SCRIPTS.add(str(runner))
    try:
        payload = build_work_order(
            profiles_dir,
            evidence_dir=tmp_path / "evidence",
            write_templates=True,
        )
    finally:
        work_order.ALLOWED_RUNNER_SCRIPTS.clear()
        work_order.ALLOWED_RUNNER_SCRIPTS.update(original_allowlist)

    row = payload["rows"][0]
    assert payload["native_evidence_bundle_required_profile_count"] == 1
    assert payload["native_evidence_bundle_missing_profile_count"] == 0
    assert payload["first_native_evidence_bundle_missing_profile_id"] == ""
    assert row["enabled"] is True
    assert row["delivery_oriented"] is True
    assert row["requires_native_evidence_bundle"] is True
    assert row["evidence_bundle_template"] == "{job_results_dir}/evidence_bundle.json"
    assert row["evidence_bundle_template_declared"] is True
    assert "evidence_bundle_template" not in row["next_required_step"]

    template = json.loads(Path(row["evidence_template"]).read_text(encoding="utf-8"))
    assert template["evidence_bundle_template"] == "{job_results_dir}/evidence_bundle.json"
    assert template["evidence_bundle_template_declared"] is True
    assert "evidence_bundle_template" in template["required_operator_action"]
