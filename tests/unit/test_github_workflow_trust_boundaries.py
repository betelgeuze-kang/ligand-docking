from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from tools.product.github_workflow_trust_boundaries import (
    PR_WORKFLOWS,
    TRUSTED_WORKFLOWS,
    audit_workflow_trust_boundaries,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def _copy_repository_policy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(WORKFLOW_DIR, root / ".github" / "workflows")
    return root


def _mutate(root: Path, workflow_name: str, before: str, after: str) -> None:
    path = root / ".github" / "workflows" / workflow_name
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")


def test_repository_workflow_trust_boundary_policy_is_ready() -> None:
    assert audit_workflow_trust_boundaries(ROOT) == []


@pytest.mark.parametrize("workflow_name", sorted(PR_WORKFLOWS))
def test_pull_request_workflow_files_are_hosted_only(workflow_name: str) -> None:
    path = WORKFLOW_DIR / workflow_name
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert set(workflow["on"]) == {"pull_request"}
    assert "self-hosted" not in path.read_text(encoding="utf-8").lower()
    assert all(job["runs-on"] == "ubuntu-latest" for job in workflow["jobs"].values())


def test_h4_hosted_workflow_covers_tier_alpha_runtime_binding_contract() -> None:
    workflow = yaml.load(
        (WORKFLOW_DIR / "ci-api-h4-hosted.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    pull_request_paths = set(workflow["on"]["pull_request"]["paths"])
    adjacent_test_command = next(
        step["run"]
        for step in workflow["jobs"]["api-security"]["steps"]
        if step["name"] == "Run adjacent API regressions"
    )

    for required_source in (
        "tools/product/run_tier_alpha_adrb2_dispatch_smoke.py",
        "tools/product/build_api_customer_flow_release_evidence.py",
        "tools/product/build_product_release_source_of_truth_gate.py",
        "tools/product/run_product_release_current_refresh.py",
        "scripts/normalize_product_image_smoke_artifact_ownership.sh",
    ):
        assert required_source in pull_request_paths
    for required_test in (
        "tests/unit/test_api_worker_deploy_artifacts.py",
        "tests/unit/test_build_api_customer_flow_release_evidence.py",
        "tests/unit/test_build_product_release_source_of_truth_gate.py",
        "tests/unit/test_run_product_release_current_refresh.py",
    ):
        assert required_test in pull_request_paths
        assert required_test in adjacent_test_command


@pytest.mark.parametrize("workflow_name", sorted(TRUSTED_WORKFLOWS))
def test_trusted_workflow_files_have_no_pull_request_trigger(workflow_name: str) -> None:
    workflow = yaml.load(
        (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    assert "pull_request" not in workflow["on"]
    assert "pull_request_target" not in workflow["on"]


def test_policy_rejects_a_self_hosted_pull_request_runner(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-api-worker.yml",
        "runs-on: ubuntu-latest",
        "runs-on: [self-hosted, linux]",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert "product-api-worker.yml:api-worker-contract:runner_not_hosted" in errors
    assert "product-api-worker.yml:api-worker-contract:pr_runner_not_hosted" in errors


def test_policy_rejects_an_extra_trusted_condition_branch(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-api-worker-trusted.yml",
        "${{ vars.TRUSTED_SELF_HOSTED_CI_ENABLED == 'true'",
        "${{ always() || vars.TRUSTED_SELF_HOSTED_CI_ENABLED == 'true'",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert (
        "product-api-worker-trusted.yml:"
        "api-worker-contract-trusted:condition_not_allowlisted"
    ) in errors


def test_policy_rejects_pull_request_on_a_trusted_workflow(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-image-smoke-trusted.yml",
        "on:\n  push:",
        "on:\n  pull_request: {}\n  push:",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert "product-image-smoke-trusted.yml:unexpected_triggers" in errors
    assert "product-image-smoke-trusted.yml:untrusted_trigger" in errors


def test_policy_rejects_workspace_bound_trusted_artifacts(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-image-smoke-trusted.yml",
        "${RUNNER_TEMP}/product-image-build-",
        "${GITHUB_WORKSPACE}/product-image-build-",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert (
        "product-image-smoke-trusted.yml:"
        "product-image-build-smoke-trusted:workspace_artifact_root"
    ) in errors


def test_policy_rejects_workspace_bound_artifact_uploads(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-image-smoke-trusted.yml",
        "${{ runner.temp }}/product-image-build-${{ github.run_id }}",
        "${{ github.workspace }}/runs/product-image-build-${{ github.run_id }}",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert (
        "product-image-smoke-trusted.yml:"
        "product-image-build-smoke-trusted:artifact_paths_not_allowlisted"
    ) in errors


def test_policy_rejects_a_mutable_action_tag(tmp_path: Path) -> None:
    root = _copy_repository_policy_fixture(tmp_path)
    _mutate(
        root,
        "product-image-smoke.yml",
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
        "actions/checkout@v4",
    )

    errors = audit_workflow_trust_boundaries(root)

    assert (
        "product-image-smoke.yml:"
        "product-image-build-smoke:action_not_sha_pinned:actions/checkout@v4"
    ) in errors
