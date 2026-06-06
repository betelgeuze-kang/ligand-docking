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
    row = payload["rows"][0]
    assert row["profile_id"] == "operator_profile"
    assert row["enabled"] is False
    assert row["runner_exists"] is True
    assert row["runner_allowlisted"] is True
    assert row["runner_script_sha256"]
    assert row["ready_for_operator_review"] is True

    template = json.loads(Path(row["evidence_template"]).read_text(encoding="utf-8"))
    assert template["profile_id"] == "operator_profile"
    assert template["input_contract_reviewed"] is False
    assert template["output_contract_reviewed"] is False
    assert template["claim_boundary_reviewed"] is False
    assert template["gate_policy_reviewed"] is False
    assert template["fake_result_emission_forbidden"] is False
    assert template["required_operator_action"]


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
    assert len(enabled_rows) == 2
    assert all(row["runner_allowlisted"] and row["runner_exists"] for row in enabled_rows)

    validation = validate_profiles(Path("config/api_validated_runner_profiles"))
    assert validation["status"] == "pass"
    assert validation["enabled_profile_count"] == 2
