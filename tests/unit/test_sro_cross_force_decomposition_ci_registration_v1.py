"""Hosted registration contracts; no molecular inputs or numerical execution."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shlex

import pytest
import yaml

from tools.product.github_workflow_trust_boundaries import audit_workflow_trust_boundaries

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ".github/workflows/ci-sro-cross-force-decomposition-diagnostic.yml"
SOURCE = "benchmarks/oracles/sro_cross_force_decomposition_diagnostic_v1.py"
HELPER = "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py"
FIXED_SOURCE = "betelgeuze_product/cpu_refinement_v1_2/fixed_receptor.py"
MOCK_TEST = "tests/unit/test_sro_cross_force_decomposition_diagnostic_v1.py"
REGISTRATION_TEST = "tests/unit/test_sro_cross_force_decomposition_ci_registration_v1.py"
DOCUMENT = "docs/research/sro_cross_force_decomposition_diagnostic_plan_20261001.md"
POLICY = "tools/product/github_workflow_trust_boundaries.py"
POLICY_TEST = "tests/unit/test_github_workflow_trust_boundaries.py"
CHECKOUT = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SETUP = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
INSTALL = ["python", "-m", "pip", "install", "pytest==8.3.5", "ruff==0.11.13", "PyYAML==6.0.3"]
LINT = ["python", "-m", "ruff", "check", "--isolated", "--no-cache", SOURCE, MOCK_TEST, REGISTRATION_TEST]
MOCK = ["python", "-m", "pytest", "--rootdir=$PWD", "-c", "/dev/null", "--noconftest",
        "-p", "no:cacheprovider", "-W", "error", "-q", MOCK_TEST, REGISTRATION_TEST]


def load_workflow():
    return yaml.load((ROOT / WORKFLOW).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def tokens(command):
    return shlex.split(command.replace("\\\n", " "))


def assert_hosted_mock_contract(workflow):
    """Closed command/dependency sets exclude body reads and numerical tools."""
    assert set(workflow) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert workflow["name"] == "ci-sro-cross-force-decomposition-diagnostic"
    assert set(workflow["on"]) == {"pull_request", "workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"] in (None, "")
    assert set(workflow["on"]["pull_request"]) == {"paths"}
    paths = workflow["on"]["pull_request"]["paths"]
    assert len(paths) == 9 and set(paths) == {SOURCE, HELPER, FIXED_SOURCE, MOCK_TEST, REGISTRATION_TEST,
                                           DOCUMENT, POLICY, POLICY_TEST, WORKFLOW}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "ci-sro-cross-force-decomposition-diagnostic-${{ github.event.pull_request.number || github.ref }}",
        "cancel-in-progress": "true"}
    assert set(workflow["jobs"]) == {"lint-and-mock-contract"}
    job = workflow["jobs"]["lint-and-mock-contract"]
    assert set(job) == {"runs-on", "timeout-minutes", "env", "steps"}
    assert job["runs-on"] == "ubuntu-latest" and job["timeout-minutes"] == "10"
    assert job["env"] == {"PYTHONPATH": ".", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                          "PYTHONDONTWRITEBYTECODE": "1", "BETELGEUZE_PRODUCT_TEST_ARTIFACT_BOOTSTRAP": "disabled"}
    steps = job["steps"]
    assert len(steps) == 5
    assert steps[0] == {"uses": CHECKOUT, "with": {"persist-credentials": "false", "clean": "true"}}
    assert steps[1] == {"uses": SETUP, "with": {"python-version": "3.11"}}
    for step, name, command in zip(steps[2:], (
        "Install pinned lint and mock-test dependencies", "Lint the benchmark diagnostic and mock contracts",
        "Verify mock-only diagnostic and workflow contracts"), (INSTALL, LINT, MOCK), strict=True):
        assert set(step) == {"name", "run"} and step["name"] == name
        assert tokens(step["run"]) == command


def test_registered_workflow_is_hosted_pinned_and_mock_only():
    assert_hosted_mock_contract(load_workflow())


def test_repository_workflow_trust_policy_includes_new_workflow_without_exceptions():
    assert audit_workflow_trust_boundaries(ROOT) == []


def test_diagnostic_remains_in_benchmark_only_source_role():
    assert (ROOT / SOURCE).is_file() and (ROOT / HELPER).is_file()
    assert not (ROOT / "tools/research/sro_cross_force_decomposition_diagnostic_v1.py").exists()
    assert not (ROOT / "tools/product/sro_cross_force_decomposition_diagnostic_v1.py").exists()


@pytest.mark.parametrize("mutation", ["numerical_execute", "numerical_prepare", "data_read", "archive_read",
    "torch_dependency", "openmm_dependency", "upload", "secret", "self_hosted", "write_permission",
    "credentials", "mutable_action", "conftest", "plugins", "ruff_config", "product_tool",
    "extra_job", "extra_step", "data_trigger", "pull_request_target"])
def test_contract_rejects_numerical_data_product_and_trust_leakage(mutation):
    workflow = deepcopy(load_workflow())
    job = workflow["jobs"]["lint-and-mock-contract"]
    steps = job["steps"]
    if mutation == "numerical_execute":
        steps[4]["run"] += "\npython " + SOURCE + " execute --numerical-phase-authorized"
    elif mutation == "numerical_prepare":
        steps[4]["run"] += "\npython " + SOURCE + " prepare --r2 /unopened/campaign"
    elif mutation == "data_read":
        steps[4]["run"] += "\ncat /unopened/reference/receipt.json"
    elif mutation == "archive_read":
        steps[4]["run"] += "\nunzip /unopened/old-product.whl"
    elif mutation in {"torch_dependency", "openmm_dependency"}:
        steps[2]["run"] += " " + ("torch==2.10.0" if mutation == "torch_dependency" else "openmm==8.2.0")
    elif mutation == "upload":
        steps.append({"uses": "actions/upload-artifact@" + "a" * 40, "with": {"path": "/unopened/numerical"}})
    elif mutation == "secret":
        job["env"]["TOKEN"] = "${{ secrets.CAMPAIGN_TOKEN }}"
    elif mutation == "self_hosted":
        job["runs-on"] = ["self-hosted", "linux"]
    elif mutation == "write_permission":
        workflow["permissions"]["contents"] = "write"
    elif mutation == "credentials":
        steps[0]["with"]["persist-credentials"] = "true"
    elif mutation == "mutable_action":
        steps[1]["uses"] = "actions/setup-python@v6"
    elif mutation == "conftest":
        steps[4]["run"] = steps[4]["run"].replace("--noconftest", "")
    elif mutation == "plugins":
        job["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "0"
    elif mutation == "ruff_config":
        steps[3]["run"] = steps[3]["run"].replace("--isolated", "")
    elif mutation == "product_tool":
        steps[3]["run"] = steps[3]["run"].replace(SOURCE, "tools/research/sro_cross_force_decomposition_diagnostic_v1.py")
    elif mutation == "extra_job":
        workflow["jobs"]["numerical"] = {"runs-on": "ubuntu-latest", "steps": [{"run": "torch calculation"}]}
    elif mutation == "extra_step":
        steps.append({"run": "python -m pytest tests/integration"})
    elif mutation == "data_trigger":
        workflow["on"]["pull_request"]["paths"].append("runs/frozen/**")
    else:
        workflow["on"]["pull_request_target"] = {}
    with pytest.raises(AssertionError):
        assert_hosted_mock_contract(workflow)
